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



async def search_product_catalog(query: str, db, limit: int = 5) -> list:
    try:
        results = await db.product_catalog.find({
            "is_active": True,
            "$or": [
                {"title_en": {"$regex": query, "$options": "i"}},
                {"article_number": {"$regex": query, "$options": "i"}},
                {"vendor": {"$regex": query, "$options": "i"}},
                {"product_model": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
                {"aliases": {"$elemMatch": {"$regex": query, "$options": "i"}}}
            ]
        }, {"_id": 0}).limit(limit).to_list(limit)
        return results
    except Exception:
        return []


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


async def fetch_page_texts(results: list, top_n: int = 2, per_page: int = 500, total_limit: int = 1000) -> list:
    """Fetch actual page content for top-N Brave results. Never raises — always returns list."""
    enriched = []
    total_chars = 0

    try:
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            for result in results[:top_n]:
                if total_chars >= total_limit:
                    break
                url = result.get("url", "")
                if not url:
                    enriched.append(result)
                    continue
                try:
                    resp = await client.get(
                        url,
                        headers={"User-Agent": "Mozilla/5.0 (compatible; PlanetBot/1.0)"},
                    )
                    if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                        soup = BeautifulSoup(resp.text, "html.parser")
                        # Remove noise tags
                        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                            tag.decompose()
                        text = soup.get_text(separator=" ", strip=True)
                        text = " ".join(text.split())[:per_page]
                        total_chars += len(text)
                        enriched.append({**result, "page_text": text})
                    else:
                        enriched.append(result)
                except Exception:
                    enriched.append(result)

        # Fill remaining results without page content
        for result in results[len(enriched):]:
            enriched.append(result)

    except Exception as e:
        logger.warning(f"Page fetch enrichment failed: {e}")
        return results  # fallback: return originals untouched

    return enriched


def should_use_web_search(user_message: str, has_relevant_rag: bool) -> bool:
    """
    Determine if web search should be used
    - If RAG has relevant results (score > 0.7) → No web search
    - If user explicitly requests research → Yes web search
    - Otherwise → No web search
    """
    content = user_message.strip()
    message_lower = content.lower()

    # Skip web search for short messages (greetings, etc.)
    words = content.split()
    if len(words) <= 4:
        return False

    # Skip web search for greetings and social phrases
    STOP_WORDS = ["barev", "բարև", "привет", "hello", "hi", "salam",
                  "vonc es", "inch ka", "mersi", "shnorhakalutyun"]
    if any(word in message_lower for word in STOP_WORDS):
        return False

    # Check for explicit research keywords
    for keyword in WEB_SEARCH_KEYWORDS:
        if keyword in message_lower:
            return True
    
    # If RAG doesn't have relevant results
    if not has_relevant_rag:
        return False  # Let AI use its own knowledge
    
    return False


async def fetch_url_content(url: str) -> Optional[str]:
    """
    Fetch and extract text content from URL
    Supports HTML pages and PDF files
    Returns extracted text (max 8000 chars) or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
            
            if response.status_code != 200:
                logger.warning(f"URL fetch failed: {url} - status {response.status_code}")
                return None
            
            content_type = response.headers.get('content-type', '').lower()
            
            # Handle PDF files
            if url.endswith('.pdf') or 'application/pdf' in content_type:
                try:
                    from pypdf import PdfReader
                    from io import BytesIO
                    
                    pdf_file = BytesIO(response.content)
                    pdf_reader = PdfReader(pdf_file)
                    
                    text_parts = []
                    for page in pdf_reader.pages[:10]:  # Max 10 pages
                        text_parts.append(page.extract_text())
                    
                    extracted_text = '\n\n'.join(text_parts)
                    logger.info(f"Extracted {len(extracted_text)} chars from PDF: {url}")
                    
                except Exception as pdf_error:
                    logger.error(f"PDF extraction failed for {url}: {str(pdf_error)}")
                    return None
            
            # Handle HTML pages
            else:
                try:
                    from bs4 import BeautifulSoup
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Remove script and style elements
                    for script in soup(["script", "style", "nav", "footer", "header"]):
                        script.decompose()
                    
                    # Extract text from relevant tags
                    text_parts = []
                    
                    # Get title
                    if soup.title:
                        text_parts.append(f"Title: {soup.title.string}")
                    
                    # Get headings and paragraphs
                    for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'article', 'main']):
                        text = tag.get_text(strip=True)
                        if text and len(text) > 20:  # Skip very short texts
                            text_parts.append(text)
                    
                    extracted_text = '\n\n'.join(text_parts)
                    logger.info(f"Extracted {len(extracted_text)} chars from HTML: {url}")
                    
                except Exception as html_error:
                    logger.error(f"HTML extraction failed for {url}: {str(html_error)}")
                    return None
            
            # Truncate to 8000 chars
            if extracted_text:
                return extracted_text[:8000]
            
            return None
            
    except Exception as e:
        logger.error(f"URL fetch error for {url}: {str(e)}")
        return None


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
    """Ensure GPT config singleton exists. Never overwrites existing config."""
    existing = await db.gpt_config.find_one({}, {"_id": 0})
    if existing:
        return existing  # не трогать существующий конфиг

    # Создаём дефолт только если конфига нет вовсе
    default_config = {
        "id": "1",
        "model": "claude-sonnet-4-20250514",
        "developerPrompt": """You are Claude, a helpful AI assistant by Anthropic. Use ONLY the active sources provided in context.

IMPORTANT RULES:
1. If no sources available - ask user to upload/activate files
2. Cite sources as [Source: name]
3. Be concise and accurate
4. Respond in the same language as the user's question
5. If the context seems incomplete, say: "I found limited information on this topic."
6. Never make up information not present in the sources

CLARIFYING QUESTIONS:
Если вопрос пользователя неполный, неоднозначный или требует важных уточнений для качественного ответа — задай 1 уточняющий вопрос с 2-4 вариантами ответа. Используй строго следующий формат в конце сообщения:
<clarifying>
{"question": "текст вопроса", "options": ["вариант 1", "вариант 2", "вариант 3"]}
</clarifying>
Не задавай более одного вопроса за раз. Если информации достаточно — отвечай сразу без уточнений.

EXCEL / CSV SOURCES:
When the user has Excel or CSV files as active sources, behave like an analyst, not a robot:
- First understand what the user needs — ask clarifying questions if the request is vague
- Analyze and discuss the data naturally before doing anything
- Only generate/modify an Excel file when the user explicitly asks (e.g. "generate", "create new excel", "download", "փոխիր excel", "ստեղծիր", "сгенерируй")
- When generating, confirm what you are about to do before doing it
- Never auto-generate Excel just because the user mentioned columns or data""",
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    await db.gpt_config.insert_one(default_config)
    return default_config


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
    
    messages = await db.messages.find(
        {"chatId": chat_id},
        {"_id": 0, "id": 1, "chatId": 1, "role": 1, "content": 1, "createdAt": 1,
         "citations": 1, "usedSources": 1, "autoIngestedUrls": 1, "senderEmail": 1,
         "senderName": 1, "fromCache": 1, "cacheInfo": 1, "web_sources": 1,
         "clarifying_question": 1, "clarifying_options": 1, "fetchedUrls": 1,
         "excel_file_id": 1, "excel_preview": 1}
    ).sort("createdAt", 1).to_list(500)
    
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


@router.post("/chats/{chat_id}/messages")
async def send_message(
    chat_id: str,
    message_data: MessageCreate,
    regen: bool = False,
    current_user: dict = Depends(get_current_user)
):
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
    if not regen:
        await db.messages.insert_one(user_message)
    
    # Get GPT config
    config = await ensure_gpt_config(db)
    
    # Get chat history — fetch only last 20 directly from DB
    history = await db.messages.find(
        {"chatId": chat_id},
        {"_id": 0, "role": 1, "content": 1, "createdAt": 1}
    ).sort("createdAt", -1).to_list(20)
    history = list(reversed(history))

    import time
    t0 = time.time()

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
    
    # Fetch content from URLs mentioned in user message
    fetched_url_count = 0
    fetched_urls_list = []
    if detected_urls:
        url_context_parts = []
        for url in detected_urls:
            fetched_content = await fetch_url_content(url)
            if fetched_content:
                url_context_parts.append(f"[URL Content: {url}]\n{fetched_content}")
                fetched_url_count += 1
                fetched_urls_list.append(url)
                logger.info(f"Fetched URL content: {url} ({len(fetched_content)} chars)")
        
        if url_context_parts:
            url_fetched_context = "\n\n---\n\n".join(url_context_parts)
            if document_context:
                document_context = f"===== FETCHED URL CONTENT =====\n\n{url_fetched_context}\n\n===== DOCUMENT CONTEXT =====\n\n{document_context}"
            else:
                document_context = f"===== FETCHED URL CONTENT =====\n\n{url_fetched_context}"

    # Check if RAG found relevant results (score > 0.7)
    # Filter out low-score chunks (score <= 0.6) — remove noise from context
    citations = [c for c in citations if c.get("score", 0) > 0.6]
    has_relevant_rag = any(c.get("score", 0) > 0.7 for c in citations)
    has_rag_context = bool(citations)
    print(f"[TIMING] RAG+URL fetch: {time.time()-t0:.2f}s"); t0 = time.time()

    # Product Catalog search
    catalog_results = await search_product_catalog(message_data.content, db, limit=5)
    catalog_context = ""
    if catalog_results:
        catalog_parts = []
        for p in catalog_results:
            relations_count = len(p.get("relations", []))
            part = (
                f"[Product: {p.get('title_en')}]\n"
                f"Article: {p.get('article_number')} | Vendor: {p.get('vendor')} | Model: {p.get('product_model', '')}\n"
                f"Category: {p.get('root_category', '')} > {p.get('lvl1_subcategory', '')}\n"
                f"Price: {p.get('price', 'N/A')} | Related products: {relations_count}\n"
                f"Description: {str(p.get('description', ''))[:300]}"
            )
            catalog_parts.append(part)
        catalog_context = "===== PRODUCT CATALOG =====\n\n" + "\n\n---\n\n".join(catalog_parts)

    if catalog_context:
        if document_context:
            document_context = f"{catalog_context}\n\n{document_context}"
        else:
            document_context = catalog_context
    print(f"[TIMING] Catalog: {time.time()-t0:.2f}s"); t0 = time.time()

    # Brave Web Search integration
    web_search_results = None
    web_sources = None

    # Fetch project memory early to decide if web search fallback is needed
    _project_memory_text = ""
    if project_id:
        _proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "project_memory": 1})
        _project_memory_text = (_proj or {}).get("project_memory", "") or ""
    has_project_memory = bool(_project_memory_text and len(_project_memory_text.strip()) > 50)

    brave_api_key_exists = bool(os.environ.get('BRAVE_API_KEY', ''))
    use_web_search = should_use_web_search(message_data.content, has_relevant_rag)
    # Fallback: auto-trigger when no RAG, no URL, Brave key set, not trivial, no project memory
    _words = message_data.content.strip().split()
    _msg_lower = message_data.content.lower()
    _STOP_WORDS = ["barev", "բարև", "привет", "hello", "hi", "salam",
                   "vonc es", "inch ka", "mersi", "shnorhakalutyun"]
    _is_trivial = len(_words) <= 4 or any(w in _msg_lower for w in _STOP_WORDS)
    if not use_web_search and not has_relevant_rag and not fetched_url_count and brave_api_key_exists and not _is_trivial and not has_project_memory:
        use_web_search = True
        logger.info("Fallback web search: no RAG results found, auto-triggering search")

    if use_web_search:
        logger.info("Triggering Brave Web Search...")
        web_search_results = await brave_web_search(message_data.content)
        
        if web_search_results:
            web_sources = [{"title": r["title"], "url": r["url"]} for r in web_search_results]

            # Enrich top-3 results with actual page content
            enriched_results = await fetch_page_texts(web_search_results, top_n=2, per_page=500, total_limit=1000)

            # Build context: prefer page_text, fallback to description
            web_context_parts = []
            for idx, result in enumerate(enriched_results[:5], 1):
                page_text = result.get("page_text", "").strip()
                snippet = page_text if page_text else result.get("description", "")
                web_context_parts.append(
                    f"[Web Result {idx}: {result['title']}]\nURL: {result['url']}\n{snippet}"
                )
            
            web_context = "\n\n---\n\n".join(web_context_parts)
            
            # Append to document_context if exists, or create new
            if document_context:
                document_context = f"{document_context}\n\n===== WEB SEARCH RESULTS =====\n\n{web_context}"
            else:
                document_context = f"===== WEB SEARCH RESULTS =====\n\n{web_context}"

    # Determine context type for targeted system prompt instruction
    print(f"[TIMING] Web search+fetch: {time.time()-t0:.2f}s"); t0 = time.time()
    # Priority: relevant RAG > web results > any RAG (low score) > URL > none
    if has_relevant_rag:
        context_type = "rag"
    elif web_search_results:
        context_type = "web"
    elif has_rag_context:
        context_type = "rag"
    elif fetched_url_count > 0:
        context_type = "url"
    else:
        context_type = "none"

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
    response_text = ""
    citations = []
    from_cache = False
    cache_info = None
    clarifying_question = None
    clarifying_options = None
    
    try:
        import anthropic

        CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        
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
                # Allow more context if URL content was fetched
                max_context_chars = 18000 if fetched_url_count > 0 else 10000
                context_message = f"[SYS_META sources={active_sources_list} chunks={chunks_count}]\n\n{document_context[:max_context_chars]}"
                system_parts.append(context_message)
            
            # Add URL content instruction if URLs were fetched
            if fetched_url_count > 0:
                url_instruction = "IMPORTANT: Content fetched from URL(s) provided by the user is included above under 'FETCHED URL CONTENT'. Use this content to answer questions about those URLs. When referencing URL content, mention the source URL."
                system_parts.append(url_instruction)

            # Add web search instruction if web results are used
            if web_search_results:
                web_instruction = (
                    "WEB SEARCH ACCESS: You have been provided with real-time web search results above "
                    "(under '===== WEB SEARCH RESULTS ====='). This means you DO have access to current "
                    "internet information for this query — it has been fetched for you automatically.\n\n"
                    "RULES FOR USING WEB RESULTS:\n"
                    "1. NEVER say 'I cannot access the internet', 'I don't have internet access', "
                    "or 'I cannot browse websites' — you HAVE been given the search results already.\n"
                    "2. Use the provided web content as your primary source for this query.\n"
                    "3. If page content (full article text) is available in a result, use it — "
                    "it is more reliable than the short snippet.\n"
                    "4. Synthesize information from multiple results when relevant.\n"
                    "5. ALWAYS cite your web sources at the end of your response in this format:\n\n"
                    "Источники:\n"
                    "- [Title](URL)\n"
                    "- [Title](URL)"
                )
                system_parts.append(web_instruction)

            # Add product catalog instruction if catalog results found
            if catalog_results:
                catalog_instruction = (
                    "PRODUCT CATALOG: You have been provided with matching products from the company's "
                    "product catalog above (under '===== PRODUCT CATALOG =====').\n"
                    "- Use this data to answer product-related questions accurately\n"
                    "- Mention article numbers and vendors when relevant\n"
                    "- If the user asks about related/compatible products, note that relation data is available\n"
                    "- Do not invent prices or specs not present in the catalog data"
                )
                system_parts.append(catalog_instruction)

            # Context-type specific final instruction (highest priority — overrides general rules)
            if context_type == "rag":
                system_parts.append(
                    "FINAL INSTRUCTION: Answer based on the provided document sources above. "
                    "Cite relevant sources using [Source: name] format."
                )
            elif context_type == "none":
                system_parts.append(
                    "FINAL INSTRUCTION: No document sources or web results are available for this query. "
                    "Answer from your own knowledge directly and helpfully. "
                    "Do NOT say 'there are no sources', 'I cannot find information in the sources', "
                    "'no information available in the uploaded files', or any similar phrase about missing sources. "
                    "Simply answer the question as a knowledgeable assistant would."
                )

            system_prompt = "\n\n".join(system_parts)

            # Prevent Claude from generating fake Excel/file structures
            system_prompt += "\n\nIMPORTANT: Do NOT generate XML tags, <excel_file>, <file>, or any fake file structures in your response. If the user asks to create, modify or download an Excel/CSV file — the system handles file generation automatically. Just confirm what you will do in plain text."

            # Strict Excel generation rule
            system_prompt += "\n\nSTRICT RULE: Never generate, create, or offer to download Excel/CSV files on your own initiative. Only work with Excel files that the user has explicitly uploaded as sources. Never use any Excel generation tools unless the user explicitly asks: \"создай Excel\", \"сделай таблицу для скачивания\", \"generate excel\", \"create spreadsheet\"."
            
            messages = []
            for msg in history[:-1]:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": message_data.content})

            print(f"[TIMING] System prompt length: {len(system_prompt)} chars")
            print(f"[TIMING] Messages count: {len(messages)}")
            print(f"[TIMING] Total context chars: {sum(len(str(m)) for m in messages)}")

            claude_response = claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=messages
            )
            
            response_text = claude_response.content[0].text
            tokens_used = claude_response.usage.input_tokens + claude_response.usage.output_tokens
            print(f"[TIMING] Claude API: {time.time()-t0:.2f}s"); t0 = time.time()
            
            # Parse clarifying questions
            if "<clarifying>" in response_text and "</clarifying>" in response_text:
                try:
                    import re
                    import json
                    
                    # Extract JSON from <clarifying> tags
                    match = re.search(r'<clarifying>(.*?)</clarifying>', response_text, re.DOTALL)
                    if match:
                        clarifying_json = match.group(1).strip()
                        clarifying_data = json.loads(clarifying_json)
                        
                        clarifying_question = clarifying_data.get("question")
                        clarifying_options = clarifying_data.get("options", [])
                        
                        # Remove clarifying block from content
                        response_text = response_text[:match.start()].strip()
                        
                        logger.info(f"Clarifying question extracted: {clarifying_question}")
                except Exception as e:
                    logger.error(f"Failed to parse clarifying question: {str(e)}")
            
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

    # ==================== EXCEL GENERATION DETECTION ====================
    excel_file_id = None
    excel_preview = None

    if project_id and active_source_ids and not response_text.startswith("Error:"):
        try:
            import json as _json
            import math as _math
            import pandas as _pd
            from pathlib import Path as _Path
            import uuid as _uuid

            _UPLOAD_DIR = _Path(__file__).parent.parent / "uploads"

            EXCEL_MIME_TYPES = [
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
                "text/csv",
                "application/csv",
            ]

            excel_source = await db.sources.find_one(
                {"id": {"$in": active_source_ids}, "mimeType": {"$in": EXCEL_MIME_TYPES}},
                {"_id": 0}
            )

            if excel_source:
                # Always process when Excel source is active — skip only pure questions
                SKIP_KWORDS = [
                    "что такое", "what is", "объясни", "explain", "как работает", "расскажи",
                    # Armenian
                    "ի՞նչ", "ինչ", "կարո", "բացատր", "ցույց տուր", "նկարագր",
                    # English questions
                    "what", "who", "where", "when", "why", "how", "tell me", "describe", "show me",
                    # Russian questions
                    "что", "кто", "где", "когда", "почему", "как", "покажи",
                    # Greetings
                    "barev", "բарев", "привет",
                    # About/topic words
                    "masin", "մасин", "about",
                    # Armenian question words
                    "inch", "ինч", "vortegh", "երб",
                ]
                msg_lower = message_data.content.lower()
                # Question marks (Latin and Armenian) always skip Excel processing
                has_question_mark = "?" in message_data.content or "՞" in message_data.content
                is_excel_request = not has_question_mark and not any(kw in msg_lower for kw in SKIP_KWORDS)
                # Override: only trigger Excel generation via explicit phrases
                excel_trigger_phrases = [
                    "generate excel", "create excel", "make excel",
                    "ստեղծիр excel", "փоխир excel", "գеներацрու",
                    "сгенерируй excel", "создай excel", "сделай excel",
                    "download excel", "скачать excel", "беռнел excel"
                ]
                is_excel_request = any(phrase in message_data.content.lower() for phrase in excel_trigger_phrases)

                # Two-step flow: check if AI already asked clarifying questions
                if is_excel_request:
                    recent_messages = await db.messages.find(
                        {"chatId": chat_id},
                        {"_id": 0, "role": 1, "content": 1}
                    ).sort("createdAt", -1).limit(3).to_list(3)

                    has_clarification = any(
                        "excel" in str(m.get("content", "")).lower() and
                        m.get("role") == "assistant"
                        for m in recent_messages
                    )

                    if not has_clarification:
                        # First request — ask clarifying questions instead of generating
                        is_excel_request = False
                        # Override Claude's generic response with targeted clarification
                        response_text = (
                            "Նախ ուզում եմ հասկանալ ճիշт, ինč es apes ստանال:\n\n"
                            "1. **Ի՞նч твیалнер** петк е линен — ColumBs/rows, ес կонкрет ТАМАЛики\n"
                            "2. **Քани՞ тох** моТаваРАС к линен файлумО\n"
                            "3. **Ի՞нch нпАТАКИ** нахАТЕСТВА є файлый — экспорт, ЧЕМ, ОТчет\n\n"
                            "АнМЕТС ПЕТАКАНОТЮН ТАЛА — ГЕНЕРИРУЙ Excel."
                        )
                        # Make a proper Claude call for clarification
                        try:
                            clarif_client = claude_client
                            clarif_messages = [{"role": "user", "content": message_data.content}]
                            clarif_system = (
                                "EXCEL CLARIFICATION REQUIRED: The user wants to generate an Excel file. "
                                "DO NOT generate Excel yet. Ask these 3 clarifying questions in the user's language "
                                "(Armenian, Russian, or English based on their message):\n"
                                "1. What data/columns should be included\n"
                                "2. Approximately how many rows\n"
                                "3. What is the purpose of the file\n"
                                "Keep it short and friendly. Do not generate any file or code."
                            )
                            clarif_resp = clarif_client.messages.create(
                                model="claude-sonnet-4-20250514",
                                max_tokens=512,
                                system=clarif_system,
                                messages=clarif_messages
                            )
                            response_text = clarif_resp.content[0].text
                        except Exception as clarif_err:
                            logger.warning(f"Clarification call failed: {clarif_err}")

                if is_excel_request and excel_source.get("storagePath"):
                    file_path = _UPLOAD_DIR / excel_source["storagePath"]
                    if file_path.exists():
                        ext = excel_source["storagePath"].rsplit(".", 1)[-1].lower()
                        df = _pd.read_excel(file_path) if ext in ("xlsx", "xls") else _pd.read_csv(file_path)

                        structure = (
                            f"File: {excel_source.get('originalName', 'file')}\n"
                            f"Rows: {len(df)}, Columns: {len(df.columns)}\n"
                            f"Columns: {list(df.columns)}\n"
                            f"Data (max 200 rows):\n{df.head(200).to_string(index=False)}"
                        )

                        excel_system = (
                            "You are a data transformation assistant. "
                            "The spreadsheet data is provided directly below — do not fetch anything externally.\n"
                            "Apply the user's instruction to the data and return ONLY a valid JSON object:\n"
                            '{"column_mapping": {"old": "new"}, "new_data": [[col1, col2, ...], [val1, val2, ...], ...], "message": "what was done"}\n'
                            "- new_data: first array = column names, remaining arrays = ALL data rows with transformations applied\n"
                            "- column_mapping: rename map (can be empty {})\n"
                            "- message: brief explanation in same language as instruction\n"
                            "- NEVER say you cannot do something — work only with the provided data\n"
                            "Return ONLY JSON, no markdown, no extra text."
                        )

                        excel_client = anthropic.Anthropic(api_key=os.environ.get("CLAUDE_API_KEY", ""))
                        excel_response = excel_client.messages.create(
                            model="claude-sonnet-4-20250514",
                            max_tokens=4096,
                            system=excel_system,
                            messages=[{"role": "user", "content": f"Instruction: {message_data.content}\n\n{structure}"}]
                        )

                        raw = excel_response.content[0].text.strip()
                        if raw.startswith("```"):
                            raw = raw.split("```")[1]
                            if raw.startswith("json"):
                                raw = raw[4:]

                        result_data = _json.loads(raw.strip())
                        new_data = result_data.get("new_data", [])

                        if new_data and len(new_data) > 1:
                            cols = new_data[0]
                            result_df = _pd.DataFrame(new_data[1:], columns=cols)
                        else:
                            col_map = result_data.get("column_mapping", {})
                            result_df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

                        file_id = str(_uuid.uuid4())
                        result_path = f"/tmp/excel_result_{file_id}.xlsx"
                        result_df.to_excel(result_path, index=False)

                        def _sanitize(v):
                            if v is None:
                                return None
                            if isinstance(v, float) and (_math.isnan(v) or _math.isinf(v)):
                                return None
                            return v

                        excel_file_id = file_id
                        excel_preview = {
                            "columns": [str(c) for c in result_df.columns],
                            "rows": [[_sanitize(v) for v in row] for row in result_df.head(5).values.tolist()],
                            "total_rows": len(result_df),
                            "message": result_data.get("message", ""),
                        }

                        response_text = result_data.get("message", response_text)
        except Exception as excel_err:
            logger.error(f"Excel generation error: {excel_err}")

    # ==================== END EXCEL DETECTION ====================

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
        "web_sources": web_sources,
        "clarifying_question": clarifying_question,
        "clarifying_options": clarifying_options,
        "fetchedUrls": fetched_urls_list if fetched_urls_list else None,
        "excel_file_id": excel_file_id,
        "excel_preview": excel_preview,
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
    
    return {
        "user_message": {k: v for k, v in user_message.items() if k != "_id"},
        "assistant_message": {k: v for k, v in assistant_message.items() if k != "_id"}
    }


# ==================== EDIT MESSAGE ====================

@router.put("/chats/{chat_id}/messages/{message_id}/edit", response_model=MessageResponse)
async def edit_message(
    chat_id: str,
    message_id: str,
    edit_data: MessageEditRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Edit a user message and delete all subsequent messages
    Only the message author can edit their message
    """
    db = get_db()
    
    logger.info(f"Edit request: chat_id={chat_id}, message_id={message_id}, user={current_user['email']}")
    
    # Get the message
    message = await db.messages.find_one({"id": message_id, "chatId": chat_id}, {"_id": 0})
    
    if not message:
        # Debug: check if message exists without chatId filter
        message_check = await db.messages.find_one({"id": message_id}, {"_id": 0})
        if message_check:
            logger.error(f"Message exists but chatId mismatch: expected {chat_id}, got {message_check.get('chatId')}")
        else:
            logger.error(f"Message {message_id} not found in database")
        raise HTTPException(status_code=404, detail="Message not found")
    
    logger.info(f"Found message: role={message.get('role')}, senderEmail={message.get('senderEmail')}")
    
    # Check if user is the author
    # User messages might not have senderEmail, so also check if role is 'user' and it's their chat
    is_author = message.get("senderEmail") == current_user["email"]
    is_user_message_in_own_chat = (
        message.get("role") == "user" and 
        not message.get("senderEmail")  # Old messages might not have senderEmail
    )
    
    if not (is_author or is_user_message_in_own_chat):
        # Verify chat ownership for user messages without senderEmail
        if is_user_message_in_own_chat:
            chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
            if chat and chat.get("ownerId") != current_user["id"]:
                raise HTTPException(status_code=403, detail="Only message author can edit")
        else:
            raise HTTPException(status_code=403, detail="Only message author can edit")
    
    # Check if message is from user role
    if message.get("role") != "user":
        raise HTTPException(status_code=400, detail="Only user messages can be edited")
    
    # Update message content
    message_created_at = message.get("createdAt")
    
    logger.info(f"Editing message with createdAt: {message_created_at}")
    
    await db.messages.update_one(
        {"id": message_id},
        {"$set": {"content": edit_data.content, "updatedAt": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Delete ONLY subsequent messages (messages AFTER this one by createdAt)
    # Messages BEFORE the edited message remain untouched
    deleted_result = await db.messages.delete_many({
        "chatId": chat_id,
        "createdAt": {"$gt": message_created_at}  # Only messages with createdAt > edited message's createdAt
    })
    
    logger.info(f"Deleted {deleted_result.deleted_count} messages after edited message (createdAt > {message_created_at})")
    
    # Get updated message
    updated_message = await db.messages.find_one({"id": message_id}, {"_id": 0})
    
    return MessageResponse(**updated_message)


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
        import anthropic
        claude_client = anthropic.Anthropic(api_key=os.environ.get('CLAUDE_API_KEY', ''))
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system="You are extracting PROJECT KNOWLEDGE from a conversation. Extract only permanent, reusable facts about the project, domain, business rules, decisions, or technical details discussed. DO NOT describe what was asked or answered. DO NOT write meta-descriptions like 'user asked about X'. Instead write the actual fact, e.g. 'Stock Order deposit is 20%'. Return ONLY a JSON array of strings (max 10 items). Each item max 100 chars. Write in the SAME LANGUAGE as the conversation content. No preamble, no markdown, pure JSON array.",
            messages=[{"role": "user", "content": dialog_text[:8000]}]
        )
        import json as _json
        import re as _re
        text = response.content[0].text.strip()
        # Strip markdown code blocks
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        # Find JSON array anywhere in the text
        if not text.startswith("["):
            match = _re.search(r'\[.*\]', text, _re.DOTALL)
            text = match.group(0) if match else "[]"
        if not text:
            return {"points": []}
        points = _json.loads(text.strip())
        return {"points": points if isinstance(points, list) else []}
    except Exception as e:
        logger.error(f"Extract memory points error: {str(e)}")
        return {"points": []}
