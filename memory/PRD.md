# Planet GPT — Product Requirements Document

## Обзор продукта

**Planet GPT** — корпоративная SaaS-платформа для работы с AI (GPT), позволяющая командам совместно использовать базу знаний компании через интеллектуальный чат-интерфейс.

### Ключевые преимущества
- 🔒 **Изоляция данных** — проекты и данные строго разделены между пользователями
- 📚 **Централизованная база знаний** — глобальные источники доступны всем
- 💰 **Экономия токенов** — семантический кэш снижает затраты на 30-70%
- 👥 **Гибкий доступ** — fine-grained контроль видимости чатов в shared проектах

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│                   React + Tailwind CSS                       │
│                      (Port 3000)                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Backend                               │
│                   FastAPI + Python                           │
│                      (Port 8001)                             │
├─────────────────────────────────────────────────────────────┤
│  • JWT Authentication                                        │
│  • OpenAI GPT Integration (chat, embeddings)                │
│  • File Processing (PDF, DOCX, XLSX, PPTX, CSV, Images)    │
│  • OCR (Tesseract)                                          │
│  • Semantic Cache                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Database                              │
│                        MongoDB                               │
├─────────────────────────────────────────────────────────────┤
│  Collections:                                                │
│  • users, projects, chats, messages                         │
│  • sources, source_chunks                                   │
│  • semantic_cache, source_usage                             │
│  • token_usage, user_prompts, gpt_config                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Модули и функционал

### 1. Аутентификация и пользователи

#### 1.1 Модель доступа
- **Admin-only создание** — только администратор создаёт пользователей
- **Email-based admin detection** — пользователи с `@admin.com` автоматически админы
- **JWT токены** — срок действия 24 часа

#### 1.2 Роли
| Роль | Возможности |
|------|-------------|
| **Admin** | Всё + создание пользователей, GPT config, глобальные источники |
| **User** | Проекты, чаты, источники в своих проектах |
| **User + Global Edit** | + редактирование глобальных источников |

#### 1.3 API
```
POST /api/auth/register     — Создание пользователя (admin only)
POST /api/auth/login        — Вход, возврат JWT
GET  /api/auth/me           — Текущий пользователь
```

---

### 2. Проекты

#### 2.1 Описание
Проект — контейнер для чатов и источников. Все источники проекта автоматически используются во всех чатах этого проекта.

#### 2.2 Sharing
- Владелец может поделиться проектом с другими пользователями
- Fine-grained контроль: можно указать какие конкретно чаты видны каждому shared-пользователю
- `sharedWithUsers: null` — виден всем shared участникам
- `sharedWithUsers: [userId1, userId2]` — виден только указанным

#### 2.3 API
```
GET    /api/projects                          — Список проектов
POST   /api/projects                          — Создать проект
GET    /api/projects/{id}                     — Детали проекта
DELETE /api/projects/{id}                     — Удалить проект
POST   /api/projects/{id}/share               — Поделиться с пользователем
DELETE /api/projects/{id}/share/{userId}      — Убрать пользователя
PUT    /api/chats/{chatId}/visibility         — Настроить видимость чата
```

---

### 3. Чаты

#### 3.1 Типы чатов
| Тип | Описание |
|-----|----------|
| **Project Chat** | Привязан к проекту, имеет доступ к источникам |
| **Quick Chat** | Без проекта, без источников, для быстрых вопросов |

#### 3.2 Возможности
- Переименование чатов
- Перемещение Quick Chat в проект
- Отображение имени отправителя в shared чатах
- Copy-кнопка для ответов GPT
- Кликабельные URL в ответах

#### 3.3 API
```
POST   /api/projects/{projectId}/chats    — Создать чат в проекте
POST   /api/quick-chats                   — Создать Quick Chat
GET    /api/chats/{id}/messages           — История сообщений
POST   /api/chats/{id}/messages           — Отправить сообщение
PUT    /api/chats/{id}                    — Переименовать
POST   /api/chats/{id}/move               — Переместить в проект
DELETE /api/chats/{id}                    — Удалить чат
```

---

### 4. Источники (Sources)

#### 4.1 Поддерживаемые форматы
| Формат | Обработка |
|--------|-----------|
| PDF | PyPDF2 + поддержка зашифрованных (pycryptodome) |
| DOCX | python-docx |
| PPTX | python-pptx |
| XLSX | openpyxl |
| CSV | Встроенный парсер с поддержкой больших файлов |
| TXT, MD | Прямое чтение |
| PNG, JPEG | OCR через Tesseract |
| URL | Web scraping через httpx + BeautifulSoup |

#### 4.2 Обработка
1. Файл загружается
2. Текст извлекается
3. Разбивается на chunks (~1500 символов)
4. Chunks сохраняются в `source_chunks`
5. При запросе — keyword ranking для выбора релевантных chunks

#### 4.3 Глобальные источники
- Управляются администратором
- Автоматически включаются в контекст ВСЕХ чатов
- Пользователи с разрешением `canEditGlobalSources` могут добавлять
- Статистика использования для каждого источника

#### 4.4 API
```
# Project Sources
POST   /api/projects/{id}/sources/upload     — Загрузить файл
POST   /api/projects/{id}/sources/url        — Добавить URL
GET    /api/projects/{id}/sources            — Список источников
DELETE /api/sources/{id}                     — Удалить
GET    /api/projects/{id}/sources/{id}/preview — Превью текста
GET    /api/projects/{id}/search-sources     — Поиск по источникам

# Global Sources
GET    /api/global-sources                   — Список (для пользователей)
POST   /api/global-sources/upload            — Загрузить (с разрешением)
DELETE /api/global-sources/{id}              — Удалить своё
GET    /api/global-sources/{id}/preview      — Превью

# Admin Global Sources
GET    /api/admin/global-sources             — Полный список
POST   /api/admin/global-sources/upload      — Загрузить
POST   /api/admin/global-sources/url         — Добавить URL
DELETE /api/admin/global-sources/{id}        — Удалить любой
GET    /api/admin/global-sources/stats       — Статистика использования
```

---

### 5. Семантический кэш

#### 5.1 Принцип работы
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Вопрос     │────▶│  Embedding   │────▶│  Поиск в    │
│  пользов.   │     │  (OpenAI)    │     │  кэше       │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
                    ┌───────────────────────────┴───────────────┐
                    ▼                                           ▼
            ┌───────────────┐                         ┌─────────────────┐
            │ Similarity    │                         │ Нет похожего    │
            │ ≥ 92%        │                         │ вопроса         │
            └───────┬───────┘                         └────────┬────────┘
                    ▼                                          ▼
            ┌───────────────┐                         ┌─────────────────┐
            │ Вернуть       │                         │ Вызвать GPT     │
            │ кэшированный  │                         │ + сохранить     │
            │ ответ         │                         │ в кэш           │
            └───────────────┘                         └─────────────────┘
```

#### 5.2 Настройки
| Параметр | Значение | Описание |
|----------|----------|----------|
| `CACHE_SIMILARITY_THRESHOLD` | 0.92 | Минимальная схожесть для cache hit |
| `CACHE_TTL_DAYS` | 30 | Срок жизни записи в кэше |
| `EMBEDDING_MODEL` | text-embedding-3-small | Модель для embeddings |

#### 5.3 Экономия
- Идентичные вопросы: **100% экономия**
- Похожие формулировки: **~80% экономия** (при схожести ≥92%)
- Индикатор в ответе: `📦 Ответ из кэша (схожесть: X%)`

#### 5.4 API
```
GET    /api/admin/cache/stats        — Статистика кэша
DELETE /api/admin/cache/clear        — Очистить весь кэш
DELETE /api/admin/cache/{id}         — Удалить запись
```

---

### 6. Администрирование

#### 6.1 Управление пользователями
- Создание с автогенерацией пароля
- Просмотр статистики: токены, сообщения, источники
- Настройка индивидуальной GPT модели
- Настройка custom prompt для пользователя
- Выдача разрешения на глобальные источники

#### 6.2 GPT Configuration
- Глобальная модель (по умолчанию gpt-4.1-mini)
- Developer system prompt
- Per-user override модели

#### 6.3 Статистика
- Использование токенов по пользователям
- Использование источников (какие файлы чаще всего помогают)
- Эффективность кэша (записи, попадания)

#### 6.4 API
```
GET    /api/admin/users                      — Список пользователей
GET    /api/admin/users/{id}/details         — Детали пользователя
PUT    /api/admin/users/{id}/prompt          — Установить prompt
PUT    /api/admin/users/{id}/gpt-model       — Установить модель
PUT    /api/admin/users/{id}/global-permission — Разрешение на global
DELETE /api/admin/users/{id}                 — Удалить пользователя
GET    /api/admin/config                     — GPT конфигурация
PUT    /api/admin/config                     — Обновить конфиг
GET    /api/admin/source-stats               — Статистика источников
```

---

### 7. UI/UX

#### 7.1 Страницы
| Путь | Описание | Доступ |
|------|----------|--------|
| `/login` | Вход | Все |
| `/dashboard` | Главная, список проектов и Quick Chats | Auth |
| `/projects/{id}` | Проект: чаты, источники, sharing | Auth |
| `/chats/{id}` | Чат с GPT | Auth |
| `/admin/users` | Управление пользователями | Admin |
| `/admin/users/{id}` | Детали пользователя | Admin |
| `/admin/config` | GPT конфигурация | Admin |
| `/admin/global-sources` | Глобальные источники + статистика + кэш | Admin |
| `/global-sources` | Глобальные источники (для пользователей с разрешением) | Auth + Permission |

#### 7.2 Компоненты
- Shadcn/UI как база
- Dark/Light mode
- Responsive design
- Toast notifications (sonner)
- Dialog modals

---

## База данных — Схема

### users
```javascript
{
  id: string,
  email: string,
  passwordHash: string,
  isAdmin: boolean,
  gptModel: string | null,        // Per-user model override
  canEditGlobalSources: boolean,  // Permission for global sources
  createdAt: string,
  lastActivity: string
}
```

### projects
```javascript
{
  id: string,
  name: string,
  ownerId: string,
  sharedWith: [userId, ...],
  createdAt: string
}
```

### chats
```javascript
{
  id: string,
  projectId: string | null,      // null = Quick Chat
  ownerId: string,
  title: string,
  sharedWithUsers: [userId, ...] | null,  // null = visible to all shared
  createdAt: string
}
```

### messages
```javascript
{
  id: string,
  chatId: string,
  role: "user" | "assistant",
  content: string,
  citations: [...],
  usedSources: [...],
  senderEmail: string,
  senderName: string,
  createdAt: string
}
```

### sources
```javascript
{
  id: string,
  projectId: string,             // "__global__" for global sources
  kind: "file" | "url",
  originalName: string,
  mimeType: string,
  storagePath: string,
  sizeBytes: number,
  chunkCount: number,
  uploadedBy: string,
  createdAt: string
}
```

### source_chunks
```javascript
{
  id: string,
  sourceId: string,
  projectId: string,
  chunkIndex: number,
  content: string,
  createdAt: string
}
```

### semantic_cache
```javascript
{
  id: string,
  question: string,
  answer: string,
  embedding: [float, ...],       // 1536 dimensions
  projectId: string | null,
  sourcesUsed: [...],
  createdBy: string,
  createdAt: string,
  hitCount: number,
  lastHitAt: string
}
```

### source_usage
```javascript
{
  sourceId: string,
  sourceName: string,
  usageCount: number,
  lastUsedAt: string,
  usageHistory: [{
    userId: string,
    userEmail: string,
    chatId: string,
    timestamp: string
  }, ...]  // последние 100
}
```

### token_usage
```javascript
{
  userId: string,
  totalTokens: number,
  messageCount: number,
  lastUsedAt: string
}
```

### user_prompts
```javascript
{
  userId: string,
  customPrompt: string
}
```

### gpt_config
```javascript
{
  id: "1",
  model: string,
  developerPrompt: string,
  updatedAt: string
}
```

---

## Конфигурация

### Environment Variables

#### Backend (.env)
```
MONGO_URL=mongodb://...
DB_NAME=planet_gpt
OPENAI_API_KEY=sk-...
JWT_SECRET=your-secret-key
```

#### Frontend (.env)
```
REACT_APP_BACKEND_URL=https://your-domain.com
```

### Лимиты
| Параметр | Значение |
|----------|----------|
| MAX_FILE_SIZE | 50 MB |
| CHUNK_SIZE | 1500 chars |
| MAX_CONTEXT_CHARS | 15000 |
| MAX_CHUNKS_PER_QUERY | 10 |
| CACHE_TTL_DAYS | 30 |

---

## Roadmap

### ✅ Реализовано
- [x] Аутентификация и управление пользователями
- [x] Проекты с sharing и fine-grained visibility
- [x] Project и Quick чаты
- [x] Загрузка файлов (PDF, DOCX, XLSX, PPTX, CSV, TXT, MD)
- [x] OCR для изображений
- [x] URL sources с auto-ingest
- [x] Глобальные источники
- [x] Семантический кэш с embeddings
- [x] Статистика использования источников
- [x] Per-user GPT model и prompts
- [x] Dark/Light mode

### 🔜 Планируется
- [ ] Token limits per user (daily/monthly)
- [ ] Question templates
- [ ] Usage/cost dashboard
- [ ] Background processing for large files
- [ ] Export chat history
- [ ] Webhook integrations

---

## Changelog

### 2026-02-27
- ✨ Семантический кэш с OpenAI embeddings
- ✨ UI для просмотра статистики кэша
- ✨ Разрешение пользователям редактировать глобальные источники
- ✨ Статистика использования источников
- 🐛 Исправлен CSV парсинг для больших файлов

### 2025-12-28
- ✨ Глобальные источники
- ✨ OCR для изображений
- ✨ Fine-grained chat visibility
- ✨ Source preview и download
- ✨ Token-free source search
- 🐛 Исправлена навигация "Назад" в чатах

---

## Контакты

**Продукт:** Planet GPT  
**Технологии:** React, FastAPI, MongoDB, OpenAI  
**Язык интерфейса:** Русский
