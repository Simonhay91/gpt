"""
Planet Catalog proxy routes — exposes external API data to the frontend.
All calls go through the backend (CORS bypass + key injection).
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from db.connection import get_db
from middleware.auth import get_current_user
from services.planet_api import (
    get_categories,
    get_category_attributes,
    get_catalog,
    get_brands,
    _post,
    _get,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/planet", tags=["planet_catalog"])


@router.get("/categories")
async def categories(current_user: dict = Depends(get_current_user)):
    db = get_db()
    tree = await get_categories(db)
    return tree


@router.get("/categories/{slug}/attributes")
async def category_attributes(slug: str, current_user: dict = Depends(get_current_user)):
    db = get_db()
    attrs = await get_category_attributes(db, slug)
    return attrs


@router.get("/brands")
async def brands(current_user: dict = Depends(get_current_user)):
    db = get_db()
    return await get_brands(db)


@router.post("/products")
async def products(
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Proxy for POST /web/product/explore.
    Frontend passes the ProductCriteriaDto body directly.
    """
    try:
        result = await _post("/web/product/explore", body)
        # Normalize response key
        items = result.get("products") or result.get("items") or (result if isinstance(result, list) else [])
        if isinstance(result, dict):
            return {**result, "products": items}
        return {"products": items, "total": len(items), "page": 1, "limit": len(items), "totalPages": 1}
    except Exception as exc:
        logger.error(f"planet products proxy error: {exc}")
        raise HTTPException(status_code=502, detail="Upstream catalog error")


@router.get("/products/{slug}")
async def product_detail(slug: str, current_user: dict = Depends(get_current_user)):
    try:
        return await _get(f"/web/product/{slug}")
    except Exception as exc:
        logger.error(f"planet product detail error: {exc}")
        raise HTTPException(status_code=502, detail="Upstream catalog error")


@router.get("/sections")
async def sections(current_user: dict = Depends(get_current_user)):
    try:
        return await _get("/web/section")
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Upstream catalog error")


@router.get("/sections/{section_id}/products")
async def section_products(section_id: str, current_user: dict = Depends(get_current_user)):
    try:
        return await _get(f"/web/product/section/{section_id}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Upstream catalog error")
