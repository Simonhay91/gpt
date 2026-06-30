# Planet Knowledge — Product Requirements Document (PRD)

## 0. Meta

| Field | Value |
|---|---|
| Document version | 2.0 |
| Last updated | 2026-06-30 |
| Maintained by | Boby (autonomous agent) + human review |

### Change Log

| Date | Version | Change |
|---|---|---|
| 2026-06-30 | 2.0 | Full rewrite from live codebase scan — supersedes `memory/PRD.md` v1.8 |

> **Maintained by Boby (autonomous agent) + human review.** Boby updates this document after completing each task. Humans review and approve changes before merging.

**Keywords:** meta, version, changelog, document history

---

## 1. Overview & Purpose

### 1.1 What is Planet Knowledge?

Planet Knowledge is an **enterprise AI knowledge platform** for mid-to-large companies. It centralises corporate documents, product catalogs, and web sources into a single, permission-controlled knowledge base and provides AI-powered chat on top of that knowledge.

### 1.2 Business Problem

Employees cannot quickly find answers spread across PDFs, Excel files, intranet pages, and product databases. Analysts waste hours searching documents and building Excel reports manually. Product teams lack a single view of their own catalog alongside competitor products.

Planet Knowledge solves this by:
- Ingesting and embedding all document types (PDF, DOCX, XLSX, CSV, PPTX, images, URLs)
- Exposing AI chat that cites sources, respects access control, and speaks multiple languages
- Providing specialised tools: product matching against an external catalog, competitor monitoring, OEM datasheet rebranding, and an interactive Excel assistant

### 1.3 End-to-End System Summary

```
User → React SPA → FastAPI backend → MongoDB (vectors + data)
                                   → Anthropic Claude (reasoning)
                                   → OpenAI (embeddings + image gen)
                                   → Brave Search (web search)
                                   → PlanetWorkspace API (catalog)
```

**Keywords:** overview, purpose, mission, product, what is planet knowledge

---

## 2. System Architecture

### 2.1 High-Level Components

| Component | Technology | Role |
|---|---|---|
| Frontend SPA | React 19, Tailwind CSS, Shadcn/UI | Browser UI |
| Backend API | Python 3.11, FastAPI 0.110, Uvicorn | REST API + AI orchestration |
| Database | MongoDB Atlas (motor async driver) | All persistence |
| Auth | JWT HS256 (PyJWT), bcrypt | Session management |
| AI backbone | Anthropic Claude + OpenAI | LLM + embeddings |
| File extraction | pdfplumber, markitdown, pytesseract OCR, python-docx, python-pptx | Document parsing |
| Web search | Brave Search API + httpx | Grounded web answers |
| Task scheduling | APScheduler (AsyncIOScheduler) | Cron background jobs |

### 2.2 Data Flow — Chat Message (RAG)

```
1. User sends message → POST /api/chats/{id}/messages
2. Agent router classifies intent → excel | research | rag | general | tutor
3. If rag/tutor: embed question (OpenAI text-embedding-3-small)
4. Check semantic cache (cosine sim ≥ 0.92)  →  if hit: return cached answer
5. Fetch relevant chunks from source_chunks (cosine sim, top-8, ≤ 20,000 chars)
6. (Optional) Brave web search if forceWebSearch or research intent
7. (Optional) Product catalog lookup
8. Build system prompt (GPT config + user AI profile + company info context)
9. Call Claude claude-sonnet-4-6 with context → stream response
10. Save message + citations → messages collection
11. Save answer to semantic cache
```

### 2.3 External Service Dependencies

| Service | Purpose | Auth method | Credential env var |
|---|---|---|---|
| MongoDB Atlas | All data | Connection string | `MONGO_URL` → `<MONGO_URL>` |
| Anthropic Claude | Main LLM (chat, routing, tutor summaries) | API key | `CLAUDE_API_KEY` → `<CLAUDE_API_KEY>` |
| OpenAI | Embeddings (`text-embedding-3-small`), fallback LLM (`gpt-4o-mini`), image gen (DALL-E 3) | API key | `OPENAI_API_KEY` → `<OPENAI_API_KEY>` |
| VoyageAI | Product matching embeddings (library installed, key in env) | API key | `VOYAGE_API_KEY` → `<VOYAGE_API_KEY>` |
| Brave Search | Web search grounding | API key | `BRAVE_API_KEY` → `<BRAVE_API_KEY>` |
| PlanetWorkspace API | External product catalog (`api-prod.planetworkspace.com`) | Partner key header | `PLANET_PARTNER_KEY` → `<PLANET_PARTNER_KEY>` |
| Timeweb Cloud (VPS) | Production hosting | SSH key (GitHub Secret) | `TIMEWEB_HOST`, `TIMEWEB_USER`, `TIMEWEB_SSH_KEY` |
| Emergent Agent | [UNKNOWN — needs human confirmation; `EMERGENT_LLM_KEY` env var exists but package commented out in `requirements.txt`] | API key | `EMERGENT_LLM_KEY` → `<EMERGENT_LLM_KEY>` |

> **Real values** for all credentials live in `backend/.env` (not committed). The root `.env.example` and `docker-compose.yml` show variable names only.

**Keywords:** architecture, components, data flow, external services, dependencies, infrastructure

---

## 3. Components / Modules

### 3.1 Entry Point — `backend/server.py`

- **Purpose:** FastAPI application factory. Registers all routers, configures CORS and timeout middleware, runs startup lifecycle events.
- **Key files:** `backend/server.py` (≈429 lines)
- **Startup actions (in order):**
  1. Auto-install Tesseract OCR if missing (`apt-get`)
  2. `init_admin_user()` — create/migrate default admin account (`admin@ai.planetworkspace.com` / `Admin@123456`, `mustChangePassword=True`)
  3. `seed_system_roles()` — upsert 5 system roles, back-fill `roleId=role_base` on existing users, migrate legacy permission flags
  4. `create_indexes()` — ensure all MongoDB indexes (idempotent, best-effort)
  5. Start APScheduler: competitor auto-refresh daily 2:00 AM; temp-file cleanup daily 3:00 AM
- **Request timeout:** 120 s hard ceiling via `RequestTimeoutMiddleware`; excluded paths: `/api/product-matching/match`, `/api/product-matching/research-item`, `/api/product-matching/generate-excel`, `/library/upload`
- **CORS:** `CORS_ORIGIN_REGEX` env var controls allowed origins (defaults to `.*` — permissive)

**Observations:** CORS defaults to `.*` (allow all); production should restrict this via `CORS_ORIGIN_REGEX`.

---

### 3.2 Database Layer — `backend/db/`

- **Purpose:** MongoDB connection singleton and index definitions.
- **Key files:**
  - `backend/db/connection.py` — `AsyncIOMotorClient`, `get_db()`, `get_client()`
  - `backend/db/indexes.py` — 22 index definitions across all major collections
- **Config:** `MONGO_URL` (Atlas connection string), `DB_NAME` (default: `gpt`)
- **Connection:** Module-level singleton client; shared across all async route handlers

**Observations:** No connection pooling configuration visible; Motor defaults apply. No read/write concern configured explicitly.

---

### 3.3 Authentication & Permissions — `backend/middleware/`

- **Purpose:** JWT token issuance/validation, RBAC enforcement, audit logging.
- **Key files:**
  - `backend/middleware/auth.py`
  - `backend/middleware/permissions.py`

#### 3.3.1 Auth (`auth.py`)

| Item | Value |
|---|---|
| Algorithm | HS256 |
| Expiry | 168 hours (7 days) |
| Secret source | `JWT_SECRET` env var — server crashes if unset |
| Admin domain | `@ai.planetworkspace.com` |

#### 3.3.2 RBAC (`permissions.py`)

Resolution order (later overrides earlier):
1. `@ai.planetworkspace.com` domain → wildcard `{"*"}` (bypass all checks)
2. Role permissions from `roles` collection (`roleId` on user)
3. Department-manager bonus: `product_catalog:create/update/import`, `library:create/update`
4. Per-user `permissionGrants` array
5. Per-user `permissionRevokes` array (highest precedence)

**System roles (seeded on startup, `isSystem=True`, cannot be deleted):**

| Role ID | Name | Key permissions |
|---|---|---|
| `role_super_admin` | Super Admin | `["*"]` |
| `role_base` | Base User | Read global/catalog/library/news; chat; own sources |
| `role_viewer` | Viewer | Read-only across all sections, no write |
| `role_editor` | Editor | Create/update content; manage news; no delete |
| `role_manager` | Manager | Full content CRUD; no admin panel access |

**Resources & actions** (full list in `middleware/permissions.py::RESOURCES`): `users`, `roles`, `global_sources`, `product_catalog`, `departments`, `competitors`, `library`, `news`, `reports`, `audit_logs`, `config`, `oem_datasheet`, `project_memory`, `chats`, `sources`, `cache`, `backfill`.

**Keywords:** auth, jwt, authentication, login, permissions, rbac, roles, access control, middleware

---

### 3.4 RAG Pipeline — `backend/services/rag.py`

- **Purpose:** Embedding generation, semantic chunk retrieval, company-info context injection, summary-query detection.
- **Key files:** `backend/services/rag.py`
- **Embedding model:** `text-embedding-3-small` (OpenAI), 1536 dimensions
- **Parameters:**
  - Max context: 20,000 characters per query
  - Max chunks returned: 8
  - Min score threshold: 0.30 (chunks below are dropped unless no chunks pass)
  - Fallback: keyword-overlap scoring (`score_chunk_relevance`) when embedding unavailable
  - Score boost: ×1.5 for explicitly @-mentioned source IDs (capped at 1.0)
- **Summary query handling:** Detects generic "summarize / analyze / overview" phrases (English, Russian, Armenian) via regex; for these, serves first 6 chunks per source (document overview) instead of top-similarity chunks
- **Company Info context:** A single source with `isCompanyInfo=True` in `__global__` project is always injected (≤ 2,500 chars) at the top of every chat context
- **Dimension mismatch handling:** Old Voyage 1024-dim embeddings in DB fall back to keyword scoring with 0.5× weight penalty

**Keywords:** rag, retrieval, embeddings, chunks, vector search, semantic search, cosine similarity

---

### 3.5 Semantic Cache — `backend/services/cache.py`

- **Purpose:** Cache AI answers to reduce token cost on repeated similar questions.
- **Key files:** `backend/services/cache.py`
- **Parameters:**
  - Similarity threshold: **0.92** cosine similarity
  - TTL: **30 days**
- **Cache key:** SHA-256 hash of `project_id + model + mode + dev_prompt_hash + user_prompt_hash + sorted_source_ids` — ensures zero data leakage across projects/contexts/modes
- **Security:** Before returning a cached answer, verifies the cached entry's `sourceIds` are all within the requesting user's accessible source set
- **Storage:** `semantic_cache` MongoDB collection

**Keywords:** cache, semantic cache, token cost, repeated questions

---

### 3.6 Agent System — `backend/services/agents.py` + `backend/services/agent_router.py`

- **Purpose:** Route each user message to the best-fit AI agent; each agent has a distinct system prompt.
- **Key files:**
  - `backend/services/agents.py` — agent definitions
  - `backend/services/agent_router.py` — routing logic

**Agents:**

| ID | Name | Triggers |
|---|---|---|
| `excel` | Excel Agent | Excel source active + excel/table keywords |
| `research` | Research Agent | Web search enabled + research keywords |
| `rag` | Knowledge Agent | RAG context available |
| `general` | Assistant | Fallback |
| `tutor` | Tutor | Chat `mode="tutor"` |

**Routing logic (in priority order):**
1. Rule-based keyword check (no API call)
2. If ambiguous: call `claude-sonnet-4-5` with `max_tokens=10` to classify
3. Falls back to `general` on any error or missing API key

**Keywords:** agent, routing, excel agent, research agent, tutor, knowledge agent

---

### 3.7 Message Handling — `backend/routes/messages.py`

- **Purpose:** Full send-message pipeline: agent routing → RAG → web search → product catalog → Claude response → cache save.
- **Key files:** `backend/routes/messages.py` (590+ lines)
- **Endpoints:** `POST /api/chats/{chatId}/messages`, `POST /api/chats/{chatId}/messages/stream`, `POST /api/messages/{id}/save-to-knowledge`, `PUT /api/messages/{id}`, `DELETE /api/messages/{id}`
- **Multi-file temp uploads:** Multiple temp files per message via `temp_file_ids` list
- **Web search:** Optional — triggered by `forceWebSearch=true` or auto-detected Brave keywords; uses `BRAVE_API_KEY`
- **Auto URL ingestion:** URLs mentioned in user messages are auto-fetched and injected as context
- **Library integration:** `get_accessible_library_source_ids()` resolves library items by user's departments + position + global flag
- **Tutor integration:** If chat `mode="tutor"`, auto-activates position-assigned library books; injects tutor progress note from `users.tutor_memory`
- **Source modes:** `all` (all accessible sources) vs `my` (user-owned only) vs `ai_only` (no RAG, pure LLM)
- **Primary model:** `claude-sonnet-4-6`; fallback to `gpt-4o-mini` if Claude key missing

**Keywords:** messages, chat, send message, RAG pipeline, web search, stream, response

---

### 3.8 Sources & File Processing

#### 3.8.1 Source Upload — `backend/routes/sources.py`, `backend/routes/enterprise_sources.py`

- **Purpose:** Upload files / add URLs, extract text, chunk, embed, store.
- **Key files:** `backend/routes/sources.py`, `backend/routes/enterprise_sources.py`, `backend/services/file_processor.py`
- **Max file size:** 50 MB
- **Supported formats:** PDF, DOCX, PPTX, XLSX, CSV, TXT, MD, PNG, JPG, GIF, WEBP
- **OCR:** Tesseract (English + Russian); auto-installed at startup if missing
- **Chunking:**
  - Text docs: 1,000-char chunks with 200-char overlap (`chunk_text`)
  - Tabular data (XLSX, CSV): one row per chunk with column headers prefix (`chunk_tabular_text`)
- **PDF pipeline:** markitdown → pdfplumber → pytesseract OCR (capped at 10 pages, 150 DPI for scanned PDFs)
- **Stored in:** `sources` collection + `source_chunks` collection (with OpenAI embeddings)
- **Upload storage:** `backend/uploads/` (Docker volume `backend_uploads`)

#### 3.8.2 Source Scope Hierarchy

```
Global (projectId="__global__")         — admin-managed, visible to all users
  └─ Department (departmentId=<id>)      — manager-approval workflow
       └─ Project (projectId=<id>)       — project members only
            └─ Personal (ownerId=<id>)   — user owns
Library (level="library")               — shared cross-dept, no approval workflow
```

**Keywords:** sources, file upload, document processing, chunks, embeddings, OCR, knowledge base

---

### 3.9 Library — `backend/routes/library.py`

- **Purpose:** Centrally managed document library; one file shared with multiple departments simultaneously.
- **Key files:** `backend/routes/library.py` (707+ lines), `frontend/src/pages/LibraryPage.js`
- **Data model:** `sources` collection with `level="library"`; key fields: `sharedDepartments` (array of dept IDs), `sharedPositions` (array of position strings), `isGlobalLibrary` (bool), `storagePath`
- **Chunks stored in:** `source_chunks` with `projectId="__library__"` (single copy, no duplication)
- **Max file size:** 50 MB; max chunks per item: 1,000
- **API prefix:** `/api/library`
- **Permissions:** Admin/Super-admin can share globally; dept managers can share to managed depts; members can read/download
- **Position-based access:** Items with `sharedPositions` matching user's AI profile position are auto-activated in Tutor chats

**Keywords:** library, shared documents, department library, books, position, tutor books

---

### 3.10 Tutor Mode — `backend/services/tutor.py`

- **Purpose:** Personal AI tutor that teaches from library books assigned to the user's corporate position; maintains per-book learning progress.
- **Key files:** `backend/services/tutor.py`, `frontend/src/pages/TutorPage.js`
- **Chat mode field:** `chats.mode = "tutor"`
- **Learning memory:** `users.tutor_memory.<book_id>` — `{summary, progressPercent, lastSession, updatedAt}` — capped at 500 chars per book
- **Summarization:** After tutor chat, Claude `claude-haiku-4-5-20251001` generates a teacher-style progress note; compacts when note exceeds cap
- **Auto-activation:** Position-matched library items are auto-added to active sources in tutor chats

**Keywords:** tutor, personal assistant, learning, progress, books, position-based

---

### 3.11 Admin Panel — `backend/routes/admin.py`

- **Purpose:** User management, GPT configuration, source statistics, permission management, cache management.
- **Key files:** `backend/routes/admin.py` (600+ lines)
- **Key API groups:**
  - `GET/POST/PUT/DELETE /api/admin/users` — user CRUD
  - `PUT /api/admin/users/{id}/position` — set corporate position
  - `GET/PUT /api/admin/gpt-config` — AI model + developer prompt config
  - `GET /api/admin/source-stats` — per-user source usage
  - `GET /api/admin/audit-logs` — filterable audit trail
  - `GET/DELETE /api/admin/semantic-cache` — inspect/clear cache
  - `GET /api/admin/permissions/registry` — RBAC resource/action registry for UI
  - `POST /api/admin/backfill-embeddings` — re-embed all chunks
- **GPT config stored in:** `gpt_config` collection (single document, id="1")

**Keywords:** admin, user management, gpt config, audit logs, permissions, cache, admin panel

---

### 3.12 Competitor Tracker — `backend/routes/competitors.py`

- **Purpose:** Monitor competitor product pages; scrape and cache content; match to internal products.
- **Key files:** `backend/routes/competitors.py` (400+ lines), `frontend/src/pages/CompetitorsPage.js`
- **API prefix:** `/api`
- **Endpoints:** `GET/POST /api/competitors`, `GET/PUT/DELETE /api/competitors/{id}`, `POST /api/competitors/{id}/products`, `POST /api/competitors/{id}/products/{pid}/refresh`, `PUT /api/competitors/{id}/match`
- **Scraping:** httpx + BeautifulSoup (lxml); strips nav/footer/scripts; 3,000-char content cap per URL
- **Auto-refresh:** APScheduler job runs daily at 2:00 AM; refreshes products with `auto_refresh=True` and past `refresh_interval_days`
- **Storage:** `competitors` MongoDB collection

**Keywords:** competitors, competitor tracker, scraping, monitoring, competitor products

---

### 3.13 Product Catalog — `backend/routes/product_catalog.py`, `backend/routes/product_relations.py`

- **Purpose:** Internal product catalog CRUD; keyword search; cross-product relations.
- **Key files:** `backend/routes/product_catalog.py`, `backend/routes/product_relations.py`, `backend/services/catalog_service.py`
- **API prefix:** `/api/product-catalog`
- **Search:** Regex-based across `title_en`, `article_number`, `vendor`, `product_model`, `description`, `aliases`
- **Storage:** `product_catalog` MongoDB collection
- **Relations:** `compatible`, `bundle`, `requires` links between product IDs

**Keywords:** product catalog, internal catalog, product search, relations, article number

---

### 3.14 PlanetWorkspace Catalog Integration — `backend/services/planet_api.py`

- **Purpose:** Fetch external product catalog from PlanetWorkspace API; normalize; cache embeddings; expose for product matching.
- **Key files:** `backend/services/planet_api.py`, `backend/routes/planet_catalog.py`
- **External API base URL:** `PLANET_API_URL` (default: `https://api-prod.planetworkspace.com`); auth via `x-partner-key: <PLANET_PARTNER_KEY>` header
- **Caching:**
  - In-memory: 10-minute TTL per category key; asyncio lock prevents cache stampede
  - MongoDB: `planet_category_cache` (5-hour TTL), `planet_embedding_cache` (24-hour TTL), `planet_attr_cache` (5-hour TTL), `planet_brand_cache` (5-min TTL)
- **Embeddings:** OpenAI `text-embedding-3-small` in batches of 100
- **Pagination:** `/web/product/explore` POST, page limit 500, safety cap 5,000 products

**Keywords:** planet catalog, planetworkspace, external catalog, partner API, product sync

---

### 3.15 Product Matching — `backend/routes/product_matching.py`

- **Purpose:** Upload customer product list (XLSX/CSV), AI-match each item against the PlanetWorkspace catalog, generate output Excel with matched products and datasheet links.
- **Key files:** `backend/routes/product_matching.py` (1,400+ lines)
- **Max file size:** 20 MB; max customer items: 200; max catalog products: 5,000
- **3-phase pipeline:**
  1. **Embedding similarity** (OpenAI/VoyageAI): find top-10 catalog candidates per customer item
  2. **Claude batch matching** (`claude-sonnet-4-5`, batches of 30): select best match or "no match"
  3. **Web research fallback** (Brave Search): for unmatched items, fetch web context then re-ask Claude
- **Output:** Excel file with customer items + matched catalog products + confidence + datasheet URLs
- **Storage:** Generated Excel files → `/tmp/` (ephemeral) + `excel_files` MongoDB collection (mirror for pod-restart resilience)
- **API prefix:** `/api/product-matching`
- **Excluded from timeout middleware** (can run several minutes)

**Keywords:** product matching, AI matching, customer product list, Excel output, catalog matching

---

### 3.16 OEM Datasheet Rebrander — `backend/routes/oem_datasheet.py`

- **Purpose:** Upload OEM PPTX/DOCX datasheets; replace vendor branding with customer brand (colors, logos, text); download rebranded file.
- **Key files:** `backend/routes/oem_datasheet.py` (1,000+ lines), `frontend/src/pages/OemDatasheetPage.js`
- **API prefix:** `/api/oem`
- **Brand logos:** Stored in `backend/uploads/brand_logos/`; base64 backup in MongoDB `logoDataMap` field (survives pod restarts)
- **Color replacement:** Identifies and swaps brand colors in PPTX shapes; skips neutral colors (white, black, grays)
- **Storage:** `oem_brands` MongoDB collection

**Keywords:** OEM, datasheet, rebrand, brand, PPTX, DOCX, white-label

---

### 3.17 Excel Assistant — `backend/routes/excel.py`

- **Purpose:** Upload XLSX/CSV file to a chat; ask AI to transform/filter/translate data; download modified Excel.
- **Key files:** `backend/routes/excel.py` (360+ lines)
- **API prefix:** `/api` (routes: `/api/excel-upload`, `/api/excel-process`, `/api/excel-generate`, `/api/excel-download/{id}`)
- **Max file size:** 10 MB
- **AI model:** Claude (`CLAUDE_API_KEY`) with structured JSON output
- **Output format:** `{action, column_mapping, new_data, message}` JSON; rendered back as Excel
- **Persistence:** Generated files written to `backend/uploads/excel_*.xlsx`; also mirrored to `excel_files` MongoDB collection (fallback on pod restart)
- **Trigger detection:** `services/excel_service.py` — keyword list in English, Russian, Armenian (romanized)

**Keywords:** excel assistant, CSV, spreadsheet, data transformation, excel download

---

### 3.18 Source Insights & Smart Questions — `backend/routes/insights.py`

- **Purpose:** AI-generated summary and 5 suggested questions for a set of sources; "smart question suggestions" in chat.
- **Key files:** `backend/routes/insights.py`
- **Storage:** Results cached in `source_insights` MongoDB collection

**Keywords:** insights, smart questions, source summary, AI analysis

---

### 3.19 News — `backend/routes/news.py`

- **Purpose:** Fetch and cache top stories from Hacker News API.
- **Key files:** `backend/routes/news.py`
- **API:** `GET /api/news?limit=30`
- **Source:** HackerNews API (`hacker-news.firebaseio.com`) — public, no auth required
- **Frontend:** `frontend/src/pages/NewsPage.js`

**Keywords:** news, tech news, hacker news, updates

---

### 3.20 Image Generation — `backend/routes/images.py`

- **Purpose:** Generate images from text prompts using OpenAI DALL-E 3; store and serve them.
- **Key files:** `backend/routes/images.py`
- **Storage:** `backend/generated_images/` (Docker volume `backend_generated_images`) + `generated_images` MongoDB collection
- **Default size:** 1024×1024

**Keywords:** image generation, DALL-E, AI images

---

### 3.21 Temporary Files — `backend/routes/temp_files.py`

- **Purpose:** Upload files to a chat session temporarily (without adding to knowledge base); file context injected into the message only.
- **Key files:** `backend/routes/temp_files.py`
- **Storage:** `/tmp/planet_temp_files/` (ephemeral local)
- **Lifetime:** 24 hours; APScheduler job at 3:00 AM cleans expired entries and inserts a system message in the chat notifying the user
- **OCR:** Uses unified `extract_text_from_pdf` (markitdown → pdfplumber → pytesseract)
- **Chat field:** `chats.tempFiles[]` — each entry: `{id, filename, fileType, contentText, uploadedAt, sizeBytes}`

**Keywords:** temp file, temporary upload, file attachment, chat file

---

### 3.22 Reports — `backend/routes/reports.py`

- **Purpose:** [UNKNOWN — needs human confirmation; file exists but was not fully inspected]
- **Key files:** `backend/routes/reports.py`, `frontend/src/pages/AdminReportsPage.js`

**Keywords:** reports, analytics, admin reports

---

### 3.23 Roles — `backend/routes/roles.py`

- **Purpose:** Custom role CRUD for admin.
- **Key files:** `backend/routes/roles.py`, `frontend/src/pages/AdminRolesPage.js`
- **API:** `GET/POST /api/admin/roles`, `PUT/DELETE /api/admin/roles/{id}`
- **System roles** (`isSystem=True`) cannot be deleted via API

**Keywords:** roles, custom roles, RBAC configuration

---

### 3.24 Departments — `backend/routes/departments.py`

- **Purpose:** Create/manage departments; assign users; configure department AI context (style + instructions).
- **Key files:** `backend/routes/departments.py`, `frontend/src/pages/AdminDepartmentsPage.js`
- **Storage:** `departments` collection; `managers[]` array per department

**Keywords:** departments, department management, org structure

---

### 3.25 Web Search — `backend/services/web_search.py`

- **Purpose:** Brave Search integration; URL auto-ingestion; Armenian language detection for stop-word filtering.
- **Key files:** `backend/services/web_search.py`
- **Brave Search:** `BRAVE_API_KEY`; max 3 results auto-ingested per message
- **URL fetching:** httpx with 30 s timeout
- **Language detection:** Heuristics for romanized Armenian (suffix matching + core-word dictionary) to avoid false-positive web-search triggers

**Keywords:** web search, brave search, internet, URL, fetch, web grounding

---

### 3.26 Frontend SPA — `frontend/src/`

- **Purpose:** React 19 single-page application; all user interaction.
- **Key files:**
  - `frontend/src/App.js` — routing, protected/admin route guards
  - `frontend/src/contexts/AuthContext.js` — JWT storage, `useAuth()`, `hasPermission()`
  - `frontend/src/contexts/LanguageContext.js` — i18n (RU/EN)
  - `frontend/src/contexts/ThemeContext.js` — dark/light theme
  - `frontend/src/i18n/translations.js` — translation strings
  - `frontend/src/pages/ChatPage.js` — main chat UI (798 lines)
  - `frontend/src/components/chat/SourcePanel.js` — source selection (3 tabs: project, global, department/library)
  - `frontend/src/components/chat/MoveDialog.js` — move chat between projects
  - `frontend/src/pages/LibraryPage.js` — library management
  - `frontend/src/pages/TutorPage.js` — tutor interface
  - `frontend/src/components/ui/` — Shadcn/UI component library
- **Build tool:** CRACO (Create React App override)
- **HTTP client:** Axios
- **Styling:** Tailwind CSS v3 + Shadcn/UI (Radix UI primitives)
- **Backend URL:** Set at build time via `REACT_APP_BACKEND_URL` env var

**Frontend routes:**

| Path | Component | Guard |
|---|---|---|
| `/login` | LoginPage | Public |
| `/dashboard` | DashboardPage | Protected |
| `/projects/:projectId` | ProjectPage | Protected |
| `/chats/:chatId` | ChatPage | Protected |
| `/competitors` | CompetitorsPage | Protected |
| `/product-catalog`, `/product-catalog/*` | ProductCatalogPage, ProductDetailPage | Protected |
| `/library` | LibraryPage | Protected |
| `/tutor` | TutorPage | Protected |
| `/personal-sources` | PersonalSourcesPage | Protected |
| `/global-sources` | GlobalSourcesPage | Protected |
| `/departments`, `/departments/:id/sources` | MyDepartmentsPage, DepartmentSourcesPage | Protected |
| `/news` | NewsPage | Protected |
| `/my-prompt`, `/ai-settings` | AiSettingsPage | Protected |
| `/oem-datasheet` | OemDatasheetPage | Protected |
| `/admin/config` | AdminConfigPage | Admin |
| `/admin/users`, `/admin/users/:userId` | AdminUsersPage, AdminUserDetailPage | Admin |
| `/admin/global-sources` | AdminGlobalSourcesPage | Admin |
| `/admin/departments` | AdminDepartmentsPage | Admin |
| `/admin/roles` | AdminRolesPage | Admin |
| `/admin/audit-logs` | AdminAuditLogsPage | Admin |
| `/admin/reports` | AdminReportsPage | Admin |
| `/admin/oem-brands` | AdminBrandsPage | Admin |

**Keywords:** frontend, React, SPA, pages, routes, UI, components

---

## 4. Data Sources & Integrations

| Integration | What it's used for | Auth | Key env vars |
|---|---|---|---|
| MongoDB Atlas | All data storage | Connection string | `MONGO_URL`, `DB_NAME` |
| Anthropic Claude | Primary LLM for chat, agent routing, tutor summaries | Bearer API key | `CLAUDE_API_KEY` |
| OpenAI | `text-embedding-3-small` embeddings; DALL-E 3 images; `gpt-4o-mini` fallback LLM | Bearer API key | `OPENAI_API_KEY` |
| VoyageAI | Product matching embeddings (library `voyageai==0.3.7` installed) | Bearer API key | `VOYAGE_API_KEY` |
| Brave Search | Web search grounding for research queries | API key header | `BRAVE_API_KEY` |
| PlanetWorkspace API | External product catalog (categories, products, brands, attributes) | `x-partner-key` header | `PLANET_PARTNER_KEY`, `PLANET_API_URL` |
| HackerNews API | Tech news feed | None (public) | — |
| Timeweb Cloud VPS | Production hosting server | SSH key | GitHub Secrets |
| Tesseract OCR | Image/scanned-PDF text extraction | None (local binary) | — |

**Keywords:** integrations, external services, APIs, Claude, OpenAI, Brave, PlanetWorkspace

---

## 5. Data Models / Key Data Structures

All models defined in `backend/models/schemas.py` (Pydantic v2) and `backend/models/enterprise.py`.

### 5.1 MongoDB Collections

| Collection | Description |
|---|---|
| `users` | `id`, `email`, `passwordHash`, `isAdmin` (legacy), `roleId`, `permissionGrants[]`, `permissionRevokes[]`, `departments[]`, `primaryDepartmentId`, `ai_profile`, `tutor_memory`, `mustChangePassword`, `position` |
| `projects` | `id`, `name`, `ownerId`, `sharedWith[]`, `sharedMembers[]` (with role) |
| `chats` | `id`, `projectId` (null = quick chat), `name`, `ownerId`, `activeSourceIds[]`, `sourceMode` (`all`/`my`/`ai_only`), `mode` (`tutor` or null), `sourceBookId`, `tempFiles[]`, `sharedWithUsers[]` |
| `messages` | `id`, `chatId`, `role`, `content`, `createdAt`, `citations[]`, `usedSources[]`, `agent_type`, `agent_name`, `model_used`, `tokens_used`, `web_sources[]`, `excel_file_id`, `autoIngestedUrls[]` |
| `sources` | `id`, `projectId`, `level` (`personal`/`department`/`global`/`library`), `kind` (`file`/`url`/`knowledge`), `originalName`, `url`, `mimeType`, `sizeBytes`, `storagePath`, `ownerId`, `departmentId`, `status`, `isCompanyInfo`, `sharedDepartments[]`, `sharedPositions[]`, `isGlobalLibrary`, `publishedFrom`, `contentHash` |
| `source_chunks` | `id`, `sourceId`, `projectId`, `content`/`text`, `embedding[]`, `chunkIndex`, `sourceName`, `sourceType` |
| `departments` | `id`, `name`, `description`, `managers[]`, `memberIds[]`, `aiContext` |
| `roles` | `id`, `name`, `description`, `permissions[]`, `isSystem` |
| `gpt_config` | Singleton (id="1"): `model`, `developerPrompt`, `updatedAt` |
| `audit_logs` | `id`, `entity`, `entityId`, `action`, `userId`, `userEmail`, `timestamp`, `details` |
| `semantic_cache` | `id`, `question`, `answer`, `embedding[]`, `projectId`, `cacheContextHash`, `sourceIds[]`, `hitCount`, `createdAt` |
| `token_usage` | Token consumption logs per message |
| `excel_files` | Binary MongoDB mirror of generated Excel files: `id`, `filename`, `data` (bytes), `size` |
| `competitors` | Competitor entries + product URLs + scraped content + match data |
| `product_catalog` | Internal product catalog |
| `oem_brands` | Brand configs for OEM rebrander; includes `logoDataMap` base64 |
| `planet_category_cache` | PlanetWorkspace category tree (5-hour TTL) |
| `planet_embedding_cache` | Embeddings for PlanetWorkspace products (24-hour TTL) |
| `planet_attr_cache` | PlanetWorkspace category attributes (5-hour TTL) |
| `planet_brand_cache` | PlanetWorkspace brands (5-min TTL) |

### 5.2 Key Pydantic Models (`backend/models/schemas.py`)

| Model | Purpose |
|---|---|
| `UserResponse` | User data returned to clients; includes `roleId`, `permissionGrants/Revokes`, `position` |
| `ChatResponse` | Chat metadata; `mode`, `sourceMode`, `sourceBookId` |
| `MessageCreate` | Inbound message; `content`, `temp_file_ids[]`, `activeSourceIds[]`, `forceWebSearch` |
| `MessageResponse` | Full AI response; includes `agent_type`, `model_used`, `tokens_used`, `excel_file_id`, `web_sources[]`, `citations[]` |
| `SourceResponse` | Source record; `kind`, `chunkCount`, `ocrStatus` |
| `AiProfileUpdate/Response` | Per-user AI persona; `display_name`, `position`, `preferred_language`, `response_style`, `custom_instruction` |
| `ProductCatalogCreate/Response` | Internal product; `article_number`, `title_en`, `aliases[]`, `relations[]` |
| `CompetitorResponse` | Competitor record with `products[]` and `matched_our_products[]` |
| `PositionEnum` | Corporate positions: `CEO`, `COO`, `CRO`, `DeptHead`, `Employee` |

**Keywords:** data models, schemas, collections, MongoDB, Pydantic, database schema

---

## 6. Configuration & Environments

### 6.1 Environment Variables

All real values live in `backend/.env` (not committed). Template at `backend/.env.example`:

| Variable | Description | Placeholder |
|---|---|---|
| `MONGO_URL` | MongoDB Atlas connection string | `<MONGO_URL>` |
| `DB_NAME` | MongoDB database name (default: `gpt`) | `<DB_NAME>` |
| `JWT_SECRET` | HS256 signing secret — **server refuses to start if unset** | `<JWT_SECRET>` |
| `CLAUDE_API_KEY` | Anthropic Claude API key | `<CLAUDE_API_KEY>` |
| `OPENAI_API_KEY` | OpenAI API key (embeddings + DALL-E + fallback LLM) | `<OPENAI_API_KEY>` |
| `VOYAGE_API_KEY` | VoyageAI API key (product matching embeddings) | `<VOYAGE_API_KEY>` |
| `BRAVE_API_KEY` | Brave Search API key | `<BRAVE_API_KEY>` |
| `EMERGENT_LLM_KEY` | Emergent agent key (purpose unclear — see §9) | `<EMERGENT_LLM_KEY>` |
| `PLANET_PARTNER_KEY` | PlanetWorkspace catalog API partner key | `<PLANET_PARTNER_KEY>` |
| `PLANET_API_URL` | PlanetWorkspace API base URL | `https://api-prod.planetworkspace.com` |
| `CORS_ORIGINS` | Allowed CORS origins | `<CORS_ORIGINS>` |
| `CORS_ORIGIN_REGEX` | Regex-based CORS origin override (defaults to `.*` — all allowed) | `<CORS_ORIGIN_REGEX>` |
| `UPLOAD_DIR` | Local upload directory path | `./uploads` |
| `REACT_APP_BACKEND_URL` | Backend URL baked into frontend at build time | `<REACT_APP_BACKEND_URL>` |

### 6.2 How the Project Runs

**Local development:**
- Backend: Python 3.11 venv (`backend/venv`), `uvicorn server:app --reload`, port 8001
- Frontend: `yarn start` (CRACO), port 3000

**Production (Docker Compose):**
- `docker-compose.yml` at repo root
- Backend: `backend/Dockerfile` → Python 3.11-slim, Tesseract OCR pre-installed, exposes port 8001
- Frontend: `frontend/Dockerfile` → builds React SPA with `REACT_APP_BACKEND_URL`, served via Nginx on port 80 (host port 3000)
- Persistent volumes: `backend_uploads`, `backend_generated_images`
- Network: `app-network` bridge

**CI/CD:**
- `.github/workflows/deploy.yml`: push to `main` → SSH into Timeweb host → `cd /opt/gpt && git pull origin main && docker compose up -d --build && docker image prune -f`
- `.github/workflows/sync-to-bitbucket.yml`: [UNKNOWN — sync to Bitbucket mirror; purpose/target unknown]

**Python version:** 3.11 (`.python-version` file in `backend/`)

**Keywords:** configuration, environment variables, deployment, Docker, CI/CD, production, local development

---

## 7. Rules & Constraints (Non-Negotiable)

| Rule | Where enforced |
|---|---|
| `JWT_SECRET` must be set — server crashes on startup if missing | `middleware/auth.py` (RuntimeError at import) |
| `@ai.planetworkspace.com` users always have wildcard `{"*"}` permissions — cannot be restricted | `middleware/permissions.py::is_super()` |
| `role_super_admin.permissions = ["*"]` is always reset on startup — manual changes are overwritten | `middleware/permissions.py::seed_system_roles()` |
| System roles (`isSystem=True`) cannot be deleted via API | `routes/roles.py` |
| Temp files expire after 24 hours; a system message notifies the user | `server.py::cleanup_expired_chat_temp_files()` (APScheduler 3:00 AM) |
| Competitor auto-refresh runs daily at 2:00 AM | APScheduler job in `server.py` |
| Request timeout: 120 s per HTTP request (exceptions: product-matching and library-upload routes) | `RequestTimeoutMiddleware` in `server.py` |
| Semantic cache checks source access before returning — no cross-user data leakage | `services/cache.py::find_cached_answer()` |
| Library items go `active` immediately on upload — no approval workflow | `routes/library.py` |
| Department sources require manager approval before becoming `active` | `routes/enterprise_sources.py` |
| Max file upload: 50 MB (library, enterprise sources); 20 MB (product matching); 10 MB (Excel assistant) | Route-level checks |
| Product matching max customer items: 200 per job | `routes/product_matching.py` |
| CORS defaults to `.*` (all origins) if `CORS_ORIGIN_REGEX` not set — must be restricted in production | `server.py` CORS config |
| Default admin account (`mustChangePassword=True`) — should be enforced by frontend on first login | `server.py::init_admin_user()` |

**Keywords:** rules, constraints, limits, security, non-negotiable, hard limits

---

## 8. Current State & Roadmap

### 8.1 Fully Working Features (confirmed in code)

| Feature | Status |
|---|---|
| JWT auth + RBAC (5 system roles + custom) | ✅ Working |
| Projects, chats (quick + project), messages | ✅ Working |
| RAG pipeline (embed → cosine sim → Claude) | ✅ Working |
| Personal / project / department / global sources | ✅ Working |
| Department approval workflow | ✅ Working |
| Library with position-based access | ✅ Working |
| Tutor mode with per-book learning memory | ✅ Working |
| Admin panel (users, GPT config, audit logs) | ✅ Working |
| Semantic cache (0.92 threshold, 30-day TTL) | ✅ Working |
| Image generation (DALL-E 3) | ✅ Working |
| Source insights + smart questions | ✅ Working |
| Competitor tracker (scrape + auto-refresh) | ✅ Working |
| Internal product catalog CRUD | ✅ Working |
| PlanetWorkspace catalog integration + caching | ✅ Working |
| Product matching pipeline (3-phase, Excel output) | ✅ Working |
| OEM Datasheet rebrander (PPTX/DOCX) | ✅ Working |
| Excel assistant (upload → AI transform → download) | ✅ Working |
| Temp file uploads (24-hour lifecycle) | ✅ Working |
| Web search (Brave) + auto URL ingestion | ✅ Working |
| i18n (Russian/English) | ✅ Partial (~80%) |
| Multi-language model answers | ✅ Working |
| MongoDB indexes (all major collections) | ✅ Working |
| Docker Compose deployment | ✅ Working |
| CI/CD (GitHub Actions → Timeweb SSH) | ✅ Working |

### 8.2 Partial / Known Issues

| Item | Status | Note |
|---|---|---|
| i18n translation | 🔄 ~80% complete | Some modals/toasts still untranslated |
| `ChatHeader.js`, `Message.js`, `MessageList.js`, `ChatInput.js` | 🔄 Created, not integrated | Exist in `components/chat/` but ChatPage uses inline rendering |
| `EMERGENT_LLM_KEY` env var | ❓ Unknown | `emergentintegrations` package commented out in `requirements.txt` |
| Excel files in `/tmp/` | ⚠️ Ephemeral | Pod restart loses disk files; MongoDB mirror is recovery path |
| `backend/nohup.out`, root `nohup.out` | 🔍 Legacy | Indicates server was once run with `nohup`; Docker is now standard |
| `server_monolith_old.py` | 🗑 Stale | Old monolith kept for reference; can be deleted |
| `migrate_embeddings.py`, `migrate_catalog_embeddings.py` | 🔍 Unclear | One-time scripts; unknown if already run on production |

### 8.3 Backlog (from code inspection + old PRD)

- Pending approvals page for department sources workflow
- Admin cache settings UI (currently no frontend for cache inspection)
- User token usage limits (tracked but not enforced)
- Rate limiting middleware (no implementation found)
- Object storage for Excel/image files (currently local volume — lost on full redeploy)
- Complete i18n (~20% remaining)
- Integrate `ChatHeader.js` / `Message.js` / `MessageList.js` into ChatPage

**Keywords:** current state, features, working, partial, roadmap, backlog, TODO, status

---

## 9. Observations & Open Questions

| # | Observation / Risk | Severity | Action needed |
|---|---|---|---|
| 9.1 | **CORS defaults to `.*`** — all origins allowed if `CORS_ORIGIN_REGEX` not set in production | High | Set `CORS_ORIGIN_REGEX` to production domain |
| 9.2 | **`EMERGENT_LLM_KEY`** env var exists but `emergentintegrations` package is commented out in `requirements.txt`. Purpose unknown. | Medium | [UNKNOWN — needs human confirmation] |
| 9.3 | **Default admin password logged in plaintext** to server logs on first-time creation | Medium | Remove or redact the log line after confirming it's safe |
| 9.4 | **`excel_files` MongoDB collection has no TTL index** — generated Excel files accumulate without cleanup | Medium | Add TTL index on `excel_files.createdAt` |
| 9.5 | **VoyageAI** (`voyageai==0.3.7`) library installed and `VOYAGE_API_KEY` in env, but primary embedding code uses OpenAI. Product matching may have been partially migrated. | Low | [UNKNOWN — confirm which embedding model is used in product matching in production] |
| 9.6 | **`sync-to-bitbucket.yml`** GitHub Action exists — Bitbucket mirror URL and purpose unknown | Low | [UNKNOWN — needs human confirmation] |
| 9.7 | **`server_monolith_old.py`** still committed — large dead code file | Low | Delete when confirmed safe |
| 9.8 | **`migrate_embeddings.py` / `migrate_catalog_embeddings.py`** at repo root — unclear if run on production DB | Low | [UNKNOWN — needs human confirmation] |
| 9.9 | **`memory/test_credentials.md`** file committed — may contain real credentials | High | [UNKNOWN — review immediately; rotate and remove if real credentials present] |
| 9.10 | **No rate limiting middleware** found on AI routes (messages, product-matching) | Medium | Add per-user throttling before public launch |
| 9.11 | **`routes/reports.py` full functionality** not inspected | Low | [UNKNOWN — needs human confirmation] |
| 9.12 | **`PLANET_API_URL` discrepancy**: `docker-compose.yml` defaults to `https://api-prod.planetworkspace.com` but `.env.example` shows `https://planetworkspace.com/api` | Medium | [UNKNOWN — confirm correct production URL] |
| 9.13 | **`boto3` / `s3transfer`** in `requirements.txt` but no S3 upload code found in inspected routes/services | Low | [UNKNOWN — confirm if planned or legacy] |

---

## Summary for Boby

### Secrets replaced with placeholders

| Original | Placeholder |
|---|---|
| MongoDB Atlas connection string | `<MONGO_URL>` |
| Anthropic API key | `<CLAUDE_API_KEY>` |
| OpenAI API key | `<OPENAI_API_KEY>` |
| VoyageAI API key | `<VOYAGE_API_KEY>` |
| Brave Search API key | `<BRAVE_API_KEY>` |
| PlanetWorkspace partner key | `<PLANET_PARTNER_KEY>` |
| Emergent agent key | `<EMERGENT_LLM_KEY>` |
| JWT signing secret | `<JWT_SECRET>` |
| Timeweb SSH credentials | `TIMEWEB_HOST`, `TIMEWEB_USER`, `TIMEWEB_SSH_KEY` (GitHub Secrets) |

### All UNKNOWN items (require human confirmation)

1. **`EMERGENT_LLM_KEY`** — is `emergentintegrations` still used? If not, remove the env var.
2. **`memory/test_credentials.md`** — does it contain real credentials? Review and rotate if yes.
3. **Bitbucket sync** (`sync-to-bitbucket.yml`) — what is the Bitbucket target and why?
4. **VoyageAI in product matching** — is VoyageAI or OpenAI used for embeddings in the matching pipeline in production?
5. **`migrate_embeddings.py` / `migrate_catalog_embeddings.py`** — have these been run on production? Are they still needed?
6. **`routes/reports.py`** — full functionality not confirmed.
7. **`PLANET_API_URL`** — confirm the correct production value (`api-prod.planetworkspace.com` or `planetworkspace.com/api`).
8. **`boto3` / S3** — planned for file storage or legacy remnant?
9. **Default GPT config model** — what is `gpt_config.model` set to in production?
