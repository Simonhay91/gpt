from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from openai import OpenAI
import PyPDF2
import io
import aiofiles
import httpx
from bs4 import BeautifulSoup
from docx import Document

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
IMAGES_DIR = ROOT_DIR / "generated_images"
IMAGES_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
CHUNK_SIZE = 1500  # characters per chunk
MAX_CONTEXT_CHARS = 15000  # Max characters to include in context
MAX_CHUNKS_PER_QUERY = 10  # Max chunks to include per query
MAX_AUTO_INGEST_URLS = 3  # Max URLs to auto-ingest per message

# Image generation settings
IMAGE_RATE_LIMIT_PER_HOUR = 10  # Max images per user per hour
VALID_IMAGE_SIZES = ["1024x1024", "1024x1792", "1792x1024"]

# URL pattern for detecting URLs in messages
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE)

# Supported MIME types
SUPPORTED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "md",
}

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

class UserWithUsageResponse(BaseModel):
    id: str
    email: str
    isAdmin: bool
    createdAt: str
    totalTokensUsed: int
    totalMessagesCount: int

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
    projectId: Optional[str] = None  # None for quick chats
    name: str
    createdAt: str
    activeSourceIds: Optional[List[str]] = []

class QuickChatCreate(BaseModel):
    name: Optional[str] = "Quick Chat"

class MoveChatRequest(BaseModel):
    targetProjectId: str

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: str
    chatId: str
    role: Literal["user", "assistant"]
    content: str
    createdAt: str
    citations: Optional[List[dict]] = None
    usedSources: Optional[List[dict]] = None  # For UI to reliably show "Sources used"
    autoIngestedUrls: Optional[List[str]] = None  # IDs of auto-ingested URL sources

class GPTConfigUpdate(BaseModel):
    model: Optional[str] = None
    developerPrompt: Optional[str] = None

class GPTConfigResponse(BaseModel):
    id: str
    model: str
    developerPrompt: str
    updatedAt: str

class SourceResponse(BaseModel):
    id: str
    projectId: str
    kind: Literal["file", "url"]
    originalName: Optional[str] = None
    url: Optional[str] = None
    mimeType: Optional[str] = None
    sizeBytes: Optional[int] = None
    createdAt: str
    chunkCount: int

class ActiveSourcesUpdate(BaseModel):
    sourceIds: List[str]

class UrlSourceCreate(BaseModel):
    url: str

class UserPromptUpdate(BaseModel):
    customPrompt: Optional[str] = None

class UserPromptResponse(BaseModel):
    userId: str
    customPrompt: Optional[str] = None
    updatedAt: str

class ImageGenerateRequest(BaseModel):
    prompt: str
    size: Optional[str] = "1024x1024"

class GeneratedImageResponse(BaseModel):
    id: str
    projectId: str
    prompt: str
    imagePath: str
    imageUrl: str
    size: str
    createdAt: str

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
    """Ensure GPT config singleton exists with strict active sources rules"""
    config = await db.gpt_config.find_one({"id": "1"}, {"_id": 0})
    default_prompt = """You are a helpful assistant that answers questions based on provided source documents.

ATTACHMENTS / ACTIVE SOURCES RULES (critical):
- The chat may have multiple attached sources (files/URLs) but only some are marked as ACTIVE for this chat.
- Always check and use ONLY the ACTIVE sources provided in PROJECT SOURCE CONTEXT.
- If the user asks about an attachment but no ACTIVE source text is present, respond:
  1) Ask the user to activate/select the relevant file/URL in the "Active Sources" panel, OR re-upload it.
  2) State exactly what you are missing (e.g., "No active PDF/DOCX/URL text was provided.").
- Never assume you have read an attachment unless its content is included in the PROJECT SOURCE CONTEXT.
- If multiple active sources exist, briefly list which ones you used ("Used: <source1>, <source2>").
- If the question requires a specific document, ask which file/URL to use instead of guessing.

RESPONSE STYLE:
- Keep responses concise and engineer-friendly: steps, checks, configs, and clear next actions.
- Do not fabricate facts. Only use information from the provided context.
- When answering, cite your sources by referencing the source name and chunk numbers.
- Format citations as [Source: filename, Chunk N] or [Source: URL, Chunk N]."""
    
    if not config:
        config = {
            "id": "1",
            "model": "gpt-4.1-mini",
            "developerPrompt": default_prompt,
            "updatedAt": datetime.now(timezone.utc).isoformat()
        }
        await db.gpt_config.insert_one(config)
    else:
        # Update existing config with new prompt if it's the old one
        if "ATTACHMENTS / ACTIVE SOURCES RULES" not in config.get("developerPrompt", ""):
            await db.gpt_config.update_one(
                {"id": "1"},
                {"$set": {"developerPrompt": default_prompt, "updatedAt": datetime.now(timezone.utc).isoformat()}}
            )
            config["developerPrompt"] = default_prompt
    return config

async def verify_project_ownership(project_id: str, user_id: str):
    """Verify that the user owns the project"""
    project = await db.projects.find_one({"id": project_id, "ownerId": user_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

# ==================== TEXT EXTRACTION ====================

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

def extract_text_from_docx(file_content: bytes) -> str:
    """Extract text from DOCX file content"""
    try:
        doc = Document(io.BytesIO(file_content))
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.error(f"DOCX extraction error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to extract text from DOCX: {str(e)}")

def extract_text_from_txt(file_content: bytes) -> str:
    """Extract text from TXT/MD file content"""
    try:
        return file_content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            return file_content.decode('latin-1')
        except Exception as e:
            logger.error(f"TXT extraction error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Failed to read text file: {str(e)}")

def extract_text_from_html(html_content: str) -> str:
    """Extract readable text from HTML content"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
        
        # Get text
        text = soup.get_text(separator='\n')
        
        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        
        return '\n\n'.join(lines)
    except Exception as e:
        logger.error(f"HTML extraction error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to extract text from URL: {str(e)}")

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

def score_chunk_relevance(chunk_content: str, query: str) -> float:
    """Score chunk relevance using simple keyword overlap"""
    # Tokenize query and chunk
    query_words = set(re.findall(r'\w+', query.lower()))
    chunk_words = set(re.findall(r'\w+', chunk_content.lower()))
    
    if not query_words:
        return 0.0
    
    # Calculate overlap
    overlap = len(query_words & chunk_words)
    return overlap / len(query_words)

async def get_relevant_chunks(source_ids: List[str], project_id: str, query: str) -> List[dict]:
    """Get most relevant chunks from active sources using keyword ranking"""
    if not source_ids:
        return []
    
    # Get all chunks from active sources (strict project isolation)
    all_chunks = await db.source_chunks.find({
        "sourceId": {"$in": source_ids},
        "projectId": project_id  # Double-check project isolation
    }, {"_id": 0}).to_list(10000)
    
    if not all_chunks:
        return []
    
    # Score each chunk
    scored_chunks = []
    for chunk in all_chunks:
        score = score_chunk_relevance(chunk["content"], query)
        scored_chunks.append({**chunk, "score": score})
    
    # Sort by score descending
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    
    # Select top chunks up to MAX_CHUNKS_PER_QUERY, respecting MAX_CONTEXT_CHARS
    selected_chunks = []
    total_chars = 0
    
    for chunk in scored_chunks[:MAX_CHUNKS_PER_QUERY * 2]:  # Consider more for character limit
        if len(selected_chunks) >= MAX_CHUNKS_PER_QUERY:
            break
        if total_chars + len(chunk["content"]) > MAX_CONTEXT_CHARS:
            continue
        selected_chunks.append(chunk)
        total_chars += len(chunk["content"])
    
    return selected_chunks

def extract_urls_from_text(text: str) -> List[str]:
    """Extract unique URLs from text"""
    urls = URL_PATTERN.findall(text)
    # Clean URLs (remove trailing punctuation)
    cleaned = []
    for url in urls:
        # Remove trailing punctuation that might have been captured
        url = url.rstrip('.,;:!?)]}"\'')
        if url and url not in cleaned:
            cleaned.append(url)
    return cleaned[:MAX_AUTO_INGEST_URLS]  # Limit number of auto-ingested URLs

async def auto_ingest_url(url: str, project_id: str) -> Optional[dict]:
    """
    Auto-ingest a URL: fetch, extract text, chunk, and store.
    Returns the source document or None if failed.
    """
    try:
        # Check if URL already exists in this project
        existing = await db.sources.find_one({
            "url": url,
            "projectId": project_id
        })
        
        if existing:
            logger.info(f"URL already ingested: {url}")
            return existing
        
        # Fetch URL content
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as http_client:
            response = await http_client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        if 'text/html' not in content_type and 'text/plain' not in content_type:
            logger.warning(f"URL {url} returned non-text content: {content_type}")
            return None
        
        # Extract text from HTML
        html_content = response.text
        extracted_text = extract_text_from_html(html_content)
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            logger.warning(f"Could not extract text from URL: {url}")
            return None
        
        # Generate source ID
        source_id = str(uuid.uuid4())
        
        # Create chunks
        chunks = chunk_text(extracted_text)
        
        # Extract domain for display name
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        display_name = f"{parsed_url.netloc}{parsed_url.path[:50]}"
        
        # Save source metadata
        source_doc = {
            "id": source_id,
            "projectId": project_id,
            "kind": "url",
            "originalName": display_name,
            "url": url,
            "mimeType": "text/html",
            "sizeBytes": len(html_content.encode('utf-8')),
            "storagePath": None,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.sources.insert_one(source_doc)
        
        # Save chunks
        for i, chunk_content in enumerate(chunks):
            chunk_doc = {
                "id": str(uuid.uuid4()),
                "sourceId": source_id,
                "projectId": project_id,
                "chunkIndex": i,
                "content": chunk_content,
                "createdAt": datetime.now(timezone.utc).isoformat()
            }
            await db.source_chunks.insert_one(chunk_doc)
        
        logger.info(f"Auto-ingested URL {url} with {len(chunks)} chunks for project {project_id}")
        return source_doc
        
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching URL: {url}")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error fetching URL {url}: {e.response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error auto-ingesting URL {url}: {str(e)}")
        return None

# ==================== AUTH ENDPOINTS ====================

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
    
    # Delete all sources and chunks for this project
    sources = await db.sources.find({"projectId": project_id}).to_list(1000)
    for source in sources:
        if source.get("storagePath"):
            file_path = UPLOAD_DIR / source["storagePath"]
            if file_path.exists():
                file_path.unlink()
    await db.sources.delete_many({"projectId": project_id})
    await db.source_chunks.delete_many({"projectId": project_id})
    
    # Delete project
    await db.projects.delete_one({"id": project_id})
    
    return {"message": "Project deleted successfully"}

# ==================== CHAT ENDPOINTS ====================

# --- Quick Chats (no project) ---

@api_router.get("/quick-chats", response_model=List[ChatResponse])
async def get_quick_chats(current_user: dict = Depends(get_current_user)):
    """Get all quick chats (chats without a project) for the current user"""
    chats = await db.chats.find({
        "ownerId": current_user["id"],
        "projectId": None
    }, {"_id": 0}).to_list(1000)
    return [ChatResponse(**{**c, "activeSourceIds": c.get("activeSourceIds", [])}) for c in chats]

@api_router.post("/quick-chats", response_model=ChatResponse)
async def create_quick_chat(chat_data: QuickChatCreate, current_user: dict = Depends(get_current_user)):
    """Create a quick chat without a project"""
    chat_id = str(uuid.uuid4())
    chat = {
        "id": chat_id,
        "projectId": None,
        "ownerId": current_user["id"],
        "name": chat_data.name or "Quick Chat",
        "activeSourceIds": [],
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.chats.insert_one(chat)
    return ChatResponse(**chat)

@api_router.post("/chats/{chat_id}/move", response_model=ChatResponse)
async def move_chat_to_project(chat_id: str, data: MoveChatRequest, current_user: dict = Depends(get_current_user)):
    """Move a quick chat to a project"""
    # Get the chat
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Verify ownership - check both ownerId (for quick chats) and projectId (for project chats)
    if chat.get("projectId"):
        await verify_project_ownership(chat["projectId"], current_user["id"])
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Verify target project ownership
    await verify_project_ownership(data.targetProjectId, current_user["id"])
    
    # Update the chat
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"projectId": data.targetProjectId, "ownerId": None}}
    )
    
    updated_chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    return ChatResponse(**{**updated_chat, "activeSourceIds": updated_chat.get("activeSourceIds", [])})

# --- Project Chats ---

@api_router.get("/projects/{project_id}/chats", response_model=List[ChatResponse])
async def get_chats(project_id: str, current_user: dict = Depends(get_current_user)):
    await verify_project_ownership(project_id, current_user["id"])
    
    chats = await db.chats.find({"projectId": project_id}, {"_id": 0}).to_list(1000)
    return [ChatResponse(**{**c, "activeSourceIds": c.get("activeSourceIds", [])}) for c in chats]

@api_router.post("/projects/{project_id}/chats", response_model=ChatResponse)
async def create_chat(project_id: str, chat_data: ChatCreate, current_user: dict = Depends(get_current_user)):
    await verify_project_ownership(project_id, current_user["id"])
    
    chat_id = str(uuid.uuid4())
    chat = {
        "id": chat_id,
        "projectId": project_id,
        "name": chat_data.name or "New Chat",
        "activeSourceIds": [],
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.chats.insert_one(chat)
    return ChatResponse(**chat)

@api_router.get("/chats/{chat_id}", response_model=ChatResponse)
async def get_chat(chat_id: str, current_user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Verify ownership - for quick chats check ownerId, for project chats check project ownership
    if chat.get("projectId"):
        await verify_project_ownership(chat["projectId"], current_user["id"])
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return ChatResponse(**{**chat, "activeSourceIds": chat.get("activeSourceIds", [])})

@api_router.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, current_user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Verify ownership - for quick chats check ownerId, for project chats check project ownership
    if chat.get("projectId"):
        await verify_project_ownership(chat["projectId"], current_user["id"])
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.messages.delete_many({"chatId": chat_id})
    await db.chats.delete_one({"id": chat_id})
    
    return {"message": "Chat deleted successfully"}
    
    return {"message": "Chat deleted successfully"}

# ==================== SOURCE ENDPOINTS (FILES + URLS) ====================

@api_router.post("/projects/{project_id}/sources/upload", response_model=SourceResponse)
async def upload_source(
    project_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload a file source (PDF, DOCX, TXT, MD) to a project"""
    await verify_project_ownership(project_id, current_user["id"])
    
    # Validate file type
    if file.content_type not in SUPPORTED_MIME_TYPES:
        raise HTTPException(
            status_code=400, 
            detail="Unsupported file type. Supported: PDF, DOCX, TXT, MD"
        )
    
    # Read file content
    content = await file.read()
    
    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File size exceeds maximum of {MAX_FILE_SIZE // (1024*1024)}MB")
    
    # Extract text based on file type
    file_type = SUPPORTED_MIME_TYPES[file.content_type]
    
    if file_type == "pdf":
        extracted_text = extract_text_from_pdf(content)
    elif file_type == "docx":
        extracted_text = extract_text_from_docx(content)
    else:  # txt or md
        extracted_text = extract_text_from_txt(content)
    
    if not extracted_text or len(extracted_text.strip()) < 10:
        raise HTTPException(
            status_code=400, 
            detail="This file appears to be empty or contains no extractable text. For PDFs, please ensure it's text-based, not image-based/scanned."
        )
    
    # Generate source ID and storage path
    source_id = str(uuid.uuid4())
    storage_filename = f"{source_id}.{file_type}"
    storage_path = UPLOAD_DIR / storage_filename
    
    # Save file to disk
    async with aiofiles.open(storage_path, 'wb') as f:
        await f.write(content)
    
    # Create chunks
    chunks = chunk_text(extracted_text)
    
    # Save source metadata
    source_doc = {
        "id": source_id,
        "projectId": project_id,
        "kind": "file",
        "originalName": file.filename,
        "url": None,
        "mimeType": file.content_type,
        "sizeBytes": len(content),
        "storagePath": storage_filename,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.sources.insert_one(source_doc)
    
    # Save chunks
    for i, chunk_content in enumerate(chunks):
        chunk_doc = {
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "projectId": project_id,
            "chunkIndex": i,
            "content": chunk_content,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.source_chunks.insert_one(chunk_doc)
    
    logger.info(f"Uploaded file {file.filename} with {len(chunks)} chunks for project {project_id}")
    
    return SourceResponse(
        id=source_id,
        projectId=project_id,
        kind="file",
        originalName=file.filename,
        url=None,
        mimeType=file.content_type,
        sizeBytes=len(content),
        createdAt=source_doc["createdAt"],
        chunkCount=len(chunks)
    )

@api_router.post("/projects/{project_id}/sources/url", response_model=SourceResponse)
async def add_url_source(
    project_id: str,
    data: UrlSourceCreate,
    current_user: dict = Depends(get_current_user)
):
    """Add a URL source to a project"""
    await verify_project_ownership(project_id, current_user["id"])
    
    url = data.url.strip()
    
    # Validate URL format
    if not url.startswith(('http://', 'https://')):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    
    # Fetch URL content
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as http_client:
            response = await http_client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            response.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="URL fetch timed out")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"URL returned error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)[:100]}")
    
    # Check content type
    content_type = response.headers.get('content-type', '')
    if 'text/html' not in content_type and 'text/plain' not in content_type:
        raise HTTPException(status_code=400, detail="URL must return HTML or text content")
    
    # Extract text from HTML
    html_content = response.text
    extracted_text = extract_text_from_html(html_content)
    
    if not extracted_text or len(extracted_text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Could not extract meaningful text from this URL")
    
    # Generate source ID
    source_id = str(uuid.uuid4())
    
    # Create chunks
    chunks = chunk_text(extracted_text)
    
    # Extract domain for display name
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    display_name = f"{parsed_url.netloc}{parsed_url.path[:50]}"
    
    # Save source metadata
    source_doc = {
        "id": source_id,
        "projectId": project_id,
        "kind": "url",
        "originalName": display_name,
        "url": url,
        "mimeType": "text/html",
        "sizeBytes": len(html_content.encode('utf-8')),
        "storagePath": None,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.sources.insert_one(source_doc)
    
    # Save chunks
    for i, chunk_content in enumerate(chunks):
        chunk_doc = {
            "id": str(uuid.uuid4()),
            "sourceId": source_id,
            "projectId": project_id,
            "chunkIndex": i,
            "content": chunk_content,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.source_chunks.insert_one(chunk_doc)
    
    logger.info(f"Added URL {url} with {len(chunks)} chunks for project {project_id}")
    
    return SourceResponse(
        id=source_id,
        projectId=project_id,
        kind="url",
        originalName=display_name,
        url=url,
        mimeType="text/html",
        sizeBytes=source_doc["sizeBytes"],
        createdAt=source_doc["createdAt"],
        chunkCount=len(chunks)
    )

@api_router.get("/projects/{project_id}/sources", response_model=List[SourceResponse])
async def list_sources(project_id: str, current_user: dict = Depends(get_current_user)):
    """List all sources in a project"""
    await verify_project_ownership(project_id, current_user["id"])
    
    sources = await db.sources.find({"projectId": project_id}, {"_id": 0}).to_list(1000)
    
    result = []
    for s in sources:
        chunk_count = await db.source_chunks.count_documents({"sourceId": s["id"]})
        result.append(SourceResponse(
            id=s["id"],
            projectId=s["projectId"],
            kind=s["kind"],
            originalName=s.get("originalName"),
            url=s.get("url"),
            mimeType=s.get("mimeType"),
            sizeBytes=s.get("sizeBytes"),
            createdAt=s["createdAt"],
            chunkCount=chunk_count
        ))
    
    return result

@api_router.delete("/projects/{project_id}/sources/{source_id}")
async def delete_source(project_id: str, source_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a source from a project"""
    await verify_project_ownership(project_id, current_user["id"])
    
    source = await db.sources.find_one({"id": source_id, "projectId": project_id})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Delete physical file if exists
    if source.get("storagePath"):
        file_path = UPLOAD_DIR / source["storagePath"]
        if file_path.exists():
            file_path.unlink()
    
    # Delete chunks
    await db.source_chunks.delete_many({"sourceId": source_id})
    
    # Delete source metadata
    await db.sources.delete_one({"id": source_id})
    
    # Remove from active sources in all chats
    await db.chats.update_many(
        {"projectId": project_id},
        {"$pull": {"activeSourceIds": source_id}}
    )
    
    return {"message": "Source deleted successfully"}

# ==================== IMAGE GENERATION ENDPOINTS ====================

async def check_image_rate_limit(user_id: str) -> bool:
    """Check if user has exceeded image generation rate limit"""
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    
    count = await db.generated_images.count_documents({
        "userId": user_id,
        "createdAt": {"$gte": one_hour_ago}
    })
    
    return count < IMAGE_RATE_LIMIT_PER_HOUR

@api_router.post("/projects/{project_id}/generate-image", response_model=GeneratedImageResponse)
async def generate_image(
    project_id: str,
    request: ImageGenerateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Generate an AI image using OpenAI's gpt-image-1 model"""
    await verify_project_ownership(project_id, current_user["id"])
    
    # Validate prompt
    if not request.prompt or len(request.prompt.strip()) < 3:
        raise HTTPException(status_code=400, detail="Prompt must be at least 3 characters")
    
    if len(request.prompt) > 4000:
        raise HTTPException(status_code=400, detail="Prompt must be less than 4000 characters")
    
    # Validate size
    size = request.size or "1024x1024"
    if size not in VALID_IMAGE_SIZES:
        raise HTTPException(status_code=400, detail=f"Invalid size. Valid options: {VALID_IMAGE_SIZES}")
    
    # Check rate limit
    if not await check_image_rate_limit(current_user["id"]):
        raise HTTPException(
            status_code=429, 
            detail=f"Rate limit exceeded. Maximum {IMAGE_RATE_LIMIT_PER_HOUR} images per hour."
        )
    
    # Check OpenAI client
    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    try:
        logger.info(f"Generating image for project {project_id}: {request.prompt[:50]}...")
        
        # Call OpenAI Images API
        response = openai_client.images.generate(
            model="gpt-image-1",
            prompt=request.prompt,
            size=size,
            n=1
        )
        
        # Get base64 image data
        image_data = response.data[0]
        
        # Handle both b64_json and url response formats
        if hasattr(image_data, 'b64_json') and image_data.b64_json:
            import base64
            image_bytes = base64.b64decode(image_data.b64_json)
        elif hasattr(image_data, 'url') and image_data.url:
            # Fetch image from URL
            async with httpx.AsyncClient(timeout=60.0, verify=False) as http_client:
                img_response = await http_client.get(image_data.url)
                image_bytes = img_response.content
        else:
            raise HTTPException(status_code=500, detail="No image data returned from OpenAI")
        
        # Generate unique filename
        image_id = str(uuid.uuid4())
        image_filename = f"{image_id}.png"
        image_path = IMAGES_DIR / image_filename
        
        # Save image to disk
        async with aiofiles.open(image_path, 'wb') as f:
            await f.write(image_bytes)
        
        # Save metadata to DB
        image_doc = {
            "id": image_id,
            "projectId": project_id,
            "userId": current_user["id"],
            "prompt": request.prompt,
            "imagePath": image_filename,
            "size": size,
            "createdAt": datetime.now(timezone.utc).isoformat()
        }
        await db.generated_images.insert_one(image_doc)
        
        logger.info(f"Generated image {image_id} for project {project_id}")
        
        return GeneratedImageResponse(
            id=image_id,
            projectId=project_id,
            prompt=request.prompt,
            imagePath=image_filename,
            imageUrl=f"/api/images/{image_id}",
            size=size,
            createdAt=image_doc["createdAt"]
        )
        
    except Exception as e:
        logger.error(f"Image generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate image: {str(e)[:100]}")

@api_router.get("/images/{image_id}")
async def get_image(image_id: str, current_user: dict = Depends(get_current_user)):
    """Get a generated image by ID"""
    image = await db.generated_images.find_one({"id": image_id}, {"_id": 0})
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Verify user owns the project
    await verify_project_ownership(image["projectId"], current_user["id"])
    
    image_path = IMAGES_DIR / image["imagePath"]
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=image_path,
        media_type="image/png",
        filename=f"generated_{image_id}.png"
    )

@api_router.get("/projects/{project_id}/images", response_model=List[GeneratedImageResponse])
async def list_project_images(project_id: str, current_user: dict = Depends(get_current_user)):
    """List all generated images in a project"""
    await verify_project_ownership(project_id, current_user["id"])
    
    images = await db.generated_images.find(
        {"projectId": project_id},
        {"_id": 0}
    ).sort("createdAt", -1).to_list(100)
    
    return [
        GeneratedImageResponse(
            id=img["id"],
            projectId=img["projectId"],
            prompt=img["prompt"],
            imagePath=img["imagePath"],
            imageUrl=f"/api/images/{img['id']}",
            size=img.get("size", "1024x1024"),
            createdAt=img["createdAt"]
        )
        for img in images
    ]

@api_router.delete("/projects/{project_id}/images/{image_id}")
async def delete_image(project_id: str, image_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a generated image"""
    await verify_project_ownership(project_id, current_user["id"])
    
    image = await db.generated_images.find_one({"id": image_id, "projectId": project_id})
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Delete physical file
    image_path = IMAGES_DIR / image["imagePath"]
    if image_path.exists():
        image_path.unlink()
    
    # Delete metadata
    await db.generated_images.delete_one({"id": image_id})
    
    return {"message": "Image deleted successfully"}

# ==================== ACTIVE SOURCES ENDPOINTS ====================

@api_router.post("/chats/{chat_id}/active-sources")
async def set_active_sources(chat_id: str, data: ActiveSourcesUpdate, current_user: dict = Depends(get_current_user)):
    """Set the active sources for a chat"""
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    await verify_project_ownership(chat["projectId"], current_user["id"])
    
    # Verify all source IDs belong to this project
    if data.sourceIds:
        sources = await db.sources.find({
            "id": {"$in": data.sourceIds},
            "projectId": chat["projectId"]
        }).to_list(1000)
        
        valid_ids = {s["id"] for s in sources}
        invalid_ids = set(data.sourceIds) - valid_ids
        
        if invalid_ids:
            raise HTTPException(status_code=400, detail=f"Invalid source IDs: {invalid_ids}")
    
    # Update chat with active source IDs
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"activeSourceIds": data.sourceIds}}
    )
    
    return {"message": "Active sources updated", "activeSourceIds": data.sourceIds}

@api_router.get("/chats/{chat_id}/active-sources")
async def get_active_sources(chat_id: str, current_user: dict = Depends(get_current_user)):
    """Get the active sources for a chat"""
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    await verify_project_ownership(chat["projectId"], current_user["id"])
    
    active_source_ids = chat.get("activeSourceIds", [])
    
    if not active_source_ids:
        return {"activeSources": []}
    
    sources = await db.sources.find({
        "id": {"$in": active_source_ids},
        "projectId": chat["projectId"]
    }, {"_id": 0}).to_list(1000)
    
    return {"activeSources": sources}

# ==================== MESSAGE ENDPOINTS ====================

@api_router.get("/chats/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(chat_id: str, current_user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Verify ownership - for quick chats check ownerId, for project chats check project ownership
    if chat.get("projectId"):
        await verify_project_ownership(chat["projectId"], current_user["id"])
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    messages = await db.messages.find({"chatId": chat_id}, {"_id": 0}).sort("createdAt", 1).to_list(1000)
    return [MessageResponse(**{
        **m, 
        "citations": m.get("citations"), 
        "usedSources": m.get("usedSources"),
        "autoIngestedUrls": m.get("autoIngestedUrls")
    }) for m in messages]

@api_router.post("/chats/{chat_id}/messages", response_model=MessageResponse)
async def send_message(chat_id: str, message_data: MessageCreate, current_user: dict = Depends(get_current_user)):
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Verify ownership - for quick chats check ownerId, for project chats check project ownership
    project_id = chat.get("projectId")
    if project_id:
        await verify_project_ownership(project_id, current_user["id"])
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this chat")
    
    # === AUTO-INGEST URLs from message (only for project chats) ===
    detected_urls = extract_urls_from_text(message_data.content)
    auto_ingested_sources = []
    auto_ingest_notes = []
    
    if detected_urls and project_id:
        logger.info(f"Detected {len(detected_urls)} URL(s) in message: {detected_urls}")
        
        for url in detected_urls:
            source = await auto_ingest_url(url, project_id)
            if source:
                auto_ingested_sources.append(source)
                auto_ingest_notes.append(f"Auto-ingested: {source.get('originalName', url)}")
            else:
                auto_ingest_notes.append(f"Could not fetch: {url}")
    
    # Auto-activate newly ingested sources for this chat
    active_source_ids = list(chat.get("activeSourceIds", []))
    newly_activated = []
    
    for source in auto_ingested_sources:
        if source["id"] not in active_source_ids:
            active_source_ids.append(source["id"])
            newly_activated.append(source.get("originalName") or source.get("url"))
    
    # Update chat with new active sources if any were added
    if newly_activated:
        await db.chats.update_one(
            {"id": chat_id},
            {"$set": {"activeSourceIds": active_source_ids}}
        )
        logger.info(f"Auto-activated {len(newly_activated)} source(s) for chat {chat_id}")
    
    # Save user message
    user_msg_id = str(uuid.uuid4())
    user_message = {
        "id": user_msg_id,
        "chatId": chat_id,
        "role": "user",
        "content": message_data.content,
        "citations": None,
        "autoIngestedUrls": [s["id"] for s in auto_ingested_sources] if auto_ingested_sources else None,
        "createdAt": datetime.now(timezone.utc).isoformat()
    }
    await db.messages.insert_one(user_message)
    
    # Get GPT config
    config = await ensure_gpt_config()
    
    # Get chat history
    history = await db.messages.find({"chatId": chat_id}, {"_id": 0}).sort("createdAt", 1).to_list(1000)
    
    # Get active sources and relevant chunks (including newly ingested)
    citations = []
    document_context = ""
    active_source_names = []
    
    if active_source_ids:
        # Get source names first
        sources = await db.sources.find({
            "id": {"$in": active_source_ids},
            "projectId": project_id
        }, {"_id": 0}).to_list(1000)
        
        source_names = {}
        for s in sources:
            name = s.get("originalName") or s.get("url") or "Unknown"
            source_names[s["id"]] = name
            active_source_names.append(name)
        
        # Get relevant chunks using keyword ranking
        relevant_chunks = await get_relevant_chunks(
            active_source_ids, 
            project_id, 
            message_data.content
        )
        
        if relevant_chunks:
            # Build context and track citations
            context_parts = []
            
            # Build context with chunk markers
            for chunk in relevant_chunks:
                source_name = source_names.get(chunk["sourceId"], "Unknown")
                chunk_marker = f"[Source: {source_name}, Chunk {chunk['chunkIndex']+1}]"
                context_parts.append(f"{chunk_marker}\n{chunk['content']}")
                
                # Track citation
                citations.append({
                    "sourceName": source_name,
                    "sourceId": chunk["sourceId"],
                    "chunkIndex": chunk["chunkIndex"],
                    "score": chunk.get("score", 0)
                })
            
            document_context = "\n\n---\n\n".join(context_parts)
    
    # Get user's custom prompt
    user_prompt_doc = await db.user_prompts.find_one({"userId": current_user["id"]}, {"_id": 0})
    user_custom_prompt = user_prompt_doc.get("customPrompt") if user_prompt_doc else None
    
    # Prepare messages for OpenAI
    try:
        if not openai_client:
            raise Exception("OpenAI API key not configured")
        
        # Build messages array with developer prompt, user custom prompt, document context, and chat history
        messages = [
            {"role": "developer", "content": config["developerPrompt"]}
        ]
        
        # Add user's custom prompt if exists
        if user_custom_prompt:
            messages.append({"role": "system", "content": f"USER CUSTOM INSTRUCTIONS:\n{user_custom_prompt}"})
        
        # Add document context if available
        if document_context:
            active_sources_list = ", ".join(active_source_names) if active_source_names else "None"
            context_message = f"""PROJECT SOURCE CONTEXT:
ACTIVE SOURCES FOR THIS CHAT: {active_sources_list}

The following content is from user-uploaded documents and URLs that are ACTIVE for this chat. Use this as your primary source of truth.

{document_context}

---
END OF SOURCE CONTEXT
"""
            messages.append({"role": "system", "content": context_message})
        else:
            # No context available - inform the model
            context_message = """PROJECT SOURCE CONTEXT:
No active sources are currently selected for this chat, OR no relevant content was found in the active sources.

If the user asks about a document/file/URL:
1. Ask them to upload the file or add the URL in the Sources panel
2. Remind them to check/select the source in the "Active Sources" checkboxes
3. State clearly: "No active source content is available for this query."
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
        citations = []
    
    # Deduplicate citations by source
    unique_citations = {}
    used_sources = []
    for c in citations:
        key = c["sourceId"]
        if key not in unique_citations:
            unique_citations[key] = {
                "sourceName": c["sourceName"],
                "sourceId": c["sourceId"],
                "chunks": []
            }
            used_sources.append({
                "sourceId": c["sourceId"],
                "sourceName": c["sourceName"]
            })
        unique_citations[key]["chunks"].append(c["chunkIndex"] + 1)
    
    final_citations = list(unique_citations.values()) if unique_citations else None
    final_used_sources = used_sources if used_sources else None
    
    # Save assistant message
    assistant_msg_id = str(uuid.uuid4())
    assistant_message = {
        "id": assistant_msg_id,
        "chatId": chat_id,
        "role": "assistant",
        "content": response_text,
        "citations": final_citations,
        "usedSources": final_used_sources,
        "autoIngestedUrls": [s["id"] for s in auto_ingested_sources] if auto_ingested_sources else None,
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
    
    await ensure_gpt_config()
    
    update_data = {"updatedAt": datetime.now(timezone.utc).isoformat()}
    if config_data.model is not None:
        update_data["model"] = config_data.model
    if config_data.developerPrompt is not None:
        update_data["developerPrompt"] = config_data.developerPrompt
    
    await db.gpt_config.update_one({"id": "1"}, {"$set": update_data})
    
    updated_config = await db.gpt_config.find_one({"id": "1"}, {"_id": 0})
    return GPTConfigResponse(**updated_config)

# ==================== USER PROMPT ENDPOINTS ====================

@api_router.get("/user/prompt", response_model=UserPromptResponse)
async def get_user_prompt(current_user: dict = Depends(get_current_user)):
    """Get the current user's custom GPT prompt"""
    user_prompt = await db.user_prompts.find_one({"userId": current_user["id"]}, {"_id": 0})
    
    if not user_prompt:
        return UserPromptResponse(
            userId=current_user["id"],
            customPrompt=None,
            updatedAt=datetime.now(timezone.utc).isoformat()
        )
    
    return UserPromptResponse(**user_prompt)

@api_router.put("/user/prompt", response_model=UserPromptResponse)
async def update_user_prompt(data: UserPromptUpdate, current_user: dict = Depends(get_current_user)):
    """Update the current user's custom GPT prompt"""
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
