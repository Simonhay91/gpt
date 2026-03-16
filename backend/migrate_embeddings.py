"""Migration script: Add embeddings to existing chunks using Voyage AI"""
import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import voyageai
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VOYAGE_API_KEY = 'pa-VI00cyWfnWphGvOPBZIdhMbpVgkk6sJQ7zdfgI0w_ML'
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)

async def migrate():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    total = await db.source_chunks.count_documents({"embedding": None})
    logger.info(f"Chunks without embedding: {total}")
    
    if total == 0:
        logger.info("Nothing to migrate!")
        return
    
    processed = 0
    errors = 0
    
    cursor = db.source_chunks.find({"embedding": None}, {"_id": 1, "content": 1, "text": 1})
    
    async for chunk in cursor:
        content = chunk.get("content") or chunk.get("text", "")
        if not content:
            continue
        
        try:
            result = voyage_client.embed([content[:8000]], model="voyage-3")
            embedding = result.embeddings[0]
            
            await db.source_chunks.update_one(
                {"_id": chunk["_id"]},
                {"$set": {"embedding": embedding}}
            )
            processed += 1
            
            if processed % 10 == 0:
                logger.info(f"Progress: {processed}/{total}")
                
        except Exception as e:
            errors += 1
            logger.error(f"Error on chunk: {e}")
    
    logger.info(f"Done! Processed: {processed}, Errors: {errors}")
    client.close()

asyncio.run(migrate())