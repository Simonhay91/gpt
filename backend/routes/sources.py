"""Source management routes"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from typing import List
from datetime import datetime, timezone
from pathlib import Path
import uuid
import aiofiles
import httpx

from models.schemas import (
    SourceResponse,
    ActiveSourcesUpdate,
    UrlSourceCreate,
    SearchRequest
)
from middleware.auth import get_current_user
from db.connection import get_db
from routes.projects import (
    verify_project_ownership, 
    verify_project_access,
    check_project_access,
    can_manage_sources
)
from services.file_processor import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_txt,
    extract_text_from_pptx,
    extract_text_from_xlsx,
    extract_text_from_csv,
    extract_text_from_image,
    extract_text_from_html,
    chunk_text,
    chunk_tabular_text
)

router = APIRouter(prefix="/api", tags=["sources"])

# Settings
ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 50 * 1024 * 1024

SUPPORTED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/csv": "csv",
    "application/csv": "csv",
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpg",
}


@router.post("/projects/{project_id}/sources/upload", response_model=SourceResponse)
async def upload_source(
    project_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a file source to a project"""
    db = get_db()
    access = await check_project_access(current_user, project_id, required_role="manager")
    if not can_manage_sources(access["role"]):
        raise HTTPException(status_code=403, detail="Only owners and managers can upload sources")
    
    if file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=400, 
            detail="Unsupported file type. Supported: PDF, DOCX, PPTX, XLSX, TXT, MD, PNG, JPEG"
        )
    
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File size exceeds maximum of {MAX_FILE_SIZE // (1024*1024)}MB")
    
    file_type = SUPPORTED_MIME_TYPES[file.content_type]
    
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
    
    if file_type not in ["png", "jpeg", "jpg"]:
        if not extracted_text or len(extracted_text.strip()) < 10:
            raise HTTPException(
                status_code=400, 
                detail="This file appears to be empty or contains no extractable text."
            )
    
    source_id = str(uuid.uuid4())
    storage_filename = f"{source_id}.{file_type}"
    storage_path = UPLOAD_DIR / storage_filename
    
    async with aiofiles.open(storage_path, 'wb') as f:
        await f.write(content)
    
    if file_type in ["xlsx", "csv"]:
        chunks = chunk_tabular_text(extracted_text)
    else:
        chunks = chunk_text(extracted_text)
    
    source_doc = {
        "id": source_id,
        "projectId": project_id,
        "kind": "file",
        "originalName": file.filename,
        "url": None,
        "mimeType": file.content_type,
        "sizeBytes": len(content),
        "storagePath": storage_filename,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.sources.insert_one(source_doc)
    
    for i, chunk_content in enumerate(chunks):
        chunk_doc = {
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "projectId": project_id,
            "chunkIndex": i,
            "content": chunk_content,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.source_chunks.insert_one(chunk_doc)
    
    return SourceResponse(
        id=source_id,
        projectId=project_id,
        kind="file",
        originalName=file.filename,
        url=None,
        mimeType=file.content_type,
        sizeBytes=len(content),
        createdAt=source_doc["createdAt"],
        chunkCount=len(chunks)
    )


@router.post("/projects/{project_id}/sources/upload-multiple")
async def upload_multiple_sources(
    project_id: str,
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload multiple file sources to a project"""
    db = get_db()
    await verify_project_access(project_id, current_user["id"])
    
    results = []
    errors = []
    
    for file in files:
        try:
            if file.content_type not in SUPPORTED_MIME_TYPES:
                errors.append({"filename": file.filename, "error": "Unsupported file type"})
                continue
            
            content = await file.read()
            
            if len(content) > MAX_FILE_SIZE:
                errors.append({"filename": file.filename, "error": f"File size exceeds maximum"})
                continue
            
            file_type = SUPPORTED_MIME_TYPES[file.content_type]
            
            try:
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
            except Exception as e:
                errors.append({"filename": file.filename, "error": str(e)[:100]})
                continue
            
            if file_type not in ["png", "jpeg", "jpg"]:
                if not extracted_text or len(extracted_text.strip()) < 10:
                    errors.append({"filename": file.filename, "error": "No extractable text"})
                    continue
            
            source_id = str(uuid.uuid4())
            storage_filename = f"{source_id}.{file_type}"
            storage_path = UPLOAD_DIR / storage_filename
            
            async with aiofiles.open(storage_path, 'wb') as f:
                await f.write(content)
            
            if file_type in ["xlsx", "csv"]:
                chunks = chunk_tabular_text(extracted_text)
            else:
                chunks = chunk_text(extracted_text)
            
            source_doc = {
                "id": source_id,
                "projectId": project_id,
                "kind": "file",
                "originalName": file.filename,
                "url": None,
                "mimeType": file.content_type,
                "sizeBytes": len(content),
                "storagePath": storage_filename,
                "createdAt": datetime.now(timezone.utc).isoformat()
            }
            await db.sources.insert_one(source_doc)
            
            for i, chunk_content in enumerate(chunks):
                chunk_doc = {
                    "id": str(uuid.uuid4()),
                    "sourceId": source_id,
                    "projectId": project_id,
                    "chunkIndex": i,
                    "content": chunk_content,
                    "createdAt": datetime.now(timezone.utc).isoformat()
                }
                await db.source_chunks.insert_one(chunk_doc)
            
            results.append({
                "id": source_id,
                "filename": file.filename,
                "chunkCount": len(chunks)
            })
            
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)[:100]})
    
    return {"uploaded": results, "errors": errors}


@router.post("/projects/{project_id}/sources/url", response_model=SourceResponse)
async def add_url_source(
    project_id: str,
    data: UrlSourceCreate,
    current_user: dict = Depends(get_current_user)
):
    """Add a URL source to a project"""
    db = get_db()
    await verify_project_ownership(project_id, current_user["id"])
    
    url = data.url.strip()
    
    if not url.startswith(('http://', 'https://')):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as http_client:
            response = await http_client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="URL fetch timed out")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"URL returned error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)[:100]}")
    
    content_type = response.headers.get('content-type', '')
    if 'text/html' not in content_type and 'text/plain' not in content_type:
        raise HTTPException(status_code=400, detail="URL must return HTML or text content")
    
    html_content = response.text
    extracted_text = extract_text_from_html(html_content)
    
    if not extracted_text or len(extracted_text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Could not extract meaningful text from this URL")
    
    source_id = str(uuid.uuid4())
    chunks = chunk_text(extracted_text)
    
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    display_name = f"{parsed_url.netloc}{parsed_url.path[:50]}"
    
    source_doc = {
        "id": source_id,
        "projectId": project_id,
        "kind": "url",
        "originalName": display_name,
        "url": url,
        "mimeType": "text/html",
        "sizeBytes": len(html_content.encode('utf-8')),
        "storagePath": None,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.sources.insert_one(source_doc)
    
    for i, chunk_content in enumerate(chunks):
        chunk_doc = {
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "projectId": project_id,
            "chunkIndex": i,
            "content": chunk_content,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.source_chunks.insert_one(chunk_doc)
    
    return SourceResponse(
        id=source_id,
        projectId=project_id,
        kind="url",
        originalName=display_name,
        url=url,
        mimeType="text/html",
        sizeBytes=source_doc["sizeBytes"],
        createdAt=source_doc["createdAt"],
        chunkCount=len(chunks)
    )


@router.get("/projects/{project_id}/sources", response_model=List[SourceResponse])
async def list_sources(project_id: str, current_user: dict = Depends(get_current_user)):
    """List all sources in a project"""
    db = get_db()
    await verify_project_ownership(project_id, current_user["id"])
    
    sources = await db.sources.find({"projectId": project_id}, {"_id": 0}).to_list(1000)
    
    result = []
    for s in sources:
        chunk_count = await db.source_chunks.count_documents({"sourceId": s["id"]})
        result.append(SourceResponse(
            id=s["id"],
            projectId=s["projectId"],
            kind=s["kind"],
            originalName=s.get("originalName"),
            url=s.get("url"),
            mimeType=s.get("mimeType"),
            sizeBytes=s.get("sizeBytes"),
            createdAt=s["createdAt"],
            chunkCount=chunk_count
        ))
    
    return result


@router.delete("/projects/{project_id}/sources/{source_id}")
async def delete_source(project_id: str, source_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a source from a project"""
    db = get_db()
    await verify_project_ownership(project_id, current_user["id"])
    
    source = await db.sources.find_one({"id": source_id, "projectId": project_id})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if source.get("storagePath"):
        file_path = UPLOAD_DIR / source["storagePath"]
        if file_path.exists():
            file_path.unlink()
    
    await db.source_chunks.delete_many({"sourceId": source_id})
    await db.sources.delete_one({"id": source_id})
    
    await db.chats.update_many(
        {"projectId": project_id},
        {"$pull": {"activeSourceIds": source_id}}
    )
    
    return {"message": "Source deleted successfully"}


@router.post("/projects/{project_id}/sources/search")
async def search_sources(project_id: str, search_data: SearchRequest, current_user: dict = Depends(get_current_user)):
    """Search through all source chunks in project - NO GPT, NO TOKENS"""
    db = get_db()
    await verify_project_access(project_id, current_user["id"])
    
    query = search_data.query.strip().lower()
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")
    
    sources = await db.sources.find({"projectId": project_id}, {"_id": 0}).to_list(1000)
    source_map = {s["id"]: s for s in sources}
    
    results = []
    chunks = await db.source_chunks.find({"projectId": project_id}, {"_id": 0}).to_list(10000)
    
    for chunk in chunks:
        content_lower = chunk["content"].lower()
        if query in content_lower:
            source = source_map.get(chunk["sourceId"], {})
            match_count = content_lower.count(query)
            
            idx = content_lower.find(query)
            start = max(0, idx - 150)
            end = min(len(chunk["content"]), idx + len(query) + 150)
            snippet = chunk["content"][start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(chunk["content"]):
                snippet = snippet + "..."
            
            results.append({
                "sourceId": chunk["sourceId"],
                "sourceName": source.get("originalName") or source.get("url", "Unknown"),
                "sourceKind": source.get("kind", "file"),
                "chunkIndex": chunk.get("chunkIndex", 0),
                "content": snippet,
                "matchCount": match_count
            })
    
    results.sort(key=lambda x: x["matchCount"], reverse=True)
    return results[:search_data.limit]


@router.get("/projects/{project_id}/sources/{source_id}/download")
async def download_source(project_id: str, source_id: str, current_user: dict = Depends(get_current_user)):
    """Download a single source file"""
    db = get_db()
    await verify_project_access(project_id, current_user["id"])
    
    source = await db.sources.find_one({"id": source_id, "projectId": project_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if source["kind"] != "file" or not source.get("storagePath"):
        raise HTTPException(status_code=400, detail="This source cannot be downloaded")
    
    file_path = UPLOAD_DIR / source["storagePath"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=file_path,
        filename=source.get("originalName", source["storagePath"]),
        media_type=source.get("mimeType", "application/octet-stream")
    )


@router.get("/projects/{project_id}/sources/{source_id}/preview")
async def preview_source(project_id: str, source_id: str, current_user: dict = Depends(get_current_user)):
    """Get source preview - extracted text content with quality info"""
    db = get_db()
    await verify_project_access(project_id, current_user["id"])
    
    source = await db.sources.find_one({"id": source_id, "projectId": project_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    chunks = await db.source_chunks.find(
        {"sourceId": source_id}, 
        {"_id": 0, "content": 1, "chunkIndex": 1}
    ).sort("chunkIndex", 1).to_list(1000)
    
    full_text = "\n\n".join([c["content"] for c in chunks])
    
    char_count = len(full_text)
    word_count = len(full_text.split())
    
    is_image = source.get("mimeType", "").startswith("image/")
    quality = "good"
    quality_message = "Текст извлечён успешно"
    
    if char_count == 0:
        quality = "empty"
        quality_message = "Текст не извлечён"
    elif is_image:
        if "[Image: No text detected]" in full_text or "[Image: OCR failed" in full_text:
            quality = "poor"
            quality_message = "OCR не смог распознать текст"
        elif word_count < 10:
            quality = "low"
            quality_message = "Мало текста распознано"
        else:
            quality_message = f"OCR распознал {word_count} слов"
    elif word_count < 20:
        quality = "low"
        quality_message = "Мало текста извлечено"
    
    return {
        "id": source_id,
        "name": source.get("originalName") or source.get("url"),
        "kind": source["kind"],
        "mimeType": source.get("mimeType"),
        "text": full_text,
        "chunkCount": len(chunks),
        "charCount": char_count,
        "wordCount": word_count,
        "quality": quality,
        "qualityMessage": quality_message
    }


@router.get("/projects/{project_id}/sources/download-all")
async def download_all_sources(project_id: str, current_user: dict = Depends(get_current_user)):
    """Download all file sources as a ZIP archive"""
    import zipfile
    from io import BytesIO
    
    db = get_db()
    await verify_project_access(project_id, current_user["id"])
    
    sources = await db.sources.find({
        "projectId": project_id,
        "kind": "file"
    }, {"_id": 0}).to_list(1000)
    
    if not sources:
        raise HTTPException(status_code=404, detail="No files to download")
    
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for source in sources:
            if source.get("storagePath"):
                file_path = UPLOAD_DIR / source["storagePath"]
                if file_path.exists():
                    filename = source.get("originalName", source["storagePath"])
                    with open(file_path, 'rb') as f:
                        zip_file.writestr(filename, f.read())
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=project_files.zip"}
    )


# ==================== ACTIVE SOURCES ====================

@router.post("/chats/{chat_id}/active-sources")
async def set_active_sources(chat_id: str, data: ActiveSourcesUpdate, current_user: dict = Depends(get_current_user)):
    """Set the active sources for a chat"""
    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    await verify_project_ownership(chat["projectId"], current_user["id"])
    
    if data.sourceIds:
        sources = await db.sources.find({
            "id": {"$in": data.sourceIds},
            "projectId": chat["projectId"]
        }).to_list(1000)
        
        valid_ids = {s["id"] for s in sources}
        invalid_ids = set(data.sourceIds) - valid_ids
        
        if invalid_ids:
            raise HTTPException(status_code=400, detail=f"Invalid source IDs: {invalid_ids}")
    
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"activeSourceIds": data.sourceIds}}
    )
    
    return {"message": "Active sources updated", "activeSourceIds": data.sourceIds}


@router.get("/chats/{chat_id}/active-sources")
async def get_active_sources(chat_id: str, current_user: dict = Depends(get_current_user)):
    """Get the active sources for a chat"""
    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    await verify_project_ownership(chat["projectId"], current_user["id"])
    
    active_source_ids = chat.get("activeSourceIds", [])
    
    if not active_source_ids:
        return {"activeSources": []}
    
    sources = await db.sources.find({
        "id": {"$in": active_source_ids},
        "projectId": chat["projectId"]
    }, {"_id": 0}).to_list(1000)
    
    return {"activeSources": sources}
