"""User settings routes"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone

from models.schemas import (
    UserPromptUpdate, 
    UserPromptResponse,
    AiProfileUpdate,
    AiProfileResponse,
    DepartmentAiContextUpdate,
    DepartmentAiContextResponse
)
from middleware.auth import get_current_user, is_admin
from db.connection import get_db
from services.enterprise import AuditService

router = APIRouter(prefix="/api", tags=["user_settings"])


@router.get("/user/prompt", response_model=UserPromptResponse)
async def get_user_prompt(current_user: dict = Depends(get_current_user)):
    """Get the current user's custom GPT prompt"""
    # db reference from get_current_user
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
    # db reference from get_current_user
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
    # db reference from get_current_user
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


# ==================== AI PROFILE ENDPOINTS ====================

@router.get("/users/me/ai-profile", response_model=AiProfileResponse)
async def get_ai_profile(current_user: dict = Depends(get_current_user)):
    """Get current user's AI profile settings"""
    # db reference from get_current_user
    ai_profile = current_user.get("ai_profile", {})
    
    return AiProfileResponse(
        display_name=ai_profile.get("display_name"),
        position=ai_profile.get("position"),
        department_id=ai_profile.get("department_id"),
        preferred_language=ai_profile.get("preferred_language", "ru"),
        response_style=ai_profile.get("response_style", "formal"),
        custom_instruction=ai_profile.get("custom_instruction")
    )


@router.put("/users/me/ai-profile", response_model=AiProfileResponse)
async def update_ai_profile(data: AiProfileUpdate, current_user: dict = Depends(get_current_user)):
    """Update current user's AI profile settings"""
    # db reference from get_current_user
    
    ai_profile_update = {}
    if data.display_name is not None:
        ai_profile_update["ai_profile.display_name"] = data.display_name
    if data.position is not None:
        ai_profile_update["ai_profile.position"] = data.position
    if data.department_id is not None:
        ai_profile_update["ai_profile.department_id"] = data.department_id
    if data.preferred_language is not None:
        ai_profile_update["ai_profile.preferred_language"] = data.preferred_language
    if data.response_style is not None:
        ai_profile_update["ai_profile.response_style"] = data.response_style
    if data.custom_instruction is not None:
        ai_profile_update["ai_profile.custom_instruction"] = data.custom_instruction
    
    if ai_profile_update:
        await db.users.update_one(
            {"id": current_user["id"]},
            {"$set": ai_profile_update}
        )
    
    updated_user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    ai_profile = updated_user.get("ai_profile", {})
    
    return AiProfileResponse(
        display_name=ai_profile.get("display_name"),
        position=ai_profile.get("position"),
        department_id=ai_profile.get("department_id"),
        preferred_language=ai_profile.get("preferred_language", "ru"),
        response_style=ai_profile.get("response_style", "formal"),
        custom_instruction=ai_profile.get("custom_instruction")
    )


# ==================== DEPARTMENT AI CONTEXT ENDPOINTS ====================

@router.get("/departments/{department_id}/ai-context", response_model=DepartmentAiContextResponse)
async def get_department_ai_context(department_id: str, current_user: dict = Depends(get_current_user)):
    """Get department's AI context settings"""
    # db reference from get_current_user
    
    department = await db.departments.find_one({"id": department_id}, {"_id": 0})
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Check access
    user_departments = current_user.get("departments", [])
    is_admin_user = is_admin(current_user["email"])
    
    if not is_admin_user and department_id not in user_departments:
        raise HTTPException(status_code=403, detail="Access denied")
    
    ai_context = department.get("ai_context", {})
    
    return DepartmentAiContextResponse(
        style=ai_context.get("style"),
        instruction=ai_context.get("instruction")
    )


@router.put("/departments/{department_id}/ai-context", response_model=DepartmentAiContextResponse)
async def update_department_ai_context(
    department_id: str,
    data: DepartmentAiContextUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update department's AI context settings (admin or manager only)"""
    # db reference from get_current_user
    
    department = await db.departments.find_one({"id": department_id}, {"_id": 0})
    if not department:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Check access - admin or manager
    is_admin_user = is_admin(current_user["email"])
    
    if not is_admin_user and not is_manager:
        raise HTTPException(status_code=403, detail="Only admin or department manager can update AI context")
    
    ai_context_update = department.get("ai_context", {})
    if data.style is not None:
        ai_context_update["style"] = data.style
    if data.instruction is not None:
        ai_context_update["instruction"] = data.instruction
    
    await db.departments.update_one(
        {"id": department_id},
        {"$set": {"ai_context": ai_context_update}}
    )
    
    # Log audit
    await AuditService.log_action(
        db=db,
        user_id=current_user["id"],
        action="update_department_ai_context",
        resource_type="department",
        resource_id=department_id,
        details={"ai_context": ai_context_update}
    )
    
    return DepartmentAiContextResponse(**ai_context_update)
