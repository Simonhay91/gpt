"""
PlanetWorkspace external catalog integration.

Responsibilities:
- Fetch categories (with attributes) from api-prod.planetworkspace.com
- Fetch all products (paginated) and normalize field names to match
  the existing matching pipeline conventions (title_en, article_number, etc.)
- Cache normalized products + Voyage embeddings in MongoDB so the
  matching pipeline works without any changes.

Collections used:
  planet_category_cache   — full category tree, TTL = CATEGORY_TTL_HOURS
  planet_embedding_cache  — {external_id, crm_code, embedding, updated_at}, TTL = EMBED_TTL_HOURS
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from functools import partial

import requests as _requests

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL = os.environ.get("PLANET_API_URL", "https://planetworkspace.com/api")
PARTNER_KEY = os.environ.get("PLANET_PARTNER_KEY", "")

CATEGORY_TTL_HOURS = 5
EMBED_TTL_HOURS = 24
CATALOG_TTL_MINUTES = 10   # how long to keep the in-memory catalog cache

# In-memory catalog cache — avoids re-fetching all pages on every request.
# Keyed by category_id (or "__all__"). Each entry: {products, expires_at}.
_catalog_cache: Dict[str, Any] = {}
FETCH_PAGE_LIMIT = 500        # max allowed by the API
MAX_CATALOG_PRODUCTS = 5000   # safety cap

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
EMBED_BATCH_SIZE = 100        # OpenAI embeddings batch size

# ── HTTP helpers ──────────────────────────────────────────────────────────────
# Uses synchronous `requests` in a thread-pool executor to bypass async DNS
# resolution failures that occur in some containerised environments.

def _headers() -> dict:
    return {"x-partner-key": PARTNER_KEY, "Content-Type": "application/json"}


def _sync_get(path: str, params: dict = None) -> Any:
    r = _requests.get(f"{BASE_URL}{path}", headers=_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _sync_post(path: str, body: dict) -> Any:
    r = _requests.post(f"{BASE_URL}{path}", headers=_headers(), json=body, timeout=30)
    r.raise_for_status()
    return r.json()


async def _get(path: str, params: dict = None) -> Any:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_sync_get, path, params))


async def _post(path: str, body: dict) -> Any:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_sync_post, path, body))


# ── Normalizer ────────────────────────────────────────────────────────────────

def _datasheet_url(p: dict) -> str:
    """
    Build a datasheet/product URL for use in Excel exports.
    Priority: publicDatasheets[0] direct link → Planet product page URL.
    Datasheets live at {BASE_URL}/public/... (keep /api in path).
    """
    datasheets = p.get("publicDatasheets") or []
    if datasheets:
        path = datasheets[0].get("path", "") if isinstance(datasheets[0], dict) else ""
        if path:
            base = BASE_URL.rstrip("/")
            return f"{base}/{path.lstrip('/')}"

    # Fallback: link to the product page on PlanetWorkspace
    slug = p.get("slug", "")
    if slug:
        return f"https://planetworkspace.com/web/product/{slug}"
    return ""


def _normalize(p: dict) -> dict:
    """
    Map external API field names to the conventions used by the matching pipeline.
    The pipeline expects: title_en, article_number, crm_code, vendor, product_model,
    datasheet_url, aliases, embedding.
    """
    pricing = p.get("pricingInfo") or {}
    tiers = pricing.get("tiers") or []
    price = tiers[0].get("price") if tiers else None

    return {
        # identity
        "external_id": str(p.get("id", "")),
        "slug": p.get("slug", ""),
        # pipeline-expected fields
        "title_en": p.get("name", ""),
        "article_number": p.get("articleCode") or p.get("model") or "",
        "crm_code": p.get("crmCode") or "",
        "vendor": p.get("brandName") or "",
        "product_model": p.get("model") or "",
        "datasheet_url": _datasheet_url(p),
        "aliases": [],                # populated separately via product_aliases collection
        # extra fields (useful for UI / future matching)
        "category_id": str(p.get("categoryId") or ""),
        "category_name": p.get("categoryName") or "",
        "brand_id": str(p.get("brandId") or ""),
        "is_new": p.get("isNew", False),
        "is_hot": p.get("isHot", False),
        "is_discontinued": p.get("isDiscontinued", False),
        "stock_amount": p.get("stockAmount") or 0,
        "price": price,
        "description": p.get("description") or "",
        "images": p.get("images") or [],
        "attribute_values": p.get("attributeValues") or [],
        # embedding filled later
        "embedding": None,
    }


# ── Category fetch & cache ────────────────────────────────────────────────────

async def get_categories(db) -> List[dict]:
    """
    Return the full category tree. Uses MongoDB cache (TTL = CATEGORY_TTL_HOURS).
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=CATEGORY_TTL_HOURS)).isoformat()
    cached = await db.planet_category_cache.find_one({"cached_at": {"$gte": cutoff}})
    if cached:
        return cached.get("tree", [])

    try:
        tree = await _get("/web/category")
    except Exception as exc:
        logger.error(f"planet_api: category fetch failed: {exc}")
        # Return stale cache if available
        stale = await db.planet_category_cache.find_one({})
        return stale.get("tree", []) if stale else []

    now = datetime.now(timezone.utc).isoformat()
    await db.planet_category_cache.replace_one(
        {}, {"tree": tree, "cached_at": now}, upsert=True
    )
    return tree


async def get_category_attributes(db, slug: str) -> List[dict]:
    """
    Return filterable attributes for a category slug.
    Stored inside the category cache document under planet_attr_cache.
    Returns [] if slug gives 404.
    """
    cached = await db.planet_attr_cache.find_one({"slug": slug})
    if cached:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=CATEGORY_TTL_HOURS)).isoformat()
        if cached.get("cached_at", "") >= cutoff:
            return cached.get("attributes", [])

    try:
        attrs = await _get(f"/web/category/{slug}/attributes")
    except _requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            attrs = []
        else:
            logger.warning(f"planet_api: attribute fetch failed for {slug}: {exc}")
            return cached.get("attributes", []) if cached else []
    except Exception as exc:
        logger.warning(f"planet_api: attribute fetch failed for {slug}: {exc}")
        return cached.get("attributes", []) if cached else []

    now = datetime.now(timezone.utc).isoformat()
    await db.planet_attr_cache.replace_one(
        {"slug": slug},
        {"slug": slug, "attributes": attrs, "cached_at": now},
        upsert=True,
    )
    return attrs


# ── Product fetch ─────────────────────────────────────────────────────────────

async def _fetch_all_products_raw(category_id: str = None) -> List[dict]:
    """Paginate through /web/product/explore and return all raw product dicts."""
    all_items: List[dict] = []
    page = 1

    body: Dict[str, Any] = {"page": page, "limit": FETCH_PAGE_LIMIT}
    if category_id:
        body["categoryId"] = str(category_id)

    while len(all_items) < MAX_CATALOG_PRODUCTS:
        body["page"] = page
        try:
            r = await _post("/web/product/explore", body)
        except Exception as exc:
            logger.error(f"planet_api: product fetch page {page} failed: {exc}")
            break

        # normalize response key (can be products or items)
        items = r.get("products") or r.get("items") or (r if isinstance(r, list) else [])
        if not items:
            break

        all_items.extend(items)

        # Use total count (always present) to know when we have everything
        total = r.get("total") if isinstance(r, dict) else None
        if total and len(all_items) >= total:
            break
        # No more items
        if not items:
            break

        page += 1

    return all_items[:MAX_CATALOG_PRODUCTS]


# ── Embedding helpers ─────────────────────────────────────────────────────────

def _embedding_text(p: dict) -> str:
    """Build rich text for Voyage embedding from a normalized product."""
    parts = []
    if p.get("title_en"):
        parts.append(p["title_en"])
    if p.get("article_number"):
        parts.append(f"Article: {p['article_number']}")
    if p.get("product_model"):
        parts.append(f"Model: {p['product_model']}")
    if p.get("crm_code"):
        parts.append(f"CRM: {p['crm_code']}")
    if p.get("vendor"):
        parts.append(f"Vendor: {p['vendor']}")
    if p.get("category_name"):
        parts.append(f"Category: {p['category_name']}")
    # Include selection attribute values (e.g. Form Factor: SFP+)
    for av in (p.get("attribute_values") or []):
        attr = av.get("attribute") or {}
        val = av.get("textValue") or (str(av.get("numericValue")) if av.get("numericValue") is not None else None)
        if attr.get("name") and val:
            parts.append(f"{attr['name']}: {val}")
    if p.get("description"):
        parts.append(p["description"][:400])
    return " | ".join(parts)


def _embed_batch(texts: List[str]) -> List[Optional[List[float]]]:
    """Embed texts via OpenAI text-embedding-3-small."""
    if not OPENAI_API_KEY:
        return [None] * len(texts)
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.embeddings.create(
        input=[t[:8000] for t in texts],
        model="text-embedding-3-small",
    )
    return [item.embedding for item in response.data]


async def _fill_embeddings(db, products: List[dict]) -> List[dict]:
    """
    For each product look up cached embedding from planet_embedding_cache.
    Compute and store embeddings for products that don't have one yet.
    Returns the same list with .embedding field populated where possible.
    """
    if not OPENAI_API_KEY:
        return products

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=EMBED_TTL_HOURS)).isoformat()

    # Load all cached embeddings in one query
    external_ids = [p["external_id"] for p in products if p.get("external_id")]
    cached_docs = await db.planet_embedding_cache.find(
        {"external_id": {"$in": external_ids}, "updated_at": {"$gte": cutoff}},
        {"_id": 0, "external_id": 1, "embedding": 1},
    ).to_list(len(external_ids))
    embed_map = {d["external_id"]: d["embedding"] for d in cached_docs}

    # Split into cached vs needs-compute
    needs_embed = [p for p in products if not embed_map.get(p.get("external_id"))]

    if needs_embed:
        texts = [_embedding_text(p) for p in needs_embed]
        now = datetime.now(timezone.utc).isoformat()
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch_products = needs_embed[i: i + EMBED_BATCH_SIZE]
            batch_texts = texts[i: i + EMBED_BATCH_SIZE]
            try:
                embeddings = _embed_batch(batch_texts)
            except Exception as exc:
                logger.warning(f"planet_api: OpenAI embed batch failed: {exc}")
                embeddings = [None] * len(batch_texts)

            # Upsert to cache + fill embed_map
            for p, emb in zip(batch_products, embeddings):
                eid = p.get("external_id")
                if eid and emb:
                    embed_map[eid] = emb
                    await db.planet_embedding_cache.replace_one(
                        {"external_id": eid},
                        {
                            "external_id": eid,
                            "crm_code": p.get("crm_code", ""),
                            "embedding": emb,
                            "updated_at": now,
                        },
                        upsert=True,
                    )

    # Attach embeddings to products
    for p in products:
        p["embedding"] = embed_map.get(p.get("external_id"))

    return products


# ── Datasheet URL fetch ───────────────────────────────────────────────────────

async def get_product_datasheet_url(slug: str) -> str:
    """
    Fetch a single product's detail and return its first datasheet URL.
    Used post-matching to enrich Excel output with PDF links.
    Returns empty string if unavailable.
    """
    if not slug:
        return ""
    try:
        raw = await _get(f"/web/product/{slug}")
        product_data = raw.get("product") or raw
        datasheets = product_data.get("publicDatasheets") or []
        if datasheets and isinstance(datasheets[0], dict):
            path = datasheets[0].get("path", "")
            if path:
                base = BASE_URL.rstrip("/")
                return f"{base}/{path.lstrip('/')}"
    except Exception as exc:
        logger.debug(f"planet_api: datasheet fetch failed for slug={slug!r}: {exc}")
    return ""


# ── Main public API ───────────────────────────────────────────────────────────

async def get_catalog(db, category_id: str = None) -> List[dict]:
    """
    Return the full normalized product catalog with embeddings.
    Results are cached in-memory for CATALOG_TTL_MINUTES to avoid re-fetching
    all pages from the external API on every request.
    """
    if not PARTNER_KEY:
        logger.warning("planet_api: PLANET_PARTNER_KEY not set — returning empty catalog")
        return []

    cache_key = category_id or "__all__"
    now = datetime.now(timezone.utc)

    entry = _catalog_cache.get(cache_key)
    if entry and entry["expires_at"] > now:
        logger.debug(f"planet_api: catalog memory-cache hit (key={cache_key})")
        # Re-attach embeddings (may have been computed since last fetch)
        products = await _fill_embeddings(db, entry["products"])
        return products

    logger.info(f"planet_api: fetching catalog from API (key={cache_key})")
    raw = await _fetch_all_products_raw(category_id=category_id)
    if not raw:
        return []

    normalized = [_normalize(p) for p in raw]
    normalized = await _fill_embeddings(db, normalized)

    # Store without embeddings — they are large and live in planet_embedding_cache
    products_to_store = [{k: v for k, v in p.items() if k != "embedding"} for p in normalized]
    _catalog_cache[cache_key] = {
        "products": products_to_store,
        "expires_at": now + timedelta(minutes=CATALOG_TTL_MINUTES),
    }
    logger.info(f"planet_api: catalog cached in memory ({len(normalized)} products, key={cache_key})")

    return normalized


async def get_brands(db) -> List[dict]:
    """Fetch brand list with 5-min in-memory cache."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    cached = await db.planet_brand_cache.find_one({"cached_at": {"$gte": cutoff}})
    if cached:
        return cached.get("brands", [])

    try:
        brands = await _get("/web/brand")
    except Exception as exc:
        logger.error(f"planet_api: brand fetch failed: {exc}")
        stale = await db.planet_brand_cache.find_one({})
        return stale.get("brands", []) if stale else []

    now = datetime.now(timezone.utc).isoformat()
    await db.planet_brand_cache.replace_one(
        {}, {"brands": brands, "cached_at": now}, upsert=True
    )
    return brands
