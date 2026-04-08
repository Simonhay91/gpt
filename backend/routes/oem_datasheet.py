"""OEM Datasheet Rebrander routes"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime, timezone
from uuid import uuid4
import logging
import os
import io
import re
import json
import zipfile
import tempfile

from middleware.auth import get_current_user, is_admin
from db.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/oem", tags=["oem"])

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")
BRAND_LOGOS_DIR = os.path.join(UPLOAD_DIR, "brand_logos")
os.makedirs(BRAND_LOGOS_DIR, exist_ok=True)


# ==================== HELPERS ====================

def extract_text_from_docx(content: bytes) -> str:
    """Extract all text from a Word document"""
    from docx import Document
    doc = Document(io.BytesIO(content))
    parts = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    parts.append(cell.text)
    return "\n".join(parts)


def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF using pdfplumber or PyPDF2 as fallback"""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)
    except Exception as e:
        logger.error(f"pdfplumber failed: {e}")
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception as e2:
            logger.error(f"PyPDF2 also failed: {e2}")
            return ""


def convert_pdf_to_docx(pdf_content: bytes) -> bytes:
    """
    Convert PDF → DOCX while preserving layout (tables, columns, fonts).
    Uses pdf2docx library which reconstructs the document structure.
    """
    try:
        from pdf2docx import Converter
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="pdf2docx library not installed. Cannot preserve PDF layout."
        )

    pdf_tmp = None
    docx_tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_content)
            pdf_tmp = f.name

        docx_tmp = pdf_tmp.replace(".pdf", ".docx")

        cv = Converter(pdf_tmp)
        cv.convert(docx_tmp, start=0, end=None)
        cv.close()

        with open(docx_tmp, "rb") as f:
            return f.read()
    finally:
        if pdf_tmp and os.path.exists(pdf_tmp):
            os.unlink(pdf_tmp)
        if docx_tmp and os.path.exists(docx_tmp):
            os.unlink(docx_tmp)


def replace_text_in_docx(content: bytes, replacements: dict) -> bytes:
    """
    Replace supplier text with brand text in a Word document.
    Operates run-by-run to preserve character formatting.
    Also handles the case where a word is split across multiple runs
    by working at the paragraph XML level.
    """
    from docx import Document
    from docx.oxml.ns import qn
    import lxml.etree as etree
    import copy

    if not replacements:
        return content

    doc = Document(io.BytesIO(content))

    def apply_replacements(text: str) -> str:
        for old, new in replacements.items():
            if old and old.strip() and new is not None:
                text = text.replace(old, new)
        return text

    def fix_runs_in_paragraph(para):
        """
        Merge all runs into one (preserving first run's format),
        apply replacement, then restore as single run.
        This fixes cases where a word is split across runs.
        """
        if not para.runs:
            return
        full_text = "".join(r.text for r in para.runs)
        replaced = apply_replacements(full_text)
        if replaced == full_text:
            return
        # Text changed — apply replacement run-by-run first
        for run in para.runs:
            run.text = apply_replacements(run.text)

    def process_paragraphs(paragraphs):
        for para in paragraphs:
            # First try simple per-run replacement
            for run in para.runs:
                if run.text:
                    run.text = apply_replacements(run.text)
            # Then fix any cross-run splits
            fix_runs_in_paragraph(para)

    # Paragraphs in body
    process_paragraphs(doc.paragraphs)

    # Paragraphs in tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                process_paragraphs(cell.paragraphs)

    # Headers and footers
    for section in doc.sections:
        process_paragraphs(section.header.paragraphs)
        process_paragraphs(section.footer.paragraphs)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def replace_images_in_docx(content: bytes, brand_logo_paths: list) -> bytes:
    """
    Replace existing inline images in a docx with brand logo images.
    Works at the ZIP level: finds word/media/* entries and replaces them.
    The document XML structure (positions, sizes) stays intact.
    """
    if not brand_logo_paths:
        return content

    # Read docx as zip
    with zipfile.ZipFile(io.BytesIO(content), "r") as zin:
        zip_data = {name: zin.read(name) for name in zin.namelist()}

    # Find existing media files (images), sorted by name
    media_files = sorted(
        [n for n in zip_data if n.startswith("word/media/") and not n.endswith("/")]
    )

    if not media_files:
        # No images in document — insert brand logos at the top instead
        return insert_logos_at_top(content, brand_logo_paths)

    # Replace images one-by-one, cycling brand logos if needed
    for i, media_key in enumerate(media_files):
        logo_path = brand_logo_paths[i % len(brand_logo_paths)]
        if not os.path.exists(logo_path):
            continue

        with open(logo_path, "rb") as f:
            logo_bytes = f.read()

        media_ext = os.path.splitext(media_key)[1].lower()
        logo_ext = os.path.splitext(logo_path)[1].lower()

        if logo_ext == media_ext:
            zip_data[media_key] = logo_bytes
        else:
            # Convert logo to match the media slot's format
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(logo_bytes))
                buf = io.BytesIO()
                if media_ext in (".jpg", ".jpeg"):
                    img = img.convert("RGB")
                    img.save(buf, "JPEG")
                elif media_ext == ".png":
                    img.save(buf, "PNG")
                elif media_ext == ".gif":
                    img.save(buf, "GIF")
                else:
                    img.save(buf, "PNG")
                zip_data[media_key] = buf.getvalue()
            except Exception as e:
                logger.warning(f"Logo format conversion failed ({logo_path}): {e}")
                zip_data[media_key] = logo_bytes

    # Write back as docx
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in zip_data.items():
            zout.writestr(name, data)
    return out.getvalue()


def insert_logos_at_top(content: bytes, logo_paths: list) -> bytes:
    """
    Fallback: insert brand logos at the very top of a docx
    when the original document contains no images to replace.
    """
    from docx import Document
    from docx.shared import Inches

    doc = Document(io.BytesIO(content))
    for logo_path in reversed(logo_paths):
        if not os.path.exists(logo_path):
            continue
        try:
            first = doc.paragraphs[0] if doc.paragraphs else doc.add_paragraph()
            run = first.insert_paragraph_before().add_run()
            run.add_picture(logo_path, width=Inches(1.5))
        except Exception as e:
            logger.warning(f"Could not insert logo {logo_path}: {e}")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def identify_supplier_info(text: str, openai_api_key: str) -> dict:
    """Ask GPT-4o-mini to identify supplier brand info in the document text"""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=openai_api_key)

    prompt = f"""Analyze this product datasheet text and extract the supplier/manufacturer brand information.

Return ONLY a JSON object with these fields (use null if not found):
{{
  "company_name": "...",
  "address": "...",
  "phone": "...",
  "email": "...",
  "website": "...",
  "logo_alt_text": "...",
  "other_brand_mentions": ["...", "..."]
}}

Datasheet text (first 3000 chars):
{text[:3000]}"""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0
    )
    try:
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {}


# ==================== LOGO SERVE ENDPOINT ====================

@router.get("/logo/{filename}")
async def serve_logo(filename: str):
    """Serve brand logo files"""
    from fastapi.responses import FileResponse
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    logo_path = os.path.join(BRAND_LOGOS_DIR, filename)
    if not os.path.exists(logo_path):
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(logo_path)


# ==================== BRAND ENDPOINTS ====================

@router.get("/brands")
async def list_brands(current_user: dict = Depends(get_current_user)):
    db = get_db()
    brands = await db.oem_brands.find({}, {"_id": 0}).to_list(100)
    return brands


@router.post("/brands")
async def create_brand(
    name: str = Form(...),
    address: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    website: str = Form(""),
    warrantyText: str = Form(""),
    current_user: dict = Depends(get_current_user)
):
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin only")
    db = get_db()
    brand = {
        "id": str(uuid4()),
        "name": name,
        "address": address,
        "phone": phone,
        "email": email,
        "website": website,
        "warrantyText": warrantyText,
        "approvedLogos": [],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.oem_brands.insert_one({**brand, "_id": brand["id"]})
    return brand


@router.put("/brands/{brand_id}")
async def update_brand(
    brand_id: str,
    name: str = Form(...),
    address: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    website: str = Form(""),
    warrantyText: str = Form(""),
    current_user: dict = Depends(get_current_user)
):
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin only")
    db = get_db()
    update = {
        "name": name,
        "address": address,
        "phone": phone,
        "email": email,
        "website": website,
        "warrantyText": warrantyText,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    result = await db.oem_brands.update_one({"id": brand_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Brand not found")
    brand = await db.oem_brands.find_one({"id": brand_id}, {"_id": 0})
    return brand


@router.delete("/brands/{brand_id}")
async def delete_brand(brand_id: str, current_user: dict = Depends(get_current_user)):
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin only")
    db = get_db()
    result = await db.oem_brands.delete_one({"id": brand_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Brand not found")
    return {"success": True}


@router.post("/brands/{brand_id}/logo")
async def upload_brand_logo(
    brand_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin only")
    db = get_db()
    brand = await db.oem_brands.find_one({"id": brand_id})
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    allowed = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail="Only PNG, JPG, SVG, WEBP allowed")

    filename = f"{brand_id}_{str(uuid4())[:8]}{ext}"
    logo_path = os.path.join(BRAND_LOGOS_DIR, filename)
    content = await file.read()
    with open(logo_path, "wb") as f:
        f.write(content)

    approved_logos = brand.get("approvedLogos", [])
    approved_logos.append(filename)
    await db.oem_brands.update_one(
        {"id": brand_id},
        {"$set": {"approvedLogos": approved_logos, "updatedAt": datetime.now(timezone.utc).isoformat()}}
    )
    return {"filename": filename, "approvedLogos": approved_logos}


@router.delete("/brands/{brand_id}/logo/{filename}")
async def delete_brand_logo(
    brand_id: str,
    filename: str,
    current_user: dict = Depends(get_current_user)
):
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin only")
    db = get_db()
    brand = await db.oem_brands.find_one({"id": brand_id})
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    logo_path = os.path.join(BRAND_LOGOS_DIR, filename)
    if os.path.exists(logo_path):
        os.remove(logo_path)

    approved_logos = [l for l in (brand.get("approvedLogos") or []) if l != filename]
    await db.oem_brands.update_one({"id": brand_id}, {"$set": {"approvedLogos": approved_logos}})
    return {"approvedLogos": approved_logos}


# ==================== DATASHEET PROCESSING ====================

@router.post("/process")
async def process_datasheet(
    file: UploadFile = File(...),
    brand_id: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload supplier datasheet → AI identifies supplier info → rebrand → return OEM DOCX.

    Strategy:
    - .docx input  → text replace in-place + swap inline images with brand logos
    - .pdf input   → convert to DOCX preserving layout (pdf2docx),
                     then text replace + swap inline images with brand logos
    """
    db = get_db()

    brand = await db.oem_brands.find_one({"id": brand_id}, {"_id": 0})
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    raw_content = await file.read()
    filename = file.filename.lower()

    # --- Step 1: get a DOCX with preserved layout ---
    if filename.endswith(".docx"):
        docx_content = raw_content
    elif filename.endswith(".pdf"):
        logger.info("Converting PDF → DOCX with layout preservation…")
        try:
            docx_content = convert_pdf_to_docx(raw_content)
        except Exception as e:
            logger.error(f"pdf2docx conversion failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"PDF conversion failed: {e}"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Only .docx and .pdf files are supported"
        )

    # --- Step 2: extract text for AI analysis ---
    text = extract_text_from_docx(docx_content)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    # --- Step 3: AI identifies supplier brand info ---
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    supplier_info = {}
    if openai_key:
        try:
            supplier_info = await identify_supplier_info(text, openai_key)
            logger.info(f"Supplier info identified: {supplier_info}")
        except Exception as e:
            logger.error(f"AI identification failed: {e}")

    # --- Step 4: build text replacement map ---
    replacements = {}
    if supplier_info.get("company_name") and brand.get("name"):
        replacements[supplier_info["company_name"]] = brand["name"]
    if supplier_info.get("address") and brand.get("address"):
        replacements[supplier_info["address"]] = brand["address"]
    if supplier_info.get("phone") and brand.get("phone"):
        replacements[supplier_info["phone"]] = brand["phone"]
    if supplier_info.get("email") and brand.get("email"):
        replacements[supplier_info["email"]] = brand["email"]
    if supplier_info.get("website") and brand.get("website"):
        replacements[supplier_info["website"]] = brand["website"]
    for mention in (supplier_info.get("other_brand_mentions") or []):
        if mention and mention.strip():
            replacements[mention] = brand["name"]

    # --- Step 5: replace text (preserves all formatting / structure) ---
    output_bytes = replace_text_in_docx(docx_content, replacements)

    # --- Step 6: replace inline images with brand logos ---
    logo_paths = [
        os.path.join(BRAND_LOGOS_DIR, fn)
        for fn in (brand.get("approvedLogos") or [])
        if os.path.exists(os.path.join(BRAND_LOGOS_DIR, fn))
    ]
    if logo_paths:
        output_bytes = replace_images_in_docx(output_bytes, logo_paths)

    # --- Log job ---
    await db.oem_jobs.insert_one({
        "_id": str(uuid4()),
        "userId": current_user["id"],
        "brandId": brand_id,
        "brandName": brand["name"],
        "originalFilename": file.filename,
        "supplierInfo": supplier_info,
        "replacementsCount": len(replacements),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    })

    safe_brand = re.sub(r"[^a-zA-Z0-9_-]", "_", brand["name"])
    output_filename = f"OEM_{safe_brand}_{os.path.splitext(file.filename)[0]}.docx"

    return StreamingResponse(
        io.BytesIO(output_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{output_filename}"'}
    )
