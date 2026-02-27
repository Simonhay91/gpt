from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse, StreamingResponse
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
import pytesseract
from PIL import Image

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
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/plain": "txt",
    "text/markdown": "md",
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpg",
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
    sharedWith: Optional[List[str]] = []
    createdAt: str

class ShareProjectRequest(BaseModel):
    email: str

class ChatCreate(BaseModel):
    name: Optional[str] = "New Chat"

class ChatResponse(BaseModel):
    id: str
    projectId: Optional[str] = None  # None for quick chats
    name: str
    createdAt: str
    activeSourceIds: Optional[List[str]] = []
    sharedWithUsers: Optional[List[str]] = None  # None = visible to all shared users, [] or [ids] = only those users

class QuickChatCreate(BaseModel):
    name: Optional[str] = "Quick Chat"

class MoveChatRequest(BaseModel):
    targetProjectId: str

class RenameChatRequest(BaseModel):
    name: str

class UpdateChatVisibilityRequest(BaseModel):
    sharedWithUsers: List[str]  # List of user IDs who can see this chat

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
    senderEmail: Optional[str] = None  # Email of user who sent the message
    senderName: Optional[str] = None  # Display name of sender

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
    """Verify that the user owns or has access to the project"""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check if owner or shared with
    shared_with = project.get("sharedWith", [])
    if project["ownerId"] != user_id and user_id not in shared_with:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    
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

def extract_text_from_pptx(file_content: bytes) -> str:
    """Extract text from PowerPoint file content"""
    try:
        from pptx import Presentation
        from io import BytesIO
        
        prs = Presentation(BytesIO(file_content))
        text_parts = []
        
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_text = [f"[Slide {slide_num}]"]
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_text.append(shape.text.strip())
            if len(slide_text) > 1:
                text_parts.append("\n".join(slide_text))
        
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"PPTX extraction error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to extract text from PowerPoint: {str(e)}")

def extract_text_from_xlsx(file_content: bytes) -> str:
    """Extract text from Excel file content"""
    try:
        from openpyxl import load_workbook
        from io import BytesIO
        
        wb = load_workbook(BytesIO(file_content), data_only=True)
        text_parts = []
        
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            sheet_text = [f"[Sheet: {sheet_name}]"]
            
            for row in sheet.iter_rows(values_only=True):
                row_values = [str(cell) if cell is not None else "" for cell in row]
                if any(row_values):
                    sheet_text.append(" | ".join(row_values))
            
            if len(sheet_text) > 1:
                text_parts.append("\n".join(sheet_text))
        
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"XLSX extraction error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to extract text from Excel: {str(e)}")

def extract_text_from_image(file_content: bytes) -> str:
    """Extract text from image using OCR (pytesseract)"""
    try:
        # Set tesseract path explicitly
        pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
        
        # Open image with PIL
        image = Image.open(io.BytesIO(file_content))
        
        # Convert to RGB if necessary (for PNG with transparency)
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        # Run OCR with Russian and English languages
        text = pytesseract.image_to_string(image, lang='rus+eng')
        
        # Clean up the text
        text = text.strip()
        
        if not text:
            return "[Image: No text detected]"
        
        return f"[Image OCR Content]\n{text}"
    except Exception as e:
        logger.error(f"Image OCR error: {str(e)}")
        return f"[Image: OCR failed - {str(e)[:50]}]"

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

async def verify_project_access(project_id: str, user_id: str):
    """Verify user has access to project (owner or shared)"""
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    shared_with = project.get("sharedWith", [])
    if project["ownerId"] != user_id and user_id not in shared_with:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    
    return project

@api_router.get("/projects", response_model=List[ProjectResponse])
async def get_projects(current_user: dict = Depends(get_current_user)):
    # Get owned projects and shared projects
    projects = await db.projects.find(
        {"$or": [
            {"ownerId": current_user["id"]},
            {"sharedWith": current_user["id"]}
        ]},
        {"_id": 0}
    ).to_list(1000)
    return [ProjectResponse(**{**p, "sharedWith": p.get("sharedWith", [])}) for p in projects]

@api_router.post("/projects", response_model=ProjectResponse)
async def create_project(project_data: ProjectCreate, current_user: dict = Depends(get_current_user)):
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

@api_router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    project = await verify_project_access(project_id, current_user["id"])
    return ProjectResponse(**{**project, "sharedWith": project.get("sharedWith", [])})

@api_router.post("/projects/{project_id}/share")
async def share_project(project_id: str, data: ShareProjectRequest, current_user: dict = Depends(get_current_user)):
    """Share project with another user by email"""
    project = await db.projects.find_one({"id": project_id, "ownerId": current_user["id"]}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or not owner")
    
    # Find user by email
    user_to_share = await db.users.find_one({"email": data.email}, {"_id": 0})
    if not user_to_share:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_to_share["id"] == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot share with yourself")
    
    # Add to sharedWith if not already
    shared_with = project.get("sharedWith", [])
    if user_to_share["id"] not in shared_with:
        shared_with.append(user_to_share["id"])
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"sharedWith": shared_with}}
        )
    
    return {"message": f"Project shared with {data.email}", "sharedWith": shared_with}

@api_router.delete("/projects/{project_id}/share/{user_id}")
async def unshare_project(project_id: str, user_id: str, current_user: dict = Depends(get_current_user)):
    """Remove user from shared project"""
    project = await db.projects.find_one({"id": project_id, "ownerId": current_user["id"]}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or not owner")
    
    shared_with = project.get("sharedWith", [])
    if user_id in shared_with:
        shared_with.remove(user_id)
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"sharedWith": shared_with}}
        )
    
    return {"message": "User removed from project", "sharedWith": shared_with}

@api_router.get("/projects/{project_id}/members")
async def get_project_members(project_id: str, current_user: dict = Depends(get_current_user)):
    """Get all members of a project"""
    project = await verify_project_access(project_id, current_user["id"])
    
    members = []
    
    # Get owner
    owner = await db.users.find_one({"id": project["ownerId"]}, {"_id": 0, "passwordHash": 0})
    if owner:
        members.append({"id": owner["id"], "email": owner["email"], "role": "owner"})
    
    # Get shared users
    for user_id in project.get("sharedWith", []):
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "passwordHash": 0})
        if user:
            members.append({"id": user["id"], "email": user["email"], "role": "member"})
    
    return members

@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, current_user: dict = Depends(get_current_user)):
    project = await db.projects.find_one({"id": project_id, "ownerId": current_user["id"]})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or not owner")
    
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

@api_router.put("/chats/{chat_id}/rename", response_model=ChatResponse)
async def rename_chat(chat_id: str, data: RenameChatRequest, current_user: dict = Depends(get_current_user)):
    """Rename a chat"""
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Verify ownership
    if chat.get("projectId"):
        await verify_project_ownership(chat["projectId"], current_user["id"])
    elif chat.get("ownerId") != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Update the chat name
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"name": data.name.strip()}}
    )
    
    updated_chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    return ChatResponse(**{**updated_chat, "activeSourceIds": updated_chat.get("activeSourceIds", [])})

# --- Project Chats ---

@api_router.get("/projects/{project_id}/chats", response_model=List[ChatResponse])
async def get_chats(project_id: str, current_user: dict = Depends(get_current_user)):
    project = await verify_project_ownership(project_id, current_user["id"])
    
    chats = await db.chats.find({"projectId": project_id}, {"_id": 0}).to_list(1000)
    
    # If user is owner, return all chats
    if project["ownerId"] == current_user["id"]:
        return [ChatResponse(**{**c, "activeSourceIds": c.get("activeSourceIds", []), "sharedWithUsers": c.get("sharedWithUsers")}) for c in chats]
    
    # If user is shared, filter chats by visibility
    visible_chats = []
    for c in chats:
        shared_with = c.get("sharedWithUsers")
        # None means visible to all shared users
        # Empty list [] means hidden from all shared users
        # List with IDs means only those users can see it
        if shared_with is None or current_user["id"] in shared_with:
            visible_chats.append(ChatResponse(**{**c, "activeSourceIds": c.get("activeSourceIds", []), "sharedWithUsers": shared_with}))
    
    return visible_chats

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
    
    return ChatResponse(**{**chat, "activeSourceIds": chat.get("activeSourceIds", []), "sharedWithUsers": chat.get("sharedWithUsers")})

@api_router.put("/chats/{chat_id}/visibility")
async def update_chat_visibility(chat_id: str, data: UpdateChatVisibilityRequest, current_user: dict = Depends(get_current_user)):
    """Update which shared users can see this chat (owner only)"""
    chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    if not chat.get("projectId"):
        raise HTTPException(status_code=400, detail="Quick chats cannot be shared")
    
    # Only project owner can change visibility
    project = await db.projects.find_one({"id": chat["projectId"]}, {"_id": 0})
    if not project or project["ownerId"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Only project owner can change chat visibility")
    
    # Update chat visibility
    # Empty list [] means hidden from all shared users
    # List with IDs means only those users can see it
    # To make visible to all, send list with all shared user IDs
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"sharedWithUsers": data.sharedWithUsers}}
    )
    
    updated_chat = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    return ChatResponse(**{**updated_chat, "activeSourceIds": updated_chat.get("activeSourceIds", []), "sharedWithUsers": updated_chat.get("sharedWithUsers")})

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
            detail="Unsupported file type. Supported: PDF, DOCX, PPTX, XLSX, TXT, MD, PNG, JPEG"
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
    elif file_type == "pptx":
        extracted_text = extract_text_from_pptx(content)
    elif file_type == "xlsx":
        extracted_text = extract_text_from_xlsx(content)
    elif file_type in ["png", "jpeg", "jpg"]:
        # Use OCR to extract text from images
        extracted_text = extract_text_from_image(content)
    else:  # txt or md
        extracted_text = extract_text_from_txt(content)
    
    # For non-image files, check if text was extracted
    if file_type not in ["png", "jpeg", "jpg"]:
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

@api_router.post("/projects/{project_id}/sources/upload-multiple")
async def upload_multiple_sources(
    project_id: str,
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Upload multiple file sources to a project"""
    await verify_project_access(project_id, current_user["id"])
    
    results = []
    errors = []
    
    for file in files:
        try:
            # Validate file type
            if file.content_type not in SUPPORTED_MIME_TYPES:
                errors.append({"filename": file.filename, "error": "Unsupported file type"})
                continue
            
            # Read file content
            content = await file.read()
            
            # Check file size
            if len(content) > MAX_FILE_SIZE:
                errors.append({"filename": file.filename, "error": f"File size exceeds maximum"})
                continue
            
            # Extract text based on file type
            file_type = SUPPORTED_MIME_TYPES[file.content_type]
            
            try:
                if file_type == "pdf":
                    extracted_text = extract_text_from_pdf(content)
                elif file_type == "docx":
                    extracted_text = extract_text_from_docx(content)
                elif file_type == "pptx":
                    extracted_text = extract_text_from_pptx(content)
                elif file_type == "xlsx":
                    extracted_text = extract_text_from_xlsx(content)
                elif file_type in ["png", "jpeg", "jpg"]:
                    extracted_text = extract_text_from_image(content)
                else:
                    extracted_text = extract_text_from_txt(content)
            except Exception as e:
                errors.append({"filename": file.filename, "error": str(e)[:100]})
                continue
            
            # For non-image files, check if text was extracted
            if file_type not in ["png", "jpeg", "jpg"]:
                if not extracted_text or len(extracted_text.strip()) < 10:
                    errors.append({"filename": file.filename, "error": "No extractable text"})
                    continue
            
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
            
            results.append({
                "id": source_id,
                "filename": file.filename,
                "chunkCount": len(chunks)
            })
            
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)[:100]})
    
    return {"uploaded": results, "errors": errors}

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

class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 20

class SearchResult(BaseModel):
    sourceId: str
    sourceName: str
    sourceKind: str
    chunkIndex: int
    content: str
    matchCount: int

@api_router.post("/projects/{project_id}/sources/search")
async def search_sources(project_id: str, search_data: SearchRequest, current_user: dict = Depends(get_current_user)):
    """Search through all source chunks in project - NO GPT, NO TOKENS"""
    await verify_project_access(project_id, current_user["id"])
    
    query = search_data.query.strip().lower()
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")
    
    # Get all sources in project
    sources = await db.sources.find({"projectId": project_id}, {"_id": 0}).to_list(1000)
    source_map = {s["id"]: s for s in sources}
    
    # Search through chunks
    results = []
    chunks = await db.source_chunks.find(
        {"projectId": project_id},
        {"_id": 0}
    ).to_list(10000)
    
    for chunk in chunks:
        content_lower = chunk["content"].lower()
        if query in content_lower:
            source = source_map.get(chunk["sourceId"], {})
            
            # Count matches
            match_count = content_lower.count(query)
            
            # Get snippet around first match (150 chars before and after)
            idx = content_lower.find(query)
            start = max(0, idx - 150)
            end = min(len(chunk["content"]), idx + len(query) + 150)
            snippet = chunk["content"][start:end]
            if start > 0:
                snippet = "..." + snippet
            if end < len(chunk["content"]):
                snippet = snippet + "..."
            
            results.append({
                "sourceId": chunk["sourceId"],
                "sourceName": source.get("originalName") or source.get("url", "Unknown"),
                "sourceKind": source.get("kind", "file"),
                "chunkIndex": chunk.get("chunkIndex", 0),
                "content": snippet,
                "matchCount": match_count
            })
    
    # Sort by match count and limit
    results.sort(key=lambda x: x["matchCount"], reverse=True)
    return results[:search_data.limit]

@api_router.get("/projects/{project_id}/sources/{source_id}/download")
async def download_source(project_id: str, source_id: str, current_user: dict = Depends(get_current_user)):
    """Download a single source file"""
    await verify_project_access(project_id, current_user["id"])
    
    source = await db.sources.find_one({"id": source_id, "projectId": project_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if source["kind"] != "file" or not source.get("storagePath"):
        raise HTTPException(status_code=400, detail="This source cannot be downloaded")
    
    file_path = UPLOAD_DIR / source["storagePath"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=file_path,
        filename=source.get("originalName", source["storagePath"]),
        media_type=source.get("mimeType", "application/octet-stream")
    )

@api_router.get("/projects/{project_id}/sources/{source_id}/preview")
async def preview_source(project_id: str, source_id: str, current_user: dict = Depends(get_current_user)):
    """Get source preview - extracted text content with quality info"""
    await verify_project_access(project_id, current_user["id"])
    
    source = await db.sources.find_one({"id": source_id, "projectId": project_id}, {"_id": 0})
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Get chunks for this source
    chunks = await db.source_chunks.find(
        {"sourceId": source_id}, 
        {"_id": 0, "content": 1, "chunkIndex": 1}
    ).sort("chunkIndex", 1).to_list(1000)
    
    # Combine chunks into full text
    full_text = "\n\n".join([c["content"] for c in chunks])
    
    # Calculate quality metrics
    char_count = len(full_text)
    word_count = len(full_text.split())
    
    # Determine quality based on content
    is_image = source.get("mimeType", "").startswith("image/")
    quality = "good"
    quality_message = "Текст извлечён успешно"
    
    if char_count == 0:
        quality = "empty"
        quality_message = "Текст не извлечён"
    elif is_image:
        if "[Image: No text detected]" in full_text or "[Image: OCR failed" in full_text:
            quality = "poor"
            quality_message = "OCR не смог распознать текст. Попробуйте загрузить изображение лучшего качества"
        elif word_count < 10:
            quality = "low"
            quality_message = "Мало текста распознано. Возможно изображение низкого качества"
        else:
            quality_message = f"OCR распознал {word_count} слов"
    elif word_count < 20:
        quality = "low"
        quality_message = "Мало текста извлечено"
    
    return {
        "id": source_id,
        "name": source.get("originalName") or source.get("url"),
        "kind": source["kind"],
        "mimeType": source.get("mimeType"),
        "text": full_text,
        "chunkCount": len(chunks),
        "charCount": char_count,
        "wordCount": word_count,
        "quality": quality,
        "qualityMessage": quality_message
    }

@api_router.get("/projects/{project_id}/sources/download-all")
async def download_all_sources(project_id: str, current_user: dict = Depends(get_current_user)):
    """Download all file sources as a ZIP archive"""
    import zipfile
    from io import BytesIO
    
    await verify_project_access(project_id, current_user["id"])
    
    # Get all file sources (not URLs)
    sources = await db.sources.find({
        "projectId": project_id,
        "kind": "file"
    }, {"_id": 0}).to_list(1000)
    
    if not sources:
        raise HTTPException(status_code=404, detail="No files to download")
    
    # Create ZIP in memory
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for source in sources:
            if source.get("storagePath"):
                file_path = UPLOAD_DIR / source["storagePath"]
                if file_path.exists():
                    # Use original filename in zip
                    filename = source.get("originalName", source["storagePath"])
                    with open(file_path, 'rb') as f:
                        zip_file.writestr(filename, f.read())
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=project_files.zip"
        }
    )

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
    
    # Get sender info for user messages
    result = []
    for m in messages:
        msg_data = {
            **m, 
            "citations": m.get("citations"), 
            "usedSources": m.get("usedSources"),
            "autoIngestedUrls": m.get("autoIngestedUrls"),
            "senderEmail": m.get("senderEmail"),
            "senderName": m.get("senderName")
        }
        result.append(MessageResponse(**msg_data))
    
    return result

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
    
    # In project chats, ALL sources are always active
    if project_id:
        all_project_sources = await db.sources.find({"projectId": project_id}, {"_id": 0, "id": 1}).to_list(1000)
        active_source_ids = [s["id"] for s in all_project_sources]
    else:
        active_source_ids = []
    
    # Get sender display name (use part before @ in email)
    sender_email = current_user["email"]
    sender_name = sender_email.split("@")[0] if sender_email else "User"
    
    # Save user message with sender info
    user_msg_id = str(uuid.uuid4())
    user_message = {
        "id": user_msg_id,
        "chatId": chat_id,
        "role": "user",
        "content": message_data.content,
        "citations": None,
        "autoIngestedUrls": [s["id"] for s in auto_ingested_sources] if auto_ingested_sources else None,
        "senderEmail": sender_email,
        "senderName": sender_name,
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
            logger.info(f"Adding user custom prompt for user {current_user['id']}: {user_custom_prompt[:100]}...")
            messages.append({"role": "system", "content": f"USER CUSTOM INSTRUCTIONS:\n{user_custom_prompt}"})
        else:
            logger.info(f"No custom prompt for user {current_user['id']}")
        
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
        
        # Track token usage
        tokens_used = 0
        if hasattr(response, 'usage') and response.usage:
            tokens_used = getattr(response.usage, 'total_tokens', 0)
        
        # Update user token usage in DB
        if tokens_used > 0:
            await db.token_usage.update_one(
                {"userId": current_user["id"]},
                {
                    "$inc": {"totalTokens": tokens_used, "messageCount": 1},
                    "$set": {"lastUsedAt": datetime.now(timezone.utc).isoformat()}
                },
                upsert=True
            )
        
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
        "senderEmail": None,
        "senderName": "GPT",
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

# ==================== ADMIN USER MANAGEMENT ====================

@api_router.post("/admin/users", response_model=UserResponse)
async def admin_create_user(user_data: UserCreate, current_user: dict = Depends(get_current_user)):
    """Admin creates a new user"""
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
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
    
    return UserResponse(
        id=user_id,
        email=user_data.email,
        isAdmin=is_admin(user_data.email),
        createdAt=user["createdAt"]
    )

@api_router.get("/users/list")
async def list_users_for_sharing(current_user: dict = Depends(get_current_user)):
    """Get list of all users (for sharing projects)"""
    users = await db.users.find({}, {"_id": 0, "passwordHash": 0}).to_list(1000)
    # Exclude current user and return only id and email
    return [{"id": u["id"], "email": u["email"]} for u in users if u["id"] != current_user["id"]]

@api_router.get("/admin/users", response_model=List[UserWithUsageResponse])
async def admin_list_users(current_user: dict = Depends(get_current_user)):
    """Admin gets list of all users with token usage"""
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = await db.users.find({}, {"_id": 0, "passwordHash": 0}).to_list(1000)
    
    result = []
    for user in users:
        # Get token usage for this user
        usage = await db.token_usage.find_one({"userId": user["id"]}, {"_id": 0})
        total_tokens = usage.get("totalTokens", 0) if usage else 0
        message_count = usage.get("messageCount", 0) if usage else 0
        
        result.append(UserWithUsageResponse(
            id=user["id"],
            email=user["email"],
            isAdmin=is_admin(user["email"]),
            createdAt=user["createdAt"],
            totalTokensUsed=total_tokens,
            totalMessagesCount=message_count
        ))
    
    return result

@api_router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Admin deletes a user"""
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Don't allow deleting yourself
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    # Delete user's data
    await db.users.delete_one({"id": user_id})
    await db.token_usage.delete_one({"userId": user_id})
    await db.user_prompts.delete_one({"userId": user_id})
    
    # Delete user's quick chats
    await db.chats.delete_many({"ownerId": user_id})
    
    # Delete user's projects and their data
    projects = await db.projects.find({"ownerId": user_id}).to_list(1000)
    for project in projects:
        project_id = project["id"]
        chats = await db.chats.find({"projectId": project_id}).to_list(1000)
        for chat in chats:
            await db.messages.delete_many({"chatId": chat["id"]})
        await db.chats.delete_many({"projectId": project_id})
        await db.sources.delete_many({"projectId": project_id})
        await db.source_chunks.delete_many({"projectId": project_id})
        await db.generated_images.delete_many({"projectId": project_id})
    await db.projects.delete_many({"ownerId": user_id})
    
    return {"message": "User deleted successfully"}

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
