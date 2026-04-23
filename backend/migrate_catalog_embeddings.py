"""Migration script: Generate and save Voyage AI embeddings for product_catalog."""
import asyncio
import logging
import os
import time
from motor.motor_asyncio import AsyncIOMotorClient
import voyageai
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VOYAGE_API_KEY = os.environ.get('VOYAGE_API_KEY', '')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')
BATCH_SIZE = 50   # Voyage API supports up to 128 texts per request
RATE_LIMIT_DELAY = 0.5  # seconds between batches


def _product_text(p: dict) -> str:
    """Build a rich text representation of a product for embedding."""
    parts = []
    if p.get("title_en"):
        parts.append(p["title_en"])
    if p.get("article_number"):
        parts.append(f"Article: {p['article_number']}")
    if p.get("crm_code"):
        parts.append(f"CRM: {p['crm_code']}")
    if p.get("vendor"):
        parts.append(f"Vendor: {p['vendor']}")
    if p.get("product_model"):
        parts.append(f"Model: {p['product_model']}")
    if p.get("aliases"):
        parts.append(f"Aliases: {', '.join(p['aliases'][:10])}")
    if p.get("description"):
        parts.append(p["description"][:500])
    return " | ".join(parts)


async def migrate():
    if not VOYAGE_API_KEY:
        logger.error("VOYAGE_API_KEY is not set!")
        return

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    voyage = voyageai.Client(api_key=VOYAGE_API_KEY)

    total = await db.product_catalog.count_documents(
        {"is_active": True, "$or": [{"embedding": None}, {"embedding": {"$exists": False}}]}
    )
    logger.info(f"Products without embedding: {total}")

    if total == 0:
        logger.info("All products already have embeddings!")
        client.close()
        return

    processed = 0
    errors = 0

    cursor = db.product_catalog.find(
        {"is_active": True, "$or": [{"embedding": None}, {"embedding": {"$exists": False}}]},
        {"_id": 1, "title_en": 1, "article_number": 1, "crm_code": 1,
         "vendor": 1, "product_model": 1, "aliases": 1, "description": 1},
    )

    batch_ids = []
    batch_texts = []

    async def flush_batch():
        nonlocal processed, errors
        if not batch_ids:
            return
        try:
            result = voyage.embed(batch_texts, model="voyage-3")
            for doc_id, embedding in zip(batch_ids, result.embeddings):
                await db.product_catalog.update_one(
                    {"_id": doc_id},
                    {"$set": {"embedding": embedding}},
                )
            processed += len(batch_ids)
            logger.info(f"Progress: {processed}/{total}")
        except Exception as e:
            errors += len(batch_ids)
            logger.error(f"Batch error: {e}")
        batch_ids.clear()
        batch_texts.clear()
        time.sleep(RATE_LIMIT_DELAY)

    async for product in cursor:
        text = _product_text(product)
        if not text.strip():
            continue
        batch_ids.append(product["_id"])
        batch_texts.append(text[:8000])

        if len(batch_ids) >= BATCH_SIZE:
            await flush_batch()

    await flush_batch()  # last partial batch

    logger.info(f"Done! Processed: {processed}, Errors: {errors}")
    client.close()


asyncio.run(migrate())
