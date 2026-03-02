# Planet GPT - Product Requirements Document

## Обзор продукта
Planet GPT - корпоративная SaaS-платформа для работы с AI (GPT) с многоуровневой иерархией знаний.

## Пользователи
- **Admin** - полный доступ к системе, управление пользователями, отделами, глобальными источниками
- **Department Manager** - управление источниками отдела, одобрение публикаций
- **User** - работа с проектами, личные источники, чаты

## Технический стек
- Frontend: React, Tailwind CSS, Shadcn/UI
- Backend: FastAPI, MongoDB, Motor
- AI: OpenAI GPT-4.1-mini, text-embedding-3-small
- AI (Analyzer): Google Gemini 2.5 Flash via emergentintegrations

---

## ENTERPRISE KNOWLEDGE ARCHITECTURE

### Уровни знаний (иерархия)
1. **Personal** - личные черновики пользователя (полностью приватные)
2. **Project** - знания конкретного проекта
3. **Department** - знания отдела (требует approval)
4. **Global** - корпоративная истина (требует approval)

### Retrieval порядок
**Project → Department → Global**

- Project имеет приоритет над Department
- Department имеет приоритет над Global
- Берётся несколько уровней если coverage слабый
- Override только при явном конфликте

### Права на изменение
| Уровень | Кто может изменять |
|---------|-------------------|
| Global | Только Admin |
| Department | Department Manager |
| Project | Project Owner/Manager |
| Personal | Владелец |

### Версионирование
- **Автоматическое** при каждом изменении
- Хранится: sourceId, version, contentHash, chunks, metadata
- Restore создаёт **новую версию** (не тихий откат)

### Approval Workflow (Department/Global)
```
draft → pending → approved → active
```
- Project источники: сразу active
- Department/Global: требуют одобрения менеджера/админа

### Audit Log
- Логируются: create, update, delete, approve, reject, publish, restore
- Фильтры: entity, action, level, userId, dateRange
- Доступ: Admin - все логи, Manager - логи своего отдела

---

## Реализованные функции

### ✅ Core Features
- [x] Multi-user authentication (admin-centric)
- [x] Project-based data isolation
- [x] Chat with GPT (streaming)
- [x] Source upload (PDF, DOCX, TXT, MD, PPTX, XLSX, CSV, images with OCR)
- [x] Auto-ingest URLs from chat messages
- [x] Light/Dark theme

### ✅ Role-Based Access Control
- [x] Permission matrix: Viewer, Editor, Manager
- [x] Project sharing with roles
- [x] Chat visibility control per user

### ✅ Enterprise Knowledge Architecture
- [x] Department management (CRUD, members, managers)
- [x] Personal sources (upload, list, delete)
- [x] Publish: Personal → Project/Department (copy with new ID)
- [x] Source versioning (auto on change)
- [x] Hierarchical retrieval (Project > Department > Global)
- [x] Audit logging for Department/Global changes
- [x] Approval workflow (draft → approved → active)
- [x] **Department sources page** with full workflow UI
- [x] **Retrieval integration** - department sources используются в чатах

### ✅ Excel/CSV Analyzer (Gemini AI)
- [x] File upload (CSV, XLSX) with preview table
- [x] Session-based analysis with conversation history
- [x] Quick questions templates
- [x] Gemini AI integration for data analysis
- [x] Multi-language support (RU/EN)
- [x] Export to Excel (.xlsx) with styled report
- [x] Export to PDF with formatted Q&A

### ✅ Multi-Language Support (i18n)
- [x] Language context with RU/EN translations
- [x] Language switcher in sidebar
- [x] Translated: Dashboard, Sidebar, Login, News, Admin pages
- [ ] ~30% pages still need translation

### ✅ Admin Features
- [x] User management with department assignment
- [x] Global sources management
- [x] GPT config (model, prompts)
- [x] Audit logs viewer with filters
- [x] Cache management (semantic caching)

### ✅ Security
- [x] Secure semantic caching (isolated by project, prompts, model, sources)
- [x] Backend permission checks on all endpoints
- [x] JWT authentication

---

## API Endpoints

### Departments
- `GET /api/departments` - List departments
- `POST /api/departments` - Create department (admin)
- `GET /api/departments/{id}` - Get department details
- `PUT /api/departments/{id}` - Update department
- `DELETE /api/departments/{id}` - Delete department
- `POST /api/departments/{id}/members` - Add member
- `DELETE /api/departments/{id}/members/{userId}` - Remove member
- `PUT /api/departments/{id}/members/{userId}/manager` - Toggle manager

### Personal Sources
- `GET /api/personal-sources` - List user's personal sources
- `POST /api/personal-sources/upload` - Upload personal source
- `DELETE /api/personal-sources/{id}` - Delete personal source
- `POST /api/personal-sources/{id}/publish` - Publish to project/department

### Source Versions
- `GET /api/sources/{id}/versions` - Get source versions
- `POST /api/sources/{id}/restore` - Restore version (creates new)

### Approval
- `POST /api/sources/{id}/approval` - Submit/approve/reject source

### Audit Logs
- `GET /api/admin/audit-logs` - Get audit logs with filters

### Excel/CSV Analyzer
- `POST /api/analyzer/upload` - Upload file for analysis
- `POST /api/analyzer/ask` - Ask question about uploaded data
- `GET /api/analyzer/session/{id}` - Get session info and history
- `DELETE /api/analyzer/session/{id}` - Delete analysis session
- `GET /api/analyzer/session/{id}/export/excel` - Export to Excel
- `GET /api/analyzer/session/{id}/export/pdf` - Export to PDF

### News
- `GET /api/news` - Get tech news from Hacker News API

### User Departments
- `GET /api/users/me/departments` - Get user's departments
- `PUT /api/users/me/primary-department` - Set primary department

---

## Архитектура файлов

```
/app/
├── backend/
│   ├── models/
│   │   └── enterprise.py      # Enterprise data models
│   ├── routes/
│   │   ├── departments.py     # Department routes
│   │   ├── enterprise_sources.py  # Personal/version/audit routes
│   │   ├── analyzer.py        # Excel/CSV Analyzer with Gemini
│   │   └── news.py            # Tech News API
│   ├── services/
│   │   └── enterprise.py      # AuditService, VersionService, HierarchicalRetrieval
│   ├── server.py              # Main FastAPI app (3600+ lines)
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── ExcelAnalyzerPage.js  # Gemini data analyzer
    │   │   ├── NewsPage.js           # Tech news
    │   │   ├── MyGptPromptPage.js    # User's GPT prompt
    │   │   ├── AdminDepartmentsPage.js
    │   │   ├── AdminAuditLogsPage.js
    │   │   ├── PersonalSourcesPage.js
    │   │   └── ...
    │   ├── i18n/
    │   │   └── translations.js    # RU/EN translations
    │   ├── contexts/
    │   │   └── LanguageContext.js # Language switcher
    │   └── components/
    │       └── DashboardLayout.js  # Navigation with new links
    └── package.json
```

---

## Pending / Backlog

### P0 (High Priority)
- [x] ~~UI for editing existing member roles in projects~~ (fixed in prev session)
- [x] ~~"Departments" navigation link disappearing on route changes~~ (fixed)

### P1 (Medium Priority)
- [ ] Complete i18n for all pages (~30% remaining)
- [ ] Page for Pending Approvals (unified dashboard for managers)
- [ ] Admin UI for cache settings (TTL, similarity threshold)
- [ ] Question templates

### P2 (Low Priority)
- [ ] Show sources before sending to LLM
- [ ] Usage/cost dashboard
- [ ] Bookmarks for tech news
- [ ] Global search across chats/projects
- [ ] Chat export to PDF/Markdown
- [ ] User-level token limits

### Refactoring
- [ ] Break down server.py into modular routers
- [ ] Fix useEffect dependency warnings
- [ ] Split translations.js by page/feature

---

## Credentials for Testing
- **Admin**: admin@admin.com / admin123
- **Test Users**: Create via admin panel

## Last Updated
2026-03-02 - Added Excel/CSV Analyzer with Gemini AI integration (full e2e functionality)
