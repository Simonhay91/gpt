"""RAG (Retrieval Augmented Generation) pipeline service"""
import re
import logging
from typing import List, Optional
import numpy as np
import os

logger = logging.getLogger(__name__)

# Voyage AI
import voyageai
VOYAGE_API_KEY = os.environ.get('VOYAGE_API_KEY', '')
voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)

# RAG settings
MAX_CONTEXT_CHARS = 20000
MAX_CHUNKS_PER_QUERY = 8
GLOBAL_PROJECT_ID = "__global__"


async def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding for text using Voyage AI"""
    try:
        result = voyage_client.embed([text[:8000]], model="voyage-3")
        return result.embeddings[0]
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return None


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    a = np.array(vec1)
    b = np.array(vec2)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def score_chunk_relevance(chunk_content: str, query: str) -> float:
    """Score chunk relevance using simple keyword overlap (fallback)"""
    query_words = set(re.findall(r'\w+', query.lower()))
    chunk_words = set(re.findall(r'\w+', chunk_content.lower()))
    if not query_words:
        return 0.0
    overlap = len(query_words & chunk_words)
    return overlap / len(query_words)


async def get_relevant_chunks(
    db,
    source_ids: List[str],
    project_id: str,
    query: str,
    department_ids: List[str] = None,
    mentioned_source_ids: List[str] = None
) -> List[dict]:
    """Get most relevant chunks using cosine similarity"""
    if not source_ids:
        return []

    # Verify that sources actually exist and are active
    existing_sources = await db.sources.find(
        {"id": {"$in": source_ids}},
        {"_id": 0, "id": 1}
    ).to_list(len(source_ids))
    
    existing_source_ids = [s["id"] for s in existing_sources]
    
    if not existing_source_ids:
        logger.warning(f"No existing sources found for provided IDs: {source_ids}")
        return []
    
    # Log if some sources were not found (they were deleted)
    missing_sources = set(source_ids) - set(existing_source_ids)
    if missing_sources:
        logger.info(f"Filtered out {len(missing_sources)} deleted sources: {missing_sources}")

    query_embedding = await get_embedding(query)

    # Get chunks ONLY from existing sources — project only needed fields
    all_chunks = await db.source_chunks.find(
        {"sourceId": {"$in": existing_source_ids}},
        {"_id": 0, "sourceId": 1, "content": 1, "text": 1, "embedding": 1,
         "chunkIndex": 1, "sourceName": 1, "sourceType": 1}
    ).to_list(5000)

    if not all_chunks:
        return []

    scored_chunks = []
    for chunk in all_chunks:
        content = chunk.get("content") or chunk.get("text", "")
        if not content:
            continue

        if query_embedding:
            chunk_embedding = chunk.get("embedding")
            if chunk_embedding:
                score = cosine_similarity(query_embedding, chunk_embedding)
            else:
                score = score_chunk_relevance(content, query) * 0.5
        else:
            score = score_chunk_relevance(content, query)

        # Boost score for chunks from sources the user explicitly mentioned
        if mentioned_source_ids and chunk.get("sourceId") in mentioned_source_ids:
            score = min(1.0, score * 1.5)

        scored_chunks.append({**chunk, "content": content, "score": score})

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)

    selected = []
    total_chars = 0

    MIN_SCORE_THRESHOLD = 0.3
    relevant = [c for c in scored_chunks if c["score"] >= MIN_SCORE_THRESHOLD]
    for chunk in relevant[:MAX_CHUNKS_PER_QUERY]:

        if total_chars + len(chunk["content"]) > MAX_CONTEXT_CHARS:
            break
        selected.append(chunk)
        total_chars += len(chunk["content"])

    top_score = selected[0]["score"] if selected else 0
    logger.info(f"RAG: selected {len(selected)} chunks from {len(existing_source_ids)} sources, {total_chars} chars, top score: {top_score:.3f}")

    return selected


def get_openai_client():
    """Returns None - OpenAI replaced by Voyage AI"""
    return None