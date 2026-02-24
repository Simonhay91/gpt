from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, UploadFile, File
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
import PyPDF2
import io
import aiofiles

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
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# File storage settings
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
CHUNK_SIZE = 1500  # characters per chunk
MAX_CONTEXT_CHARS = 15000  # Max characters to include in context

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
    activeFileIds: Optional[List[str]] = []

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

class ProjectFileResponse(BaseModel):
    id: str
    projectId: str
    originalName: str
    mimeType: str
    sizeBytes: int
    createdAt: str
    chunkCount: int

class ActiveFilesUpdate(BaseModel):
    fileIds: List[str]

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

def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF file content"""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"PDF extraction error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to extract text from PDF: {str(e)}")

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """Split text into chunks of approximately chunk_size characters"""
    if not text:
        return []
    
    chunks = []
    current_chunk = ""
    
    # Split by paragraphs first
    paragraphs = text.split('\n\n')
    
    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # If paragraph is longer than chunk_size, split it
            if len(para) > chunk_size:
                words = para.split()
                current_chunk = ""
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= chunk_size:
                        if current_chunk:
                            current_chunk += " " + word
                        else:
                            current_chunk = word
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = word
            else:
                current_chunk = para
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

async def verify_project_ownership(project_id: str, user_id: str):
    """Verify that the user owns the project"""
    project = await db.projects.find_one({"id": project_id, "ownerId": user_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

# ==================== AUTH ENDPOINTS ====================

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserCreate):
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": user_data.email,
        "passwordHash": hash_password(user_data.password),
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one(user)
    
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
    
    # Delete all files and chunks for this project
    files = await db.project_files.find({"projectId": project_id}).to_list(1000)
    for file in files:
        # Delete physical file
        file_path = UPLOAD_DIR / file.get("storagePath", "")
        if file_path.exists():
            file_path.unlink()
    await db.project_files.delete_many({"projectId": project_id})
    await db.project_file_chunks.delete_many({"projectId": project_id})
    
    # Delete project
    await db.projects.delete_one({"id": project_id})
    
    return {"message": "Project deleted successfully"}

# ==================== CHAT ENDPOINTS ====================

@api_router.get("/projects/{project_id}/chats", response_model=List[ChatResponse])
async def get_chats(project_id: str, current_user: dict = Depends(get_current_user)):
    await verify_project_ownership(project_id, current_user["id"])
    
    chats = await db.chats.find({"projectId": project_id}, {"_id": 0}).to_list(1000)
    return [ChatResponse(**{**c, "activeFileIds": c.get("activeFileIds", [])}) for c in chats]

@api_router.post("/projects/{project_id}/chats", response_model=ChatResponse)
async def create_chat(project_id: str, chat_data: ChatCreate, current_user: dict = Depends(get_current_user)):
    await verify_project_ownership(project_id, current_user["id"])
    
    chat_id = str(uuid.uuid4())
    chat = {
        "id": chat_id,
        "projectId": project_id,
        "name": chat_data.name or "New Chat",
        "activeFileIds": [],
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.chats.insert_one(chat)
    return ChatResponse(**chat)

@api_router.get("/chats/{chat_id}", response_model=ChatResponse)
async def get_chat(chat_id: str, current_user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    await verify_project_ownership(chat["projectId"], current_user["id"])
    return ChatResponse(**{**chat, "activeFileIds": chat.get("activeFileIds", [])})

@api_router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, current_user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    await verify_project_ownership(chat["projectId"], current_user["id"])
    
    await db.messages.delete_many({"chatId": chat_id})
    await db.chats.delete_one({"id": chat_id})
    
    return {"message": "Chat deleted successfully"}

# ==================== FILE ENDPOINTS ====================

@api_router.post("/projects/{project_id}/files", response_model=ProjectFileResponse)
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a PDF file to a project"""
    await verify_project_ownership(project_id, current_user["id"])
    
    # Validate file type
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Read file content
    content = await file.read()
    
    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File size exceeds maximum of {MAX_FILE_SIZE // (1024*1024)}MB")
    
    # Extract text from PDF
    extracted_text = extract_text_from_pdf(content)
    
    if not extracted_text or len(extracted_text.strip()) < 10:
        raise HTTPException(
            status_code=400, 
            detail="This PDF seems to be image-based or contains no extractable text. Please upload a text-based PDF."
        )
    
    # Generate file ID and storage path
    file_id = str(uuid.uuid4())
    storage_filename = f"{file_id}.pdf"
    storage_path = UPLOAD_DIR / storage_filename
    
    # Save file to disk
    async with aiofiles.open(storage_path, 'wb') as f:
        await f.write(content)
    
    # Create chunks
    chunks = chunk_text(extracted_text)
    
    # Save file metadata
    file_doc = {
        "id": file_id,
        "projectId": project_id,
        "originalName": file.filename,
        "mimeType": file.content_type,
        "sizeBytes": len(content),
        "storagePath": storage_filename,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.project_files.insert_one(file_doc)
    
    # Save chunks
    for i, chunk_content in enumerate(chunks):
        chunk_doc = {
            "id": str(uuid.uuid4()),
            "projectFileId": file_id,
            "projectId": project_id,
            "chunkIndex": i,
            "content": chunk_content,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.project_file_chunks.insert_one(chunk_doc)
    
    logger.info(f"Uploaded file {file.filename} with {len(chunks)} chunks for project {project_id}")
    
    return ProjectFileResponse(
        id=file_id,
        projectId=project_id,
        originalName=file.filename,
        mimeType=file.content_type,
        sizeBytes=len(content),
        createdAt=file_doc["createdAt"],
        chunkCount=len(chunks)
    )

@api_router.get("/projects/{project_id}/files", response_model=List[ProjectFileResponse])
async def list_files(project_id: str, current_user: dict = Depends(get_current_user)):
    """List all files in a project"""
    await verify_project_ownership(project_id, current_user["id"])
    
    files = await db.project_files.find({"projectId": project_id}, {"_id": 0}).to_list(1000)
    
    result = []
    for f in files:
        chunk_count = await db.project_file_chunks.count_documents({"projectFileId": f["id"]})
        result.append(ProjectFileResponse(
            id=f["id"],
            projectId=f["projectId"],
            originalName=f["originalName"],
            mimeType=f["mimeType"],
            sizeBytes=f["sizeBytes"],
            createdAt=f["createdAt"],
            chunkCount=chunk_count
        ))
    
    return result

@api_router.delete("/projects/{project_id}/files/{file_id}")
async def delete_file(project_id: str, file_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a file from a project"""
    await verify_project_ownership(project_id, current_user["id"])
    
    file = await db.project_files.find_one({"id": file_id, "projectId": project_id})
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete physical file
    file_path = UPLOAD_DIR / file.get("storagePath", "")
    if file_path.exists():
        file_path.unlink()
    
    # Delete chunks
    await db.project_file_chunks.delete_many({"projectFileId": file_id})
    
    # Delete file metadata
    await db.project_files.delete_one({"id": file_id})
    
    # Remove from active files in all chats
    await db.chats.update_many(
        {"projectId": project_id},
        {"$pull": {"activeFileIds": file_id}}
    )
    
    return {"message": "File deleted successfully"}

# ==================== ACTIVE FILES ENDPOINTS ====================

@api_router.post("/chats/{chat_id}/active-files")
async def set_active_files(chat_id: str, data: ActiveFilesUpdate, current_user: dict = Depends(get_current_user)):
    """Set the active files for a chat"""
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    project = await verify_project_ownership(chat["projectId"], current_user["id"])
    
    # Verify all file IDs belong to this project
    if data.fileIds:
        files = await db.project_files.find({
            "id": {"$in": data.fileIds},
            "projectId": chat["projectId"]
        }).to_list(1000)
        
        valid_ids = {f["id"] for f in files}
        invalid_ids = set(data.fileIds) - valid_ids
        
        if invalid_ids:
            raise HTTPException(status_code=400, detail=f"Invalid file IDs: {invalid_ids}")
    
    # Update chat with active file IDs
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"activeFileIds": data.fileIds}}
    )
    
    return {"message": "Active files updated", "activeFileIds": data.fileIds}

@api_router.get("/chats/{chat_id}/active-files")
async def get_active_files(chat_id: str, current_user: dict = Depends(get_current_user)):
    """Get the active files for a chat"""
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    await verify_project_ownership(chat["projectId"], current_user["id"])
    
    active_file_ids = chat.get("activeFileIds", [])
    
    if not active_file_ids:
        return {"activeFiles": []}
    
    files = await db.project_files.find({
        "id": {"$in": active_file_ids},
        "projectId": chat["projectId"]
    }, {"_id": 0}).to_list(1000)
    
    return {"activeFiles": files}

# ==================== MESSAGE ENDPOINTS ====================

@api_router.get("/chats/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(chat_id: str, current_user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    await verify_project_ownership(chat["projectId"], current_user["id"])
    
    messages = await db.messages.find({"chatId": chat_id}, {"_id": 0}).sort("createdAt", 1).to_list(1000)
    return [MessageResponse(**m) for m in messages]

@api_router.post("/chats/{chat_id}/messages", response_model=MessageResponse)
async def send_message(chat_id: str, message_data: MessageCreate, current_user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    project = await verify_project_ownership(chat["projectId"], current_user["id"])
    
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
    
    # Get active file chunks for context
    document_context = ""
    active_file_ids = chat.get("activeFileIds", [])
    
    if active_file_ids:
        # Get chunks ONLY from active files of THIS project (strict isolation)
        chunks = await db.project_file_chunks.find({
            "projectFileId": {"$in": active_file_ids},
            "projectId": chat["projectId"]  # Double-check project isolation
        }, {"_id": 0}).sort("chunkIndex", 1).to_list(1000)
        
        # Build context from chunks, respecting max context size
        context_parts = []
        total_chars = 0
        
        for chunk in chunks:
            if total_chars + len(chunk["content"]) > MAX_CONTEXT_CHARS:
                break
            context_parts.append(chunk["content"])
            total_chars += len(chunk["content"])
        
        if context_parts:
            document_context = "\n\n---\n\n".join(context_parts)
    
    # Prepare messages for OpenAI
    try:
        if not openai_client:
            raise Exception("OpenAI API key not configured")
        
        # Build messages array with developer prompt, document context, and chat history
        messages = [
            {"role": "developer", "content": config["developerPrompt"]}
        ]
        
        # Add document context if available
        if document_context:
            context_message = f"""PROJECT DOCUMENT CONTEXT:
The user has attached documents to this conversation. Use the following content to answer their questions when relevant:

{document_context}

---
END OF DOCUMENT CONTEXT
"""
            messages.append({"role": "system", "content": context_message})
        
        # Add chat history
        for msg in history[:-1]:  # Exclude the message we just added
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": message_data.content
        })
        
        # Call OpenAI Responses API
        response = openai_client.responses.create(
            model=config["model"],
            input=messages
        )
        
        response_text = response.output_text
        
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
