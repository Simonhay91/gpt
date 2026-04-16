"""Product Matching — upload customer file, AI-match against catalog, return Excel."""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from typing import List
import io
import os
import re
import json
import uuid
import logging

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
MAX_CATALOG_PRODUCTS = 1000
CLAUDE_BATCH_SIZE = 50             # customer items per Claude call


# ==================== FILE PARSERS ====================

def _parse_excel(content: bytes) -> List[str]:
    import pandas as pd
    buf = io.BytesIO(content)
    try:
        df = pd.read_excel(buf, header=None)
    except Exception:
        buf.seek(0)
        try:
            df = pd.read_csv(buf, header=None, on_bad_lines="skip")
        except Exception:
            buf.seek(0)
            df = pd.read_csv(buf, on_bad_lines="skip")
    seen: set = set()
    items: List[str] = []
    for col in df.columns:
        for val in df[col].dropna():
            s = str(val).strip()
            if s and s.lower() not in ("nan", "none", "") and s not in seen:
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
        aliases = ", ".join(p.get("aliases") or [])
        line = (
            f"[{i + 1}] title={p.get('title_en', '')} | "
            f"article={p.get('article_number', '')} | "
            f"crm={p.get('crm_code', '')} | "
            f"vendor={p.get('vendor', '')} | "
            f"model={p.get('product_model', '')} | "
            f"aliases={aliases} | "
            f"datasheet={p.get('datasheet_url', '')}"
        )
        lines.append(line)
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
        max_tokens=4096,
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


# ==================== ENDPOINT ====================

@router.post("/match")
async def match_products(
    file: UploadFile = File(...),
    mode: str = Form("global"),   # "global" | "oem"
    current_user: dict = Depends(get_current_user),
):
    """
    Upload a customer file (xlsx/xls/csv/docx/pdf) with product names.
    Returns Excel with matched catalog products.
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
        oem_vendor_names = {
            b["name"].lower() for b in oem_brands if b.get("name")
        }

    # 4. Pre-format catalog once (reused across batches)
    catalog_text = _format_catalog(catalog)

    # 5. Claude matching in batches of CLAUDE_BATCH_SIZE
    raw_results: List[dict] = []
    for i in range(0, len(customer_items), CLAUDE_BATCH_SIZE):
        batch = customer_items[i: i + CLAUDE_BATCH_SIZE]
        try:
            batch_results = _claude_match_batch(batch, catalog_text, len(catalog))
        except Exception as exc:
            logger.error(f"Claude batch {i // CLAUDE_BATCH_SIZE + 1} error: {exc}")
            batch_results = _empty_batch(batch, "Matching error")
        raw_results.extend(batch_results)

    # 6. Apply mode logic to pick the right code field
    rows: List[dict] = []
    for r in raw_results:
        vendor_lower = (r.get("vendor") or "").lower()
        article = r.get("article_number") or ""
        crm = r.get("crm_code") or ""

        if mode == "global":
            code = crm or article
        else:
            # OEM mode: article for OEM-registered vendors, else CRM
            if vendor_lower and vendor_lower in oem_vendor_names:
                code = article or crm
            else:
                code = crm or article

        rows.append(
            {
                "customer_item": r.get("customer_item", ""),
                "code": code,
                "matched_title": r.get("matched_title", ""),
                "datasheet_url": r.get("datasheet_url", ""),
                "comment": r.get("comment"),
            }
        )

    # 7. Build Excel and return
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
