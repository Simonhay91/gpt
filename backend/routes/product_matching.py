"""Product Matching — upload customer file, AI-match against catalog, preview + Excel."""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from typing import List, Optional
import io
import os
import re
import json
import uuid
import logging
from datetime import datetime, timezone
from pydantic import BaseModel

import anthropic
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from db.connection import get_db
from middleware.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/product-matching", tags=["product-matching"])

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
MAX_FILE_SIZE = 20 * 1024 * 1024   # 20 MB
MAX_CUSTOMER_ITEMS = 200
MAX_CATALOG_PRODUCTS = 500
CLAUDE_BATCH_SIZE = 30             # customer items per Claude call


# ==================== TEMPLATE BUILDER ====================

# Keywords that identify the "product name" column in customer Excel files
_PRODUCT_COL_KEYWORDS = (
    "product", "name", "item", "description", "наименование",
    "товар", "продукт", "անվանում", "ապրանք", "model", "модель",
)

_SKIP_VALUES = {"nan", "none", "", "qty", "quantity", "price", "notes", "note",
                "колич", "цена", "примечание", "remarks", "კომენტარი"}


def _build_template_excel() -> bytes:
    """Generate the customer template Excel file and return as bytes."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Products"

    header_fill = PatternFill("solid", fgColor="FFF2CC")   # soft yellow
    header_font = Font(bold=True, size=12, color="1F4E79")
    hint_font   = Font(italic=True, size=10, color="808080")
    border_side = openpyxl.styles.Side(style="thin", color="BFBFBF")
    border      = openpyxl.styles.Border(
        left=border_side, right=border_side,
        top=border_side, bottom=border_side,
    )

    headers = ["Product Name", "Qty", "Notes"]
    col_widths = [45, 10, 30]

    for col_idx, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill   = header_fill
        cell.font   = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = w

    ws.row_dimensions[1].height = 22

    # Hint row
    hint_cell = ws.cell(row=2, column=1, value="← Paste your product names here (required)")
    hint_cell.font = hint_font
    hint_cell.alignment = Alignment(vertical="center")

    ws.cell(row=2, column=2, value="").font = hint_font
    ws.cell(row=2, column=3, value="").font = hint_font

    # Freeze header row
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


# ==================== FILE PARSERS ====================

def _parse_excel(content: bytes) -> List[str]:
    import pandas as pd
    buf = io.BytesIO(content)

    # Try reading with header row first
    try:
        df_with_header = pd.read_excel(buf, header=0)
    except Exception:
        buf.seek(0)
        try:
            df_with_header = pd.read_csv(buf, header=0, on_bad_lines="skip")
        except Exception:
            df_with_header = None

    # Detect product name column by header keyword
    target_col = None
    if df_with_header is not None:
        for col in df_with_header.columns:
            col_lower = str(col).lower().strip()
            if any(kw in col_lower for kw in _PRODUCT_COL_KEYWORDS):
                target_col = col
                break

    if target_col is not None:
        # Use the detected named column (skip header — already excluded by header=0)
        series = df_with_header[target_col].dropna()
    else:
        # Fallback: use first column, read without header to include all rows
        buf.seek(0)
        try:
            df_no_header = pd.read_excel(buf, header=None)
        except Exception:
            buf.seek(0)
            try:
                df_no_header = pd.read_csv(buf, header=None, on_bad_lines="skip")
            except Exception:
                buf.seek(0)
                df_no_header = pd.read_csv(buf, on_bad_lines="skip")
        series = df_no_header.iloc[:, 0].dropna()

    seen: set = set()
    items: List[str] = []
    for val in series:
        s = str(val).strip()
        if s and s.lower() not in _SKIP_VALUES and s not in seen:
            seen.add(s)
            items.append(s)
    return items


def _parse_docx(content: bytes) -> List[str]:
    from docx import Document
    doc = Document(io.BytesIO(content))
    seen: set = set()
    items: List[str] = []

    def _add(text: str):
        s = text.strip()
        if s and s not in seen:
            seen.add(s)
            items.append(s)

    for para in doc.paragraphs:
        _add(para.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                _add(cell.text)
    return items


def _parse_pdf(content: bytes) -> List[str]:
    import pdfplumber
    seen: set = set()
    items: List[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                s = line.strip()
                if s and s not in seen:
                    seen.add(s)
                    items.append(s)
    return items


# ==================== CLAUDE MATCHING ====================

def _format_catalog(catalog: List[dict]) -> str:
    lines = []
    for i, p in enumerate(catalog):
        aliases = ", ".join((p.get("aliases") or [])[:5])  # max 5 aliases to save tokens
        parts = [
            f"[{i + 1}]",
            f"title={p.get('title_en', '')}",
            f"article={p.get('article_number', '')}",
            f"crm={p.get('crm_code', '')}",
            f"vendor={p.get('vendor', '')}",
        ]
        if p.get('product_model'):
            parts.append(f"model={p['product_model']}")
        if aliases:
            parts.append(f"aliases={aliases}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


OPTICAL_CABLE_DOMAIN = """
OPTICAL FIBER CABLE NAMING CONVENTION (use this to interpret customer requests):

MODEL FORMAT: [PREFIX]-[TUBE]([MODIFIER])-([FIBER_RANGE])FO([SPEC])-[STRENGTH]KN

--- PREFIX (installation type) ---
AS       = Aerial ADSS self-supporting
AM       = Aerial Messenger / Drop outdoor (Fig-8 or flat)
U-TIC    = Underground Steel Tape armored
U-DIC    = Underground Steel Wire armored
U-TBC    = Underground Air Blow Cable
OM3      = Multimode OM3
OM4      = Multimode OM4
IR       = Indoor Riser
ID       = Indoor Drop

--- TUBE CONSTRUCTION ---
L   = Central Loose Tube
M   = Loose Tube + Central Strength member (mix)
S   = Multi Tube / Central Strength member
ST  = Single Tube (indoor)
MT  = Multi Tube (indoor)
FL  = Flat Drop cable
OR  = O-ring / Fig-8 shape

--- MODIFIERS (in parentheses after tube type) ---
(A)    = Aramid yarns reinforcement
(PA)   = Partial Aramid yarns
(D)    = FRP messenger
(W)    = Steel wire strength member
(L)    = Double sheath (e.g. AS(L)-S = double-sheath ADSS)
(KFRP) = Kevlar FRP reinforcement

--- FIBER COUNT ---
Written as (min-max)FO, e.g.:
  (1-24)FO  = supports 1 to 24 fibers
  (4-72)FO  = supports 4 to 72 fibers
  (96-144)FO = supports 96 to 144 fibers
  (2-480)FO = supports 2 to 480 fibers
Match customer's fiber count to the range that contains it.

--- FIBER SPEC SUFFIX ---
(none)   = Standard SMF ITU-T G.652D
LSZH     = Low Smoke Zero Halogen
G657A2   = Bend-insensitive ITU-T G.657A2 (indoor/drop)
Aqua     = OM3 indoor aqua color
300m/1km = Drum length

--- TENSILE STRENGTH (trailing KN) ---
Common values: 0.5, 0.6, 0.8, 1, 1.5, 2, 2.7, 2.8, 3, 3.5, 4, 4.5, 5.5, 7, 7.5, 8, 9, 9.5, 20, 25 KN

--- MATCHING EXAMPLES ---
Customer says → Best model match:
"ADSS 12 fiber 2KN"                    → AS-M-(4-12)FO-2KN      (12 falls in 4-12 range)
"ADSS 48fo 3kn strength member"        → AS-S-(4-72)FO-3KN       (48 in 4-72, strength member)
"aerial loose tube 24 fiber 1.5kn"     → AS-L-(1-24)FO-1.5KN
"ADSS double sheath 96fo 20kn aramid"  → AS(L)-S-(8-96)FO-20KN
"fig-8 loose tube 12fo 5.5kn"         → AM-L-(1-24)FO-5.5KN
"drop flat FRP messenger 2fo 0.6kn"   → AM-L-FL(D)-(1-4)FO-0.6KN
"drop o-ring aramid 4fo 1kn"          → AM-L-OR(A)-(1-4)FO-1KN
"underground steel tape 24fo 2.7kn"   → U-TIC-L-(2-24)FO-2.7KN
"underground steel wire multi 48fo"   → U-DIC-S-(8-96)FO-7KN
"air blow cable 96 fiber"             → U-TBC-S-(2-480)FO
"indoor riser 48fo single tube"       → IR-ST-(8-24)FO-G657A2
"indoor riser multi tube 72fo"        → IR-MT-(14-96)FO-G657A2
"indoor drop flat FRP 2fo"            → ID-FL(D)-(1-4)FO-G657A2
"indoor drop flat steel wire 4fo"     → ID-FL(W)-(1-4)FO-G657A2
"indoor drop o-ring 300m drum"        → ID-OR3MM-(1-4)FO-G657A2(300m)
"om3 multimode 12fo 1kn lszh"         → OM3-L-(6-12)FO-1kN-LSZH
"om4 multimode cable"                 → OM4-L-(6-12)FO-1kN-LSZH
"drop adss aramid 12fo 1kn"           → AS-L(A)-(4-24)FO-1KN
"""


def _claude_match_batch(
    batch: List[str],
    catalog_text: str,
    catalog_len: int,
) -> List[dict]:
    """
    Send one batch of customer items + full catalog to Claude.
    Returns list of match dicts in the same order as batch.
    """
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    items_text = "\n".join(f"[{i + 1}] {name}" for i, name in enumerate(batch))

    prompt = f"""You are a product matching assistant for a fiber optics and network equipment catalog.

{OPTICAL_CABLE_DOMAIN}

CATALOG ({catalog_len} products):
{catalog_text}

CUSTOMER ITEMS ({len(batch)} items to match):
{items_text}

For each customer item find the best matching catalog product.
Use the optical cable naming convention above to interpret both customer requests and catalog model codes.
Return a JSON array with exactly {len(batch)} objects in the same order:
[
  {{
    "customer_item": "<original customer item text>",
    "matched_title": "<catalog title_en, empty string if no match>",
    "article_number": "<article_number from catalog, empty string if no match>",
    "crm_code": "<crm_code from catalog, empty string if no match>",
    "vendor": "<vendor from catalog, empty string if no match>",
    "datasheet_url": "<datasheet_url from catalog, empty string if no match>",
    "comment": "<short English note if approximate match (different spec/fiber count/strength), null if exact match or no match>"
  }}
]

Rules:
- For optical cables: decode the customer's description using the naming convention, then find the catalog model whose fiber range contains the requested count and whose strength is closest.
- If no suitable match exists, leave matched fields as empty strings and set comment to a brief English reason.
- If match is approximate (e.g. customer asked for 1.5KN but catalog has 2KN), describe the difference in comment.
- Return ONLY the JSON array, no extra text."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        logger.error(f"Claude returned no JSON array: {raw[:300]}")
        return _empty_batch(batch, "Matching error")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        logger.error(f"Claude JSON decode error: {exc} | raw[:300]={raw[:300]}")
        return _empty_batch(batch, "Matching error")


def _empty_batch(items: List[str], comment: str) -> List[dict]:
    return [
        {
            "customer_item": item,
            "matched_title": "",
            "article_number": "",
            "crm_code": "",
            "vendor": "",
            "datasheet_url": "",
            "comment": comment,
        }
        for item in items
    ]


# ==================== EXCEL BUILDER ====================

def _build_excel(rows: List[dict], mode: str) -> str:
    """Build result Excel, save to /tmp/, return path."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Product Matching"

    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    alt_fill = PatternFill("solid", fgColor="EBF3FB")
    unmatch_fill = PatternFill("solid", fgColor="FFF2CC")

    code_label = "CRM Code" if mode == "global" else "Article Number"
    headers = ["Customer Item", code_label, "Our Product Title", "Datasheet URL", "Comment"]

    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 22

    col_widths = [35, 20, 40, 40, 45]
    for col_idx, w in enumerate(col_widths, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = w

    for row_idx, r in enumerate(rows, 2):
        is_matched = bool(r.get("matched_title", "").strip())
        is_alt_row = (row_idx % 2 == 0)

        if not is_matched:
            fill = unmatch_fill
        elif is_alt_row:
            fill = alt_fill
        else:
            fill = None

        values = [
            r.get("customer_item", ""),
            r.get("code", ""),
            r.get("matched_title", ""),
            r.get("datasheet_url", ""),
            r.get("comment") or "",
        ]

        for col_idx, val in enumerate(values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            if fill:
                cell.fill = fill
            cell.alignment = Alignment(
                vertical="center",
                wrap_text=(col_idx in (1, 5)),
            )

    path = f"/tmp/product_matching_{uuid.uuid4()}.xlsx"
    wb.save(path)
    return path


def _remove_file(path: str):
    try:
        os.unlink(path)
    except Exception:
        pass


# ==================== PYDANTIC MODELS ====================

class GenerateRequest(BaseModel):
    mode: str = "global"
    results: List[dict]


# ==================== ENDPOINTS ====================

@router.get("/template")
async def download_template(current_user: dict = Depends(get_current_user)):
    """Return a pre-formatted customer Excel template for product matching."""
    template_bytes = _build_template_excel()
    path = f"/tmp/product_matching_template_{uuid.uuid4()}.xlsx"
    with open(path, "wb") as f:
        f.write(template_bytes)
    return FileResponse(
        path=path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="product_matching_template.xlsx",
        background=BackgroundTask(_remove_file, path),
    )


@router.post("/match")
async def match_products(
    file: UploadFile = File(...),
    mode: str = Form("global"),   # "global" | "oem"
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a customer file (xlsx/xls/csv/docx/pdf) with product names.
    Returns JSON preview results for user review before Excel generation.
    mode='global' → CRM codes; mode='oem' → article for OEM vendors, else CRM.
    """
    db = get_db()

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 20 MB)")

    filename = (file.filename or "").lower()

    # 1. Parse customer items from file
    try:
        if filename.endswith(".pdf"):
            customer_items = _parse_pdf(content)
        elif filename.endswith(".docx"):
            customer_items = _parse_docx(content)
        else:
            customer_items = _parse_excel(content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}")

    if not customer_items:
        raise HTTPException(status_code=400, detail="No product names found in file")

    customer_items = customer_items[:MAX_CUSTOMER_ITEMS]

    # 2. Load active catalog products
    catalog = await db.product_catalog.find(
        {"is_active": True},
        {
            "_id": 0,
            "article_number": 1,
            "title_en": 1,
            "crm_code": 1,
            "vendor": 1,
            "product_model": 1,
            "datasheet_url": 1,
            "aliases": 1,
        },
    ).limit(MAX_CATALOG_PRODUCTS).to_list(MAX_CATALOG_PRODUCTS)

    if not catalog:
        raise HTTPException(status_code=404, detail="Product catalog is empty")

    # 3. Load OEM vendor names (for OEM mode code selection)
    oem_vendor_names: set = set()
    if mode == "oem":
        oem_brands = await db.oem_brands.find({}, {"_id": 0, "name": 1}).to_list(200)
        oem_vendor_names = {b["name"].lower() for b in oem_brands if b.get("name")}

    # 4. Build alias lookup: alias_text → catalog product
    alias_lookup: dict = {}
    for p in catalog:
        for alias in (p.get("aliases") or []):
            alias_lookup[alias.lower().strip()] = p
    # Also load product_aliases collection
    saved_aliases = await db.product_aliases.find(
        {}, {"_id": 0}
    ).to_list(10000)
    # Build crm_code → catalog product map
    crm_to_product = {p.get("crm_code", ""): p for p in catalog if p.get("crm_code")}
    article_to_product = {p.get("article_number", ""): p for p in catalog if p.get("article_number")}
    for sa in saved_aliases:
        key = (sa.get("alias") or "").lower().strip()
        if key and key not in alias_lookup:
            prod = crm_to_product.get(sa.get("crm_code") or "") or article_to_product.get(sa.get("article_number") or "")
            if prod:
                alias_lookup[key] = prod

    # 5. Pre-format catalog once (reused across batches)
    catalog_text = _format_catalog(catalog)

    # 6. Split customer items: alias-matched vs needs Claude
    alias_matched: dict = {}  # index → result dict
    needs_claude: List[tuple] = []  # (original_index, item)

    for idx, item in enumerate(customer_items):
        item_lower = item.lower().strip()
        if item_lower in alias_lookup:
            p = alias_lookup[item_lower]
            alias_matched[idx] = {
                "customer_item": item,
                "matched_title": p.get("title_en", ""),
                "article_number": p.get("article_number", ""),
                "crm_code": p.get("crm_code", ""),
                "vendor": p.get("vendor", ""),
                "datasheet_url": p.get("datasheet_url", ""),
                "comment": None,
                "match_type": "auto",
                "confidence": "high",
            }
        else:
            needs_claude.append((idx, item))

    # 7. Claude matching for unresolved items in batches
    claude_items = [item for _, item in needs_claude]
    raw_claude: List[dict] = []
    for i in range(0, len(claude_items), CLAUDE_BATCH_SIZE):
        batch = claude_items[i: i + CLAUDE_BATCH_SIZE]
        try:
            batch_results = _claude_match_batch(batch, catalog_text, len(catalog))
        except Exception as exc:
            logger.error(f"Claude batch {i // CLAUDE_BATCH_SIZE + 1} error: {exc}")
            batch_results = _empty_batch(batch, "Matching error")
        raw_claude.extend(batch_results)

    # 8. Merge alias-matched + Claude results in original order
    claude_iter = iter(enumerate(raw_claude))
    claude_map: dict = {}
    for claude_idx, r in enumerate(raw_claude):
        orig_idx = needs_claude[claude_idx][0]
        claude_map[orig_idx] = r

    results: List[dict] = []
    for idx, item in enumerate(customer_items):
        if idx in alias_matched:
            r = alias_matched[idx]
        else:
            r = claude_map.get(idx, {"customer_item": item, "matched_title": "", "article_number": "", "crm_code": "", "vendor": "", "datasheet_url": "", "comment": "Matching error"})
            # Determine confidence based on whether match found
            has_match = bool(r.get("matched_title", "").strip())
            comment = r.get("comment")
            if not has_match:
                confidence = None
            elif comment:
                confidence = "medium"
            else:
                confidence = "high"
            r["match_type"] = "auto"
            r["confidence"] = confidence

        # Apply mode logic to pick code
        vendor_lower = (r.get("vendor") or "").lower()
        article = r.get("article_number") or ""
        crm = r.get("crm_code") or ""

        if mode == "global":
            code = crm or article
        else:
            if vendor_lower and vendor_lower in oem_vendor_names:
                code = article or crm
            else:
                code = crm or article

        results.append({
            "customer_item": r.get("customer_item", ""),
            "crm_code": crm or None,
            "article_number": article or None,
            "matched_title": r.get("matched_title", ""),
            "code": code or None,
            "datasheet_url": r.get("datasheet_url", "") or None,
            "comment": r.get("comment") or None,
            "match_type": r.get("match_type", "auto"),
            "confidence": r.get("confidence"),
        })

    return {"results": results}


@router.post("/generate")
async def generate_excel(
    data: GenerateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Accept reviewed results, save aliases to product_aliases collection,
    generate and return Excel file.
    """
    db = get_db()
    results = data.results
    mode = data.mode

    # Save aliases (skip duplicates)
    now = datetime.now(timezone.utc).isoformat()
    for r in results:
        customer_item = (r.get("customer_item") or "").strip()
        crm_code = r.get("crm_code") or None
        article_number = r.get("article_number") or None
        if not customer_item:
            continue
        if not crm_code and not article_number:
            continue

        # Check for existing alias
        existing = await db.product_aliases.find_one({
            "alias": customer_item,
            **({"crm_code": crm_code} if crm_code else {"article_number": article_number}),
        })
        if not existing:
            confidence = "confirmed" if r.get("match_type") == "confirmed" else "auto"
            alias_doc = {
                "crm_code": crm_code,
                "article_number": article_number,
                "alias": customer_item,
                "confidence": confidence,
                "saved_at": now,
            }
            await db.product_aliases.insert_one(alias_doc)

    # Build Excel rows from results
    rows = [
        {
            "customer_item": r.get("customer_item", ""),
            "code": r.get("code") or "",
            "matched_title": r.get("matched_title") or "",
            "datasheet_url": r.get("datasheet_url") or "",
            "comment": r.get("comment") or "",
        }
        for r in results
    ]

    try:
        excel_path = _build_excel(rows, mode)
    except Exception as exc:
        logger.error(f"Excel build error: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to build Excel: {str(exc)[:100]}")

    return FileResponse(
        path=excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="product_matching_results.xlsx",
        background=BackgroundTask(_remove_file, excel_path),
    )


@router.get("/search")
async def search_products(
    q: str = Query(..., min_length=1),
    current_user: dict = Depends(get_current_user),
):
    """
    Search product_catalog by title, article_number, aliases.
    Also searches product_aliases collection.
    Returns max 10 deduplicated results.
    """
    db = get_db()
    q_strip = q.strip()
    regex = {"$regex": q_strip, "$options": "i"}

    # Search catalog
    catalog_results = await db.product_catalog.find(
        {
            "is_active": True,
            "$or": [
                {"title_en": regex},
                {"article_number": regex},
                {"aliases": regex},
            ],
        },
        {"_id": 0, "crm_code": 1, "article_number": 1, "title_en": 1, "vendor": 1},
    ).limit(10).to_list(10)

    seen_crm: set = set()
    results = []
    for p in catalog_results:
        key = p.get("crm_code") or p.get("article_number") or ""
        if key and key not in seen_crm:
            seen_crm.add(key)
            results.append({
                "crm_code": p.get("crm_code"),
                "article_number": p.get("article_number"),
                "title": p.get("title_en", ""),
                "code": p.get("crm_code") or p.get("article_number"),
                "vendor": p.get("vendor", ""),
            })

    # Search product_aliases if we have room
    if len(results) < 10:
        alias_hits = await db.product_aliases.find(
            {"alias": regex},
            {"_id": 0, "crm_code": 1, "article_number": 1},
        ).limit(10).to_list(10)

        crm_codes_from_aliases = list({a["crm_code"] for a in alias_hits if a.get("crm_code")} - seen_crm)
        article_nums_from_aliases = list({a["article_number"] for a in alias_hits if a.get("article_number") and not a.get("crm_code")} - seen_crm)

        if crm_codes_from_aliases or article_nums_from_aliases:
            extra = await db.product_catalog.find(
                {
                    "is_active": True,
                    "$or": [
                        *({"crm_code": c} for c in crm_codes_from_aliases),
                        *({"article_number": a} for a in article_nums_from_aliases),
                    ],
                },
                {"_id": 0, "crm_code": 1, "article_number": 1, "title_en": 1, "vendor": 1},
            ).limit(10 - len(results)).to_list(10)

            for p in extra:
                key = p.get("crm_code") or p.get("article_number") or ""
                if key and key not in seen_crm:
                    seen_crm.add(key)
                    results.append({
                        "crm_code": p.get("crm_code"),
                        "article_number": p.get("article_number"),
                        "title": p.get("title_en", ""),
                        "code": p.get("crm_code") or p.get("article_number"),
                        "vendor": p.get("vendor", ""),
                    })

    return results[:10]
