"""Chat routes"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from datetime import datetime, timezone
import logging
import uuid

from models.schemas import (
    ChatCreate, 
    ChatResponse, 
    QuickChatCreate,
    MoveChatRequest,
    RenameChatRequest,
    UpdateChatVisibilityRequest,
    SourceModeUpdate
)
from middleware.auth import get_current_user
from db.connection import get_db
from routes.projects import verify_project_ownership

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chats"])


async def _summarize_previous_tutor_chat(chat_id: str, user_id: str):
    """Background task: summarize a finished tutor chat into per-book progress."""
    try:
        from services.tutor import summarize_tutor_chat
        db = get_db()
        chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
        if chat:
            await summarize_tutor_chat(db, chat, user_id)
    except Exception as e:  # noqa: BLE001 - best-effort, never blocks
        logger.error(f"Tutor auto-summarize error for {chat_id}: {e}")


async def _tutor_auto_active_source_ids(db, current_user: dict) -> List[str]:
    """Sources auto-activated in a Tutor chat: Company Info + position books."""
    from services.rag import get_company_info_context
    from routes.messages import get_position_library_source_ids

    ids: List[str] = []
    ci = await get_company_info_context(db)
    if ci and ci.get("sourceId"):
        ids.append(ci["sourceId"])
    ids.extend(await get_position_library_source_ids(db, current_user))
    # Dedup, preserve order
    seen = set()
    return [x for x in ids if not (x in seen or seen.add(x))]


# ==================== QUICK CHATS ====================

@router.get("/quick-chats", response_model=List[ChatResponse])
async def get_quick_chats(
    mode: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Get quick chats (no project) for the current user.

    ``mode=tutor`` returns only Tutor chats; otherwise Tutor chats are excluded
    so they live in their own Tutor section.
    """
    db = get_db()
    query = {"ownerId": current_user["id"], "projectId": None}
    if mode == "tutor":
        query["mode"] = "tutor"
    else:
        query["mode"] = {"$ne": "tutor"}
    chats = await db.chats.find(query, {"_id": 0}).to_list(1000)
    return [ChatResponse(**{**c, "activeSourceIds": c.get("activeSourceIds")}) for c in chats]


@router.post("/quick-chats", response_model=ChatResponse)
async def create_quick_chat(
    chat_data: QuickChatCreate,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Create a quick chat. With ``mode=tutor`` it becomes a Tutor chat:
    sources are auto-activated (Company Info + position books) and the previous
    Tutor chat is summarized into learning memory in the background.
    """
    db = get_db()
    chat_id = str(uuid.uuid4())
    is_tutor = chat_data.mode == "tutor"

    active_source_ids = None
    if is_tutor:
        # Summarize the most recent earlier tutor chat (so progress carries over),
        # then auto-activate this user's company info + position books.
        prev = await db.chats.find(
            {"ownerId": current_user["id"], "projectId": None, "mode": "tutor"},
            {"_id": 0, "id": 1},
        ).sort("createdAt", -1).to_list(1)
        if prev:
            background_tasks.add_task(_summarize_previous_tutor_chat, prev[0]["id"], current_user["id"])
        active_source_ids = await _tutor_auto_active_source_ids(db, current_user)

    chat = {
        "id": chat_id,
        "projectId": None,
        "ownerId": current_user["id"],
        "name": chat_data.name or ("Урок" if is_tutor else "Quick Chat"),
        "activeSourceIds": active_source_ids,
        "sourceMode": "all",
        "mode": "tutor" if is_tutor else None,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.chats.insert_one(chat)
    return ChatResponse(**chat)


@router.post("/chats/{chat_id}/move", response_model=ChatResponse)
async def move_chat_to_project(chat_id: str, data: MoveChatRequest, current_user: dict = Depends(get_current_user)):
    """Move a quick chat to a project"""
    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if chat.get("projectId"):
        await verify_project_ownership(chat["projectId"], current_user["id"])
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await verify_project_ownership(data.targetProjectId, current_user["id"])
    
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"projectId": data.targetProjectId, "ownerId": None}}
    )
    
    updated_chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    return ChatResponse(**{**updated_chat, "activeSourceIds": updated_chat.get("activeSourceIds")})


@router.put("/chats/{chat_id}/rename", response_model=ChatResponse)
async def rename_chat(chat_id: str, data: RenameChatRequest, current_user: dict = Depends(get_current_user)):
    """Rename a chat"""
    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if chat.get("projectId"):
        await verify_project_ownership(chat["projectId"], current_user["id"])
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"name": data.name.strip()}}
    )
    
    updated_chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    return ChatResponse(**{**updated_chat, "activeSourceIds": updated_chat.get("activeSourceIds")})


# ==================== PROJECT CHATS ====================

@router.get("/projects/{project_id}/chats", response_model=List[ChatResponse])
async def get_chats(project_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    project = await verify_project_ownership(project_id, current_user["id"])
    
    chats = await db.chats.find({"projectId": project_id}, {"_id": 0}).to_list(1000)
    
    if project["ownerId"] == current_user["id"]:
        return [ChatResponse(**{**c, "activeSourceIds": c.get("activeSourceIds"), "sharedWithUsers": c.get("sharedWithUsers")}) for c in chats]
    
    visible_chats = []
    for c in chats:
        shared_with = c.get("sharedWithUsers")
        if shared_with is None or current_user["id"] in shared_with:
            visible_chats.append(ChatResponse(**{**c, "activeSourceIds": c.get("activeSourceIds"), "sharedWithUsers": shared_with}))
    
    return visible_chats


@router.post("/projects/{project_id}/chats", response_model=ChatResponse)
async def create_chat(project_id: str, chat_data: ChatCreate, current_user: dict = Depends(get_current_user)):
    db = get_db()
    await verify_project_ownership(project_id, current_user["id"])
    
    chat_id = str(uuid.uuid4())
    chat = {
        "id": chat_id,
        "projectId": project_id,
        "name": chat_data.name or "New Chat",
        "activeSourceIds": None,
        "sourceMode": "all",
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.chats.insert_one(chat)
    return ChatResponse(**chat)


@router.get("/chats/{chat_id}", response_model=ChatResponse)
async def get_chat(chat_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if chat.get("projectId"):
        await verify_project_ownership(chat["projectId"], current_user["id"])
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return ChatResponse(**{**chat, "activeSourceIds": chat.get("activeSourceIds"), "sharedWithUsers": chat.get("sharedWithUsers")})


@router.put("/chats/{chat_id}/visibility")
async def update_chat_visibility(chat_id: str, data: UpdateChatVisibilityRequest, current_user: dict = Depends(get_current_user)):
    """Update which shared users can see this chat (owner only)"""
    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if not chat.get("projectId"):
        raise HTTPException(status_code=400, detail="Quick chats cannot be shared")
    
    project = await db.projects.find_one({"id": chat["projectId"]}, {"_id": 0})
    if not project or project["ownerId"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Only project owner can change chat visibility")
    
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"sharedWithUsers": data.sharedWithUsers}}
    )
    
    updated_chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    return ChatResponse(**{**updated_chat, "activeSourceIds": updated_chat.get("activeSourceIds"), "sharedWithUsers": updated_chat.get("sharedWithUsers")})


@router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if chat.get("projectId"):
        await verify_project_ownership(chat["projectId"], current_user["id"])
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.messages.delete_many({"chatId": chat_id})
    await db.chats.delete_one({"id": chat_id})
    
    return {"message": "Chat deleted successfully"}


@router.put("/chats/{chat_id}/source-mode")
async def update_source_mode(chat_id: str, data: SourceModeUpdate, current_user: dict = Depends(get_current_user)):
    """Update source mode for a chat"""
    db = get_db()
    if data.sourceMode not in ['all', 'my', 'ai_only']:
        raise HTTPException(status_code=400, detail="Invalid source mode. Use 'all' or 'my'")
    
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if chat.get("projectId"):
        await verify_project_ownership(chat["projectId"], current_user["id"])
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"sourceMode": data.sourceMode}}
    )
    
    return {"message": "Source mode updated", "sourceMode": data.sourceMode}
