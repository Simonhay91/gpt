# История обновлений / Changelog

Формат: `[дата] — краткое описание`  
Ветка: `main`  
UI версия: `frontend/src/data/changelog.js`

---

## 2026-04-14 — v2.9.12

### Feature: Excel Assistant in Plus menu
**Commit:** `134c80c`  
**Файлы:** `frontend/src/pages/ChatPage.js`, `frontend/src/components/chat/ChatInput.js`, `frontend/src/components/ExcelAssistant.js`

- Plus menu: пункт «Excel Assistant» открывает диалог загрузки таблицы и инструкции к AI (`POST /chats/{id}/excel-process`)
- `ExcelAssistant`: опционально `hideTrigger`, controlled `open` / `onOpenChange` для открытия из родителя без отдельной кнопки в хедере

---

## 2026-04-14 — v2.9.11

### Feature: animated thinking steps during AI response
**Commit:** `ed0ba22`  
**Файлы:** `frontend/src/pages/ChatPage.js`

- Заменили спиннер на анимированные шаги: 📂 Reading sources → 🔍 Searching chunks → 🧠 Thinking → ✍️ Writing answer
- Шаги появляются с задержкой (0 / 1.8 / 3.8 / 6.0 с) для имитации реального процесса
- Адаптация: если нет источников — RAG-шаги пропускаются; если включён Web Search — первый шаг меняется на «Searching the web...»
- Завершённые шаги помечаются ✅ и становятся тусклыми, активный шаг анимирован с bouncing dots

---

## 2026-04-14 — v2.9.10

### Fix/Rollback: auto-save context not writing Project Memory
**Commit:** `6aca086`  
**Файлы:** `backend/routes/messages.py`, `frontend/src/pages/ChatPage.js`

- Откат изменения: авто‑сохранение контекста больше не пишет в Project Memory

---

## 2026-04-14 — v2.9.7

### Fix: AI always knows active sources even when no chunks retrieved
**Файл:** `backend/routes/messages.py`

- Добавлен `elif active_source_names:` блок — если `document_context` пустой но источники активны, AI получает SYS_META с именами источников
- Решает проблему: AI отвечал «нет источников» на мета-вопросы типа «ты видишь файл?», т.к. RAG не находил релевантных чанков по таким запросам

---

## 2026-04-14 — v2.9.6

### Fix: activeSourceIds race condition — send with message payload
**Файлы:** `backend/models/schemas.py`, `backend/routes/messages.py`, `frontend/src/pages/ChatPage.js`

- `MessageCreate` schema: добавлено поле `activeSourceIds: Optional[List[str]]`
- `send_message`: приоритет отдаётся `message_data.activeSourceIds` (real-time из frontend) над DB значением (могло отставать на 500мс из-за debounce)
- `ChatPage.js`: `activeSourceIds` теперь всегда включается в payload сообщения

---

## 2026-04-14 — v2.9.5

### Fix: My Sources shows project badge for sources saved from project chat
**Файл:** `backend/routes/enterprise_sources.py`

- `list_personal_sources`: если у source есть `projectId` (прямая ссылка через save_to_knowledge), добавляет project badge в `publishedTo`
- Дедупликация: не дублирует badge если тот же проект уже есть через `publishedFrom`

---

## 2026-04-14 — v2.9.4

### Fix: save_to_knowledge always saves as personal level
**Файл:** `backend/routes/messages.py`

- `level` всегда `"personal"` — источник появляется в My Sources page
- `projectId` сохраняется для связи с проектом (если вызвано из проектного чата)
- Предыдущий фикс (v2.9.3) ошибочно ставил `level=project`, из-за чего источник не показывался в My Sources

---

## 2026-04-14 — v2.9.3

### RAG — Fix source selection, filename targeting, save-to-sources (`244af3a`)
**Файлы:** `backend/routes/messages.py`, `backend/services/rag.py`

- **Bug fix:** `activeSourceIds` (checkbox в SourcePanel) теперь реально ограничивает RAG-пул.  
  Логика: `null` = чат новый → все источники; `[]` = всё снято вручную → ни одного; `[ids]` = пересечение с accessible.
- **Bug fix:** Pre-RAG filename resolution — если пользователь упоминает имя файла в сообщении, retrieval ограничивается только этим источником.
- **Улучшение:** `SYS_META` теперь содержит `targeted=<filename>` с инструкцией фокусироваться только на упомянутом файле.
- **Улучшение:** `rag.py` — 1.5× score boost для чанков из явно упомянутого источника.
- **Bug fix:** `save_to_knowledge` — при сохранении из проектного чата источник теперь создаётся как `level=project` с реальным `projectId` (раньше всегда `personal + null`).
- **Bug fix:** `save_to_knowledge` — новый источник автоматически добавляется в `chat.activeSourceIds`.

---

### OEM: PDF image extraction, header image upload, brand live preview (`764b813`)
**Файлы:** `backend/routes/oem_datasheet.py`, `frontend/src/pages/AdminBrandsPage.js`

- Добавлена функция `extract_images_from_pdf` (PyMuPDF/fitz) — извлекает изображения из PDF.
- В `rebuild_docx_from_pdf` — изображения вставляются после каждой секции (index 0 пропускается как логотип поставщика).
- Новый endpoint `POST /api/oem/brands/{id}/header-image` — загрузка header image с сохранением в MongoDB (`logoDataMap`).
- Header image вставляется в header-полосу документа рядом с логотипом.
- `extractedImageCount` логируется в `oem_jobs`.
- `AdminBrandsPage`: живой preview бренда (header/footer/colors) справа от формы.
- Слайдеры для `headerHeightPx` (40–120), `logoSizePx` (20–80), `footerHeightPx` (24–60).
- Поле загрузки header image в форме редактирования бренда.

---

### Product matching: AI match-file endpoint + Match File UI (`86deacc`)
**Файлы:** `backend/routes/product_catalog.py`, `frontend/src/pages/ProductCatalogPage.js`

- AI-эндпоинт для сопоставления файла с товарами каталога.
- UI для загрузки файла и просмотра результатов матчинга в ProductCatalogPage.

---

## 2026-04-13

### Fix sidebar layout (`4466540`)
**Файл:** `frontend/src/components/DashboardLayout.js`

- Flex column layout для сайдбара.
- Nav прокручивается независимо.
- Секция пользователя всегда внизу.

---

### Logo persistence — MongoDB base64 fallback (`2a97f3b`)
**Файл:** `backend/routes/oem_datasheet.py`

- Логотипы бренда сохраняются в MongoDB как base64.
- При redeploy (потеря файлов) логотип восстанавливается из базы данных автоматически.

---

### OEM header/footer — full-width edge-to-edge band (`cad5f6e`)
**Файл:** `backend/routes/oem_datasheet.py`

- Полноширинная цветная полоса header/footer через отрицательный `w:ind`.
- Точная высота через `w:lineRule=exact`.
- Контроль: `headerHeightPx`, `headerPaddingPx`, `logoSizePx`, `footerHeightPx`, `footerPaddingPx`.
- Copyright по центру footer-а через tab stop.

---

*Этот файл обновляется вручную после каждого значимого коммита.*
