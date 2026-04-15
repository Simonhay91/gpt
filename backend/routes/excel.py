"""Excel / CSV Assistant route"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime, timezone
import os
import uuid
import json
import logging
import tempfile
import io
import math
import pandas as pd
import anthropic

from db.connection import get_db
from middleware.auth import get_current_user
from routes.projects import check_project_access
from pathlib import Path

router = APIRouter()
logger = logging.getLogger(__name__)

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"

GENERATE_SYSTEM_PROMPT = """You are a data transformation assistant. The spreadsheet data is provided directly below — do not fetch anything externally.
Apply the user's instruction to the data and return ONLY a valid JSON object:
{"column_mapping": {"old": "new"}, "new_data": [[col1, col2, ...], [val1, val2, ...], ...], "message": "what was done"}
- new_data: first array = column names, remaining arrays = ALL data rows with transformations applied
- column_mapping: rename map (can be empty {})
- message: brief explanation in same language as instruction
- NEVER say you cannot do something — work only with the provided data
Return ONLY JSON, no markdown, no extra text."""

SYSTEM_PROMPT = """You are a data transformation assistant. You receive spreadsheet data directly in this message — ALL the data is already provided to you. You do NOT need to fetch anything from external sources.

Your ONLY job is to transform the provided data according to the user's instruction.

Return ONLY a valid JSON object with this exact structure:
{"action": "modify_columns"|"add_column"|"translate"|"filter"|"other", "column_mapping": {"old_name": "new_name"}, "new_data": [[row1values], [row2values], ...], "message": "explanation of what was done"}

Rules:
- new_data must contain ALL rows from the original data with transformations applied
- If column names changed, include new column names as the FIRST array in new_data
- If only renaming columns with no data changes, new_data can be empty []
- column_mapping maps old column name to new column name
- For translation tasks: translate the column headers and/or cell values as instructed
- NEVER say you cannot do something — work only with the data given
- Respond in the same language as the user instruction
- Return ONLY the JSON object, no markdown fences, no explanation outside JSON"""


def read_dataframe(contents: bytes, filename: str) -> pd.DataFrame:
    ext = filename.rsplit(".", 1)[-1].lower()
    buf = io.BytesIO(contents)
    if ext == "csv":
        return pd.read_csv(buf)
    elif ext in ("xlsx", "xls"):
        return pd.read_excel(buf)
    else:
        raise ValueError(f"Unsupported format: {ext}")


def apply_transformations(df: pd.DataFrame, claude_resp: dict) -> pd.DataFrame:
    column_mapping = claude_resp.get("column_mapping") or {}
    new_data = claude_resp.get("new_data") or []

    result = df.copy()

    # Rename columns if mapping provided
    if column_mapping:
        result = result.rename(columns={k: v for k, v in column_mapping.items() if k in result.columns})

    # Rebuild data if new_data provided
    if new_data:
        current_cols = list(result.columns)
        data_start = 0

        # Check if first row is headers (all strings, not matching current data)
        if len(new_data) > 0:
            first_row = new_data[0]
            if (len(first_row) > 0 and
                    all(isinstance(v, str) for v in first_row) and
                    len(new_data) > 1):
                # First row looks like column headers
                current_cols = first_row
                data_start = 1

        try:
            result = pd.DataFrame(new_data[data_start:], columns=current_cols)
        except Exception:
            # Fallback: use original columns
            result = pd.DataFrame(new_data, columns=list(df.columns))

    return result


@router.post("/chats/{chat_id}/excel-process")
async def excel_process(
    chat_id: str,
    file: UploadFile = File(...),
    instruction: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """Process Excel/CSV file using AI instructions"""
    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    filename = file.filename or "file.xlsx"
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ("xlsx", "xls", "csv"):
        raise HTTPException(status_code=400, detail="Unsupported format. Use xlsx, xls or csv")

    # Read into DataFrame
    try:
        df = read_dataframe(contents, filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {str(e)}")

    # Build context for Claude
    columns_info = list(df.columns)
    preview_rows = df.head(5).values.tolist()
    structure_info = (
        f"File: {filename}\n"
        f"Rows: {len(df)}, Columns: {len(df.columns)}\n"
        f"Column names: {columns_info}\n"
        f"First 5 rows sample:\n{df.head(5).to_string(index=False)}\n\n"
        f"User instruction: {instruction}"
    )

    # Call Claude
    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": structure_info}]
        )
        raw_text = response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)[:100]}")

    # Parse Claude JSON response
    try:
        # Strip markdown fences if present
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        claude_resp = json.loads(raw_text.strip())
    except json.JSONDecodeError as e:
        logger.error(f"Claude returned invalid JSON: {raw_text[:200]}")
        raise HTTPException(status_code=500, detail="AI returned invalid response. Please try again.")

    # Apply transformations
    try:
        result_df = apply_transformations(df, claude_resp)
    except Exception as e:
        logger.error(f"DataFrame transformation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply transformations: {str(e)[:100]}")

    # Save result to uploads/ (permanent)
    file_id = str(uuid.uuid4())
    result_path = str(ROOT_DIR / "uploads" / f"excel_{file_id}.xlsx")
    try:
        result_df.to_excel(result_path, index=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save result: {str(e)[:100]}")

    # Build preview — sanitize NaN/Inf which are not JSON serializable
    import math

    def sanitize(val):
        if val is None:
            return None
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val

    preview_cols = [str(c) for c in result_df.columns]
    preview_data = [
        [sanitize(v) for v in row]
        for row in result_df.head(5).values.tolist()
    ]

    return {
        "message": claude_resp.get("message", "Processing complete"),
        "action": claude_resp.get("action", "other"),
        "download_url": f"/api/excel/download/{file_id}",
        "rows": len(result_df),
        "columns": len(result_df.columns),
        "preview_columns": preview_cols,
        "preview": preview_data
    }


@router.post("/chats/{chat_id}/excel-generate")
async def excel_generate(
    chat_id: str,
    request: dict,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Generate/transform Excel from a project source using AI instructions"""
    instruction = request.get("instruction", "").strip()
    source_id = request.get("source_id", "").strip()

    if not instruction:
        raise HTTPException(status_code=400, detail="instruction is required")
    if not source_id:
        raise HTTPException(status_code=400, detail="source_id is required")

    # Verify chat exists and get project_id
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    project_id = chat.get("projectId")
    if not project_id:
        raise HTTPException(status_code=400, detail="Chat is not part of a project")

    # Verify project access
    await check_project_access(current_user, project_id, required_role="viewer")

    # Find the source
    source = await db.sources.find_one({"id": source_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.get("storagePath"):
        raise HTTPException(status_code=400, detail="Source has no file on disk")

    # Read file
    file_path = UPLOAD_DIR / source["storagePath"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Source file not found on disk")

    ext = source["storagePath"].rsplit(".", 1)[-1].lower()
    try:
        df = pd.read_excel(file_path) if ext in ("xlsx", "xls") else pd.read_csv(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {str(e)[:100]}")

    # Build structure for Claude (max 500 rows)
    structure = (
        f"File: {source.get('originalName', 'file')}\n"
        f"Rows: {len(df)}, Columns: {len(df.columns)}\n"
        f"Columns: {list(df.columns)}\n"
        f"Data (max 500 rows):\n{df.head(500).to_string(index=False)}"
    )

    # Call Claude
    try:
        client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=GENERATE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Instruction: {instruction}\n\n{structure}"}]
        )
        raw_text = response.content[0].text.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)[:100]}")

    # Parse JSON
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    try:
        result_data = json.loads(raw_text.strip())
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI returned invalid response. Please try again.")

    # Apply transformations
    new_data = result_data.get("new_data", [])
    if new_data and len(new_data) > 1:
        cols = new_data[0]
        rows_data = new_data[1:]
        result_df = pd.DataFrame(rows_data, columns=cols)
    else:
        col_map = result_data.get("column_mapping", {})
        result_df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Save to uploads/ (permanent)
    file_id = str(uuid.uuid4())
    result_path = str(ROOT_DIR / "uploads" / f"excel_{file_id}.xlsx")
    try:
        result_df.to_excel(result_path, index=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save result: {str(e)[:100]}")

    def _sanitize(v):
        if v is None:
            return None
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v

    preview_cols = [str(c) for c in result_df.columns]
    preview_data = [[_sanitize(v) for v in row] for row in result_df.head(5).values.tolist()]

    return {
        "message": result_data.get("message", "Done"),
        "file_id": file_id,
        "rows": len(result_df),
        "columns": len(result_df.columns),
        "preview_columns": preview_cols,
        "preview": preview_data
    }


@router.get("/excel/download/{file_id}")
async def download_excel(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Download processed Excel file"""
    try:
        uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID")

    result_path = str(ROOT_DIR / "uploads" / f"excel_{file_id}.xlsx")
    if not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="Файл не найден. Попросите AI создать файл заново.")

    return FileResponse(
        path=result_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="result.xlsx"
    )
