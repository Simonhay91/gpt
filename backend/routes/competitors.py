"""Competitor Tracker routes"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from datetime import datetime, timezone
from uuid import uuid4
import logging
import httpx
from bs4 import BeautifulSoup

from models.schemas import (
    CompetitorCreate,
    CompetitorUpdate,
    CompetitorResponse,
    CompetitorProductCreate,
    CompetitorMatchUpdate
)
from middleware.auth import get_current_user
from db.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["competitors"])


# ==================== HELPER FUNCTIONS ====================

async def fetch_and_parse_url(url: str, max_chars: int = 3000) -> Dict[str, Any]:
    """
    Fetch URL and parse content using BeautifulSoup.
    Returns: {
        "title": str,
        "content": str (limited to max_chars),
        "error": Optional[str]
    }
    """
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, verify=False) as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Remove scripts and styles
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            # Get title
            title = soup.title.string.strip() if soup.title else url
            
            # Get body text
            body = soup.find('body')
            if body:
                text = body.get_text(separator='\n', strip=True)
            else:
                text = soup.get_text(separator='\n', strip=True)
            
            # Clean up text
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = '\n'.join(lines)
            
            # Limit to max_chars
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
            
            return {
                "title": title[:200],
                "content": text,
                "error": None
            }
    except httpx.TimeoutException:
        return {"title": None, "content": None, "error": "Timeout while fetching URL"}
    except httpx.HTTPStatusError as e:
        return {"title": None, "content": None, "error": f"HTTP error: {e.response.status_code}"}
    except Exception as e:
        return {"title": None, "content": None, "error": f"Error fetching URL: {str(e)}"}


async def check_competitor_tracker_access(current_user: dict) -> bool:
    """Check if user has access to Competitor Tracker"""
    db = get_db()
    user_dept_ids = current_user.get("departments", [])
    logger.info(f"Checking competitor access for user {current_user.get('email')}, departments: {user_dept_ids}")
    
    if not user_dept_ids:
        logger.info("User has no departments")
        return False
    
    # Check if any of user's departments has competitor_tracker_enabled
    departments = await db.departments.find(
        {"id": {"$in": user_dept_ids}},
        {"_id": 0, "id": 1, "name": 1, "competitor_tracker_enabled": 1}
    ).to_list(100)
    
    logger.info(f"Found departments: {departments}")
    result = any(dept.get("competitor_tracker_enabled", False) for dept in departments)
    logger.info(f"Access result: {result}")
    return result


async def auto_refresh_competitor_products():
    """Background task to auto-refresh competitor products based on their schedule"""
    db = get_db()
    logger.info("🔄 Starting auto-refresh of competitor products...")
    
    try:
        competitors = await db.competitors.find({}, {"_id": 0}).to_list(10000)
        
        total_refreshed = 0
        total_failed = 0
        
        for competitor in competitors:
            for product in competitor.get("products", []):
                if not product.get("auto_refresh", False):
                    continue
                
                last_fetched = product.get("last_fetched")
                refresh_interval_days = product.get("refresh_interval_days", 7)
                
                if last_fetched:
                    last_fetched_dt = datetime.fromisoformat(last_fetched.replace('Z', '+00:00'))
                    days_since_fetch = (datetime.now(timezone.utc) - last_fetched_dt).days
                    
                    if days_since_fetch < refresh_interval_days:
                        continue
                
                logger.info(f"Auto-refreshing: {competitor['name']} - {product['url']}")
                result = await fetch_and_parse_url(product["url"])
                
                if not result["error"]:
                    now = datetime.now(timezone.utc).isoformat()
                    await db.competitors.update_one(
                        {"id": competitor["id"], "products.id": product["id"]},
                        {"$set": {
                            "products.$.title": result["title"],
                            "products.$.cached_content": result["content"],
                            "products.$.last_fetched": now
                        }}
                    )
                    total_refreshed += 1
                    logger.info(f"✓ Refreshed: {product['url']}")
                else:
                    total_failed += 1
                    logger.error(f"✗ Failed to refresh {product['url']}: {result['error']}")
        
        logger.info(f"🔄 Auto-refresh completed: {total_refreshed} refreshed, {total_failed} failed")
        
    except Exception as e:
        logger.error(f"Error in auto_refresh_competitor_products: {str(e)}")


# ==================== COMPETITOR ENDPOINTS ====================

@router.post("/competitors", response_model=CompetitorResponse)
async def create_competitor(data: CompetitorCreate, current_user: dict = Depends(get_current_user)):
    """Create a new competitor (requires competitor_tracker access)"""
    db = get_db()
    has_access = await check_competitor_tracker_access(current_user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied. Competitor Tracker not enabled for your department.")
    
    competitor_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    competitor = {
        "id": competitor_id,
        "name": data.name,
        "website": data.website,
        "products": [],
        "matched_our_products": [],
        "created_by": current_user["id"],
        "created_at": now
    }
    
    await db.competitors.insert_one(competitor)
    
    return CompetitorResponse(**competitor)


@router.get("/competitors")
async def list_competitors(current_user: dict = Depends(get_current_user)):
    """List all competitors (requires competitor_tracker access)"""
    db = get_db()
    has_access = await check_competitor_tracker_access(current_user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied. Competitor Tracker not enabled for your department.")
    
    competitors = await db.competitors.find({}, {"_id": 0}).to_list(1000)
    return competitors


@router.get("/competitors/{competitor_id}", response_model=CompetitorResponse)
async def get_competitor(competitor_id: str, current_user: dict = Depends(get_current_user)):
    """Get competitor details"""
    db = get_db()
    has_access = await check_competitor_tracker_access(current_user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    competitor = await db.competitors.find_one({"id": competitor_id}, {"_id": 0})
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    return CompetitorResponse(**competitor)


@router.put("/competitors/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(competitor_id: str, data: CompetitorUpdate, current_user: dict = Depends(get_current_user)):
    """Update competitor"""
    db = get_db()
    has_access = await check_competitor_tracker_access(current_user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    competitor = await db.competitors.find_one({"id": competitor_id}, {"_id": 0})
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    update_data = {}
    if data.name is not None:
        update_data["name"] = data.name
    if data.website is not None:
        update_data["website"] = data.website
    
    if update_data:
        await db.competitors.update_one({"id": competitor_id}, {"$set": update_data})
        competitor.update(update_data)
    
    return CompetitorResponse(**competitor)


@router.delete("/competitors/{competitor_id}")
async def delete_competitor(competitor_id: str, current_user: dict = Depends(get_current_user)):
    """Delete competitor"""
    db = get_db()
    has_access = await check_competitor_tracker_access(current_user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.competitors.delete_one({"id": competitor_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    return {"success": True, "message": "Competitor deleted"}


# ==================== PRODUCT ENDPOINTS ====================

@router.post("/competitors/{competitor_id}/products")
async def add_competitor_product(
    competitor_id: str,
    data: CompetitorProductCreate,
    current_user: dict = Depends(get_current_user)
):
    """Add a product URL to competitor"""
    db = get_db()
    has_access = await check_competitor_tracker_access(current_user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    competitor = await db.competitors.find_one({"id": competitor_id}, {"_id": 0})
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    product_id = str(uuid4())
    product = {
        "id": product_id,
        "url": data.url,
        "title": None,
        "cached_content": None,
        "last_fetched": None,
        "auto_refresh": data.auto_refresh,
        "refresh_interval_days": data.refresh_interval_days
    }
    
    await db.competitors.update_one(
        {"id": competitor_id},
        {"$push": {"products": product}}
    )
    
    return {"success": True, "product": product}


@router.delete("/competitors/{competitor_id}/products/{product_id}")
async def delete_competitor_product(
    competitor_id: str,
    product_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a product from competitor"""
    db = get_db()
    has_access = await check_competitor_tracker_access(current_user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    result = await db.competitors.update_one(
        {"id": competitor_id},
        {"$pull": {"products": {"id": product_id}}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return {"success": True, "message": "Product deleted"}


@router.post("/competitors/{competitor_id}/products/{product_id}/fetch")
async def fetch_competitor_product(
    competitor_id: str,
    product_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Fetch and cache product URL content"""
    db = get_db()
    has_access = await check_competitor_tracker_access(current_user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    competitor = await db.competitors.find_one({"id": competitor_id}, {"_id": 0})
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    product = next((p for p in competitor.get("products", []) if p["id"] == product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    result = await fetch_and_parse_url(product["url"])
    
    if result["error"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    now = datetime.now(timezone.utc).isoformat()
    await db.competitors.update_one(
        {"id": competitor_id, "products.id": product_id},
        {"$set": {
            "products.$.title": result["title"],
            "products.$.cached_content": result["content"],
            "products.$.last_fetched": now
        }}
    )
    
    return {
        "success": True,
        "title": result["title"],
        "content_length": len(result["content"]),
        "last_fetched": now
    }


@router.post("/competitors/{competitor_id}/refresh")
async def refresh_all_products(
    competitor_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Refresh all products for a competitor"""
    db = get_db()
    has_access = await check_competitor_tracker_access(current_user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    competitor = await db.competitors.find_one({"id": competitor_id}, {"_id": 0})
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    products = competitor.get("products", [])
    success_count = 0
    failed_count = 0
    
    for product in products:
        result = await fetch_and_parse_url(product["url"])
        
        if not result["error"]:
            now = datetime.now(timezone.utc).isoformat()
            await db.competitors.update_one(
                {"id": competitor_id, "products.id": product["id"]},
                {"$set": {
                    "products.$.title": result["title"],
                    "products.$.cached_content": result["content"],
                    "products.$.last_fetched": now
                }}
            )
            success_count += 1
        else:
            failed_count += 1
    
    return {
        "success": True,
        "total": len(products),
        "success_count": success_count,
        "failed_count": failed_count
    }


@router.put("/competitors/{competitor_id}/match")
async def update_competitor_matches(
    competitor_id: str,
    data: CompetitorMatchUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update product matching"""
    db = get_db()
    has_access = await check_competitor_tracker_access(current_user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    competitor = await db.competitors.find_one({"id": competitor_id}, {"_id": 0})
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    matches = [m.dict() for m in data.matched_our_products]
    
    await db.competitors.update_one(
        {"id": competitor_id},
        {"$set": {"matched_our_products": matches}}
    )
    
    return {"success": True, "matched_count": len(matches)}
