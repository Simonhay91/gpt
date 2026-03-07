"""
Planet Knowledge - Modular FastAPI Server
=========================================
This is the main entry point that imports and configures all route modules.
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from pathlib import Path
import os
import logging
from dotenv import load_dotenv

# Load environment
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
from db.connection import get_db, get_client

# Auth middleware
from middleware.auth import get_current_user

# Import all route modules
from routes.auth import router as auth_router
from routes.projects import router as projects_router
from routes.chats import router as chats_router
from routes.sources import router as sources_router
from routes.messages import router as messages_router
from routes.admin import router as admin_router
from routes.user_settings import router as user_settings_router
from routes.global_sources import router as global_sources_router
from routes.images import router as images_router
from routes.insights import router as insights_router, setup_insights_routes

# Enterprise Knowledge Architecture routes
from routes.departments import setup_department_routes, router as departments_router
from routes.enterprise_sources import setup_enterprise_source_routes, router as enterprise_sources_router
from routes.news import router as news_router

# Create the main app
app = FastAPI(
    title="Planet Knowledge",
    description="Multi-user collaboration platform with AI-powered knowledge management",
    version="2.0.0"
)

# Get database instance
db = get_db()

# Setup routes that need dependencies
setup_department_routes(db, get_current_user)
setup_enterprise_source_routes(db, get_current_user)
setup_insights_routes(db, get_current_user)

# Include all routers
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(chats_router)
app.include_router(sources_router)
app.include_router(messages_router)
app.include_router(admin_router)
app.include_router(user_settings_router)
app.include_router(global_sources_router)
app.include_router(images_router)
app.include_router(insights_router)
app.include_router(departments_router)
app.include_router(enterprise_sources_router)
app.include_router(news_router, prefix="/api")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoints
@app.get("/")
async def root():
    return {"message": "Planet Knowledge API", "version": "2.0.0"}

@app.get("/api/")
async def api_root():
    return {"message": "Planet Knowledge API", "version": "2.0.0"}

@app.get("/api/health")
async def health_check():
    from datetime import datetime, timezone
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# Shutdown event
@app.on_event("shutdown")
async def shutdown_db_client():
    get_client().close()

# For development - run with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
