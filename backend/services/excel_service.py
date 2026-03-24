"""Excel file generation service"""
import json
import math
import uuid
import logging
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

EXCEL_MIME_TYPES = [
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
    "application/csv",
]

EXCEL_TRIGGER_PHRASES = [
    "generate excel", "create excel", "make excel",
    "сгенерируй excel", "создай excel", "сделай excel",
    "download excel", "скачать excel",
    # edit / modify phrases
    "edit", "modify", "update", "change", "fix",
    "edit ara", "poxi", "փոխիր", "խմբագրիր", "թարմացրու",
    "редактируй", "измени", "обнови", "исправь",
    "readme", "sheet", "arajin togh", "առաջին տող",
]

# Subset of EXCEL_TRIGGER_PHRASES that indicate targeted cell editing
# (not full regeneration). Checked first — these bypass the clarification flow.
EXCEL_EDIT_PHRASES = [
    "edit", "modify", "update", "change", "fix",
    "edit ara", "poxi", "փոխիր", "խմբագրիր", "թարմացրու",
    "редактируй", "измени", "обнови", "исправь",
    "readme", "sheet", "arajin togh", "առաջին տող",
]

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"


def is_excel_trigger(message_content: str) -> bool:
    """Check if message explicitly requests Excel generation or editing."""
    return any(phrase in message_content.lower() for phrase in EXCEL_TRIGGER_PHRASES)


def is_edit_trigger(message_content: str) -> bool:
    """Check if message requests targeted cell editing (not full regeneration)."""
    return any(phrase in message_content.lower() for phrase in EXCEL_EDIT_PHRASES)


def _sanitize_value(v):
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


async def targeted_excel_edit(source_file_path: str, instruction: str, claude_client) -> tuple:
    """Edit specific cells in Excel without destroying formulas and structure."""
    import openpyxl

    # 1. Ask Claude which cells to change
    analysis_response = claude_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=(
            "You are an Excel cell editor. "
            "The user's instruction may be in Armenian, Russian, or English — understand it regardless of language.\n"
            "Common operations: \"poxi/փոխիր/замени\" = replace, \"gri/գրիր/напиши\" = write/set, "
            "\"avelacru/ավելացրու/добавь\" = add, \"jnjel/ջնջել/удали\" = delete/clear.\n"
            "Return ONLY a JSON array of cell edits — no markdown, no explanation:\n"
            "[{\"sheet\": \"README\", \"cell\": \"A4\", \"value\": \"New Value\"}, ...]\n"
            "Rules:\n"
            "- Only edit cells that need to change based on the instruction\n"
            "- Do not touch formulas, only static text/values\n"
            "- Return [] if instruction is unclear or no edits are needed"
        ),
        messages=[{"role": "user", "content": f"Instruction: {instruction}"}]
    )

    raw = analysis_response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        edits = json.loads(raw.strip())
    except json.JSONDecodeError:
        logger.warning(f"targeted_excel_edit: Claude returned invalid JSON: {raw[:200]}")
        return None, None, "Could not determine what to edit."

    if not edits:
        return None, None, "Could not determine what to edit."

    # 2. Apply edits via openpyxl (preserves formulas and structure)
    wb = openpyxl.load_workbook(source_file_path)
    applied = []
    for edit in edits:
        sheet_name = edit.get("sheet")
        cell = edit.get("cell")
        value = edit.get("value")
        if sheet_name and cell and sheet_name in wb.sheetnames:
            wb[sheet_name][cell] = value
            applied.append(edit)
        else:
            logger.warning(f"targeted_excel_edit: skipped invalid edit {edit}")

    if not applied:
        return None, None, "No valid edits could be applied."

    # 3. Save to /tmp/
    file_id = str(uuid.uuid4())
    output_path = f"/tmp/excel_result_{file_id}.xlsx"
    wb.save(output_path)
    print(f"[EXCEL EDIT DEBUG] file_id={file_id}, output_path={output_path}, edits={edits}")

    preview = {
        "columns": ["sheet", "cell", "value"],
        "rows": [[e.get("sheet"), e.get("cell"), e.get("value")] for e in applied],
        "total_rows": len(applied),
        "message": f"Edited {len(applied)} cell(s).",
    }
    return file_id, preview, f"Done. Edited {len(applied)} cell(s)."


async def maybe_generate_excel(
    db,
    chat_id: str,
    project_id: str,
    active_source_ids: list,
    message_content: str,
    claude_client,
    current_response_text: str
) -> Tuple[Optional[str], Optional[dict], str]:
    """
    Attempt to generate an Excel file if conditions are met.
    Returns (excel_file_id, excel_preview, response_text).
    If no Excel should be generated, returns (None, None, current_response_text).
    """
    if not project_id or not active_source_ids:
        return None, None, current_response_text

    if not is_excel_trigger(message_content):
        return None, None, current_response_text

    try:
        excel_source = await db.sources.find_one(
            {"id": {"$in": active_source_ids}, "mimeType": {"$in": EXCEL_MIME_TYPES}},
            {"_id": 0}
        )
        if not excel_source:
            return None, None, current_response_text

        # ── Targeted edit path (skips clarification flow) ──
        if is_edit_trigger(message_content):
            if not excel_source.get("storagePath"):
                return None, None, current_response_text
            edit_file_path = UPLOAD_DIR / excel_source["storagePath"]
            if not edit_file_path.exists():
                return None, None, current_response_text
            try:
                return await targeted_excel_edit(str(edit_file_path), message_content, claude_client)
            except Exception as edit_err:
                logger.error(f"targeted_excel_edit error: {edit_err}")
                return None, None, current_response_text

        # ── Full generation path: two-step flow with clarification ──
        recent_messages = await db.messages.find(
            {"chatId": chat_id},
            {"_id": 0, "role": 1, "content": 1}
        ).sort("createdAt", -1).limit(3).to_list(3)

        has_clarification = any(
            "excel" in str(m.get("content", "")).lower() and m.get("role") == "assistant"
            for m in recent_messages
        )

        if not has_clarification:
            try:
                clarif_resp = claude_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=512,
                    system=(
                        "EXCEL CLARIFICATION REQUIRED: The user wants to generate an Excel file. "
                        "DO NOT generate Excel yet. Ask these 3 clarifying questions in the user's language "
                        "(Armenian, Russian, or English based on their message):\n"
                        "1. What data/columns should be included\n"
                        "2. Approximately how many rows\n"
                        "3. What is the purpose of the file\n"
                        "Keep it short and friendly. Do not generate any file or code."
                    ),
                    messages=[{"role": "user", "content": message_content}]
                )
                return None, None, clarif_resp.content[0].text
            except Exception as clarif_err:
                logger.warning(f"Excel clarification call failed: {clarif_err}")
                return None, None, current_response_text

        if not excel_source.get("storagePath"):
            return None, None, current_response_text

        file_path = UPLOAD_DIR / excel_source["storagePath"]
        if not file_path.exists():
            return None, None, current_response_text

        ext = excel_source["storagePath"].rsplit(".", 1)[-1].lower()
        df = pd.read_excel(file_path) if ext in ("xlsx", "xls") else pd.read_csv(file_path)

        structure = (
            f"File: {excel_source.get('originalName', 'file')}\n"
            f"Rows: {len(df)}, Columns: {len(df.columns)}\n"
            f"Columns: {list(df.columns)}\n"
            f"Data (max 200 rows):\n{df.head(200).to_string(index=False)}"
        )

        excel_response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=(
                "You are a data transformation assistant. "
                "The spreadsheet data is provided directly below — do not fetch anything externally.\n"
                "The user's instruction may be in Armenian, Russian, or English — understand it regardless of language.\n"
                "Common operations: \"poxi/փոխիր/замени\" = replace/rename, \"gri/գրիր/напиши\" = write/set value,\n"
                "\"avelacru/ավելացրու/добавь\" = add, \"jnjel/ջնջել/удали\" = delete.\n"
                "Apply the user's instruction to the data and return ONLY a valid JSON object:\n"
                '{"column_mapping": {"old": "new"}, "new_data": [[col1, col2, ...], [val1, val2, ...], ...], "message": "what was done"}\n'
                "- new_data: first array = column names, remaining arrays = ALL data rows with transformations applied\n"
                "- column_mapping: rename map (can be empty {})\n"
                "- message: brief explanation in same language as instruction\n"
                "- NEVER say you cannot do something — work only with the provided data\n"
                "Return ONLY JSON, no markdown, no extra text."
            ),
            messages=[{"role": "user", "content": f"Instruction: {message_content}\n\n{structure}"}]
        )

        raw = excel_response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result_data = json.loads(raw.strip())
        new_data = result_data.get("new_data", [])

        if new_data and len(new_data) > 1:
            cols = new_data[0]
            result_df = pd.DataFrame(new_data[1:], columns=cols)
        else:
            col_map = result_data.get("column_mapping", {})
            result_df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        file_id = str(uuid.uuid4())
        result_path = f"/tmp/excel_result_{file_id}.xlsx"
        result_df.to_excel(result_path, index=False)

        excel_preview = {
            "columns": [str(c) for c in result_df.columns],
            "rows": [[_sanitize_value(v) for v in row] for row in result_df.head(5).values.tolist()],
            "total_rows": len(result_df),
            "message": result_data.get("message", ""),
        }

        response_text = result_data.get("message", current_response_text)
        return file_id, excel_preview, response_text

    except Exception as excel_err:
        logger.error(f"Excel generation error: {excel_err}")
        return None, None, current_response_text
