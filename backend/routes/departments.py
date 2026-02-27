"""
Department Routes - Enterprise Knowledge Architecture
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/departments", tags=["departments"])


def setup_department_routes(db, get_current_user, is_admin, audit_service):
    """Setup department routes with dependencies"""
    
    @router.get("", response_model=List[dict])
    async def list_departments(current_user: dict = Depends(get_current_user)):
        """List all departments (admin sees all, users see their own)"""
        if is_admin(current_user["email"]):
            departments = await db.departments.find({}, {"_id": 0}).to_list(100)
        else:
            # Users see departments they belong to
            user_dept_ids = current_user.get("departments", [])
            departments = await db.departments.find(
                {"id": {"$in": user_dept_ids}},
                {"_id": 0}
            ).to_list(100)
        
        # Add member count
        for dept in departments:
            dept["memberCount"] = len(dept.get("members", []))
            dept["managerCount"] = len(dept.get("managers", []))
        
        return departments
    
    @router.post("", response_model=dict)
    async def create_department(
        data: dict,
        current_user: dict = Depends(get_current_user)
    ):
        """Create department (admin only)"""
        if not is_admin(current_user["email"]):
            raise HTTPException(status_code=403, detail="Admin only")
        
        dept_id = str(uuid.uuid4())
        department = {
            "id": dept_id,
            "name": data.get("name", "").strip(),
            "description": data.get("description", ""),
            "managers": [],
            "members": [],
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": None
        }
        
        if not department["name"]:
            raise HTTPException(status_code=400, detail="Name is required")
        
        await db.departments.insert_one(department)
        
        # Audit log
        await audit_service.log(
            entity="department",
            entity_id=dept_id,
            entity_name=department["name"],
            action="create",
            user_id=current_user["id"],
            user_email=current_user["email"],
            level="department"
        )
        
        # Return without _id
        department.pop("_id", None)
        return department
    
    @router.get("/{department_id}", response_model=dict)
    async def get_department(
        department_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Get department details"""
        department = await db.departments.find_one(
            {"id": department_id},
            {"_id": 0}
        )
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        
        # Check access
        if not is_admin(current_user["email"]):
            user_depts = current_user.get("departments", [])
            if department_id not in user_depts:
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Enrich with user details
        member_ids = [m.get("userId") for m in department.get("members", [])]
        users = await db.users.find(
            {"id": {"$in": member_ids}},
            {"_id": 0, "passwordHash": 0}
        ).to_list(100)
        user_map = {u["id"]: u for u in users}
        
        enriched_members = []
        for member in department.get("members", []):
            user = user_map.get(member.get("userId"), {})
            enriched_members.append({
                **member,
                "email": user.get("email", member.get("email", "")),
                "isManager": member.get("userId") in department.get("managers", [])
            })
        
        department["members"] = enriched_members
        
        # Get source count
        source_count = await db.sources.count_documents({
            "departmentId": department_id,
            "level": "department"
        })
        department["sourceCount"] = source_count
        
        return department
    
    @router.put("/{department_id}", response_model=dict)
    async def update_department(
        department_id: str,
        data: dict,
        current_user: dict = Depends(get_current_user)
    ):
        """Update department (admin or manager)"""
        department = await db.departments.find_one({"id": department_id}, {"_id": 0})
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        
        # Check permission
        is_manager = current_user["id"] in department.get("managers", [])
        if not is_admin(current_user["email"]) and not is_manager:
            raise HTTPException(status_code=403, detail="Admin or manager only")
        
        # Track changes for audit
        changes = {}
        updates = {"updatedAt": datetime.now(timezone.utc).isoformat()}
        
        if "name" in data and data["name"] != department.get("name"):
            changes["name"] = {"old": department.get("name"), "new": data["name"]}
            updates["name"] = data["name"].strip()
        
        if "description" in data and data["description"] != department.get("description"):
            changes["description"] = {"old": department.get("description"), "new": data["description"]}
            updates["description"] = data["description"]
        
        if updates:
            await db.departments.update_one(
                {"id": department_id},
                {"$set": updates}
            )
            
            if changes:
                await audit_service.log(
                    entity="department",
                    entity_id=department_id,
                    entity_name=department["name"],
                    action="update",
                    user_id=current_user["id"],
                    user_email=current_user["email"],
                    changes=changes,
                    level="department"
                )
        
        return await db.departments.find_one({"id": department_id}, {"_id": 0})
    
    @router.delete("/{department_id}")
    async def delete_department(
        department_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Delete department (admin only)"""
        if not is_admin(current_user["email"]):
            raise HTTPException(status_code=403, detail="Admin only")
        
        department = await db.departments.find_one({"id": department_id}, {"_id": 0})
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        
        # Check for department sources
        source_count = await db.sources.count_documents({
            "departmentId": department_id,
            "level": "department"
        })
        if source_count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete: department has {source_count} sources. Archive or move them first."
            )
        
        # Remove department from all users
        await db.users.update_many(
            {"departments": department_id},
            {"$pull": {"departments": department_id}}
        )
        await db.users.update_many(
            {"primaryDepartmentId": department_id},
            {"$set": {"primaryDepartmentId": None}}
        )
        
        await db.departments.delete_one({"id": department_id})
        
        await audit_service.log(
            entity="department",
            entity_id=department_id,
            entity_name=department["name"],
            action="delete",
            user_id=current_user["id"],
            user_email=current_user["email"],
            level="department"
        )
        
        return {"message": "Department deleted"}
    
    # ==================== MEMBER MANAGEMENT ====================
    
    @router.post("/{department_id}/members")
    async def add_department_member(
        department_id: str,
        data: dict,
        current_user: dict = Depends(get_current_user)
    ):
        """Add member to department (admin or manager)"""
        department = await db.departments.find_one({"id": department_id}, {"_id": 0})
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        
        # Check permission
        is_manager = current_user["id"] in department.get("managers", [])
        if not is_admin(current_user["email"]) and not is_manager:
            raise HTTPException(status_code=403, detail="Admin or manager only")
        
        user_id = data.get("userId")
        is_new_manager = data.get("isManager", False)
        
        # Verify user exists
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "passwordHash": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if already member
        existing_member = next(
            (m for m in department.get("members", []) if m.get("userId") == user_id),
            None
        )
        if existing_member:
            raise HTTPException(status_code=400, detail="User already a member")
        
        # Add member
        new_member = {
            "userId": user_id,
            "email": user["email"],
            "isManager": is_new_manager,
            "joinedAt": datetime.now(timezone.utc).isoformat()
        }
        
        update_ops = {
            "$push": {"members": new_member}
        }
        
        if is_new_manager:
            update_ops["$addToSet"] = {"managers": user_id}
        
        await db.departments.update_one({"id": department_id}, update_ops)
        
        # Add department to user
        user_update = {"$addToSet": {"departments": department_id}}
        # Set as primary if user has no primary department
        if not user.get("primaryDepartmentId"):
            user_update["$set"] = {"primaryDepartmentId": department_id}
        
        await db.users.update_one({"id": user_id}, user_update)
        
        await audit_service.log(
            entity="department",
            entity_id=department_id,
            entity_name=department["name"],
            action="update",
            user_id=current_user["id"],
            user_email=current_user["email"],
            changes={"members": {"added": user["email"]}},
            metadata={"newMember": user_id, "isManager": is_new_manager},
            level="department"
        )
        
        return {"message": f"Added {user['email']} to department", "member": new_member}
    
    @router.delete("/{department_id}/members/{user_id}")
    async def remove_department_member(
        department_id: str,
        user_id: str,
        current_user: dict = Depends(get_current_user)
    ):
        """Remove member from department"""
        department = await db.departments.find_one({"id": department_id}, {"_id": 0})
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        
        is_manager = current_user["id"] in department.get("managers", [])
        if not is_admin(current_user["email"]) and not is_manager:
            raise HTTPException(status_code=403, detail="Admin or manager only")
        
        # Remove from department
        await db.departments.update_one(
            {"id": department_id},
            {
                "$pull": {
                    "members": {"userId": user_id},
                    "managers": user_id
                }
            }
        )
        
        # Remove from user
        await db.users.update_one(
            {"id": user_id},
            {"$pull": {"departments": department_id}}
        )
        
        # Clear primary if this was it
        await db.users.update_one(
            {"id": user_id, "primaryDepartmentId": department_id},
            {"$set": {"primaryDepartmentId": None}}
        )
        
        return {"message": "Member removed"}
    
    @router.put("/{department_id}/members/{user_id}/manager")
    async def toggle_manager_status(
        department_id: str,
        user_id: str,
        data: dict,
        current_user: dict = Depends(get_current_user)
    ):
        """Toggle manager status for a member (admin only for promoting to manager)"""
        department = await db.departments.find_one({"id": department_id}, {"_id": 0})
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")
        
        is_manager_action = data.get("isManager", False)
        
        # Only admin can promote to manager
        if is_manager_action and not is_admin(current_user["email"]):
            raise HTTPException(status_code=403, detail="Only admin can promote to manager")
        
        # Current managers can demote other managers (but not themselves)
        is_current_manager = current_user["id"] in department.get("managers", [])
        if not is_manager_action and not is_admin(current_user["email"]) and not is_current_manager:
            raise HTTPException(status_code=403, detail="Permission denied")
        
        if user_id == current_user["id"] and not is_manager_action:
            raise HTTPException(status_code=400, detail="Cannot demote yourself")
        
        if is_manager_action:
            await db.departments.update_one(
                {"id": department_id},
                {"$addToSet": {"managers": user_id}}
            )
            # Update member record
            await db.departments.update_one(
                {"id": department_id, "members.userId": user_id},
                {"$set": {"members.$.isManager": True}}
            )
        else:
            await db.departments.update_one(
                {"id": department_id},
                {"$pull": {"managers": user_id}}
            )
            await db.departments.update_one(
                {"id": department_id, "members.userId": user_id},
                {"$set": {"members.$.isManager": False}}
            )
        
        return {"message": f"Manager status updated to {is_manager_action}"}
    
    return router
