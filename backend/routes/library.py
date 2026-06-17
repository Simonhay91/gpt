"""Library routes — shared document library across departments.

A library item is stored in the `sources` collection with ``level="library"`` so
the existing RAG pipeline (which reads ``source_chunks`` by ``sourceId`` and
verifies sources in ``db.sources``) keeps working without any change. A single
item can be shared with multiple departments at once via the
``sharedDepartments`` array, so one uploaded file is reused everywhere instead of
being duplicated per department.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import datetime, timezone
from pathlib import Path
import uuid
import hashlib
import json
import logging
import asyncio
import aiofiles

from middleware.auth import get_current_user, is_admin
from db.connection import get_db
from services.file_processor import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_pptx,
    extract_text_from_xlsx,
    extract_text_from_csv,
    extract_text_from_txt,
    extract_text_from_image,
    chunk_text,
    chunk_tabular_text,
)
from services.rag import get_embedding

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/library", tags=["library"])

ROOT_DIR = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
LIBRARY_PROJECT_ID = "__library__"

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
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}


# ==================== HELPERS ====================

def _compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_text(content: bytes, file_type: str) -> str:
    """Route raw bytes to the right extractor based on file type."""
    if file_type == "pdf":
        return extract_text_from_pdf(content)
    if file_type == "docx":
        return extract_text_from_docx(content)
    if file_type == "pptx":
        return extract_text_from_pptx(content)
    if file_type == "xlsx":
        return extract_text_from_xlsx(content)
    if file_type == "csv":
        return extract_text_from_csv(content)
    if file_type in ("txt", "md"):
        return extract_text_from_txt(content)
    if file_type in ("png", "jpg", "jpeg", "gif", "webp"):
        return extract_text_from_image(content)
    return ""


def _do_chunking(text: str, file_type: str):
    if file_type in ("xlsx", "csv"):
        return chunk_tabular_text(text)
    return chunk_text(text)


def _parse_department_ids(raw: Optional[str]) -> List[str]:
    """Accept either a JSON array string or a comma-separated string."""
    if not raw:
        return []
    raw = raw.strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed if str(x).strip()]
    except (json.JSONDecodeError, TypeError):
        pass
    return [part.strip() for part in raw.split(",") if part.strip()]


def _parse_tags(raw: Optional[str]) -> List[str]:
    return _parse_department_ids(raw)  # same parsing rules (JSON array or CSV)


async def _managed_department_ids(db, current_user: dict) -> set:
    """Department ids the user is allowed to manage (admin → all)."""
    if is_admin(current_user["email"]):
        depts = await db.departments.find({}, {"_id": 0, "id": 1}).to_list(1000)
        return {d["id"] for d in depts}
    managed = await db.departments.find(
        {"managers": current_user["id"]}, {"_id": 0, "id": 1}
    ).to_list(1000)
    return {d["id"] for d in managed}


def _user_can_access(current_user: dict, item: dict) -> bool:
    if is_admin(current_user["email"]):
        return True
    if item.get("isGlobalLibrary"):
        return True
    user_depts = set(current_user.get("departments", []))
    return bool(user_depts & set(item.get("sharedDepartments", [])))


async def _enrich_with_department_names(db, items: List[dict]) -> List[dict]:
    """Attach human-readable department names to each item's shared list."""
    all_dept_ids = set()
    for it in items:
        all_dept_ids.update(it.get("sharedDepartments", []))
    names = {}
    if all_dept_ids:
        docs = await db.departments.find(
            {"id": {"$in": list(all_dept_ids)}}, {"_id": 0, "id": 1, "name": 1}
        ).to_list(1000)
        names = {d["id"]: d["name"] for d in docs}
    for it in items:
        it["sharedDepartmentNames"] = [
            {"id": did, "name": names.get(did, "Unknown")}
            for did in it.get("sharedDepartments", [])
        ]
    return items


# ==================== BACKGROUND EMBEDDING ====================

async def _embed_with_retry(text: str, max_retries: int = 5) -> Optional[List[float]]:
    """Call get_embedding with exponential backoff on rate-limit errors (429)."""
    for attempt in range(max_retries):
        try:
            result = await get_embedding(text)
            return result
        except Exception as exc:
            msg = str(exc)
            is_rate_limit = "429" in msg or "rate_limit" in msg.lower() or "rate limit" in msg.lower()
            if is_rate_limit and attempt < max_retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s
                logger.warning(f"Rate limit hit, retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait)
            else:
                logger.error(f"Embedding failed after {attempt + 1} attempts: {exc}")
                return None
    return None


async def _generate_embeddings_background(source_id: str, chunks: list):
    """Generate embeddings for all chunks in the background.

    Called after the upload endpoint returns so the HTTP response is not
    blocked by N sequential OpenAI API calls.  Updates each chunk in-place
    and flips the source status to ``active`` when done.

    Rate-limit protection:
    - Small pause every 20 chunks to avoid hitting TPM limits.
    - Per-chunk retry with exponential backoff on 429 errors.
    """
    db = get_db()
    failed = 0
    try:
        for i, chunk_content in enumerate(chunks):
            embedding = await _embed_with_retry(chunk_content)
            if embedding is None:
                failed += 1
            await db.source_chunks.update_one(
                {"sourceId": source_id, "chunkIndex": i},
                {"$set": {"embedding": embedding}},
            )
            # Pause every 20 chunks to stay under OpenAI TPM/RPM limits
            if (i + 1) % 20 == 0:
                logger.info(f"Library embedding progress {source_id}: {i + 1}/{len(chunks)} chunks")
                await asyncio.sleep(1.0)

        await db.sources.update_one(
            {"id": source_id},
            {"$set": {"status": "active", "updatedAt": _now_iso()}},
        )
        logger.info(
            f"Library embeddings done for {source_id}: "
            f"{len(chunks) - failed}/{len(chunks)} chunks embedded, {failed} failed"
        )
    except Exception as exc:
        logger.error(f"Library embedding background error for {source_id}: {exc}")
        await db.sources.update_one(
            {"id": source_id},
            {"$set": {"status": "active", "updatedAt": _now_iso()}},
        )


# ==================== UPLOAD ====================

@router.post("/upload")
async def upload_library_item(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    departmentIds: Optional[str] = Form(None),
    isGlobal: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """Upload a file to the library and share it with one or more departments.

    Only an admin or a department manager can upload. A manager can only share
    with departments they manage.
    """
    db = get_db()

    dept_ids = _parse_department_ids(departmentIds)
    is_global = str(isGlobal).lower() in ("1", "true", "yes") if isGlobal else False

    # Permission: admin or manager of every target department.
    managed = await _managed_department_ids(db, current_user)
    if not is_admin(current_user["email"]):
        if is_global:
            raise HTTPException(status_code=403, detail="Only admin can publish to all departments")
        if not dept_ids:
            raise HTTPException(status_code=400, detail="Select at least one department")
        not_managed = [d for d in dept_ids if d not in managed]
        if not_managed:
            raise HTTPException(status_code=403, detail="You can only share with departments you manage")

    if file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    file_type = SUPPORTED_MIME_TYPES[file.content_type]
    try:
        extracted_text = _extract_text(content, file_type)
    except Exception as e:
        logger.error(f"Library extract error: {e}")
        raise HTTPException(status_code=400, detail="Could not read file content")

    if not extracted_text or len(extracted_text.strip()) < 10:
        raise HTTPException(status_code=400, detail="No text could be extracted from file")

    source_id = str(uuid.uuid4())
    content_hash = _compute_hash(extracted_text)
    chunks = _do_chunking(extracted_text, file_type)

    storage_filename = f"{source_id}.{file_type}"
    storage_path = UPLOAD_DIR / storage_filename
    async with aiofiles.open(storage_path, "wb") as f:
        await f.write(content)

    item = {
        "id": source_id,
        "level": "library",
        "ownerId": current_user["id"],
        "ownerEmail": current_user["email"],
        "projectId": None,
        "departmentId": None,
        "sharedDepartments": dept_ids,
        "isGlobalLibrary": is_global,
        "kind": "file",
        "title": (title or file.filename or "Untitled").strip(),
        "description": (description or "").strip(),
        "tags": _parse_tags(tags),
        "originalName": file.filename,
        "mimeType": file.content_type,
        "sizeBytes": len(content),
        "storagePath": storage_filename,
        "version": 1,
        "contentHash": content_hash,
        # "processing" until background embeddings finish; RAG still works
        # because get_relevant_chunks falls back to keyword scoring when
        # embedding is None.
        "status": "processing",
        "createdAt": _now_iso(),
        "createdBy": current_user["id"],
        "createdByEmail": current_user["email"],
        "updatedAt": None,
    }
    await db.sources.insert_one(item)

    # Save all chunks immediately (no embeddings yet) so the item is
    # usable right away via keyword fallback in RAG.
    for i, chunk_content in enumerate(chunks):
        await db.source_chunks.insert_one({
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "projectId": LIBRARY_PROJECT_ID,
            "chunkIndex": i,
            "content": chunk_content,
            "embedding": None,
            "createdAt": _now_iso(),
        })

    # Generate embeddings in the background — response returns immediately.
    background_tasks.add_task(_generate_embeddings_background, source_id, chunks)

    item.pop("_id", None)
    item["chunkCount"] = len(chunks)
    return item


# ==================== LIST ====================

@router.get("")
async def list_library_items(
    manage: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """List library items.

    Default: items the user can access (their departments + global items).
    ``manage=true``: items the user can manage (admin → all; manager → items
    shared with departments they manage).
    """
    db = get_db()
    if manage and is_admin(current_user["email"]):
        query = {"level": "library"}
    elif manage:
        managed = await _managed_department_ids(db, current_user)
        query = {"level": "library", "sharedDepartments": {"$in": list(managed)}}
    elif is_admin(current_user["email"]):
        query = {"level": "library"}
    else:
        user_depts = current_user.get("departments", [])
        query = {
            "level": "library",
            "$or": [
                {"sharedDepartments": {"$in": user_depts}},
                {"isGlobalLibrary": True},
            ],
        }

    items = await db.sources.find(query, {"_id": 0}).sort("createdAt", -1).to_list(1000)

    source_ids = [it["id"] for it in items]
    chunk_counts = {}
    if source_ids:
        rows = await db.source_chunks.aggregate([
            {"$match": {"sourceId": {"$in": source_ids}}},
            {"$group": {"_id": "$sourceId", "count": {"$sum": 1}}},
        ]).to_list(None)
        chunk_counts = {r["_id"]: r["count"] for r in rows}
    for it in items:
        it["chunkCount"] = chunk_counts.get(it["id"], 0)

    await _enrich_with_department_names(db, items)
    return items


# ==================== SINGLE ITEM ====================

@router.get("/{item_id}")
async def get_library_item(item_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    item = await db.sources.find_one({"id": item_id, "level": "library"}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")
    if not _user_can_access(current_user, item):
        raise HTTPException(status_code=403, detail="Access denied")
    item["chunkCount"] = await db.source_chunks.count_documents({"sourceId": item_id})
    await _enrich_with_department_names(db, [item])
    return item


# ==================== UPDATE METADATA ====================

@router.put("/{item_id}")
async def update_library_item(
    item_id: str, data: dict, current_user: dict = Depends(get_current_user)
):
    db = get_db()
    item = await db.sources.find_one({"id": item_id, "level": "library"}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")

    managed = await _managed_department_ids(db, current_user)
    is_owner = item.get("ownerId") == current_user["id"]
    shares_managed_dept = bool(set(item.get("sharedDepartments", [])) & managed)
    if not is_admin(current_user["email"]) and not is_owner and not shares_managed_dept:
        raise HTTPException(status_code=403, detail="Not allowed to edit this item")

    updates = {"updatedAt": _now_iso()}
    if "title" in data:
        updates["title"] = (data.get("title") or "").strip()
    if "description" in data:
        updates["description"] = (data.get("description") or "").strip()
    if "tags" in data:
        tags = data.get("tags")
        updates["tags"] = tags if isinstance(tags, list) else _parse_tags(tags)

    await db.sources.update_one({"id": item_id}, {"$set": updates})
    updated = await db.sources.find_one({"id": item_id}, {"_id": 0})
    await _enrich_with_department_names(db, [updated])
    return updated


# ==================== SHARE ====================

@router.post("/{item_id}/share")
async def share_library_item(
    item_id: str, data: dict, current_user: dict = Depends(get_current_user)
):
    """Set the full list of departments an item is shared with.

    Body: ``{"departmentIds": ["a", "b"], "isGlobal": false}``. This replaces the
    existing share list, so one item can live in several departments at once.
    """
    db = get_db()
    item = await db.sources.find_one({"id": item_id, "level": "library"}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")

    new_dept_ids = data.get("departmentIds")
    if not isinstance(new_dept_ids, list):
        new_dept_ids = _parse_department_ids(new_dept_ids)
    new_dept_ids = [str(d) for d in new_dept_ids if str(d).strip()]
    is_global = bool(data.get("isGlobal", item.get("isGlobalLibrary", False)))

    managed = await _managed_department_ids(db, current_user)
    if not is_admin(current_user["email"]):
        if is_global:
            raise HTTPException(status_code=403, detail="Only admin can publish to all departments")
        # A manager may only add/remove departments they manage. Departments they
        # don't manage that were already shared are preserved untouched.
        existing = set(item.get("sharedDepartments", []))
        preserved = {d for d in existing if d not in managed}
        requested_manageable = {d for d in new_dept_ids if d in managed}
        not_allowed = {d for d in new_dept_ids if d not in managed and d not in existing}
        if not_allowed:
            raise HTTPException(status_code=403, detail="You can only share with departments you manage")
        new_dept_ids = list(preserved | requested_manageable)

    await db.sources.update_one(
        {"id": item_id},
        {"$set": {
            "sharedDepartments": new_dept_ids,
            "isGlobalLibrary": is_global,
            "updatedAt": _now_iso(),
        }},
    )
    updated = await db.sources.find_one({"id": item_id}, {"_id": 0})
    await _enrich_with_department_names(db, [updated])
    return updated


@router.delete("/{item_id}/share/{department_id}")
async def unshare_library_item(
    item_id: str, department_id: str, current_user: dict = Depends(get_current_user)
):
    """Remove a single department from an item's share list."""
    db = get_db()
    item = await db.sources.find_one({"id": item_id, "level": "library"}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")

    managed = await _managed_department_ids(db, current_user)
    if not is_admin(current_user["email"]) and department_id not in managed:
        raise HTTPException(status_code=403, detail="You can only manage departments you manage")

    await db.sources.update_one(
        {"id": item_id},
        {"$pull": {"sharedDepartments": department_id}, "$set": {"updatedAt": _now_iso()}},
    )
    updated = await db.sources.find_one({"id": item_id}, {"_id": 0})
    await _enrich_with_department_names(db, [updated])
    return updated


# ==================== DOWNLOAD ====================

@router.get("/{item_id}/download")
async def download_library_item(item_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    item = await db.sources.find_one({"id": item_id, "level": "library"}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")
    if not _user_can_access(current_user, item):
        raise HTTPException(status_code=403, detail="Access denied")
    if not item.get("storagePath"):
        raise HTTPException(status_code=404, detail="File not available")
    file_path = UPLOAD_DIR / item["storagePath"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing on server")
    return FileResponse(
        path=str(file_path),
        filename=item.get("originalName") or item.get("title") or "download",
        media_type=item.get("mimeType") or "application/octet-stream",
    )


# ==================== PREVIEW ====================

@router.get("/{item_id}/preview")
async def preview_library_item(item_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    item = await db.sources.find_one({"id": item_id, "level": "library"}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")
    if not _user_can_access(current_user, item):
        raise HTTPException(status_code=403, detail="Access denied")

    chunks = await db.source_chunks.find(
        {"sourceId": item_id},
        {"_id": 0, "content": 1, "chunkIndex": 1},
    ).sort("chunkIndex", 1).to_list(100)
    content = "\n\n---\n\n".join(c.get("content", "") for c in chunks)
    max_preview = 10000
    if len(content) > max_preview:
        content = content[:max_preview] + f"\n\n... [{max_preview}/{len(content)} chars]"
    return {
        "sourceId": item_id,
        "title": item.get("title"),
        "originalName": item.get("originalName"),
        "content": content,
        "totalChunks": len(chunks),
    }


# ==================== DELETE ====================

@router.delete("/{item_id}")
async def delete_library_item(item_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    item = await db.sources.find_one({"id": item_id, "level": "library"}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Library item not found")

    is_owner = item.get("ownerId") == current_user["id"]
    if not is_admin(current_user["email"]) and not is_owner:
        raise HTTPException(status_code=403, detail="Only admin or uploader can delete")

    if item.get("storagePath"):
        file_path = UPLOAD_DIR / item["storagePath"]
        if file_path.exists():
            file_path.unlink()

    await db.source_chunks.delete_many({"sourceId": item_id})
    await db.source_versions.delete_many({"sourceId": item_id})
    await db.sources.delete_one({"id": item_id})

    # Remove from any chat that had it activated so dangling ids don't linger.
    await db.chats.update_many(
        {"activeSourceIds": item_id},
        {"$pull": {"activeSourceIds": item_id}},
    )
    return {"message": "Library item deleted"}
