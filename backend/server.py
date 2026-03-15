"""
Planet Knowledge - Modular FastAPI Server
Main application entry point that imports and configures all route modules.
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from uuid import uuid4
import os
import logging
import bcrypt
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
from routes.insights import router as insights_router, setup_insights_routes
from routes.competitors import router as competitors_router, auto_refresh_competitor_products
from routes.product_catalog import router as product_catalog_router

# Enterprise routes with setup functions
from routes.departments import setup_department_routes, router as departments_router
from routes.enterprise_sources import setup_enterprise_source_routes, router as enterprise_sources_router
from routes.news import router as news_router

# Import services and dependencies needed for enterprise route setup
from services.enterprise import AuditService, VersionService
from services.file_processor import (
    chunk_text, 
    chunk_tabular_text,
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_pptx,
    extract_text_from_xlsx,
    extract_text_from_csv,
    extract_text_from_txt,
    extract_text_from_image
)
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


# Text extraction wrapper that routes to appropriate extraction function
async def extract_text_wrapper(content: bytes, file_type: str) -> str:
    """Extract text from file content based on file type"""
    try:
        if file_type == "pdf":
            return extract_text_from_pdf(content)
        elif file_type == "docx":
            return extract_text_from_docx(content)
        elif file_type == "pptx":
            return extract_text_from_pptx(content)
        elif file_type == "xlsx":
            return extract_text_from_xlsx(content)
        elif file_type in ["csv"]:
            return extract_text_from_csv(content)
        elif file_type in ["txt", "md"]:
            return extract_text_from_txt(content)
        elif file_type in ["png", "jpg", "jpeg", "gif", "webp"]:
            return extract_text_from_image(content)
        else:
            logger.warning(f"Unsupported file type for extraction: {file_type}")
            return ""
    except Exception as e:
        logger.error(f"Text extraction error for type {file_type}: {str(e)}")
        raise


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
setup_insights_routes(db, get_current_user)

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
app.include_router(product_catalog_router)

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

async def init_admin_user():
    """Create or update admin user for fresh deployments"""
    try:
        admin_email = "admin@ai.planetworkspace.com"
        admin_password = "Admin@123456"
        
        # Check if correct admin exists
        existing_admin = await db.users.find_one({"email": admin_email})
        
        if existing_admin:
            logger.info(f"✓ Admin user already exists: {admin_email}")
            return
        
        # Check for old admin emails and update
        old_emails = ["admin@admin.com", "admin@planetworkspace.com"]
        old_admin = None
        
        for old_email in old_emails:
            old_admin = await db.users.find_one({"email": old_email})
            if old_admin:
                logger.info(f"Found old admin: {old_email}")
                break
        
        if old_admin:
            # Update old admin to new email and password
            password_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await db.users.update_one(
                {"_id": old_admin["_id"]},
                {"$set": {
                    "email": admin_email,
                    "passwordHash": password_hash,
                    "mustChangePassword": True,
                    "canEditGlobalSources": True
                }}
            )
            logger.info(f"✓ Updated admin user to: {admin_email}")
            logger.info(f"✓ Password reset to: {admin_password}")
            return
        
        # No admin exists - create new one
        logger.info("No admin found - creating new admin user...")
        password_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        admin_user = {
            "id": str(uuid4()),
            "email": admin_email,
            "passwordHash": password_hash,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "departments": [],
            "primaryDepartmentId": None,
            "canEditGlobalSources": True,
            "mustChangePassword": True
        }
        
        await db.users.insert_one(admin_user)
        logger.info(f"✓ Created admin user: {admin_email}")
        logger.info(f"✓ Default password: {admin_password}")
            
    except Exception as e:
        logger.error(f"Error initializing admin user: {e}")
        import traceback
        logger.error(traceback.format_exc())


@app.on_event("startup")
async def startup_event():
    """Initialize database and start background scheduler"""
    # Create admin user if database is empty
    await init_admin_user()
    
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
