"""Product catalog search service"""
import logging

logger = logging.getLogger(__name__)


async def search_product_catalog(query: str, db, limit: int = 5) -> list:
    """Search product catalog by keyword across multiple fields."""
    try:
        results = await db.product_catalog.find(
            {
                "is_active": True,
                "$or": [
                    {"title_en": {"$regex": query, "$options": "i"}},
                    {"article_number": {"$regex": query, "$options": "i"}},
                    {"vendor": {"$regex": query, "$options": "i"}},
                    {"product_model": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                    {"aliases": {"$elemMatch": {"$regex": query, "$options": "i"}}}
                ]
            },
            {"_id": 0}
        ).limit(limit).to_list(limit)
        return results
    except Exception:
        return []
