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
    # English
    "generate excel", "create excel", "make excel", "create spreadsheet",
    "make spreadsheet", "download excel", "export excel", "export to excel",
    # Russian
    "сгенерируй excel", "создай excel", "сделай excel", "скачать excel",
    "сгенерируй таблицу", "создай таблицу", "сделай таблицу",
    # Armenian romanized
    "excel generacru", "excel sarcru", "excel beri", "excel download ara",
    "avelacru excel", "excel poxi", "kercru excel",
    # Armenian unicode
    "excel ստեղծիր", "excel բեր", "excel ներբեռնիր",
    # edit / modify — English
    "edit", "modify", "update", "change", "fix",
    # edit / modify — Armenian romanized
    "edit ara", "poxi", "kpoxes", "popoxir",
    # edit / modify — Armenian unicode
    "փոխիր", "խմբագրիր", "թարմացրու", "ուղղիր",
    # edit / modify — Russian
    "редактируй", "измени", "обнови", "исправь",
    # Excel-specific row/column operations
    "arajin togh", "առաջին տող", "readme",
]

# Subset that indicates targeted cell editing (not full regeneration).
EXCEL_EDIT_PHRASES = [
    # English
    "edit", "modify", "update", "change", "fix",
    # Armenian romanized
    "edit ara", "poxi", "kpoxes", "popoxir",
    # Armenian unicode
    "փոխիր", "խմբագրիր", "թարմացրու", "ուղղիր",
    # Russian
    "редактируй", "измени", "обнови", "исправь",
    # Excel-specific
    "arajin togh", "առաջին տող", "readme",
]

# Messages matching these patterns must NEVER trigger Excel edit or generation.
EXCEL_EDIT_SKIP_WORDS = [
    # Sheet info queries — English
    "what sheets", "list sheets", "show sheets", "which sheet", "how many sheets",
    # Sheet info queries — Armenian romanized
    "inch sheeter", "inch sheet", "inch sheter", "sheeter ka", "sheet ka",
    "inch sheeter ka", "qani sheet", "qani sheeter", "sheeter uni", "sheet uni",
    "inch sheeter es tesnum", "inch sheet es tesnum",
    # Sheet info queries — Armenian unicode
    "ինչ sheet", "քանի sheet", "ինչ շիտ", "sheet-եր",
    # Sheet info queries — Russian
    "какие листы", "список листов", "сколько листов", "какие вкладки",
    # General question/info words — Armenian romanized
    "anhaskacox", "inch ka", "inch uni", "inch pes", "vonc",
    "asa indz", "tur indz", "cuyc tur", "cuic tur", "tesnem",
    # Russian question indicators
    "что такое", "что это", "как называется", "расскажи",
    # English info indicators
    "what is", "show me", "tell me", "list all",
]

# Minimum word count for edit trigger — short questions never trigger edit.
EXCEL_EDIT_MIN_WORDS = 4

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"


def is_excel_trigger(message_content: str) -> bool:
    """Check if message explicitly requests Excel generation or editing."""
    content_lower = message_content.lower()
    # Never trigger if skip words present
    if any(skip in content_lower for skip in EXCEL_EDIT_SKIP_WORDS):
        return False
    return any(phrase in content_lower for phrase in EXCEL_TRIGGER_PHRASES)


def is_edit_trigger(message_content: str) -> bool:
    """Check if message requests targeted cell editing (not full regeneration).

    Guards:
    1. Skip if message contains any EXCEL_EDIT_SKIP_WORDS.
    2. Skip if message is too short (< EXCEL_EDIT_MIN_WORDS words).
    3. Only trigger if an EXCEL_EDIT_PHRASES keyword is present.
    """
    content_lower = message_content.strip().lower()

    # Guard 1: explicit skip words
    if any(skip in content_lower for skip in EXCEL_EDIT_SKIP_WORDS):
        return False

    # Guard 2: too short — "anhaskacox es?" and similar must not edit
    if len(content_lower.split()) < EXCEL_EDIT_MIN_WORDS:
        return False

    # Guard 3: must contain an actual edit keyword
    return any(phrase in content_lower for phrase in EXCEL_EDIT_PHRASES)


def _sanitize_value(v):
    if v is None:
        return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


async def targeted_excel_edit(source_file_path: str, instruction: str, claude_client) -> tuple:
    """Edit specific cells in Excel without destroying formulas and structure."""
    import openpyxl

    if not source_file_path.endswith(('.xlsx', '.xlsm', '.xls')):
        return None, None, "Edit is only supported for Excel files (.xlsx). CSV files cannot be edited this way."

    # Build file structure so Claude knows what sheets/cells exist
    _wb_preview = openpyxl.load_workbook(source_file_path, read_only=True, data_only=True)
    file_structure = {}
    for _sheet_name in _wb_preview.sheetnames:
        _ws = _wb_preview[_sheet_name]
        _rows_preview = []
        for i, _row in enumerate(_ws.iter_rows(values_only=True)):
            if i >= 10:
                break
            _rows_preview.append(list(_row))
        file_structure[_sheet_name] = {"rows": _rows_preview, "max_row": _ws.max_row, "max_col": _ws.max_column}
    _wb_preview.close()

    print(f"[EXCEL EDIT DEBUG] Instruction: {instruction}")
    print(f"[EXCEL EDIT DEBUG] File structure sent to Claude: {json.dumps(file_structure, ensure_ascii=False)[:500]}")

    # 1. Ask Claude which cells to change
    analysis_response = claude_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=(
            "You are an Excel cell editor. "
            "The user's instruction may be in Armenian, Russian, or English — understand all three languages.\n"
            "Common operations by language:\n"
            "- Armenian: poxi/փոխիր = replace | gri/գրիր = write | avelacru/ավելացրու = add | jnjel/ջնջել = delete\n"
            "- Russian: замени = replace | напиши = write | добавь = add | удали = delete\n"
            "- English: change/replace = replace | write/set = write | add = add | delete/clear = delete\n"
            "Return ONLY a JSON array of cell edits — no markdown, no explanation.\n"
            "Rules:\n"
            "- Return JSON array of cell edits\n"
            '- Each edit: {"sheet": "...", "cell": "...", "value": "...", "color": "..."}\n'
            "- value is optional — omit if only changing color\n"
            "- color is optional — hex without #: Red=FF0000, Yellow=FFFF00, Green=00FF00\n"
            "- To color entire row: one edit per cell (A5, B5, C5 ... up to last column)\n"
            "- Armenian colors: karmir/կարմիր=FF0000, deghin/դեղին=FFFF00, kanahaguyn/կանաչագույն=00FF00\n"
            "- Russian colors: красный=FF0000, жёлтый=FFFF00, зелёный=00FF00\n"
            "- Formulas start with = and go in value field\n"
            "- Return [] only if truly impossible\n"
            "Return ONLY JSON array, no explanation."
        ),
        messages=[{"role": "user", "content": f"Instruction: {instruction}\n\nFile structure:\n{json.dumps(file_structure, ensure_ascii=False)}"}]
    )

    print(f"[EXCEL EDIT DEBUG] Claude raw response: {analysis_response.content[0].text}")

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
    from openpyxl.styles import PatternFill
    wb = openpyxl.load_workbook(source_file_path)
    applied = []
    for edit in edits:
        sheet_name = edit.get("sheet")
        cell = edit.get("cell")
        value = edit.get("value")
        color = edit.get("color")
        if sheet_name and cell and sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            if value is not None:
                ws[cell] = value
            if color:
                ws[cell].fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
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
    current_response_text: str,
    temp_file_path: Optional[str] = None,
) -> Tuple[Optional[str], Optional[dict], str, bool]:
    """
    Attempt to generate an Excel file if conditions are met.
    If temp_file_path is provided, uses that file instead of looking up project sources.
    Returns (excel_file_id, excel_preview, response_text, is_clarification).
    If no Excel should be generated, returns (None, None, current_response_text, False).
    When a clarification question is asked, returns (None, None, clarif_text, True).
    """
    # If no temp file, require project + active sources
    if not temp_file_path and (not project_id or not active_source_ids):
        return None, None, current_response_text, False

    if not is_excel_trigger(message_content):
        return None, None, current_response_text, False

    try:
        # ── Resolve the actual file to operate on ──
        if temp_file_path and Path(temp_file_path).exists():
            actual_file_path = Path(temp_file_path)
            actual_ext = actual_file_path.suffix.lstrip(".").lower()
            source_name = actual_file_path.name.split("_", 1)[-1]  # strip UUID prefix
            logger.info(f"Excel service using temp file: {source_name}")
        else:
            # Prefer XLSX/XLS over CSV
            excel_source = await db.sources.find_one(
                {
                    "id": {"$in": active_source_ids},
                    "mimeType": {"$in": [
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "application/vnd.ms-excel"
                    ]}
                },
                {"_id": 0}
            )
            if not excel_source:
                excel_source = await db.sources.find_one(
                    {"id": {"$in": active_source_ids}, "mimeType": {"$in": ["text/csv", "application/csv"]}},
                    {"_id": 0}
                )
            if not excel_source:
                return None, None, current_response_text, False
            if not excel_source.get("storagePath"):
                return None, None, current_response_text, False
            actual_file_path = UPLOAD_DIR / excel_source["storagePath"]
            actual_ext = excel_source["storagePath"].rsplit(".", 1)[-1].lower()
            source_name = excel_source.get("originalName", "file")

        if not actual_file_path.exists():
            return None, None, current_response_text, False

        # ── Targeted edit path (skips clarification flow) ──
        if is_edit_trigger(message_content):
            try:
                file_id, preview, text = await targeted_excel_edit(str(actual_file_path), message_content, claude_client)
                return file_id, preview, text, False
            except Exception as edit_err:
                logger.error(f"targeted_excel_edit error: {edit_err}")
                return None, None, current_response_text, False

        # ── Full generation path: two-step flow with clarification ──
        has_clarification = message_content.strip().startswith("__CONFIRM_EXCEL__")
        if has_clarification:
            message_content = message_content[len("__CONFIRM_EXCEL__"):].strip()

        if not has_clarification:
            try:
                clarif_resp = claude_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=512,
                    system=(
                        "EXCEL CLARIFICATION REQUIRED: The user wants to generate an Excel file.\n"
                        "DO NOT generate Excel yet.\n"
                        "IMPORTANT: Detect the language of the user's message:\n"
                        "- If Armenian (հայerен script or romanized like 'inch', 'vor', 'barev') → respond in Armenian\n"
                        "- If Russian (\u043a\u0438\u0440\u0438\u043b\u043b\u0438\u0446\u0430) → respond in Russian\n"
                        "- If English → respond in English\n\n"
                        "Ask these 3 clarifying questions in the SAME language as the user's message:\n"
                        "1. What data/columns should be included\n"
                        "2. Approximately how many rows\n"
                        "3. What is the purpose of the file\n\n"
                        "Keep it short and friendly. Do not generate any file or code."
                    ),
                    messages=[{"role": "user", "content": message_content}]
                )
                return None, None, clarif_resp.content[0].text, True
            except Exception as clarif_err:
                logger.warning(f"Excel clarification call failed: {clarif_err}")
                return None, None, current_response_text, False

        df = pd.read_excel(actual_file_path) if actual_ext in ("xlsx", "xls") else pd.read_csv(actual_file_path)

        structure = (
            f"File: {source_name}\n"
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
                "The user's instruction may be in Armenian, Russian, or English — understand all three.\n"
                "Common operations by language:\n"
                "- Armenian: poxi/\u0583\u0578\u056d\u056b\u0580 = replace | gri/\u0563\u0580\u056b\u0580 = write | avel = add | jnjel = delete\n"
                "- Russian: \u0437\u0430\u043c\u0435\u043d\u0438 = replace | \u043d\u0430\u043f\u0438\u0448\u0438 = write | \u0434\u043e\u0431\u0430\u0432\u044c = add | \u0443\u0434\u0430\u043b\u0438 = delete\n"
                "- English: rename/change/update/add/remove\n"
                "Apply the user's instruction to the data and return ONLY a valid JSON object:\n"
                '{"column_mapping": {"old": "new"}, "new_data": [[col1, col2, ...], [val1, val2, ...], ...], "message": "what was done"}\n'
                "- new_data: first array = column names, remaining = ALL data rows with transformations applied\n"
                "- column_mapping: rename map (can be empty {})\n"
                "- message: brief explanation in SAME language as the user's instruction\n"
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
        return file_id, excel_preview, response_text, False

    except Exception as excel_err:
        logger.error(f"Excel generation error: {excel_err}")
        return None, None, current_response_text, False

