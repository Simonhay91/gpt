"""Authentication routes"""
from fastapi import APIRouter, Depends
from models.schemas import UserLogin, TokenResponse, UserResponse
from middleware.auth import (
    verify_password, 
    create_token, 
    is_admin, 
    get_current_user
)
from db.connection import get_db

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    db = get_db()
    user = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(user_data.password, user["passwordHash"]):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user["id"], user["email"])
    
    return TokenResponse(
        token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            isAdmin=is_admin(user["email"]),
            createdAt=user["createdAt"]
        )
    )


@router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        isAdmin=is_admin(current_user["email"]),
        createdAt=current_user["createdAt"],
        canEditGlobalSources=current_user.get("canEditGlobalSources", False),
        departments=current_user.get("departments", []),
        primaryDepartmentId=current_user.get("primaryDepartmentId")
    )
