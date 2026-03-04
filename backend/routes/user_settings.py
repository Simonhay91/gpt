"""User settings routes"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone

from models.schemas import UserPromptUpdate, UserPromptResponse
from middleware.auth import get_current_user
from db.connection import get_db

router = APIRouter(prefix="/api", tags=["user_settings"])


@router.get("/user/prompt", response_model=UserPromptResponse)
async def get_user_prompt(current_user: dict = Depends(get_current_user)):
    """Get the current user's custom GPT prompt"""
    db = get_db()
    user_prompt = await db.user_prompts.find_one({"userId": current_user["id"]}, {"_id": 0})
    
    if not user_prompt:
        return UserPromptResponse(
            userId=current_user["id"],
            customPrompt=None,
            updatedAt=datetime.now(timezone.utc).isoformat()
        )
    
    return UserPromptResponse(**user_prompt)


@router.put("/user/prompt", response_model=UserPromptResponse)
async def update_user_prompt(data: UserPromptUpdate, current_user: dict = Depends(get_current_user)):
    """Update the current user's custom GPT prompt"""
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    existing = await db.user_prompts.find_one({"userId": current_user["id"]})
    
    if existing:
        await db.user_prompts.update_one(
            {"userId": current_user["id"]},
            {"$set": {"customPrompt": data.customPrompt, "updatedAt": now}}
        )
    else:
        await db.user_prompts.insert_one({
            "userId": current_user["id"],
            "customPrompt": data.customPrompt,
            "updatedAt": now
        })
    
    return UserPromptResponse(
        userId=current_user["id"],
        customPrompt=data.customPrompt,
        updatedAt=now
    )


@router.put("/users/me/primary-department")
async def set_primary_department(
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    """Set user's primary department"""
    db = get_db()
    department_id = data.get("departmentId")
    
    if department_id:
        department = await db.departments.find_one({"id": department_id}, {"_id": 0})
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        
        user_depts = current_user.get("departments", [])
        if department_id not in user_depts:
            raise HTTPException(status_code=403, detail="You are not a member of this department")
    
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"primaryDepartmentId": department_id}}
    )
    
    return {"message": "Primary department updated", "primaryDepartmentId": department_id}


@router.get("/users/me/departments")
async def get_my_departments(current_user: dict = Depends(get_current_user)):
    """Get current user's departments with details"""
    db = get_db()
    user_dept_ids = current_user.get("departments", [])
    
    if not user_dept_ids:
        return []
    
    departments = await db.departments.find(
        {"id": {"$in": user_dept_ids}},
        {"_id": 0}
    ).to_list(100)
    
    for dept in departments:
        dept["isManager"] = current_user["id"] in dept.get("managers", [])
        dept["isPrimary"] = dept["id"] == current_user.get("primaryDepartmentId")
    
    return departments
