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

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"


def is_excel_trigger(message_content: str) -> bool:
    """Check if message explicitly requests Excel generation."""
    return any(phrase in message_content.lower() for phrase in EXCEL_TRIGGER_PHRASES)


def _sanitize_value(v):
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


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

        # Two-step flow: first time → ask clarifying questions
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
