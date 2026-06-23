"""Global sources routes"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from datetime import datetime, timezone
from pathlib import Path
import uuid
import aiofiles
import httpx
import logging

from models.schemas import UrlSourceCreate
from middleware.auth import get_current_user
from middleware.permissions import require, resolve_permissions
from db.connection import get_db
from services.rag import get_embedding
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



@router.get("/admin/global-sources")
async def get_global_sources_admin(current_user: dict = Depends(require("global_sources", "read"))):
    """Get all global sources - admin only for full list"""
    db = get_db()
    
    sources = await db.sources.find({"projectId": GLOBAL_PROJECT_ID}, {"_id": 0}).to_list(1000)
    return sources


@router.get("/global-sources")
async def get_global_sources_for_users(current_user: dict = Depends(require("global_sources", "read"))):
    """Get global sources for any authenticated user"""
    db = get_db()
    sources = await db.sources.find({"projectId": GLOBAL_PROJECT_ID}, {"_id": 0}).to_list(1000)
    perms = await resolve_permissions(current_user)
    can_edit = "*" in perms or "global_sources:create" in perms
    return {"sources": sources, "canEdit": can_edit}


@router.post("/global-sources/upload")
async def user_upload_global_source(
    file: UploadFile = File(...),
    current_user: dict = Depends(require("global_sources", "create")),
):
    """User with permission uploads a global source file"""
    db = get_db()
    
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
        embedding = await get_embedding(chunk_content)
        chunk_doc = {
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "projectId": GLOBAL_PROJECT_ID,
            "chunkIndex": i,
            "content": chunk_content,
            "embedding": embedding,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.source_chunks.insert_one(chunk_doc)
    
    logger.info(f"User {current_user['email']} uploaded global source {file.filename}")
    return {**source_doc, "_id": None}


@router.delete("/global-sources/{source_id}")
async def user_delete_global_source(source_id: str, current_user: dict = Depends(require("global_sources", "delete"))):
    """User with permission deletes a global source"""
    db = get_db()

    source = await db.sources.find_one({"id": source_id, "projectId": GLOBAL_PROJECT_ID}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Global source not found")
    
    if source.get("storagePath"):
        file_path = UPLOAD_DIR / source["storagePath"]
        if file_path.exists():
            file_path.unlink()
    
    await db.source_chunks.delete_many({"sourceId": source_id})
    await db.sources.delete_one({"id": source_id})
    await db.chats.update_many(
        {"activeSourceIds": source_id},
        {"$pull": {"activeSourceIds": source_id}}
    )

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
    current_user: dict = Depends(require("global_sources", "create")),
):
    """Admin uploads a global source file"""
    db = get_db()
    
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
        embedding = await get_embedding(chunk_content)
        chunk_doc = {
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "projectId": GLOBAL_PROJECT_ID,
            "chunkIndex": i,
            "content": chunk_content,
            "embedding": embedding,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.source_chunks.insert_one(chunk_doc)
    
    return {**source_doc, "_id": None}


@router.post("/admin/global-sources/url")
async def admin_add_global_url_source(url_data: UrlSourceCreate, current_user: dict = Depends(require("global_sources", "create"))):
    """Admin adds a URL as global source"""
    db = get_db()
    
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
        embedding = await get_embedding(chunk_content)
        chunk_doc = {
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "projectId": GLOBAL_PROJECT_ID,
            "chunkIndex": i,
            "content": chunk_content,
            "embedding": embedding,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.source_chunks.insert_one(chunk_doc)
    
    return {**source_doc, "_id": None}


@router.delete("/admin/global-sources/{source_id}")
async def admin_delete_global_source(source_id: str, current_user: dict = Depends(require("global_sources", "delete"))):
    """Admin deletes a global source"""
    db = get_db()
    
    source = await db.sources.find_one({"id": source_id, "projectId": GLOBAL_PROJECT_ID}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Global source not found")
    
    if source.get("storagePath"):
        file_path = UPLOAD_DIR / source["storagePath"]
        if file_path.exists():
            file_path.unlink()
    
    await db.source_chunks.delete_many({"sourceId": source_id})
    await db.sources.delete_one({"id": source_id})
    await db.chats.update_many(
        {"activeSourceIds": source_id},
        {"$pull": {"activeSourceIds": source_id}}
    )

    return {"message": "Global source deleted"}


@router.put("/admin/global-sources/{source_id}/company-info")
async def set_company_info(source_id: str, data: dict, current_user: dict = Depends(require("global_sources", "update"))):
    """Mark/unmark a global source as the singleton "Company Info" source.

    Only one source can be the company info at a time, so setting a new one
    clears the flag on all others. This source is auto-injected (with a small
    char budget) into every chat as background context.
    """
    db = get_db()

    source = await db.sources.find_one({"id": source_id, "projectId": GLOBAL_PROJECT_ID}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Global source not found")

    enabled = bool(data.get("isCompanyInfo", True))

    if enabled:
        # Singleton: clear the flag everywhere else first.
        await db.sources.update_many(
            {"isCompanyInfo": True},
            {"$set": {"isCompanyInfo": False}}
        )
        await db.sources.update_one({"id": source_id}, {"$set": {"isCompanyInfo": True}})
    else:
        await db.sources.update_one({"id": source_id}, {"$set": {"isCompanyInfo": False}})

    return {"message": "Company info updated", "sourceId": source_id, "isCompanyInfo": enabled}


@router.get("/admin/global-sources/{source_id}/preview")
async def admin_preview_global_source(source_id: str, current_user: dict = Depends(require("global_sources", "read"))):
    """Preview global source content"""
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
        "wordCount": len(full_text.split())
    }


@router.post("/admin/global-sources/backfill-embeddings")
async def backfill_global_source_embeddings(current_user: dict = Depends(require("backfill", "run"))):
    """Backfill embeddings for existing global source chunks that don't have them.

    Safe to call multiple times — only processes chunks where embedding is missing.
    """
    db = get_db()

    chunks = await db.source_chunks.find(
        {"projectId": GLOBAL_PROJECT_ID, "embedding": {"$in": [None, []]}},
        {"_id": 1, "content": 1}
    ).to_list(5000)

    updated = 0
    failed = 0
    for chunk in chunks:
        content = chunk.get("content", "")
        if not content:
            continue
        try:
            embedding = await get_embedding(content)
            if embedding:
                await db.source_chunks.update_one(
                    {"_id": chunk["_id"]},
                    {"$set": {"embedding": embedding}}
                )
                updated += 1
        except Exception as e:
            logger.warning(f"Backfill embedding failed for chunk {chunk.get('_id')}: {e}")
            failed += 1

    logger.info(f"Backfill complete: {updated} updated, {failed} failed")
    return {"updated": updated, "failed": failed, "total": len(chunks)}
