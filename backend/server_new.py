"""
Planet Knowledge API - Refactored Server

This is the main FastAPI application entry point.
All business logic has been moved to modular routes and services.
"""
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pathlib import Path
import os
import logging

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create the main app
app = FastAPI(title="Planet Knowledge API")

# Security
security = HTTPBearer()

# Import database connection
from db.connection import get_db, get_client

# Import routers
from routes.auth import router as auth_router
from routes.projects import router as projects_router
from routes.chats import router as chats_router
from routes.sources import router as sources_router

# Enterprise routes (existing)
from services.enterprise import AuditService, VersionService, HierarchicalRetrieval
from routes.departments import setup_department_routes, router as departments_router
from routes.enterprise_sources import setup_enterprise_source_routes, router as enterprise_sources_router
from routes.news import router as news_router
from routes.analyzer import setup_analyzer_routes, router as analyzer_router

# Import for messages and other complex routes
from routes.messages import router as messages_router
from routes.admin import router as admin_router
from routes.images import router as images_router
from routes.global_sources import router as global_sources_router
from routes.user_settings import router as user_settings_router

# Middleware auth
from middleware.auth import get_current_user, is_admin

# File processor for enterprise routes
from services.file_processor import chunk_text, chunk_tabular_text

# Settings
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 50 * 1024 * 1024

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

# Initialize database
db = get_db()

# Initialize enterprise services
audit_service = AuditService(db)
version_service = VersionService(db)
hierarchical_retrieval = HierarchicalRetrieval(db)


# Helper function for text extraction (wrapper for existing functions)
async def extract_text_wrapper(content: bytes, file_type: str) -> str:
    """Wrapper to extract text based on file type"""
    from services.file_processor import (
        extract_text_from_pdf,
        extract_text_from_docx,
        extract_text_from_pptx,
        extract_text_from_xlsx,
        extract_text_from_csv,
        extract_text_from_image,
        extract_text_from_txt
    )
    
    if file_type == "pdf":
        return extract_text_from_pdf(content)
    elif file_type == "docx":
        return extract_text_from_docx(content)
    elif file_type == "pptx":
        return extract_text_from_pptx(content)
    elif file_type == "xlsx":
        return extract_text_from_xlsx(content)
    elif file_type == "csv":
        return extract_text_from_csv(content)
    elif file_type in ["png", "jpeg", "jpg"]:
        return extract_text_from_image(content)
    else:
        return extract_text_from_txt(content)


# Setup enterprise routes with dependencies
setup_department_routes(db, get_current_user, is_admin, audit_service)
setup_enterprise_source_routes(
    db, 
    get_current_user, 
    is_admin, 
    audit_service, 
    version_service,
    extract_text_wrapper,
    chunk_text,
    chunk_tabular_text,
    UPLOAD_DIR,
    MAX_FILE_SIZE,
    SUPPORTED_MIME_TYPES
)

# Setup analyzer routes
setup_analyzer_routes(db, get_current_user)

# Include all routers
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(chats_router)
app.include_router(sources_router)
app.include_router(messages_router)
app.include_router(admin_router)
app.include_router(images_router)
app.include_router(global_sources_router)
app.include_router(user_settings_router)

# Enterprise routers
app.include_router(departments_router)
app.include_router(enterprise_sources_router)
app.include_router(news_router, prefix="/api")
app.include_router(analyzer_router, prefix="/api")


# ==================== HEALTH CHECK ====================

@app.get("/api/")
async def root():
    return {"message": "Planet Knowledge API is running"}


@app.get("/api/health")
async def health():
    from datetime import datetime, timezone
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


# ==================== CORS MIDDLEWARE ====================

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== SHUTDOWN ====================

@app.on_event("shutdown")
async def shutdown_db_client():
    client = get_client()
    client.close()
