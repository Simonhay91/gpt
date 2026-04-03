# Planet Knowledge — Product Requirements Document

**Version:** 2.9  
**Last Updated:** Апрель 2026  
**Admin credentials:** `admin@ai.planetworkspace.com` / `Admin@123456`

---

## 1. Продукт

**Planet Knowledge** — корпоративная платформа управления знаниями с AI-чатом, семантическим поиском и аналитикой.

### Миссия
Объединить все корпоративные знания в единую систему с интеллектуальным поиском и анализом на базе AI.

---

## 2. Роли пользователей

| Роль | Возможности |
|------|------------|
| **Admin** | Всё + управление пользователями, GPT config, глобальные источники, аудит |
| **Manager** | Одобрение источников, управление отделом, создание контента |
| **Editor** | Создание и редактирование источников, чат |
| **Viewer** | Просмотр, чат с AI |

---

## 3. Текущая архитектура

### Backend
```
Framework:    FastAPI (Python 3.11+)
Database:     MongoDB (motor async driver)
AI:           Claude claude-sonnet-4-20250514 (via emergentintegrations)
Embeddings:   Voyage AI (voyage-3)
Web Search:   Brave Search API
URL Parsing:  BeautifulSoup4 + pypdf + pdfplumber
Auth:         JWT (PyJWT)
Scheduler:    APScheduler

Services:
  services/web_search.py      — Brave search, URL fetching, auto-ingest
  services/catalog_service.py — Product catalog search
  services/excel_service.py   — Excel generation + targeted edits (openpyxl/pandas)
  services/agents.py          — Agent definitions (excel/research/rag/general)
  services/agent_router.py    — Rule-based + Claude Haiku routing
  routes/messages.py          — RAG + Chat AI + agent routing (~1061 lines)
  routes/temp_files.py        — Temp file upload/save endpoints
```

### Frontend
```
Framework:    React 18
Styling:      Tailwind CSS
Components:   Shadcn/UI
Icons:        Lucide React
HTTP:         Axios
Routing:      React Router v6

Chat Components:
  pages/ChatPage.js                    — Orchestrator (~940 lines)
  components/chat/MessageBubble.js     — Single message rendering + Excel/confirm buttons
  components/chat/SourcePanel.js       — Sources panel UI
  components/chat/ChatInput.js         — Input area + plus menu + paperclip
  data/changelog.js                    — App version + changelog (v2.9.0)
```

### Структура проекта
```
/app/
├── backend/
│   ├── db/connection.py
│   ├── middleware/auth.py
│   ├── models/schemas.py            # Pydantic models (MessageCreate, MessageResponse)
│   ├── services/
│   │   ├── rag.py
│   │   ├── cache.py
│   │   ├── file_processor.py
│   │   ├── web_search.py
│   │   ├── catalog_service.py
│   │   ├── excel_service.py
│   │   ├── agents.py                # NEW: Agent definitions
│   │   └── agent_router.py          # NEW: Agent routing logic
│   ├── routes/
│   │   ├── messages.py
│   │   ├── temp_files.py            # NEW: /api/chat/upload-temp, /api/chat/save-temp-to-source
│   │   ├── sources.py
│   │   ├── projects.py
│   │   ├── auth.py
│   │   ├── chats.py
│   │   ├── images.py
│   │   ├── admin.py
│   │   ├── excel.py
│   │   └── ...
│   └── server.py
│
└── frontend/src/
    ├── components/chat/
    │   ├── MessageBubble.js
    │   ├── SourcePanel.js
    │   └── ChatInput.js
    ├── contexts/
    │   ├── AuthContext.js           # exports: user (not currentUser)
    │   └── LanguageContext.js
    ├── data/changelog.js            # APP_VERSION = "2.9.0"
    ├── i18n/translations.js
    └── pages/
        ├── ChatPage.js
        ├── DashboardPage.js
        ├── ProjectPage.js
        └── ...
```

### MongoDB Collections
```
users            # Пользователи (roles, ai_profile, departments)
projects         # Проекты (project_memory)
chats            # Чаты (quick + project, sourceMode)
messages         # Сообщения (citations, web_sources, excel_file_id,
                 #   is_excel_clarification, agent_type, agent_name, uploadedFile)
sources          # Все источники (personal/project/department/global)
source_chunks    # Векторные chunks (embedding via Voyage AI)
departments      # Отделы
gpt_config       # Настройки AI (developer prompt, model)
audit_logs       # Аудит логи
semantic_cache   # Кэш ответов
token_usage      # Статистика токенов
user_prompts     # Пользовательские промпты
source_usage     # Статистика источников
product_catalog  # Каталог продуктов
competitors      # Конкурентный трекер
```

---

## 4. Реализованные функции ✅

| Модуль | Статус | Описание |
|--------|--------|----------|
| Аутентификация | ✅ | JWT, 4 роли, смена пароля |
| Проекты | ✅ | CRUD, участники, project memory |
| Quick Chats | ✅ | Чат без проекта |
| RAG Pipeline | ✅ | Voyage AI embeddings, cosine similarity |
| Semantic Cache | ✅ | Схожесть > 0.95 → кэш |
| Personal Sources | ✅ | Upload, URL, knowledge save |
| Project Sources | ✅ | Upload, URL, dept copy |
| Department Sources | ✅ | Workflow одобрения, manager controls |
| Global Sources | ✅ | Admin only |
| Source Insights | ✅ | AI summary + 5 вопросов по источнику |
| Brave Web Search | ✅ | Авто-триггер + стоп-слова (RU/EN/AM) |
| URL Content Fetch | ✅ | Авто-чтение HTML/PDF из URL в сообщении |
| Edit Message | ✅ | Редактирование + регенерация AI ответа |
| Clarifying Questions | ✅ | AI задаёт уточняющие вопросы с кнопками |
| Save Context | ✅ | Суммаризация чата → AI Profile |
| Project Memory | ✅ | Ключевые факты → фон для AI |
| Image Generation | ✅ | gpt-image-1 via Emergent LLM Key |
| Excel Generation | ✅ | Полный pipeline: pandas + openpyxl targeted edits |
| Excel Confirmation | ✅ | __CONFIRM_EXCEL__ prefix flow, кнопка в UI |
| Temp File Upload | ✅ | Скрепка в чате, /api/chat/upload-temp, vision + text |
| Agent Routing | ✅ | 4 агента: excel/research/rag/general, rule + Haiku |
| Competitor Tracker | ✅ | Отслеживание конкурентов |
| Product Catalog | ✅ | Фазы 1-2: CRUD, CSV import, relations |
| Tech News | ✅ | Hacker News |
| Admin Audit Logs | ✅ | Фильтрация + пагинация |
| i18n (RU/EN) | 🔄 | ~80% переведено |
| Changelog UI | ✅ | История обновлений в интерфейсе (v2.9.0) |

---

## 5. Схема ключевых полей

### Message (в БД) — актуальная
```python
{
  "id": str,
  "chatId": str,
  "role": "user" | "assistant",
  "content": str,
  "citations": [{sourceId, sourceName, sourceType, chunks}],
  "usedSources": [{sourceId, sourceName, sourceType}],
  "web_sources": [{"title": str, "url": str}],
  "fetchedUrls": [str],
  "clarifying_question": str,
  "clarifying_options": [str],
  "fromCache": bool,
  "autoIngestedUrls": [str],
  "excel_file_id": str | None,          # ID в /tmp/excel_result_{uuid}.xlsx
  "excel_preview": dict | None,         # {columns, rows, total_rows, message}
  "is_excel_clarification": bool,       # True = AI задал уточн. вопросы перед генерацией
  "uploadedFile": dict | None,          # {name, fileType} — temp file badge
  "agent_type": str | None,             # "excel"|"research"|"rag"|"general"
  "agent_name": str | None,             # "Excel Agent" | "Research Agent" | ...
  "createdAt": ISO datetime
}
```

### User (в БД)
```python
{
  "id": str,
  "email": str,
  "isAdmin": bool,
  "role": str,
  "departments": [str],
  "ai_profile": {
    "display_name": str,
    "position": str,
    "preferred_language": "ru" | "en",
    "response_style": str,
    "custom_instruction": str
  },
  "gptModel": str
}
```

---

## 6. Ключевые API эндпоинты

```
# Auth
POST   /api/auth/login
GET    /api/auth/me

# Chats & Messages
POST   /api/quick-chats
POST   /api/projects/{id}/chats
POST   /api/chats/{id}/messages              # RAG + Brave + Claude + Agent routing
PUT    /api/chats/{id}/messages/{msg_id}/edit
POST   /api/chats/{id}/save-context
POST   /api/chats/{id}/extract-memory-points

# Temp File Upload (NEW)
POST   /api/chat/upload-temp                 # multipart: file + chat_id
POST   /api/chat/save-temp-to-source         # JSON: temp_file_id, project_id, ...

# Excel
GET    /api/excel/download/{file_id}

# Sources
POST   /api/projects/{id}/sources/upload
POST   /api/projects/{id}/sources/url
DELETE /api/projects/{id}/sources/{id}
POST   /api/save-to-knowledge

# Product Catalog
GET    /api/product-catalog
POST   /api/product-catalog/import
POST   /api/product-catalog/match

# Admin
GET    /api/admin/users
GET    /api/admin/audit-logs?limit=&offset=
GET    /api/admin/gpt-config
PUT    /api/admin/gpt-config
```

---

## 7. Приоритизированный бэклог

### 🟠 P1 — Высокий приоритет

#### Fix init_admin_user (продакшен)
- **Что:** При создании нового admin в `server.py` не добавляются `isAdmin: True` и `role: "admin"`
- **Где:** `server.py` → функция `init_admin_user`
- **Эффект:** На чистой БД (продакшен) admin логинится, но не имеет прав
- **Статус:** НЕ ИСПРАВЛЕНО ⚠️

#### Excel файлы → Object Storage
- **Что:** Сейчас Excel сохраняется в `/tmp/excel_result_{uuid}.xlsx` — теряется при перезапуске
- **Как:** Мигрировать на persistent object storage через `integration_playbook_expert_v2`
- **Затронуто:** `excel_service.py`, `routes/excel.py`, `MessageBubble.js` (download URL)
- **Статус:** НЕ РЕАЛИЗОВАНО ⚠️

#### Product Catalog AI Integration (Фаза 3)
- `POST /api/product-catalog/chat-search` — AI ищет в каталоге по запросу из чата
- Тендерный анализ: загрузить список → AI сопоставляет с каталогом

### 🟡 P2 — Средний приоритет

- **i18n** — оставшиеся ~20% строк (`ChatPage.js`, модали, toasts)
- **Agent badge в UI** — показывать `agent_name` под ответом AI в `MessageBubble`
- **Product Catalog Weekly Sync** — APScheduler job каждое воскресенье

### 🔵 P3 — Низкий приоритет

- **useEffect dependency warnings** — не критично, нет рантайм-эффекта
- **API Rate Limiting** — FastAPI middleware + counter
- **Question Templates** — сохранённые шаблоны вопросов
- **Dashboard использования** — токены per-user, топ источников
- **Глобальный поиск** — `GET /api/search?q=...`
- **Экспорт чата** — PDF/Markdown
- **Mobile responsive** — адаптив для < 768px
- **SSO / SAML** — корпоративная аутентификация
- **Sentry** — production error tracking

---

## 8. Известные технические долги

| Файл | Проблема | Приоритет |
|------|----------|-----------|
| `server.py` → `init_admin_user` | Не проставляет `isAdmin`/`role` | P1 |
| `excel_service.py` | Excel в `/tmp` — теряется при рестарте | P1 |
| `messages.py` | ~1061 строк, смешана бизнес-логика | P2 |
| `enterprise_sources.py` | ~802 строк | P3 |
| i18n | ~20% строк не переведено | P2 |
| `useEffect` warnings | Отсутствующие зависимости | P3 |

---

## 9. Changelog — сессии

### Апрель 2026 (текущая сессия)
- ✅ **P0 Crash fix** — `ChatPage.js` использовал `currentUser` вместо `user` из `useAuth()`. Исправлено в 4 местах.
- ✅ **Excel confirmation flow** — `__CONFIRM_EXCEL__` prefix вместо ненадёжного поиска "excel" в истории. Кнопка «Да, генерируй Excel» в UI. Поле `is_excel_clarification` в MessageResponse.
- ✅ **Temp File Upload** — POST /api/chat/upload-temp (JPG/PNG/PDF/XLSX/CSV/DOCX ≤20MB). Скрепка в ChatInput. Vision для изображений. Prompt «Сохранить в источники?» после ответа AI. POST /api/chat/save-temp-to-source с индексацией через Voyage AI.
- ✅ **Agent Routing System** — `services/agents.py` (4 агента) + `services/agent_router.py` (rule-based + Claude Haiku). Поля `agent_type`/`agent_name` в каждом assistant message. AsyncAnthropic для non-blocking routing.
- ✅ **Excel download UX** — tooltip "Файл доступен до перезапуска", 404-specific error toast.
- ✅ **Web Search bug fix** — армянские romanized команды (`poxi`, `popoxir`, `gri`, `avel`, `jnjel`) добавлены в `_TRIVIAL_STOP` и `_ARMENIAN_EDIT_WORDS` — больше не триггерят web search.
- ✅ **Changelog обновлён** — v2.9.0, 4 новые записи.

### Март 2026 (рефакторинг + Excel)
- ✅ **messages.py рефакторинг** — разбит на `web_search.py`, `catalog_service.py`, `excel_service.py`
- ✅ **ChatPage.js рефакторинг** — `MessageBubble.js`, `SourcePanel.js`, `ChatInput.js`
- ✅ **Excel targeted edits** — `openpyxl` для точечного редактирования ячеек, формулы, цвета (HEX PatternFill)
- ✅ **Image generation** — мигрирован на `emergentintegrations` + `gpt-image-1`
- ✅ **Product Catalog** — Фазы 1-2: CRUD, CSV import, relations
- ✅ **Brave Web Search** — авто-fallback, стоп-слова, BeautifulSoup fetch

### Февраль 2026
- ✅ URL Content Fetching, Clarifying Questions, Save Context, Project Memory
- ✅ Image Generator reference photo, JWT 7 days, Auth fix
- ✅ Source Insights, Competitor Tracker, Audit Logs pagination

### Октябрь–Январь 2026
- ✅ RAG Pipeline (Voyage AI), Semantic Cache, Admin panel
- ✅ Аутентификация + роли, Проекты, Quick Chats, i18n foundation

---

## 10. Тестовые аккаунты

| Роль | Email | Пароль |
|------|-------|--------|
| Admin | admin@ai.planetworkspace.com | Admin@123456 |

---

*Planet Knowledge PRD v2.9 — Confidential*
