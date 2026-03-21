# Planet Knowledge - Complete Product Requirements Document

## 1. Executive Summary

### 1.1 Название продукта
**Planet Knowledge** - корпоративная платформа управления знаниями с AI

### 1.2 Миссия
Объединить все корпоративные знания в единую систему с интеллектуальным поиском и анализом на базе AI.

### 1.3 Ключевые ценности
| Для бизнеса | Для пользователей |
|-------------|-------------------|
| Централизация знаний | Быстрый поиск информации |
| Контроль доступа | Естественные вопросы к AI |
| Аудит и compliance | Работа с документами |
| Снижение затрат | Анализ данных без Excel навыков |

---

## 2. Целевая аудитория

### 2.1 Пользовательские роли
```
┌─────────────────────────────────────────────────────────────┐
│                        ADMIN                                 │
│    • Управление пользователями                              │
│    • Настройка GPT                                          │
│    • Глобальные источники                                   │
│    • Аудит логи                                             │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│    MANAGER    │   │    EDITOR     │   │    VIEWER     │
│  • Одобрение  │   │  • Создание   │   │  • Просмотр   │
│    источников │   │    контента   │   │    контента   │
│  • Управление │   │  • Редактир.  │   │  • Чат с AI   │
│    отделом    │   │    источников │   │               │
└───────────────┘   └───────────────┘   └───────────────┘
```

### 2.2 User Personas

#### Persona 1: IT Administrator (Админ)
- **Имя:** Александр, 35 лет
- **Роль:** Системный администратор
- **Задачи:** Управление пользователями, настройка AI, мониторинг
- **Боль:** Сложность контроля доступа к корпоративным данным
- **Решение:** Централизованная админка с полным контролем

#### Persona 2: Department Manager (Менеджер)
- **Имя:** Мария, 42 года
- **Роль:** Руководитель отдела закупок
- **Задачи:** Одобрение документов, управление базой знаний отдела
- **Боль:** Разрозненные документы, долгий поиск информации
- **Решение:** Иерархическая база знаний с workflow одобрения

#### Persona 3: Business Analyst (Пользователь)
- **Имя:** Дмитрий, 28 лет
- **Роль:** Бизнес-аналитик
- **Задачи:** Анализ данных, поиск информации, создание отчётов
- **Боль:** Ручной анализ Excel файлов, сложные формулы
- **Решение:** AI-анализатор с естественным языком

---

## 3. Функциональные требования

### 3.1 Модуль аутентификации

#### 3.1.1 Регистрация/Вход
```
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

#### 3.1.2 JWT токены
- Access token: 24 часа
- Хранение: localStorage
- Формат: Bearer token

#### 3.1.3 Роли и права
| Действие | Admin | Manager | Editor | Viewer |
|----------|-------|---------|--------|--------|
| Управление пользователями | ✅ | ❌ | ❌ | ❌ |
| Глобальные источники | ✅ | ❌ | ❌ | ❌ |
| Настройка GPT | ✅ | ❌ | ❌ | ❌ |
| Аудит логи | ✅ | ❌ | ❌ | ❌ |
| Одобрение источников | ✅ | ✅ | ❌ | ❌ |
| Удаление источников отдела | ✅ | ✅ | ❌ | ❌ |
| Создание источников | ✅ | ✅ | ✅ | ❌ |
| Чат с AI | ✅ | ✅ | ✅ | ✅ |

---

### 3.2 Модуль проектов

#### 3.2.1 Структура проекта
```python
Project = {
    "id": "uuid",
    "name": "Название проекта",
    "description": "Описание",
    "ownerId": "user_uuid",
    "members": [
        {"userId": "...", "role": "editor|viewer"}
    ],
    "createdAt": "ISO datetime",
    "updatedAt": "ISO datetime"
}
```

#### 3.2.2 API Endpoints
```
POST   /api/projects              # Создать проект
GET    /api/projects              # Список проектов
GET    /api/projects/{id}         # Детали проекта
PUT    /api/projects/{id}         # Обновить проект
DELETE /api/projects/{id}         # Удалить проект
POST   /api/projects/{id}/members # Добавить участника
DELETE /api/projects/{id}/members/{userId}
```

#### 3.2.3 Права доступа к проекту
| Роль в проекте | Просмотр | Редактирование | Удаление | Управление участниками |
|----------------|----------|----------------|----------|------------------------|
| Owner | ✅ | ✅ | ✅ | ✅ |
| Editor | ✅ | ✅ | ❌ | ❌ |
| Viewer | ✅ | ❌ | ❌ | ❌ |

---

### 3.3 Модуль чатов

#### 3.3.1 Типы чатов
| Тип | Описание | Источники |
|-----|----------|-----------|
| Quick Chat | Быстрый чат без проекта | Нет |
| Project Chat | Чат внутри проекта | Project + Global sources |

#### 3.3.2 Структура чата
```python
Chat = {
    "id": "uuid",
    "projectId": "uuid|null",  # null для quick chat
    "name": "Название чата",
    "ownerId": "user_uuid",
    "activeSourceIds": ["source_id_1", "source_id_2"],
    "messages": [
        {
            "id": "uuid",
            "role": "user|assistant",
            "content": "текст сообщения",
            "timestamp": "ISO datetime",
            "citations": [{"source": "...", "chunk": 1}]
        }
    ],
    "createdAt": "ISO datetime"
}
```

#### 3.3.3 API Endpoints
```
POST   /api/quick-chats                    # Создать quick chat
GET    /api/quick-chats                    # Список quick chats
POST   /api/projects/{id}/chats            # Создать project chat
GET    /api/projects/{id}/chats            # Список project chats
GET    /api/chats/{id}                     # Получить чат
DELETE /api/chats/{id}                     # Удалить чат
POST   /api/chats/{id}/messages            # Отправить сообщение
PUT    /api/chats/{id}/active-sources      # Установить активные источники
```

#### 3.3.4 RAG Pipeline
```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│    User      │───▶│   Embed      │───▶│   Search     │
│   Question   │    │   Question   │    │   Vectors    │
└──────────────┘    └──────────────┘    └──────────────┘
                                              │
┌──────────────┐    ┌──────────────┐          ▼
│   Response   │◀───│     GPT      │◀───┌──────────────┐
│   to User    │    │   Generate   │    │   Context    │
└──────────────┘    └──────────────┘    │   Chunks     │
                                        └──────────────┘
```

---

### 3.4 Модуль источников (Sources)

#### 3.4.1 Иерархия источников
```
┌─────────────────────────────────────────────────────────────┐
│                     GLOBAL SOURCES                           │
│            (Доступны всем пользователям)                    │
│                    Управляет: Admin                         │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  DEPARTMENT   │   │  DEPARTMENT   │   │  DEPARTMENT   │
│   SOURCES     │   │   SOURCES     │   │   SOURCES     │
│ (Engineering) │   │    (Sales)    │   │   (Finance)   │
│ Manager: John │   │ Manager: Mary │   │ Manager: Alex │
└───────────────┘   └───────────────┘   └───────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                      PROJECT SOURCES                           │
│                  (Специфичны для проекта)                     │
│                   Управляет: Project Owner                    │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                      PERSONAL SOURCES                          │
│                    (Личные файлы юзера)                       │
│                   Управляет: User                             │
└───────────────────────────────────────────────────────────────┘
```

#### 3.4.2 Типы источников
| Тип | Расширения | Обработка |
|-----|------------|-----------|
| Document | .pdf, .docx, .txt | Text extraction |
| Spreadsheet | .xlsx, .csv | Table parsing |
| Presentation | .pptx | Slide extraction |
| Image | .png, .jpg | OCR (Tesseract) |
| URL | http(s):// | Web scraping |

#### 3.4.3 Workflow статусы
```
┌─────────┐    ┌──────────┐    ┌─────────┐
│  DRAFT  │───▶│ PENDING  │───▶│ ACTIVE  │
│         │    │ APPROVAL │    │         │
└─────────┘    └──────────┘    └─────────┘
     │              │               │
     │              ▼               │
     │         ┌──────────┐        │
     └────────▶│ REJECTED │◀───────┘
               └──────────┘
```

#### 3.4.4 Chunking стратегия
```python
# Для текстовых документов
chunk_size = 1000  # символов
chunk_overlap = 200  # символов

# Для таблиц (Excel/CSV)
# Каждая строка = отдельный chunk с заголовками
"Column1: value1, Column2: value2, Column3: value3"
```

#### 3.4.5 API Endpoints
```
# Personal Sources
POST   /api/sources/upload          # Загрузить файл
POST   /api/sources/url             # Добавить URL
GET    /api/sources                 # Список личных источников
DELETE /api/sources/{id}            # Удалить источник

# Project Sources
POST   /api/projects/{id}/sources/upload
GET    /api/projects/{id}/sources

# Department Sources
GET    /api/departments/{id}/sources
POST   /api/departments/{id}/sources/upload
PUT    /api/sources/{id}/approve    # Manager only
PUT    /api/sources/{id}/reject     # Manager only

# Global Sources (Admin only)
GET    /api/admin/global-sources
POST   /api/admin/global-sources/upload
DELETE /api/admin/global-sources/{id}
```

---

### 3.5 Модуль отделов (Departments)

#### 3.5.1 Структура отдела
```python
Department = {
    "id": "uuid",
    "name": "Engineering",
    "description": "Инженерный отдел",
    "managerId": "user_uuid",
    "memberIds": ["user_1", "user_2"],
    "createdAt": "ISO datetime"
}
```

#### 3.5.2 API Endpoints
```
GET    /api/departments              # Список отделов (Admin)
POST   /api/departments              # Создать отдел (Admin)
PUT    /api/departments/{id}         # Обновить отдел (Admin)
DELETE /api/departments/{id}         # Удалить отдел (Admin)
GET    /api/departments/{id}/members # Участники отдела
POST   /api/departments/{id}/members # Добавить участника
```

---

### 3.6 Модуль администрирования

#### 3.6.1 Управление пользователями
```
GET    /api/admin/users              # Список пользователей
POST   /api/admin/users              # Создать пользователя
PUT    /api/admin/users/{id}         # Обновить пользователя
DELETE /api/admin/users/{id}         # Удалить пользователя
PUT    /api/admin/users/{id}/role    # Изменить роль
```

#### 3.6.2 Настройка GPT
```python
GPTConfig = {
    "id": "1",
    "model": "gpt-4.1-mini",
    "developerPrompt": "You are a helpful assistant...",
    "temperature": 0.7,
    "maxTokens": 4096,
    "updatedAt": "ISO datetime"
}
```

```
GET    /api/admin/gpt-config         # Получить настройки
PUT    /api/admin/gpt-config         # Обновить настройки
```

#### 3.6.3 Аудит логи
```python
AuditLog = {
    "id": "uuid",
    "userId": "user_uuid",
    "userEmail": "user@example.com",
    "action": "source_upload|source_delete|login|...",
    "resourceType": "source|user|project|...",
    "resourceId": "resource_uuid",
    "details": {"fileName": "report.pdf", ...},
    "timestamp": "ISO datetime"
}
```

```
GET /api/admin/audit-logs?action=...&userId=...&from=...&to=...
```

---

### 3.7 Excel/CSV Analyzer

#### 3.7.1 Возможности
| Функция | Описание |
|---------|----------|
| Загрузка файлов | CSV, XLSX до 10 MB |
| Вопросы на естественном языке | "Покажи все продукты где..." |
| Экспорт результатов | PDF, Excel |
| Debug информация | Количество строк в контексте |

#### 3.7.2 API Endpoints
```
POST   /api/analyzer/upload                    # Загрузить файл
POST   /api/analyzer/ask                       # Задать вопрос
GET    /api/analyzer/session/{id}              # Получить сессию
DELETE /api/analyzer/session/{id}              # Удалить сессию
GET    /api/analyzer/session/{id}/export/excel # Экспорт Excel
GET    /api/analyzer/session/{id}/export/pdf   # Экспорт PDF
```

#### 3.7.3 Ограничения
- Max файл: 10 MB
- Max контекст: 100,000 символов (~500 строк)
- In-memory хранение сессий

---

### 3.8 Semantic Cache

#### 3.8.1 Принцип работы
```
┌──────────────┐    ┌──────────────┐
│   Question   │───▶│   Embed      │
│              │    │   Question   │
└──────────────┘    └──────────────┘
                          │
                          ▼
                    ┌──────────────┐
                    │   Search     │
                    │   Cache DB   │
                    └──────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
    similarity > 0.95           similarity < 0.95
            │                           │
            ▼                           ▼
    ┌──────────────┐           ┌──────────────┐
    │ Return       │           │ Call GPT     │
    │ Cached       │           │ Save to      │
    │ Answer       │           │ Cache        │
    └──────────────┘           └──────────────┘
```

#### 3.8.2 Конфигурация
```python
CacheConfig = {
    "enabled": True,
    "similarityThreshold": 0.95,
    "ttlDays": 7,
    "maxEntries": 10000
}
```

---

### 3.9 Tech News

#### 3.9.1 Функционал
- Отображение топ новостей с Hacker News
- Автообновление каждые 30 минут
- Ссылки на оригинальные статьи

#### 3.9.2 API
```
GET /api/news?limit=30
```

---

### 3.10 Мультиязычность (i18n)

#### 3.10.1 Поддерживаемые языки
- 🇷🇺 Русский (ru)
- 🇬🇧 English (en)

#### 3.10.2 Реализация
```javascript
// Frontend: LanguageContext
const { language, setLanguage, t } = useLanguage();

// Использование
<Button>{t('nav.dashboard')}</Button>
```

#### 3.10.3 Статус перевода
| Раздел | RU | EN |
|--------|----|----|
| Login | ✅ | ✅ |
| Dashboard | ✅ | ✅ |
| Sidebar | ✅ | ✅ |
| Admin pages | ✅ | ✅ |
| News | ✅ | ✅ |
| Analyzer | ✅ | ✅ |
| Modals/Toasts | 🔄 | 🔄 |

---

## 4. Техническая архитектура

### 4.1 Стек технологий

#### Backend
```
Framework:    FastAPI (Python 3.11+)
Database:     MongoDB (motor async driver)
AI:           OpenAI GPT-4.1-mini, text-embedding-3-small
OCR:          Tesseract
File parsing: openpyxl, python-pptx, PyPDF2
Auth:         JWT (PyJWT)
```

#### Frontend
```
Framework:    React 18
Styling:      Tailwind CSS
Components:   Shadcn/UI
Icons:        Lucide React
HTTP:         Axios
Routing:      React Router v6
State:        React Context
```

### 4.2 Структура проекта
```
/app/
├── backend/
│   ├── models/
│   │   └── enterprise.py          # Pydantic models
│   ├── routes/
│   │   ├── analyzer.py            # Excel analyzer
│   │   ├── departments.py         # Departments CRUD
│   │   ├── enterprise_sources.py  # Sources management
│   │   └── news.py                # Tech news API
│   ├── services/
│   │   └── enterprise.py          # Business logic
│   ├── server.py                  # Main FastAPI app (~3600 lines)
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/                # Shadcn components
│   │   │   └── DashboardLayout.js
│   │   ├── contexts/
│   │   │   ├── AuthContext.js
│   │   │   └── LanguageContext.js
│   │   ├── i18n/
│   │   │   └── translations.js
│   │   ├── pages/
│   │   │   ├── LoginPage.js
│   │   │   ├── DashboardPage.js
│   │   │   ├── ProjectPage.js
│   │   │   ├── ChatPage.js
│   │   │   ├── NewsPage.js
│   │   │   ├── ExcelAnalyzerPage.js
│   │   │   ├── MyGptPromptPage.js
│   │   │   ├── PersonalSourcesPage.js
│   │   │   ├── DepartmentSourcesPage.js
│   │   │   ├── AdminUsersPage.js
│   │   │   ├── AdminDepartmentsPage.js
│   │   │   ├── AdminGptConfigPage.js
│   │   │   ├── AdminGlobalSourcesPage.js
│   │   │   └── AdminAuditLogsPage.js
│   │   └── App.js
│   ├── package.json
│   └── .env
│
└── memory/
    ├── PRD.md
    └── EXCEL_ANALYZER_PRD.md
```

### 4.3 База данных (MongoDB)

#### Collections
```
users                 # Пользователи
projects              # Проекты
chats                 # Чаты (quick + project)
sources               # Все источники
source_chunks         # Векторные chunks
departments           # Отделы
gpt_config            # Настройки GPT
audit_logs            # Аудит логи
semantic_cache        # Кэш ответов
token_usage           # Использование токенов
user_prompts          # Пользовательские промпты
```

#### Индексы
```javascript
// sources
db.sources.createIndex({ "projectId": 1 })
db.sources.createIndex({ "departmentId": 1 })
db.sources.createIndex({ "userId": 1 })
db.sources.createIndex({ "scope": 1, "status": 1 })

// source_chunks
db.source_chunks.createIndex({ "sourceId": 1 })
db.source_chunks.createIndex({ "embedding": "2dsphere" })  // Vector search

// audit_logs
db.audit_logs.createIndex({ "timestamp": -1 })
db.audit_logs.createIndex({ "userId": 1, "action": 1 })
```

### 4.4 API Authentication Flow
```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  Login  │────▶│  Verify │────▶│ Generate│────▶│  Return │
│ Request │     │  Creds  │     │   JWT   │     │  Token  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘

┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│   API   │────▶│ Extract │────▶│  Verify │────▶│ Process │
│ Request │     │  Token  │     │   JWT   │     │ Request │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
```

---

## 5. Нефункциональные требования

### 5.1 Производительность
| Метрика | Требование |
|---------|------------|
| Время ответа API | < 200ms (без AI) |
| Время ответа GPT | < 10 сек |
| Загрузка страницы | < 2 сек |
| Concurrent users | 100+ |

### 5.2 Безопасность
- [x] JWT аутентификация
- [x] Role-based access control
- [x] Audit logging
- [x] Input validation (Pydantic)
- [ ] Rate limiting
- [ ] HTTPS only (production)

### 5.3 Масштабируемость
- MongoDB sharding ready
- Stateless backend
- File storage abstraction

### 5.4 Мониторинг
- [ ] Error tracking (Sentry)
- [ ] Performance metrics (Prometheus)
- [ ] Log aggregation (ELK)

---

## 6. Текущий статус

### 6.1 Реализованные функции ✅
| Модуль | Статус | Примечания |
|--------|--------|------------|
| Аутентификация | ✅ | JWT, роли |
| Проекты | ✅ | CRUD, участники |
| Чаты | ✅ | Quick + Project |
| RAG Pipeline | ✅ | Embeddings + GPT |
| Personal Sources | ✅ | Upload, URL |
| Department Sources | ✅ | Workflow approval |
| Global Sources | ✅ | Admin only |
| Admin Panel | ✅ | Users, GPT config |
| Audit Logs | ✅ | Фильтрация |
| Excel Analyzer | ✅ | GPT-4.1-mini |
| Export PDF/Excel | ✅ | Analyzer results |
| Tech News | ✅ | Hacker News |
| i18n (RU/EN) | 🔄 | ~80% готово |
| Semantic Cache | ✅ | Базовая версия |

### 6.2 В разработке 🔄
| Функция | Приоритет | Статус |
|---------|-----------|--------|
| Column selector (Analyzer) | P0 | Planned |
| Two-stage analysis | P0 | Planned |
| Complete i18n | P1 | In progress |
| Pending approvals page | P1 | Planned |
| Cache settings UI | P1 | Planned |

### 6.3 Backlog 📋
| Функция | Приоритет |
|---------|-----------|
| Question templates | P2 |
| Source preview before query | P2 |
| Usage/cost dashboard | P2 |
| News bookmarks | P2 |
| Global search | P2 |
| Chat export (PDF/MD) | P2 |
| User token limits | P3 |
| Notifications | P3 |
| Mobile responsive | P3 |

---

## 7. Известные проблемы

### 7.1 Технические
| Проблема | Severity | Workaround |
|----------|----------|------------|
| Excel Analyzer: только ~500 строк | High | Уменьшить колонки |
| Analyzer sessions in-memory | Medium | Перезагрузка теряет данные |
| useEffect dependency warnings | Low | Не влияет на работу |

### 7.2 UX
| Проблема | Severity |
|----------|----------|
| Нет индикатора обработки больших файлов | Medium |
| Нет выбора колонок в Analyzer | High |
| ~20% UI не переведено | Medium |

---

## 8. Roadmap

### Q1 2024 - Оптимизация Analyzer
- [ ] Two-stage analysis (Python filter → GPT format)
- [ ] Column selector UI
- [ ] MongoDB persistence for sessions
- [ ] Progress indicators

### Q2 2024 - Enterprise Features
- [ ] SSO integration (SAML/OIDC)
- [ ] Advanced audit reporting
- [ ] API rate limiting
- [ ] Usage dashboards

### Q3 2024 - Collaboration
- [ ] Real-time chat notifications
- [ ] @mentions in chats
- [ ] Shared analysis sessions
- [ ] Comments on sources

### Q4 2024 - Advanced AI
- [ ] Multi-model support (GPT-4, Claude, Gemini)
- [ ] Custom fine-tuned models
- [ ] AI-powered source suggestions
- [ ] Automated categorization

---

## 9. Тестовые аккаунты

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@admin.com | admin123 |
| Manager | manager@test.com | testpassword |

---

## 10. API Reference

### Base URL
```
Production: https://url-fetch-dev.preview.emergentagent.com/api
```

### Authentication Header
```
Authorization: Bearer <jwt_token>
```

### Common Responses
```json
// Success
{ "id": "...", "name": "...", ... }

// Error
{ "detail": "Error message" }
```

### Full API List
```
# Auth
POST   /api/auth/register
POST   /api/auth/login
GET    /api/auth/me

# Projects
GET    /api/projects
POST   /api/projects
GET    /api/projects/{id}
PUT    /api/projects/{id}
DELETE /api/projects/{id}

# Chats
POST   /api/quick-chats
GET    /api/quick-chats
POST   /api/projects/{id}/chats
GET    /api/projects/{id}/chats
GET    /api/chats/{id}
DELETE /api/chats/{id}
POST   /api/chats/{id}/messages
PUT    /api/chats/{id}/active-sources

# Sources
POST   /api/sources/upload
POST   /api/sources/url
GET    /api/sources
DELETE /api/sources/{id}

# Departments
GET    /api/departments
POST   /api/departments
PUT    /api/departments/{id}
DELETE /api/departments/{id}
GET    /api/departments/{id}/sources
POST   /api/departments/{id}/sources/upload

# Admin
GET    /api/admin/users
POST   /api/admin/users
PUT    /api/admin/users/{id}
DELETE /api/admin/users/{id}
GET    /api/admin/gpt-config
PUT    /api/admin/gpt-config
GET    /api/admin/global-sources
POST   /api/admin/global-sources/upload
DELETE /api/admin/global-sources/{id}
GET    /api/admin/audit-logs

# Analyzer
POST   /api/analyzer/upload
POST   /api/analyzer/ask
GET    /api/analyzer/session/{id}
DELETE /api/analyzer/session/{id}
GET    /api/analyzer/session/{id}/export/excel
GET    /api/analyzer/session/{id}/export/pdf

# News
GET    /api/news

# User Settings
GET    /api/user/prompt
PUT    /api/user/prompt
```

---

## 11. Changelog

### 2024-03-02
- Excel/CSV Analyzer переключен на GPT-4.1-mini
- Добавлен debug info в ответы Analyzer
- Основной чат работает на GPT-4.1-mini

### 2024-03-01
- Добавлена мультиязычность (RU/EN)
- Реализована страница Tech News
- Улучшен RAG для табличных данных
- Конвертирован My GPT Prompt в отдельную страницу

### 2024-02-28
- Реализован workflow одобрения источников
- Добавлены права менеджера (удаление, одобрение)
- Исправлен баг с навигацией "Departments"

### 2024-03-04 (Refactoring Sprint)
- **Backend Modularization Started:**
  - Created `/app/backend/db/connection.py` - Database connection module
  - Created `/app/backend/models/schemas.py` - Pydantic models for requests/responses
  - Created `/app/backend/middleware/auth.py` - Authentication middleware
  - Created `/app/backend/services/cache.py` - Semantic cache service
  - Created `/app/backend/services/rag.py` - RAG pipeline service
  - Created `/app/backend/services/file_processor.py` - File extraction utilities
  - Created `/app/backend/routes/insights.py` - Source Insights & Smart Questions
  - Created new route modules: `auth.py`, `projects.py`, `chats.py`, `messages.py`, `sources.py`, `admin.py`, `images.py`, `global_sources.py`, `user_settings.py`
  - Created `/app/backend/server_modular.py` - Compact modular server (424 lines) as reference
- **Frontend Componentization Started:**
  - Created `/app/frontend/src/components/chat/` directory
  - Created reusable components: `ChatHeader.js`, `Message.js`, `MessageList.js`, `ChatInput.js`
- **API Pagination Added:**
  - Added `paginate_query()` helper function
  - Paginated endpoints: `/projects`, `/quick-chats`, `/chats`, `/messages`, `/sources`, `/admin/users`
  - Response format: `{ items: [], total: N, page: N, pageSize: N, totalPages: N }`
  - Frontend updated to handle new paginated response format
- **Bug Fixes:**
  - Fixed `analyzer.py` session management (was using undefined dictionary, now uses MongoDB)
  - **Fixed "Publish failed" bug** - chunks for "Save to Knowledge" sources use `text` field instead of `content`. Updated all chunk processing code to handle both field names.
  - **Fixed "Failed to load chat"** - SourceResponse model now supports `kind: "knowledge"` type
  - Removed `emergentintegrations` from requirements.txt (was causing deployment failures)
- **UI Improvements:**
  - Made all action buttons always visible (removed hover requirement)
- **New Features:**
  - **Source Insights**: AI analyzes sources, generates summary + 5 suggested questions. Available on all source pages.
  - **Smart Question Suggestions**: "💡 Get question ideas" button in chat generates relevant questions based on active sources.
  - AI responses now match the language of the source document (Armenian, Russian, English, etc.)
- **Tests:** All 32 core API tests passed (100% success rate)

---

## 12. Technical Debt & Refactoring Status

### Server.py Refactoring (P0 - In Progress)
| Module | Status | Lines | Description |
|--------|--------|-------|-------------|
| auth.py | Created | ~60 | Auth routes (login, me) |
| projects.py | Created | ~250 | Project CRUD + sharing |
| chats.py | Created | ~200 | Chat CRUD + visibility |
| messages.py | Created | ~400 | Messages + RAG pipeline |
| sources.py | Created | ~350 | Source upload + management |
| admin.py | Created | ~300 | Admin functions |
| images.py | Created | ~150 | Image generation |
| global_sources.py | Created | ~200 | Global sources |
| user_settings.py | Created | ~80 | User prompts |
| **server.py** | **NOT YET REPLACED** | 3700+ | Monolith still in use |

### ChatPage.js Refactoring (P0 - In Progress)
| Component | Status | Lines | Description |
|-----------|--------|-------|-------------|
| ChatHeader.js | Created | ~140 | Header with controls |
| Message.js | Created | ~250 | Single message display |
| MessageList.js | Created | ~90 | Messages container |
| ChatInput.js | Created | ~70 | Input area |
| SourcePanel.js | **TODO** | - | Sources panel |
| **ChatPage.js** | **NOT YET UPDATED** | 1468 | Monolith still in use |

### Next Steps for Refactoring
1. Replace server.py with modular imports (careful migration)
2. Update ChatPage.js to use new components
3. Create SourcePanel.js component
4. Remove duplicate code
5. Update tests

---

## 13. Session Updates (2026-03-07)

### Completed Tasks
1. **✅ Excel/CSV Analyzer Removal (P0)** - Полностью удалён
   - Removed `/api/analyzer/*` endpoints from server.py
   - Removed `ExcelAnalyzerPage.js` import from App.js
   - Removed `/analyzer` route from App.js
   - Removed navigation link from DashboardLayout.js
   - Removed `FileSpreadsheet` icon import
   - Removed translations from `translations.js`
   - Deleted test files (`test_analyzer.py`, analyzer tests in `test_core_apis.py`)
   - Deleted backup server files (`server_new.py`, `server_modular.py`, `server_backup.py`, `server_full_backup.py`)
   - **All tests passed:** 100% backend, 100% frontend

2. **⚠️ Server.py Refactoring (P0)** - Attempted but reverted
   - Created modular server.py that imports all routers
   - **Issue:** `setup_department_routes()` and `setup_enterprise_source_routes()` require complex dependencies (db, get_current_user, is_admin, audit_service, version_service, etc.)
   - **Decision:** Reverted to monolith with analyzer removed; full refactor requires rewriting route modules to use dependency injection differently
   - Server.py still ~4000 lines but functional without analyzer

### Test Results (iteration_11.json)
- Backend: 10/10 tests passed (100%)
- Frontend: 5/5 UI checks passed (100%)
- All analyzer endpoints return 404 ✅
- Navigation no longer shows Excel Analyzer ✅
- Core features working (auth, projects, chats) ✅

### Remaining P0 Tasks
1. **Complete server.py refactoring** - Requires updating route modules to not use setup functions with dependencies
2. **Complete ChatPage.js refactoring** - Integrate existing components

### Files Cleaned Up
- `/app/backend/server_new.py` - Deleted
- `/app/backend/server_modular.py` - Deleted
- `/app/backend/server_backup.py` - Deleted
- `/app/backend/server_full_backup.py` - Deleted
- `/app/backend/tests/test_analyzer.py` - Deleted
- `/app/backend/routes/analyzer.py` - Already did not exist

---

## 14. Session Updates (2026-03-08)

### Critical Bug Fixed
1. **✅ ReferenceError: TrendingUp is not defined (P0 BLOCKER)** - ИСПРАВЛЕНО
   - **Проблема:** Приложение крашилось после логина из-за отсутствующего импорта `TrendingUp` в `DashboardLayout.js`
   - **Решение:** Добавлен импорт `TrendingUp` из `lucide-react` в `/app/frontend/src/components/DashboardLayout.js`
   - **Тестирование:** Успешный логин под admin@admin.com, dashboard полностью загружается
   - **Статус:** ✅ ИСПРАВЛЕНО И ПРОТЕСТИРОВАНО

### Current Status
- Приложение **полностью работоспособно**
- Все основные функции доступны: логин, dashboard, чаты, проекты, competitors
- Интерфейс на русском языке работает корректно

### Pending Tasks (P1)
1. ~~**Рефакторинг server.py (~4800 строк)**~~ ✅ ЗАВЕРШЕНО
2. **Рефакторинг ChatPage.js (~1780 строк)** - Интегрировать созданные компоненты
3. **Улучшение атрибуции источников в AI** - Показывать какой файл использован для ответа
4. **Полная интернационализация (i18n)** - Все строки на русском

### Known Technical Debt
- ~~`server.py`: ~4800 строк монолита~~ ✅ Рефакторинг завершен
- `ChatPage.js`: ~1780 строк монолита
- Созданы компоненты чата, но не интегрированы

---

## 15. Session Updates (2026-03-09)

### Completed: Server.py Refactoring (P0)
**БЫЛО:** `server.py` = 4791 строк (монолит)
**СТАЛО:** `server.py` = 177 строк (точка входа)

Код разбит на модульные файлы:
| Модуль | Строк | Описание |
|--------|-------|----------|
| `routes/admin.py` | 429 | Админ-панель, управление пользователями |
| `routes/auth.py` | 50 | Аутентификация |
| `routes/chats.py` | 217 | Управление чатами |
| `routes/competitors.py` | 418 | **NEW** Competitor Tracker |
| `routes/departments.py` | 430 | Управление отделами |
| `routes/enterprise_sources.py` | 802 | Корпоративные источники |
| `routes/global_sources.py` | 369 | Глобальные источники |
| `routes/images.py` | 189 | Генерация изображений |
| `routes/insights.py` | 288 | AI-аналитика |
| `routes/messages.py` | 590 | RAG pipeline, сообщения |
| `routes/news.py` | 108 | Новости |
| `routes/projects.py` | 336 | Проекты |
| `routes/sources.py` | 647 | Источники документов |
| `routes/user_settings.py` | 232 | Настройки пользователя, AI Profile |

**Всего в routes:** 5106 строк (модульная структура)

### Test Results
- ✅ Login API работает
- ✅ Projects API работает
- ✅ Quick chats API работает
- ✅ Admin users API работает
- ✅ AI Profile API работает
- ✅ Dashboard загружается
- ✅ Все функции работают

---

## 16. Session Updates (2026-03-10)

### Completed: Product Catalog Feature (Этапы 1-2)

**Backend (`/app/backend/routes/product_catalog.py`):**
- CRUD endpoints для продуктов
- CSV импорт с preview и выбором колонок
- Relations management (compatible, bundle, requires)
- Tender matching endpoint
- Статистика и фильтры по категориям/вендорам

**Frontend:**
- `/product-catalog` — список продуктов с поиском и фильтрами
- `/product-catalog/{id}` — детальная страница с редактированием
- Import Modal с preview и выбором extra columns
- Relations UI с двусторонними связями
- Sidebar link "Product Catalog" (доступен всем)

**Схема данных (`product_catalog` collection):**
```
{
  "id": uuid,
  "article_number": string (unique),
  "title_en": string,
  "crm_code": string,
  "root_category": string,
  "lvl1/2/3_subcategory": string,
  "vendor": string,
  "description": string,
  "features": string,
  "attribute_values": string,
  "product_model": string,
  "datasheet_url": string,
  "aliases": [string],
  "price": float,
  "relations": [{product_id, relation_type}],
  "extra_fields": object,
  "is_active": bool,
  "source": "csv_import" | "manual",
  "last_synced_at": datetime
}
```

**API Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/product-catalog` | GET | Список с поиском и фильтрами |
| `/api/product-catalog/stats` | GET | Статистика |
| `/api/product-catalog/categories` | GET | Категории для фильтров |
| `/api/product-catalog/{id}` | GET | Один продукт |
| `/api/product-catalog` | POST | Создать (Admin/Manager) |
| `/api/product-catalog/{id}` | PUT | Обновить |
| `/api/product-catalog/{id}` | DELETE | Soft delete |
| `/api/product-catalog/import/preview` | POST | Preview CSV |
| `/api/product-catalog/import` | POST | Импорт CSV |
| `/api/product-catalog/{id}/relations` | POST | Добавить связь |
| `/api/product-catalog/{id}/relations/{rid}` | DELETE | Удалить связь |
| `/api/product-catalog/match` | POST | Tender matching |

### Bug Fixes
- Исправлен конфликт `date-fns@4.1.0` → `^3.6.0`
- Исправлен конфликт `react-day-picker@8.10.1` → `^9.4.4`
- Исправлен `db = get_db()` в `user_settings.py`
- Исправлен порядок роутов `/stats` перед `/{product_id}`
- **[FIXED 2026-03-12]** Исправлена критическая ошибка загрузки файлов (400 Bad Request) - `extract_text_wrapper` возвращал пустую строку вместо извлечения текста из файлов

### Pending (Этап 3)
- AI Integration — поиск продуктов в чате
- Tender Analysis panel в Project Sources
- Weekly Sync (APScheduler)

---

**Document Version:** 1.7
**Last Updated:** 2026-02-XX
**Author:** Planet Knowledge Team

## 18. Session Updates (2026-02)

### Completed: URL Content Fetching Feature

**Feature:** Automatic URL reading in chat messages
- When user pastes any URL (HTML page or PDF) in chat, the AI automatically reads and uses the content
- Supports HTML pages (via BeautifulSoup) and PDF files (via pypdf, up to 10 pages)
- Max 3 URLs per message, max 8000 chars per URL
- Context limit automatically expands to 18000 chars when URL content is present
- Gracefully handles inaccessible URLs (404, 403) — AI continues without crashing

**Modified:** `/app/backend/routes/messages.py`
- Added URL fetch loop after RAG context build
- Added URL instruction in Claude system prompt
- Increased context window for URL-enriched queries

**Tests:**
- HTML test: `https://httpbin.org/html` — AI correctly read Moby Dick excerpt ✅
- PDF test: `https://filesamples.com/samples/document/pdf/sample1.pdf` — AI correctly read document ✅

## 17. Session Updates (2026-03-16)

### RAG Pipeline — Semantic Search Implementation

**Changes:**
- `services/rag.py` — replaced keyword search with cosine similarity
- `services/rag.py` — OpenAI embeddings replaced with **Voyage AI** (`voyage-3`)
- `routes/sources.py` — embeddings now generated on file upload (3 endpoints)
- `frontend/ChatPage.js` — fixed `PUT → POST` for active-sources (405 bug)
- `migrate_embeddings.py` — migration script for existing chunks

**Result:** Semantic RAG pipeline fully operational in production ✅