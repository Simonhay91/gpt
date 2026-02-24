# Shared Project GPT - Product Requirements Document

## Original Problem Statement
Build a production-ready full-stack SaaS web app called "Shared Project GPT" with:
- One shared GPT configuration (model + developer/system prompt) used by ALL users
- Users work inside Projects with strict isolation (no data leakage between projects)
- Each project has its own chats and history
- Simple email-based login (JWT)
- Admin features for configuring GPT model and system prompt
- **File attachments support** (PDF, DOCX, TXT, MD) with text extraction
- **URL sources** with HTML content extraction
- **Keyword-based retrieval** for relevant chunks
- **Citations** in AI responses

## Architecture

### Tech Stack
- **Frontend**: React 19 + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Auth**: JWT-based email/password authentication
- **AI**: OpenAI Responses API (gpt-4.1-mini)
- **File Processing**: PyPDF2 (PDF), python-docx (DOCX), BeautifulSoup (HTML)

### Database Schema (MongoDB Collections)
- **users**: id, email, passwordHash, createdAt
- **projects**: id, name, ownerId, createdAt
- **chats**: id, projectId, name, activeSourceIds[], createdAt
- **messages**: id, chatId, role, content, citations[], createdAt
- **gpt_config**: id (singleton), model, developerPrompt, updatedAt
- **sources**: id, projectId, kind (file|url), originalName, url, mimeType, sizeBytes, storagePath, createdAt
- **source_chunks**: id, sourceId, projectId, chunkIndex, content, createdAt

### Security
- JWT tokens with 24h expiration
- Password hashing with bcrypt
- Project ownership validation on every request
- Admin access determined by @admin.com email domain
- API key stored server-side only (never exposed to frontend)
- Strict source/chunk isolation by projectId
- All OpenAI calls server-side only

## User Personas

1. **Regular User**: Creates projects, uploads files/URLs, organizes chats, converses with AI
2. **Administrator**: Same as regular user + can configure global GPT settings

## Core Requirements (Static)

### P0 - Must Have (Implemented)
- [x] User registration and login with email/password
- [x] JWT-based authentication
- [x] Create, list, delete projects
- [x] Create, list, delete chats within projects
- [x] Send messages and receive AI responses
- [x] Chat history persistence per chat
- [x] Project isolation (users can only see their own projects)
- [x] Admin config page for model and system prompt
- [x] Dark theme UI
- [x] PDF file upload with text extraction
- [x] DOCX file upload with text extraction
- [x] TXT/MD file upload
- [x] URL source with HTML content extraction
- [x] Chunk-based document storage (~1500 chars)
- [x] Active source selection per chat
- [x] Keyword-based retrieval (query term overlap scoring)
- [x] Citations in AI responses (source name + chunk indices)
- [x] Source deletion with cleanup

### P1 - Should Have
- [ ] Streaming responses for better UX
- [ ] Rate limiting per user
- [ ] Project/Chat renaming
- [ ] Message editing/deletion
- [ ] Export chat history

### P2 - Nice to Have
- [ ] Vector embeddings for semantic search
- [ ] S3 storage for production files
- [ ] More file formats (XLSX, PPT)
- [ ] Usage analytics dashboard

## What's Been Implemented

### Date: Feb 24, 2026 - Initial MVP
- Complete FastAPI backend with all CRUD endpoints
- JWT authentication with email/password
- MongoDB integration with proper isolation
- OpenAI Responses API integration
- Admin-only config endpoints
- Login/Register pages with dark theme
- Dashboard, Project, Chat, Admin pages

### Date: Feb 24, 2026 - Active Sources UX Improvements
- Updated developer prompt with strict ATTACHMENTS / ACTIVE SOURCES RULES
- AI tells users to activate sources when none are selected
- Added `usedSources` field to API response for reliable UI display
- Active sources persist per chat (stored in chat document as `activeSourceIds`)
- Context includes "ACTIVE SOURCES FOR THIS CHAT: <list>" header
- Improved citation format with source names and chunk numbers

## API Endpoints

### Auth
- POST /api/auth/register - User registration
- POST /api/auth/login - User login
- GET /api/auth/me - Get current user

### Projects
- GET/POST /api/projects - Projects CRUD
- GET/DELETE /api/projects/{id} - Single project

### Chats
- GET/POST /api/projects/{id}/chats - Chats CRUD
- GET/DELETE /api/chats/{id} - Single chat

### Sources
- POST /api/projects/{id}/sources/upload - Upload file (PDF, DOCX, TXT, MD)
- POST /api/projects/{id}/sources/url - Add URL source
- GET /api/projects/{id}/sources - List sources
- DELETE /api/projects/{id}/sources/{sourceId} - Delete source
- POST /api/chats/{id}/active-sources - Set active sources
- GET /api/chats/{id}/active-sources - Get active sources

### Messages
- GET/POST /api/chats/{id}/messages - Messages + AI response with citations

### Admin
- GET/PUT /api/admin/config - GPT configuration

## Retrieval Algorithm
1. Get all chunks from active sources (strict project filter)
2. Score each chunk by keyword overlap with query
3. Rank chunks by score descending
4. Select top N chunks (max 10) respecting context limit (15K chars)
5. Include chunk markers in context for citation tracking
6. Return response with deduplicated citations

## Prioritized Backlog
1. Implement streaming responses
2. Add vector embeddings for semantic search
3. Implement S3 storage adapter
4. Add rate limiting

## Next Tasks
1. Add streaming for long responses
2. Implement file preview in UI
3. Add search within sources
4. Consider vector embeddings for large document sets
