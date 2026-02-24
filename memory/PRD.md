# Planet GPT - Product Requirements Document

## Overview
Planet GPT is a multi-user SaaS platform for AI-powered conversations with project-based data isolation. Users share a single, admin-configurable GPT configuration while maintaining separate projects and chats.

## Core Features

### Authentication & User Management
- **Admin-only user creation** - No self-registration, admin creates users
- **Email/password login** - Simple JWT-based authentication
- **Admin detection** - Users with `@admin.com` email have admin privileges
- **User token tracking** - Admin can see how many tokens each user consumed

### Quick Chats (No Project)
- Users can start chats without creating a project first
- Quick chats appear in "My Chats" section on Dashboard
- Users can move quick chats to a project later
- Quick chats don't have access to file sources

### Project-based Conversations
- Each user can create multiple projects
- Projects contain chats with access to file/URL sources
- Strict data isolation - users only see their own projects

### Source Management (Project-only)
- Upload files: PDF, DOCX, TXT, MD
- Add URLs as sources
- Auto-ingest URLs from chat messages
- Select active sources per chat for AI context
- AI provides citations referencing source chunks

### User Custom Prompt
- Each user can set their own custom GPT instructions
- Custom prompt is added to all conversations
- Private to each user

### Admin Panel
- **User Management** (`/admin/users`)
  - Create new users with generated passwords
  - View all users with token usage stats
  - Delete users
- **GPT Config** (`/admin/config`)
  - Set global GPT model
  - Configure developer system prompt

### Image Generation (Project-only)
- Generate images using OpenAI DALL-E
- Images stored per project
- Authenticated image access

## Technical Stack
- **Frontend**: React + Tailwind CSS + Shadcn/UI
- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **AI**: OpenAI GPT-4.1-mini for chat, DALL-E 3 for images

## Database Collections
- `users` - User accounts
- `projects` - User projects
- `chats` - Conversations (can belong to project or be "quick chat")
- `messages` - Chat messages with citations
- `sources` - Uploaded files and URLs
- `source_chunks` - Chunked source text for retrieval
- `gpt_config` - Global GPT configuration (singleton)
- `user_prompts` - User custom instructions
- `token_usage` - Per-user token consumption tracking
- `generated_images` - AI-generated images

## API Endpoints

### Auth
- `POST /api/auth/login` - User login

### Admin - User Management
- `POST /api/admin/users` - Create user (admin only)
- `GET /api/admin/users` - List all users with usage stats
- `DELETE /api/admin/users/{id}` - Delete user

### Admin - Config
- `GET /api/admin/config` - Get GPT config
- `PUT /api/admin/config` - Update GPT config

### Quick Chats
- `GET /api/quick-chats` - List user's quick chats
- `POST /api/quick-chats` - Create quick chat
- `POST /api/chats/{id}/move` - Move chat to project

### User Settings
- `GET /api/user/prompt` - Get user's custom prompt
- `PUT /api/user/prompt` - Update user's custom prompt

### Projects & Chats
- `GET/POST /api/projects` - List/Create projects
- `GET/DELETE /api/projects/{id}` - Get/Delete project
- `GET/POST /api/projects/{id}/chats` - List/Create chats
- `GET/DELETE /api/chats/{id}` - Get/Delete chat
- `GET/POST /api/chats/{id}/messages` - Get/Send messages

### Sources
- `POST /api/projects/{id}/sources/upload` - Upload file
- `POST /api/projects/{id}/sources/url` - Add URL
- `GET /api/projects/{id}/sources` - List sources
- `DELETE /api/projects/{id}/sources/{id}` - Delete source
- `GET/POST /api/chats/{id}/active-sources` - Get/Set active sources

### Images
- `POST /api/projects/{id}/generate-image` - Generate image
- `GET /api/projects/{id}/images` - List images
- `GET /api/images/{id}` - Get image file

## Changelog

### 2026-02-24
- Renamed from "Shared GPT" to "Planet GPT"
- Removed user self-registration
- Added admin user management with:
  - Create/delete users
  - Password generation
  - Token usage tracking per user
- Added Quick Chats feature (chats without project)
- Added "Move chat to project" functionality
- Added User custom GPT prompt settings

### Previous
- Initial MVP with projects, chats, file sources
- Multi-format source support (PDF, DOCX, TXT, MD, URLs)
- Auto-ingest URLs from messages
- Active source persistence per chat
- AI citations in responses
- Image generation with DALL-E

## Admin Credentials
- Email: `admin@admin.com`
- Password: `admin123`

## Future Tasks (Backlog)
- P1: Document preview panel
- P1: Source search/filter
- P2: Usage/cost dashboard
- P2: Background ingestion for large files
- P2: "Clear Active Sources" toggle
