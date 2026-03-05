"""Project routes"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime, timezone
import uuid

from models.schemas import (
    ProjectCreate, 
    ProjectResponse, 
    ShareProjectRequest,
    ProjectMember
)
from middleware.auth import get_current_user
from db.connection import get_db

router = APIRouter(prefix="/api", tags=["projects"])


# ==================== PERMISSION HELPERS ====================

async def get_user_project_role(user_id: str, project: dict) -> Optional[str]:
    """Get user's role in a project. Returns None if no access."""
    if project["ownerId"] == user_id:
        return "owner"
    
    shared_members = project.get("sharedMembers", [])
    for member in shared_members:
        if member.get("userId") == user_id:
            return member.get("role", "viewer")
    
    if user_id in project.get("sharedWith", []):
        return "viewer"
    
    return None


async def check_project_access(user: dict, project_id: str, required_role: str = "viewer") -> dict:
    """Check if user has access to project with required role."""
    db = get_db()
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    role = await get_user_project_role(user["id"], project)
    
    if role is None:
        raise HTTPException(status_code=403, detail="Access denied to this project")
    
    role_levels = {"owner": 4, "manager": 3, "editor": 2, "viewer": 1}
    user_level = role_levels.get(role, 0)
    required_level = role_levels.get(required_role, 1)
    
    if user_level < required_level:
        raise HTTPException(
            status_code=403, 
            detail=f"Insufficient permissions. Required: {required_role}, Your role: {role}"
        )
    
    return {"project": project, "role": role}


async def verify_project_ownership(project_id: str, user_id: str):
    """Verify that the user owns or has access to the project"""
    db = get_db()
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    shared_with = project.get("sharedWith", [])
    if project["ownerId"] != user_id and user_id not in shared_with:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    
    return project


async def verify_project_access(project_id: str, user_id: str):
    """Verify user has access to project (owner or shared)"""
    db = get_db()
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    shared_with = project.get("sharedWith", [])
    if project["ownerId"] != user_id and user_id not in shared_with:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    
    return project


def can_manage_sources(role: str) -> bool:
    return role in ["owner", "manager"]


def can_edit_chats(role: str) -> bool:
    return role in ["owner", "manager", "editor"]


def can_manage_members(role: str) -> bool:
    return role in ["owner", "manager"]


async def get_user_accessible_project_ids(user_id: str) -> List[str]:
    """Get list of all project IDs user has access to"""
    db = get_db()
    owned = await db.projects.find({"ownerId": user_id}, {"id": 1, "_id": 0}).to_list(1000)
    shared_old = await db.projects.find({"sharedWith": user_id}, {"id": 1, "_id": 0}).to_list(1000)
    shared_new = await db.projects.find({"sharedMembers.userId": user_id}, {"id": 1, "_id": 0}).to_list(1000)
    
    all_ids = set()
    for p in owned + shared_old + shared_new:
        all_ids.add(p["id"])
    
    return list(all_ids)


# ==================== PROJECT ENDPOINTS ====================

@router.get("/projects", response_model=List[ProjectResponse])
async def get_projects(current_user: dict = Depends(get_current_user)):
    db = get_db()
    projects = await db.projects.find(
        {"$or": [
            {"ownerId": current_user["id"]},
            {"sharedWith": current_user["id"]}
        ]},
        {"_id": 0}
    ).to_list(1000)
    return [ProjectResponse(**{**p, "sharedWith": p.get("sharedWith", [])}) for p in projects]


@router.post("/projects", response_model=ProjectResponse)
async def create_project(project_data: ProjectCreate, current_user: dict = Depends(get_current_user)):
    db = get_db()
    project_id = str(uuid.uuid4())
    project = {
        "id": project_id,
        "name": project_data.name,
        "ownerId": current_user["id"],
        "sharedWith": [],
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.projects.insert_one(project)
    return ProjectResponse(**project)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    project = await verify_project_access(project_id, current_user["id"])
    return ProjectResponse(**{**project, "sharedWith": project.get("sharedWith", [])})


@router.post("/projects/{project_id}/share")
async def share_project(project_id: str, data: ShareProjectRequest, current_user: dict = Depends(get_current_user)):
    """Share project with another user by email with specified role"""
    db = get_db()
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    role = await get_user_project_role(current_user["id"], project)
    if not can_manage_members(role) and role != "owner":
        raise HTTPException(status_code=403, detail="Only owner or manager can share project")
    
    user_to_share = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user_to_share:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_to_share["id"] == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot share with yourself")
    
    if user_to_share["id"] == project["ownerId"]:
        raise HTTPException(status_code=400, detail="Cannot change owner's role")
    
    valid_roles = ["viewer", "editor", "manager"]
    share_role = data.role if data.role in valid_roles else "viewer"
    
    if share_role == "manager" and role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can grant manager role")
    
    shared_members = project.get("sharedMembers", [])
    shared_members = [m for m in shared_members if m.get("userId") != user_to_share["id"]]
    shared_members.append({
        "userId": user_to_share["id"],
        "email": user_to_share["email"],
        "role": share_role
    })
    
    shared_with = project.get("sharedWith", [])
    if user_to_share["id"] not in shared_with:
        shared_with.append(user_to_share["id"])
    
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"sharedWith": shared_with, "sharedMembers": shared_members}}
    )
    
    return {"message": f"Project shared with {data.email} as {share_role}", "sharedMembers": shared_members}


@router.put("/projects/{project_id}/members/{user_id}/role")
async def update_member_role(
    project_id: str, 
    user_id: str, 
    role: str,
    current_user: dict = Depends(get_current_user)
):
    """Update a member's role in the project"""
    db = get_db()
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project["ownerId"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Only owner can change member roles")
    
    if user_id == project["ownerId"]:
        raise HTTPException(status_code=400, detail="Cannot change owner's role")
    
    valid_roles = ["viewer", "editor", "manager"]
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Valid: {valid_roles}")
    
    shared_members = project.get("sharedMembers", [])
    updated = False
    for member in shared_members:
        if member.get("userId") == user_id:
            member["role"] = role
            updated = True
            break
    
    if not updated:
        raise HTTPException(status_code=404, detail="Member not found in project")
    
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"sharedMembers": shared_members}}
    )
    
    return {"message": f"Role updated to {role}", "sharedMembers": shared_members}


@router.delete("/projects/{project_id}/share/{user_id}")
async def unshare_project(project_id: str, user_id: str, current_user: dict = Depends(get_current_user)):
    """Remove user from shared project"""
    db = get_db()
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    role = await get_user_project_role(current_user["id"], project)
    if not can_manage_members(role) and role != "owner":
        raise HTTPException(status_code=403, detail="Only owner or manager can remove members")
    
    target_role = await get_user_project_role(user_id, project)
    if role == "manager" and target_role == "manager":
        raise HTTPException(status_code=403, detail="Managers cannot remove other managers")
    
    shared_with = project.get("sharedWith", [])
    if user_id in shared_with:
        shared_with.remove(user_id)
    
    shared_members = project.get("sharedMembers", [])
    shared_members = [m for m in shared_members if m.get("userId") != user_id]
    
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"sharedWith": shared_with, "sharedMembers": shared_members}}
    )
    
    return {"message": "User removed from project", "sharedMembers": shared_members}


@router.get("/projects/{project_id}/members")
async def get_project_members(project_id: str, current_user: dict = Depends(get_current_user)):
    """Get all members of a project with their roles"""
    db = get_db()
    project = await verify_project_access(project_id, current_user["id"])
    
    members = []
    
    owner = await db.users.find_one({"id": project["ownerId"]}, {"_id": 0, "passwordHash": 0})
    if owner:
        members.append({"id": owner["id"], "email": owner["email"], "role": "owner"})
    
    shared_members = project.get("sharedMembers", [])
    seen_user_ids = set()
    
    for member in shared_members:
        user_id = member.get("userId")
        if user_id and user_id not in seen_user_ids:
            seen_user_ids.add(user_id)
            members.append({
                "id": user_id,
                "email": member.get("email", ""),
                "role": member.get("role", "viewer")
            })
    
    for user_id in project.get("sharedWith", []):
        if user_id not in seen_user_ids:
            user = await db.users.find_one({"id": user_id}, {"_id": 0, "passwordHash": 0})
            if user:
                members.append({"id": user["id"], "email": user["email"], "role": "viewer"})
                seen_user_ids.add(user_id)
    
    return members


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    project = await db.projects.find_one({"id": project_id, "ownerId": current_user["id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or not owner")
    
    from pathlib import Path
    UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
    
    chats = await db.chats.find({"projectId": project_id}).to_list(1000)
    chat_ids = [chat["id"] for chat in chats]
    if chat_ids:
        await db.messages.delete_many({"chatId": {"$in": chat_ids}})
    
    await db.chats.delete_many({"projectId": project_id})
    
    sources = await db.sources.find({"projectId": project_id}).to_list(1000)
    for source in sources:
        if source.get("storagePath"):
            file_path = UPLOAD_DIR / source["storagePath"]
            if file_path.exists():
                file_path.unlink()
    await db.sources.delete_many({"projectId": project_id})
    await db.source_chunks.delete_many({"projectId": project_id})
    
    await db.projects.delete_one({"id": project_id})
    
    return {"message": "Project deleted successfully"}
