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
    # ── English — generate ──
    "generate excel", "create excel", "make excel", "create spreadsheet",
    "make spreadsheet", "download excel", "export excel", "export to excel",
    "generate", "download", "export", "get file", "give me file", "save as excel",
    # ── English — edit ──
    "edit", "modify", "update", "change", "fix",
    # ── Russian — generate ──
    "сгенерируй excel", "создай excel", "сделай excel", "скачать excel",
    "сгенерируй таблицу", "создай таблицу", "сделай таблицу",
    "скачай", "скачать", "сохрани", "экспортируй", "генерируй", "создай файл",
    # ── Russian — edit ──
    "редактируй", "измени", "обнови", "исправь", "поменяй",
    # ── Armenian romanized — generate ──
    "excel generacru", "excel sarcru", "excel beri", "excel download ara",
    "avelacru excel", "excel poxi", "kercru excel",
    "generacru", "sarcru", "beri", "tui", "ktur", "bacer", "paterastirel",
    "download ara", "paterastr", "excel baci", "excel kazmir",
    # ── Armenian romanized — edit ──
    "edit ara", "poxi", "kpoxes", "popoxir", "gri", "nerkayacru",
    # ── Armenian unicode — generate ──
    "excel ստեղծիր", "excel բեր", "excel ներբեռնիր",
    "ստեղծիր", "բեր", "տուր", "ներբեռնիր", "պատրաստիր", "գեներացրու",
    # ── Armenian unicode — edit ──
    "փոխիր", "խմբագրիր", "թարմացրու", "ուղղիր", "գրիր",
    # ── Excel-specific ──
    "arajin togh", "առաջին տող", "readme",
]

# When an existing Excel source is found, ALL trigger phrases route to targeted_edit.
# Full generation only happens when there is NO existing file (scratch creation).
EXCEL_EDIT_PHRASES = [
    # ── English ──
    "edit", "modify", "update", "change", "fix",
    "generate", "download", "export", "get file", "give me file",
    # ── Russian ──
    "редактируй", "измени", "обнови", "исправь", "поменяй",
    "скачай", "скачать", "сохрани", "экспортируй", "генерируй",
    # ── Armenian romanized ──
    "edit ara", "poxi", "kpoxes", "popoxir", "gri", "nerkayacru",
    "generacru", "sarcru", "beri", "tui", "ktur", "bacer",
    "download ara", "paterastr", "paterastirel",
    # ── Armenian unicode ──
    "փոխիր", "խմբագրիր", "թարմացրու", "ուղղիր", "գրիր",
    "ստեղծիր", "բեր", "տուր", "ներբեռնիր", "պատրաստիր", "գեներացրու",
    # ── Excel-specific ──
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

# Minimum word count for edit trigger — short messages like "generacru" (1 word) ARE valid.
EXCEL_EDIT_MIN_WORDS = 1

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
    """Edit Excel file — cells, formulas, styles, chart titles, merges, row/col sizes."""
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment
    from openpyxl.utils import get_column_letter

    if not source_file_path.endswith(('.xlsx', '.xlsm', '.xls')):
        return None, None, "Edit is only supported for Excel files (.xlsx). CSV files cannot be edited this way."

    # ── Build full file structure for Claude ──
    _wb_preview = openpyxl.load_workbook(source_file_path, read_only=True, data_only=True)
    file_structure = {}
    for _sheet_name in _wb_preview.sheetnames:
        _ws = _wb_preview[_sheet_name]
        _rows_data = []
        for _row in _ws.iter_rows(values_only=True):
            _rows_data.append(list(_row))
        file_structure[_sheet_name] = {
            "rows": _rows_data,
            "max_row": _ws.max_row,
            "max_col": _ws.max_column,
        }
    _wb_preview.close()

    # Collect chart info from a writable workbook (read_only doesn't expose charts)
    _wb_charts = openpyxl.load_workbook(source_file_path)
    charts_info = {}
    for _sheet_name in _wb_charts.sheetnames:
        _ws_c = _wb_charts[_sheet_name]
        _chart_list = []
        for _i, _chart in enumerate(getattr(_ws_c, '_charts', [])):
            _title = ""
            try:
                _title = str(_chart.title) if _chart.title else ""
            except Exception:
                pass
            _chart_list.append({"index": _i, "title": _title, "type": type(_chart).__name__})
        if _chart_list:
            charts_info[_sheet_name] = _chart_list
    _wb_charts.close()

    if charts_info:
        for _sn, _cl in charts_info.items():
            if _sn in file_structure:
                file_structure[_sn]["charts"] = _cl

    print(f"[EXCEL EDIT DEBUG] Instruction: {instruction}")
    print(f"[EXCEL EDIT DEBUG] File structure: {json.dumps(file_structure, ensure_ascii=False)[:800]}")

    # ── Ask Claude for rich operation list ──
    analysis_response = claude_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=(
            "You are a full-featured Excel editor. The user's instruction may be in Armenian, Russian, or English.\n"
            "Language hints:\n"
            "- Armenian: poxi/փոխիր=change | gri/գրիր=write | karmir/կարմիր=red | deghin/դեղին=yellow | kanahaguyn/կանաչ=green | spitak/սպիտակ=white | sheganakarguyn/շականակ=brown\n"
            "- Russian: замени=change | напиши=write | красный=red | жёлтый=yellow\n"
            "- English: change/set/write | red/yellow/green\n\n"
            "Return ONLY a JSON array of operations — no markdown, no explanation.\n"
            "Supported operation types:\n"
            '1. {"type":"cell","sheet":"...","cell":"A1","value":"..."}  — set cell value or formula (=SUM(...))\n'
            '2. {"type":"fill","sheet":"...","cell":"A1","color":"FF0000"}  — background color (hex, no #)\n'
            '3. {"type":"font","sheet":"...","cell":"A1","bold":true,"italic":false,"size":14,"color":"FFFFFF"}  — font style\n'
            '4. {"type":"chart_title","sheet":"...","chart_index":0,"title":"New Title"}  — change chart title\n'
            '5. {"type":"chart_fill","sheet":"...","chart_index":0,"color":"FF0000"}  — chart plot area background\n'
            '6. {"type":"merge","sheet":"...","range":"A1:D1"}  — merge cells\n'
            '7. {"type":"unmerge","sheet":"...","range":"A1:D1"}  — unmerge cells\n'
            '8. {"type":"row_height","sheet":"...","row":1,"height":30}  — row height in points\n'
            '9. {"type":"col_width","sheet":"...","col":"A","width":20}  — column width\n'
            "Color names → hex: red=FF0000, yellow=FFFF00, green=00FF00, blue=0000FF, white=FFFFFF, black=000000, orange=FFA500\n"
            "Rules:\n"
            "- For chart_title: use chart_index from the provided charts list\n"
            "- Formulas start with = (e.g. =SUM(A1:A10))\n"
            "- You may combine multiple operations in one array\n"
            "- Return [] only if the instruction is truly impossible\n"
            "Return ONLY JSON array."
        ),
        messages=[{"role": "user", "content": f"Instruction: {instruction}\n\nFile structure:\n{json.dumps(file_structure, ensure_ascii=False)}"}]
    )

    print(f"[EXCEL EDIT DEBUG] Claude raw: {analysis_response.content[0].text}")

    raw = analysis_response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        ops = json.loads(raw.strip())
    except json.JSONDecodeError:
        logger.warning(f"targeted_excel_edit: invalid JSON from Claude: {raw[:200]}")
        return None, None, "Չհաջողվեց հասկանալ ինչ փոփոխություններ կատարել։ Խնդրեմ ավելի կոնկրետ նկարագրիր։"

    if not ops:
        return None, None, "Չհաջողվեց որոշել ինչ փոփոխություններ կատարել։ Խնդրեմ ավելի կոնկրետ նկարագրիր։"

    # ── Apply all operations ──
    wb = openpyxl.load_workbook(source_file_path)
    applied = []
    skipped = []

    for op in ops:
        op_type = op.get("type", "cell")
        sheet_name = op.get("sheet")

        if sheet_name and sheet_name not in wb.sheetnames:
            skipped.append(op)
            logger.warning(f"targeted_excel_edit: sheet not found: {sheet_name}")
            continue

        ws = wb[sheet_name] if sheet_name else wb.active

        try:
            if op_type == "cell":
                cell = op.get("cell")
                value = op.get("value")
                if cell and value is not None:
                    ws[cell] = value
                    applied.append(op)

            elif op_type == "fill":
                cell = op.get("cell")
                color = op.get("color", "").lstrip("#")
                if cell and color:
                    ws[cell].fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
                    applied.append(op)

            elif op_type == "font":
                cell = op.get("cell")
                if cell:
                    existing = ws[cell].font
                    bold = op.get("bold", existing.bold)
                    italic = op.get("italic", existing.italic)
                    size = op.get("size", existing.size)
                    fcolor = op.get("color", "").lstrip("#") or None
                    ws[cell].font = Font(
                        bold=bold,
                        italic=italic,
                        size=size,
                        color=fcolor if fcolor else existing.color,
                    )
                    applied.append(op)

            elif op_type == "chart_title":
                chart_index = op.get("chart_index", 0)
                title = op.get("title", "")
                charts = getattr(ws, '_charts', [])
                if chart_index < len(charts):
                    charts[chart_index].title = title
                    applied.append(op)
                else:
                    skipped.append(op)
                    logger.warning(f"targeted_excel_edit: chart_index {chart_index} out of range")

            elif op_type == "chart_fill":
                chart_index = op.get("chart_index", 0)
                color = op.get("color", "").lstrip("#")
                charts = getattr(ws, '_charts', [])
                if chart_index < len(charts) and color:
                    from openpyxl.drawing.fill import PatternFillProperties
                    from openpyxl.chart.data_source import NumDataSource
                    # Set plot area fill via graphical properties
                    chart = charts[chart_index]
                    try:
                        from openpyxl.drawing.spreadsheet_drawing import SpreadsheetDrawing
                        from openpyxl.chart._chart import AxDataSource
                        # Use solidFill on plot area if accessible
                        if hasattr(chart, 'plot_area') and hasattr(chart.plot_area, 'spPr'):
                            from openpyxl.drawing.fill import SolidColorFillProperties
                            chart.plot_area.spPr.solidFill = color
                    except Exception:
                        pass
                    applied.append(op)
                else:
                    skipped.append(op)

            elif op_type == "merge":
                cell_range = op.get("range")
                if cell_range:
                    ws.merge_cells(cell_range)
                    applied.append(op)

            elif op_type == "unmerge":
                cell_range = op.get("range")
                if cell_range:
                    ws.unmerge_cells(cell_range)
                    applied.append(op)

            elif op_type == "row_height":
                row = op.get("row")
                height = op.get("height")
                if row and height:
                    ws.row_dimensions[int(row)].height = float(height)
                    applied.append(op)

            elif op_type == "col_width":
                col = op.get("col", "").lstrip("#")
                width = op.get("width")
                if col and width:
                    ws.column_dimensions[col.upper()].width = float(width)
                    applied.append(op)

            else:
                skipped.append(op)
                logger.warning(f"targeted_excel_edit: unknown op type: {op_type}")

        except Exception as apply_err:
            skipped.append(op)
            logger.warning(f"targeted_excel_edit: failed to apply {op}: {apply_err}")

    if not applied:
        return None, None, "Փոփոխություններ կատարել չհաջողվեց։ Հնարավոր է ֆայլի կառուցվածքը չի համապատասխանում հրահանգին։"

    # ── Save ──
    file_id = str(uuid.uuid4())
    output_path = str(UPLOAD_DIR / f"excel_{file_id}.xlsx")
    wb.save(output_path)
    print(f"[EXCEL EDIT DEBUG] file_id={file_id}, applied={len(applied)}, skipped={len(skipped)}")

    preview = {
        "columns": ["type", "sheet", "detail"],
        "rows": [
            [e.get("type"), e.get("sheet"), e.get("cell") or e.get("range") or f"chart[{e.get('chart_index',0)}]"]
            for e in applied
        ],
        "total_rows": len(applied),
        "message": f"Applied {len(applied)} operation(s)." + (f" Skipped {len(skipped)}." if skipped else ""),
    }
    summary = f"Կատարվեց {len(applied)} փոփոխություն։" + (f" Չկատարվեց {len(skipped)}։" if skipped else "")
    return file_id, preview, summary


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
    if not temp_file_path and not project_id:
        print(f"[EXCEL] early exit: no temp_file and no project_id")
        return None, None, current_response_text, False

    # If active_source_ids is empty but project_id exists, fall back to all project sources
    effective_source_ids = active_source_ids or []
    print(f"[EXCEL] start: project_id={project_id}, active_source_ids_count={len(effective_source_ids)}")

    if not is_excel_trigger(message_content):
        print(f"[EXCEL] no trigger found in message: {message_content[:80]}")
        return None, None, current_response_text, False

    try:
        # ── Resolve the actual file to operate on ──
        if temp_file_path and Path(temp_file_path).exists():
            actual_file_path = Path(temp_file_path)
            actual_ext = actual_file_path.suffix.lstrip(".").lower()
            source_name = actual_file_path.name.split("_", 1)[-1]  # strip UUID prefix
            print(f"[EXCEL] using temp file: {source_name}")
        else:
            # Build search filter: prefer active sources, but if empty fall back to all project sources
            id_filter = {"id": {"$in": effective_source_ids}} if effective_source_ids else {"projectId": project_id}

            # 1. Try by mimeType (xlsx/xls)
            excel_source = await db.sources.find_one(
                {
                    **id_filter,
                    "mimeType": {"$in": [
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "application/vnd.ms-excel"
                    ]}
                },
                {"_id": 0}
            )
            # 2. Try by mimeType (csv)
            if not excel_source:
                excel_source = await db.sources.find_one(
                    {**id_filter, "mimeType": {"$in": ["text/csv", "application/csv"]}},
                    {"_id": 0}
                )
            # 3. Fallback: find by file extension in storagePath or originalName
            if not excel_source:
                all_sources = await db.sources.find(id_filter, {"_id": 0}).to_list(100)
                for s in all_sources:
                    sp = (s.get("storagePath") or "").lower()
                    on = (s.get("originalName") or "").lower()
                    if sp.endswith((".xlsx", ".xls", ".csv")) or on.endswith((".xlsx", ".xls", ".csv")):
                        excel_source = s
                        print(f"[EXCEL] found source by extension fallback: {on}, mimeType={s.get('mimeType')}")
                        break

            if not excel_source:
                print(f"[EXCEL] no excel source found among {len(active_source_ids)} active sources")
                return None, None, current_response_text, False
            if not excel_source.get("storagePath"):
                print(f"[EXCEL] source has no storagePath: {excel_source.get('id')}")
                return None, None, current_response_text, False
            actual_file_path = UPLOAD_DIR / excel_source["storagePath"]
            actual_ext = excel_source["storagePath"].rsplit(".", 1)[-1].lower()
            source_name = excel_source.get("originalName", "file")
            print(f"[EXCEL] resolved source: {source_name}, path={actual_file_path}, exists={actual_file_path.exists()}")

        if not actual_file_path.exists():
            print(f"[EXCEL] file not found on disk: {actual_file_path}")
            return None, None, current_response_text, False

        # ── When an existing file is found → ALWAYS use targeted edit ──
        # Full generation destroys original formatting/charts/formulas.
        # The edit path handles everything: value changes, colors, chart titles, formulas, etc.
        print(f"[EXCEL] routing to targeted_edit (source file exists)")
        try:
            file_id, preview, text = await targeted_excel_edit(str(actual_file_path), message_content, claude_client)
            if file_id:
                return file_id, preview, text, False
            # Edit returned no ops — ask user to clarify
            clarif_text = (
                text if text else
                "Չհասկացա ինչ փոփոխություն կատարել։ Խնդրեմ կոնկրետ նկարագրիր — "
                "օրինակ՝ «A2 բջիջում գրիր 100» կամ «Price սյունակի բոլոր արժեքները բազմապատկիր 1.2-ով»։"
            )
            print(f"[EXCEL] targeted_edit returned no ops, returning clarification")
            return None, None, clarif_text, True
        except Exception as edit_err:
            logger.error(f"targeted_excel_edit error: {edit_err}")
            return None, None, "Excel ֆայլի մշակման ժամանակ սխալ առաջացավ։ Խնդրեմ կրկին փորձիր։", True

        # ── Full generation path: only reached if edit produced nothing ──
        # (e.g. user confirmed scratch creation via __CONFIRM_EXCEL__ button)
        has_clarification = message_content.strip().startswith("__CONFIRM_EXCEL__")
        if has_clarification:
            message_content = message_content[len("__CONFIRM_EXCEL__"):].strip()

        if not has_clarification:
            # Return the edit's error/info text rather than asking clarification again
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
        result_path = str(UPLOAD_DIR / f"excel_{file_id}.xlsx")
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

