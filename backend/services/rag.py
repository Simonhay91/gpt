"""RAG (Retrieval Augmented Generation) pipeline service"""
import re
import logging
from typing import List, Optional
from openai import OpenAI
import os

logger = logging.getLogger(__name__)

# OpenAI API Key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
EMBEDDING_MODEL = "text-embedding-3-small"

# RAG settings
MAX_CONTEXT_CHARS = 10000
MAX_CHUNKS_PER_QUERY = 5
GLOBAL_PROJECT_ID = "__global__"

# Initialize OpenAI client for embeddings
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


async def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding for text using OpenAI"""
    if not openai_client:
        return None
    try:
        response = openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text[:8000]
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return None


def score_chunk_relevance(chunk_content: str, query: str) -> float:
    """Score chunk relevance using simple keyword overlap"""
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
    department_ids: List[str] = None
) -> List[dict]:
    """Get most relevant chunks from active sources using keyword ranking"""
    if not source_ids:
        return []
    
    project_id_filter = [GLOBAL_PROJECT_ID]
    if project_id:
        project_id_filter.append(project_id)
    if department_ids:
        project_id_filter.extend(department_ids)
    
    logger.info(f"get_relevant_chunks: source_ids count={len(source_ids)}, project_id_filter={project_id_filter}")
    
    all_chunks = await db.source_chunks.find({
        "sourceId": {"$in": source_ids},
        "projectId": {"$in": project_id_filter}
    }, {"_id": 0}).to_list(50000)
    
    if not all_chunks:
        return []
    
    scored_chunks = []
    for chunk in all_chunks:
        score = score_chunk_relevance(chunk["content"], query)
        scored_chunks.append({**chunk, "score": score})
    
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    
    selected_chunks = []
    total_chars = 0
    
    for chunk in scored_chunks[:MAX_CHUNKS_PER_QUERY]:
        if total_chars + len(chunk["content"]) > MAX_CONTEXT_CHARS:
            break
        selected_chunks.append(chunk)
        total_chars += len(chunk["content"])
    
    logger.info(f"RAG optimization: Selected {len(selected_chunks)}/{len(scored_chunks)} chunks, {total_chars} chars")
    
    return selected_chunks


def get_openai_client():
    """Get the OpenAI client instance"""
    return openai_client
