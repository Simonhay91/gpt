"""
Enterprise Knowledge Architecture Models
Levels: Personal → Project → Department → Global
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime
from enum import Enum


# ==================== ENUMS ====================

class SourceLevel(str, Enum):
    """Knowledge hierarchy levels"""
    PERSONAL = "personal"      # Private user drafts
    PROJECT = "project"        # Project-specific knowledge
    DEPARTMENT = "department"  # Department knowledge
    GLOBAL = "global"          # Corporate truth


class SourceStatus(str, Enum):
    """Approval workflow status for Department/Global sources"""
    DRAFT = "draft"           # Initial state, not visible to others
    PENDING = "pending"       # Submitted for approval
    APPROVED = "approved"     # Approved by manager/admin
    ACTIVE = "active"         # Currently active version
    ARCHIVED = "archived"     # Old version, kept for history


class AuditAction(str, Enum):
    """Audit log action types"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    REJECT = "reject"
    PUBLISH = "publish"
    RESTORE = "restore"


# ==================== DEPARTMENT MODELS ====================

class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class DepartmentMember(BaseModel):
    userId: str
    email: str
    isManager: bool = False
    joinedAt: str


class DepartmentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    managers: List[str] = []  # User IDs
    members: List[DepartmentMember] = []
    sourceCount: Optional[int] = 0
    createdAt: str
    updatedAt: Optional[str] = None


class AddDepartmentMemberRequest(BaseModel):
    userId: str
    isManager: bool = False


class SetPrimaryDepartmentRequest(BaseModel):
    departmentId: str


# ==================== ENHANCED USER MODEL ====================

class UserDepartmentInfo(BaseModel):
    departmentId: str
    departmentName: str
    isManager: bool


class EnhancedUserResponse(BaseModel):
    id: str
    email: str
    isAdmin: bool
    createdAt: str
    canEditGlobalSources: Optional[bool] = False
    primaryDepartmentId: Optional[str] = None
    departments: List[UserDepartmentInfo] = []


# ==================== SOURCE VERSION MODELS ====================

class SourceVersionMetadata(BaseModel):
    """Metadata for a source version"""
    sourceId: str
    version: int
    contentHash: str
    sizeBytes: int
    chunkCount: int
    createdBy: str
    createdByEmail: str
    createdAt: str
    changeDescription: Optional[str] = None
    previousVersion: Optional[int] = None


class SourceVersionResponse(BaseModel):
    id: str
    sourceId: str
    version: int
    contentHash: str
    sizeBytes: int
    chunkCount: int
    createdBy: str
    createdByEmail: str
    createdAt: str
    changeDescription: Optional[str] = None
    isActive: bool = False


class RestoreVersionRequest(BaseModel):
    version: int
    changeDescription: Optional[str] = "Restored from previous version"


# ==================== ENHANCED SOURCE MODELS ====================

class EnhancedSourceResponse(BaseModel):
    """Source with enterprise metadata"""
    id: str
    projectId: Optional[str] = None
    departmentId: Optional[str] = None
    level: SourceLevel
    status: SourceStatus = SourceStatus.ACTIVE
    kind: Literal["file", "url"]
    originalName: Optional[str] = None
    url: Optional[str] = None
    mimeType: Optional[str] = None
    sizeBytes: Optional[int] = None
    version: int = 1
    contentHash: str
    createdAt: str
    createdBy: str
    createdByEmail: Optional[str] = None
    updatedAt: Optional[str] = None
    chunkCount: int
    # Approval workflow
    approvedBy: Optional[str] = None
    approvedAt: Optional[str] = None
    rejectionReason: Optional[str] = None


class PublishSourceRequest(BaseModel):
    """Request to publish personal source to project/department"""
    targetLevel: Literal["project", "department"]
    targetId: str  # projectId or departmentId
    newName: Optional[str] = None  # Optional rename on publish


class ApprovalRequest(BaseModel):
    """Request to approve/reject a source"""
    action: Literal["approve", "reject"]
    comment: Optional[str] = None


# ==================== AUDIT LOG MODELS ====================

class AuditLogEntry(BaseModel):
    id: str
    entity: Literal["source", "department", "user", "config"]
    entityId: str
    entityName: Optional[str] = None
    action: AuditAction
    level: Optional[SourceLevel] = None
    userId: str
    userEmail: str
    changes: dict = {}  # {field: {old: x, new: y}}
    metadata: dict = {}  # Additional context
    timestamp: str
    ipAddress: Optional[str] = None


class AuditLogFilter(BaseModel):
    entity: Optional[str] = None
    entityId: Optional[str] = None
    action: Optional[str] = None
    level: Optional[str] = None
    userId: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    limit: int = 100
    offset: int = 0


# ==================== RETRIEVAL MODELS ====================

class RetrievalSource(BaseModel):
    """Source info for retrieval results"""
    sourceId: str
    sourceName: str
    level: SourceLevel
    departmentId: Optional[str] = None
    departmentName: Optional[str] = None
    projectId: Optional[str] = None
    chunkId: str
    chunkIndex: int
    content: str
    score: float


class RetrievalResult(BaseModel):
    """Result of hierarchical retrieval"""
    query: str
    totalChunks: int
    sources: List[RetrievalSource]
    levelCoverage: dict  # {level: chunk_count}
    conflictWarnings: List[str] = []  # Warnings about conflicting info
