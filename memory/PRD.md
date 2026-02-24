# Shared Project GPT - Product Requirements Document

## Original Problem Statement
Build a production-ready full-stack SaaS web app called "Shared Project GPT" with:
- One shared GPT configuration (model + developer/system prompt) used by ALL users
- Users work inside Projects with strict isolation (no data leakage between projects)
- Each project has its own chats and history
- Simple email-based login (JWT)
- Admin features for configuring GPT model and system prompt

## Architecture

### Tech Stack
- **Frontend**: React 19 + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Auth**: JWT-based email/password authentication
- **AI**: OpenAI Responses API (gpt-4.1-mini)

### Database Schema (MongoDB Collections)
- **users**: id, email, passwordHash, createdAt
- **projects**: id, name, ownerId, createdAt
- **chats**: id, projectId, name, createdAt
- **messages**: id, chatId, role (user/assistant), content, createdAt
- **gpt_config**: id (singleton), model, developerPrompt, updatedAt

### Security
- JWT tokens with 24h expiration
- Password hashing with bcrypt
- Project ownership validation on every request
- Admin access determined by @admin.com email domain
- API key stored server-side only (never exposed to frontend)

## User Personas

1. **Regular User**: Creates projects, organizes chats, converses with AI
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

### P1 - Should Have
- [ ] Rate limiting per user
- [ ] Project renaming
- [ ] Chat renaming
- [ ] Message editing/deletion
- [ ] Export chat history

### P2 - Nice to Have
- [ ] Knowledge base per project (deferred)
- [ ] Multiple admin users management
- [ ] Usage analytics dashboard
- [ ] Streaming responses
- [ ] File attachments in chat

## What's Been Implemented

### Date: Feb 24, 2026

**Backend** (/app/backend/server.py)
- Complete FastAPI implementation with all CRUD endpoints
- JWT authentication with email/password
- MongoDB integration with proper isolation
- OpenAI Responses API integration
- Admin-only config endpoints

**Frontend** (/app/frontend/src/)
- Login/Register pages with dark theme
- Dashboard with project cards
- Project page with chat list
- Chat page with real-time messaging
- Admin config page with tabs for model and prompt
- Responsive sidebar navigation
- Toast notifications with sonner

**API Endpoints**
- POST /api/auth/register - User registration
- POST /api/auth/login - User login
- GET /api/auth/me - Get current user
- GET/POST/DELETE /api/projects - Projects CRUD
- GET/POST /api/projects/{id}/chats - Chats CRUD
- DELETE /api/chats/{id} - Delete chat
- GET/POST /api/chats/{id}/messages - Messages + AI response
- GET/PUT /api/admin/config - GPT configuration (admin only)

## Prioritized Backlog

1. Add streaming responses for better UX
2. Implement rate limiting
3. Add chat/project renaming
4. Export chat history feature
5. Knowledge base integration (future phase)

## Next Tasks
1. Test with different OpenAI models
2. Add loading states and error boundaries
3. Implement keyboard shortcuts for chat
4. Add message search within chats
