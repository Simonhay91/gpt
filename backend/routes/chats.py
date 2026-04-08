"""Chat routes"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime, timezone
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

router = APIRouter(prefix="/api", tags=["chats"])


# ==================== QUICK CHATS ====================

@router.get("/quick-chats", response_model=List[ChatResponse])
async def get_quick_chats(current_user: dict = Depends(get_current_user)):
    """Get all quick chats (chats without a project) for the current user"""
    db = get_db()
    chats = await db.chats.find({
        "ownerId": current_user["id"],
        "projectId": None
    }, {"_id": 0}).to_list(1000)
    return [ChatResponse(**{**c, "activeSourceIds": c.get("activeSourceIds", [])}) for c in chats]


@router.post("/quick-chats", response_model=ChatResponse)
async def create_quick_chat(chat_data: QuickChatCreate, current_user: dict = Depends(get_current_user)):
    """Create a quick chat without a project"""
    db = get_db()
    chat_id = str(uuid.uuid4())
    chat = {
        "id": chat_id,
        "projectId": None,
        "ownerId": current_user["id"],
        "name": chat_data.name or "Quick Chat",
        "activeSourceIds": [],
        "sourceMode": "all",
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
    return ChatResponse(**{**updated_chat, "activeSourceIds": updated_chat.get("activeSourceIds", [])})


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
    return ChatResponse(**{**updated_chat, "activeSourceIds": updated_chat.get("activeSourceIds", [])})


# ==================== PROJECT CHATS ====================

@router.get("/projects/{project_id}/chats", response_model=List[ChatResponse])
async def get_chats(project_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    project = await verify_project_ownership(project_id, current_user["id"])
    
    chats = await db.chats.find({"projectId": project_id}, {"_id": 0}).to_list(1000)
    
    if project["ownerId"] == current_user["id"]:
        return [ChatResponse(**{**c, "activeSourceIds": c.get("activeSourceIds", []), "sharedWithUsers": c.get("sharedWithUsers")}) for c in chats]
    
    visible_chats = []
    for c in chats:
        shared_with = c.get("sharedWithUsers")
        if shared_with is None or current_user["id"] in shared_with:
            visible_chats.append(ChatResponse(**{**c, "activeSourceIds": c.get("activeSourceIds", []), "sharedWithUsers": shared_with}))
    
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
        "activeSourceIds": [],
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
    
    return ChatResponse(**{**chat, "activeSourceIds": chat.get("activeSourceIds", []), "sharedWithUsers": chat.get("sharedWithUsers")})


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
    return ChatResponse(**{**updated_chat, "activeSourceIds": updated_chat.get("activeSourceIds", []), "sharedWithUsers": updated_chat.get("sharedWithUsers")})


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
