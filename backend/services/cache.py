"""Semantic cache service for reducing token usage"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import hashlib
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Semantic cache settings
CACHE_SIMILARITY_THRESHOLD = 0.92
CACHE_TTL_DAYS = 30


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    a = np.array(vec1)
    b = np.array(vec2)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def hash_string(s: str) -> str:
    """Create short hash of string for cache key"""
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def build_cache_key_context(
    project_id: Optional[str],
    model: str,
    developer_prompt: str,
    user_prompt: Optional[str],
    source_ids: List[str]
) -> str:
    """Build deterministic cache context hash for ZERO DATA LEAKAGE"""
    components = [
        f"project:{project_id or 'none'}",
        f"model:{model}",
        f"dev_prompt:{hash_string(developer_prompt)}",
        f"user_prompt:{hash_string(user_prompt) if user_prompt else 'none'}",
        f"sources:{hash_string(','.join(sorted(source_ids)))}"
    ]
    return hash_string('|'.join(components))


async def find_cached_answer(
    db,
    question: str, 
    project_id: Optional[str],
    question_embedding: List[float],
    cache_context_hash: str,
    user_accessible_source_ids: List[str]
) -> Optional[dict]:
    """
    Find similar cached question with ZERO DATA LEAKAGE protection.
    """
    query = {
        "projectId": project_id if project_id else None,
        "cacheContextHash": cache_context_hash
    }
    
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS)).isoformat()
    query["createdAt"] = {"$gte": cutoff_date}
    
    cache_entries = await db.semantic_cache.find(query, {"_id": 0}).to_list(500)
    
    if not cache_entries:
        return None
    
    best_match = None
    best_similarity = 0
    
    for entry in cache_entries:
        if not entry.get("embedding"):
            continue
        
        cached_source_ids = entry.get("sourceIds", [])
        if cached_source_ids:
            if not all(sid in user_accessible_source_ids for sid in cached_source_ids):
                logger.info(f"Cache SKIP: User lacks access to some sources in cached entry {entry['id']}")
                continue
        
        similarity = cosine_similarity(question_embedding, entry["embedding"])
        
        if similarity > best_similarity and similarity >= CACHE_SIMILARITY_THRESHOLD:
            best_similarity = similarity
            best_match = entry
    
    if best_match:
        await db.semantic_cache.update_one(
            {"id": best_match["id"]},
            {
                "$inc": {"hitCount": 1},
                "$set": {"lastHitAt": datetime.now(timezone.utc).isoformat()}
            }
        )
        return {
            "answer": best_match["answer"],
            "originalQuestion": best_match["question"],
            "similarity": best_similarity,
            "hitCount": best_match.get("hitCount", 0) + 1,
            "cacheId": best_match["id"],
            "sourceIds": best_match.get("sourceIds", [])
        }
    
    return None


async def save_to_cache(
    db,
    question: str,
    answer: str,
    project_id: Optional[str],
    embedding: List[float],
    user_id: str,
    cache_context_hash: str,
    source_ids: List[str],
    sources_used: Optional[List[dict]] = None
):
    """Save question-answer pair to semantic cache with full context"""
    import uuid
    
    cache_entry = {
        "id": str(uuid.uuid4()),
        "question": question,
        "answer": answer,
        "embedding": embedding,
        "projectId": project_id,
        "cacheContextHash": cache_context_hash,
        "sourceIds": source_ids,
        "sourcesUsed": sources_used,
        "createdBy": user_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "hitCount": 0,
        "lastHitAt": None
    }
    await db.semantic_cache.insert_one(cache_entry)
    logger.info(f"Cached answer for question: {question[:50]}... (context: {cache_context_hash})")
