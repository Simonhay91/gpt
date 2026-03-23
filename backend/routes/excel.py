"""Excel / CSV Assistant route"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from datetime import datetime, timezone
import os
import uuid
import json
import logging
import tempfile
import io
import pandas as pd
import anthropic

from db.connection import get_db
from middleware.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

SYSTEM_PROMPT = """You are an Excel/CSV data processing assistant. The user will provide a spreadsheet structure and instructions.
Return ONLY a JSON object with this exact structure:
{"action": "modify_columns"|"add_column"|"translate"|"filter"|"other", "column_mapping": {"old_name": "new_name"}, "new_data": [[row1values], [row2values], ...], "message": "explanation of what was done"}
The new_data array must contain ALL rows with the transformations applied.
If column names changed, include them as the first array in new_data.
If only renaming columns (no data changes), new_data can be empty.
Respond in the same language as the user instruction.
Return ONLY the JSON object, no markdown, no explanation outside the JSON."""


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

    # Save result to /tmp/
    file_id = str(uuid.uuid4())
    result_path = f"/tmp/excel_result_{file_id}.xlsx"
    try:
        result_df.to_excel(result_path, index=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save result: {str(e)[:100]}")

    # Build preview
    preview_cols = list(result_df.columns)
    preview_data = result_df.head(5).values.tolist()

    return {
        "message": claude_resp.get("message", "Processing complete"),
        "action": claude_resp.get("action", "other"),
        "download_url": f"/api/excel/download/{file_id}",
        "rows": len(result_df),
        "columns": len(result_df.columns),
        "preview_columns": preview_cols,
        "preview": preview_data
    }


@router.get("/excel/download/{file_id}")
async def download_excel(
    file_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """Download processed Excel file and delete it after serving"""
    # Sanitize file_id (only allow UUID format)
    try:
        uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID")

    result_path = f"/tmp/excel_result_{file_id}.xlsx"
    if not os.path.exists(result_path):
        raise HTTPException(status_code=404, detail="File not found or already downloaded")

    def _cleanup(path: str):
        try:
            os.remove(path)
        except Exception:
            pass

    background_tasks.add_task(_cleanup, result_path)

    return FileResponse(
        path=result_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="result.xlsx"
    )
