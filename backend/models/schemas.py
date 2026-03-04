"""Pydantic models for request/response schemas"""
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal


# ==================== AUTH MODELS ====================

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    isAdmin: bool
    createdAt: str
    canEditGlobalSources: Optional[bool] = False
    departments: Optional[List[str]] = []
    primaryDepartmentId: Optional[str] = None


class UserWithUsageResponse(BaseModel):
    id: str
    email: str
    isAdmin: bool
    createdAt: str
    totalTokensUsed: int
    totalMessagesCount: int
    canEditGlobalSources: Optional[bool] = False


class UpdateUserGlobalPermissionRequest(BaseModel):
    canEditGlobalSources: bool


class TokenResponse(BaseModel):
    token: str
    user: UserResponse


# ==================== PROJECT MODELS ====================

class ProjectCreate(BaseModel):
    name: str


class ProjectMember(BaseModel):
    userId: str
    email: str
    role: str  # viewer, editor, manager


class ProjectResponse(BaseModel):
    id: str
    name: str
    ownerId: str
    sharedWith: Optional[List[str]] = []
    sharedMembers: Optional[List[ProjectMember]] = []
    createdAt: str


class ShareProjectRequest(BaseModel):
    email: str
    role: Optional[str] = "viewer"


# ==================== CHAT MODELS ====================

class ChatCreate(BaseModel):
    name: Optional[str] = "New Chat"


class ChatResponse(BaseModel):
    id: str
    projectId: Optional[str] = None
    name: str
    createdAt: str
    activeSourceIds: Optional[List[str]] = []
    sharedWithUsers: Optional[List[str]] = None
    sourceMode: Optional[str] = "all"


class QuickChatCreate(BaseModel):
    name: Optional[str] = "Quick Chat"


class MoveChatRequest(BaseModel):
    targetProjectId: str


class RenameChatRequest(BaseModel):
    name: str


class UpdateChatVisibilityRequest(BaseModel):
    sharedWithUsers: List[str]


class SourceModeUpdate(BaseModel):
    sourceMode: str  # 'all' or 'my'


# ==================== MESSAGE MODELS ====================

class MessageCreate(BaseModel):
    content: str


class EnhancedCitation(BaseModel):
    """Enhanced citation with full context"""
    sourceId: str
    sourceName: str
    sourceType: str
    chunkId: str
    chunkIndex: int
    textFragment: str
    score: float


class MessageResponse(BaseModel):
    id: str
    chatId: str
    role: Literal["user", "assistant"]
    content: str
    createdAt: str
    citations: Optional[List[dict]] = None
    usedSources: Optional[List[dict]] = None
    autoIngestedUrls: Optional[List[str]] = None
    senderEmail: Optional[str] = None
    senderName: Optional[str] = None
    fromCache: Optional[bool] = False
    cacheInfo: Optional[dict] = None


# ==================== SOURCE MODELS ====================

class SourceResponse(BaseModel):
    id: str
    projectId: str
    kind: Literal["file", "url", "knowledge"]
    originalName: Optional[str] = None
    url: Optional[str] = None
    mimeType: Optional[str] = None
    sizeBytes: Optional[int] = None
    createdAt: str
    chunkCount: int


class ActiveSourcesUpdate(BaseModel):
    sourceIds: List[str]


class UrlSourceCreate(BaseModel):
    url: str


class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 20


class SearchResult(BaseModel):
    sourceId: str
    sourceName: str
    sourceKind: str
    chunkIndex: int
    content: str
    matchCount: int


# ==================== GPT CONFIG MODELS ====================

class GPTConfigUpdate(BaseModel):
    model: Optional[str] = None
    developerPrompt: Optional[str] = None


class GPTConfigResponse(BaseModel):
    id: str
    model: str
    developerPrompt: str
    updatedAt: str


# ==================== USER PROMPT MODELS ====================

class UserPromptUpdate(BaseModel):
    customPrompt: Optional[str] = None


class UserPromptResponse(BaseModel):
    userId: str
    customPrompt: Optional[str] = None
    updatedAt: str


# ==================== IMAGE MODELS ====================

class ImageGenerateRequest(BaseModel):
    prompt: str
    size: Optional[str] = "1024x1024"


class GeneratedImageResponse(BaseModel):
    id: str
    projectId: str
    prompt: str
    imagePath: str
    imageUrl: str
    size: str
    createdAt: str


# ==================== SAVE TO KNOWLEDGE ====================

class SaveToKnowledgeRequest(BaseModel):
    content: str
    chatId: Optional[str] = None


# ==================== ADMIN MODELS ====================

class UpdateUserModelRequest(BaseModel):
    model: Optional[str] = None
