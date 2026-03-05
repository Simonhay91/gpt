# Planet Knowledge - Анализ рисков и структуры

## 🔴 КРИТИЧЕСКИЕ РИСКИ (Нужно исправить срочно)

### 1. **server.py - Монолит 3,725 строк**
```
Проблема: Один файл содержит 108 функций и 70 API endpoints
Риск: Сложность поддержки, merge конфликты, медленная разработка

Решение:
- Разбить на модули:
  /routes/auth.py       - аутентификация
  /routes/projects.py   - проекты
  /routes/chats.py      - чаты и сообщения
  /routes/sources.py    - источники (объединить с enterprise_sources.py)
  /routes/admin.py      - админка
  /services/rag.py      - RAG pipeline
  /services/cache.py    - семантический кэш
```

### 2. **send_message() - 377 строк в одной функции**
```
Проблема: Гигантская функция, невозможно тестировать
Риск: Баги, сложность отладки

Решение:
async def send_message():
    await validate_chat_access()      # 20 строк
    await process_auto_urls()         # 30 строк
    sources = await get_sources()     # 50 строк
    context = await build_rag_context() # 40 строк
    response = await call_claude()    # 30 строк
    await save_message()              # 20 строк
    await update_cache()              # 20 строк
```

### 3. **Excel Analyzer - In-Memory Sessions**
```python
# routes/analyzer.py:20
analysis_sessions = {}  # ← ТЕРЯЕТСЯ при перезапуске!

Риск: Пользователи теряют сессии анализа
Решение: Сохранять в MongoDB с TTL индексом
```

### 4. **Нет Error Boundaries на Frontend**
```
Проблема: 0 ErrorBoundary компонентов
Риск: Один JS error ломает всё приложение

Решение: Добавить ErrorBoundary wrapper
```

---

## 🟠 СРЕДНИЕ РИСКИ (Нужно запланировать)

### 5. **ChatPage.js - 1,467 строк**
```
Проблема: Самый большой React компонент
Риск: Медленный рендеринг, сложность поддержки

Решение:
- ChatHeader.js      (100 строк)
- MessageList.js     (200 строк)
- MessageInput.js    (150 строк)
- SourcePanel.js     (300 строк)
- ChatActions.js     (100 строк)
```

### 6. **36 запросов с to_list(1000)**
```python
await db.sources.find({...}).to_list(1000)

Проблема: Загрузка всех данных в память
Риск: OOM при большом количестве источников

Решение: Добавить пагинацию
async def get_sources_paginated(skip: int = 0, limit: int = 50):
    return await db.sources.find({...}).skip(skip).limit(limit).to_list(limit)
```

### 7. **Отсутствуют MongoDB индексы**
```javascript
// Нужно создать:
db.sources.createIndex({"level": 1, "status": 1})
db.sources.createIndex({"ownerId": 1, "level": 1})
db.source_chunks.createIndex({"sourceId": 1, "chunkIndex": 1})
db.messages.createIndex({"chatId": 1, "createdAt": -1})
db.chats.createIndex({"projectId": 1, "createdAt": -1})
db.audit_logs.createIndex({"timestamp": -1}, {expireAfterSeconds: 7776000}) // 90 дней
```

### 8. **Нет Rate Limiting**
```
Проблема: 2 упоминания rate limit, но не реализовано
Риск: DDoS, исчерпание API токенов

Решение: slowapi или custom middleware
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@limiter.limit("10/minute")
async def send_message(...):
```

### 9. **Incomplete i18n (локализация ~70%)**
```
Найдено hardcoded строк:
- toast.info('Ничего не найдено')
- toast.info('Requires manager approval')
- Множество других в модальных окнах

Решение: Пройти все файлы и заменить на t('key')
```

---

## 🟡 НИЗКИЕ РИСКИ (Технический долг)

### 10. **Дублирование кода: 88 раз {"_id": 0}**
```python
# Повторяется везде:
await db.sources.find_one({"id": id}, {"_id": 0})
await db.chats.find_one({"id": id}, {"_id": 0})

Решение: Создать helper
async def find_one_clean(collection, query):
    return await collection.find_one(query, {"_id": 0})
```

### 11. **TODO комментарии не реализованы**
```python
# enterprise_sources.py:693
# TODO: Add proper access check based on level

# enterprise_sources.py:727  
# TODO: Add proper permission check
```

### 12. **Нет PropTypes/TypeScript на Frontend**
```
Проблема: 0 PropTypes определений
Риск: Runtime ошибки из-за неправильных props

Решение (минимальное):
ComponentName.propTypes = {
  data: PropTypes.array.isRequired,
  onSave: PropTypes.func
};
```

### 13. **16 файлов с useEffect (потенциальные warnings)**
```
Проблема: useEffect dependency warnings в консоли
Риск: Stale closures, бесконечные ререндеры

Решение: Проверить каждый useEffect и добавить зависимости
```

---

## 📊 ПРИОРИТЕТЫ ИСПРАВЛЕНИЯ

### Фаза 1 (1-2 недели) - Критические
| # | Задача | Сложность | Влияние |
|---|--------|-----------|---------|
| 1 | Разбить server.py на модули | Высокая | Критическое |
| 2 | Refactor send_message() | Средняя | Высокое |
| 3 | MongoDB для analyzer sessions | Низкая | Среднее |
| 4 | Добавить ErrorBoundary | Низкая | Среднее |

### Фаза 2 (2-3 недели) - Средние
| # | Задача | Сложность | Влияние |
|---|--------|-----------|---------|
| 5 | Разбить ChatPage.js | Средняя | Среднее |
| 6 | Добавить пагинацию | Средняя | Среднее |
| 7 | Создать MongoDB индексы | Низкая | Высокое |
| 8 | Rate limiting | Средняя | Среднее |
| 9 | Завершить i18n | Низкая | Низкое |

### Фаза 3 (Backlog) - Низкие
| # | Задача | Сложность |
|---|--------|-----------|
| 10 | Helper для _id exclusion | Низкая |
| 11 | Исправить TODO | Низкая |
| 12 | PropTypes/TypeScript | Высокая |
| 13 | useEffect warnings | Низкая |

---

## 🏗️ РЕКОМЕНДУЕМАЯ СТРУКТУРА ПОСЛЕ РЕФАКТОРИНГА

```
/app/
├── backend/
│   ├── routes/
│   │   ├── auth.py            # Login, register, token
│   │   ├── projects.py        # CRUD проектов
│   │   ├── chats.py           # Чаты и сообщения
│   │   ├── sources.py         # Все источники (unified)
│   │   ├── admin.py           # Админ endpoints
│   │   ├── analyzer.py        # Excel analyzer
│   │   └── news.py            # Tech news
│   │
│   ├── services/
│   │   ├── rag.py             # RAG pipeline
│   │   ├── cache.py           # Semantic cache
│   │   ├── embeddings.py      # OpenAI embeddings
│   │   ├── claude.py          # Claude integration
│   │   └── file_processor.py  # File parsing
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── project.py
│   │   ├── chat.py
│   │   └── source.py
│   │
│   ├── middleware/
│   │   ├── auth.py            # JWT verification
│   │   ├── rate_limit.py      # Rate limiting
│   │   └── error_handler.py   # Global error handler
│   │
│   ├── db/
│   │   ├── indexes.py         # MongoDB index creation
│   │   └── connection.py      # DB connection
│   │
│   └── server.py              # ~200 строк (только app setup)
│
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── chat/
    │   │   │   ├── ChatHeader.js
    │   │   │   ├── MessageList.js
    │   │   │   ├── MessageInput.js
    │   │   │   └── SourcePanel.js
    │   │   ├── common/
    │   │   │   ├── ErrorBoundary.js
    │   │   │   └── LoadingSpinner.js
    │   │   └── ui/
    │   │       └── (shadcn components)
    │   │
    │   ├── hooks/
    │   │   ├── useChat.js
    │   │   ├── useSources.js
    │   │   └── useAuth.js
    │   │
    │   └── pages/
    │       └── (simplified pages)
```

---

## ⚡ QUICK WINS (можно сделать за 1 день)

1. **Создать MongoDB индексы** - 30 минут
2. **Добавить ErrorBoundary** - 1 час
3. **Перенести analyzer sessions в MongoDB** - 2 часа
4. **Завершить i18n** - 3 часа
5. **Исправить TODO комментарии** - 1 час

---

## 📈 МЕТРИКИ ДЛЯ ОТСЛЕЖИВАНИЯ

После рефакторинга отслеживать:
- Размер файлов (< 500 строк)
- Покрытие тестами (> 60%)
- Время ответа API (< 200ms без AI)
- Memory usage (< 512MB)
- Error rate (< 1%)
