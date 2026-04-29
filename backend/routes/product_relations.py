"""Product Relations — AI-powered compatibility detection between catalog products."""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel
import os
import re
import json
import uuid
import logging
import numpy as np
from datetime import datetime, timezone
from bson import ObjectId

import anthropic

from db.connection import get_db
from middleware.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/product-relations", tags=["product-relations"])

CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY", "")

VOYAGE_TOP_K = 5          # candidates per product from opposite category
CLAUDE_BATCH_SIZE = 20    # pairs per Claude call


# ==================== HELPERS ====================

def _cosine_similarity(a: list, b: list) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0


def _voyage_embed_batch(texts: List[str]) -> List[Optional[List[float]]]:
    import voyageai
    client = voyageai.Client(api_key=VOYAGE_API_KEY)
    result = client.embed(texts, model="voyage-3")
    return result.embeddings


def _voyage_top_k(
    items: List[dict],
    candidates: List[dict],
    k: int,
) -> List[List[dict]]:
    """For each item in `items`, return TOP-k semantically similar products from `candidates`."""
    item_texts = [p.get("title_en", "") + " " + p.get("article_number", "") for p in items]
    cand_texts = [p.get("title_en", "") + " " + p.get("article_number", "") for p in candidates]

    try:
        item_embs = _voyage_embed_batch(item_texts)
        cand_embs = _voyage_embed_batch(cand_texts)
    except Exception as exc:
        logger.warning(f"Voyage embed failed in relations: {exc}")
        return [candidates[:k] for _ in items]

    results = []
    for item_emb in item_embs:
        if not item_emb:
            results.append(candidates[:k])
            continue
        scores = []
        for j, cand_emb in enumerate(cand_embs):
            if cand_emb:
                score = _cosine_similarity(item_emb, cand_emb)
            else:
                score = 0.0
            scores.append((score, j))
        top_indices = [j for _, j in sorted(scores, reverse=True)[:k]]
        results.append([candidates[j] for j in top_indices])
    return results


def _claude_check_compatibility(
    pairs: List[tuple],  # [(product_a, product_b), ...]
    rule_description: str,
) -> List[dict]:
    """Ask Claude whether each (A, B) pair is compatible. Returns list of result dicts."""
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

    pairs_text_parts = []
    for i, (a, b) in enumerate(pairs):
        pairs_text_parts.append(
            f"[{i + 1}]\n"
            f"  Product A: {a.get('title_en', '')} | Article: {a.get('article_number', '')} | Vendor: {a.get('vendor', '')}\n"
            f"  Product B: {b.get('title_en', '')} | Article: {b.get('article_number', '')} | Vendor: {b.get('vendor', '')}"
        )
    pairs_text = "\n\n".join(pairs_text_parts)

    prompt = f"""You are a product compatibility analyst for a fiber optics and network equipment catalog.

{rule_description}

For each pair below, decide if Product A and Product B can work together in the same installation (are compatible).

{pairs_text}

Return a JSON array with exactly {len(pairs)} objects in the same order:
[
  {{
    "pair": <1-based index>,
    "compatible": <true|false>,
    "confidence": "<high|medium|low>",
    "reason": "<one short English sentence explaining why they are or are not compatible>"
  }}
]

Rules:
- confidence="high": clearly compatible or clearly incompatible — no ambiguity
- confidence="medium": likely compatible but with some uncertainty
- confidence="low": uncertain — insufficient information to decide
- Return ONLY the JSON array, no extra text."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        logger.error(f"Claude (relations) returned no JSON array: {raw[:300]}")
        return [{"pair": i + 1, "compatible": False, "confidence": "low", "reason": "Parse error"} for i in range(len(pairs))]
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        logger.error(f"Claude (relations) JSON decode error: {exc}")
        return [{"pair": i + 1, "compatible": False, "confidence": "low", "reason": "Parse error"} for i in range(len(pairs))]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ==================== SCHEMAS ====================

class RelationRuleCreate(BaseModel):
    title: str
    category_a: str
    category_b: str
    description: str
    is_active: bool = True


class RelationRuleUpdate(BaseModel):
    title: Optional[str] = None
    category_a: Optional[str] = None
    category_b: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


# ==================== RELATION RULES CRUD ====================

@router.get("/rules")
async def list_relation_rules(current_user: dict = Depends(get_current_user)):
    db = get_db()
    rules = await db.relation_rules.find({}).sort("created_at", -1).to_list(200)
    for r in rules:
        r["_id"] = str(r["_id"])
    return rules


@router.post("/rules", status_code=201)
async def create_relation_rule(
    body: RelationRuleCreate,
    current_user: dict = Depends(get_current_user),
):
    if not (current_user.get("isAdmin") or current_user.get("role") in ("admin", "manager")):
        raise HTTPException(status_code=403, detail="Admin or Manager required")
    db = get_db()
    doc = {
        **body.model_dump(),
        "created_by": str(current_user.get("_id", current_user.get("id", ""))),
        "created_at": now_iso(),
        "last_run_at": None,
    }
    result = await db.relation_rules.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    return doc


@router.put("/rules/{rule_id}")
async def update_relation_rule(
    rule_id: str,
    body: RelationRuleUpdate,
    current_user: dict = Depends(get_current_user),
):
    if not (current_user.get("isAdmin") or current_user.get("role") in ("admin", "manager")):
        raise HTTPException(status_code=403, detail="Admin or Manager required")
    db = get_db()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    await db.relation_rules.update_one(
        {"_id": ObjectId(rule_id)},
        {"$set": updates},
    )
    rule = await db.relation_rules.find_one({"_id": ObjectId(rule_id)})
    rule["_id"] = str(rule["_id"])
    return rule


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_relation_rule(
    rule_id: str,
    current_user: dict = Depends(get_current_user),
):
    if not (current_user.get("isAdmin") or current_user.get("role") in ("admin", "manager")):
        raise HTTPException(status_code=403, detail="Admin or Manager required")
    db = get_db()
    await db.relation_rules.delete_one({"_id": ObjectId(rule_id)})
    return


# ==================== RUN AI ANALYSIS ====================

async def _run_rule_analysis(rule_id: str):
    """Background task: load products from both categories, find compatible pairs via Claude, save results."""
    db = get_db()

    rule = await db.relation_rules.find_one({"_id": ObjectId(rule_id)})
    if not rule:
        logger.error(f"relation rule {rule_id} not found")
        return

    cat_a = rule["category_a"]
    cat_b = rule["category_b"]
    description = rule.get("description", "")

    logger.info(f"[relations] Running rule '{rule['title']}': {cat_a} ↔ {cat_b}")

    products_a = await db.product_catalog.find(
        {"is_active": True, "root_category": cat_a},
        {"_id": 0, "id": 1, "title_en": 1, "article_number": 1, "crm_code": 1, "vendor": 1, "embedding": 1},
    ).to_list(1000)

    products_b = await db.product_catalog.find(
        {"is_active": True, "root_category": cat_b},
        {"_id": 0, "id": 1, "title_en": 1, "article_number": 1, "crm_code": 1, "vendor": 1, "embedding": 1},
    ).to_list(1000)

    # Handle same-category case: use full list for both sides
    same_category = cat_a == cat_b

    if not products_a or not products_b:
        logger.warning(f"[relations] No products found for categories: {cat_a}, {cat_b}")
        await db.relation_rules.update_one(
            {"_id": ObjectId(rule_id)},
            {"$set": {"last_run_at": now_iso()}},
        )
        return

    # Build candidate pairs using Voyage pre-filter
    pairs: List[tuple] = []  # (product_a, product_b)
    seen_pairs: set = set()

    try:
        top_k_results = _voyage_top_k(products_a, products_b, VOYAGE_TOP_K)
    except Exception as exc:
        logger.warning(f"[relations] Voyage failed, using first {VOYAGE_TOP_K} candidates: {exc}")
        top_k_results = [products_b[:VOYAGE_TOP_K] for _ in products_a]

    for prod_a, candidates in zip(products_a, top_k_results):
        for prod_b in candidates:
            if same_category and prod_a["id"] == prod_b["id"]:
                continue
            pair_key = tuple(sorted([prod_a["id"], prod_b["id"]]))
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                pairs.append((prod_a, prod_b))

    logger.info(f"[relations] {len(pairs)} candidate pairs to evaluate")

    # Existing relations index (to avoid duplicates)
    existing = await db.product_relations.find(
        {"rule_id": rule_id},
        {"_id": 0, "product_id_a": 1, "product_id_b": 1},
    ).to_list(50000)
    existing_keys = {tuple(sorted([e["product_id_a"], e["product_id_b"]])) for e in existing}

    saved = 0
    # Process in batches
    for batch_start in range(0, len(pairs), CLAUDE_BATCH_SIZE):
        batch = pairs[batch_start: batch_start + CLAUDE_BATCH_SIZE]
        try:
            results = _claude_check_compatibility(batch, description)
        except Exception as exc:
            logger.error(f"[relations] Claude batch failed: {exc}")
            continue

        for res, (prod_a, prod_b) in zip(results, batch):
            if not res.get("compatible"):
                continue
            confidence = (res.get("confidence") or "").lower()
            if confidence == "low":
                continue  # discard low confidence

            pair_key = tuple(sorted([prod_a["id"], prod_b["id"]]))
            if pair_key in existing_keys:
                continue  # already saved

            doc = {
                "id": str(uuid.uuid4()),
                "rule_id": rule_id,
                "rule_title": rule["title"],
                "product_id_a": prod_a["id"],
                "crm_code_a": prod_a.get("crm_code", ""),
                "title_a": prod_a.get("title_en", ""),
                "product_id_b": prod_b["id"],
                "crm_code_b": prod_b.get("crm_code", ""),
                "title_b": prod_b.get("title_en", ""),
                "confidence": confidence,
                "reason": res.get("reason", ""),
                "source": "ai",
                "created_at": now_iso(),
            }
            await db.product_relations.insert_one(doc)
            existing_keys.add(pair_key)
            saved += 1

    await db.relation_rules.update_one(
        {"_id": ObjectId(rule_id)},
        {"$set": {"last_run_at": now_iso()}},
    )
    logger.info(f"[relations] Rule '{rule['title']}' done — {saved} new relations saved")


@router.post("/rules/{rule_id}/run", status_code=202)
async def run_relation_rule(
    rule_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    if not (current_user.get("isAdmin") or current_user.get("role") in ("admin", "manager")):
        raise HTTPException(status_code=403, detail="Admin or Manager required")
    db = get_db()
    rule = await db.relation_rules.find_one({"_id": ObjectId(rule_id)})
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    background_tasks.add_task(_run_rule_analysis, rule_id)
    return {"message": "Analysis started", "rule_id": rule_id}


# ==================== GET COMPATIBLE PRODUCTS ====================

@router.get("/{crm_code}")
async def get_related_products(
    crm_code: str,
    current_user: dict = Depends(get_current_user),
):
    """Return AI-generated compatible products for a given CRM code."""
    db = get_db()

    product = await db.product_catalog.find_one(
        {"crm_code": crm_code, "is_active": True},
        {"_id": 0, "id": 1},
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product_id = product["id"]

    # Find all AI relations where this product appears on either side
    raw = await db.product_relations.find(
        {
            "$or": [
                {"product_id_a": product_id},
                {"product_id_b": product_id},
            ]
        },
        {"_id": 0},
    ).to_list(100)

    if not raw:
        return []

    # Collect the "other" product ids
    other_ids = []
    relation_meta = {}
    for r in raw:
        if r["product_id_a"] == product_id:
            other_id = r["product_id_b"]
            other_title = r.get("title_b", "")
            other_crm = r.get("crm_code_b", "")
        else:
            other_id = r["product_id_a"]
            other_title = r.get("title_a", "")
            other_crm = r.get("crm_code_a", "")
        other_ids.append(other_id)
        relation_meta[other_id] = {
            "confidence": r.get("confidence"),
            "reason": r.get("reason"),
            "title": other_title,
            "crm_code": other_crm,
            "rule_title": r.get("rule_title", ""),
        }

    # Enrich with full product data
    products = await db.product_catalog.find(
        {"id": {"$in": other_ids}, "is_active": True},
        {"_id": 0, "id": 1, "title_en": 1, "article_number": 1, "crm_code": 1,
         "vendor": 1, "root_category": 1, "price": 1, "datasheet_url": 1},
    ).to_list(100)

    result = []
    for p in products:
        meta = relation_meta.get(p["id"], {})
        result.append({
            **p,
            "confidence": meta.get("confidence"),
            "reason": meta.get("reason"),
            "rule_title": meta.get("rule_title", ""),
            "relation_source": "ai",
        })

    # Sort: high confidence first
    order = {"high": 0, "medium": 1, "low": 2}
    result.sort(key=lambda x: order.get(x.get("confidence", "low"), 2))

    return result


@router.get("/{crm_code}/public")
async def get_related_products_public(crm_code: str):
    """Public endpoint — no auth required. For external website usage."""
    db = get_db()

    product = await db.product_catalog.find_one(
        {"crm_code": crm_code, "is_active": True},
        {"_id": 0, "id": 1},
    )
    if not product:
        return []

    product_id = product["id"]

    raw = await db.product_relations.find(
        {
            "$or": [
                {"product_id_a": product_id},
                {"product_id_b": product_id},
            ]
        },
        {"_id": 0},
    ).to_list(100)

    if not raw:
        return []

    other_ids = []
    relation_meta = {}
    for r in raw:
        if r["product_id_a"] == product_id:
            other_id = r["product_id_b"]
            other_crm = r.get("crm_code_b", "")
        else:
            other_id = r["product_id_a"]
            other_crm = r.get("crm_code_a", "")
        other_ids.append(other_id)
        relation_meta[other_id] = {
            "confidence": r.get("confidence"),
            "reason": r.get("reason"),
            "crm_code": other_crm,
        }

    products = await db.product_catalog.find(
        {"id": {"$in": other_ids}, "is_active": True},
        {"_id": 0, "id": 1, "title_en": 1, "article_number": 1, "crm_code": 1,
         "vendor": 1, "root_category": 1, "price": 1, "datasheet_url": 1},
    ).to_list(100)

    result = []
    for p in products:
        meta = relation_meta.get(p["id"], {})
        result.append({
            **p,
            "confidence": meta.get("confidence"),
            "reason": meta.get("reason"),
        })

    order = {"high": 0, "medium": 1, "low": 2}
    result.sort(key=lambda x: order.get(x.get("confidence", "low"), 2))
    return result
