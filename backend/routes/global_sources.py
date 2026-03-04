"""Global sources routes"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from datetime import datetime, timezone
from pathlib import Path
import uuid
import aiofiles
import httpx
import logging

from models.schemas import UrlSourceCreate
from middleware.auth import get_current_user, is_admin
from db.connection import get_db
from services.file_processor import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_pptx,
    extract_text_from_xlsx,
    extract_text_from_csv,
    extract_text_from_image,
    extract_text_from_txt,
    extract_text_from_html,
    chunk_text
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["global_sources"])

# Settings
ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 50 * 1024 * 1024
GLOBAL_PROJECT_ID = "__global__"

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/csv": "csv",
    "application/csv": "csv",
    "image/png": "png",
    "image/jpeg": "jpeg"
}


async def can_edit_global_sources(user: dict) -> bool:
    """Check if user can edit global sources"""
    if is_admin(user["email"]):
        return True
    return user.get("canEditGlobalSources", False)


@router.get("/admin/global-sources")
async def get_global_sources_admin(current_user: dict = Depends(get_current_user)):
    """Get all global sources - admin only for full list"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    sources = await db.sources.find({"projectId": GLOBAL_PROJECT_ID}, {"_id": 0}).to_list(1000)
    return sources


@router.get("/global-sources")
async def get_global_sources_for_users(current_user: dict = Depends(get_current_user)):
    """Get global sources for any authenticated user"""
    db = get_db()
    sources = await db.sources.find({"projectId": GLOBAL_PROJECT_ID}, {"_id": 0}).to_list(1000)
    can_edit = await can_edit_global_sources(current_user)
    return {"sources": sources, "canEdit": can_edit}


@router.post("/global-sources/upload")
async def user_upload_global_source(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """User with permission uploads a global source file"""
    db = get_db()
    if not await can_edit_global_sources(current_user):
        raise HTTPException(status_code=403, detail="You don't have permission to edit global sources")
    
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")
    
    file_type = ALLOWED_TYPES[file.content_type]
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB")
    
    source_id = str(uuid.uuid4())
    file_ext = file.filename.split(".")[-1] if "." in file.filename else file_type
    storage_name = f"global_{source_id}.{file_ext}"
    file_path = UPLOAD_DIR / storage_name
    
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    # Extract text
    if file_type == "pdf":
        extracted_text = extract_text_from_pdf(content)
    elif file_type == "docx":
        extracted_text = extract_text_from_docx(content)
    elif file_type == "pptx":
        extracted_text = extract_text_from_pptx(content)
    elif file_type == "xlsx":
        extracted_text = extract_text_from_xlsx(content)
    elif file_type == "csv":
        extracted_text = extract_text_from_csv(content)
    elif file_type in ["png", "jpeg", "jpg"]:
        extracted_text = extract_text_from_image(content)
    else:
        extracted_text = extract_text_from_txt(content)
    
    chunks = chunk_text(extracted_text)
    
    source_doc = {
        "id": source_id,
        "projectId": GLOBAL_PROJECT_ID,
        "kind": "file",
        "originalName": file.filename,
        "mimeType": file.content_type,
        "storagePath": storage_name,
        "sizeBytes": len(content),
        "uploadedBy": current_user["id"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "chunkCount": len(chunks)
    }
    await db.sources.insert_one(source_doc)
    
    for i, chunk_content in enumerate(chunks):
        chunk_doc = {
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "projectId": GLOBAL_PROJECT_ID,
            "chunkIndex": i,
            "content": chunk_content,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.source_chunks.insert_one(chunk_doc)
    
    logger.info(f"User {current_user['email']} uploaded global source {file.filename}")
    return {**source_doc, "_id": None}


@router.delete("/global-sources/{source_id}")
async def user_delete_global_source(source_id: str, current_user: dict = Depends(get_current_user)):
    """User with permission deletes a global source"""
    db = get_db()
    if not await can_edit_global_sources(current_user):
        raise HTTPException(status_code=403, detail="You don't have permission to edit global sources")
    
    source = await db.sources.find_one({"id": source_id, "projectId": GLOBAL_PROJECT_ID}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Global source not found")
    
    if not is_admin(current_user["email"]) and source.get("uploadedBy") != current_user["id"]:
        raise HTTPException(status_code=403, detail="You can only delete sources you uploaded")
    
    if source.get("storagePath"):
        file_path = UPLOAD_DIR / source["storagePath"]
        if file_path.exists():
            file_path.unlink()
    
    await db.source_chunks.delete_many({"sourceId": source_id})
    await db.sources.delete_one({"id": source_id})
    
    return {"message": "Global source deleted"}


@router.get("/global-sources/{source_id}/preview")
async def user_preview_global_source(source_id: str, current_user: dict = Depends(get_current_user)):
    """Preview global source content - any authenticated user"""
    db = get_db()
    source = await db.sources.find_one({"id": source_id, "projectId": GLOBAL_PROJECT_ID}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Global source not found")
    
    chunks = await db.source_chunks.find(
        {"sourceId": source_id},
        {"_id": 0, "content": 1, "chunkIndex": 1}
    ).sort("chunkIndex", 1).to_list(1000)
    
    full_text = "\n\n".join([c["content"] for c in chunks])
    
    return {
        "id": source_id,
        "name": source.get("originalName") or source.get("url"),
        "text": full_text,
        "chunkCount": len(chunks),
        "wordCount": len(full_text.split()),
        "uploadedBy": source.get("uploadedBy")
    }


# ==================== ADMIN GLOBAL SOURCES ====================

@router.post("/admin/global-sources/upload")
async def admin_upload_global_source(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Admin uploads a global source file"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")
    
    file_type = ALLOWED_TYPES[file.content_type]
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB")
    
    source_id = str(uuid.uuid4())
    file_ext = file.filename.split(".")[-1] if "." in file.filename else file_type
    storage_name = f"global_{source_id}.{file_ext}"
    file_path = UPLOAD_DIR / storage_name
    
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    # Extract text
    if file_type == "pdf":
        extracted_text = extract_text_from_pdf(content)
    elif file_type == "docx":
        extracted_text = extract_text_from_docx(content)
    elif file_type == "pptx":
        extracted_text = extract_text_from_pptx(content)
    elif file_type == "xlsx":
        extracted_text = extract_text_from_xlsx(content)
    elif file_type == "csv":
        extracted_text = extract_text_from_csv(content)
    elif file_type in ["png", "jpeg", "jpg"]:
        extracted_text = extract_text_from_image(content)
    else:
        extracted_text = extract_text_from_txt(content)
    
    chunks = chunk_text(extracted_text)
    
    source_doc = {
        "id": source_id,
        "projectId": GLOBAL_PROJECT_ID,
        "kind": "file",
        "originalName": file.filename,
        "mimeType": file.content_type,
        "storagePath": storage_name,
        "sizeBytes": len(content),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "chunkCount": len(chunks)
    }
    await db.sources.insert_one(source_doc)
    
    for i, chunk_content in enumerate(chunks):
        chunk_doc = {
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "projectId": GLOBAL_PROJECT_ID,
            "chunkIndex": i,
            "content": chunk_content,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.source_chunks.insert_one(chunk_doc)
    
    return {**source_doc, "_id": None}


@router.post("/admin/global-sources/url")
async def admin_add_global_url_source(url_data: UrlSourceCreate, current_user: dict = Depends(get_current_user)):
    """Admin adds a URL as global source"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    url = str(url_data.url)
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            html_content = response.text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}")
    
    extracted_text = extract_text_from_html(html_content)
    
    if not extracted_text or len(extracted_text) < 50:
        raise HTTPException(status_code=400, detail="Could not extract meaningful content from URL")
    
    chunks = chunk_text(extracted_text)
    
    source_id = str(uuid.uuid4())
    source_doc = {
        "id": source_id,
        "projectId": GLOBAL_PROJECT_ID,
        "kind": "url",
        "url": url,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "chunkCount": len(chunks)
    }
    await db.sources.insert_one(source_doc)
    
    for i, chunk_content in enumerate(chunks):
        chunk_doc = {
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "projectId": GLOBAL_PROJECT_ID,
            "chunkIndex": i,
            "content": chunk_content,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.source_chunks.insert_one(chunk_doc)
    
    return {**source_doc, "_id": None}


@router.delete("/admin/global-sources/{source_id}")
async def admin_delete_global_source(source_id: str, current_user: dict = Depends(get_current_user)):
    """Admin deletes a global source"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    source = await db.sources.find_one({"id": source_id, "projectId": GLOBAL_PROJECT_ID}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Global source not found")
    
    if source.get("storagePath"):
        file_path = UPLOAD_DIR / source["storagePath"]
        if file_path.exists():
            file_path.unlink()
    
    await db.source_chunks.delete_many({"sourceId": source_id})
    await db.sources.delete_one({"id": source_id})
    
    return {"message": "Global source deleted"}


@router.get("/admin/global-sources/{source_id}/preview")
async def admin_preview_global_source(source_id: str, current_user: dict = Depends(get_current_user)):
    """Preview global source content"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    source = await db.sources.find_one({"id": source_id, "projectId": GLOBAL_PROJECT_ID}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Global source not found")
    
    chunks = await db.source_chunks.find(
        {"sourceId": source_id},
        {"_id": 0, "content": 1, "chunkIndex": 1}
    ).sort("chunkIndex", 1).to_list(1000)
    
    full_text = "\n\n".join([c["content"] for c in chunks])
    
    return {
        "id": source_id,
        "name": source.get("originalName") or source.get("url"),
        "text": full_text,
        "chunkCount": len(chunks),
        "wordCount": len(full_text.split())
    }
