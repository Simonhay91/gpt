"""
Admin — Roles & Permissions management.

Endpoints:
    GET    /api/admin/permissions/registry       → RESOURCES dict (for UI matrix)
    GET    /api/admin/roles                      → list all roles
    POST   /api/admin/roles                      → create custom role
    GET    /api/admin/roles/{role_id}            → get one role
    PUT    /api/admin/roles/{role_id}            → update role (name / description / permissions)
    DELETE /api/admin/roles/{role_id}            → soft-delete (system roles protected)
    PUT    /api/admin/users/{user_id}/role       → assign role to user
    PUT    /api/admin/users/{user_id}/permission-grants   → set per-user grants
    PUT    /api/admin/users/{user_id}/permission-revokes  → set per-user revokes
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from db.connection import get_db
from middleware.permissions import RESOURCES, require, log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["roles"])


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────────────────────────────────────

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    permissions: List[str] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class AssignRoleRequest(BaseModel):
    roleId: str


class PermissionOverridesRequest(BaseModel):
    permissions: List[str]  # list of "resource:action" strings


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _validate_permissions(permissions: List[str]) -> List[str]:
    """Validate each permission string is a known resource:action pair."""
    valid = {f"{r}:{a}" for r, actions in RESOURCES.items() for a in actions}
    valid.add("*")
    invalid = [p for p in permissions if p not in valid]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown permissions: {invalid}. "
                   f"Check GET /api/admin/permissions/registry for the full list.",
        )
    return permissions


def _serialize_role(role: dict) -> dict:
    role.pop("_id", None)
    return role


# ──────────────────────────────────────────────────────────────────────────────
# Permission registry (for frontend UI)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/admin/permissions/registry")
async def get_permissions_registry(actor=Depends(require("roles", "read"))):
    """Return the full resource/action registry for the permissions matrix UI."""
    return {
        "resources": RESOURCES,
        "allPermissions": [
            f"{r}:{a}" for r, actions in RESOURCES.items() for a in actions
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# Role CRUD
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/admin/roles")
async def list_roles(actor=Depends(require("roles", "read"))):
    """List all roles (excluding soft-deleted)."""
    db = get_db()
    roles = await db.roles.find(
        {"deletedAt": {"$exists": False}}, {"_id": 0}
    ).to_list(500)

    # Annotate each role with the count of users assigned to it
    for role in roles:
        role["userCount"] = await db.users.count_documents({"roleId": role["id"]})

    return roles


@router.post("/admin/roles", status_code=201)
async def create_role(data: RoleCreate, actor=Depends(require("roles", "create"))):
    """Create a new custom role."""
    db = get_db()

    _validate_permissions(data.permissions)

    # Name uniqueness check (case-insensitive)
    existing = await db.roles.find_one(
        {"name": {"$regex": f"^{data.name}$", "$options": "i"},
         "deletedAt": {"$exists": False}}
    )
    if existing:
        raise HTTPException(status_code=400, detail="A role with this name already exists.")

    now = datetime.now(timezone.utc).isoformat()
    role = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "description": data.description,
        "permissions": data.permissions,
        "isSystem": False,
        "createdAt": now,
        "updatedAt": now,
        "createdBy": actor["id"],
    }
    await db.roles.insert_one(role)
    await log_action(actor["id"], actor["email"], "role.create", "role", role["id"],
                     {"name": data.name})
    return _serialize_role(role)


@router.get("/admin/roles/{role_id}")
async def get_role(role_id: str, actor=Depends(require("roles", "read"))):
    """Get a single role by ID."""
    db = get_db()
    role = await db.roles.find_one(
        {"id": role_id, "deletedAt": {"$exists": False}}, {"_id": 0}
    )
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")
    role["userCount"] = await db.users.count_documents({"roleId": role_id})
    return role


@router.put("/admin/roles/{role_id}")
async def update_role(role_id: str, data: RoleUpdate, actor=Depends(require("roles", "update"))):
    """Update a role's name, description, or permissions."""
    db = get_db()
    role = await db.roles.find_one(
        {"id": role_id, "deletedAt": {"$exists": False}}, {"_id": 0}
    )
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")

    if role.get("isSystem") and role["id"] == "role_super_admin":
        raise HTTPException(status_code=403, detail="The super_admin role cannot be modified.")

    updates: dict = {"updatedAt": datetime.now(timezone.utc).isoformat()}

    if data.name is not None:
        if role.get("isSystem"):
            raise HTTPException(status_code=403, detail="System role names cannot be changed.")
        existing = await db.roles.find_one(
            {"name": {"$regex": f"^{data.name}$", "$options": "i"},
             "id": {"$ne": role_id},
             "deletedAt": {"$exists": False}}
        )
        if existing:
            raise HTTPException(status_code=400, detail="A role with this name already exists.")
        updates["name"] = data.name

    if data.description is not None:
        updates["description"] = data.description

    if data.permissions is not None:
        _validate_permissions(data.permissions)
        updates["permissions"] = data.permissions

    await db.roles.update_one({"id": role_id}, {"$set": updates})
    await log_action(actor["id"], actor["email"], "role.update", "role", role_id,
                     {"changes": list(updates.keys())})

    updated = await db.roles.find_one({"id": role_id}, {"_id": 0})
    return _serialize_role(updated)


@router.delete("/admin/roles/{role_id}")
async def delete_role(role_id: str, actor=Depends(require("roles", "delete"))):
    """
    Soft-delete a custom role.
    System roles and roles with assigned users are protected.
    """
    db = get_db()
    role = await db.roles.find_one(
        {"id": role_id, "deletedAt": {"$exists": False}}, {"_id": 0}
    )
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")

    if role.get("isSystem"):
        raise HTTPException(status_code=403, detail="System roles cannot be deleted.")

    user_count = await db.users.count_documents({"roleId": role_id})
    if user_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete role: {user_count} user(s) are assigned to it. "
                   f"Reassign them first.",
        )

    now = datetime.now(timezone.utc).isoformat()
    await db.roles.update_one(
        {"id": role_id},
        {"$set": {"deletedAt": now, "deletedBy": actor["id"]}},
    )
    await log_action(actor["id"], actor["email"], "role.delete", "role", role_id,
                     {"name": role.get("name")})
    return {"message": f"Role '{role['name']}' deleted."}


# ──────────────────────────────────────────────────────────────────────────────
# User → Role assignment
# ──────────────────────────────────────────────────────────────────────────────

@router.put("/admin/users/{user_id}/role")
async def assign_role_to_user(
    user_id: str,
    data: AssignRoleRequest,
    actor=Depends(require("roles", "assign")),
):
    """Assign a role to a user (replaces their current role)."""
    db = get_db()

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "roleId": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    role = await db.roles.find_one(
        {"id": data.roleId, "deletedAt": {"$exists": False}}, {"_id": 0, "name": 1}
    )
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")

    old_role_id = user.get("roleId")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"roleId": data.roleId}},
    )
    await log_action(
        actor["id"], actor["email"], "user.role_assign", "user", user_id,
        {"email": user["email"], "oldRoleId": old_role_id, "newRoleId": data.roleId,
         "newRoleName": role["name"]},
    )
    return {"message": f"Role '{role['name']}' assigned to {user['email']}."}


# ──────────────────────────────────────────────────────────────────────────────
# Per-user permission overrides
# ──────────────────────────────────────────────────────────────────────────────

@router.put("/admin/users/{user_id}/permission-grants")
async def set_permission_grants(
    user_id: str,
    data: PermissionOverridesRequest,
    actor=Depends(require("roles", "assign")),
):
    """
    Set per-user permission grants (permissions added on top of the role).
    Replaces the existing grant list.
    """
    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    _validate_permissions(data.permissions)

    await db.users.update_one(
        {"id": user_id},
        {"$set": {"permissionGrants": data.permissions}},
    )
    await log_action(actor["id"], actor["email"], "user.permission_grants_set", "user", user_id,
                     {"email": user["email"], "grants": data.permissions})
    return {"message": "Permission grants updated.", "grants": data.permissions}


@router.put("/admin/users/{user_id}/permission-revokes")
async def set_permission_revokes(
    user_id: str,
    data: PermissionOverridesRequest,
    actor=Depends(require("roles", "assign")),
):
    """
    Set per-user permission revokes (permissions removed from the role).
    Replaces the existing revoke list.
    """
    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    _validate_permissions(data.permissions)

    await db.users.update_one(
        {"id": user_id},
        {"$set": {"permissionRevokes": data.permissions}},
    )
    await log_action(actor["id"], actor["email"], "user.permission_revokes_set", "user", user_id,
                     {"email": user["email"], "revokes": data.permissions})
    return {"message": "Permission revokes updated.", "revokes": data.permissions}
