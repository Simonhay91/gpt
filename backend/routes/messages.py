"""Message routes — RAG pipeline, web search, Excel generation"""
import os
import re
import uuid
import json
import asyncio
import hashlib
import logging
from typing import List, Optional
from datetime import datetime, timezone

import anthropic
import openai as openai_lib
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from models.schemas import MessageCreate, MessageResponse, SaveToKnowledgeRequest, MessageEditRequest
from middleware.auth import get_current_user
from db.connection import get_db
from routes.projects import check_project_access, can_edit_chats, verify_project_ownership
from services.rag import (
    get_relevant_chunks, get_embedding, get_openai_client,
    is_summary_query, get_document_overview_chunks, get_company_info_context,
)
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


async def get_accessible_library_source_ids(db, current_user: dict) -> list:
    """Library items the user may activate in a chat.

    An item is accessible when it is shared with one of the user's departments,
    shared with the user's position, marked global, or the user is an admin.
    Library items are opt-in: they are returned as part of the *accessible* pool
    but are only used when the user explicitly selects them in the Source panel
    (or auto-activated in a Tutor chat).
    """
    from middleware.auth import is_admin as _is_admin
    if _is_admin(current_user.get("email", "")):
        query = {"level": "library", "status": {"$in": ["active", None]}}
    else:
        user_depts = current_user.get("departments", [])
        or_clauses = [
            {"sharedDepartments": {"$in": user_depts}},
            {"isGlobalLibrary": True},
        ]
        pos = (current_user.get("ai_profile") or {}).get("position")
        if pos:
            or_clauses.append({"sharedPositions": pos})
        query = {
            "level": "library",
            "status": {"$in": ["active", None]},
            "$or": or_clauses,
        }
    items = await db.sources.find(query, {"_id": 0, "id": 1}).to_list(1000)
    return [it["id"] for it in items]


async def get_position_library_source_ids(db, current_user: dict) -> list:
    """Library items assigned to the user's position only (for Tutor auto-activation)."""
    pos = (current_user.get("ai_profile") or {}).get("position")
    if not pos:
        return []
    items = await db.sources.find(
        {"level": "library", "status": {"$in": ["active", None]}, "sharedPositions": pos},
        {"_id": 0, "id": 1},
    ).to_list(1000)
    return [it["id"] for it in items]


async def get_global_source_ids(db) -> list:
    """All global sources (projectId == '__global__'). Used to include them in the
    accessible pool for Tutor chats so they survive the activeSourceIds intersect."""
    items = await db.sources.find(
        {"projectId": GLOBAL_PROJECT_ID},
        {"_id": 0, "id": 1},
    ).to_list(1000)
    return [it["id"] for it in items]


async def _company_info_system_part(db, source_mode: str):
    """Always-on company description, capped to a small budget. None when unset."""
    if source_mode == 'ai_only':
        return None
    ci = await get_company_info_context(db)
    if not ci:
        return None
    return (
        f"COMPANY INFO ({ci['name']}):\n{ci['text']}\n\n"
        "This is general background about the company. Use it naturally when relevant; "
        "do not mention that it was provided as background."
    )


async def _tutor_memory_system_part(db, chat: dict, current_user: dict, active_source_ids: list):
    """Per-book learning progress, injected only in Tutor chats.

    Resolves the user's ``tutor_memory[book_id]`` summaries for the books that
    are active in this chat and formats them as a background "TUTOR PROGRESS"
    note so the AI can continue teaching from where the learner left off.
    """
    if not chat or chat.get("mode") != "tutor":
        return None
    tutor_memory = current_user.get("tutor_memory") or {}
    if not tutor_memory or not active_source_ids:
        return None

    relevant = [(sid, tutor_memory[sid]) for sid in active_source_ids
                if tutor_memory.get(sid) and tutor_memory[sid].get("summary")]
    if not relevant:
        return None

    # Map source ids → human titles for clearer context.
    titles = {}
    sids = [sid for sid, _ in relevant]
    docs = await db.sources.find({"id": {"$in": sids}}, {"_id": 0, "id": 1, "title": 1, "originalName": 1}).to_list(len(sids))
    for d in docs:
        titles[d["id"]] = d.get("title") or d.get("originalName") or "книга"

    notes = []
    for sid, mem in relevant:
        notes.append(f"- {titles.get(sid, 'книга')}: {mem['summary']}")

    return (
        "TUTOR PROGRESS (what this learner has already covered):\n"
        + "\n".join(notes)
        + "\n\nContinue teaching from here. Briefly acknowledge prior progress, then move forward."
    )

# RAG score thresholds
RAG_SCORE_MIN = 0.20          # Default minimum chunk score (lowered — generic queries score lower)
RAG_SCORE_MIN_EXCEL = 0.15   # Lower threshold for xlsx/csv sources
RAG_SCORE_RELEVANT = 0.40     # Threshold to consider RAG "relevant" (skip web search)

EXCEL_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "text/csv",
    "application/csv",
}


def _to_openai_messages(system_prompt: str, anthropic_messages: list) -> list:
    """Convert Anthropic-format messages to OpenAI chat format."""
    result = [{"role": "system", "content": system_prompt}]
    for msg in anthropic_messages:
        role = msg["role"]
        content = msg["content"]
        if isinstance(content, list):
            oai_content = []
            for block in content:
                if block.get("type") == "text":
                    oai_content.append({"type": "text", "text": block.get("text", "")})
                elif block.get("type") == "image":
                    src = block.get("source", {})
                    oai_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{src.get('media_type','image/jpeg')};base64,{src.get('data','')}"}
                    })
            result.append({"role": role, "content": oai_content})
        else:
            result.append({"role": role, "content": str(content)})
    return result


async def _openai_fallback(system_prompt: str, anthropic_messages: list) -> tuple[str, int]:
    """Call GPT-4o-mini as fallback. Returns (response_text, tokens_used)."""
    oai_client = openai_lib.AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))
    oai_msgs = _to_openai_messages(system_prompt, anthropic_messages)
    oai_resp = await oai_client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=4096,
        messages=oai_msgs
    )
    text = oai_resp.choices[0].message.content or ""
    tokens = oai_resp.usage.total_tokens if oai_resp.usage else 0
    return text, tokens


async def ensure_gpt_config(db):
    """Ensure GPT config singleton exists. Never overwrites existing config."""
    existing = await db.gpt_config.find_one({}, {"_id": 0})
    if existing:
        return existing

    default_config = {
        "id": "1",
        "model": "claude-sonnet-4-6",
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

    # ── 2. Collect source IDs ──
    # Department and global sources are temporarily excluded from chat RAG.
    # Only personal (My Sources) + project sources are used.
    source_mode = chat.get("sourceMode", "all")
    user_department_ids = []  # dept/global excluded — kept for rag.py signature compatibility

    personal_sources = await db.sources.find(
        {
            "$or": [
                {"level": "personal", "ownerId": current_user["id"]},
                {"level": "personal", "sharedInChatIds": chat_id},
            ],
            "status": {"$in": ["active", None]},
        },
        {"_id": 0, "id": 1, "sharedInChatIds": 1}
    ).to_list(1000)
    personal_source_ids = [s["id"] for s in personal_sources]

    # Sources explicitly shared into this chat — always active regardless of checkbox state
    shared_to_chat_ids = set(
        s["id"] for s in personal_sources
        if chat_id in (s.get("sharedInChatIds") or [])
    )

    project_source_ids = []
    if project_id:
        project_sources = await db.sources.find(
            {"projectId": project_id, "level": {"$in": ["project", None]}, "status": {"$in": ["active", None]}},
            {"_id": 0, "id": 1}
        ).to_list(1000)
        project_source_ids = [s["id"] for s in project_sources]

    # Library items the user can activate (opt-in: not active by default, but part
    # of the accessible pool so explicit checkbox selection in the panel works).
    library_source_ids = await get_accessible_library_source_ids(db, current_user)

    # Global sources are added to the accessible pool for Tutor chats so the IDs
    # stored in activeSourceIds (set at chat creation) survive the intersect below.
    global_source_ids = await get_global_source_ids(db) if chat.get("mode") == "tutor" else []

    active_source_ids = personal_source_ids + project_source_ids
    user_accessible_source_ids = active_source_ids + library_source_ids + global_source_ids

    # AI Only mode — bypass all sources and web search
    if source_mode == 'ai_only':
        active_source_ids = []
        personal_source_ids = []
        project_source_ids = []

    # Apply user's checkbox selection from SourcePanel.
    # Prefer payload value (real-time from frontend) over DB value (may lag due to 500ms debounce).
    # None  = chat never touched (new chat) → use all accessible sources
    # []    = user explicitly unchecked everything → no sources
    # [ids] = user selected specific sources → intersect with accessible
    # NOTE: sources explicitly shared into this chat (shared_to_chat_ids) are always kept,
    #       because they were added via Share to Chat — not via the checkbox panel.
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
                # Intersect with the full accessible pool (incl. library) so an
                # explicitly selected library item is kept active.
                active_source_ids = [sid for sid in user_accessible_source_ids if sid in sel_set]
        # Re-add shared-to-chat sources — they must always be active
        for sid in shared_to_chat_ids:
            if sid not in active_source_ids:
                active_source_ids.append(sid)

    # ── 3. Save user message ──
    sender_email = current_user["email"]
    sender_name = sender_email.split("@")[0] if sender_email else "User"
    user_msg_id = str(uuid.uuid4())

    # Load temp file content if provided (supports multiple files)
    temp_files_data = []  # list of {text, image_b64, mime, info, excel_path}
    _image_exts = {"jpg", "jpeg", "png"}
    _effective_ids = message_data.effective_temp_file_ids
    if _effective_ids:
        from pathlib import Path as _Path
        _TEMP_DIR = _Path("/tmp/planet_temp_files")
        for _fid in _effective_ids:
            _matches = list(_TEMP_DIR.glob(f"{_fid}_*"))
            if not _matches:
                continue
            _temp_path = _matches[0]
            _filename = _temp_path.name.split("_", 1)[-1]
            _ext = _filename.rsplit(".", 1)[-1].lower() if "." in _filename else ""
            _content = _temp_path.read_bytes()
            _fd = {"text": "", "image_b64": None, "mime": None, "info": None, "excel_path": None}
            if _ext in ("xlsx", "xls", "csv"):
                _fd["excel_path"] = str(_temp_path)
            try:
                if _ext in _image_exts:
                    import base64 as _b64
                    _fd["image_b64"] = _b64.b64encode(_content).decode()
                    _fd["mime"] = "image/jpeg" if _ext in ("jpg", "jpeg") else "image/png"
                    _fd["text"] = "[Изображение прикреплено]"
                elif _ext == "pdf":
                    from services.file_processor import extract_text_from_pdf as _pdfread
                    import asyncio as _asyncio
                    loop = _asyncio.get_event_loop()
                    _fd["text"] = await loop.run_in_executor(None, _pdfread, _content)
                elif _ext in ("xlsx", "xls"):
                    from services.file_processor import extract_text_from_xlsx as _xread
                    _fd["text"] = _xread(_content)
                elif _ext == "csv":
                    from services.file_processor import extract_text_from_csv as _cread
                    _fd["text"] = _cread(_content)
                elif _ext == "docx":
                    from services.file_processor import extract_text_from_docx as _dread
                    _fd["text"] = _dread(_content)
            except Exception as _te:
                logger.error(f"Temp file read error: {_te}")
            _fd["info"] = {"name": _filename, "fileType": _ext if _ext not in _image_exts else "image"}
            temp_files_data.append(_fd)

    # Convenience aliases for code that still expects single-file variables
    temp_file_content_text = next((f["text"] for f in temp_files_data if f["text"] and not f["image_b64"]), "")
    temp_file_image_b64 = next((f["image_b64"] for f in temp_files_data if f["image_b64"]), None)
    temp_file_mime = next((f["mime"] for f in temp_files_data if f["mime"]), None)
    temp_file_info = temp_files_data[0]["info"] if temp_files_data else None
    temp_excel_path = next((f["excel_path"] for f in temp_files_data if f["excel_path"]), None)

    _uploaded_infos = [f["info"] for f in temp_files_data if f["info"]]
    user_message = {
        "id": user_msg_id,
        "chatId": chat_id,
        "role": "user",
        "content": message_data.content,
        "citations": None,
        "autoIngestedUrls": [s["id"] for s in auto_ingested_sources] if auto_ingested_sources else None,
        "senderEmail": sender_email,
        "senderName": sender_name,
        "uploadedFile": _uploaded_infos[0] if len(_uploaded_infos) == 1 else None,
        "uploadedFiles": _uploaded_infos if len(_uploaded_infos) > 1 else None,
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
    catalog_results = None  # fetched in parallel with RAG when sources are active

    if active_source_ids:
        sources = await db.sources.find({"id": {"$in": active_source_ids}}, {"_id": 0}).to_list(1000)
        source_names = {}
        excel_source_ids = set()

        for s in sources:
            name = s.get("originalName") or s.get("url") or "Unknown"
            level = s.get("level")
            if level == "library" and s.get("title"):
                name = s.get("title")
            source_names[s["id"]] = name
            active_source_names.append(name)
            if level == "department":
                source_types[s["id"]] = "department"
            elif level == "library":
                source_types[s["id"]] = "library"
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

        # Generic summary/analyze queries: embeddings are weak signal — fetch the
        # first chunks of each active source instead (covers TOC, intro, abstract).
        if is_summary_query(message_data.content):
            _rag_coro = get_document_overview_chunks(
                db, rag_source_ids, chunks_per_source=6
            )
        else:
            _rag_coro = get_relevant_chunks(
                db, rag_source_ids, project_id, message_data.content, user_department_ids,
                mentioned_source_ids=mentioned_source_ids
            )
        # Run RAG and product catalog search in parallel (independent operations)
        relevant_chunks, catalog_results = await asyncio.gather(
            _rag_coro,
            search_product_catalog(message_data.content, db, limit=5)
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
                # rag.py already filters/falls-back; only drop truly empty matches here
                if score <= 0.05:
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

    # ── 7. Product catalog search ── (already fetched in parallel with RAG when sources active)
    if catalog_results is None:
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
    _project_doc_cache = None
    if project_id:
        _project_doc_cache = await db.projects.find_one({"id": project_id}, {"_id": 0})
        _project_memory_text = (_project_doc_cache or {}).get("project_memory", "") or ""
    has_project_memory = bool(_project_memory_text and len(_project_memory_text.strip()) > 50)

    brave_key_exists = bool(os.environ.get('BRAVE_API_KEY', ''))

    # User explicitly requested web search via Plus menu toggle
    # forceWebSearch=True  → always search
    # forceWebSearch=False → user turned it OFF — never search (skip auto + fallback too)
    # forceWebSearch=None  → legacy / not sent — use auto logic
    user_disabled_web_search = (message_data.forceWebSearch is False)

    if user_disabled_web_search:
        use_web_search = False
    elif message_data.forceWebSearch and brave_key_exists and source_mode != 'ai_only':
        use_web_search = True
    else:
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

    if not use_web_search and not user_disabled_web_search \
            and not has_relevant_rag and not fetched_url_count \
            and brave_key_exists and not _is_trivial and not has_project_memory \
            and not active_source_ids and source_mode != 'ai_only':
        use_web_search = True
        logger.info("Fallback web search: no RAG results, auto-triggering")

    # Tutor chats teach strictly from the assigned books — never pull the web in.
    if chat.get("mode") == "tutor":
        use_web_search = False

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
        source_ids=active_source_ids,
        mode=chat.get("mode")
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
    model_used = None

    try:
        CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
        claude_client = anthropic.AsyncAnthropic(api_key=CLAUDE_API_KEY)

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
            # Tutor chats bypass auto-routing — the Tutor agent always wins so
            # teaching behaviour is consistent (Risk 5).
            if chat.get("mode") == "tutor":
                selected_agent_type = "tutor"
            else:
                selected_agent_type = await route_to_agent(
                    message=message_data.content,
                    has_excel_source=has_excel_source,
                    has_rag_context=has_rag_context,
                    use_web_search=use_web_search,
                )
            selected_agent = get_agent(selected_agent_type)
            logger.info(f"Agent selected: {selected_agent['name']}")

            system_parts = [config["developerPrompt"], selected_agent["system_prompt"]]

            # Company Info — always-on, small budget, before everything else
            _ci_part = await _company_info_system_part(db, source_mode)
            if _ci_part:
                system_parts.append(_ci_part)

            # Project memory
            if project_id:
                project_doc = _project_doc_cache
                if project_doc and project_doc.get("project_memory"):
                    system_parts.append(
                        f"BACKGROUND CONTEXT:\n{project_doc['project_memory']}\n\n"
                        "Use this context naturally when relevant. Do not mention or reference this context explicitly."
                    )

            # Tutor memory — per-book learning progress (only in tutor chats)
            _tutor_part = await _tutor_memory_system_part(db, chat, current_user, active_source_ids)
            if _tutor_part:
                system_parts.append(_tutor_part)

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

            # ── Inject current message's temp files ──
            _text_files = [f for f in temp_files_data if f["text"] and not f["image_b64"]]
            _multi = len(_text_files) > 1
            for _i, _fd in enumerate(_text_files):
                _fname = _fd["info"].get("name", "файл") if _fd["info"] else "файл"
                _label = f"ФАЙЛ {_i + 1}: {_fname}" if _multi else f"ПРИКРЕПЛЁННЫЙ ФАЙЛ: {_fname}"
                system_prompt += (
                    f"\n\n===== {_label} =====\n"
                    f"{_fd['text'][:8000]}\n"
                    "===== КОНЕЦ ФАЙЛА =====\n"
                )
            if _text_files:
                system_prompt += "Используй содержимое этих файлов для ответа на вопрос пользователя."

            # ── Inject persistent chat temp files (uploaded in earlier messages) ──
            # Limit: max 3 files, max 15000 total chars to avoid prompt explosion
            chat_temp_files = chat.get("tempFiles") or []
            _current_ids = set(message_data.effective_temp_file_ids)
            persistent_files = [f for f in chat_temp_files if f.get("id") not in _current_ids]
            if persistent_files:
                _ptf_chars = 0
                _PTF_MAX_TOTAL = 15000
                for _ptf in persistent_files[:3]:
                    _pname = _ptf.get("filename", "файл")
                    _pcontent = _ptf.get("content", "")
                    if _pcontent and _ptf_chars < _PTF_MAX_TOTAL:
                        _slice = _pcontent[:_PTF_MAX_TOTAL - _ptf_chars]
                        system_prompt += (
                            f"\n\n===== ФАЙЛ ИЗ ЧАТА: {_pname} =====\n"
                            f"{_slice}\n"
                            "===== КОНЕЦ ФАЙЛА =====\n"
                        )
                        _ptf_chars += len(_slice)

            messages = []
            for msg in history[:-1]:
                content = msg.get("content", "").strip()
                if content:
                    messages.append({"role": msg["role"], "content": content})

            # Build last user message — vision block for images, plain text otherwise
            _image_files = [f for f in temp_files_data if f["image_b64"]]
            _user_text = message_data.content.strip() or (
                "Что на этом изображении?" if _image_files
                else "Проанализируй прикреплённый файл"
            )
            if _image_files:
                user_content = [
                    {"type": "image", "source": {"type": "base64", "media_type": f["mime"], "data": f["image_b64"]}}
                    for f in _image_files
                ] + [{"type": "text", "text": _user_text}]
            else:
                user_content = _user_text

            if isinstance(user_content, list):
                for block in user_content:
                    if block.get("type") == "text" and not block.get("text", "").strip():
                        block["text"] = "Analyze this file and summarize the key points."
            elif not str(user_content).strip():
                user_content = "Analyze this file and summarize the key points."
            messages.append({"role": "user", "content": user_content})

            # Use Sonnet for document-heavy tasks; Haiku for general chat
            _chat_model = (
                "claude-sonnet-4-6"
                if selected_agent_type in ("rag", "excel", "research", "tutor")
                else "claude-haiku-4-5-20251001"
            )
            model_used = _chat_model
            try:
                claude_response = await claude_client.messages.create(
                    model=_chat_model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=messages
                )
                response_text = claude_response.content[0].text
                tokens_used = claude_response.usage.input_tokens + claude_response.usage.output_tokens
            except Exception as _claude_err:
                logger.warning(f"Claude failed ({_claude_err}), falling back to GPT-4o-mini")
                model_used = "gpt-4o-mini"
                response_text, tokens_used = await _openai_fallback(system_prompt, messages)

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
            excel_claude_client = anthropic.AsyncAnthropic(api_key=CLAUDE_API_KEY)
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
        "model_used": model_used,
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


# ==================== STREAMING MESSAGE ====================

@router.post("/chats/{chat_id}/messages/stream")
async def send_message_stream(
    chat_id: str,
    message_data: MessageCreate,
    regen: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Streaming version — yields SSE tokens then a final [META] event with the saved message data."""
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

    # ── 1. Auto-ingest URLs ──
    detected_urls = extract_urls_from_text(message_data.content)
    auto_ingested_sources = []
    if detected_urls and project_id and can_edit_chats(user_role):
        for url in detected_urls:
            source = await auto_ingest_url(db, url, project_id)
            if source:
                auto_ingested_sources.append(source)

    # ── 2. Collect source IDs ──
    source_mode = chat.get("sourceMode", "all")
    user_department_ids = []

    personal_sources = await db.sources.find(
        {
            "$or": [
                {"level": "personal", "ownerId": current_user["id"]},
                {"level": "personal", "sharedInChatIds": chat_id},
            ],
            "status": {"$in": ["active", None]},
        },
        {"_id": 0, "id": 1, "sharedInChatIds": 1}
    ).to_list(1000)
    personal_source_ids = [s["id"] for s in personal_sources]
    shared_to_chat_ids = set(
        s["id"] for s in personal_sources
        if chat_id in (s.get("sharedInChatIds") or [])
    )

    project_source_ids = []
    if project_id:
        project_sources = await db.sources.find(
            {"projectId": project_id, "level": {"$in": ["project", None]}, "status": {"$in": ["active", None]}},
            {"_id": 0, "id": 1}
        ).to_list(1000)
        project_source_ids = [s["id"] for s in project_sources]

    library_source_ids = await get_accessible_library_source_ids(db, current_user)

    # Global sources are added to the accessible pool for Tutor chats so the IDs
    # stored in activeSourceIds (set at chat creation) survive the intersect below.
    global_source_ids = await get_global_source_ids(db) if chat.get("mode") == "tutor" else []

    active_source_ids = personal_source_ids + project_source_ids
    user_accessible_source_ids = active_source_ids + library_source_ids + global_source_ids

    if source_mode == 'ai_only':
        active_source_ids = []
        personal_source_ids = []
        project_source_ids = []

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
                # Intersect with the full accessible pool (incl. library) so an
                # explicitly selected library item is kept active.
                active_source_ids = [sid for sid in user_accessible_source_ids if sid in sel_set]
        for sid in shared_to_chat_ids:
            if sid not in active_source_ids:
                active_source_ids.append(sid)

    # ── 3. Save user message ──
    sender_email = current_user["email"]
    sender_name = sender_email.split("@")[0] if sender_email else "User"
    user_msg_id = str(uuid.uuid4())

    temp_files_data = []
    _image_exts_s = {"jpg", "jpeg", "png"}
    _effective_ids_s = message_data.effective_temp_file_ids
    if _effective_ids_s:
        from pathlib import Path as _Path
        _TEMP_DIR = _Path("/tmp/planet_temp_files")
        for _fid in _effective_ids_s:
            _matches = list(_TEMP_DIR.glob(f"{_fid}_*"))
            if not _matches:
                continue
            _temp_path = _matches[0]
            _filename = _temp_path.name.split("_", 1)[-1]
            _ext = _filename.rsplit(".", 1)[-1].lower() if "." in _filename else ""
            _content = _temp_path.read_bytes()
            _fd = {"text": "", "image_b64": None, "mime": None, "info": None, "excel_path": None}
            if _ext in ("xlsx", "xls", "csv"):
                _fd["excel_path"] = str(_temp_path)
            try:
                if _ext in _image_exts_s:
                    import base64 as _b64
                    _fd["image_b64"] = _b64.b64encode(_content).decode()
                    _fd["mime"] = "image/jpeg" if _ext in ("jpg", "jpeg") else "image/png"
                    _fd["text"] = "[Изображение прикреплено]"
                elif _ext == "pdf":
                    from services.file_processor import extract_text_from_pdf as _pdfread
                    _fd["text"] = await asyncio.get_event_loop().run_in_executor(None, _pdfread, _content)
                elif _ext in ("xlsx", "xls"):
                    from services.file_processor import extract_text_from_xlsx as _xread
                    _fd["text"] = _xread(_content)
                elif _ext == "csv":
                    from services.file_processor import extract_text_from_csv as _cread
                    _fd["text"] = _cread(_content)
                elif _ext == "docx":
                    from services.file_processor import extract_text_from_docx as _dread
                    _fd["text"] = _dread(_content)
            except Exception as _te:
                logger.error(f"Temp file read error: {_te}")
            _fd["info"] = {"name": _filename, "fileType": _ext if _ext not in _image_exts_s else "image"}
            temp_files_data.append(_fd)

    temp_file_content_text = next((f["text"] for f in temp_files_data if f["text"] and not f["image_b64"]), "")
    temp_file_image_b64 = next((f["image_b64"] for f in temp_files_data if f["image_b64"]), None)
    temp_file_mime = next((f["mime"] for f in temp_files_data if f["mime"]), None)
    temp_file_info = temp_files_data[0]["info"] if temp_files_data else None
    temp_excel_path = next((f["excel_path"] for f in temp_files_data if f["excel_path"]), None)

    _uploaded_infos_s = [f["info"] for f in temp_files_data if f["info"]]
    user_message = {
        "id": user_msg_id,
        "chatId": chat_id,
        "role": "user",
        "content": message_data.content,
        "citations": None,
        "autoIngestedUrls": [s["id"] for s in auto_ingested_sources] if auto_ingested_sources else None,
        "senderEmail": sender_email,
        "senderName": sender_name,
        "uploadedFile": _uploaded_infos_s[0] if len(_uploaded_infos_s) == 1 else None,
        "uploadedFiles": _uploaded_infos_s if len(_uploaded_infos_s) > 1 else None,
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
    catalog_results = None

    if active_source_ids:
        sources = await db.sources.find({"id": {"$in": active_source_ids}}, {"_id": 0}).to_list(1000)
        source_names = {}
        excel_source_ids = set()

        for s in sources:
            name = s.get("originalName") or s.get("url") or "Unknown"
            level = s.get("level")
            if level == "library" and s.get("title"):
                name = s.get("title")
            source_names[s["id"]] = name
            active_source_names.append(name)
            if level == "department":
                source_types[s["id"]] = "department"
            elif level == "library":
                source_types[s["id"]] = "library"
            elif s.get("projectId") == GLOBAL_PROJECT_ID or level == "global":
                source_types[s["id"]] = "global"
            else:
                source_types[s["id"]] = "project"
            if s.get("mimeType") in EXCEL_MIME_TYPES:
                excel_source_ids.add(s["id"])
                has_excel_source = True
            sheet_names = s.get("sheetNames", [])
            if sheet_names and s.get("mimeType") in (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
            ):
                xlsx_sheet_info.append(f"- {name}: {', '.join(sheet_names)}")

        user_msg_lower = message_data.content.lower()
        mentioned_source_ids = []
        for s in sources:
            name = (s.get("originalName") or s.get("url") or "").lower().strip()
            if name and len(name) > 3 and name in user_msg_lower:
                mentioned_source_ids.append(s["id"])

        rag_source_ids = mentioned_source_ids if mentioned_source_ids else active_source_ids

        if is_summary_query(message_data.content):
            _rag_coro = get_document_overview_chunks(db, rag_source_ids, chunks_per_source=6)
        else:
            _rag_coro = get_relevant_chunks(
                db, rag_source_ids, project_id, message_data.content, user_department_ids,
                mentioned_source_ids=mentioned_source_ids
            )
        # Run RAG and catalog search in parallel
        relevant_chunks, catalog_results = await asyncio.gather(
            _rag_coro,
            search_product_catalog(message_data.content, db, limit=5)
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
                if score <= 0.05:
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

    # ── 6. Fetch URL content ──
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

    # ── 7. Product catalog (already fetched in parallel with RAG if sources were active) ──
    if catalog_results is None:
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
    _project_doc_cache = None
    if project_id:
        _project_doc_cache = await db.projects.find_one({"id": project_id}, {"_id": 0})
        _project_memory_text = (_project_doc_cache or {}).get("project_memory", "") or ""
    has_project_memory = bool(_project_memory_text and len(_project_memory_text.strip()) > 50)

    brave_key_exists = bool(os.environ.get('BRAVE_API_KEY', ''))
    user_disabled_web_search = (message_data.forceWebSearch is False)

    if user_disabled_web_search:
        use_web_search = False
    elif message_data.forceWebSearch and brave_key_exists and source_mode != 'ai_only':
        use_web_search = True
    else:
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

    if has_excel_source and has_rag_context:
        use_web_search = False
    _ARMENIAN_EDIT_WORDS = ["poxi", "popoxir", "kpoxes", "gri", "avel", "jnjel", "poxel", "փոխիր", "գրիր", "ջնջիր"]
    if any(w in _msg_lower for w in _ARMENIAN_EDIT_WORDS):
        use_web_search = False

    if not use_web_search and not user_disabled_web_search \
            and not has_relevant_rag and not fetched_url_count \
            and brave_key_exists and not _is_trivial and not has_project_memory \
            and not active_source_ids and source_mode != 'ai_only':
        use_web_search = True

    # Tutor chats teach strictly from the assigned books — never pull the web in.
    if chat.get("mode") == "tutor":
        use_web_search = False

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

    # ── 9. Context type ──
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
        source_ids=active_source_ids,
        mode=chat.get("mode")
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

    # ── Build system_prompt & agent (needed before streaming starts) ──
    selected_agent_type = "general"
    selected_agent = get_agent("general")
    system_prompt = ""
    claude_messages = []
    _chat_model = "claude-haiku-4-5-20251001"
    CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY', '')

    if not cache_hit:
        # Tutor chats bypass auto-routing — the Tutor agent always wins (Risk 5).
        if chat.get("mode") == "tutor":
            selected_agent_type = "tutor"
        else:
            selected_agent_type = await route_to_agent(
                message=message_data.content,
                has_excel_source=has_excel_source,
                has_rag_context=has_rag_context,
                use_web_search=use_web_search,
            )
        selected_agent = get_agent(selected_agent_type)
        logger.info(f"[stream] Agent selected: {selected_agent['name']}")

        system_parts = [config["developerPrompt"], selected_agent["system_prompt"]]

        # Company Info — always-on, small budget, before everything else
        _ci_part = await _company_info_system_part(db, source_mode)
        if _ci_part:
            system_parts.append(_ci_part)

        if project_id:
            project_doc = _project_doc_cache
            if project_doc and project_doc.get("project_memory"):
                system_parts.append(
                    f"BACKGROUND CONTEXT:\n{project_doc['project_memory']}\n\n"
                    "Use this context naturally when relevant. Do not mention or reference this context explicitly."
                )

        # Tutor memory — per-book learning progress (only in tutor chats)
        _tutor_part = await _tutor_memory_system_part(db, chat, current_user, active_source_ids)
        if _tutor_part:
            system_parts.append(_tutor_part)

        if user_custom_prompt:
            system_parts.append(f"USER INSTRUCTIONS:\n{user_custom_prompt}")

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

        _text_files_s = [f for f in temp_files_data if f["text"] and not f["image_b64"]]
        _multi_s = len(_text_files_s) > 1
        for _i, _fd in enumerate(_text_files_s):
            _fname = _fd["info"].get("name", "файл") if _fd["info"] else "файл"
            _label = f"ФАЙЛ {_i + 1}: {_fname}" if _multi_s else f"ПРИКРЕПЛЁННЫЙ ФАЙЛ: {_fname}"
            system_prompt += (
                f"\n\n===== {_label} =====\n"
                f"{_fd['text'][:8000]}\n"
                "===== КОНЕЦ ФАЙЛА =====\n"
            )
        if _text_files_s:
            system_prompt += "Используй содержимое этих файлов для ответа на вопрос пользователя."

        chat_temp_files = chat.get("tempFiles") or []
        _current_ids_s = set(message_data.effective_temp_file_ids)
        persistent_files = [f for f in chat_temp_files if f.get("id") not in _current_ids_s]
        if persistent_files:
            _ptf_chars = 0
            _PTF_MAX_TOTAL = 15000
            for _ptf in persistent_files[:3]:
                _pname = _ptf.get("filename", "файл")
                _pcontent = _ptf.get("content", "")
                if _pcontent and _ptf_chars < _PTF_MAX_TOTAL:
                    _slice = _pcontent[:_PTF_MAX_TOTAL - _ptf_chars]
                    system_prompt += (
                        f"\n\n===== ФАЙЛ ИЗ ЧАТА: {_pname} =====\n"
                        f"{_slice}\n"
                        "===== КОНЕЦ ФАЙЛА =====\n"
                    )
                    _ptf_chars += len(_slice)

        for msg in history[:-1]:
            content = msg.get("content", "").strip()
            if content:
                claude_messages.append({"role": msg["role"], "content": content})

        _image_files_s = [f for f in temp_files_data if f["image_b64"]]
        _user_text = message_data.content.strip() or (
            "Что на этом изображении?" if _image_files_s
            else "Проанализируй прикреплённый файл"
        )
        if _image_files_s:
            user_content = [
                {"type": "image", "source": {"type": "base64", "media_type": f["mime"], "data": f["image_b64"]}}
                for f in _image_files_s
            ] + [{"type": "text", "text": _user_text}]
        else:
            user_content = _user_text

        if isinstance(user_content, list):
            for block in user_content:
                if block.get("type") == "text" and not block.get("text", "").strip():
                    block["text"] = "Analyze this file and summarize the key points."
        elif not str(user_content).strip():
            user_content = "Analyze this file and summarize the key points."
        claude_messages.append({"role": "user", "content": user_content})

        _chat_model = (
            "claude-sonnet-4-6"
            if selected_agent_type in ("rag", "excel", "research", "tutor")
            else "claude-haiku-4-5-20251001"
        )

    # ── 11. Stream Claude response ──
    async def event_stream():
        _response_text = ""
        _from_cache = False
        _cache_info = None
        _clarifying_question = None
        _clarifying_options = None
        _tokens_used = 0

        _model_used = _chat_model if not cache_hit else None

        try:
            if cache_hit:
                _full = (
                    cache_hit["answer"]
                    + f"\n\n---\n_📦 Ответ из кэша (схожесть: {cache_hit['similarity']:.0%})_"
                )
                _response_text = _full
                _from_cache = True
                _cache_info = {
                    "similarity": cache_hit["similarity"],
                    "hitCount": cache_hit["hitCount"],
                    "cacheId": cache_hit["cacheId"],
                }
                chunk_size = 30
                for i in range(0, len(_full), chunk_size):
                    yield f"data: {json.dumps({'token': _full[i:i+chunk_size]})}\n\n"
                    await asyncio.sleep(0)
            else:
                claude_client = anthropic.AsyncAnthropic(api_key=CLAUDE_API_KEY)
                _claude_ok = False
                try:
                    async with claude_client.messages.stream(
                        model=_chat_model,
                        max_tokens=4096,
                        system=system_prompt,
                        messages=claude_messages
                    ) as stream:
                        async for text in stream.text_stream:
                            _response_text += text
                            yield f"data: {json.dumps({'token': text})}\n\n"
                        _final_msg = await stream.get_final_message()
                        _tokens_used = _final_msg.usage.input_tokens + _final_msg.usage.output_tokens
                    _claude_ok = True
                except Exception as _claude_err:
                    logger.warning(f"[stream] Claude failed ({_claude_err}), falling back to GPT-4o-mini")
                    _model_used = "gpt-4o-mini"
                    _response_text = ""
                    # Stream from GPT-4o-mini
                    _oai_client = openai_lib.AsyncOpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))
                    _oai_msgs = _to_openai_messages(system_prompt, claude_messages)
                    _oai_stream = await _oai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        max_tokens=4096,
                        messages=_oai_msgs,
                        stream=True
                    )
                    async for _chunk in _oai_stream:
                        _delta = _chunk.choices[0].delta.content if _chunk.choices else None
                        if _delta:
                            _response_text += _delta
                            yield f"data: {json.dumps({'token': _delta})}\n\n"

        except Exception as e:
            logger.error(f"[stream] Error: {e}")
            yield f"data: {json.dumps({'error': str(e)[:100]})}\n\n"
            return

        # Parse clarifying question
        if "<clarifying>" in _response_text and "</clarifying>" in _response_text:
            try:
                _match = re.search(r'<clarifying>(.*?)</clarifying>', _response_text, re.DOTALL)
                if _match:
                    _cdata = json.loads(_match.group(1).strip())
                    _clarifying_question = _cdata.get("question")
                    _clarifying_options = _cdata.get("options", [])
                    _response_text = _response_text[:_match.start()].strip()
            except Exception as e:
                logger.error(f"[stream] Clarifying parse error: {e}")

        # Token usage
        if _tokens_used > 0:
            await db.token_usage.update_one(
                {"userId": current_user["id"]},
                {
                    "$inc": {"totalTokens": _tokens_used, "messageCount": 1},
                    "$set": {"lastUsedAt": datetime.now(timezone.utc).isoformat()}
                },
                upsert=True
            )

        # Excel generation
        _excel_file_id, _excel_preview, _is_excel_clarification = None, None, False
        if not _response_text.startswith("Error:"):
            try:
                _excel_client = anthropic.AsyncAnthropic(api_key=CLAUDE_API_KEY)
                _excel_file_id, _excel_preview, _response_text, _is_excel_clarification = await maybe_generate_excel(
                    db=db,
                    chat_id=chat_id,
                    project_id=project_id,
                    active_source_ids=active_source_ids,
                    message_content=message_data.content,
                    claude_client=_excel_client,
                    current_response_text=_response_text,
                    temp_file_path=temp_excel_path,
                )
            except Exception as e:
                logger.error(f"[stream] Excel service error: {e}")

        # Deduplicate citations
        _unique_citations = {}
        _used_sources = []
        for c in citations:
            key = c["sourceId"]
            if key not in _unique_citations:
                _unique_citations[key] = {
                    "sourceName": c["sourceName"],
                    "sourceId": c["sourceId"],
                    "sourceType": c.get("sourceType", "unknown"),
                    "chunks": []
                }
                _used_sources.append({
                    "sourceId": c["sourceId"],
                    "sourceName": c["sourceName"],
                    "sourceType": c.get("sourceType", "unknown")
                })
            _unique_citations[key]["chunks"].append({
                "index": c["chunkIndex"] + 1,
                "chunkId": c.get("chunkId", ""),
                "textFragment": c.get("textFragment", "")
            })
        _final_citations = list(_unique_citations.values()) if _unique_citations else None
        _final_used_sources = _used_sources if _used_sources else None

        # Save to semantic cache
        if question_embedding and not _from_cache and not _response_text.startswith("Error:"):
            await save_to_cache(
                db,
                question=message_data.content,
                answer=_response_text,
                project_id=project_id,
                embedding=question_embedding,
                user_id=current_user["id"],
                cache_context_hash=cache_context_hash,
                source_ids=active_source_ids,
                sources_used=_final_used_sources
            )

        # Save assistant message
        _assistant_msg_id = str(uuid.uuid4())
        _assistant_message = {
            "id": _assistant_msg_id,
            "chatId": chat_id,
            "role": "assistant",
            "content": _response_text,
            "citations": _final_citations,
            "usedSources": _final_used_sources,
            "autoIngestedUrls": [s["id"] for s in auto_ingested_sources] if auto_ingested_sources else None,
            "senderEmail": None,
            "senderName": "GPT",
            "fromCache": _from_cache,
            "cacheInfo": _cache_info,
            "web_sources": web_sources,
            "clarifying_question": _clarifying_question,
            "clarifying_options": _clarifying_options,
            "fetchedUrls": fetched_urls_list if fetched_urls_list else None,
            "excel_file_id": _excel_file_id,
            "excel_preview": _excel_preview,
            "is_excel_clarification": _is_excel_clarification,
            "agent_type": selected_agent_type,
            "agent_name": selected_agent["name"],
            "model_used": _model_used,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.messages.insert_one(_assistant_message)

        # Track source usage
        if _final_used_sources:
            for _src in _final_used_sources:
                await db.source_usage.update_one(
                    {"sourceId": _src["sourceId"]},
                    {
                        "$inc": {"usageCount": 1},
                        "$set": {
                            "lastUsedAt": datetime.now(timezone.utc).isoformat(),
                            "sourceName": _src["sourceName"]
                        },
                        "$push": {
                            "usageHistory": {
                                "$each": [{
                                    "userId": current_user["id"],
                                    "userEmail": current_user["email"],
                                    "chatId": chat_id,
                                    "messageId": _assistant_msg_id,
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }],
                                "$slice": -100
                            }
                        }
                    },
                    upsert=True
                )

        # Final metadata event
        _meta = {
            "user_message": {k: v for k, v in user_message.items() if k != "_id"},
            "assistant_message": {k: v for k, v in _assistant_message.items() if k != "_id"}
        }
        yield f"data: [META]{json.dumps(_meta, default=str)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


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

        claude_client = anthropic.AsyncAnthropic(api_key=CLAUDE_API_KEY)
        response = await claude_client.messages.create(
            model="claude-sonnet-4-6",
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
        claude_client = anthropic.AsyncAnthropic(api_key=CLAUDE_API_KEY)
        response = await claude_client.messages.create(
            model="claude-sonnet-4-6",
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


# ==================== TUTOR: FINISH LESSON ====================

@router.post("/chats/{chat_id}/tutor-summarize")
async def tutor_summarize(chat_id: str, current_user: dict = Depends(get_current_user)):
    """Summarize a Tutor chat into per-book progress notes ("Завершить урок").

    Idempotent and safe — no-ops for non-tutor chats or chats without enough
    content. Returns the list of book ids whose progress was updated.
    """
    from services.tutor import summarize_tutor_chat

    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    result = await summarize_tutor_chat(db, chat, current_user["id"])
    return {"success": True, **result}