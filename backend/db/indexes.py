"""MongoDB index definitions.

Indexes only speed up the queries the app already runs; they never change
query results or logic. Creating an index that already exists is a no-op, so
this module is safe to run on every startup.
"""
import logging

import pymongo

logger = logging.getLogger(__name__)


# Each entry: (collection_name, keys, options)
# keys follow the pymongo format: list of (field, direction) tuples.
_INDEXES = [
    # projects — dashboard access checks query these fields
    ("projects", [("id", pymongo.ASCENDING)], {}),
    ("projects", [("ownerId", pymongo.ASCENDING)], {}),
    ("projects", [("sharedWith", pymongo.ASCENDING)], {}),
    ("projects", [("sharedMembers.userId", pymongo.ASCENDING)], {}),

    # chats
    ("chats", [("id", pymongo.ASCENDING)], {}),
    ("chats", [("projectId", pymongo.ASCENDING)], {}),
    ("chats", [("ownerId", pymongo.ASCENDING)], {}),

    # messages — get_messages: find({chatId}).sort(createdAt, 1)
    ("messages", [("chatId", pymongo.ASCENDING), ("createdAt", pymongo.ASCENDING)], {}),

    # sources
    ("sources", [("id", pymongo.ASCENDING)], {}),
    ("sources", [("projectId", pymongo.ASCENDING)], {}),
    ("sources", [("ownerId", pymongo.ASCENDING)], {}),
    ("sources", [("level", pymongo.ASCENDING)], {}),
    ("sources", [("publishedFrom", pymongo.ASCENDING)], {}),
    # library — list items shared with a user's departments
    ("sources", [("level", pymongo.ASCENDING), ("sharedDepartments", pymongo.ASCENDING)], {}),

    # source_chunks — RAG lookups and chunk counts
    ("source_chunks", [("sourceId", pymongo.ASCENDING)], {}),
    ("source_chunks", [("projectId", pymongo.ASCENDING)], {}),

    # semantic_cache — find_cached_answer: {projectId, cacheContextHash, createdAt}
    (
        "semantic_cache",
        [
            ("projectId", pymongo.ASCENDING),
            ("cacheContextHash", pymongo.ASCENDING),
            ("createdAt", pymongo.ASCENDING),
        ],
        {},
    ),

    # users
    ("users", [("id", pymongo.ASCENDING)], {}),
    ("users", [("email", pymongo.ASCENDING)], {}),
]


async def create_indexes(db):
    """Create all indexes in the background. Idempotent and best-effort.

    Wrapped per-index in try/except so a single failing index never blocks
    startup or other indexes.
    """
    created = 0
    for collection_name, keys, options in _INDEXES:
        try:
            await db[collection_name].create_index(keys, background=True, **options)
            created += 1
        except Exception as e:  # noqa: BLE001 - best-effort, never fatal
            logger.warning(f"Index creation skipped for {collection_name} {keys}: {e}")
    logger.info(f"✓ MongoDB indexes ensured ({created}/{len(_INDEXES)})")
