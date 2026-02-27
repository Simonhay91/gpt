"""
Enterprise Knowledge Services
Handles versioning, audit logging, and hierarchical retrieval
"""
import hashlib
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of content"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def generate_id() -> str:
    """Generate unique ID"""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Current timestamp in ISO format"""
    return datetime.now(timezone.utc).isoformat()


class AuditService:
    """Service for audit logging"""
    
    def __init__(self, db):
        self.db = db
        self.collection = db.audit_logs
    
    async def log(
        self,
        entity: str,
        entity_id: str,
        action: str,
        user_id: str,
        user_email: str,
        changes: dict = None,
        metadata: dict = None,
        level: str = None,
        entity_name: str = None,
        ip_address: str = None
    ):
        """Create audit log entry"""
        entry = {
            "id": generate_id(),
            "entity": entity,
            "entityId": entity_id,
            "entityName": entity_name,
            "action": action,
            "level": level,
            "userId": user_id,
            "userEmail": user_email,
            "changes": changes or {},
            "metadata": metadata or {},
            "timestamp": now_iso(),
            "ipAddress": ip_address
        }
        await self.collection.insert_one(entry)
        logger.info(f"Audit: {action} on {entity}/{entity_id} by {user_email}")
        return entry
    
    async def get_logs(
        self,
        entity: str = None,
        entity_id: str = None,
        action: str = None,
        level: str = None,
        user_id: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[dict]:
        """Query audit logs with filters"""
        query = {}
        
        if entity:
            query["entity"] = entity
        if entity_id:
            query["entityId"] = entity_id
        if action:
            query["action"] = action
        if level:
            query["level"] = level
        if user_id:
            query["userId"] = user_id
        if start_date:
            query["timestamp"] = {"$gte": start_date}
        if end_date:
            if "timestamp" in query:
                query["timestamp"]["$lte"] = end_date
            else:
                query["timestamp"] = {"$lte": end_date}
        
        cursor = self.collection.find(query, {"_id": 0})
        cursor = cursor.sort("timestamp", -1).skip(offset).limit(limit)
        return await cursor.to_list(limit)


class VersionService:
    """Service for source versioning"""
    
    def __init__(self, db):
        self.db = db
        self.versions = db.source_versions
        self.sources = db.sources
        self.chunks = db.source_chunks
    
    async def create_version(
        self,
        source_id: str,
        content: str,
        chunks: List[str],
        user_id: str,
        user_email: str,
        change_description: str = None
    ) -> dict:
        """Create new version of a source"""
        # Get current version number
        source = await self.sources.find_one({"id": source_id}, {"_id": 0})
        if not source:
            raise ValueError(f"Source {source_id} not found")
        
        current_version = source.get("version", 1)
        new_version = current_version + 1
        
        # Compute content hash
        content_hash = compute_content_hash(content)
        
        # Store version metadata
        version_doc = {
            "id": generate_id(),
            "sourceId": source_id,
            "version": new_version,
            "contentHash": content_hash,
            "sizeBytes": len(content.encode('utf-8')),
            "chunkCount": len(chunks),
            "createdBy": user_id,
            "createdByEmail": user_email,
            "createdAt": now_iso(),
            "changeDescription": change_description,
            "previousVersion": current_version,
            # Store chunk content for this version
            "chunks": chunks
        }
        await self.versions.insert_one(version_doc)
        
        # Update source with new version
        await self.sources.update_one(
            {"id": source_id},
            {
                "$set": {
                    "version": new_version,
                    "contentHash": content_hash,
                    "updatedAt": now_iso()
                }
            }
        )
        
        logger.info(f"Created version {new_version} for source {source_id}")
        return version_doc
    
    async def get_versions(self, source_id: str) -> List[dict]:
        """Get all versions of a source"""
        cursor = self.versions.find(
            {"sourceId": source_id},
            {"_id": 0, "chunks": 0}  # Exclude chunk content for listing
        ).sort("version", -1)
        return await cursor.to_list(100)
    
    async def get_version(self, source_id: str, version: int) -> Optional[dict]:
        """Get specific version of a source"""
        return await self.versions.find_one(
            {"sourceId": source_id, "version": version},
            {"_id": 0}
        )
    
    async def restore_version(
        self,
        source_id: str,
        target_version: int,
        user_id: str,
        user_email: str,
        change_description: str = None
    ) -> dict:
        """Restore to a previous version (creates NEW version, not silent rollback)"""
        # Get the target version
        target = await self.get_version(source_id, target_version)
        if not target:
            raise ValueError(f"Version {target_version} not found for source {source_id}")
        
        # Create new version from target's content
        description = change_description or f"Restored from version {target_version}"
        
        new_version = await self.create_version(
            source_id=source_id,
            content="",  # We use chunks directly
            chunks=target.get("chunks", []),
            user_id=user_id,
            user_email=user_email,
            change_description=description
        )
        
        # Update source chunks with restored content
        await self.chunks.delete_many({"sourceId": source_id})
        
        source = await self.sources.find_one({"id": source_id}, {"_id": 0})
        project_id = source.get("projectId", source.get("departmentId", "__global__"))
        
        for i, chunk_content in enumerate(target.get("chunks", [])):
            chunk_doc = {
                "id": generate_id(),
                "sourceId": source_id,
                "projectId": project_id,
                "chunkIndex": i,
                "content": chunk_content,
                "createdAt": now_iso()
            }
            await self.chunks.insert_one(chunk_doc)
        
        logger.info(f"Restored source {source_id} to version {target_version}")
        return new_version


class HierarchicalRetrieval:
    """
    Hierarchical knowledge retrieval
    Order: Project → Department → Global
    Takes multiple levels if coverage is weak
    Override only on explicit conflicts
    """
    
    # Minimum chunks needed from a level to consider it "covered"
    MIN_COVERAGE_THRESHOLD = 3
    # Score threshold for considering chunks relevant
    RELEVANCE_THRESHOLD = 0.2
    
    def __init__(self, db):
        self.db = db
        self.sources = db.sources
        self.chunks = db.source_chunks
        self.departments = db.departments
    
    async def retrieve(
        self,
        query: str,
        user_id: str,
        project_id: str = None,
        user_department_ids: List[str] = None,
        max_chunks: int = 10,
        max_context_chars: int = 15000
    ) -> dict:
        """
        Hierarchical retrieval with coverage-based multi-level selection
        
        Returns chunks from multiple levels if single level coverage is weak
        """
        from .enterprise import SourceLevel, RetrievalSource
        
        user_department_ids = user_department_ids or []
        
        # Results storage
        all_chunks = []
        level_coverage = {level.value: 0 for level in SourceLevel}
        conflict_warnings = []
        
        # Step 1: Get Project level chunks (highest priority)
        if project_id:
            project_chunks = await self._get_level_chunks(
                query, SourceLevel.PROJECT, project_id=project_id
            )
            all_chunks.extend(project_chunks)
            level_coverage[SourceLevel.PROJECT.value] = len(project_chunks)
        
        # Step 2: Get Department level chunks
        for dept_id in user_department_ids:
            dept_chunks = await self._get_level_chunks(
                query, SourceLevel.DEPARTMENT, department_id=dept_id
            )
            # Check for conflicts with project level
            if project_id and level_coverage[SourceLevel.PROJECT.value] > 0:
                conflicts = self._detect_conflicts(all_chunks, dept_chunks, query)
                if conflicts:
                    # Project overrides department on conflict
                    conflict_warnings.extend(conflicts)
                    dept_chunks = [c for c in dept_chunks if c not in conflicts]
            
            all_chunks.extend(dept_chunks)
            level_coverage[SourceLevel.DEPARTMENT.value] += len(dept_chunks)
        
        # Step 3: Get Global level chunks
        global_chunks = await self._get_level_chunks(query, SourceLevel.GLOBAL)
        
        # Check for conflicts with higher levels
        if level_coverage[SourceLevel.PROJECT.value] > 0 or level_coverage[SourceLevel.DEPARTMENT.value] > 0:
            conflicts = self._detect_conflicts(all_chunks, global_chunks, query)
            if conflicts:
                conflict_warnings.extend(conflicts)
                global_chunks = [c for c in global_chunks if c not in conflicts]
        
        all_chunks.extend(global_chunks)
        level_coverage[SourceLevel.GLOBAL.value] = len(global_chunks)
        
        # Step 4: Sort by score and apply limits
        all_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # Select chunks respecting character limit
        selected_chunks = []
        total_chars = 0
        
        for chunk in all_chunks:
            if len(selected_chunks) >= max_chunks:
                break
            chunk_len = len(chunk.get("content", ""))
            if total_chars + chunk_len > max_context_chars:
                continue
            selected_chunks.append(chunk)
            total_chars += chunk_len
        
        return {
            "query": query,
            "totalChunks": len(selected_chunks),
            "sources": selected_chunks,
            "levelCoverage": level_coverage,
            "conflictWarnings": conflict_warnings
        }
    
    async def _get_level_chunks(
        self,
        query: str,
        level: 'SourceLevel',
        project_id: str = None,
        department_id: str = None
    ) -> List[dict]:
        """Get relevant chunks from a specific level"""
        # Build query for sources at this level
        source_query = {"level": level.value, "status": "active"}
        
        if level.value == "project" and project_id:
            source_query["projectId"] = project_id
        elif level.value == "department" and department_id:
            source_query["departmentId"] = department_id
        elif level.value == "global":
            source_query["projectId"] = "__global__"
        
        # Get sources
        sources = await self.sources.find(source_query, {"_id": 0}).to_list(100)
        source_ids = [s["id"] for s in sources]
        source_map = {s["id"]: s for s in sources}
        
        if not source_ids:
            return []
        
        # Get chunks
        chunks = await self.chunks.find(
            {"sourceId": {"$in": source_ids}},
            {"_id": 0}
        ).to_list(10000)
        
        # Score chunks by relevance
        scored_chunks = []
        for chunk in chunks:
            score = self._score_relevance(chunk.get("content", ""), query)
            if score >= self.RELEVANCE_THRESHOLD:
                source = source_map.get(chunk["sourceId"], {})
                scored_chunks.append({
                    "sourceId": chunk["sourceId"],
                    "sourceName": source.get("originalName", "Unknown"),
                    "level": level.value,
                    "departmentId": source.get("departmentId"),
                    "projectId": source.get("projectId"),
                    "chunkId": chunk["id"],
                    "chunkIndex": chunk.get("chunkIndex", 0),
                    "content": chunk["content"],
                    "score": score
                })
        
        # Sort by score
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        return scored_chunks[:20]  # Limit per level
    
    def _score_relevance(self, content: str, query: str) -> float:
        """Simple keyword-based relevance scoring"""
        import re
        query_words = set(re.findall(r'\w+', query.lower()))
        content_words = set(re.findall(r'\w+', content.lower()))
        
        if not query_words:
            return 0.0
        
        overlap = len(query_words & content_words)
        return overlap / len(query_words)
    
    def _detect_conflicts(
        self,
        existing_chunks: List[dict],
        new_chunks: List[dict],
        query: str
    ) -> List[str]:
        """
        Detect potential conflicts between chunks from different levels
        Returns warnings about conflicting information
        """
        # Simple conflict detection: if both levels mention same key terms
        # but have different contexts, warn about potential conflict
        warnings = []
        
        # This is a simplified implementation
        # In production, you'd want semantic similarity comparison
        existing_content = " ".join(c.get("content", "")[:200] for c in existing_chunks)
        
        for chunk in new_chunks:
            new_content = chunk.get("content", "")[:200]
            # Check if they discuss same topic but might conflict
            # (simplified: just check for significant content overlap)
            if self._has_potential_conflict(existing_content, new_content):
                warnings.append(
                    f"Potential conflict: {chunk.get('sourceName')} ({chunk.get('level')}) "
                    f"may contain information that differs from higher priority sources"
                )
        
        return warnings[:3]  # Limit warnings
    
    def _has_potential_conflict(self, content1: str, content2: str) -> bool:
        """Check if two content pieces might conflict"""
        import re
        words1 = set(re.findall(r'\w+', content1.lower()))
        words2 = set(re.findall(r'\w+', content2.lower()))
        
        # If significant overlap in words but not identical, might conflict
        overlap = len(words1 & words2)
        union = len(words1 | words2)
        
        if union == 0:
            return False
        
        jaccard = overlap / union
        # Conflict if moderate overlap (same topic) but not high (not identical)
        return 0.3 < jaccard < 0.8
