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
    canEditProductCatalog: Optional[bool] = False
    departments: Optional[List[str]] = []
    primaryDepartmentId: Optional[str] = None
    mustChangePassword: Optional[bool] = False


class UserWithUsageResponse(BaseModel):
    id: str
    email: str
    isAdmin: bool
    createdAt: str
    totalTokensUsed: int
    totalMessagesCount: int
    canEditGlobalSources: Optional[bool] = False
    canEditProductCatalog: Optional[bool] = False


class UpdateUserGlobalPermissionRequest(BaseModel):
    canEditGlobalSources: bool


class UpdateUserCatalogPermissionRequest(BaseModel):
    canEditProductCatalog: bool


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
    temp_file_id: Optional[str] = None  # ID of a temp file uploaded via /api/chat/upload-temp
    activeSourceIds: Optional[List[str]] = None  # Current checkbox state from frontend (avoids debounce race condition)
    forceWebSearch: Optional[bool] = None  # If True, always run Brave web search regardless of auto-logic


class MessageEditRequest(BaseModel):
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
    web_sources: Optional[List[dict]] = None  # Brave Search results: [{"title": str, "url": str}]
    clarifying_question: Optional[str] = None  # Clarifying question text
    clarifying_options: Optional[List[str]] = None  # Options for clarifying question
    fetchedUrls: Optional[List[str]] = None  # URLs whose content was fetched and used as context
    excel_file_id: Optional[str] = None      # ID of generated Excel file in /tmp/
    excel_preview: Optional[dict] = None     # Preview data for inline table display
    is_excel_clarification: Optional[bool] = False  # True when AI asked clarifying questions before Excel generation
    uploadedFile: Optional[dict] = None      # { name, fileType } for temp file badge in UI
    agent_type: Optional[str] = None         # Selected agent: excel | research | rag | general
    agent_name: Optional[str] = None         # Human-readable agent name


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
    ocrStatus: Optional[str] = None       # "processing" | "ready" | None
    ocrTotalPages: Optional[int] = None
    ocrProcessedPages: Optional[int] = None


class ActiveSourcesUpdate(BaseModel):
    sourceIds: Optional[List[str]] = None  # null = reset to "use all sources"


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


# ==================== AI PROFILE MODELS ====================

class AiProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    position: Optional[str] = None
    department_id: Optional[str] = None
    preferred_language: Optional[str] = None  # ru, en
    response_style: Optional[str] = None  # formal, casual, technical, simple
    custom_instruction: Optional[str] = None


class AiProfileResponse(BaseModel):
    display_name: Optional[str] = None
    position: Optional[str] = None
    department_id: Optional[str] = None
    preferred_language: Optional[str] = "ru"
    response_style: Optional[str] = "formal"
    custom_instruction: Optional[str] = None


class DepartmentAiContextUpdate(BaseModel):
    style: Optional[str] = None
    instruction: Optional[str] = None


class DepartmentAiContextResponse(BaseModel):
    style: Optional[str] = None
    instruction: Optional[str] = None


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


# ==================== COMPETITOR TRACKER MODELS ====================

class CompetitorProduct(BaseModel):
    id: str
    url: str
    title: Optional[str] = None
    cached_content: Optional[str] = None
    last_fetched: Optional[str] = None
    auto_refresh: bool = False
    refresh_interval_days: int = 7


class CompetitorProductCreate(BaseModel):
    url: str
    auto_refresh: bool = False
    refresh_interval_days: int = 7


class MatchedProduct(BaseModel):
    competitor_product_url: str
    our_product_ref: str  # Source ID
    match_type: str  # "auto" | "manual" | "category"


class CompetitorCreate(BaseModel):
    name: str
    website: str


class CompetitorUpdate(BaseModel):
    name: Optional[str] = None
    website: Optional[str] = None


class CompetitorResponse(BaseModel):
    id: str
    name: str
    website: str
    products: List[CompetitorProduct] = []
    matched_our_products: List[MatchedProduct] = []
    created_by: str
    created_at: str


class CompetitorMatchUpdate(BaseModel):
    matched_our_products: List[MatchedProduct]


# ==================== PRODUCT CATALOG MODELS ====================

class ProductRelation(BaseModel):
    product_id: str
    relation_type: Literal["compatible", "bundle", "requires"]


class ProductCatalogCreate(BaseModel):
    article_number: str
    title_en: str
    crm_code: Optional[str] = None
    root_category: Optional[str] = None
    lvl1_subcategory: Optional[str] = None
    lvl2_subcategory: Optional[str] = None
    lvl3_subcategory: Optional[str] = None
    vendor: Optional[str] = None
    description: Optional[str] = None
    features: Optional[str] = None
    attribute_values: Optional[str] = None
    product_model: Optional[str] = None
    datasheet_url: Optional[str] = None
    aliases: Optional[List[str]] = []
    price: Optional[float] = None
    extra_fields: Optional[dict] = None


class ProductCatalogUpdate(BaseModel):
    title_en: Optional[str] = None
    crm_code: Optional[str] = None
    root_category: Optional[str] = None
    lvl1_subcategory: Optional[str] = None
    lvl2_subcategory: Optional[str] = None
    lvl3_subcategory: Optional[str] = None
    vendor: Optional[str] = None
    description: Optional[str] = None
    features: Optional[str] = None
    attribute_values: Optional[str] = None
    product_model: Optional[str] = None
    datasheet_url: Optional[str] = None
    aliases: Optional[List[str]] = None
    price: Optional[float] = None
    extra_fields: Optional[dict] = None


class ProductCatalogResponse(BaseModel):
    id: str
    article_number: str
    title_en: str
    crm_code: Optional[str] = None
    root_category: Optional[str] = None
    lvl1_subcategory: Optional[str] = None
    lvl2_subcategory: Optional[str] = None
    lvl3_subcategory: Optional[str] = None
    vendor: Optional[str] = None
    description: Optional[str] = None
    features: Optional[str] = None
    attribute_values: Optional[str] = None
    product_model: Optional[str] = None
    datasheet_url: Optional[str] = None
    aliases: List[str] = []
    price: Optional[float] = None
    relations: List[ProductRelation] = []
    extra_fields: Optional[dict] = None
    is_active: bool = True
    last_synced_at: Optional[str] = None
    source: str = "manual"
    created_by: str
    updated_by: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class ProductRelationCreate(BaseModel):
    product_id: str
    relation_type: Literal["compatible", "bundle", "requires"]


class ProductImportResult(BaseModel):
    added: int
    updated: int
    deactivated: int
    skipped: int
    errors: List[str] = []


class ProductMatchRequest(BaseModel):
    titles: List[str]


class ProductMatchResult(BaseModel):
    query: str
    matched: Optional[ProductCatalogResponse] = None
    confidence: float = 0.0
