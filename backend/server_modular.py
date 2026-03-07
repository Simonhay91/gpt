"""
Planet Knowledge API - Modular Server
=====================================
This is the refactored, modular version of the server.
All business logic has been moved to separate route modules.
"""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Literal
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
import os
import jwt
import bcrypt
import uuid
import logging
import re
import hashlib
import numpy as np
import httpx
import aiofiles
from bs4 import BeautifulSoup
import PyPDF2
import io
from docx import Document
from PIL import Image
import pytesseract

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ==================== APP SETUP ====================
app = FastAPI(title="Planet Knowledge API")
api_router = APIRouter()
security = HTTPBearer()

# ==================== DATABASE ====================
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# ==================== CONSTANTS ====================
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
IMAGES_DIR = ROOT_DIR / "generated_images"
IMAGES_DIR.mkdir(exist_ok=True)

JWT_SECRET = os.environ.get('JWT_SECRET', 'shared-project-gpt-secret-key-2024')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
ADMIN_EMAIL_DOMAIN = "@admin.com"

MAX_FILE_SIZE = 50 * 1024 * 1024
CHUNK_SIZE = 1500
MAX_CONTEXT_CHARS = 10000
MAX_CHUNKS_PER_QUERY = 5
GLOBAL_PROJECT_ID = "__global__"
CACHE_SIMILARITY_THRESHOLD = 0.92
CACHE_TTL_DAYS = 30
IMAGE_RATE_LIMIT_PER_HOUR = 10

SUPPORTED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/plain": "txt",
    "text/markdown": "md",
    "text/csv": "csv",
    "application/csv": "csv",
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpg",
}

# ==================== PYDANTIC MODELS ====================
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    token: str
    user: dict

class ProjectCreate(BaseModel):
    name: str

class ChatCreate(BaseModel):
    name: Optional[str] = "New Chat"

class MessageCreate(BaseModel):
    content: str

class SourceResponse(BaseModel):
    id: str
    projectId: str
    kind: Literal["file", "url", "knowledge"]
    originalName: Optional[str] = None
    url: Optional[str] = None
    mimeType: Optional[str] = None
    sizeBytes: Optional[int] = None
    createdAt: str
    chunkCount: int

class PaginatedResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    pageSize: int
    totalPages: int

# ==================== AUTH HELPERS ====================
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_token(user_id: str, email: str) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    return jwt.encode({"sub": user_id, "email": email, "exp": expiration}, JWT_SECRET, algorithm=JWT_ALGORITHM)

def is_admin(email: str) -> bool:
    return email.endswith(ADMIN_EMAIL_DOMAIN)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ==================== PROJECT HELPERS ====================
async def verify_project_access(project_id: str, user_id: str):
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project["ownerId"] != user_id and user_id not in project.get("sharedWith", []):
        raise HTTPException(status_code=403, detail="Access denied")
    return project

# ==================== PAGINATION HELPER ====================
async def paginate(collection, query: dict, page: int = 1, page_size: int = 50, sort_field: str = "createdAt", sort_order: int = -1):
    """Generic pagination helper"""
    skip = (page - 1) * page_size
    total = await collection.count_documents(query)
    items = await collection.find(query, {"_id": 0}).sort(sort_field, sort_order).skip(skip).limit(page_size).to_list(page_size)
    total_pages = (total + page_size - 1) // page_size
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages
    }

# ==================== TEXT EXTRACTION ====================
def extract_text_from_pdf(content: bytes) -> str:
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
    return "\n".join([p.extract_text() or "" for p in pdf_reader.pages]).strip()

def extract_text_from_docx(content: bytes) -> str:
    doc = Document(io.BytesIO(content))
    return "\n\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def extract_text_from_txt(content: bytes) -> str:
    for enc in ['utf-8', 'utf-8-sig', 'cp1251', 'latin-1']:
        try:
            return content.decode(enc)
        except:
            continue
    return content.decode('utf-8', errors='replace')

def extract_text_from_image(content: bytes) -> str:
    try:
        pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
        image = Image.open(io.BytesIO(content))
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        text = pytesseract.image_to_string(image, lang='rus+eng').strip()
        return f"[Image OCR]\n{text}" if text else "[Image: No text detected]"
    except Exception as e:
        return f"[Image: OCR failed - {str(e)[:50]}]"

def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    for el in soup(['script', 'style', 'nav', 'footer', 'header']):
        el.decompose()
    return '\n\n'.join([line.strip() for line in soup.get_text(separator='\n').splitlines() if line.strip()])

def chunk_text(text: str, size: int = CHUNK_SIZE) -> List[str]:
    if not text:
        return []
    chunks, current = [], ""
    for para in text.split('\n\n'):
        if len(current) + len(para) + 2 <= size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current.strip())
            current = para if len(para) <= size else para[:size]
    if current:
        chunks.append(current.strip())
    return chunks

# ==================== IMPORT EXISTING ROUTES ====================
from services.enterprise import AuditService, VersionService, HierarchicalRetrieval
from routes.departments import setup_department_routes, router as departments_router
from routes.enterprise_sources import setup_enterprise_source_routes, router as enterprise_sources_router
from routes.news import router as news_router
from routes.analyzer import setup_analyzer_routes, router as analyzer_router
from routes.insights import setup_insights_routes, router as insights_router

# Initialize services
audit_service = AuditService(db)
version_service = VersionService(db)
hierarchical_retrieval = HierarchicalRetrieval(db)

# Text extraction wrapper for enterprise routes
async def extract_text_wrapper(content: bytes, file_type: str) -> str:
    if file_type == "pdf":
        return extract_text_from_pdf(content)
    elif file_type == "docx":
        return extract_text_from_docx(content)
    elif file_type in ["png", "jpeg", "jpg"]:
        return extract_text_from_image(content)
    else:
        return extract_text_from_txt(content)

# Setup routes with dependencies
setup_department_routes(db, get_current_user, is_admin, audit_service)
setup_enterprise_source_routes(db, get_current_user, is_admin, audit_service, version_service, extract_text_wrapper, chunk_text, chunk_text, UPLOAD_DIR, MAX_FILE_SIZE, SUPPORTED_MIME_TYPES)
setup_analyzer_routes(db, get_current_user)
setup_insights_routes(db, get_current_user)

# ==================== AUTH ROUTES ====================
@api_router.post("/auth/login")
async def login(data: UserLogin):
    user = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user or not verify_password(data.password, user["passwordHash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": create_token(user["id"], user["email"]), "user": {
        "id": user["id"], "email": user["email"], "isAdmin": is_admin(user["email"]),
        "createdAt": user["createdAt"], "canEditGlobalSources": user.get("canEditGlobalSources", False),
        "departments": user.get("departments", []), "primaryDepartmentId": user.get("primaryDepartmentId")
    }}

@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {"id": user["id"], "email": user["email"], "isAdmin": is_admin(user["email"]),
            "createdAt": user["createdAt"], "canEditGlobalSources": user.get("canEditGlobalSources", False),
            "departments": user.get("departments", []), "primaryDepartmentId": user.get("primaryDepartmentId")}

# ==================== PROJECTS WITH PAGINATION ====================
@api_router.get("/projects")
async def get_projects(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), user: dict = Depends(get_current_user)):
    query = {"$or": [{"ownerId": user["id"]}, {"sharedWith": user["id"]}]}
    return await paginate(db.projects, query, page, page_size)

@api_router.post("/projects")
async def create_project(data: ProjectCreate, user: dict = Depends(get_current_user)):
    project = {"id": str(uuid.uuid4()), "name": data.name, "ownerId": user["id"], "sharedWith": [], "createdAt": datetime.now(timezone.utc).isoformat()}
    await db.projects.insert_one(project)
    return {k: v for k, v in project.items() if k != "_id"}

@api_router.get("/projects/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    return await verify_project_access(project_id, user["id"])

@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    project = await db.projects.find_one({"id": project_id, "ownerId": user["id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Not found or not owner")
    await db.chats.delete_many({"projectId": project_id})
    await db.sources.delete_many({"projectId": project_id})
    await db.source_chunks.delete_many({"projectId": project_id})
    await db.projects.delete_one({"id": project_id})
    return {"message": "Deleted"}

# ==================== CHATS WITH PAGINATION ====================
@api_router.get("/quick-chats")
async def get_quick_chats(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), user: dict = Depends(get_current_user)):
    return await paginate(db.chats, {"ownerId": user["id"], "projectId": None}, page, page_size)

@api_router.post("/quick-chats")
async def create_quick_chat(data: ChatCreate, user: dict = Depends(get_current_user)):
    chat = {"id": str(uuid.uuid4()), "projectId": None, "ownerId": user["id"], "name": data.name or "Quick Chat",
            "activeSourceIds": [], "sourceMode": "all", "createdAt": datetime.now(timezone.utc).isoformat()}
    await db.chats.insert_one(chat)
    return {k: v for k, v in chat.items() if k != "_id"}

@api_router.get("/projects/{project_id}/chats")
async def get_project_chats(project_id: str, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), user: dict = Depends(get_current_user)):
    await verify_project_access(project_id, user["id"])
    return await paginate(db.chats, {"projectId": project_id}, page, page_size)

@api_router.post("/projects/{project_id}/chats")
async def create_chat(project_id: str, data: ChatCreate, user: dict = Depends(get_current_user)):
    await verify_project_access(project_id, user["id"])
    chat = {"id": str(uuid.uuid4()), "projectId": project_id, "name": data.name or "New Chat",
            "activeSourceIds": [], "sourceMode": "all", "createdAt": datetime.now(timezone.utc).isoformat()}
    await db.chats.insert_one(chat)
    return {k: v for k, v in chat.items() if k != "_id"}

@api_router.get("/chats/{chat_id}")
async def get_chat(chat_id: str, user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.get("projectId"):
        await verify_project_access(chat["projectId"], user["id"])
    elif chat.get("ownerId") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return chat

@api_router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.get("projectId"):
        await verify_project_access(chat["projectId"], user["id"])
    elif chat.get("ownerId") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.messages.delete_many({"chatId": chat_id})
    await db.chats.delete_one({"id": chat_id})
    return {"message": "Deleted"}

# ==================== SOURCES WITH PAGINATION ====================
@api_router.get("/projects/{project_id}/sources")
async def list_sources(project_id: str, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), user: dict = Depends(get_current_user)):
    await verify_project_access(project_id, user["id"])
    result = await paginate(db.sources, {"projectId": project_id}, page, page_size)
    # Add chunk counts
    for item in result["items"]:
        item["chunkCount"] = await db.source_chunks.count_documents({"sourceId": item["id"]})
    return result

# ==================== MESSAGES ====================
@api_router.get("/chats/{chat_id}/messages")
async def get_messages(chat_id: str, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=500), user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    if chat.get("projectId"):
        await verify_project_access(chat["projectId"], user["id"])
    elif chat.get("ownerId") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return await paginate(db.messages, {"chatId": chat_id}, page, page_size, "createdAt", 1)

# ==================== ADMIN ====================
@api_router.get("/admin/users")
async def list_users(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), user: dict = Depends(get_current_user)):
    if not is_admin(user["email"]):
        raise HTTPException(status_code=403, detail="Admin required")
    result = await paginate(db.users, {}, page, page_size)
    # Remove password hashes, add usage
    for item in result["items"]:
        item.pop("passwordHash", None)
        usage = await db.token_usage.find_one({"userId": item["id"]}, {"_id": 0})
        item["totalTokensUsed"] = usage.get("totalTokens", 0) if usage else 0
        item["isAdmin"] = is_admin(item["email"])
    return result

@api_router.post("/admin/users")
async def create_user(data: UserCreate, user: dict = Depends(get_current_user)):
    if not is_admin(user["email"]):
        raise HTTPException(status_code=403, detail="Admin required")
    if await db.users.find_one({"email": data.email}):
        raise HTTPException(status_code=400, detail="Email exists")
    new_user = {"id": str(uuid.uuid4()), "email": data.email, "passwordHash": hash_password(data.password),
                "createdAt": datetime.now(timezone.utc).isoformat(), "departments": [], "canEditGlobalSources": False}
    await db.users.insert_one(new_user)
    return {"id": new_user["id"], "email": new_user["email"], "isAdmin": is_admin(data.email), "createdAt": new_user["createdAt"]}

# ==================== GLOBAL SOURCES WITH PAGINATION ====================
@api_router.get("/global-sources")
async def get_global_sources(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), user: dict = Depends(get_current_user)):
    result = await paginate(db.sources, {"projectId": GLOBAL_PROJECT_ID}, page, page_size)
    return {"sources": result["items"], "canEdit": is_admin(user["email"]) or user.get("canEditGlobalSources", False), **{k: v for k, v in result.items() if k != "items"}}

# ==================== HEALTH ====================
@api_router.get("/")
async def root():
    return {"message": "Planet Knowledge API"}

@api_router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# ==================== INCLUDE ROUTERS ====================
app.include_router(api_router, prefix="/api")
app.include_router(departments_router)
app.include_router(enterprise_sources_router)
app.include_router(news_router, prefix="/api")
app.include_router(analyzer_router, prefix="/api")
app.include_router(insights_router)

# ==================== CORS ====================
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','), allow_methods=["*"], allow_headers=["*"])

# ==================== SHUTDOWN ====================
@app.on_event("shutdown")
async def shutdown():
    client.close()
