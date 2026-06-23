"""
Central RBAC engine.

Usage in routes:
    from middleware.permissions import require

    @router.delete("/admin/users/{user_id}")
    async def delete_user(user_id: str, actor = Depends(require("users", "delete"))):
        ...

When adding a new feature that needs permission control, extend RESOURCES below
and call require() on every route that mutates or reads sensitive data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Set

from fastapi import Depends, HTTPException

from db.connection import get_db
from middleware.auth import get_current_user, is_admin

# ──────────────────────────────────────────────────────────────────────────────
# Resource / action registry — single source of truth.
# Frontend reads GET /api/admin/permissions/registry to build the matrix UI.
# ──────────────────────────────────────────────────────────────────────────────
RESOURCES: dict[str, list[str]] = {
    "users":           ["read", "create", "update", "delete", "reset_password"],
    "roles":           ["read", "create", "update", "delete", "assign"],
    "global_sources":  ["read", "create", "update", "delete", "approve"],
    "product_catalog": ["read", "create", "update", "delete", "import"],
    "departments":     ["read", "create", "update", "delete"],
    "competitors":     ["read", "create", "update", "delete"],
    "library":         ["read", "create", "update", "delete"],
    "news":            ["read", "manage"],
    "reports":         ["read"],
    "audit_logs":      ["read"],
    "config":          ["read", "update"],
    "oem_datasheet":   ["read", "create", "update", "delete"],
    "project_memory":  ["read", "update"],
    "chats":           ["read", "create", "delete"],
    "sources":         ["read", "create", "delete"],
    "cache":           ["read", "clear"],
    "backfill":        ["run"],
}

# ──────────────────────────────────────────────────────────────────────────────
# System roles — seeded on every startup (idempotent upsert).
# isSystem=True roles cannot be deleted via the API.
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM_ROLES: list[dict] = [
    {
        "id": "role_super_admin",
        "name": "Super Admin",
        "description": "Full access (auto-applied to @ai.planetworkspace.com accounts).",
        "isSystem": True,
        "permissions": ["*"],
    },
    {
        "id": "role_base",
        "name": "Base User",
        "description": "Default role for new users. Chats, own sources, and read-only content.",
        "isSystem": True,
        "permissions": [
            "global_sources:read",
            "product_catalog:read",
            "departments:read",
            "competitors:read",
            "library:read",
            "news:read",
            "oem_datasheet:read",
            "project_memory:read",
            "chats:read", "chats:create", "chats:delete",
            "sources:read", "sources:create", "sources:delete",
        ],
    },
    {
        "id": "role_viewer",
        "name": "Viewer",
        "description": "Read-only access to all non-admin sections.",
        "isSystem": True,
        "permissions": [
            "global_sources:read",
            "product_catalog:read",
            "departments:read",
            "competitors:read",
            "library:read",
            "news:read",
            "oem_datasheet:read",
            "project_memory:read",
            "chats:read",
            "sources:read",
        ],
    },
    {
        "id": "role_editor",
        "name": "Editor",
        "description": "Create and update content across all sections.",
        "isSystem": True,
        "permissions": [
            "global_sources:read", "global_sources:create", "global_sources:update",
            "product_catalog:read", "product_catalog:create",
            "product_catalog:update", "product_catalog:import",
            "departments:read",
            "competitors:read", "competitors:create", "competitors:update",
            "library:read", "library:create", "library:update",
            "news:read", "news:manage",
            "oem_datasheet:read", "oem_datasheet:create", "oem_datasheet:update",
            "project_memory:read", "project_memory:update",
            "chats:read", "chats:create", "chats:delete",
            "sources:read", "sources:create", "sources:delete",
        ],
    },
    {
        "id": "role_manager",
        "name": "Manager",
        "description": "Full content access including delete. No access to admin panel.",
        "isSystem": True,
        "permissions": [
            "global_sources:read", "global_sources:create",
            "global_sources:update", "global_sources:delete",
            "product_catalog:read", "product_catalog:create",
            "product_catalog:update", "product_catalog:delete", "product_catalog:import",
            "departments:read", "departments:create", "departments:update",
            "competitors:read", "competitors:create",
            "competitors:update", "competitors:delete",
            "library:read", "library:create", "library:update", "library:delete",
            "news:read", "news:manage",
            "oem_datasheet:read", "oem_datasheet:create",
            "oem_datasheet:update", "oem_datasheet:delete",
            "reports:read",
            "project_memory:read", "project_memory:update",
            "chats:read", "chats:create", "chats:delete",
            "sources:read", "sources:create", "sources:delete",
        ],
    },
]


# Department manager bonus permissions — mirrors the old check_manager_status logic.
# Users who are managers of any department get catalog and library write access,
# regardless of their base role. This preserves pre-RBAC behaviour.
_DEPT_MANAGER_PERMS = frozenset([
    "product_catalog:create", "product_catalog:update", "product_catalog:import",
    "library:create", "library:update",
])


# ──────────────────────────────────────────────────────────────────────────────
# Synchronous super-admin helper (no DB call needed)
# ──────────────────────────────────────────────────────────────────────────────

def is_super(user: dict) -> bool:
    """
    Return True when *user* has unrestricted (wildcard) access.

    This covers two cases:
    - Domain admin: @ai.planetworkspace.com email addresses.
    - Role-based super-admin: any user assigned role_super_admin explicitly,
      regardless of their email domain.

    Use this for data-scoping checks inside route handlers where the
    endpoint has already passed a require() gate and we just need to decide
    whether the user sees/edits ALL records vs. their own subset.
    """
    return is_admin(user.get("email", "")) or user.get("roleId") == "role_super_admin"


# ──────────────────────────────────────────────────────────────────────────────
# Core permission resolver
# ──────────────────────────────────────────────────────────────────────────────

async def resolve_permissions(user: dict) -> Set[str]:
    """
    Return the full permission set for *user*.

    Resolution order (later steps override earlier):
      1. Admin domain users → {"*"} (bypass everything).
      2. Role permissions from roles collection.
      3. Department-manager bonus perms (catalog/library write).
      4. Per-user permissionGrants (added on top of role).
      5. Per-user permissionRevokes (removed last, highest precedence).
    """
    if is_admin(user.get("email", "")):
        return {"*"}

    db = get_db()
    perms: set[str] = set()

    # Step 2 — role
    role_id = user.get("roleId")
    if role_id:
        role = await db.roles.find_one(
            {"id": role_id, "deletedAt": {"$exists": False}},
            {"_id": 0, "permissions": 1},
        )
        if role:
            perms.update(role.get("permissions", []))

    # Step 3 — department manager bonus (preserves pre-RBAC behaviour)
    user_id = user.get("id")
    if user_id:
        is_dept_manager = await db.departments.count_documents(
            {"managers": user_id}, limit=1
        )
        if is_dept_manager:
            perms.update(_DEPT_MANAGER_PERMS)

    # Steps 4 & 5 — per-user overrides
    perms.update(user.get("permissionGrants", []))
    perms.difference_update(user.get("permissionRevokes", []))

    return perms


# ──────────────────────────────────────────────────────────────────────────────
# FastAPI dependency factory
# ──────────────────────────────────────────────────────────────────────────────

def require(resource: str, action: str):
    """
    Return a FastAPI dependency that enforces permission *resource*:*action*.
    The dependency resolves to the authenticated user dict on success.
    """
    perm = f"{resource}:{action}"

    async def _dependency(current_user: dict = Depends(get_current_user)):
        perms = await resolve_permissions(current_user)
        if "*" not in perms and perm not in perms:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {perm}",
            )
        return current_user

    return _dependency


# ──────────────────────────────────────────────────────────────────────────────
# Audit log helper
# ──────────────────────────────────────────────────────────────────────────────

async def log_action(
    actor_id: str,
    actor_email: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    """
    Write a structured entry to the audit_logs collection.

    Schema is intentionally compatible with AuditService (enterprise.py) so that
    both kinds of entries are visible in the existing audit log viewer:
      entity / entityId / userId / userEmail / timestamp

    action examples: "user.delete", "role.create", "user.role_assign"
    """
    import uuid as _uuid

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": str(_uuid.uuid4()),
        # AuditService-compatible fields
        "entity": resource_type,
        "entityId": resource_id,
        "action": action,
        "userId": actor_id,
        "userEmail": actor_email,
        "timestamp": now,
        # Extra context (ignored by old viewer, useful for new one)
        "details": details or {},
    }
    try:
        await db.audit_logs.insert_one(entry)
    except Exception:
        pass  # audit failures must never break the main flow


# ──────────────────────────────────────────────────────────────────────────────
# Startup seeder
# ──────────────────────────────────────────────────────────────────────────────

async def seed_system_roles(db) -> None:
    """
    Idempotently upsert all SYSTEM_ROLES and run one-time data migrations:

    1. Roles — use $setOnInsert for permissions so admin UI changes survive
       server restarts. Exception: role_super_admin always enforces ["*"].
    2. Users — back-fill roleId=role_base for any user missing it.
    3. Flags — migrate canEditGlobalSources / canEditProductCatalog → permissionGrants
       so existing delegated users keep their access under the new RBAC system.
    """
    import logging
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)
    now = datetime.now(timezone.utc).isoformat()

    # ── 1. Seed system roles ──────────────────────────────────────────────────
    for role in SYSTEM_ROLES:
        if role["id"] == "role_super_admin":
            # super_admin's ["*"] must always be authoritative — no drift allowed.
            await db.roles.update_one(
                {"id": role["id"]},
                {
                    "$set": {**role, "updatedAt": now},
                    "$setOnInsert": {"createdAt": now},
                },
                upsert=True,
            )
        else:
            # For all other system roles: only set permissions on first insert.
            # If an admin has customised them via the UI those changes are kept.
            await db.roles.update_one(
                {"id": role["id"]},
                {
                    "$set": {
                        "name": role["name"],
                        "description": role["description"],
                        "isSystem": role["isSystem"],
                        "updatedAt": now,
                    },
                    "$setOnInsert": {
                        "permissions": role["permissions"],
                        "createdAt": now,
                    },
                },
                upsert=True,
            )

    # ── 2. Back-fill roleId ───────────────────────────────────────────────────
    result = await db.users.update_many(
        {"roleId": {"$exists": False}},
        {"$set": {
            "roleId": "role_base",
            "permissionGrants": [],
            "permissionRevokes": [],
        }},
    )
    if result.modified_count:
        logger.info(f"✓ Assigned role_base to {result.modified_count} existing user(s)")

    # ── 3. One-time flag → permissionGrants migration ─────────────────────────
    # canEditGlobalSources=True → grants [global_sources:create/update/delete]
    # canEditProductCatalog=True → grants [product_catalog:create/update/delete/import]
    # We never clear the old flags (backward-safe) but mark migration done with
    # a new field so we don't re-run on every restart.

    FLAG_MIGRATIONS = [
        (
            "canEditGlobalSources",
            ["global_sources:create", "global_sources:update", "global_sources:delete"],
        ),
        (
            "canEditProductCatalog",
            ["product_catalog:create", "product_catalog:update",
             "product_catalog:delete", "product_catalog:import"],
        ),
    ]

    for flag, new_grants in FLAG_MIGRATIONS:
        cursor = db.users.find(
            {flag: True, "flagsMigrated": {"$not": {"$elemMatch": {"$eq": flag}}}},
            {"_id": 0, "id": 1, "permissionGrants": 1},
        )
        async for user in cursor:
            existing = set(user.get("permissionGrants") or [])
            existing.update(new_grants)
            await db.users.update_one(
                {"id": user["id"]},
                {
                    "$set": {"permissionGrants": sorted(existing)},
                    "$addToSet": {"flagsMigrated": flag},
                },
            )
        migrated = await db.users.count_documents(
            {"flagsMigrated": {"$elemMatch": {"$eq": flag}}}
        )
        if migrated:
            logger.info(f"✓ Migrated {flag} → permissionGrants for {migrated} user(s)")

    logger.info(f"✓ System roles seeded ({len(SYSTEM_ROLES)} roles)")
