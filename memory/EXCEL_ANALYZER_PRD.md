# Excel/CSV Analyzer - Product Requirements Document

## 1. Обзор продукта

### 1.1 Назначение
Excel/CSV Analyzer - инструмент для интеллектуального анализа табличных данных с использованием AI (GPT-4.1-mini). Позволяет пользователям загружать файлы и задавать вопросы на естественном языке.

### 1.2 Целевая аудитория
- Бизнес-аналитики
- Менеджеры по продуктам
- Специалисты по закупкам
- Финансовые аналитики
- Любые пользователи, работающие с табличными данными

### 1.3 Ключевые проблемы, которые решает
| Проблема | Решение |
|----------|---------|
| Сложность Excel формул | Вопросы на естественном языке |
| Поиск по большим таблицам | AI-поиск с фильтрацией |
| Анализ данных без навыков программирования | Автоматический анализ |
| Генерация отчётов | Экспорт в PDF/Excel |

---

## 2. Текущая архитектура

### 2.1 Технический стек
```
Backend:  FastAPI + Python
Frontend: React + Tailwind CSS
AI:       GPT-4.1-mini (OpenAI)
Storage:  In-memory sessions (временно)
```

### 2.2 Поток данных
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Upload    │────▶│   Parse     │────▶│   Store     │
│   CSV/XLSX  │     │   to Text   │     │   Session   │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
┌─────────────┐     ┌─────────────┐           ▼
│   Return    │◀────│   GPT-4.1   │◀────┌─────────────┐
│   Answer    │     │   Process   │     │   Question  │
└─────────────┘     └─────────────┘     └─────────────┘
```

### 2.3 API Endpoints
| Endpoint | Method | Описание |
|----------|--------|----------|
| `/api/analyzer/upload` | POST | Загрузка файла, создание сессии |
| `/api/analyzer/ask` | POST | Отправка вопроса |
| `/api/analyzer/session/{id}` | GET | Получение истории сессии |
| `/api/analyzer/session/{id}` | DELETE | Удаление сессии |
| `/api/analyzer/session/{id}/export/excel` | GET | Экспорт в Excel |
| `/api/analyzer/session/{id}/export/pdf` | GET | Экспорт в PDF |

### 2.4 Структура данных сессии
```python
{
    "session_id": "uuid",
    "file_path": "/tmp/analyzer_uuid.csv",
    "file_name": "products.csv",
    "mime_type": "text/csv",
    "user_id": "user_uuid",
    "columns": ["Name", "Price", "Category", ...],
    "total_rows": 3620,
    "created_at": "2024-03-02T15:00:00Z",
    "messages": [
        {"question": "...", "answer": "...", "timestamp": "..."}
    ]
}
```

---

## 3. Текущие ограничения

### 3.1 Технические лимиты
| Параметр | Текущее значение | Причина |
|----------|------------------|---------|
| Max символов | 100,000 | GPT context window |
| Max строк | ~350-500 | Зависит от ширины данных |
| Max размер файла | 10 MB | Память сервера |
| Max значение ячейки | 150 символов | Оптимизация контекста |

### 3.2 Проблемы с большими файлами
```
Файл: 3620 строк × 20 колонок
Средняя строка: ~2000 символов
Всего: ~7,200,000 символов

GPT лимит: 100,000 символов
Результат: Только ~50 строк попадают в контекст
```

### 3.3 Известные баги
1. **Truncation без уведомления** - пользователь не видит какие строки пропущены
2. **Нет выбора колонок** - все колонки включаются в контекст
3. **In-memory storage** - сессии теряются при перезапуске

---

## 4. Roadmap улучшений

### 4.1 Phase 1: Оптимизация контекста (P0)
**Цель:** Увеличить количество анализируемых строк

#### 4.1.1 Умный выбор колонок
```python
# Пользователь выбирает нужные колонки
POST /api/analyzer/configure
{
    "session_id": "...",
    "selected_columns": ["Name", "Price", "Category"],
    "exclude_columns": ["Description", "Long_Text"]
}
```

#### 4.1.2 Двухэтапный анализ
```
Этап 1: Фильтрация в Python (все 3620 строк)
        - Поиск по ключевым словам
        - Фильтрация по условиям
        
Этап 2: AI анализ (только релевантные строки)
        - GPT получает отфильтрованные данные
        - Полный контекст для точного ответа
```

#### 4.1.3 Chunked processing
```python
# Для вопросов типа "найди все X"
async def process_in_chunks(data, question):
    results = []
    for chunk in split_into_chunks(data, 500):
        matches = await gpt_find_matches(chunk, question)
        results.extend(matches)
    return aggregate_results(results)
```

### 4.2 Phase 2: Предварительная обработка (P1)
**Цель:** Быстрые ответы без AI для простых запросов

#### 4.2.1 Локальные операции (без GPT)
| Операция | Реализация |
|----------|------------|
| Подсчёт строк | `len(df)` |
| Уникальные значения | `df['col'].unique()` |
| Сумма/Среднее | `df['col'].sum()` |
| Фильтрация | `df[df['col'] == 'value']` |
| Дубликаты | `df.duplicated()` |

#### 4.2.2 Интеллектуальный роутинг
```python
def route_question(question: str):
    # Простые операции - Python
    if "сколько строк" in question.lower():
        return "local", count_rows
    if "уникальные значения" in question.lower():
        return "local", get_unique
    if "сумма" in question.lower():
        return "local", calculate_sum
    
    # Сложный анализ - GPT
    return "gpt", analyze_with_gpt
```

### 4.3 Phase 3: Персистентность (P1)
**Цель:** Сохранение сессий между перезапусками

#### 4.3.1 MongoDB schema
```python
# Collection: analyzer_sessions
{
    "_id": ObjectId,
    "session_id": "uuid",
    "user_id": "user_uuid",
    "file_name": "products.csv",
    "file_path": "/uploads/analyzer/uuid.csv",
    "columns": [...],
    "total_rows": 3620,
    "messages": [...],
    "created_at": ISODate,
    "last_accessed": ISODate,
    "expires_at": ISODate  # Auto-delete after 7 days
}
```

#### 4.3.2 File storage
```
/uploads/analyzer/
├── {session_id}.csv
├── {session_id}.xlsx
└── {session_id}_metadata.json
```

### 4.4 Phase 4: UI улучшения (P2)

#### 4.4.1 Column selector
```jsx
<ColumnSelector
    columns={session.columns}
    selected={selectedColumns}
    onChange={handleColumnChange}
/>
// Позволяет выбрать какие колонки анализировать
```

#### 4.4.2 Filter builder
```jsx
<FilterBuilder
    columns={session.columns}
    filters={[
        { column: "Category", operator: "equals", value: "Optical cable" },
        { column: "Tax", operator: "not_empty" }
    ]}
    onApply={handleFilter}
/>
// Визуальный построитель фильтров
```

#### 4.4.3 Data preview с пагинацией
```jsx
<DataTable
    data={session.preview}
    totalRows={session.total_rows}
    page={currentPage}
    pageSize={100}
    onPageChange={handlePageChange}
/>
```

#### 4.4.4 Progress indicator
```jsx
<AnalysisProgress
    stage="filtering"  // filtering | analyzing | formatting
    progress={65}
    rowsProcessed={2400}
    totalRows={3620}
/>
```

---

## 5. Детальные спецификации

### 5.1 Двухэтапный анализ (подробно)

#### Архитектура
```
┌──────────────────────────────────────────────────────────┐
│                    User Question                          │
│         "Покажи все optical cable с tax > 0"             │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│              Question Classifier (GPT)                    │
│    Определяет: тип запроса, колонки, условия             │
│    Output: {type: "filter", columns: [...], conditions}   │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│              Python Filter Engine                         │
│    Обрабатывает ВСЕ 3620 строк локально                  │
│    Применяет условия фильтрации                          │
│    Output: 200 matching rows                              │
└────────────────────────┬─────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────┐
│              GPT Formatter                                │
│    Получает только 200 отфильтрованных строк             │
│    Форматирует ответ для пользователя                    │
│    Output: Formatted list with all 200 products          │
└──────────────────────────────────────────────────────────┘
```

#### Реализация
```python
async def smart_analyze(session: dict, question: str):
    # Step 1: Classify question
    classification = await classify_question(question, session['columns'])
    
    # Step 2: Local processing if possible
    if classification['type'] == 'filter':
        # Parse all data into DataFrame
        df = load_dataframe(session['file_path'])
        
        # Apply filters locally
        for condition in classification['conditions']:
            df = apply_condition(df, condition)
        
        # Now send only filtered data to GPT
        filtered_text = df_to_text(df)
        
    elif classification['type'] == 'aggregate':
        # Calculate locally
        df = load_dataframe(session['file_path'])
        result = calculate_aggregate(df, classification)
        return format_aggregate_result(result)
    
    else:
        # Complex analysis - use chunked GPT
        filtered_text = session['file_text']
    
    # Step 3: GPT formatting
    response = await gpt_format_response(filtered_text, question)
    return response
```

### 5.2 Question Classifier

#### Типы запросов
| Тип | Пример | Обработка |
|-----|--------|-----------|
| `filter` | "Покажи все X где Y" | Python filter → GPT format |
| `aggregate` | "Сумма/среднее/count" | Python only |
| `search` | "Найди product ABC" | Python search → GPT format |
| `compare` | "Сравни A и B" | GPT with filtered data |
| `analyze` | "Какие тренды?" | GPT with sampled data |

#### Classifier prompt
```python
CLASSIFIER_PROMPT = """
Analyze this question about a CSV/Excel file and classify it.

Columns available: {columns}

Question: {question}

Return JSON:
{
    "type": "filter|aggregate|search|compare|analyze",
    "target_columns": ["col1", "col2"],
    "conditions": [
        {"column": "Category", "operator": "contains", "value": "optical"}
    ],
    "aggregation": "sum|avg|count|min|max" (if type=aggregate)
}
"""
```

### 5.3 Формат данных для GPT

#### Текущий формат (неоптимальный)
```
R1:OptoWire AS-L-16FO-4KN Aerial ADSS Optical Cable|T-OC-AA-CLT-0005|20007|521|506|5|0|...
```
~200 символов на строку с 20 колонками

#### Оптимизированный формат
```
# Только выбранные колонки
R1:OptoWire AS-L-16FO|20007|5|0
R2:OptoWire AS-L-24FO|20008|3|0
```
~40 символов на строку

#### Выигрыш
```
Текущий:  100,000 / 200 = 500 строк
Новый:    100,000 / 40  = 2,500 строк
Улучшение: 5x
```

---

## 6. UI/UX Спецификации

### 6.1 Новый интерфейс загрузки

```
┌─────────────────────────────────────────────────────────┐
│  📊 Excel/CSV Analyzer                         [GPT-4.1] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │     📁 Перетащите файл или нажмите             │   │
│  │        Поддерживаются: .xlsx, .csv             │   │
│  │        Максимум: 10 MB                         │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 6.2 Выбор колонок (новое)

```
┌─────────────────────────────────────────────────────────┐
│  📋 Выберите колонки для анализа                        │
├─────────────────────────────────────────────────────────┤
│  ☑ Name           ☑ Category        ☐ Description      │
│  ☑ Price          ☑ Tax             ☐ Long_Notes       │
│  ☑ Code           ☐ Internal_ID     ☐ Created_Date     │
│                                                         │
│  Выбрано: 5 из 12 колонок                              │
│  Примерное покрытие: ~2,500 строк из 3,620             │
│                                                         │
│  [Выбрать все]  [Снять все]  [Применить]               │
└─────────────────────────────────────────────────────────┘
```

### 6.3 Debug панель (новое)

```
┌─────────────────────────────────────────────────────────┐
│  🔧 Debug Info                              [Свернуть]  │
├─────────────────────────────────────────────────────────┤
│  Файл:        products.csv                              │
│  Всего строк: 3,620                                     │
│  ─────────────────────────────────────────────────────  │
│  В контексте: 2,450 строк (67%)                        │
│  Символов:    98,500 / 100,000                         │
│  Колонок:     5 из 12                                   │
│  ─────────────────────────────────────────────────────  │
│  Этап 1:      Python фильтрация ✓                      │
│  Найдено:     234 совпадения                           │
│  Этап 2:      GPT форматирование ✓                     │
│  Токенов:     ~25,000                                   │
└─────────────────────────────────────────────────────────┘
```

### 6.4 Быстрые действия (новое)

```
┌─────────────────────────────────────────────────────────┐
│  ⚡ Быстрые действия (без AI)                           │
├─────────────────────────────────────────────────────────┤
│  [📊 Статистика]  [🔍 Дубликаты]  [📈 Уникальные]      │
│  [➕ Сумма по...]  [📉 Пустые значения]                 │
└─────────────────────────────────────────────────────────┘
```

---

## 7. Метрики успеха

### 7.1 Технические метрики
| Метрика | Текущее | Цель |
|---------|---------|------|
| Строк в контексте | ~100-500 | 2000+ |
| Время ответа | 5-15 сек | < 5 сек |
| Точность фильтрации | ~60% | 95%+ |
| Успешных запросов | 70% | 95%+ |

### 7.2 Бизнес метрики
| Метрика | Измерение |
|---------|-----------|
| Использование | Сессий в день |
| Вовлечённость | Вопросов на сессию |
| Удовлетворённость | Полнота ответов |
| Экспорт | % сессий с экспортом |

---

## 8. Приоритеты реализации

### Sprint 1 (Неделя 1-2)
- [ ] Column selector UI
- [ ] Python-based filtering
- [ ] Question classifier
- [ ] Двухэтапный анализ

### Sprint 2 (Неделя 3-4)
- [ ] Быстрые действия (без AI)
- [ ] Debug панель
- [ ] MongoDB persistence
- [ ] File storage

### Sprint 3 (Неделя 5-6)
- [ ] Filter builder UI
- [ ] Data preview с пагинацией
- [ ] Progress indicator
- [ ] Оптимизация производительности

---

## 9. Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| GPT не понимает вопрос | Средняя | Высокое | Few-shot примеры в промпте |
| Превышение лимита токенов | Высокая | Среднее | Двухэтапный анализ |
| Потеря сессий | Высокая | Среднее | MongoDB persistence |
| Медленные ответы | Средняя | Среднее | Локальная обработка |

---

## 10. Заключение

Excel/CSV Analyzer - мощный инструмент, который требует оптимизации для работы с большими файлами. Ключевые улучшения:

1. **Двухэтапный анализ** - фильтрация в Python, форматирование в GPT
2. **Выбор колонок** - пользователь контролирует что анализировать
3. **Локальные операции** - быстрые ответы без AI
4. **Персистентность** - сохранение сессий в MongoDB

Эти изменения увеличат покрытие данных в 5-10 раз и значительно улучшат пользовательский опыт.
