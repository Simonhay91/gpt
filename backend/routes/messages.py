"""Message routes including RAG pipeline"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging
import re
import httpx
import hashlib
import os

from models.schemas import MessageCreate, MessageResponse, SaveToKnowledgeRequest, MessageEditRequest
from middleware.auth import get_current_user
from db.connection import get_db
from routes.projects import (
    check_project_access, 
    can_edit_chats,
    verify_project_ownership
)
from services.rag import get_relevant_chunks, get_embedding, get_openai_client
from services.cache import (
    build_cache_key_context, 
    find_cached_answer, 
    save_to_cache
)
from services.file_processor import chunk_text, extract_text_from_html

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["messages"])

# Constants
GLOBAL_PROJECT_ID = "__global__"
MAX_AUTO_INGEST_URLS = 3
MAX_CHUNKS_PER_QUERY = 5
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE)

# Web search keywords (multilingual)
WEB_SEARCH_KEYWORDS = [
    "research", "найди в интернете", "ищи", "поищи", "search",
    "գտիր", "փնտրիր", "փնտրել", "որոնիր", "որոնել"
]


async def brave_web_search(query: str) -> Optional[List[dict]]:
    """
    Search the web using Brave Search API
    Returns list of {"title": str, "url": str, "description": str}
    """
    brave_api_key = os.environ.get('BRAVE_API_KEY', '')
    if not brave_api_key:
        logger.warning("BRAVE_API_KEY not set, skipping web search")
        return None
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "X-Subscription-Token": brave_api_key,
                    "Accept": "application/json"
                },
                params={
                    "q": query,
                    "count": 5,
                    "search_lang": "en"
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Brave Search API error: {response.status_code}")
                return None
            
            data = response.json()
            web_results = data.get("web", {}).get("results", [])
            
            if not web_results:
                return None
            
            formatted_results = []
            for result in web_results[:5]:
                formatted_results.append({
                    "title": result.get("title", "Untitled"),
                    "url": result.get("url", ""),
                    "description": result.get("description", "")
                })
            
            logger.info(f"Brave Search returned {len(formatted_results)} results")
            return formatted_results
            
    except Exception as e:
        logger.error(f"Brave Search error: {str(e)}")
        return None


def should_use_web_search(user_message: str, has_relevant_rag: bool) -> bool:
    """
    Determine if web search should be used
    - If RAG has relevant results (score > 0.7) → No web search
    - If user explicitly requests research → Yes web search
    - Otherwise → No web search
    """
    # Check for explicit research keywords
    message_lower = user_message.lower()
    for keyword in WEB_SEARCH_KEYWORDS:
        if keyword in message_lower:
            return True
    
    # If RAG doesn't have relevant results
    if not has_relevant_rag:
        return False  # Let AI use its own knowledge
    
    return False


def extract_urls_from_text(text: str) -> List[str]:
    """Extract unique URLs from text"""
    urls = URL_PATTERN.findall(text)
    cleaned = []
    for url in urls:
        url = url.rstrip('.,;:!?)]}"\'')
        if url and url not in cleaned:
            cleaned.append(url)
    return cleaned[:MAX_AUTO_INGEST_URLS]


async def auto_ingest_url(db, url: str, project_id: str) -> Optional[dict]:
    """Auto-ingest a URL: fetch, extract text, chunk, and store."""
    try:
        existing = await db.sources.find_one({"url": url, "projectId": project_id})
        if existing:
            return existing
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as http_client:
            response = await http_client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
        
        content_type = response.headers.get('content-type', '')
        if 'text/html' not in content_type and 'text/plain' not in content_type:
            return None
        
        html_content = response.text
        extracted_text = extract_text_from_html(html_content)
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            return None
        
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
        
        return source_doc
        
    except Exception as e:
        logger.error(f"Error auto-ingesting URL {url}: {str(e)}")
        return None


async def ensure_gpt_config(db):
    """Ensure GPT config singleton exists"""
    config = await db.gpt_config.find_one({"id": "1"}, {"_id": 0})
    default_prompt = """You are Claude, a helpful AI assistant by Anthropic. Use ONLY the active sources provided in context.

IMPORTANT RULES:
1. If no sources available - ask user to upload/activate files
2. Cite sources as [Source: name]
3. Be concise and accurate
4. Respond in the same language as the user's question
5. If the context seems incomplete, say: "I found limited information on this topic."
6. Never make up information not present in the sources"""
    
    if not config:
        config = {
            "id": "1",
            "model": "claude-sonnet-4-20250514",
            "developerPrompt": default_prompt,
            "updatedAt": datetime.now(timezone.utc).isoformat()
        }
        await db.gpt_config.insert_one(config)
    return config


@router.get("/chats/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(chat_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if chat.get("projectId"):
        await verify_project_ownership(chat["projectId"], current_user["id"])
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    messages = await db.messages.find({"chatId": chat_id}, {"_id": 0}).sort("createdAt", 1).to_list(1000)
    
    result = []
    for m in messages:
        msg_data = {
            **m, 
            "citations": m.get("citations"), 
            "usedSources": m.get("usedSources"),
            "autoIngestedUrls": m.get("autoIngestedUrls"),
            "senderEmail": m.get("senderEmail"),
            "senderName": m.get("senderName")
        }
        result.append(MessageResponse(**msg_data))
    
    return result


@router.post("/chats/{chat_id}/messages", response_model=MessageResponse)
async def send_message(chat_id: str, message_data: MessageCreate, current_user: dict = Depends(get_current_user)):
    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    project_id = chat.get("projectId")
    user_role = None
    
    if project_id:
        try:
            access = await check_project_access(current_user, project_id, required_role="viewer")
            user_role = access["role"]
        except HTTPException:
            raise HTTPException(status_code=403, detail="Not authorized to access this project")
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this chat")
    
    # Auto-ingest URLs
    detected_urls = extract_urls_from_text(message_data.content)
    auto_ingested_sources = []
    
    if detected_urls and project_id and can_edit_chats(user_role):
        for url in detected_urls:
            source = await auto_ingest_url(db, url, project_id)
            if source:
                auto_ingested_sources.append(source)
    
    # Get source IDs with hierarchy
    personal_source_ids = []
    project_source_ids = []
    department_source_ids = []
    global_source_ids = []
    user_department_ids = current_user.get("departments", [])
    source_mode = chat.get("sourceMode", "all")
    
    # Personal sources
    personal_sources = await db.sources.find({
        "level": "personal",
        "ownerId": current_user["id"],
        "status": {"$in": ["active", None]}
    }, {"_id": 0, "id": 1}).to_list(1000)
    personal_source_ids = [s["id"] for s in personal_sources]
    
    # Project sources
    if project_id:
        project_sources = await db.sources.find({
            "projectId": project_id,
            "level": {"$in": ["project", None]},
            "status": {"$in": ["active", None]}
        }, {"_id": 0, "id": 1}).to_list(1000)
        project_source_ids = [s["id"] for s in project_sources]
    
    # Department and global sources only if source_mode is 'all'
    if source_mode == 'all':
        if user_department_ids:
            department_sources = await db.sources.find({
                "departmentId": {"$in": user_department_ids},
                "level": "department",
                "status": "active"
            }, {"_id": 0, "id": 1}).to_list(1000)
            department_source_ids = [s["id"] for s in department_sources]
        
        global_sources = await db.sources.find({
            "$or": [
                {"projectId": GLOBAL_PROJECT_ID},
                {"level": "global", "status": "active"}
            ]
        }, {"_id": 0, "id": 1}).to_list(1000)
        global_source_ids = [s["id"] for s in global_sources]
    
    active_source_ids = personal_source_ids + project_source_ids + department_source_ids + global_source_ids
    user_accessible_source_ids = active_source_ids.copy()
    
    # Save user message
    sender_email = current_user["email"]
    sender_name = sender_email.split("@")[0] if sender_email else "User"
    
    user_msg_id = str(uuid.uuid4())
    user_message = {
        "id": user_msg_id,
        "chatId": chat_id,
        "role": "user",
        "content": message_data.content,
        "citations": None,
        "autoIngestedUrls": [s["id"] for s in auto_ingested_sources] if auto_ingested_sources else None,
        "senderEmail": sender_email,
        "senderName": sender_name,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(user_message)
    
    # Get GPT config
    config = await ensure_gpt_config(db)
    
    # Get chat history
    history = await db.messages.find({"chatId": chat_id}, {"_id": 0}).sort("createdAt", 1).to_list(1000)
    history = history[-20:]

    # Get relevant chunks and build context
    citations = []
    document_context = ""
    active_source_names = []
    source_types = {}
    
    if active_source_ids:
        sources = await db.sources.find({"id": {"$in": active_source_ids}}, {"_id": 0}).to_list(1000)
        
        source_names = {}
        for s in sources:
            name = s.get("originalName") or s.get("url") or "Unknown"
            source_names[s["id"]] = name
            active_source_names.append(name)
            level = s.get("level")
            if level == "department":
                source_types[s["id"]] = "department"
            elif s.get("projectId") == GLOBAL_PROJECT_ID or level == "global":
                source_types[s["id"]] = "global"
            else:
                source_types[s["id"]] = "project"
        
        relevant_chunks = await get_relevant_chunks(db, active_source_ids, project_id, message_data.content, user_department_ids)
        
        if relevant_chunks:
            def chunk_priority(chunk):
                source_type = source_types.get(chunk["sourceId"], "global")
                type_priority = {"project": 0, "department": 1, "global": 2}.get(source_type, 2)
                return (type_priority, -chunk.get("score", 0))
            
            relevant_chunks.sort(key=chunk_priority)
            
            context_parts = []
            for chunk in relevant_chunks:
                source_name = source_names.get(chunk["sourceId"], "Unknown")
                source_type = source_types.get(chunk["sourceId"], "global")
                chunk_marker = f"[Source: {source_name} ({source_type.upper()}), Chunk {chunk['chunkIndex']+1}]"
                context_parts.append(f"{chunk_marker}\n{chunk['content']}")
                
                citations.append({
                    "sourceName": source_name,
                    "sourceId": chunk["sourceId"],
                    "sourceType": source_type,
                    "chunkId": chunk.get("id", ""),
                    "chunkIndex": chunk["chunkIndex"],
                    "textFragment": chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk["content"],
                    "score": chunk.get("score", 0)
                })
            
            document_context = "\n\n---\n\n".join(context_parts)
    
    # Check if RAG found relevant results (score > 0.7)
    has_relevant_rag = any(c.get("score", 0) > 0.7 for c in citations)
    
    # Brave Web Search integration
    web_search_results = None
    web_sources = None
    
    if should_use_web_search(message_data.content, has_relevant_rag):
        logger.info("Triggering Brave Web Search...")
        web_search_results = await brave_web_search(message_data.content)
        
        if web_search_results:
            web_sources = [{"title": r["title"], "url": r["url"]} for r in web_search_results]
            
            # Add web results to context
            web_context_parts = []
            for idx, result in enumerate(web_search_results, 1):
                web_context_parts.append(
                    f"[Web Result {idx}: {result['title']}]\nURL: {result['url']}\n{result['description']}"
                )
            
            web_context = "\n\n---\n\n".join(web_context_parts)
            
            # Append to document_context if exists, or create new
            if document_context:
                document_context = f"{document_context}\n\n===== WEB SEARCH RESULTS =====\n\n{web_context}"
            else:
                document_context = f"===== WEB SEARCH RESULTS =====\n\n{web_context}"
    
    # Get user's custom prompt
    user_prompt_doc = await db.user_prompts.find_one({"userId": current_user["id"]}, {"_id": 0})
    user_custom_prompt = user_prompt_doc.get("customPrompt") if user_prompt_doc else None
    
    # Build cache context hash
    user_model = current_user.get("gptModel")
    model_to_use = user_model if user_model else config["model"]
    
    cache_context_hash = build_cache_key_context(
        project_id=project_id,
        model=model_to_use,
        developer_prompt=config["developerPrompt"],
        user_prompt=user_custom_prompt,
        source_ids=active_source_ids
    )
    
    # Semantic cache check
    cache_hit = None
    question_embedding = None
    cache_info = None
    openai_client = get_openai_client()
    
    if active_source_ids and openai_client:
        question_embedding = await get_embedding(message_data.content)
        if question_embedding:
            cache_hit = await find_cached_answer(
                db,
                message_data.content,
                project_id,
                question_embedding,
                cache_context_hash,
                user_accessible_source_ids
            )
            
            if cache_hit:
                logger.info(f"Cache HIT! Similarity: {cache_hit['similarity']:.3f}")
                cache_info = {
                    "similarity": cache_hit['similarity'],
                    "hitCount": cache_hit['hitCount'],
                    "cacheId": cache_hit['cacheId']
                }
    
    # Call Claude API
    try:
        import anthropic
        import os
        
        CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        
        from_cache = False
        
        if cache_hit:
            response_text = cache_hit["answer"]
            response_text += f"\n\n---\n_📦 Ответ из кэша (схожесть: {cache_hit['similarity']:.0%})_"
            tokens_used = 0
            from_cache = True
        else:
            # system_parts = [config["developerPrompt"]]
            
            # if user_custom_prompt:s
            #     system_parts.append(f"USER INSTRUCTIONS:\n{user_custom_prompt}")
            
            system_parts = [config["developerPrompt"]]

            # Inject project memory
            if project_id:
                project_doc = await db.projects.find_one({"id": project_id}, {"_id": 0})
                if project_doc and project_doc.get("project_memory"):
                    system_parts.append(f"BACKGROUND CONTEXT:\n{project_doc['project_memory']}\n\nUse this context naturally when relevant. Do not mention or reference this context explicitly — just use it to inform your answers.")

            if user_custom_prompt:
                system_parts.append(f"USER INSTRUCTIONS:\n{user_custom_prompt}")
                        
            if document_context:
                active_sources_list = ", ".join(active_source_names) if active_source_names else "None"
                chunks_count = len(citations) if citations else 0
                context_message = f"SOURCES: {active_sources_list}\nCHUNKS: {chunks_count} (top {MAX_CHUNKS_PER_QUERY} most relevant)\n\n{document_context[:10000]}"
                system_parts.append(context_message)
            
            system_prompt = "\n\n".join(system_parts)
            
            messages = []
            for msg in history[:-1]:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": message_data.content})
            
            claude_response = claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=messages
            )
            
            response_text = claude_response.content[0].text
            tokens_used = claude_response.usage.input_tokens + claude_response.usage.output_tokens
            
            if tokens_used > 0:
                await db.token_usage.update_one(
                    {"userId": current_user["id"]},
                    {
                        "$inc": {"totalTokens": tokens_used, "messageCount": 1},
                        "$set": {"lastUsedAt": datetime.now(timezone.utc).isoformat()}
                    },
                    upsert=True
                )
        
    except Exception as e:
        logger.error(f"Claude API error: {str(e)}")
        response_text = f"Error: {str(e)[:100]}"
        citations = []
        from_cache = False
    
    # Deduplicate citations
    unique_citations = {}
    used_sources = []
    for c in citations:
        key = c["sourceId"]
        if key not in unique_citations:
            unique_citations[key] = {
                "sourceName": c["sourceName"],
                "sourceId": c["sourceId"],
                "sourceType": c.get("sourceType", "unknown"),
                "chunks": []
            }
            used_sources.append({
                "sourceId": c["sourceId"],
                "sourceName": c["sourceName"],
                "sourceType": c.get("sourceType", "unknown")
            })
        unique_citations[key]["chunks"].append({
            "index": c["chunkIndex"] + 1,
            "chunkId": c.get("chunkId", ""),
            "textFragment": c.get("textFragment", "")
        })
    
    final_citations = list(unique_citations.values()) if unique_citations else None
    final_used_sources = used_sources if used_sources else None
    
    # Save to semantic cache
    if question_embedding and not from_cache and not response_text.startswith("Error:"):
        await save_to_cache(
            db,
            question=message_data.content,
            answer=response_text,
            project_id=project_id,
            embedding=question_embedding,
            user_id=current_user["id"],
            cache_context_hash=cache_context_hash,
            source_ids=active_source_ids,
            sources_used=final_used_sources
        )
    
    # Save assistant message
    assistant_msg_id = str(uuid.uuid4())
    assistant_message = {
        "id": assistant_msg_id,
        "chatId": chat_id,
        "role": "assistant",
        "content": response_text,
        "citations": final_citations,
        "usedSources": final_used_sources,
        "autoIngestedUrls": [s["id"] for s in auto_ingested_sources] if auto_ingested_sources else None,
        "senderEmail": None,
        "senderName": "GPT",
        "fromCache": from_cache,
        "cacheInfo": cache_info,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(assistant_message)
    
    # Track source usage
    if final_used_sources:
        for source_info in final_used_sources:
            await db.source_usage.update_one(
                {"sourceId": source_info["sourceId"]},
                {
                    "$inc": {"usageCount": 1},
                    "$set": {
                        "lastUsedAt": datetime.now(timezone.utc).isoformat(),
                        "sourceName": source_info["sourceName"]
                    },
                    "$push": {
                        "usageHistory": {
                            "$each": [{
                                "userId": current_user["id"],
                                "userEmail": current_user["email"],
                                "chatId": chat_id,
                                "messageId": assistant_msg_id,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }],
                            "$slice": -100
                        }
                    }
                },
                upsert=True
            )
    
    return MessageResponse(**assistant_message)


# ==================== SAVE TO KNOWLEDGE ====================

@router.post("/save-to-knowledge")
async def save_to_knowledge(
    request: SaveToKnowledgeRequest,
    current_user: dict = Depends(get_current_user)
):
    """Save AI message content as a Personal Source"""
    db = get_db()
    openai_client = get_openai_client()
    
    try:
        content_preview = request.content[:50].replace('\n', ' ').strip()
        if len(request.content) > 50:
            content_preview += "..."
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        source_name = f"{content_preview} ({timestamp})"
        
        source_id = str(uuid.uuid4())
        
        source_doc = {
            "id": source_id,
            "level": "personal",
            "ownerId": current_user["id"],
            "ownerEmail": current_user["email"],
            "projectId": None,
            "departmentId": None,
            "kind": "knowledge",
            "originalName": source_name,
            "mimeType": "text/plain",
            "sizeBytes": len(request.content.encode('utf-8')),
            "storagePath": None,
            "extractedText": request.content,
            "contentHash": hashlib.sha256(request.content.encode('utf-8')).hexdigest(),
            "status": "active",
            "currentVersion": 1,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat()
        }
        
        await db.sources.insert_one(source_doc)
        
        chunks = chunk_text(request.content, chunk_size=1000)
        
        for i, chunk_text_content in enumerate(chunks):
            try:
                if openai_client:
                    embedding_response = openai_client.embeddings.create(
                        model="text-embedding-3-small",
                        input=chunk_text_content
                    )
                    embedding = embedding_response.data[0].embedding
                else:
                    embedding = None
                
                chunk_doc = {
                    "id": str(uuid.uuid4()),
                    "sourceId": source_id,
                    "sourceName": source_name,
                    "chunkIndex": i,
                    "text": chunk_text_content,
                    "embedding": embedding,
                    "createdAt": datetime.now(timezone.utc).isoformat()
                }
                await db.source_chunks.insert_one(chunk_doc)
            except Exception as e:
                logger.error(f"Error creating embedding for chunk {i}: {str(e)}")
        
        await db.audit_logs.insert_one({
            "id": str(uuid.uuid4()),
            "userId": current_user["id"],
            "userEmail": current_user["email"],
            "action": "save_to_knowledge",
            "resourceType": "source",
            "resourceId": source_id,
            "details": {"sourceName": source_name, "contentLength": len(request.content)},
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return {
            "success": True,
            "sourceId": source_id,
            "sourceName": source_name,
            "message": "Saved to Knowledge ✅"
        }
        
    except Exception as e:
        logger.error(f"Error saving to knowledge: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")


@router.post("/chats/{chat_id}/save-context")
async def save_chat_context(chat_id: str, data: dict, current_user: dict = Depends(get_current_user)):
    """
    Save chat context to user's AI Profile
    - Sends dialog to AI for summarization
    - Saves summary to user's ai_profile.custom_instruction with timestamp
    """
    db = get_db()
    
    # Verify chat access
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Check access
    if chat.get("ownerId") != current_user["id"]:
        if chat.get("projectId"):
            project = await db.projects.find_one({"id": chat["projectId"]}, {"_id": 0})
            if not project or project.get("ownerId") != current_user["id"]:
                raise HTTPException(status_code=403, detail="Access denied")
    
    dialog_text = data.get("dialogText", "")
    if not dialog_text or len(dialog_text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Dialog text too short")
    
    try:
        # Send to Claude for summarization
        import anthropic
        import os
        
        CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
        if not CLAUDE_API_KEY:
            raise HTTPException(status_code=500, detail="AI service not configured")
        
        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        
        system_prompt = """Прочитай этот диалог и напиши краткое резюме: какие темы обсуждались, к каким выводам пришли, что важно помнить для продолжения в следующем чате. Максимум 150 слов. Только резюме, без предисловий."""
        
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=system_prompt,
            messages=[
                {"role": "user", "content": dialog_text}
            ]
        )
        
        summary = response.content[0].text.strip()
        
        # Word count check (approximate)
        word_count = len(summary.split())
        if word_count > 200:  # Allow some buffer
            # Truncate to approximately 150 words
            words = summary.split()[:150]
            summary = ' '.join(words) + '...'
        
        # Save to user's AI Profile (ai_profile.custom_instruction)
        now = datetime.now(timezone.utc)
        context_prefix = f"[Контекст чата: {now.strftime('%Y-%m-%d %H:%M')}]\n{summary}"
        
        # Get current user data
        user_data = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get existing custom instruction
        ai_profile = user_data.get("ai_profile", {})
        existing_instruction = ai_profile.get("custom_instruction", "")
        
        # Append new context
        if existing_instruction:
            updated_instruction = f"{existing_instruction}\n\n{context_prefix}".strip()
        else:
            updated_instruction = context_prefix
        
        # Update user's ai_profile.custom_instruction
        await db.users.update_one(
            {"id": current_user["id"]},
            {
                "$set": {
                    "ai_profile.custom_instruction": updated_instruction,
                    "ai_profile.updatedAt": now.isoformat()
                }
            }
        )
        
        return {
            "success": True,
            "summary": summary,
            "message": "Контекст сохранен в AI Profile"
        }
        
    except Exception as e:
        logger.error(f"Error saving context: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save context: {str(e)}")

@router.post("/chats/{chat_id}/extract-memory-points")
async def extract_memory_points(chat_id: str, data: dict, current_user: dict = Depends(get_current_user)):
    """Extract key points from conversation for project memory"""
    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    dialog_text = data.get("dialogText", "")
    if not dialog_text or len(dialog_text.strip()) < 20:
        return {"points": []}

    try:
        import anthropic, os
        claude_client = anthropic.Anthropic(api_key=os.environ.get('CLAUDE_API_KEY', ''))
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system="You are extracting PROJECT KNOWLEDGE from a conversation. Extract only permanent, reusable facts about the project, domain, business rules, decisions, or technical details discussed. DO NOT describe what was asked or answered. DO NOT write meta-descriptions like 'user asked about X'. Instead write the actual fact, e.g. 'Stock Order deposit is 20%'. Return ONLY a JSON array of strings (max 10 items). Each item max 100 chars. Write in the SAME LANGUAGE as the conversation content. No preamble, no markdown, pure JSON array.",
            messages=[{"role": "user", "content": dialog_text}]
        )
        import json
        text = response.content[0].text.strip()
        points = json.loads(text)
        return {"points": points if isinstance(points, list) else []}
    except Exception as e:
        logger.error(f"Extract memory points error: {str(e)}")
        return {"points": []}