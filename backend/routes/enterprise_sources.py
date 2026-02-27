"""
Enterprise Sources Routes - Multi-level knowledge management
Levels: Personal → Project → Department → Global
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import List, Optional
import uuid
import hashlib
from datetime import datetime, timezone

router = APIRouter(tags=["enterprise-sources"])


def setup_enterprise_source_routes(
    db,
    get_current_user,
    is_admin,
    audit_service,
    version_service,
    extract_text_func,
    chunk_text_func,
    UPLOAD_DIR,
    MAX_FILE_SIZE,
    SUPPORTED_MIME_TYPES
):
    """Setup enterprise source routes with dependencies"""
    
    def compute_hash(content: str) -> str:
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
    
    # ==================== PERSONAL SOURCES ====================
    
    @router.post("/api/personal-sources/upload")
    async def upload_personal_source(
        file: UploadFile = File(...),
        current_user: dict = Depends(get_current_user)
    ):
        """Upload personal source (fully private)"""
        if file.content_type not in SUPPORTED_MIME_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large")
        
        # Extract text
        file_type = SUPPORTED_MIME_TYPES[file.content_type]
        extracted_text = await extract_text_func(content, file_type)
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            raise HTTPException(status_code=400, detail="No text extracted")
        
        # Create source
        source_id = str(uuid.uuid4())
        content_hash = compute_hash(extracted_text)
        chunks = chunk_text_func(extracted_text)
        
        # Save file
        import aiofiles
        storage_filename = f"{source_id}.{file_type}"
        storage_path = UPLOAD_DIR / storage_filename
        async with aiofiles.open(storage_path, 'wb') as f:
            await f.write(content)
        
        source_doc = {
            "id": source_id,
            "level": "personal",
            "ownerId": current_user["id"],
            "ownerEmail": current_user["email"],
            "projectId": None,
            "departmentId": None,
            "kind": "file",
            "originalName": file.filename,
            "mimeType": file.content_type,
            "sizeBytes": len(content),
            "storagePath": storage_filename,
            "version": 1,
            "contentHash": content_hash,
            "status": "active",
            "createdAt": now_iso(),
            "createdBy": current_user["id"],
            "createdByEmail": current_user["email"],
            "updatedAt": None
        }
        await db.sources.insert_one(source_doc)
        
        # Save chunks
        for i, chunk_content in enumerate(chunks):
            chunk_doc = {
                "id": str(uuid.uuid4()),
                "sourceId": source_id,
                "projectId": f"__personal_{current_user['id']}__",
                "chunkIndex": i,
                "content": chunk_content,
                "createdAt": now_iso()
            }
            await db.source_chunks.insert_one(chunk_doc)
        
        # Create initial version
        await version_service.versions.insert_one({
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "version": 1,
            "contentHash": content_hash,
            "sizeBytes": len(content),
            "chunkCount": len(chunks),
            "createdBy": current_user["id"],
            "createdByEmail": current_user["email"],
            "createdAt": now_iso(),
            "changeDescription": "Initial upload",
            "previousVersion": None,
            "chunks": chunks
        })
        
        source_doc["chunkCount"] = len(chunks)
        # Remove _id added by insert_one
        source_doc.pop("_id", None)
        return source_doc
    
    @router.get("/api/personal-sources")
    async def list_personal_sources(current_user: dict = Depends(get_current_user)):
        """List user's personal sources"""
        sources = await db.sources.find(
            {"level": "personal", "ownerId": current_user["id"]},
            {"_id": 0}
        ).to_list(100)
        
        # Add chunk counts
        for source in sources:
            count = await db.source_chunks.count_documents({"sourceId": source["id"]})
            source["chunkCount"] = count
        
        return sources
    
    @router.delete("/api/personal-sources/{source_id}")
    async def delete_personal_source(
        source_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Delete personal source"""
        source = await db.sources.find_one({"id": source_id}, {"_id": 0})
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        if source.get("level") != "personal":
            raise HTTPException(status_code=400, detail="Not a personal source")
        
        if source.get("ownerId") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not your source")
        
        # Delete file, chunks, versions
        if source.get("storagePath"):
            file_path = UPLOAD_DIR / source["storagePath"]
            if file_path.exists():
                file_path.unlink()
        
        await db.source_chunks.delete_many({"sourceId": source_id})
        await db.source_versions.delete_many({"sourceId": source_id})
        await db.sources.delete_one({"id": source_id})
        
        return {"message": "Personal source deleted"}
    
    # ==================== PUBLISH (Personal → Project/Department) ====================
    
    @router.post("/api/personal-sources/{source_id}/publish")
    async def publish_personal_source(
        source_id: str,
        data: dict,
        current_user: dict = Depends(get_current_user)
    ):
        """
        Publish personal source to project or department
        Creates a COPY with new ID (not a move)
        """
        source = await db.sources.find_one({"id": source_id}, {"_id": 0})
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        if source.get("level") != "personal":
            raise HTTPException(status_code=400, detail="Not a personal source")
        
        if source.get("ownerId") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not your source")
        
        target_level = data.get("targetLevel")  # "project" or "department"
        target_id = data.get("targetId")
        new_name = data.get("newName", source.get("originalName"))
        
        if target_level not in ["project", "department"]:
            raise HTTPException(status_code=400, detail="Invalid target level")
        
        # Verify access to target
        if target_level == "project":
            project = await db.projects.find_one({"id": target_id}, {"_id": 0})
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            # Check if user has manager access
            # ... (simplified check)
        elif target_level == "department":
            department = await db.departments.find_one({"id": target_id}, {"_id": 0})
            if not department:
                raise HTTPException(status_code=404, detail="Department not found")
            # Check if user is manager
            if current_user["id"] not in department.get("managers", []):
                if not is_admin(current_user["email"]):
                    raise HTTPException(status_code=403, detail="Only department managers can publish here")
        
        # Get original chunks
        original_chunks = await db.source_chunks.find(
            {"sourceId": source_id},
            {"_id": 0}
        ).sort("chunkIndex", 1).to_list(10000)
        
        chunk_contents = [c["content"] for c in original_chunks]
        
        # Create new source (COPY)
        new_source_id = str(uuid.uuid4())
        content_hash = source.get("contentHash", compute_hash("".join(chunk_contents)))
        
        # Determine initial status
        if target_level == "department":
            initial_status = "draft"  # Requires approval
        else:
            initial_status = "active"  # Project sources active immediately
        
        new_source = {
            "id": new_source_id,
            "level": target_level,
            "ownerId": current_user["id"],
            "ownerEmail": current_user["email"],
            "projectId": target_id if target_level == "project" else None,
            "departmentId": target_id if target_level == "department" else None,
            "kind": source.get("kind", "file"),
            "originalName": new_name,
            "mimeType": source.get("mimeType"),
            "sizeBytes": source.get("sizeBytes"),
            "storagePath": None,  # Copy doesn't need file storage
            "version": 1,
            "contentHash": content_hash,
            "status": initial_status,
            "createdAt": now_iso(),
            "createdBy": current_user["id"],
            "createdByEmail": current_user["email"],
            "publishedFrom": source_id,  # Track origin
            "updatedAt": None
        }
        await db.sources.insert_one(new_source)
        
        # Copy chunks
        for i, chunk_content in enumerate(chunk_contents):
            chunk_doc = {
                "id": str(uuid.uuid4()),
                "sourceId": new_source_id,
                "projectId": target_id,
                "chunkIndex": i,
                "content": chunk_content,
                "createdAt": now_iso()
            }
            await db.source_chunks.insert_one(chunk_doc)
        
        # Create version
        await db.source_versions.insert_one({
            "id": str(uuid.uuid4()),
            "sourceId": new_source_id,
            "version": 1,
            "contentHash": content_hash,
            "sizeBytes": source.get("sizeBytes", 0),
            "chunkCount": len(chunk_contents),
            "createdBy": current_user["id"],
            "createdByEmail": current_user["email"],
            "createdAt": now_iso(),
            "changeDescription": f"Published from personal source",
            "previousVersion": None,
            "chunks": chunk_contents
        })
        
        # Audit log
        await audit_service.log(
            entity="source",
            entity_id=new_source_id,
            entity_name=new_name,
            action="publish",
            user_id=current_user["id"],
            user_email=current_user["email"],
            metadata={
                "sourceLevel": target_level,
                "targetId": target_id,
                "originalSourceId": source_id,
                "status": initial_status
            },
            level=target_level
        )
        
        new_source["chunkCount"] = len(chunk_contents)
        # Remove _id added by insert_one
        new_source.pop("_id", None)
        return {
            "message": f"Published to {target_level}",
            "source": new_source,
            "requiresApproval": initial_status == "draft"
        }
    
    # ==================== DEPARTMENT SOURCES ====================
    
    @router.post("/api/departments/{department_id}/sources/upload")
    async def upload_department_source(
        department_id: str,
        file: UploadFile = File(...),
        current_user: dict = Depends(get_current_user)
    ):
        """Upload source to department (creates draft, requires approval)"""
        department = await db.departments.find_one({"id": department_id}, {"_id": 0})
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        
        # Check if user is manager or admin
        is_manager = current_user["id"] in department.get("managers", [])
        if not is_admin(current_user["email"]) and not is_manager:
            raise HTTPException(status_code=403, detail="Only managers can upload department sources")
        
        if file.content_type not in SUPPORTED_MIME_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large")
        
        file_type = SUPPORTED_MIME_TYPES[file.content_type]
        extracted_text = await extract_text_func(content, file_type)
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            raise HTTPException(status_code=400, detail="No text extracted")
        
        source_id = str(uuid.uuid4())
        content_hash = compute_hash(extracted_text)
        chunks = chunk_text_func(extracted_text)
        
        # Save file
        import aiofiles
        storage_filename = f"{source_id}.{file_type}"
        storage_path = UPLOAD_DIR / storage_filename
        async with aiofiles.open(storage_path, 'wb') as f:
            await f.write(content)
        
        source_doc = {
            "id": source_id,
            "level": "department",
            "ownerId": current_user["id"],
            "ownerEmail": current_user["email"],
            "projectId": None,
            "departmentId": department_id,
            "kind": "file",
            "originalName": file.filename,
            "mimeType": file.content_type,
            "sizeBytes": len(content),
            "storagePath": storage_filename,
            "version": 1,
            "contentHash": content_hash,
            "status": "draft",  # Requires approval
            "createdAt": now_iso(),
            "createdBy": current_user["id"],
            "createdByEmail": current_user["email"],
            "updatedAt": None
        }
        await db.sources.insert_one(source_doc)
        
        # Save chunks (but source is draft)
        for i, chunk_content in enumerate(chunks):
            chunk_doc = {
                "id": str(uuid.uuid4()),
                "sourceId": source_id,
                "projectId": department_id,
                "chunkIndex": i,
                "content": chunk_content,
                "createdAt": now_iso()
            }
            await db.source_chunks.insert_one(chunk_doc)
        
        # Create version
        await db.source_versions.insert_one({
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "version": 1,
            "contentHash": content_hash,
            "sizeBytes": len(content),
            "chunkCount": len(chunks),
            "createdBy": current_user["id"],
            "createdByEmail": current_user["email"],
            "createdAt": now_iso(),
            "changeDescription": "Initial upload",
            "previousVersion": None,
            "chunks": chunks
        })
        
        # Audit log
        await audit_service.log(
            entity="source",
            entity_id=source_id,
            entity_name=file.filename,
            action="create",
            user_id=current_user["id"],
            user_email=current_user["email"],
            metadata={"departmentId": department_id, "status": "draft"},
            level="department"
        )
        
        source_doc["chunkCount"] = len(chunks)
        # Remove _id added by insert_one
        source_doc.pop("_id", None)
        return source_doc
    
    @router.get("/api/departments/{department_id}/sources")
    async def list_department_sources(
        department_id: str,
        status: Optional[str] = None,
        current_user: dict = Depends(get_current_user)
    ):
        """List department sources"""
        department = await db.departments.find_one({"id": department_id}, {"_id": 0})
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        
        # Check access
        user_depts = current_user.get("departments", [])
        if department_id not in user_depts and not is_admin(current_user["email"]):
            raise HTTPException(status_code=403, detail="Access denied")
        
        query = {"level": "department", "departmentId": department_id}
        
        # Non-managers only see active sources
        is_manager = current_user["id"] in department.get("managers", [])
        if not is_manager and not is_admin(current_user["email"]):
            query["status"] = "active"
        elif status:
            query["status"] = status
        
        sources = await db.sources.find(query, {"_id": 0}).to_list(100)
        
        for source in sources:
            count = await db.source_chunks.count_documents({"sourceId": source["id"]})
            source["chunkCount"] = count
        
        return sources
    
    # ==================== APPROVAL WORKFLOW ====================
    
    @router.post("/api/sources/{source_id}/approval")
    async def process_approval(
        source_id: str,
        data: dict,
        current_user: dict = Depends(get_current_user)
    ):
        """
        Approve or reject a source (Department/Global)
        Workflow: draft → pending → approved → active
        """
        source = await db.sources.find_one({"id": source_id}, {"_id": 0})
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        level = source.get("level")
        action = data.get("action")  # "approve" or "reject"
        comment = data.get("comment", "")
        
        if action not in ["approve", "reject", "submit", "activate"]:
            raise HTTPException(status_code=400, detail="Invalid action")
        
        # Permission check
        if level == "global":
            if not is_admin(current_user["email"]):
                raise HTTPException(status_code=403, detail="Only admin can approve global sources")
        elif level == "department":
            department = await db.departments.find_one(
                {"id": source.get("departmentId")},
                {"_id": 0}
            )
            if not department:
                raise HTTPException(status_code=404, detail="Department not found")
            is_manager = current_user["id"] in department.get("managers", [])
            if not is_manager and not is_admin(current_user["email"]):
                raise HTTPException(status_code=403, detail="Only managers can approve")
        else:
            raise HTTPException(status_code=400, detail="Approval only for department/global sources")
        
        current_status = source.get("status", "draft")
        
        # State machine
        if action == "submit" and current_status == "draft":
            new_status = "pending"
        elif action == "approve" and current_status in ["draft", "pending"]:
            new_status = "approved"
        elif action == "activate" and current_status == "approved":
            new_status = "active"
        elif action == "reject":
            new_status = "draft"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot {action} from status {current_status}"
            )
        
        updates = {
            "status": new_status,
            "updatedAt": now_iso()
        }
        
        if action == "approve":
            updates["approvedBy"] = current_user["id"]
            updates["approvedAt"] = now_iso()
        elif action == "reject":
            updates["rejectionReason"] = comment
            updates["approvedBy"] = None
            updates["approvedAt"] = None
        
        await db.sources.update_one({"id": source_id}, {"$set": updates})
        
        # Audit log
        await audit_service.log(
            entity="source",
            entity_id=source_id,
            entity_name=source.get("originalName"),
            action=action,
            user_id=current_user["id"],
            user_email=current_user["email"],
            changes={"status": {"old": current_status, "new": new_status}},
            metadata={"comment": comment},
            level=level
        )
        
        return {
            "message": f"Source {action}d",
            "newStatus": new_status
        }
    
    # ==================== VERSION MANAGEMENT ====================
    
    @router.get("/api/sources/{source_id}/versions")
    async def get_source_versions(
        source_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get all versions of a source"""
        source = await db.sources.find_one({"id": source_id}, {"_id": 0})
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        # TODO: Add proper access check based on level
        
        versions = await db.source_versions.find(
            {"sourceId": source_id},
            {"_id": 0, "chunks": 0}  # Exclude content for listing
        ).sort("version", -1).to_list(100)
        
        # Mark current active version
        current_version = source.get("version", 1)
        for v in versions:
            v["isActive"] = v["version"] == current_version
        
        return versions
    
    @router.post("/api/sources/{source_id}/restore")
    async def restore_source_version(
        source_id: str,
        data: dict,
        current_user: dict = Depends(get_current_user)
    ):
        """
        Restore to a previous version
        Creates NEW version (not silent rollback)
        """
        source = await db.sources.find_one({"id": source_id}, {"_id": 0})
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        target_version = data.get("version")
        change_description = data.get("changeDescription", f"Restored from version {target_version}")
        
        if not target_version:
            raise HTTPException(status_code=400, detail="Version required")
        
        # TODO: Add proper permission check
        
        try:
            new_version = await version_service.restore_version(
                source_id=source_id,
                target_version=target_version,
                user_id=current_user["id"],
                user_email=current_user["email"],
                change_description=change_description
            )
            
            # Audit log
            await audit_service.log(
                entity="source",
                entity_id=source_id,
                entity_name=source.get("originalName"),
                action="restore",
                user_id=current_user["id"],
                user_email=current_user["email"],
                changes={"version": {"old": source.get("version"), "new": new_version["version"]}},
                metadata={"restoredFrom": target_version},
                level=source.get("level")
            )
            
            return {
                "message": f"Restored to version {target_version}",
                "newVersion": new_version["version"]
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # ==================== AUDIT LOGS ====================
    
    @router.get("/api/admin/audit-logs")
    async def get_audit_logs(
        entity: Optional[str] = None,
        entity_id: Optional[str] = None,
        action: Optional[str] = None,
        level: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        current_user: dict = Depends(get_current_user)
    ):
        """Get audit logs (admin only for full access, managers for their department)"""
        if not is_admin(current_user["email"]):
            # Non-admins can only see department logs they manage
            user_managed_depts = []
            departments = await db.departments.find(
                {"managers": current_user["id"]},
                {"_id": 0, "id": 1}
            ).to_list(100)
            user_managed_depts = [d["id"] for d in departments]
            
            if not user_managed_depts:
                raise HTTPException(status_code=403, detail="No audit access")
            
            # Filter to only department logs
            level = "department"
            # Would need to add departmentId filter here
        
        logs = await audit_service.get_logs(
            entity=entity,
            entity_id=entity_id,
            action=action,
            level=level,
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        
        return logs
    
    return router
