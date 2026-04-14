"""Message routes — RAG pipeline, web search, Excel generation"""
import os
import re
import uuid
import json
import hashlib
import logging
from typing import List, Optional
from datetime import datetime, timezone

import anthropic
from fastapi import APIRouter, HTTPException, Depends

from models.schemas import MessageCreate, MessageResponse, SaveToKnowledgeRequest, MessageEditRequest
from middleware.auth import get_current_user
from db.connection import get_db
from routes.projects import check_project_access, can_edit_chats, verify_project_ownership
from services.rag import get_relevant_chunks, get_embedding, get_openai_client
from services.cache import build_cache_key_context, find_cached_answer, save_to_cache
from services.file_processor import chunk_text
from services.web_search import (
    brave_web_search, fetch_page_texts, should_use_web_search,
    fetch_url_content, extract_urls_from_text, auto_ingest_url
)
from services.catalog_service import search_product_catalog
from services.excel_service import maybe_generate_excel
from services.agent_router import route_to_agent
from services.agents import get_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["messages"])

GLOBAL_PROJECT_ID = "__global__"
MAX_CHUNKS_PER_QUERY = 5

# RAG score thresholds
RAG_SCORE_MIN = 0.35          # Default minimum chunk score
RAG_SCORE_MIN_EXCEL = 0.25   # Lower threshold for xlsx/csv sources
RAG_SCORE_RELEVANT = 0.45     # Threshold to consider RAG "relevant" (skip web search)

EXCEL_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
    "application/csv",
}


async def ensure_gpt_config(db):
    """Ensure GPT config singleton exists. Never overwrites existing config."""
    existing = await db.gpt_config.find_one({}, {"_id": 0})
    if existing:
        return existing

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
- Only generate/modify an Excel file when the user explicitly asks (e.g. "generate", "create new excel", "download", "сгенерируй excel", "создай excel")
- When generating, confirm what you are about to do before doing it
- Never auto-generate Excel just because the user mentioned columns or data""",
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    await db.gpt_config.insert_one(default_config)
    return default_config


# ==================== GET MESSAGES ====================

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
         "excel_file_id": 1, "excel_preview": 1, "is_excel_clarification": 1,
         "uploadedFile": 1, "agent_type": 1, "agent_name": 1}
    ).sort("createdAt", 1).to_list(500)

    return [
        MessageResponse(**{
            **m,
            "citations": m.get("citations"),
            "usedSources": m.get("usedSources"),
            "autoIngestedUrls": m.get("autoIngestedUrls"),
            "senderEmail": m.get("senderEmail"),
            "senderName": m.get("senderName")
        })
        for m in messages
    ]


# ==================== SEND MESSAGE ====================

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

    # ── 1. Auto-ingest URLs from message ──
    detected_urls = extract_urls_from_text(message_data.content)
    auto_ingested_sources = []

    if detected_urls and project_id and can_edit_chats(user_role):
        for url in detected_urls:
            source = await auto_ingest_url(db, url, project_id)
            if source:
                auto_ingested_sources.append(source)

    # ── 2. Collect source IDs by hierarchy ──
    source_mode = chat.get("sourceMode", "all")
    user_department_ids = current_user.get("departments", [])

    personal_sources = await db.sources.find(
        {"level": "personal", "ownerId": current_user["id"], "status": {"$in": ["active", None]}},
        {"_id": 0, "id": 1}
    ).to_list(1000)
    personal_source_ids = [s["id"] for s in personal_sources]

    project_source_ids = []
    if project_id:
        project_sources = await db.sources.find(
            {"projectId": project_id, "level": {"$in": ["project", None]}, "status": {"$in": ["active", None]}},
            {"_id": 0, "id": 1}
        ).to_list(1000)
        project_source_ids = [s["id"] for s in project_sources]

    department_source_ids = []
    global_source_ids = []
    if source_mode == 'all':
        if user_department_ids:
            dept_sources = await db.sources.find(
                {"departmentId": {"$in": user_department_ids}, "level": "department", "status": "active"},
                {"_id": 0, "id": 1}
            ).to_list(1000)
            department_source_ids = [s["id"] for s in dept_sources]

        global_sources = await db.sources.find(
            {"$or": [{"projectId": GLOBAL_PROJECT_ID}, {"level": "global", "status": "active"}]},
            {"_id": 0, "id": 1}
        ).to_list(1000)
        global_source_ids = [s["id"] for s in global_sources]

    active_source_ids = personal_source_ids + project_source_ids + department_source_ids + global_source_ids
    user_accessible_source_ids = active_source_ids.copy()

    # AI Only mode — bypass all sources and web search
    if source_mode == 'ai_only':
        active_source_ids = []
        personal_source_ids = []
        project_source_ids = []
        department_source_ids = []
        global_source_ids = []

    # Apply user's checkbox selection from SourcePanel.
    # Prefer payload value (real-time from frontend) over DB value (may lag due to 500ms debounce).
    # None  = chat never touched (new chat) → use all accessible sources
    # []    = user explicitly unchecked everything → no sources
    # [ids] = user selected specific sources → intersect with accessible
    if source_mode != 'ai_only':
        chat_selected = (
            message_data.activeSourceIds
            if message_data.activeSourceIds is not None
            else chat.get("activeSourceIds")
        )
        if chat_selected is not None:
            if len(chat_selected) == 0:
                active_source_ids = []
            else:
                sel_set = set(chat_selected)
                active_source_ids = [sid for sid in active_source_ids if sid in sel_set]

    # ── 3. Save user message ──
    sender_email = current_user["email"]
    sender_name = sender_email.split("@")[0] if sender_email else "User"
    user_msg_id = str(uuid.uuid4())

    # Load temp file content if provided
    temp_file_content_text = ""
    temp_file_image_b64 = None
    temp_file_mime = None
    temp_file_info = None
    temp_excel_path = None  # path to temp Excel/CSV — passed to maybe_generate_excel
    if message_data.temp_file_id:
        from pathlib import Path as _Path
        _TEMP_DIR = _Path("/tmp/planet_temp_files")
        _matches = list(_TEMP_DIR.glob(f"{message_data.temp_file_id}_*"))
        if _matches:
            _temp_path = _matches[0]
            _filename = _temp_path.name.split("_", 1)[-1]  # strip UUID prefix
            _ext = _filename.rsplit(".", 1)[-1].lower() if "." in _filename else ""
            _content = _temp_path.read_bytes()
            _image_exts = {"jpg", "jpeg", "png"}
            # Capture Excel/CSV path for generation/editing
            if _ext in ("xlsx", "xls", "csv"):
                temp_excel_path = str(_temp_path)
            try:
                if _ext in _image_exts:
                    import base64 as _b64
                    temp_file_image_b64 = _b64.b64encode(_content).decode()
                    temp_file_mime = "image/jpeg" if _ext in ("jpg", "jpeg") else "image/png"
                    temp_file_content_text = "[Изображение прикреплено]"
                elif _ext == "pdf":
                    import pdfplumber as _plumber
                    from io import BytesIO as _BIO
                    _parts = []
                    with _plumber.open(_BIO(_content)) as _pdf:
                        for _pg in _pdf.pages:
                            _t = _pg.extract_text() or ""
                            if _t.strip():
                                _parts.append(_t)
                    temp_file_content_text = "\n\n".join(_parts)
                elif _ext in ("xlsx", "xls"):
                    from services.file_processor import extract_text_from_xlsx as _xread
                    temp_file_content_text = _xread(_content)
                elif _ext == "csv":
                    from services.file_processor import extract_text_from_csv as _cread
                    temp_file_content_text = _cread(_content)
                elif _ext == "docx":
                    from services.file_processor import extract_text_from_docx as _dread
                    temp_file_content_text = _dread(_content)
            except Exception as _te:
                logger.error(f"Temp file read error: {_te}")
            temp_file_info = {"name": _filename, "fileType": _ext if _ext not in _image_exts else "image"}

    user_message = {
        "id": user_msg_id,
        "chatId": chat_id,
        "role": "user",
        "content": message_data.content,
        "citations": None,
        "autoIngestedUrls": [s["id"] for s in auto_ingested_sources] if auto_ingested_sources else None,
        "senderEmail": sender_email,
        "senderName": sender_name,
        "uploadedFile": temp_file_info,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    if not regen:
        await db.messages.insert_one(user_message)

    # ── 4. Config & history ──
    config = await ensure_gpt_config(db)
    history = await db.messages.find(
        {"chatId": chat_id},
        {"_id": 0, "role": 1, "content": 1, "createdAt": 1}
    ).sort("createdAt", -1).to_list(20)
    history = list(reversed(history))

    # ── 5. Build RAG context ──
    citations = []
    document_context = ""
    active_source_names = []
    source_types = {}
    xlsx_sheet_info = []
    has_excel_source = False
    mentioned_source_ids = []
    source_names = {}

    if active_source_ids:
        sources = await db.sources.find({"id": {"$in": active_source_ids}}, {"_id": 0}).to_list(1000)
        source_names = {}
        excel_source_ids = set()

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

            # Track excel sources for lower threshold
            if s.get("mimeType") in EXCEL_MIME_TYPES:
                excel_source_ids.add(s["id"])
                has_excel_source = True

            # Collect sheet names for xlsx sources
            sheet_names = s.get("sheetNames", [])
            if sheet_names and s.get("mimeType") in (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
            ):
                xlsx_sheet_info.append(f"- {name}: {', '.join(sheet_names)}")

        # Pre-RAG: if user mentions a specific source name, restrict retrieval to that source
        user_msg_lower = message_data.content.lower()
        mentioned_source_ids = []
        for s in sources:
            name = (s.get("originalName") or s.get("url") or "").lower().strip()
            if name and len(name) > 3 and name in user_msg_lower:
                mentioned_source_ids.append(s["id"])

        rag_source_ids = mentioned_source_ids if mentioned_source_ids else active_source_ids

        relevant_chunks = await get_relevant_chunks(
            db, rag_source_ids, project_id, message_data.content, user_department_ids,
            mentioned_source_ids=mentioned_source_ids
        )

        if relevant_chunks:
            def chunk_priority(chunk):
                source_type = source_types.get(chunk["sourceId"], "global")
                type_priority = {"project": 0, "department": 1, "global": 2}.get(source_type, 2)
                return (type_priority, -chunk.get("score", 0))

            relevant_chunks.sort(key=chunk_priority)

            context_parts = []
            for chunk in relevant_chunks:
                score = chunk.get("score", 0)
                source_id = chunk["sourceId"]
                # Use lower threshold for excel sources
                min_score = RAG_SCORE_MIN_EXCEL if source_id in excel_source_ids else RAG_SCORE_MIN
                if score <= min_score:
                    continue

                source_name = source_names.get(source_id, "Unknown")
                source_type = source_types.get(source_id, "global")
                chunk_marker = f"[Source: {source_name} ({source_type.upper()}), Chunk {chunk['chunkIndex']+1}]"
                context_parts.append(f"{chunk_marker}\n{chunk['content']}")
                citations.append({
                    "sourceName": source_name,
                    "sourceId": source_id,
                    "sourceType": source_type,
                    "chunkId": chunk.get("id", ""),
                    "chunkIndex": chunk["chunkIndex"],
                    "textFragment": chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk["content"],
                    "score": score
                })

            document_context = "\n\n---\n\n".join(context_parts)

    # ── 6. Fetch URL content from message ──
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

        if url_context_parts:
            url_fetched_context = "\n\n---\n\n".join(url_context_parts)
            if document_context:
                document_context = f"===== FETCHED URL CONTENT =====\n\n{url_fetched_context}\n\n===== DOCUMENT CONTEXT =====\n\n{document_context}"
            else:
                document_context = f"===== FETCHED URL CONTENT =====\n\n{url_fetched_context}"

    has_relevant_rag = any(c.get("score", 0) > RAG_SCORE_RELEVANT for c in citations)
    has_rag_context = bool(citations)

    # ── 7. Product catalog search ──
    catalog_results = await search_product_catalog(message_data.content, db, limit=5)
    catalog_context = ""
    if catalog_results:
        catalog_parts = []
        for p in catalog_results:
            relations_count = len(p.get("relations", []))
            catalog_parts.append(
                f"[Product: {p.get('title_en')}]\n"
                f"Article: {p.get('article_number')} | Vendor: {p.get('vendor')} | Model: {p.get('product_model', '')}\n"
                f"Category: {p.get('root_category', '')} > {p.get('lvl1_subcategory', '')}\n"
                f"Price: {p.get('price', 'N/A')} | Related products: {relations_count}\n"
                f"Description: {str(p.get('description', ''))[:300]}"
            )
        catalog_context = "===== PRODUCT CATALOG =====\n\n" + "\n\n---\n\n".join(catalog_parts)

    if catalog_context:
        document_context = f"{catalog_context}\n\n{document_context}" if document_context else catalog_context

    # ── 8. Web search fallback ──
    web_search_results = None
    web_sources = None

    _project_memory_text = ""
    if project_id:
        _proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "project_memory": 1})
        _project_memory_text = (_proj or {}).get("project_memory", "") or ""
    has_project_memory = bool(_project_memory_text and len(_project_memory_text.strip()) > 50)

    brave_key_exists = bool(os.environ.get('BRAVE_API_KEY', ''))
    use_web_search = should_use_web_search(message_data.content, has_relevant_rag)
    if source_mode == 'ai_only':
        use_web_search = False

    _words = message_data.content.strip().split()
    _msg_lower = message_data.content.lower()
    _TRIVIAL_STOP = ["barev", "բарев", "привет", "hello", "hi", "salam",
                     "vonc es", "inch ka", "mersi", "shnorhakalutyun",
                     "poxi", "popoxir", "kpoxes", "popoxeq", "gri", "grep", "greq",
                     "avel", "aveli", "hanel", "jnjel", "poxel", "khmbagrel",
                     "փոխիր", "գրիր", "ջնջիր", "ավելացրու"]
    _is_trivial = len(_words) <= 4 or any(w in _msg_lower for w in _TRIVIAL_STOP)

    # Don't web search if user is asking about excel source content
    if has_excel_source and has_rag_context:
        use_web_search = False

    # Don't web search for Armenian edit commands
    _ARMENIAN_EDIT_WORDS = ["poxi", "popoxir", "kpoxes", "gri", "avel", "jnjel", "poxel", "փոխիր", "գրիր", "ջնջիր"]
    if any(w in _msg_lower for w in _ARMENIAN_EDIT_WORDS):
        use_web_search = False

    if not use_web_search and not has_relevant_rag and not fetched_url_count \
            and brave_key_exists and not _is_trivial and not has_project_memory \
            and not active_source_ids and source_mode != 'ai_only':
        use_web_search = True
        logger.info("Fallback web search: no RAG results, auto-triggering")

    if use_web_search:
        web_search_results = await brave_web_search(message_data.content)
        if web_search_results:
            web_sources = [{"title": r["title"], "url": r["url"]} for r in web_search_results]
            enriched_results = await fetch_page_texts(web_search_results, top_n=2, per_page=500, total_limit=1000)
            web_context_parts = []
            for idx, result in enumerate(enriched_results[:5], 1):
                page_text = result.get("page_text", "").strip()
                snippet = page_text if page_text else result.get("description", "")
                web_context_parts.append(
                    f"[Web Result {idx}: {result['title']}]\nURL: {result['url']}\n{snippet}"
                )
            web_context = "\n\n---\n\n".join(web_context_parts)
            document_context = (
                f"{document_context}\n\n===== WEB SEARCH RESULTS =====\n\n{web_context}"
                if document_context else f"===== WEB SEARCH RESULTS =====\n\n{web_context}"
            )

    # ── 9. Determine context type ──
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

    # ── 10. Cache & user config ──
    user_prompt_doc = await db.user_prompts.find_one({"userId": current_user["id"]}, {"_id": 0})
    user_custom_prompt = user_prompt_doc.get("customPrompt") if user_prompt_doc else None

    user_model = current_user.get("gptModel")
    model_to_use = user_model if user_model else config["model"]

    cache_context_hash = build_cache_key_context(
        project_id=project_id,
        model=model_to_use,
        developer_prompt=config["developerPrompt"],
        user_prompt=user_custom_prompt,
        source_ids=active_source_ids
    )

    cache_hit = None
    question_embedding = None
    openai_client = get_openai_client()

    if active_source_ids and openai_client:
        question_embedding = await get_embedding(message_data.content)
        if question_embedding:
            cache_hit = await find_cached_answer(
                db, message_data.content, project_id, question_embedding,
                cache_context_hash, user_accessible_source_ids
            )

    # ── 11. Claude API call ──
    response_text = ""
    from_cache = False
    cache_info = None
    clarifying_question = None
    clarifying_options = None
    selected_agent_type = "general"
    selected_agent = get_agent("general")

    try:
        CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

        if cache_hit:
            response_text = cache_hit["answer"]
            response_text += f"\n\n---\n_📦 Ответ из кэша (схожесть: {cache_hit['similarity']:.0%})_"
            from_cache = True
            tokens_used = 0
            cache_info = {
                "similarity": cache_hit['similarity'],
                "hitCount": cache_hit['hitCount'],
                "cacheId": cache_hit['cacheId']
            }
        else:
            # ── Agent routing ──
            selected_agent_type = await route_to_agent(
                message=message_data.content,
                has_excel_source=has_excel_source,
                has_rag_context=has_rag_context,
                use_web_search=use_web_search,
            )
            selected_agent = get_agent(selected_agent_type)
            logger.info(f"Agent selected: {selected_agent['name']}")

            system_parts = [config["developerPrompt"], selected_agent["system_prompt"]]

            # Project memory
            if project_id:
                project_doc = await db.projects.find_one({"id": project_id}, {"_id": 0})
                if project_doc and project_doc.get("project_memory"):
                    system_parts.append(
                        f"BACKGROUND CONTEXT:\n{project_doc['project_memory']}\n\n"
                        "Use this context naturally when relevant. Do not mention or reference this context explicitly."
                    )

            if user_custom_prompt:
                system_parts.append(f"USER INSTRUCTIONS:\n{user_custom_prompt}")

            # Inject real sheet names
            if xlsx_sheet_info:
                system_parts.append(
                    "EXCEL FILE SHEETS (real data from uploaded files — use ONLY these, never invent sheet names):\n"
                    + "\n".join(xlsx_sheet_info)
                )

            if document_context:
                active_sources_list = ", ".join(active_source_names) if active_source_names else "None"
                chunks_count = len(citations)
                max_context_chars = 18000 if fetched_url_count > 0 else 10000
                targeted_note = ""
                if mentioned_source_ids:
                    targeted_names = [source_names.get(sid, sid) for sid in mentioned_source_ids]
                    targeted_note = f" targeted={', '.join(targeted_names)} | IMPORTANT: The user explicitly asked about these file(s). Focus ONLY on content from these sources."
                context_message = (
                    f"[SYS_META sources={active_sources_list} chunks={chunks_count}{targeted_note}]\n\n"
                    f"{document_context[:max_context_chars]}"
                )
                system_parts.append(context_message)
            elif active_source_names:
                # Always inform AI about active sources even when no chunks matched the query
                active_sources_list = ", ".join(active_source_names)
                system_parts.append(
                    f"[SYS_META sources={active_sources_list} chunks=0]\n\n"
                    f"The following sources are active: {active_sources_list}. "
                    "No relevant content was retrieved for this specific query, but the sources exist and are active."
                )

            if fetched_url_count > 0:
                system_parts.append(
                    "IMPORTANT: Content fetched from URL(s) provided by the user is included above under "
                    "'FETCHED URL CONTENT'. Use this content to answer questions about those URLs. "
                    "When referencing URL content, mention the source URL."
                )

            if web_search_results:
                system_parts.append(
                    "WEB SEARCH ACCESS: You have been provided with real-time web search results above "
                    "(under '===== WEB SEARCH RESULTS ====='). This means you DO have access to current "
                    "internet information for this query.\n\n"
                    "RULES FOR USING WEB RESULTS:\n"
                    "1. NEVER say 'I cannot access the internet' — you HAVE been given the search results.\n"
                    "2. Use the provided web content as your primary source for this query.\n"
                    "3. If page content is available in a result, use it.\n"
                    "4. Synthesize information from multiple results when relevant.\n"
                    "5. ALWAYS cite your web sources at the end:\n\nИсточники:\n- [Title](URL)\n- [Title](URL)"
                )

            if catalog_results:
                system_parts.append(
                    "PRODUCT CATALOG: You have been provided with matching products from the company's "
                    "product catalog above (under '===== PRODUCT CATALOG =====').\n"
                    "- Use this data to answer product-related questions accurately\n"
                    "- Mention article numbers and vendors when relevant\n"
                    "- Do not invent prices or specs not present in the catalog data"
                )

            if context_type == "rag":
                system_parts.append(
                    "FINAL INSTRUCTION: Answer based on the provided document sources above. "
                    "Cite relevant sources using [Source: name] format."
                )
            elif context_type == "none":
                system_parts.append(
                    "FINAL INSTRUCTION: No document sources or web results are available for this query. "
                    "Answer from your own knowledge directly and helpfully. "
                    "Do NOT say 'there are no sources' or 'no information available in the uploaded files'. "
                    "Simply answer the question as a knowledgeable assistant would."
                )

            system_prompt = "\n\n".join(system_parts)
            system_prompt += (
                "\n\nIMPORTANT: Do NOT generate XML tags, <excel_file>, <file>, or any fake file structures. "
                "If the user asks to create/modify/download an Excel/CSV file — the system handles generation automatically."
            )
            system_prompt += (
                "\n\nSTRICT RULE: Never generate Excel/CSV files on your own initiative. "
                "Only when user explicitly asks: \"создай Excel\", \"сделай таблицу\", \"generate excel\", \"create spreadsheet\"."
            )

            # ── Inject temp file content ──
            if temp_file_content_text and not temp_file_image_b64:
                _fname = temp_file_info.get("name", "файл") if temp_file_info else "файл"
                system_prompt += (
                    f"\n\n===== ПРИКРЕПЛЁННЫЙ ФАЙЛ: {_fname} =====\n"
                    f"{temp_file_content_text[:8000]}\n"
                    "===== КОНЕЦ ФАЙЛА =====\n"
                    "Используй содержимое этого файла для ответа на вопрос пользователя."
                )

            messages = []
            for msg in history[:-1]:
                content = msg.get("content", "").strip()
                if content:
                    messages.append({"role": msg["role"], "content": content})

            # Build last user message — vision block for images, plain text otherwise
            _user_text = message_data.content.strip() or (
                "Что на этом изображении?" if temp_file_image_b64
                else "Проанализируй прикреплённый файл"
            )
            if temp_file_image_b64 and temp_file_mime:
                user_content = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": temp_file_mime,
                            "data": temp_file_image_b64,
                        },
                    },
                    {"type": "text", "text": _user_text},
                ]
            else:
                user_content = _user_text

            if isinstance(user_content, list):
                for block in user_content:
                    if block.get("type") == "text" and not block.get("text", "").strip():
                        block["text"] = "Analyze this file and summarize the key points."
            elif not str(user_content).strip():
                user_content = "Analyze this file and summarize the key points."
            messages.append({"role": "user", "content": user_content})

            claude_response = claude_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=messages
            )

            response_text = claude_response.content[0].text
            tokens_used = claude_response.usage.input_tokens + claude_response.usage.output_tokens

            if "<clarifying>" in response_text and "</clarifying>" in response_text:
                try:
                    match = re.search(r'<clarifying>(.*?)</clarifying>', response_text, re.DOTALL)
                    if match:
                        clarifying_data = json.loads(match.group(1).strip())
                        clarifying_question = clarifying_data.get("question")
                        clarifying_options = clarifying_data.get("options", [])
                        response_text = response_text[:match.start()].strip()
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

    # ── 12. Excel generation ──
    excel_file_id = None
    excel_preview = None
    is_excel_clarification = False

    if not response_text.startswith("Error:"):
        try:
            CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
            excel_claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
            excel_file_id, excel_preview, response_text, is_excel_clarification = await maybe_generate_excel(
                db=db,
                chat_id=chat_id,
                project_id=project_id,
                active_source_ids=active_source_ids,
                message_content=message_data.content,
                claude_client=excel_claude_client,
                current_response_text=response_text,
                temp_file_path=temp_excel_path,
            )
            print(f"[EXCEL RESULT DEBUG] excel_file_id={excel_file_id}, excel_preview={excel_preview}, is_clarification={is_excel_clarification}")
        except Exception as e:
            logger.error(f"Excel service error: {str(e)}")

    # ── 13. Deduplicate citations ──
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

    # ── 14. Save to semantic cache ──
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

    # ── 15. Save assistant message ──
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
        "is_excel_clarification": is_excel_clarification,
        "agent_type": selected_agent_type,
        "agent_name": selected_agent["name"],
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(assistant_message)

    # ── 16. Track source usage ──
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
    db = get_db()
    message = await db.messages.find_one({"id": message_id, "chatId": chat_id}, {"_id": 0})

    if not message:
        message_check = await db.messages.find_one({"id": message_id}, {"_id": 0})
        if message_check:
            logger.error(f"Message exists but chatId mismatch: expected {chat_id}, got {message_check.get('chatId')}")
        else:
            logger.error(f"Message {message_id} not found in database")
        raise HTTPException(status_code=404, detail="Message not found")

    is_author = message.get("senderEmail") == current_user["email"]
    is_user_message_in_own_chat = (
        message.get("role") == "user" and not message.get("senderEmail")
    )

    if not (is_author or is_user_message_in_own_chat):
        if is_user_message_in_own_chat:
            chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
            if chat and chat.get("ownerId") != current_user["id"]:
                raise HTTPException(status_code=403, detail="Only message author can edit")
        else:
            raise HTTPException(status_code=403, detail="Only message author can edit")

    if message.get("role") != "user":
        raise HTTPException(status_code=400, detail="Only user messages can be edited")

    message_created_at = message.get("createdAt")
    await db.messages.update_one(
        {"id": message_id},
        {"$set": {"content": edit_data.content, "updatedAt": datetime.now(timezone.utc).isoformat()}}
    )

    deleted_result = await db.messages.delete_many({
        "chatId": chat_id,
        "createdAt": {"$gt": message_created_at}
    })
    logger.info(f"Deleted {deleted_result.deleted_count} messages after edited message")

    updated_message = await db.messages.find_one({"id": message_id}, {"_id": 0})
    return MessageResponse(**updated_message)


# ==================== SAVE TO KNOWLEDGE ====================

@router.post("/save-to-knowledge")
async def save_to_knowledge(
    request: SaveToKnowledgeRequest,
    current_user: dict = Depends(get_current_user)
):
    """Save AI message content as a Personal or Project Source"""
    db = get_db()
    openai_client = get_openai_client()

    try:
        content_preview = request.content[:50].replace('\n', ' ').strip()
        if len(request.content) > 50:
            content_preview += "..."
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        source_name = f"{content_preview} ({timestamp})"
        source_id = str(uuid.uuid4())

        # Resolve project from chat if provided
        # Always keep level=personal so it appears in My Sources page.
        # projectId is set to link it to the project for visibility.
        source_project_id = None
        chat_doc = None
        if request.chatId:
            chat_doc = await db.chats.find_one({"id": request.chatId}, {"_id": 0, "projectId": 1, "activeSourceIds": 1})
            if chat_doc and chat_doc.get("projectId"):
                source_project_id = chat_doc["projectId"]

        source_doc = {
            "id": source_id,
            "level": "personal",
            "ownerId": current_user["id"],
            "ownerEmail": current_user["email"],
            "projectId": source_project_id,
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

        # Auto-add the new source to the chat's active sources
        if request.chatId:
            existing_active = (chat_doc.get("activeSourceIds") or []) if chat_doc else []
            if source_id not in existing_active:
                await db.chats.update_one(
                    {"id": request.chatId},
                    {"$push": {"activeSourceIds": source_id}}
                )

        chunks = chunk_text(request.content, chunk_size=1000)
        for i, chunk_text_content in enumerate(chunks):
            try:
                embedding = None
                if openai_client:
                    embedding_response = openai_client.embeddings.create(
                        model="text-embedding-3-small",
                        input=chunk_text_content
                    )
                    embedding = embedding_response.data[0].embedding

                await db.source_chunks.insert_one({
                    "id": str(uuid.uuid4()),
                    "sourceId": source_id,
                    "sourceName": source_name,
                    "chunkIndex": i,
                    "text": chunk_text_content,
                    "embedding": embedding,
                    "createdAt": datetime.now(timezone.utc).isoformat()
                })
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

        return {"success": True, "sourceId": source_id, "sourceName": source_name, "message": "Saved to Knowledge ✅"}

    except Exception as e:
        logger.error(f"Error saving to knowledge: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save: {str(e)}")


# ==================== SAVE CONTEXT ====================

@router.post("/chats/{chat_id}/save-context")
async def save_chat_context(chat_id: str, data: dict, current_user: dict = Depends(get_current_user)):
    """Save chat context to user's AI Profile via summarization"""
    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    if chat.get("ownerId") != current_user["id"]:
        if chat.get("projectId"):
            project = await db.projects.find_one({"id": chat["projectId"]}, {"_id": 0})
            if not project or project.get("ownerId") != current_user["id"]:
                raise HTTPException(status_code=403, detail="Access denied")

    dialog_text = data.get("dialogText", "")
    if not dialog_text or len(dialog_text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Dialog text too short")

    try:
        CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
        if not CLAUDE_API_KEY:
            raise HTTPException(status_code=500, detail="AI service not configured")

        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system="Прочитай этот диалог и напиши краткое резюме: какие темы обсуждались, к каким выводам пришли, что важно помнить для продолжения в следующем чате. Максимум 150 слов. Только резюме, без предисловий.",
            messages=[{"role": "user", "content": dialog_text}]
        )

        summary = response.content[0].text.strip()
        words = summary.split()
        if len(words) > 200:
            summary = ' '.join(words[:150]) + '...'

        now = datetime.now(timezone.utc)
        context_prefix = f"[Контекст чата: {now.strftime('%Y-%m-%d %H:%M')}]\n{summary}"

        user_data = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        ai_profile = user_data.get("ai_profile", {})
        existing_instruction = ai_profile.get("custom_instruction", "")
        updated_instruction = f"{existing_instruction}\n\n{context_prefix}".strip() if existing_instruction else context_prefix

        await db.users.update_one(
            {"id": current_user["id"]},
            {"$set": {
                "ai_profile.custom_instruction": updated_instruction,
                "ai_profile.updatedAt": now.isoformat()
            }}
        )

        return {"success": True, "summary": summary, "message": "Контекст сохранен в AI Profile"}

    except Exception as e:
        logger.error(f"Error saving context: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save context: {str(e)}")


# ==================== EXTRACT MEMORY POINTS ====================

@router.post("/chats/{chat_id}/extract-memory-points")
async def extract_memory_points(chat_id: str, data: dict, current_user: dict = Depends(get_current_user)):
    """Extract key facts from conversation for project memory"""
    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    dialog_text = data.get("dialogText", "")
    if not dialog_text or len(dialog_text.strip()) < 20:
        return {"points": []}

    try:
        CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
        claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        response = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=(
                "You are extracting PROJECT KNOWLEDGE from a conversation. "
                "Extract only permanent, reusable facts about the project, domain, business rules, decisions, or technical details discussed. "
                "DO NOT describe what was asked or answered. DO NOT write meta-descriptions like 'user asked about X'. "
                "Instead write the actual fact, e.g. 'Stock Order deposit is 20%'. "
                "Return ONLY a JSON array of strings (max 10 items). Each item max 100 chars. "
                "Write in the SAME LANGUAGE as the conversation content. No preamble, no markdown, pure JSON array."
            ),
            messages=[{"role": "user", "content": dialog_text[:8000]}]
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        if not text.startswith("["):
            match = re.search(r'\[.*\]', text, re.DOTALL)
            text = match.group(0) if match else "[]"
        if not text:
            return {"points": []}

        points = json.loads(text.strip())
        return {"points": points if isinstance(points, list) else []}

    except Exception as e:
        logger.error(f"Extract memory points error: {str(e)}")
        return {"points": []}