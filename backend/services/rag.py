"""RAG (Retrieval Augmented Generation) pipeline service"""
import re
import logging
from typing import List, Optional
import numpy as np
import os

logger = logging.getLogger(__name__)

# Voyage AI — lazy init to avoid crash when key is missing at startup
import voyageai
VOYAGE_API_KEY = os.environ.get('VOYAGE_API_KEY', '')
_voyage_client = None

def _get_voyage_client():
    global _voyage_client
    if _voyage_client is None and VOYAGE_API_KEY and VOYAGE_API_KEY != 'dummy':
        try:
            _voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)
        except Exception:
            pass
    return _voyage_client

# RAG settings
MAX_CONTEXT_CHARS = 20000
MAX_CHUNKS_PER_QUERY = 8  # increased from 5 for broader context coverage
GLOBAL_PROJECT_ID = "__global__"


async def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding for text using Voyage AI"""
    client = _get_voyage_client()
    if not client:
        return None
    try:
        result = client.embed([text[:8000]], model="voyage-3")
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

    MIN_SCORE_THRESHOLD = 0.30  # lowered from 0.45 — generic queries (summarize/analyze) score lower
    relevant = [c for c in scored_chunks if c["score"] >= MIN_SCORE_THRESHOLD]

    # If no chunks pass threshold but sources exist, include top chunks anyway
    # (handles "summarize this file" type queries that score low semantically)
    if not relevant and scored_chunks:
        relevant = scored_chunks[:MAX_CHUNKS_PER_QUERY]
        logger.info(f"RAG: no chunks above threshold, using top {len(relevant)} by score (best: {scored_chunks[0]['score']:.3f})")

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


# ==================== SUMMARY INTENT DETECTION ====================

# Phrases that indicate user wants a high-level overview, not a specific question.
# Embedding similarity is weak for these queries — semantic search picks random
# chunks, so we instead serve the FIRST N chunks of the document (intro/TOC).
_SUMMARY_PATTERNS = [
    # English
    r"\b(summari[sz]e|summary|analy[sz]e|overview|tldr|key\s+points)\b",
    r"\bwhat(?:'s|\s+is)\s+(?:in|about|this)\s+(?:the\s+)?(?:file|document|pdf)\b",
    r"\b(?:tell|explain)\s+me\s+about\s+(?:the\s+)?(?:file|document|pdf)\b",
    # Russian
    r"\b(саммари|резюме|кратко\s+о|расскажи\s+о|расскажи\s+про|что\s+в\s+(?:этом\s+)?файле|"
    r"проанализируй|анализ|обзор|пересказ|краткое\s+содержание)\b",
    # Armenian (transliterated)
    r"\b(amphop|amfop|verluc|verlucutyun|hamarot|inch\s+ka\s+ays)\b",
]

_SUMMARY_RE = re.compile("|".join(_SUMMARY_PATTERNS), re.IGNORECASE)


def is_summary_query(query: str) -> bool:
    """True when the query is a generic summary/overview request."""
    if not query:
        return False
    return bool(_SUMMARY_RE.search(query))


async def get_document_overview_chunks(
    db,
    source_ids: List[str],
    chunks_per_source: int = 6,
) -> List[dict]:
    """
    Return the FIRST N chunks (by chunkIndex) of each active source.
    Used for generic summary queries where embedding similarity is unreliable.
    """
    if not source_ids:
        return []

    selected: List[dict] = []
    total_chars = 0

    for sid in source_ids:
        chunks = await db.source_chunks.find(
            {"sourceId": sid},
            {"_id": 0, "sourceId": 1, "content": 1, "text": 1,
             "chunkIndex": 1, "sourceName": 1, "sourceType": 1}
        ).sort("chunkIndex", 1).to_list(chunks_per_source)

        for chunk in chunks:
            content = chunk.get("content") or chunk.get("text", "")
            if not content:
                continue
            if total_chars + len(content) > MAX_CONTEXT_CHARS:
                break
            # Use a synthetic high score so downstream "relevant" checks see this
            # context as substantive, equivalent to an above-threshold semantic match.
            selected.append({**chunk, "content": content, "score": 0.80})
            total_chars += len(content)

        if total_chars >= MAX_CONTEXT_CHARS:
            break

    logger.info(
        f"RAG (overview): selected {len(selected)} first-chunks from "
        f"{len(source_ids)} sources, {total_chars} chars"
    )
    return selected