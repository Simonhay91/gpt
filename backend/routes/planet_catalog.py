"""
Planet Catalog proxy routes — exposes external API data to the frontend.
All calls go through the backend (CORS bypass + key injection).
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import Response as FastAPIResponse
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
    _normalize,
    _headers,
    BASE_URL,
)
import logging
import requests as _requests

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
    Items are normalized so vendor/category_name are always populated.
    """
    try:
        result = await _post("/web/product/explore", body)
        raw_items = result.get("products") or result.get("items") or (result if isinstance(result, list) else [])
        items = [_normalize(p) for p in raw_items]
        if isinstance(result, dict):
            return {**result, "products": items}
        return {"products": items, "total": len(items), "page": 1, "limit": len(items), "totalPages": 1}
    except Exception as exc:
        logger.error(f"planet products proxy error: {exc}")
        raise HTTPException(status_code=502, detail="Upstream catalog error")


@router.get("/products/{slug:path}")
async def product_detail(slug: str, current_user: dict = Depends(get_current_user)):
    try:
        raw = await _get(f"/web/product/{slug}")
        # Planet API wraps: {product: {...}, metadata: {...}, pricingInfo: {...}, inStock: 0}
        product_data = raw.get("product") or raw
        normalized = _normalize(product_data)
        # Enrich with detail-only fields not in _normalize
        normalized["features"] = product_data.get("features") or ""
        normalized["publicDatasheets"] = product_data.get("publicDatasheets") or []
        normalized["contentForm"] = product_data.get("contentForm")
        normalized["category"] = product_data.get("category")
        normalized["partnerForms"] = product_data.get("partnerForms") or []
        normalized["inStock"] = raw.get("inStock", 0)
        normalized["onWay"] = raw.get("onWay", 0)
        # Merge: product_data fields first (camelCase originals), normalized overrides pipeline fields
        return {**product_data, **normalized}
    except Exception as exc:
        logger.error(f"planet product detail error: {exc}")
        raise HTTPException(status_code=502, detail="Upstream catalog error")


@router.get("/by-crm/{crm_code}/aliases")
async def aliases_by_crm(crm_code: str, current_user: dict = Depends(get_current_user)):
    """Return saved aliases for a product by CRM code (from product_aliases collection)."""
    db = get_db()
    raw = await db.product_aliases.find(
        {"crm_code": crm_code}
    ).sort("saved_at", -1).to_list(200)
    return [
        {
            "id": str(a["_id"]),
            "alias": a.get("alias", ""),
            "confidence": a.get("confidence", "auto"),
            "saved_at": a.get("saved_at"),
        }
        for a in raw
    ]


@router.get("/by-crm/{crm_code}/relations")
async def relations_by_crm(crm_code: str, current_user: dict = Depends(get_current_user)):
    """Return AI-generated relations for a product by CRM code."""
    db = get_db()
    raw = await db.product_relations.find(
        {"$or": [{"crm_code_a": crm_code}, {"crm_code_b": crm_code}]},
        {"_id": 0},
    ).to_list(100)

    result = []
    for r in raw:
        if r.get("crm_code_a") == crm_code:
            other_crm = r.get("crm_code_b", "")
            other_title = r.get("title_b", "")
        else:
            other_crm = r.get("crm_code_a", "")
            other_title = r.get("title_a", "")
        result.append({
            "crm_code": other_crm,
            "title": other_title,
            "confidence": r.get("confidence"),
            "reason": r.get("reason"),
            "rule_title": r.get("rule_title", ""),
        })

    order = {"high": 0, "medium": 1, "low": 2}
    result.sort(key=lambda x: order.get(x.get("confidence", "low"), 2))
    return result


@router.get("/img")
async def proxy_image(path: str = Query(...)):
    """
    Proxy planet image files through the backend.
    Browser cannot reach api-prod.planetworkspace.com directly (ERR_NAME_NOT_RESOLVED),
    so all images are fetched server-side and forwarded.
    No auth required — product images are public catalog data.
    """
    try:
        # Normalise path — strip leading slash
        clean = path.lstrip("/")
        base = BASE_URL.rstrip("/")
        # Remove /api suffix to get root URL (images live at root, not under /api)
        if base.endswith("/api"):
            base = base[:-4]
        url = f"{base}/{clean}"
        r = _requests.get(url, headers=_headers(), timeout=15)
        r.raise_for_status()
        media_type = r.headers.get("content-type", "image/webp")
        return FastAPIResponse(
            content=r.content,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as exc:
        logger.warning(f"planet img proxy failed for path={path!r}: {exc}")
        raise HTTPException(status_code=404, detail="Image not found")


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
