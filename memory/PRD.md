Planet Knowledge
Product Requirements Document — v1.7
Last Updated: March 2026

18. Session Updates (2026-03) — New Features

18.1 RAG Pipeline — Voyage AI Embeddings ✅
Semantic search fully implemented. Voyage AI (voyage-3) replaces OpenAI embeddings. Cosine similarity via numpy in rag.py. Semantic cache at 0.95 threshold.



18.2 Project Memory ✅
AI-extracted project-level memory persisted across sessions.

Flow: button → AI extraction → popup with selectable points → token counter → save
1500-token limit per project
Backend: GET/PUT /projects/{id}/memory
POST /chats/{id}/extract-memory-points
Memory injected into system prompts in messages.py
Chat history optimized to last 20 messages

18.3 Image Generation ✅
DALL-E 3 for generation, DALL-E 2 for inpainting. Pillow for resize/upscale.



18.4 AI Personalization ✅
User ai_profile and department ai_context fields in MongoDB. Dynamic system prompt assembly at chat start.

Fields: display_name, position, department_id, preferred_language, response_style, custom_instruction
Department ai_context editable by admin and department managers only
Validation limits in place

18.5 Competitor Tracker ✅
Sales department feature. Fetches and caches competitor URLs.

httpx + BeautifulSoup (3000 char limit per page)
competitor_tracker_enabled boolean per department
date-fns downgraded to ^3.6.0 to resolve version conflict

18.6 Save Context / User Memory ✅
'Save Context' button in chat triggers AI summarization (max 150 words). Saved to user's AI Profile with date-prefixed label. Auto-injected into new chat system prompts. User-level, not department-level.

18.7 Clarifying Questions ✅
AI automatically detects ambiguous questions and asks for clarification with clickable option buttons.

Backend: messages.py parses <clarifying> tags from Claude response
Schema: MessageResponse extended with clarifying_question and clarifying_options fields
System prompt: Claude instructed to use structured <clarifying> format
Frontend: ChatPage.js renders amber-colored question card with clickable buttons
Auto-send on button click; user can also ignore and type freely
Multilingual — AI adapts question language to user language



18.8 Brave Web Search Integration ✅
AI uses Brave Search API when RAG sources are insufficient or user explicitly requests research.

Trigger 1: RAG finds no relevant chunks (score < 0.7)
Trigger 2: User uses keywords — 'research', 'найди в интернете', 'գտիր', 'փնտրիր'
API: https://api.search.brave.com/res/v1/web/search, count=5
Results passed as context to Claude with source attribution
Frontend: web_sources shown as clickable links under AI message
Env var: BRAVE_API_KEY



18.9 URL Auto-Fetch in Chat ✅
When user pastes a URL in chat, AI automatically fetches and reads the content.

URL detection: regex https?://\S+ in user message
PDF: pypdf text extraction
HTML pages: BeautifulSoup — extracts p, h1, h2, h3 tags
Content truncated to 8000 characters
Added as context to Claude with label 'Содержимое по ссылке {url}'
Silent fail — if fetch fails, continues without error

18.10 Edit Message ✅
Users can edit their sent messages. AI regenerates response from the edited point.

Hover on user message → pencil icon appears
Click → message becomes editable field with Save/Cancel
On Save: messages AFTER edited message are deleted (not all messages)
AI regenerates response for the edited message
Backend: PUT /api/chats/{chat_id}/messages/{message_id}/edit
Deletion query uses createdAt > current_message.createdAt

19. Product Catalog — Phase 3 (Planned)

19.1 Overview
Phase 3 extends the Product Catalog with AI-powered chat, smart relations, and bulk import tools.

19.2 Smart Relations
Three-layer relation system for connecting related products:



Schema Update — ProductRelation
Existing ProductRelation model extended with source tracking fields (additive, no existing fields modified):

source: Literal['auto', 'manual', 'csv'] = 'manual'
added_by: Optional[str] = None
added_at: Optional[str] = None

Auto-Relations Engine
Endpoint: POST /api/product-catalog/auto-relations (Admin/Manager only)
Parses attribute_values field (semicolon-separated Key: Value pairs)
Normalizes attribute key names via fuzzy matching (difflib, 80% threshold)
Extracts numeric values and ranges — supports formats: 5.5±0.5, 5.1 - 5.6, 1.5 kN
Compares products within same lvl1_subcategory for numeric overlap
Creates bidirectional compatible relations, no duplicates

CSV Relations Import
Endpoint: POST /api/product-catalog/import-relations
Format: crm_code | related_crm_codes (comma-separated)
System automatically creates bidirectional relations
Export: GET /api/product-catalog/export-relations

19.3 Product Catalog Chat Assistant
Dedicated AI chat for product discovery, embedded as sidebar in the Product Catalog page.



Endpoint: POST /api/product-catalog/chat
Input: message (str), chat_history (last 10 messages)
Embeddings: POST /api/product-catalog/generate-embeddings (Admin only, upsert by crm_code)
Response: answer (str), sources [{crm_code, title_en, relations}]

19.4 Department Access Control
Admin controls which departments have access to Product Catalog.

New field: product_catalog_enabled: bool = False on departments collection
Endpoint: PATCH /api/departments/{id}/product-catalog-access (Admin only)
Access rule: Admin always — others only if their department has access enabled
Members see catalog + chat. Managers can import/export.

19.5 Product Catalog UI — Phase 3



20. Current Feature Status (March 2026)



21. Updated Tech Stack



22. Known Open Issues



Planet Knowledge PRD v1.7 — Confidential


## Session Update (Feb 2026)

### Completed: URL Content Fetching + UI Indicator

**Feature:** Auto-read URL content in chat messages with visual feedback

**Backend (`routes/messages.py`):**
- Integrated `fetch_url_content` into `send_message` endpoint (after RAG context build)
- Tracks `fetched_urls_list` (list of successfully fetched URLs)
- Passes fetched URL content as context section to Claude (up to 18000 chars when URL present)
- Stores `fetchedUrls` field in assistant message document

**Backend (`models/schemas.py`):**
- Added `fetchedUrls: Optional[List[str]] = None` to `MessageResponse`

**Frontend (`pages/ChatPage.js`):**
- Added sky-blue pill badge "🔗 URL прочитан: domain.com" below AI response
- Clickable badge opens URL in new tab
- Handles multiple fetched URLs (one badge per URL)

**Tests passed:**
- HTML: `https://httpbin.org/html` → AI correctly described Moby Dick ✅
- PDF: `https://filesamples.com/samples/document/pdf/sample1.pdf` → AI correctly read document ✅
- `fetchedUrls: ['https://...']` present in API response ✅
- UI badge renders correctly below AI message ✅
