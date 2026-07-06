# История обновлений / Changelog

Формат: `[дата] — краткое описание`  
Ветка: `main`  
UI версия: `frontend/src/data/changelog.js`

---

## 2026-07-06 — v2.9.63

**Feature: Admin Tutors section**

- `backend/models/schemas.py` — добавлена позиция `TUTOR = "Tutor"` в `PositionEnum`
- `backend/routes/admin.py` — новый endpoint `GET /api/admin/tutors` (список пользователей с position=Tutor)
- `frontend/src/pages/AdminTutorsPage.js` — новая страница: список тьюторов, создание, сброс пароля, удаление
- `frontend/src/App.js` — маршрут `/admin/tutors`
- `frontend/src/components/DashboardLayout.js` — ссылка «Тьюторы» в сайдбаре для admin
- `frontend/src/pages/AdminUserDetailPage.js` — добавлен вариант «Тьютор» в dropdown должностей

---

## 2026-06-11 — v2.9.62

**Fix: user bubble text visibility + project memory limit increase**

- `frontend/src/components/chat/MessageBubble.js` — user bubble: `bg-primary text-primary-foreground` → `bg-indigo-600 text-white` (fix invisible text in light theme)
- `frontend/src/components/chat/Message.js` — same fix applied to legacy Message component
- `backend/routes/projects.py` — project memory char limit: 6 000 → 12 000
- `frontend/src/components/ProjectMemoryModal.js` — MAX_CHARS: 6 000 → 12 000, token display: 1 500 → 3 000

---

## 2026-06-11 — v2.9.60

**Multi-file upload in chat**

- `frontend/src/components/chat/ChatInput.js` — `multiple` attr on file input, `tempFiles[]` array badges, per-badge remove button
- `frontend/src/pages/ChatPage.js` — `tempFiles` array state, parallel upload loop, `temp_file_ids` payload
- `frontend/src/components/chat/MessageBubble.js` — render `uploadedFiles[]` array badges (backward compat with `uploadedFile`)
- `backend/models/schemas.py` — `MessageCreate.temp_file_ids: List[str]` + `effective_temp_file_ids` property
- `backend/routes/messages.py` — both endpoints: multi-file processing loop, per-file prompt injection (`===== ФАЙЛ 1 =====`), multi-image vision blocks

---

## 2026-06-11 — v2.9.57

### Fix: modern typing indicator + empty bubble fix

**Файлы:** `frontend/src/pages/ChatPage.js`, `frontend/src/components/chat/MessageBubble.js`

- Replaced `ThinkingSteps` multi-step animation with a clean 3-dot `TypingIndicator` (like Claude/ChatGPT)
- `MessageBubble`: returns null when `message.isStreaming && !message.content` — prevents empty bubble with action buttons showing before first token

---

## 2026-06-11 — v2.9.56

### New: Streaming responses + parallel RAG optimizations

**Файлы:** `backend/routes/messages.py`, `frontend/src/pages/ChatPage.js`, `frontend/src/components/chat/MessageBubble.js`

- New endpoint `POST /api/chats/{chat_id}/messages/stream` — Anthropic `messages.stream()` + FastAPI `StreamingResponse`, SSE token-by-token, final `[META]` event with saved message data
- Frontend `sendMessage` rewritten: `axios.post` → `fetch` + `ReadableStream`, placeholder assistant message updated token-by-token
- Regen flow also uses streaming
- `MessageBubble`: blinking cursor while `message.isStreaming` is true
- `ThinkingSteps` hidden once first streaming token arrives
- `asyncio.gather(RAG, catalog_search)` — parallel execution, saves ~200–400ms
- Duplicate `db.projects.find_one` call eliminated (project_doc cached in `_project_doc_cache`)

---

## 2026-06-11 — v2.9.55

### New: Project Memory limit doubled — 6000 → 12000 characters

**Файлы:** `backend/routes/projects.py`, `frontend/src/components/ProjectMemoryModal.js`, `frontend/src/pages/ChatPage.js`

- Backend: `update_project_memory` — лимит поднят с 6000 до 12000 символов (~3000 токенов)
- `ProjectMemoryModal`: `MAX_CHARS` 6000→12000, `WARN_CHARS` 4800→9600, label «/ 3000 токенов»
- `ChatPage.saveToProjectMemory`: guard поднят с 6000 до 12000

---

## 2026-06-11 — v2.9.54

### Fix: shared-to-chat personal sources always active regardless of checkbox state

**Файл:** `backend/routes/messages.py`

- Баг: если пользователь снимал все галочки в Sources panel (activeSourceIds = []), источники расшаренные через «Share to Chat» тоже исключались из RAG — хотя они были явно добавлены владельцем чата через отдельный механизм
- Fix: `shared_to_chat_ids` — новый set из источников где `chat_id ∈ sharedInChatIds`; после применения checkbox-фильтра эти ID всегда добавляются обратно в `active_source_ids`
- MongoDB projection обновлён: `sharedInChatIds: 1` добавлен в personal sources query чтобы данные были доступны без отдельного запроса

---

## 2026-06-11 — v2.9.53

### New: Share personal source to a specific project chat

**Файлы:** `backend/routes/enterprise_sources.py`, `frontend/src/pages/PersonalSourcesPage.js`

- `PersonalSourcesPage`: новая кнопка «Share to Chat» рядом с «Опубликовать» — открывает диалог выбора проекта и чата; шаринг не создаёт копию, только добавляет `chatId` в `sharedInChatIds` источника
- Бейджи на карточке источника: отображают имена чатов, куда расшарен источник (фиолетовые); клик по бейджу — отменяет шаринг (`DELETE /sources/{id}/share-to-chat/{chatId}`)
- `list_personal_sources`: поле `sharedInChats` теперь содержит `{chatId, chatName, projectId, projectName}` — dangling refs (удалённые чаты) автоматически пропускаются
- Защита от дублирования: кнопка Share задизейблена и показывает предупреждение если источник уже расшарен в выбранный чат

---

## 2026-06-10 — v2.9.52

### Fix: update all Claude model IDs to claude-sonnet-4-6

- `backend/routes/messages.py`, `admin.py`, `excel.py`, `images.py`, `insights.py`, `product_catalog.py`, `product_matching.py`, `product_relations.py`, `services/excel_service.py` — all replaced `claude-sonnet-4-20250514` and `claude-sonnet-4-5-20251001` with `claude-sonnet-4-6`

---

## 2026-06-10 — v2.9.51

### Fix: restore correct Claude model names in messages.py

- `backend/routes/messages.py` — all model references restored to `claude-sonnet-4-5-20251001` / `claude-haiku-4-5-20251001`; accidentally reverted to old names in v2.9.49

---

## 2026-06-10 — v2.9.50

### Fix: SourcePanel — all personal sources marked as shared incorrectly

- `frontend/src/components/chat/SourcePanel.js` — removed incorrect `sharedIds` Set that caused all sources to appear shared when any one source was shared; `isSharedHere` now checks `source.sharedInChatIds` directly per source

---

## 2026-06-10 — v2.9.49

### New: Chat-level personal source sharing

- `backend/routes/sources.py` — 3 new endpoints: `GET /personal-sources/shared-in-chat/{chat_id}`, `PUT /sources/{id}/share-to-chat`, `DELETE /sources/{id}/share-to-chat/{chat_id}`
- `backend/routes/messages.py` — personal source query extended with `$or` to include sources where `sharedInChatIds` contains current `chat_id`
- `frontend/src/pages/ChatPage.js` — `fetchChatData` now loads `sharedPersonalSources` + owner's `myPersonalSources`; added `sharePersonalSourceToChat` / `unsharePersonalSourceFromChat` handlers
- `frontend/src/components/chat/SourcePanel.js` — new "My Personal Sources" section (owner: Share toggle per source); new "Shared by Owner" section (participants: read-only, lock badge)

---

## 2026-05-14 — v2.9.48

### Fix: planet-search 504 on cold start + matching blocks event loop

- `backend/routes/product_matching.py` — `planet_search`: catalog fetch moved outside `asyncio.timeout(5s)`; 5s budget now applies only to embedding+scoring step
- `backend/routes/product_matching.py` — `_claude_match_with_candidates`, `_claude_match_batch`, `_web_research_item`, `_phase3_web_rematch`: all converted to `async def` + `AsyncAnthropic` + `await`; callers in `match_products` and `research_item` updated with `await`
- `backend/server.py` — `RequestTimeoutMiddleware`: `/api/product-matching/match`, `/research-item`, `/generate-excel` excluded from timeout; these routes have unbounded processing time by design

---

## 2026-05-13 — v2.9.47

### Feature: dynamic model routing — Sonnet for RAG/Excel, Haiku for general chat

- `backend/routes/messages.py` — Claude model now selected based on `selected_agent_type`: `rag | excel | research` → `claude-sonnet-4-20250514`; `general` → `claude-haiku-4-20250514`

---

## 2026-05-13 — v2.9.46

### Fix: RAG crash on embedding dimension mismatch (Voyage 1024d vs OpenAI 1536d)

- `backend/services/rag.py` — `get_relevant_chunks` now checks `len(chunk_embedding) == len(query_embedding)` before calling `cosine_similarity`; mismatched chunks (old Voyage AI 1024-dim vs current OpenAI 1536-dim) fall back to text-relevance scoring instead of crashing with `ValueError: shapes not aligned`

---

## 2026-05-13 — v2.9.45

### Fix: 500 error on POST /api/chats/{id}/messages — async Anthropic client

- `backend/routes/messages.py` — all 4 `anthropic.Anthropic(...)` instantiations changed to `anthropic.AsyncAnthropic(...)`; all `.messages.create(...)` calls now `await`ed — prevents event-loop blocking that caused the 30 s middleware timeout to fire mid-request
- `backend/services/excel_service.py` — both `claude_client.messages.create(...)` calls now `await`ed (functions are already `async def`)
- `backend/server.py` — `RequestTimeoutMiddleware` timeout raised from 30 s → 120 s (safety net only; planet-search keeps its own 5 s internal budget)

---

## 2026-05-13 — v2.9.44

### Fix: planet-search timeout hardening for ShadowDB client

- `backend/server.py` — added `RequestTimeoutMiddleware` (30 s hard ceiling on all HTTP requests, returns 504 JSON on breach); added `asyncio` import and `starlette.types` imports
- `backend/routes/product_matching.py` — added `import asyncio`; added `PLANET_SEARCH_TIMEOUT = 5.0`, `_ALIAS_DB_TIMEOUT_MS = 2000`, `_EMBED_TIMEOUT = 3.0` constants; handler now wraps pipeline in `asyncio.timeout(5.0)`, raises HTTP 504 on `TimeoutError` and HTTP 503 on unexpected errors
- `backend/routes/product_matching.py` — extracted `_planet_search_pipeline()` async helper; MongoDB alias query gets `.max_time_ms(2000)`; embedding step uses new `_voyage_embed_batch_async()` (runs sync call in executor via `asyncio.wait_for`); timeout on embedding falls back to text search, not a hard error
- `backend/routes/product_matching.py` — `_voyage_embed_batch()` now sets `timeout=3.0` on the OpenAI client; `_voyage_embed_batch_async()` added as async thread-executor wrapper with configurable timeout
- `backend/routes/product_matching.py` — added `GET /api/product-matching/planet-search/ready` readiness probe; checks MongoDB reachability and `planet_embedding_cache` document count; returns 503 if not ready

---

## 2026-05-13 — v2.9.43

### Fix: Chat Access checkbox double-toggle

- `frontend/src/pages/ProjectPage.js` — removed `onClick` from the wrapper `div` in Chat Visibility dialog; only `Checkbox.onCheckedChange` now fires, preventing the double-toggle that made checkboxes appear non-functional

---

## 2026-05-13 — v2.9.42

### Fix: Relation Rules — Attribute Links category filtering & auto-select

- `frontend/src/pages/ProductCatalogPage.js` — Side A/B category dropdowns in Attribute Links now filter to show only the categories selected in Side A/B respectively
- `frontend/src/pages/ProductCatalogPage.js` — added `useEffect` hooks that auto-select the category (and trigger attribute load) when exactly one category is chosen on Side A or Side B

---

## 2026-05-05 — v2.9.41

### Background OCR for large scanned PDFs
- `backend/services/file_processor.py` — added `extract_text_from_pdf_with_meta()` returning OCR metadata, `ocr_pdf_page_range()` for background processing, kept `extract_text_from_pdf()` backward-compatible
- `backend/routes/sources.py` — added `_process_remaining_ocr` async background task using `run_in_executor`, upload endpoint now schedules background OCR when PDF is truncated, list endpoint returns `ocrStatus` field
- `backend/models/schemas.py` — added `ocrStatus`, `ocrTotalPages`, `ocrProcessedPages` to `SourceResponse`
- `frontend/src/components/chat/SourcePanel.js` — amber spinner badge showing "10/43 pages" while OCR processing
- `frontend/src/pages/ChatPage.js` — `startOcrPolling()` polls every 5s until all sources are ready; upload toast shows background processing message; large PDF warning for files >4MB

---

## 2026-05-03 — v2.9.40

### Fix: OCR fallback for scanned/image-based PDF uploads

**Файлы:** `backend/services/file_processor.py`, `backend/Dockerfile`, `frontend/src/data/changelog.js`, `CHANGELOG.md`

- `extract_text_from_pdf` now falls back to PyMuPDF + pytesseract OCR when MarkItDown and pdfplumber extract no text (image-based PDFs)
- Auto-detects available Tesseract languages (`eng+rus` if both present, else `eng`)
- Added `tesseract-ocr-rus` to Dockerfile for Russian-language document support

---

## 2026-04-30 — v2.9.39

### Fix: Reports badge — cache in localStorage to prevent flicker

**Файлы:** `frontend/src/components/DashboardLayout.js`, `frontend/src/data/changelog.js`

- `openReportsCount` now initializes from `localStorage` so the badge renders immediately on navigation without flash
- After each fetch the new count is written back to `localStorage`

---

## 2026-04-30 — v2.9.38

### Fix: Admin Reports — 403 fix + sidebar badge

**Файлы:** `backend/routes/reports.py`, `frontend/src/components/DashboardLayout.js`, `frontend/src/data/changelog.js`

- `GET /api/admin/reports` and `PATCH /api/admin/reports/{id}`: replaced `current_user.get("isAdmin")` (always `None` in MongoDB) with `is_admin(current_user["email"])` — consistent with all other admin routes
- Sidebar: admins now see an amber badge on the Reports nav item showing the count of open reports (fetched alongside other sidebar data, refreshed every 5 min)

---

## 2026-04-29 — v2.9.37

### New: Relation Rules — run status tracking + polling

**Файлы:** `backend/routes/product_relations.py`, `frontend/src/pages/ProductCatalogPage.js`, `frontend/src/data/changelog.js`

- Backend: `run_status` field on `relation_rules` — `running` → `completed` / `failed`; also tracks `run_saved` count and `run_error` message
- Error handling wrapper in `_run_rule_analysis` catches any crash → writes `failed` status
- Frontend: after clicking Run, polls `GET /rules` every 4s; updates rule card live
- Rule card shows badge: blue "Running…" (spinner) / green "✓ Done (N saved)" / red "✗ Failed" (hover shows error)
- Toast on completion with count or error message

---

## 2026-04-29 — v2.9.36

### New: Relation Rules — cascading category selector + multiselect

**Файлы:** `backend/routes/product_catalog.py`, `backend/routes/product_relations.py`, `frontend/src/pages/ProductCatalogPage.js`, `frontend/src/data/changelog.js`

- New `GET /api/product-catalog/category-tree` endpoint — returns full nested hierarchy `{root: {lvl1: {lvl2: [lvl3]}}}`
- `RelationRuleCreate`/`Update` schema: `category_a/b: str` → `categories_a/b: List[str]` (backward compatible — old rules still work)
- `_run_rule_analysis` now queries all 4 category levels for each selected category via `$or`
- Frontend: new `CategorySelector` component — root → lvl1 → lvl2 cascading dropdowns, "+ Add" button, selected categories shown as removable tags
- Both Side A and Side B support multiple categories

---

## 2026-04-29 — v2.9.35

### Fix: Relation Rules — all 4 category levels in dropdowns

**Файлы:** `frontend/src/pages/ProductCatalogPage.js`, `backend/routes/product_relations.py`, `frontend/src/data/changelog.js`

- Dropdown now shows root_categories + lvl1_subcategories via `<optgroup>` (API already returns both)
- Backend `_category_query()` helper: searches across all 4 levels (`root_category`, `lvl1_subcategory`, `lvl2_subcategory`, `lvl3_subcategory`) via `$or`

---

## 2026-04-29 — v2.9.34

### Fix: Relation Rules — category dropdowns

**Файлы:** `frontend/src/pages/ProductCatalogPage.js`, `frontend/src/data/changelog.js`

- Category A / Category B text inputs replaced with `<select>` dropdowns populated from `categories.root_categories` (already loaded on page mount)

---

## 2026-04-29 — v2.9.33

### New: Both Together — AI-powered product compatibility

**Файлы:** `backend/routes/product_relations.py` (new), `backend/server.py`, `frontend/src/pages/ProductCatalogPage.js`, `frontend/src/pages/ProductDetailPage.js`, `frontend/src/data/changelog.js`

- New `relation_rules` MongoDB collection — stores category pairs + compatibility description for AI
- New `product_relations` MongoDB collection — stores AI-detected compatible pairs (product_id_a/b, crm_code, confidence, reason, rule_id)
- 6 new endpoints under `/api/product-relations/*`:
  - `GET/POST/PUT/DELETE /api/product-relations/rules` — CRUD for relation rules (Admin/Manager only)
  - `POST /api/product-relations/rules/{id}/run` — triggers background AI analysis (Voyage pre-filter → Claude batch compatibility check)
  - `GET /api/product-relations/{crm_code}` — returns compatible products for a given CRM code (authenticated)
  - `GET /api/product-relations/{crm_code}/public` — same but no auth required (for external website)
- AI logic: Voyage top-5 semantic pre-filter per product → Claude checks compatibility in batches of 20 → high/medium confidence auto-saved, low/none discarded
- ProductCatalogPage: "Relation Rules" button → modal with category pair config, description field, Run/edit/delete/toggle per rule
- ProductDetailPage: "Both Together" section in sidebar — AI-suggested compatible products with confidence badge (high/medium) and Claude's reason

---

## 2026-04-23 — v2.9.30

### New: Product Matching — Domain Rules Editor
**Файлы:** `backend/routes/product_matching.py`, `frontend/src/pages/ProductCatalogPage.js`, `frontend/src/data/changelog.js`

- New `matching_domain_rules` MongoDB collection — stores custom vendor naming rules with title, content, category, is_active, created_by, updated_at
- 4 new endpoints: `GET/POST /api/product-matching/domain-rules`, `PUT/DELETE /api/product-matching/domain-rules/{id}`
- `/match` endpoint loads active rules from DB at request time, appends to `OPTICAL_CABLE_DOMAIN` as `full_domain` passed to both Claude functions
- `_claude_match_with_candidates` and `_claude_match_batch` accept optional `domain` parameter (falls back to hardcoded constant)
- Frontend: "Matching Rules" button (⚙️) in Product Catalog header — visible only to canEdit users
- Modal with inline Add/Edit form (title, category dropdown, content textarea, active checkbox) + scrollable rules list
- Per-rule: toggle active (CheckCircle/AlertCircle), edit (pencil), delete (trash) actions

---

## 2026-04-23 — v2.9.32

### Fix: Matching Rules button open for all users
**Файлы:** `frontend/src/pages/ProductCatalogPage.js`, `frontend/src/data/changelog.js`

- "Matching Rules" button moved outside `{canEdit && ...}` — visible to all authenticated users

---

## 2026-04-23 — v2.9.31

### New: canEditProductCatalog permission + alias delete
**Файлы:** `backend/models/schemas.py`, `backend/routes/admin.py`, `backend/routes/auth.py`, `backend/routes/product_matching.py`, `backend/routes/product_catalog.py`, `frontend/src/pages/AdminUserDetailPage.js`, `frontend/src/pages/ProductDetailPage.js`, `frontend/src/data/changelog.js`

- New `canEditProductCatalog` field on UserResponse — default False for new users
- New `PUT /api/admin/users/{id}/catalog-permission` endpoint
- AdminUserDetailPage: "Product Catalog" permission card with grant/revoke toggle
- `DELETE /api/product-matching/aliases/{alias_id}` — admin or canEditProductCatalog required
- `GET /product-catalog/{id}/learned-aliases` now returns `id` field (ObjectId as str)
- ProductDetailPage: 🗑 delete button on each learned alias row (visible to admin + canEditProductCatalog users)

---

## 2026-04-23 — v2.9.29

### New: Product Detail — Learned Aliases section
**Файлы:** `backend/routes/product_catalog.py`, `frontend/src/pages/ProductDetailPage.js`, `frontend/src/data/changelog.js`

- New `GET /api/product-catalog/{id}/learned-aliases` endpoint — queries `product_aliases` collection by crm_code/article_number
- ProductDetailPage fetches learned aliases in parallel with product data
- New "Learned Aliases" section (blue) shows alias text, confidence badge (auto/confirmed), and date saved

---

## 2026-04-23 — v2.9.28

### Fix: Product Matching — comment always filled
**Файлы:** `backend/routes/product_matching.py`, `frontend/src/data/changelog.js`

- Claude prompt updated in both `_claude_match_with_candidates` and `_claude_match_batch`
- `comment` is now always required (never null): high → "Exact match: …", medium → "Approximate: …", none → "No match: …"

---

## 2026-04-23 — v2.9.27

### Fix: Product Matching — manual web research button, remove auto Phase 3
**Файлы:** `backend/routes/product_matching.py`, `frontend/src/pages/ProductCatalogPage.js`, `frontend/src/data/changelog.js`

- Removed automatic Phase 3 web search from `/match` endpoint (was causing container crash/timeout)
- New `POST /api/product-matching/research-item` endpoint — web search + Voyage re-embed + Claude re-match for a single item
- Preview table: unmatched rows (no matched_title) now show a `🌐 Research` button
- Clicking Research calls the new endpoint, updates that row in-place with result + web source URLs
- `match_type: "web_research"` set on researched rows for tracking

---

## 2026-04-23 — v2.9.26

### New: Product Matching — Phase 3 web research fallback + GYTA support
**Файлы:** `backend/routes/product_matching.py`, `frontend/src/data/changelog.js`

- Phase 3: items with `confidence="none"` after Phase 2 are now researched via Claude `web_search_20250305` built-in tool
- `_web_research_item()` — Claude searches the web, returns enriched product description + source URLs
- `_phase3_web_rematch()` — re-embeds enriched description via Voyage, fetches TOP-12 candidates, Claude re-matches
- Matched items via web research show comment: "Matched via web research. Sources: url1 · url2 · url3"
- Response includes `web_sources: [...]` field with up to 5 source URLs
- `VOYAGE_TOP_K` increased 5 → 10 for broader candidate coverage in Phase 1
- `PHASE3_TOP_K = 12` for post-web-research re-embedding
- `OPTICAL_CABLE_DOMAIN` extended with GYTA/GYTS naming convention: modules×core = total fiber count (e.g. 6 modules/8 core = 48FO)

---

## 2026-04-22 — v2.9.25

### New: Report feature + persistent chat temp files
**Файлы:** `backend/routes/reports.py` (new), `backend/server.py`, `frontend/src/pages/AdminReportsPage.js` (new), `frontend/src/components/chat/MessageBubble.js`, `frontend/src/components/chat/MessageList.js`, `frontend/src/pages/ChatPage.js`, `frontend/src/components/DashboardLayout.js`, `frontend/src/App.js`, `frontend/src/data/changelog.js`

- New `POST /api/reports` — user submits report with tags + optional comment + chat history snapshot
- New `GET /api/admin/reports`, `PATCH /api/admin/reports/{id}` — admin views/resolves reports
- 🚩 Flag button on assistant message hover → modal with 4 quick tags + free text
- Admin `/admin/reports` page: expandable rows with Q, AI answer, sources, context history; Resolve/Ignore/Reopen actions
- Temp files now persisted in `chat.tempFiles` (MongoDB) — AI remembers uploaded files for entire chat session
- Daily APScheduler job at 3 AM cleans up temp files older than 24h and posts notification message in affected chats

## 2026-04-22 — v2.9.22

### New: markitdown PDF/DOCX extraction + RAG threshold tuning
**Файлы:** `backend/services/file_processor.py`, `backend/services/rag.py`, `backend/requirements.txt`, `frontend/src/data/changelog.js`

- markitdown integrated as primary extractor for PDF and DOCX; falls back to pdfplumber / python-docx
- `MIN_SCORE_THRESHOLD` raised 0.3 → 0.45, added `RAG_SCORE_RELEVANT = 0.55`
- `MAX_CHUNKS_PER_QUERY` lowered 8 → 5

---

## 2026-04-16 — v2.9.21

### New: Template download + smart Excel column detection
**Файлы:** `backend/routes/product_matching.py`, `frontend/src/pages/ProductCatalogPage.js`, `frontend/src/data/changelog.js`

- New `GET /api/product-matching/template` — returns styled Excel template (yellow header, hints, freeze pane)
- `_parse_excel` now detects "Product Name" column by header keyword; falls back to first column
- Skips Qty/Price/Notes columns automatically
- Modal: "Download template" link above the upload zone

---

## 2026-04-16 — v2.9.19

### New: Product Matching feature
**Файлы:** `backend/routes/product_matching.py` (new), `backend/server.py`, `frontend/src/pages/ProductCatalogPage.js`, `frontend/src/data/changelog.js`

- Новый backend route `POST /api/product-matching/match` — принимает файл + mode (global/oem)
- Парсинг Excel/CSV (все ячейки), DOCX (параграфы + таблицы), PDF (построчно)
- Claude claude-sonnet-4-20250514 matching: полный каталог + батчи по 50 элементов
- Global mode → CRM код; OEM mode → article для OEM-вендоров, иначе CRM
- Excel-ответ: 5 колонок, синий хедер, чередующиеся строки, жёлтые — несовпавшие
- Обновлён Modal в ProductCatalogPage: drag & drop, кнопки Global/OEM, download-ссылка без закрытия

---

## 2026-04-15 — v2.9.18

### Fix: Web Search OFF now truly disables search
**Файлы:** `frontend/src/pages/ChatPage.js`, `frontend/src/components/chat/ChatInput.js`, `backend/routes/messages.py`

- Frontend now sends `forceWebSearch: false` (explicit) when toggle is OFF, instead of `undefined`
- Backend: `forceWebSearch=False` → skip ALL web search: forced, auto (`should_use_web_search`), and fallback
- Introduced `user_disabled_web_search` flag to cleanly block fallback trigger
- UI label updated: "OFF — web search disabled" (was "OFF — auto only")

---

## 2026-04-15 — v2.9.17

### Fix: Excel always uses targeted edit when source exists + expanded triggers
**Файлы:** `backend/services/excel_service.py`

- When an Excel source exists in the project, ALL requests (generate, download, edit) now route to `targeted_excel_edit` — full generation (which destroys formatting/charts) is no longer used
- Expanded `EXCEL_TRIGGER_PHRASES` and `EXCEL_EDIT_PHRASES` with 30+ new phrases: Armenian romanized (generacru, sarcru, beri, download ara...), Armenian unicode (ստեղծիր, բեր, գեներացրու...), Russian (скачай, скачать, генерируй...), English (generate, download, export...)
- `EXCEL_EDIT_MIN_WORDS` reduced from 4 to 1 — single-word commands now work

---

## 2026-04-15 — v2.9.16

### Fix: Excel source lookup by file extension fallback
**Файлы:** `backend/services/excel_service.py`

- Added extension-based fallback when mimeType lookup fails (storagePath or originalName ending in .xlsx/.xls/.csv)
- Added `[EXCEL]` debug logging on all early-return paths for easier diagnosis
- Fixes case where file was stored with wrong/unexpected mimeType in DB

---

## 2026-04-15 — v2.9.15

### Feature: Full Excel editor — chart titles, font, merge, formulas
**Файлы:** `backend/services/excel_service.py`

- `targeted_excel_edit` полностью переписан: поддержка 9 типов операций (`cell`, `fill`, `font`, `chart_title`, `chart_fill`, `merge`, `unmerge`, `row_height`, `col_width`)
- Claude получает полную структуру файла (все строки, не только 10) + информацию о charts (индекс, тип, текущий title)
- Rich JSON schema с полем `type` — AI сам выбирает нужный тип операции
- Исправлен silent fail: теперь пользователь видит армянское сообщение об ошибке вместо пустого ответа

---

## 2026-04-14 — v2.9.14

### Fix: Excel generated files saved permanently
**Файлы:** `backend/services/excel_service.py`, `backend/routes/excel.py`

- Все `excel_result_*.xlsx` теперь сохраняются в `/uploads/` вместо `/tmp/`
- Download больше не ломается после перезапуска сервера

---

## 2026-04-14 — v2.9.13

### Rollback: Excel Assistant from Plus menu
- Removed Excel Assistant from Plus menu (was unstable, /tmp file loss on restart)

---

## 2026-04-14 — v2.9.11

### Feature: animated thinking steps during AI response
**Commit:** `ed0ba22`  
**Файлы:** `frontend/src/pages/ChatPage.js`

- Заменили спиннер на анимированные шаги: 📂 Reading sources → 🔍 Searching chunks → 🧠 Thinking → ✍️ Writing answer
- Шаги появляются с задержкой (0 / 1.8 / 3.8 / 6.0 с) для имитации реального процесса
- Адаптация: если нет источников — RAG-шаги пропускаются; если включён Web Search — первый шаг меняется на «Searching the web...»
- Завершённые шаги помечаются ✅ и становятся тусклыми, активный шаг анимирован с bouncing dots

---

## 2026-04-14 — v2.9.10

### Fix/Rollback: auto-save context not writing Project Memory
**Commit:** `6aca086`  
**Файлы:** `backend/routes/messages.py`, `frontend/src/pages/ChatPage.js`

- Откат изменения: авто‑сохранение контекста больше не пишет в Project Memory

---

## 2026-04-14 — v2.9.7

### Fix: AI always knows active sources even when no chunks retrieved
**Файл:** `backend/routes/messages.py`

- Добавлен `elif active_source_names:` блок — если `document_context` пустой но источники активны, AI получает SYS_META с именами источников
- Решает проблему: AI отвечал «нет источников» на мета-вопросы типа «ты видишь файл?», т.к. RAG не находил релевантных чанков по таким запросам

---

## 2026-04-14 — v2.9.6

### Fix: activeSourceIds race condition — send with message payload
**Файлы:** `backend/models/schemas.py`, `backend/routes/messages.py`, `frontend/src/pages/ChatPage.js`

- `MessageCreate` schema: добавлено поле `activeSourceIds: Optional[List[str]]`
- `send_message`: приоритет отдаётся `message_data.activeSourceIds` (real-time из frontend) над DB значением (могло отставать на 500мс из-за debounce)
- `ChatPage.js`: `activeSourceIds` теперь всегда включается в payload сообщения

---

## 2026-04-14 — v2.9.5

### Fix: My Sources shows project badge for sources saved from project chat
**Файл:** `backend/routes/enterprise_sources.py`

- `list_personal_sources`: если у source есть `projectId` (прямая ссылка через save_to_knowledge), добавляет project badge в `publishedTo`
- Дедупликация: не дублирует badge если тот же проект уже есть через `publishedFrom`

---

## 2026-04-14 — v2.9.4

### Fix: save_to_knowledge always saves as personal level
**Файл:** `backend/routes/messages.py`

- `level` всегда `"personal"` — источник появляется в My Sources page
- `projectId` сохраняется для связи с проектом (если вызвано из проектного чата)
- Предыдущий фикс (v2.9.3) ошибочно ставил `level=project`, из-за чего источник не показывался в My Sources

---

## 2026-04-14 — v2.9.3

### RAG — Fix source selection, filename targeting, save-to-sources (`244af3a`)
**Файлы:** `backend/routes/messages.py`, `backend/services/rag.py`

- **Bug fix:** `activeSourceIds` (checkbox в SourcePanel) теперь реально ограничивает RAG-пул.  
  Логика: `null` = чат новый → все источники; `[]` = всё снято вручную → ни одного; `[ids]` = пересечение с accessible.
- **Bug fix:** Pre-RAG filename resolution — если пользователь упоминает имя файла в сообщении, retrieval ограничивается только этим источником.
- **Улучшение:** `SYS_META` теперь содержит `targeted=<filename>` с инструкцией фокусироваться только на упомянутом файле.
- **Улучшение:** `rag.py` — 1.5× score boost для чанков из явно упомянутого источника.
- **Bug fix:** `save_to_knowledge` — при сохранении из проектного чата источник теперь создаётся как `level=project` с реальным `projectId` (раньше всегда `personal + null`).
- **Bug fix:** `save_to_knowledge` — новый источник автоматически добавляется в `chat.activeSourceIds`.

---

### OEM: PDF image extraction, header image upload, brand live preview (`764b813`)
**Файлы:** `backend/routes/oem_datasheet.py`, `frontend/src/pages/AdminBrandsPage.js`

- Добавлена функция `extract_images_from_pdf` (PyMuPDF/fitz) — извлекает изображения из PDF.
- В `rebuild_docx_from_pdf` — изображения вставляются после каждой секции (index 0 пропускается как логотип поставщика).
- Новый endpoint `POST /api/oem/brands/{id}/header-image` — загрузка header image с сохранением в MongoDB (`logoDataMap`).
- Header image вставляется в header-полосу документа рядом с логотипом.
- `extractedImageCount` логируется в `oem_jobs`.
- `AdminBrandsPage`: живой preview бренда (header/footer/colors) справа от формы.
- Слайдеры для `headerHeightPx` (40–120), `logoSizePx` (20–80), `footerHeightPx` (24–60).
- Поле загрузки header image в форме редактирования бренда.

---

### Product matching: AI match-file endpoint + Match File UI (`86deacc`)
**Файлы:** `backend/routes/product_catalog.py`, `frontend/src/pages/ProductCatalogPage.js`

- AI-эндпоинт для сопоставления файла с товарами каталога.
- UI для загрузки файла и просмотра результатов матчинга в ProductCatalogPage.

---

## 2026-04-13

### Fix sidebar layout (`4466540`)
**Файл:** `frontend/src/components/DashboardLayout.js`

- Flex column layout для сайдбара.
- Nav прокручивается независимо.
- Секция пользователя всегда внизу.

---

### Logo persistence — MongoDB base64 fallback (`2a97f3b`)
**Файл:** `backend/routes/oem_datasheet.py`

- Логотипы бренда сохраняются в MongoDB как base64.
- При redeploy (потеря файлов) логотип восстанавливается из базы данных автоматически.

---

### OEM header/footer — full-width edge-to-edge band (`cad5f6e`)
**Файл:** `backend/routes/oem_datasheet.py`

- Полноширинная цветная полоса header/footer через отрицательный `w:ind`.
- Точная высота через `w:lineRule=exact`.
- Контроль: `headerHeightPx`, `headerPaddingPx`, `logoSizePx`, `footerHeightPx`, `footerPaddingPx`.
- Copyright по центру footer-а через tab stop.

---

*Этот файл обновляется вручную после каждого значимого коммита.*
