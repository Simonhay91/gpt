"""
Planet Knowledge - Modular FastAPI Server
Main application entry point that imports and configures all route modules.
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== APP INITIALIZATION ====================

app = FastAPI(title="Planet Knowledge API", version="2.0.0")

# Scheduler for background tasks
scheduler = AsyncIOScheduler()

# ==================== IMPORT ROUTE MODULES ====================

from db.connection import get_db, get_client

# Import all route modules
from routes.auth import router as auth_router
from routes.projects import router as projects_router
from routes.chats import router as chats_router
from routes.sources import router as sources_router
from routes.messages import router as messages_router
from routes.admin import router as admin_router
from routes.global_sources import router as global_sources_router
from routes.user_settings import router as user_settings_router
from routes.images import router as images_router
from routes.insights import router as insights_router
from routes.competitors import router as competitors_router, auto_refresh_competitor_products

# Enterprise routes with setup functions
from routes.departments import setup_department_routes, router as departments_router
from routes.enterprise_sources import setup_enterprise_source_routes, router as enterprise_sources_router
from routes.news import router as news_router

# Import services and dependencies needed for enterprise route setup
from services.enterprise import AuditService, VersionService
from services.file_processor import chunk_text, chunk_tabular_text
from middleware.auth import get_current_user, is_admin

# File storage settings
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

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
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp"
}

# Initialize services
db = get_db()
audit_service = AuditService(db)
version_service = VersionService(db)


# Wrapper for extract_text - delegated to enterprise_sources setup
async def extract_text_wrapper(file_path, mime_type):
    """Placeholder wrapper - actual extraction happens in route modules"""
    return ""


# ==================== SETUP ENTERPRISE ROUTES ====================

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

# ==================== REGISTER ALL ROUTERS ====================

# Core routes
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(chats_router)
app.include_router(sources_router)
app.include_router(messages_router)

# Admin routes
app.include_router(admin_router)
app.include_router(global_sources_router)

# User routes
app.include_router(user_settings_router)

# Feature routes
app.include_router(images_router)
app.include_router(insights_router)
app.include_router(competitors_router)

# Enterprise routes
app.include_router(departments_router)
app.include_router(enterprise_sources_router)
app.include_router(news_router, prefix="/api")

# ==================== MIDDLEWARE ====================

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== HEALTH ENDPOINTS ====================

@app.get("/api/")
async def root():
    return {"message": "Planet Knowledge API is running", "version": "2.0.0"}


@app.get("/api/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


# ==================== LIFECYCLE EVENTS ====================

@app.on_event("startup")
async def startup_event():
    """Start background scheduler"""
    # Schedule auto-refresh task to run daily at 2 AM
    scheduler.add_job(
        auto_refresh_competitor_products,
        CronTrigger(hour=2, minute=0),
        id="auto_refresh_competitors",
        replace_existing=True
    )
    scheduler.start()
    logger.info("✓ Planet Knowledge API started")
    logger.info("✓ Scheduler started - Auto-refresh will run daily at 2:00 AM")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    scheduler.shutdown()
    get_client().close()
    logger.info("✓ Planet Knowledge API shutdown complete")
