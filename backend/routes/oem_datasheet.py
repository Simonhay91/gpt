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

from middleware.auth import get_current_user, is_admin
from db.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/oem", tags=["oem"])

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")
BRAND_LOGOS_DIR = os.path.join(UPLOAD_DIR, "brand_logos")
os.makedirs(BRAND_LOGOS_DIR, exist_ok=True)


# ==================== HELPERS ====================

def extract_text_from_docx(content: bytes) -> str:
    """Extract text from Word document"""
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
    """Extract text from PDF"""
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


async def identify_supplier_info(text: str, openai_api_key: str) -> dict:
    """Ask GPT to identify supplier brand info in the document text"""
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


def replace_in_docx(content: bytes, replacements: dict) -> bytes:
    """Replace text strings in a Word document"""
    from docx import Document
    doc = Document(io.BytesIO(content))

    def replace_in_text(text: str, replacements: dict) -> str:
        for old, new in replacements.items():
            if old and new and old.strip():
                text = text.replace(old, new)
        return text

    # Replace in paragraphs
    for para in doc.paragraphs:
        if para.text:
            new_text = replace_in_text(para.text, replacements)
            if new_text != para.text:
                # Preserve formatting by replacing run by run
                for run in para.runs:
                    run.text = replace_in_text(run.text, replacements)

    # Replace in tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.text = replace_in_text(run.text, replacements)

    # Replace in headers and footers
    for section in doc.sections:
        for para in section.header.paragraphs:
            for run in para.runs:
                run.text = replace_in_text(run.text, replacements)
        for para in section.footer.paragraphs:
            for run in para.runs:
                run.text = replace_in_text(run.text, replacements)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def add_logos_to_docx(content: bytes, logo_paths: list) -> bytes:
    """Add brand logos at the top of the Word document"""
    from docx import Document
    from docx.shared import Inches
    doc = Document(io.BytesIO(content))

    # Insert logos at the beginning
    for logo_path in reversed(logo_paths):
        if os.path.exists(logo_path):
            try:
                # Insert before first paragraph
                para = doc.paragraphs[0] if doc.paragraphs else doc.add_paragraph()
                run = para.insert_paragraph_before().add_run()
                run.add_picture(logo_path, width=Inches(1.5))
            except Exception as e:
                logger.warning(f"Could not add logo {logo_path}: {e}")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def create_branded_docx_from_text(text: str, brand: dict, supplier_info: dict) -> bytes:
    """Create a new Word document from extracted text with brand info replaced"""
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Add brand header
    header_para = doc.add_paragraph()
    header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = header_para.add_run(brand.get("name", ""))
    run.bold = True
    run.font.size = Pt(16)

    # Add logos
    for logo_filename in (brand.get("approvedLogos") or []):
        logo_path = os.path.join(BRAND_LOGOS_DIR, logo_filename)
        if os.path.exists(logo_path):
            try:
                logo_para = doc.add_paragraph()
                logo_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = logo_para.add_run()
                run.add_picture(logo_path, width=Inches(1.5))
            except Exception as e:
                logger.warning(f"Logo insert failed: {e}")

    doc.add_paragraph()  # spacer

    # Build replacement map
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
            replacements[mention] = brand.get("name", mention)

    # Add document content with replacements
    for line in text.split("\n"):
        if line.strip():
            replaced_line = line
            for old, new in replacements.items():
                replaced_line = replaced_line.replace(old, new)
            doc.add_paragraph(replaced_line)

    # Footer with brand contact info
    doc.add_paragraph()
    footer_para = doc.add_paragraph()
    footer_text = []
    if brand.get("address"):
        footer_text.append(brand["address"])
    if brand.get("phone"):
        footer_text.append(brand["phone"])
    if brand.get("email"):
        footer_text.append(brand["email"])
    if brand.get("website"):
        footer_text.append(brand["website"])
    if brand.get("warrantyText"):
        footer_text.append(brand["warrantyText"])
    footer_para.add_run(" | ".join(footer_text))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ==================== LOGO SERVE ENDPOINT ====================

@router.get("/logo/{filename}")
async def serve_logo(filename: str):
    """Serve brand logo files"""
    from fastapi.responses import FileResponse
    logo_path = os.path.join(BRAND_LOGOS_DIR, filename)
    if not os.path.exists(logo_path):
        raise HTTPException(status_code=404, detail="Logo not found")
    # Basic security: no path traversal
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
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
    Main endpoint: upload supplier datasheet → AI rebrand → return OEM Word file
    """
    db = get_db()

    # Load brand
    brand = await db.oem_brands.find_one({"id": brand_id}, {"_id": 0})
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    # Read file
    content = await file.read()
    filename = file.filename.lower()

    # Extract text
    if filename.endswith(".docx"):
        text = extract_text_from_docx(content)
        is_docx = True
    elif filename.endswith(".pdf"):
        text = extract_text_from_pdf(content)
        is_docx = False
    else:
        raise HTTPException(
            status_code=400,
            detail="Only .docx and .pdf files are supported"
        )

    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    # AI: identify supplier info
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    supplier_info = {}
    if openai_key:
        try:
            supplier_info = await identify_supplier_info(text, openai_key)
            logger.info(f"Supplier info found: {supplier_info}")
        except Exception as e:
            logger.error(f"AI identification failed: {e}")

    # Build replacement map
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

    # Process document
    if is_docx and replacements:
        # In-place replacement in original .docx (preserves formatting)
        output_bytes = replace_in_docx(content, replacements)
        # Add logos on top
        logo_paths = [
            os.path.join(BRAND_LOGOS_DIR, fn)
            for fn in (brand.get("approvedLogos") or [])
        ]
        if logo_paths:
            output_bytes = add_logos_to_docx(output_bytes, logo_paths)
    else:
        # For PDF or when no replacements: build new branded .docx from text
        output_bytes = create_branded_docx_from_text(text, brand, supplier_info)

    # Log job
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

    # Return file
    safe_brand = re.sub(r'[^a-zA-Z0-9_-]', '_', brand["name"])
    output_filename = f"OEM_{safe_brand}_{os.path.splitext(file.filename)[0]}.docx"

    return StreamingResponse(
        io.BytesIO(output_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{output_filename}"'}
    )
