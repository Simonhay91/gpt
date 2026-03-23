# Planet Knowledge — Product Requirements Document

**Version:** 2.1  
**Last Updated:** February 2026  
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
URL Parsing:  BeautifulSoup4 + pypdf
Auth:         JWT (PyJWT)
Scheduler:    APScheduler
```

### Frontend
```
Framework:    React 18
Styling:      Tailwind CSS
Components:   Shadcn/UI
Icons:        Lucide React
HTTP:         Axios
Routing:      React Router v6
```

### Структура проекта
```
/app/
├── backend/
│   ├── db/connection.py             # MongoDB connection
│   ├── middleware/auth.py           # JWT auth middleware
│   ├── models/schemas.py            # Pydantic models
│   ├── services/
│   │   ├── rag.py                   # RAG pipeline (Voyage AI embeddings)
│   │   ├── cache.py                 # Semantic cache
│   │   └── file_processor.py        # File text extraction
│   ├── routes/
│   │   ├── admin.py                 # Admin panel (~429 lines)
│   │   ├── auth.py                  # Authentication (~50 lines)
│   │   ├── chats.py                 # Chat CRUD (~217 lines)
│   │   ├── competitors.py           # Competitor tracker (~418 lines)
│   │   ├── departments.py           # Departments (~430 lines)
│   │   ├── enterprise_sources.py    # Corporate sources (~802 lines)
│   │   ├── global_sources.py        # Global sources (~369 lines)
│   │   ├── images.py                # Image generation (~189 lines)
│   │   ├── insights.py              # AI analytics (~288 lines)
│   │   ├── messages.py              # RAG + Chat AI (~1061 lines) ⚠️ needs refactor
│   │   ├── news.py                  # Tech news (~108 lines)
│   │   ├── product_catalog.py       # Product catalog
│   │   ├── projects.py              # Projects (~336 lines)
│   │   ├── sources.py               # Sources upload (~647 lines)
│   │   └── user_settings.py         # AI Profile, prompts (~232 lines)
│   └── server.py                    # Entry point (~177 lines) ✅ refactored
│
└── frontend/src/
    ├── components/
    │   ├── ui/                      # Shadcn components
    │   ├── DashboardLayout.js
    │   ├── ImageGenerator.js
    │   ├── ProjectMemoryModal.js
    │   └── SmartQuestions.js
    ├── contexts/
    │   ├── AuthContext.js
    │   └── LanguageContext.js
    ├── i18n/translations.js
    └── pages/
        ├── ChatPage.js              # ~1441 lines ⚠️ needs refactor
        ├── DashboardPage.js
        ├── ProjectPage.js
        ├── PersonalSourcesPage.js
        ├── DepartmentSourcesPage.js
        ├── AdminUsersPage.js
        ├── AdminAuditLogsPage.js
        ├── AdminGptConfigPage.js
        ├── AdminGlobalSourcesPage.js
        └── ProductCatalogPage.js
```

### MongoDB Collections
```
users            # Пользователи (roles, ai_profile, departments)
projects         # Проекты (project_memory)
chats            # Чаты (quick + project, sourceMode)
messages         # Сообщения (citations, web_sources, fetchedUrls, clarifying_*)
sources          # Все источники (personal/project/department/global)
source_chunks    # Векторные chunks (embedding via Voyage AI)
departments      # Отделы
gpt_config       # Настройки AI (developer prompt, model)
audit_logs       # Аудит логи (с пагинацией)
semantic_cache   # Кэш ответов (cosine similarity)
token_usage      # Статистика использования токенов
user_prompts     # Пользовательские промпты
source_usage     # Статистика использования источников
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
| Brave Web Search | ✅ | При ключевых словах "найди в интернете" |
| URL Content Fetch | ✅ | Авто-чтение HTML/PDF из URL в сообщении |
| Edit Message | ✅ | Редактирование + регенерация AI ответа |
| Clarifying Questions | ✅ | AI задаёт уточняющие вопросы с кнопками |
| Save Context | ✅ | Суммаризация чата → AI Profile |
| Project Memory | ✅ | Ключевые факты → фон для AI |
| Image Generation | ✅ | Внутри project chat |
| Competitor Tracker | ✅ | Отслеживание конкурентов |
| Product Catalog | ✅ | Фазы 1-2: CRUD, CSV import, relations |
| Tech News | ✅ | Hacker News |
| Admin Audit Logs | ✅ | Фильтрация + пагинация |
| i18n (RU/EN) | 🔄 | ~80% переведено |
| Server.py | ✅ | Рефакторинг завершён (177 строк) |

---

## 5. Приоритизированный бэклог

### 🔴 P0 — Критично (технический долг)

#### Рефакторинг ChatPage.js
- **Что:** `ChatPage.js` = ~1441 строк, god-компонент
- **Как:** Вынести в отдельные хуки и компоненты:
  - `useMessages.js` — логика отправки/редактирования сообщений
  - `useSources.js` — управление источниками
  - `SourcePanel.js` — панель источников
  - `MessageBubble.js` — рендер одного сообщения
  - `ChatInput.js` — поле ввода
- **Почему:** Сложность поддержки, частые регрессии

---

### 🟡 P1 — Высокий приоритет

#### Product Catalog AI Integration (Фаза 3)
- **Что:** Поиск продуктов через AI-чат
  - Пользователь пишет: "Найди маршрутизаторы Cisco" → AI ищет в каталоге
  - AI предлагает похожие/совместимые продукты на основе relations
  - Тендерный анализ: загрузить список → AI сопоставляет с каталогом
- **Эндпоинты:** `POST /api/product-catalog/chat-search`, `POST /api/product-catalog/tender-analyze`
- **Где:** `routes/product_catalog.py` + `routes/messages.py` (интеграция в RAG)

#### Product Catalog Weekly Sync
- **Что:** APScheduler job для автообновления каталога
- **Как:** Каждое воскресенье в 3:00 — повторный импорт из источника
- **Где:** `server.py` scheduler + `routes/product_catalog.py`

#### Полная интернационализация (i18n)
- **Что:** Оставшиеся ~20% хардкод-строк в UI
- **Файлы:** `ChatPage.js`, `ProjectPage.js`, модальные окна, toast-уведомления
- **Где:** `i18n/translations.js` + замена строк в компонентах

---

### 🔵 P2 — Средний приоритет

#### API Rate Limiting
- **Что:** Ограничение запросов per-user per-minute
- **Как:** FastAPI middleware + Redis или in-memory counter
- **Зачем:** Защита от злоупотреблений

#### Шаблоны вопросов (Question Templates)
- **Что:** Сохранённые шаблоны вопросов для быстрого ввода
- **UI:** Кнопки под полем ввода чата
- **DB:** `question_templates` collection

#### Dashboard использования / затрат
- **Что:** Для Admin — сколько токенов потратил каждый пользователь, топ источников
- **API:** `GET /api/admin/usage-stats`
- **UI:** Новая страница `/admin/usage`

#### Глобальный поиск
- **Что:** Поиск по всем источникам, чатам, проектам из одного места
- **API:** `GET /api/search?q=...`
- **UI:** Строка поиска в хедере

#### Экспорт чата
- **Что:** Скачать историю чата в PDF или Markdown
- **API:** `GET /api/chats/{id}/export?format=pdf|md`

#### Индикатор прогресса загрузки файла
- **Что:** Progress bar при загрузке больших файлов
- **UI:** Заменить spinner на реальный прогресс в `ChatPage.js` и `PersonalSourcesPage.js`

---

### ⚪ P3 — Низкий приоритет / Будущее

#### Mobile responsive
- Адаптивный дизайн для мобильных устройств
- Сейчас приложение не оптимизировано для экранов < 768px

#### SSO / SAML
- Корпоративная аутентификация (SAML 2.0, OIDC)
- Актуально при масштабировании на крупные компании

#### Real-time уведомления
- WebSocket для уведомлений: "Источник одобрен", "Новое сообщение в чате"
- `FastAPI WebSocket` + React context

#### @mentions в чатах
- Упоминание коллег в project chat
- Уведомления при упоминании

#### Комментарии к источникам
- Обсуждение документов прямо в карточке источника

#### Мульти-модельный UI
- Дать пользователю выбирать модель AI: Claude / GPT-4o / Gemini
- Уже есть `gptModel` поле в users collection

#### Error Tracking (Sentry)
- Интеграция Sentry для production-мониторинга ошибок

---

## 6. Ключевые API эндпоинты

```
# Auth
POST   /api/auth/login
GET    /api/auth/me

# Chats & Messages
POST   /api/quick-chats
POST   /api/projects/{id}/chats
POST   /api/chats/{id}/messages              # RAG + Brave + URL fetch + Claude
PUT    /api/chats/{id}/messages/{msg_id}/edit
POST   /api/chats/{id}/save-context
POST   /api/chats/{id}/extract-memory-points

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

## 7. Схема ключевых полей

### Message (в БД)
```python
{
  "id": str,
  "chatId": str,
  "role": "user" | "assistant",
  "content": str,
  "citations": [{sourceId, sourceName, sourceType, chunks}],
  "usedSources": [{sourceId, sourceName, sourceType}],
  "web_sources": [{"title": str, "url": str}],       # Brave Search
  "fetchedUrls": [str],                                # URL Content Fetch
  "clarifying_question": str,
  "clarifying_options": [str],
  "fromCache": bool,
  "autoIngestedUrls": [str],
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
    "custom_instruction": str    # хранит Save Context суммаризации
  },
  "gptModel": str                # per-user AI model override
}
```

---

## 8. Известные технические долги

| Файл | Проблема | Приоритет |
|------|----------|-----------|
| `ChatPage.js` | ~1441 строк, god-component | P0 |
| `messages.py` | ~1061 строк, смешана бизнес-логика | P1 |
| `enterprise_sources.py` | ~802 строк | P2 |
| i18n | ~20% строк не переведено | P1 |
| `useEffect` warnings | Отсутствующие зависимости в dep-array | P3 |

---

## 9. Changelog

### Февраль 2026 — Текущая сессия
- ✅ **URL Content Fetching** — авто-чтение HTML/PDF из URL в чате (BeautifulSoup + pypdf)
- ✅ **URL Indicator UI** — бейдж "🔗 URL прочитан: domain.com" под ответом AI
- ✅ **ensure_gpt_config fix** — конфиг не перезаписывается при рестарте (`find_one({})` → `return`)
- ✅ **Clarifying Questions light mode fix** — цвета amber адаптированы для light/dark режимов
- ✅ **SmartQuestions hidden** — секция "Получить идеи вопросов" скрыта в чате
- ✅ **PDF as URL source** — `sources.py` теперь принимает `application/pdf` при добавлении URL-источника (pypdf extraction)
- ✅ **Personal Sources — publishedTo badge** — бейджи "📁 Project" / "🏢 Dept" на карточках личных источников
- ✅ **Chat sources — project badge** — бейдж имени проекта на каждом источнике в панели чата
- ✅ **Project Memory fix** — переключён на `anthropic.Anthropic` + добавлен `return {"points": []}` в except
- ✅ **Image Generator — reference photo** — загрузка фото в таб Generate, кнопка активна без текста если есть фото
- ✅ **ImageGenerator bug fix** — восстановлен `editFile` state (setEditFile not defined)
- ✅ **Tab title** — "Planet GPT" → "PLANET KNOWLEDGE", favicon обновлён (fa-globe стиль)
- ✅ **Auth fix** — `fetchUser()` вызывает `logout()` только при 401, не при сетевых ошибках
- ✅ **JWT expiry** — увеличен с 24ч до 7 дней

### Предыдущие сессии (Март 2026)
- ✅ **Brave Web Search** — веб-поиск через Brave API
- ✅ **Edit Message** — редактирование сообщений + регенерация AI
- ✅ **Clarifying Questions** — AI задаёт уточняющие вопросы
- ✅ **Save Context** — суммаризация диалога → AI Profile
- ✅ **Project Memory** — ключевые факты как фон для AI
- ✅ **Product Catalog Phase 1-2** — CRUD, CSV import, relations, tender matching
- ✅ **Server.py refactoring** — 4791 → 177 строк
- ✅ **Source Insights** — AI анализ источников + вопросы
- ✅ **Semantic RAG** — Voyage AI embeddings, cosine similarity
- ✅ **Competitor Tracker** — отслеживание конкурентов
- ✅ **Audit Logs pagination** — limit/offset
- ✅ **File upload fix** — 400 Bad Request устранён
- ✅ **Favicon** — добавлен

---

## 10. Тестовые аккаунты

| Роль | Email | Пароль |
|------|-------|--------|
| Admin | admin@ai.planetworkspace.com | Admin@123456 |

---

*Planet Knowledge PRD v2.1 — Confidential*
