from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from openai import OpenAI

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Settings
JWT_SECRET = os.environ.get('JWT_SECRET', 'shared-project-gpt-secret-key-2024')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Admin email domain
ADMIN_EMAIL_DOMAIN = "@admin.com"

# OpenAI API Key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', os.environ.get('EMERGENT_LLM_KEY', ''))

# Create the main app
app = FastAPI(title="Shared Project GPT")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    isAdmin: bool
    createdAt: str

class TokenResponse(BaseModel):
    token: str
    user: UserResponse

class ProjectCreate(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: str
    name: str
    ownerId: str
    createdAt: str

class ChatCreate(BaseModel):
    name: Optional[str] = "New Chat"

class ChatResponse(BaseModel):
    id: str
    projectId: str
    name: str
    createdAt: str

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: str
    chatId: str
    role: Literal["user", "assistant"]
    content: str
    createdAt: str

class GPTConfigUpdate(BaseModel):
    model: Optional[str] = None
    developerPrompt: Optional[str] = None

class GPTConfigResponse(BaseModel):
    id: str
    model: str
    developerPrompt: str
    updatedAt: str

# ==================== HELPERS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str, email: str) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expiration
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_token(token)
    user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def is_admin(email: str) -> bool:
    return email.endswith(ADMIN_EMAIL_DOMAIN)

async def ensure_gpt_config():
    """Ensure GPT config singleton exists"""
    config = await db.gpt_config.find_one({"id": "1"}, {"_id": 0})
    if not config:
        config = {
            "id": "1",
            "model": "gpt-4.1-mini",
            "developerPrompt": "You are a helpful assistant. Be concise and clear in your responses.",
            "updatedAt": datetime.now(timezone.utc).isoformat()
        }
        await db.gpt_config.insert_one(config)
    return config

# ==================== AUTH ENDPOINTS ====================

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    # Check if user exists
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": user_data.email,
        "passwordHash": hash_password(user_data.password),
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user)
    
    # Generate token
    token = create_token(user_id, user_data.email)
    
    return TokenResponse(
        token=token,
        user=UserResponse(
            id=user_id,
            email=user_data.email,
            isAdmin=is_admin(user_data.email),
            createdAt=user["createdAt"]
        )
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
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
            createdAt=user["createdAt"]
        )
    )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        isAdmin=is_admin(current_user["email"]),
        createdAt=current_user["createdAt"]
    )

# ==================== PROJECT ENDPOINTS ====================

@api_router.get("/projects", response_model=List[ProjectResponse])
async def get_projects(current_user: dict = Depends(get_current_user)):
    projects = await db.projects.find(
        {"ownerId": current_user["id"]},
        {"_id": 0}
    ).to_list(1000)
    return [ProjectResponse(**p) for p in projects]

@api_router.post("/projects", response_model=ProjectResponse)
async def create_project(project_data: ProjectCreate, current_user: dict = Depends(get_current_user)):
    project_id = str(uuid.uuid4())
    project = {
        "id": project_id,
        "name": project_data.name,
        "ownerId": current_user["id"],
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.projects.insert_one(project)
    return ProjectResponse(**project)

@api_router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    project = await db.projects.find_one(
        {"id": project_id, "ownerId": current_user["id"]},
        {"_id": 0}
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(**project)

@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, current_user: dict = Depends(get_current_user)):
    project = await db.projects.find_one({"id": project_id, "ownerId": current_user["id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Delete all messages in all chats of this project
    chats = await db.chats.find({"projectId": project_id}).to_list(1000)
    chat_ids = [chat["id"] for chat in chats]
    if chat_ids:
        await db.messages.delete_many({"chatId": {"$in": chat_ids}})
    
    # Delete all chats
    await db.chats.delete_many({"projectId": project_id})
    
    # Delete project
    await db.projects.delete_one({"id": project_id})
    
    return {"message": "Project deleted successfully"}

# ==================== CHAT ENDPOINTS ====================

@api_router.get("/projects/{project_id}/chats", response_model=List[ChatResponse])
async def get_chats(project_id: str, current_user: dict = Depends(get_current_user)):
    # Verify project ownership
    project = await db.projects.find_one({"id": project_id, "ownerId": current_user["id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    chats = await db.chats.find({"projectId": project_id}, {"_id": 0}).to_list(1000)
    return [ChatResponse(**c) for c in chats]

@api_router.post("/projects/{project_id}/chats", response_model=ChatResponse)
async def create_chat(project_id: str, chat_data: ChatCreate, current_user: dict = Depends(get_current_user)):
    # Verify project ownership
    project = await db.projects.find_one({"id": project_id, "ownerId": current_user["id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    chat_id = str(uuid.uuid4())
    chat = {
        "id": chat_id,
        "projectId": project_id,
        "name": chat_data.name or "New Chat",
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.chats.insert_one(chat)
    return ChatResponse(**chat)

@api_router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, current_user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Verify project ownership
    project = await db.projects.find_one({"id": chat["projectId"], "ownerId": current_user["id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Delete all messages
    await db.messages.delete_many({"chatId": chat_id})
    
    # Delete chat
    await db.chats.delete_one({"id": chat_id})
    
    return {"message": "Chat deleted successfully"}

# ==================== MESSAGE ENDPOINTS ====================

@api_router.get("/chats/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(chat_id: str, current_user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Verify project ownership
    project = await db.projects.find_one({"id": chat["projectId"], "ownerId": current_user["id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    messages = await db.messages.find({"chatId": chat_id}, {"_id": 0}).sort("createdAt", 1).to_list(1000)
    return [MessageResponse(**m) for m in messages]

@api_router.post("/chats/{chat_id}/messages", response_model=MessageResponse)
async def send_message(chat_id: str, message_data: MessageCreate, current_user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Verify project ownership
    project = await db.projects.find_one({"id": chat["projectId"], "ownerId": current_user["id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Save user message
    user_msg_id = str(uuid.uuid4())
    user_message = {
        "id": user_msg_id,
        "chatId": chat_id,
        "role": "user",
        "content": message_data.content,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(user_message)
    
    # Get GPT config
    config = await ensure_gpt_config()
    
    # Get chat history
    history = await db.messages.find({"chatId": chat_id}, {"_id": 0}).sort("createdAt", 1).to_list(1000)
    
    # Prepare messages for OpenAI
    try:
        # Use emergentintegrations library
        llm_chat = LlmChat(
            api_key=OPENAI_API_KEY,
            session_id=f"chat-{chat_id}",
            system_message=config["developerPrompt"]
        ).with_model("openai", config["model"])
        
        # Build conversation history for context
        # The library manages history internally, but we need to pass our stored history
        # For simplicity, we'll send the full context in the user message
        context_messages = []
        for msg in history[:-1]:  # Exclude the message we just added
            context_messages.append(f"{msg['role'].upper()}: {msg['content']}")
        
        # Create user message with context
        full_context = "\n".join(context_messages) if context_messages else ""
        user_query = message_data.content
        if full_context:
            user_query = f"Previous conversation:\n{full_context}\n\nCurrent message: {message_data.content}"
        
        user_msg = UserMessage(text=user_query)
        
        # Get response
        response_text = await llm_chat.send_message(user_msg)
        
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        response_text = f"I apologize, but I encountered an error processing your request. Please try again later. (Error: {str(e)[:100]})"
    
    # Save assistant message
    assistant_msg_id = str(uuid.uuid4())
    assistant_message = {
        "id": assistant_msg_id,
        "chatId": chat_id,
        "role": "assistant",
        "content": response_text,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(assistant_message)
    
    return MessageResponse(**assistant_message)

# ==================== ADMIN ENDPOINTS ====================

@api_router.get("/admin/config", response_model=GPTConfigResponse)
async def get_gpt_config(current_user: dict = Depends(get_current_user)):
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    config = await ensure_gpt_config()
    return GPTConfigResponse(**config)

@api_router.put("/admin/config", response_model=GPTConfigResponse)
async def update_gpt_config(config_data: GPTConfigUpdate, current_user: dict = Depends(get_current_user)):
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    config = await ensure_gpt_config()
    
    update_data = {"updatedAt": datetime.now(timezone.utc).isoformat()}
    if config_data.model is not None:
        update_data["model"] = config_data.model
    if config_data.developerPrompt is not None:
        update_data["developerPrompt"] = config_data.developerPrompt
    
    await db.gpt_config.update_one({"id": "1"}, {"$set": update_data})
    
    updated_config = await db.gpt_config.find_one({"id": "1"}, {"_id": 0})
    return GPTConfigResponse(**updated_config)

# ==================== HEALTH CHECK ====================

@api_router.get("/")
async def root():
    return {"message": "Shared Project GPT API is running"}

@api_router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
