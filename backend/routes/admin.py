"""Admin routes"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime, timezone, timedelta
import uuid
import os
import logging

logger = logging.getLogger(__name__)
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY", "")

from models.schemas import (
    UserCreate, 
    UserResponse, 
    UserWithUsageResponse,
    UpdateUserGlobalPermissionRequest,
    UpdateUserCatalogPermissionRequest,
    GPTConfigUpdate,
    GPTConfigResponse,
    UserPromptUpdate,
    UpdateUserModelRequest
)
from middleware.auth import get_current_user, is_admin, hash_password
from db.connection import get_db
from services.cache import CACHE_SIMILARITY_THRESHOLD, CACHE_TTL_DAYS

router = APIRouter(prefix="/api", tags=["admin"])

GLOBAL_PROJECT_ID = "__global__"


@router.get("/admin/source-stats")
async def get_source_stats(current_user: dict = Depends(get_current_user)):
    """Get source statistics per user - for admin dashboard"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = await db.users.find({}, {"_id": 0, "id": 1, "email": 1}).to_list(1000)
    user_map = {u["id"]: u["email"] for u in users}
    
    projects = await db.projects.find({}, {"_id": 0, "id": 1, "ownerId": 1, "name": 1}).to_list(1000)
    project_owner_map = {p["id"]: p["ownerId"] for p in projects}
    
    sources = await db.sources.find({}, {"_id": 0, "projectId": 1, "sizeBytes": 1, "originalName": 1, "createdAt": 1, "kind": 1}).to_list(10000)
    
    user_stats = {}
    for source in sources:
        project_id = source.get("projectId")
        owner_id = project_owner_map.get(project_id)
        
        if not owner_id:
            continue
            
        if owner_id not in user_stats:
            user_stats[owner_id] = {
                "userId": owner_id,
                "email": user_map.get(owner_id, "Unknown"),
                "sourceCount": 0,
                "totalSizeBytes": 0,
                "fileCount": 0,
                "urlCount": 0
            }
        
        user_stats[owner_id]["sourceCount"] += 1
        user_stats[owner_id]["totalSizeBytes"] += source.get("sizeBytes", 0) or 0
        
        if source.get("kind") == "url":
            user_stats[owner_id]["urlCount"] += 1
        else:
            user_stats[owner_id]["fileCount"] += 1
    
    result = list(user_stats.values())
    result.sort(key=lambda x: x["totalSizeBytes"], reverse=True)
    
    total_sources = sum(u["sourceCount"] for u in result)
    total_size = sum(u["totalSizeBytes"] for u in result)
    
    return {
        "users": result,
        "totalSources": total_sources,
        "totalSizeBytes": total_size
    }


@router.get("/admin/global-sources/stats")
async def get_global_sources_usage_stats(current_user: dict = Depends(get_current_user)):
    """Get usage statistics for all global sources"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    sources = await db.sources.find(
        {"projectId": GLOBAL_PROJECT_ID}, 
        {"_id": 0, "id": 1, "originalName": 1, "url": 1, "chunkCount": 1, "sizeBytes": 1, "createdAt": 1}
    ).to_list(1000)
    
    result = []
    for source in sources:
        usage = await db.source_usage.find_one({"sourceId": source["id"]}, {"_id": 0})
        
        source_name = source.get("originalName") or source.get("url") or "Unknown"
        
        result.append({
            "sourceId": source["id"],
            "sourceName": source_name,
            "chunkCount": source.get("chunkCount", 0),
            "sizeBytes": source.get("sizeBytes", 0),
            "createdAt": source.get("createdAt"),
            "usageCount": usage.get("usageCount", 0) if usage else 0,
            "lastUsedAt": usage.get("lastUsedAt") if usage else None,
            "recentUsers": [
                {"email": u["userEmail"], "timestamp": u["timestamp"]} 
                for u in (usage.get("usageHistory", []) if usage else [])[-5:]
            ]
        })
    
    result.sort(key=lambda x: x["usageCount"], reverse=True)
    
    total_usage = sum(s["usageCount"] for s in result)
    sources_used = sum(1 for s in result if s["usageCount"] > 0)
    
    return {
        "sources": result,
        "totalUsageCount": total_usage,
        "sourcesUsedCount": sources_used,
        "totalSourcesCount": len(result)
    }


@router.get("/admin/cache/stats")
async def get_cache_stats(current_user: dict = Depends(get_current_user)):
    """Get semantic cache statistics"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    cache_entries = await db.semantic_cache.find({}, {"_id": 0, "embedding": 0}).to_list(1000)
    
    total_entries = len(cache_entries)
    total_hits = sum(e.get("hitCount", 0) for e in cache_entries)
    
    by_project = {}
    for entry in cache_entries:
        pid = entry.get("projectId") or "global"
        if pid not in by_project:
            by_project[pid] = {"count": 0, "hits": 0}
        by_project[pid]["count"] += 1
        by_project[pid]["hits"] += entry.get("hitCount", 0)
    
    top_entries = sorted(cache_entries, key=lambda x: x.get("hitCount", 0), reverse=True)[:10]
    
    return {
        "totalEntries": total_entries,
        "totalHits": total_hits,
        "byProject": by_project,
        "topEntries": [{
            "id": e["id"],
            "question": e["question"][:100] + "..." if len(e.get("question", "")) > 100 else e.get("question", ""),
            "hitCount": e.get("hitCount", 0),
            "lastHitAt": e.get("lastHitAt"),
            "createdAt": e.get("createdAt")
        } for e in top_entries],
        "settings": {
            "similarityThreshold": CACHE_SIMILARITY_THRESHOLD,
            "ttlDays": CACHE_TTL_DAYS
        }
    }


@router.delete("/admin/cache/clear")
async def clear_cache(current_user: dict = Depends(get_current_user)):
    """Clear all semantic cache entries"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.semantic_cache.delete_many({})
    return {"message": f"Cleared {result.deleted_count} cache entries"}


@router.delete("/admin/cache/{cache_id}")
async def delete_cache_entry(cache_id: str, current_user: dict = Depends(get_current_user)):
    """Delete specific cache entry"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.semantic_cache.delete_one({"id": cache_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cache entry not found")
    return {"message": "Cache entry deleted"}


@router.get("/admin/config", response_model=GPTConfigResponse)
async def get_gpt_config(current_user: dict = Depends(get_current_user)):
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    config = await db.gpt_config.find_one({"id": "1"}, {"_id": 0})
    if not config:
        config = {
            "id": "1",
            "model": "claude-sonnet-4-20250514",
            "developerPrompt": "You are a helpful assistant.",
            "updatedAt": datetime.now(timezone.utc).isoformat()
        }
        await db.gpt_config.insert_one(config)
    return GPTConfigResponse(**config)


@router.put("/admin/config", response_model=GPTConfigResponse)
async def update_gpt_config(config_data: GPTConfigUpdate, current_user: dict = Depends(get_current_user)):
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    update_data = {"updatedAt": datetime.now(timezone.utc).isoformat()}
    if config_data.model is not None:
        update_data["model"] = config_data.model
    if config_data.developerPrompt is not None:
        update_data["developerPrompt"] = config_data.developerPrompt
    
    await db.gpt_config.update_one({"id": "1"}, {"$set": update_data}, upsert=True)
    
    updated_config = await db.gpt_config.find_one({"id": "1"}, {"_id": 0})
    return GPTConfigResponse(**updated_config)


# ==================== USER MANAGEMENT ====================

@router.post("/admin/users", response_model=UserResponse)
async def admin_create_user(user_data: UserCreate, current_user: dict = Depends(get_current_user)):
    """Admin creates a new user - user must change password on first login"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_id = str(uuid.uuid4())
    user = {
        "id": user_id,
        "email": user_data.email,
        "passwordHash": hash_password(user_data.password),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "departments": [],
        "primaryDepartmentId": None,
        "canEditGlobalSources": False,
        "canEditProductCatalog": False,
        "mustChangePassword": True  # User must change password on first login
    }
    await db.users.insert_one(user)
    
    return UserResponse(
        id=user_id,
        email=user_data.email,
        isAdmin=is_admin(user_data.email),
        createdAt=user["createdAt"]
    )


@router.get("/users/list")
async def list_users_for_sharing(current_user: dict = Depends(get_current_user)):
    """Get list of all users (for sharing projects)"""
    db = get_db()
    users = await db.users.find({}, {"_id": 0, "passwordHash": 0}).to_list(1000)
    return [{"id": u["id"], "email": u["email"]} for u in users if u["id"] != current_user["id"]]


@router.get("/admin/users", response_model=List[UserWithUsageResponse])
async def admin_list_users(current_user: dict = Depends(get_current_user)):
    """Admin gets list of all users with token usage"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = await db.users.find({}, {"_id": 0, "passwordHash": 0}).to_list(1000)
    
    result = []
    for user in users:
        usage = await db.token_usage.find_one({"userId": user["id"]}, {"_id": 0})
        total_tokens = usage.get("totalTokens", 0) if usage else 0
        message_count = usage.get("messageCount", 0) if usage else 0
        
        result.append(UserWithUsageResponse(
            id=user["id"],
            email=user["email"],
            isAdmin=is_admin(user["email"]),
            createdAt=user["createdAt"],
            totalTokensUsed=total_tokens,
            totalMessagesCount=message_count,
            canEditGlobalSources=user.get("canEditGlobalSources", False),
            canEditProductCatalog=user.get("canEditProductCatalog", False),
        ))
    
    return result


@router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    """Admin deletes a user - CASCADE DELETE all related data"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_id == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    # 1. Delete user's projects and all related data
    projects = await db.projects.find({"ownerId": user_id}).to_list(1000)
    for project in projects:
        project_id = project["id"]
        # Delete project chats and their messages
        chats = await db.chats.find({"projectId": project_id}).to_list(1000)
        for chat in chats:
            await db.messages.delete_many({"chatId": chat["id"]})
        await db.chats.delete_many({"projectId": project_id})
        # Delete project sources and chunks
        await db.sources.delete_many({"projectId": project_id})
        await db.source_chunks.delete_many({"projectId": project_id})
        # Delete generated images
        await db.generated_images.delete_many({"projectId": project_id})
        # Delete project files
        await db.project_files.delete_many({"projectId": project_id})
        await db.project_file_chunks.delete_many({"projectId": project_id})
    await db.projects.delete_many({"ownerId": user_id})
    
    # 2. Delete user's quick chats (no project)
    quick_chats = await db.chats.find({"ownerId": user_id, "projectId": None}).to_list(1000)
    for chat in quick_chats:
        await db.messages.delete_many({"chatId": chat["id"]})
    await db.chats.delete_many({"ownerId": user_id})
    
    # 3. Delete user's personal sources
    await db.sources.delete_many({"ownerId": user_id, "level": "personal"})
    await db.source_chunks.delete_many({"ownerId": user_id})
    
    # 4. Delete user settings and prompts
    await db.user_prompts.delete_one({"userId": user_id})
    await db.token_usage.delete_one({"userId": user_id})
    
    # 5. Delete user's analyzer sessions
    await db.analyzer_sessions.delete_many({"userId": user_id})
    
    # 6. Delete user's semantic cache entries
    await db.semantic_cache.delete_many({"userId": user_id})
    
    # 7. Delete user's source usage history
    await db.source_usage.delete_many({"userId": user_id})
    
    # 8. Remove user from departments (update, not delete)
    await db.departments.update_many(
        {"members": user_id},
        {"$pull": {"members": user_id}}
    )
    await db.departments.update_many(
        {"managers": user_id},
        {"$pull": {"managers": user_id}}
    )
    
    # 9. Update audit logs to mark user as deleted (keep for audit trail)
    await db.audit_logs.update_many(
        {"userId": user_id},
        {"$set": {"userDeleted": True}}
    )
    
    # 10. Delete competitors created by user
    await db.competitors.delete_many({"created_by": user_id})
    
    # 11. Delete products created by user (or mark as orphaned)
    await db.product_catalog.update_many(
        {"created_by": user_id},
        {"$set": {"created_by": "deleted_user", "updated_by": "deleted_user"}}
    )
    
    # 12. Finally delete the user
    await db.users.delete_one({"id": user_id})
    
    return {"message": "User and all related data deleted successfully"}


@router.get("/admin/users/{user_id}/details")
async def get_user_details(user_id: str, current_user: dict = Depends(get_current_user)):
    """Get detailed user info for admin"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "passwordHash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_prompt = await db.user_prompts.find_one({"userId": user_id}, {"_id": 0})
    projects = await db.projects.find({"ownerId": user_id}, {"_id": 0}).to_list(100)
    
    projects_with_stats = []
    for p in projects:
        chat_count = await db.chats.count_documents({"projectId": p["id"]})
        source_count = await db.sources.count_documents({"projectId": p["id"]})
        projects_with_stats.append({**p, "chatCount": chat_count, "sourceCount": source_count})
    
    usage = await db.token_usage.find_one({"userId": user_id}, {"_id": 0})
    
    user_messages = await db.messages.find(
        {"senderEmail": user["email"], "role": "user"},
        {"_id": 0, "id": 1, "chatId": 1, "content": 1, "createdAt": 1}
    ).sort("createdAt", -1).to_list(20)
    
    user_model = user.get("gptModel")
    prompt_text = ""
    if user_prompt:
        prompt_text = user_prompt.get("customPrompt") or user_prompt.get("prompt", "")
    
    return {
        "user": user,
        "prompt": prompt_text,
        "gptModel": user_model,
        "projects": projects_with_stats,
        "tokenUsage": {
            "totalTokens": usage.get("totalTokensUsed", 0) if usage else 0,
            "totalMessages": usage.get("totalMessagesCount", 0) if usage else 0
        },
        "recentActivity": user_messages
    }


@router.put("/admin/users/{user_id}/prompt")
async def update_user_prompt_admin(user_id: str, data: UserPromptUpdate, current_user: dict = Depends(get_current_user)):
    """Admin updates user's custom prompt"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.user_prompts.update_one(
        {"userId": user_id},
        {"$set": {"userId": user_id, "customPrompt": data.customPrompt, "updatedAt": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    
    return {"message": "Prompt updated"}


@router.put("/admin/users/{user_id}/gpt-model")
async def update_user_gpt_model(user_id: str, data: UpdateUserModelRequest, current_user: dict = Depends(get_current_user)):
    """Admin sets user-specific GPT model"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.users.update_one({"id": user_id}, {"$set": {"gptModel": data.model}})
    
    return {"message": "Model updated", "model": data.model}


@router.post("/admin/users/{user_id}/reset-password")
async def admin_reset_password(user_id: str, current_user: dict = Depends(get_current_user)):
    """Admin generates a new random password for a user"""
    import random, string
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "isAdmin": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate a secure random password: 12 chars, letters + digits + symbols
    chars = string.ascii_letters + string.digits + "!@#$%"
    new_password = ''.join(random.choices(chars, k=12))

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "passwordHash": hash_password(new_password),
            "mustChangePassword": True,
            "passwordResetAt": datetime.now(timezone.utc).isoformat(),
            "passwordResetBy": current_user["email"]
        }}
    )
    return {"new_password": new_password, "email": user["email"]}


@router.put("/admin/users/{user_id}/global-permission")
async def update_user_global_permission(    user_id: str, 
    data: UpdateUserGlobalPermissionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Admin grants/revokes global source editing permission"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"canEditGlobalSources": data.canEditGlobalSources}}
    )
    
    return {"message": f"Global sources permission {'granted' if data.canEditGlobalSources else 'revoked'}"}


@router.put("/admin/users/{user_id}/catalog-permission")
async def update_user_catalog_permission(
    user_id: str,
    data: UpdateUserCatalogPermissionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Admin grants/revokes product catalog editing permission (aliases, domain rules)"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")

    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.users.update_one(
        {"id": user_id},
        {"$set": {"canEditProductCatalog": data.canEditProductCatalog}}
    )

    return {"message": f"Product catalog permission {'granted' if data.canEditProductCatalog else 'revoked'}"}


@router.get("/admin/users/{user_id}/question-history")
async def get_user_question_history(user_id: str, current_user: dict = Depends(get_current_user)):
    """Get user's question history (user messages only, no AI responses)"""
    db = get_db()
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get all user messages (role=user) in chronological order
    user_messages = await db.messages.find(
        {"senderEmail": user["email"], "role": "user"},
        {"_id": 0, "id": 1, "chatId": 1, "content": 1, "createdAt": 1}
    ).sort("createdAt", -1).to_list(500)  # Last 500 questions
    
    # Enrich with chat names
    chat_ids = list(set(msg["chatId"] for msg in user_messages))
    chats = await db.chats.find(
        {"id": {"$in": chat_ids}},
        {"_id": 0, "id": 1, "name": 1}
    ).to_list(len(chat_ids))
    
    chat_name_map = {chat["id"]: chat.get("name") or "Untitled Chat" for chat in chats}
    
    result = []
    for msg in user_messages:
        result.append({
            "content": msg["content"],
            "createdAt": msg["createdAt"],
            "chatName": chat_name_map.get(msg["chatId"], "Unknown Chat")
        })
    
    return result


# ==================== EMBEDDING BACKFILL ====================

@router.post("/admin/backfill-embeddings")
async def backfill_embeddings(current_user: dict = Depends(get_current_user)):
    """
    Generate Voyage AI embeddings for all active catalog products that are missing one.
    Admin only. Safe to call multiple times — skips products that already have embeddings.
    """
    if not is_admin(current_user["email"]):
        raise HTTPException(status_code=403, detail="Admin access required")

    if not VOYAGE_API_KEY:
        raise HTTPException(status_code=400, detail="VOYAGE_API_KEY is not configured on the server")

    db = get_db()

    products = await db.product_catalog.find(
        {"is_active": True, "$or": [{"embedding": None}, {"embedding": {"$exists": False}}]},
        {
            "_id": 0, "id": 1, "title_en": 1, "article_number": 1, "crm_code": 1,
            "vendor": 1, "product_model": 1, "aliases": 1, "description": 1,
        },
    ).to_list(10000)

    if not products:
        return {"message": "All products already have embeddings", "processed": 0, "errors": 0}

    import voyageai
    import time
    voyage = voyageai.Client(api_key=VOYAGE_API_KEY)

    BATCH_SIZE = 50
    processed = 0
    errors = 0

    def _text(p: dict) -> str:
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

    for i in range(0, len(products), BATCH_SIZE):
        batch = products[i: i + BATCH_SIZE]
        ids = [p["id"] for p in batch]
        texts = [_text(p)[:8000] for p in batch]
        try:
            result = voyage.embed(texts, model="voyage-3")
            for pid, emb in zip(ids, result.embeddings):
                await db.product_catalog.update_one(
                    {"id": pid}, {"$set": {"embedding": emb}}
                )
            processed += len(batch)
            logger.info(f"Backfill embeddings: {processed}/{len(products)}")
        except Exception as exc:
            errors += len(batch)
            logger.error(f"Backfill batch error: {exc}")
        time.sleep(0.5)

    return {
        "message": "Backfill complete",
        "total_without_embedding": len(products),
        "processed": processed,
        "errors": errors,
    }
