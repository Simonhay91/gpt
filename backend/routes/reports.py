"""Message report routes — collect AI response feedback from users"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from middleware.auth import get_current_user
from db.connection import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["reports"])


class CreateReportRequest(BaseModel):
    messageId: str
    chatId: str
    tags: List[str]
    comment: Optional[str] = None
    messageContent: str
    userQuestion: Optional[str] = None
    chatHistory: Optional[List[dict]] = None
    activeSources: Optional[List[str]] = None
    agentType: Optional[str] = None


@router.post("/reports")
async def create_report(data: CreateReportRequest, current_user: dict = Depends(get_current_user)):
    db = get_db()

    existing = await db.reports.find_one({"messageId": data.messageId, "userId": current_user["id"]})
    if existing:
        raise HTTPException(status_code=409, detail="Already reported")

    report = {
        "id": str(uuid.uuid4()),
        "messageId": data.messageId,
        "chatId": data.chatId,
        "userId": current_user["id"],
        "userEmail": current_user.get("email", ""),
        "tags": data.tags,
        "comment": data.comment or "",
        "messageContent": data.messageContent,
        "userQuestion": data.userQuestion or "",
        "chatHistory": data.chatHistory or [],
        "activeSources": data.activeSources or [],
        "agentType": data.agentType or "",
        "status": "open",
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    await db.reports.insert_one(report)
    return {"success": True, "reportId": report["id"]}


@router.get("/admin/reports")
async def get_reports(
    status: Optional[str] = None,
    tag: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    current_user: dict = Depends(get_current_user)
):
    if not current_user.get("isAdmin"):
        raise HTTPException(status_code=403, detail="Admin only")

    db = get_db()
    query = {}
    if status:
        query["status"] = status
    if tag:
        query["tags"] = tag

    total = await db.reports.count_documents(query)
    reports = await db.reports.find(query, {"_id": 0}).sort("createdAt", -1).skip(skip).limit(limit).to_list(limit)
    return {"items": reports, "total": total}


@router.patch("/admin/reports/{report_id}")
async def update_report_status(
    report_id: str,
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    if not current_user.get("isAdmin"):
        raise HTTPException(status_code=403, detail="Admin only")

    db = get_db()
    allowed = {"status", "adminNote"}
    update = {k: v for k, v in data.items() if k in allowed}
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")

    update["updatedAt"] = datetime.now(timezone.utc).isoformat()
    result = await db.reports.update_one({"id": report_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"success": True}
