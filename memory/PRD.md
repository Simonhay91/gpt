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
- **Project Sharing** - Owner can share projects with other users
- **Chat Visibility Control** - Owner can choose which chats shared users can see
- **Auto-active Sources** - All sources in a project are automatically used as AI context
- **Sender Names in Chat** - Messages show who sent them (for shared projects)

### Source Management (Project-only)
- Upload files: **PDF, DOCX, PPTX, XLSX, TXT, MD, PNG, JPEG**
- **OCR for Images** - Text is automatically extracted from PNG/JPEG using pytesseract
- **Multiple file upload** supported
- **Preview extracted text** from any source
- **Download individual files**
- Add URLs as sources
- Auto-ingest URLs from chat messages
- AI provides citations referencing source chunks

### Global Sources (Admin Only)
- **Centralized knowledge base** - Admin uploads files/URLs that are available to ALL users
- All global sources are automatically included in GPT context for every chat
- Managed at `/admin/global-sources`
- Supports same file types as project sources

### User Custom Prompt
- Each user can set their own custom GPT instructions
- Custom prompt is added to all conversations
- Private to each user

### Admin Panel
- **User Management** (`/admin/users`)
  - Create new users with generated passwords
  - View all users with token usage stats
  - Delete users
- **Global Sources** (`/admin/global-sources`)
  - Upload files to central knowledge base
  - Add URLs as global sources
  - Preview/delete global sources
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
- `projects` - User projects (with sharedWith array for collaboration)
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

### Users
- `GET /api/users/list` - Get list of users (for sharing)

### Quick Chats
- `GET /api/quick-chats` - List user's quick chats
- `POST /api/quick-chats` - Create quick chat
- `POST /api/chats/{id}/move` - Move chat to project
- `PUT /api/chats/{id}/rename` - Rename chat

### User Settings
- `GET /api/user/prompt` - Get user's custom prompt
- `PUT /api/user/prompt` - Update user's custom prompt

### Projects & Chats
- `GET/POST /api/projects` - List/Create projects
- `GET/DELETE /api/projects/{id}` - Get/Delete project
- `POST /api/projects/{id}/share` - Share project with user
- `DELETE /api/projects/{id}/share/{userId}` - Remove user from project
- `GET /api/projects/{id}/members` - Get project members
- `GET/POST /api/projects/{id}/chats` - List/Create chats
- `GET/DELETE /api/chats/{id}` - Get/Delete chat
- `PUT /api/chats/{id}/visibility` - Update chat visibility for shared users
- `GET/POST /api/chats/{id}/messages` - Get/Send messages

### Sources
- `POST /api/projects/{id}/sources/upload` - Upload single file
- `POST /api/projects/{id}/sources/upload-multiple` - Upload multiple files
- `POST /api/projects/{id}/sources/url` - Add URL
- `GET /api/projects/{id}/sources` - List sources
- `GET /api/projects/{id}/sources/{id}/preview` - Preview extracted text
- `GET /api/projects/{id}/sources/{id}/download` - Download file
- `DELETE /api/projects/{id}/sources/{id}` - Delete source

### Images
- `POST /api/projects/{id}/generate-image` - Generate image
- `GET /api/projects/{id}/images` - List images
- `GET /api/images/{id}` - Get image file

## Changelog

### 2025-12-28
- **Project Sharing** - Share projects with other users
  - User list selection in Share dialog
  - `/api/users/list` endpoint for available users
  - Members management in project
  - **Chat Visibility Control** - Choose which chats each shared user can see
- **Sender Names in Chat** - User messages show sender name for collaboration
- **OCR for Images** - Text extracted from PNG/JPEG using pytesseract (Russian + English)
- **Auto-active Sources** - All sources automatically active in project chats
  - Removed manual checkbox selection
- **New File Types** - Added support for PPTX, XLSX, PNG, JPEG
- **Multiple File Upload** - Upload multiple files at once
- **Source Preview** - View extracted text from any source
- **Source Download** - Download individual files
- **UI Improvements**
  - 5px padding on chat list
  - Preview/Download buttons on source items

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
