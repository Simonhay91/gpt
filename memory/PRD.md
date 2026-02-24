# Shared Project GPT - Product Requirements Document

## Original Problem Statement
Build a production-ready full-stack SaaS web app called "Shared Project GPT" with:
- One shared GPT configuration (model + developer/system prompt) used by ALL users
- Users work inside Projects with strict isolation (no data leakage between projects)
- Each project has its own chats and history
- Simple email-based login (JWT)
- Admin features for configuring GPT model and system prompt
- PDF attachments support with document-based Q&A

## Architecture

### Tech Stack
- **Frontend**: React 19 + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Auth**: JWT-based email/password authentication
- **AI**: OpenAI Responses API (gpt-4.1-mini)
- **PDF Processing**: PyPDF2 for text extraction

### Database Schema (MongoDB Collections)
- **users**: id, email, passwordHash, createdAt
- **projects**: id, name, ownerId, createdAt
- **chats**: id, projectId, name, activeFileIds[], createdAt
- **messages**: id, chatId, role (user/assistant), content, createdAt
- **gpt_config**: id (singleton), model, developerPrompt, updatedAt
- **project_files**: id, projectId, originalName, mimeType, sizeBytes, storagePath, createdAt
- **project_file_chunks**: id, projectFileId, projectId, chunkIndex, content, createdAt

### Security
- JWT tokens with 24h expiration
- Password hashing with bcrypt
- Project ownership validation on every request
- Admin access determined by @admin.com email domain
- API key stored server-side only (never exposed to frontend)
- Strict file isolation by projectId

## User Personas

1. **Regular User**: Creates projects, organizes chats, uploads PDFs, converses with AI
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
- [x] Chunk-based document storage
- [x] Active file selection per chat
- [x] Document context in AI responses
- [x] File deletion with cleanup

### P1 - Should Have
- [ ] Rate limiting per user
- [ ] Project/Chat renaming
- [ ] Message editing/deletion
- [ ] Export chat history
- [ ] Streaming responses

### P2 - Nice to Have
- [ ] Vector embeddings for semantic search
- [ ] Multiple file formats (DOCX, TXT)
- [ ] Usage analytics dashboard
- [ ] File preview in UI

## What's Been Implemented

### Date: Feb 24, 2026 - Initial MVP
- Complete FastAPI backend with all CRUD endpoints
- JWT authentication with email/password
- MongoDB integration with proper isolation
- OpenAI Responses API integration
- Admin-only config endpoints
- Login/Register pages with dark theme
- Dashboard, Project, Chat, Admin pages
- Responsive sidebar navigation
- Toast notifications

### Date: Feb 24, 2026 - PDF Attachments Feature
- PDF upload endpoint with PyPDF2 text extraction
- Text chunking (~1500 chars per chunk)
- Project file storage (local disk, pluggable for S3)
- Active file selection per chat (checkboxes)
- Document context injection in OpenAI requests
- File panel UI with upload button
- File metadata display (size, chunks, date)
- Auto-activation of newly uploaded files
- Error handling for image-based PDFs

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

### Messages
- GET/POST /api/chats/{id}/messages - Messages + AI response

### Files (New)
- POST /api/projects/{id}/files - Upload PDF
- GET /api/projects/{id}/files - List files
- DELETE /api/projects/{id}/files/{fileId} - Delete file
- POST /api/chats/{id}/active-files - Set active files
- GET /api/chats/{id}/active-files - Get active files

### Admin
- GET/PUT /api/admin/config - GPT configuration

## Prioritized Backlog

1. Add streaming responses for better UX
2. Implement rate limiting
3. Add vector embeddings for large document search
4. Support additional file formats (DOCX, TXT)
5. Add file preview in UI

## Next Tasks
1. Implement streaming responses
2. Add progress indicator for large file uploads
3. Add file search within projects
4. Consider S3 storage for production
