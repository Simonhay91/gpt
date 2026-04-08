"""Authentication routes"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from models.schemas import UserLogin, TokenResponse, UserResponse
from middleware.auth import (
    verify_password, 
    create_token, 
    is_admin, 
    get_current_user,
    hash_password
)
from db.connection import get_db

router = APIRouter(prefix="/api", tags=["auth"])


class ChangePasswordRequest(BaseModel):
    new_password: str


@router.post("/auth/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    db = get_db()
    user = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(user_data.password, user["passwordHash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user["id"], user["email"])
    
    return TokenResponse(
        token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            isAdmin=is_admin(user["email"]),
            createdAt=user["createdAt"],
            mustChangePassword=user.get("mustChangePassword", False)
        )
    )


@router.post("/auth/change-password")
async def change_password(data: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """Change password - required on first login if mustChangePassword is True"""
    db = get_db()
    
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    # Update password and remove mustChangePassword flag
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {
            "passwordHash": hash_password(data.new_password),
            "mustChangePassword": False
        }}
    )
    
    return {"message": "Password changed successfully"}


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        isAdmin=is_admin(current_user["email"]),
        createdAt=current_user["createdAt"],
        canEditGlobalSources=current_user.get("canEditGlobalSources", False),
        departments=current_user.get("departments", []),
        primaryDepartmentId=current_user.get("primaryDepartmentId"),
        mustChangePassword=current_user.get("mustChangePassword", False)
    )
