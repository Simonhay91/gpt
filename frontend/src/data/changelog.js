export const APP_VERSION = "2.1.0";

export const CHANGELOG = [
  {
    version: "2.1.0",
    date: "Февраль 2026",
    badge: "new",
    changes: [
      "Авто-чтение HTML/PDF из URL прямо в чате",
      "Бейдж «URL прочитан» под ответом AI",
      "Добавление PDF по ссылке как источника",
      "Личные источники — показывает в каких проектах опубликован файл",
      "Источники в чате — бейдж с именем проекта",
      "Project Memory — исправлена работа извлечения фактов",
      "Image Generator — загрузка фото-референса в Generate",
      "Заголовок вкладки: PLANET KNOWLEDGE + новый favicon",
      "Авторизация — токен действует 7 дней",
      "Логика GPT config — промпт не перезаписывается при рестарте",
    ]
  },
  {
    version: "2.0.0",
    date: "Январь 2026",
    badge: null,
    changes: [
      "Brave Web Search — веб-поиск прямо из чата",
      "Редактирование сообщений с регенерацией ответа AI",
      "Уточняющие вопросы — AI просит дополнительный контекст",
      "Save Context — суммаризация диалога в AI Profile",
      "Project Memory — AI помнит ключевые факты проекта",
      "Product Catalog Phase 2 — импорт CSV, связи продуктов",
      "Конкурентный трекер",
      "Рефакторинг server.py",
    ]
  },
  {
    version: "1.5.0",
    date: "Декабрь 2025",
    badge: null,
    changes: [
      "RAG Pipeline — Voyage AI semantic search",
      "Semantic Cache — повторные запросы без AI",
      "Source Insights — AI анализ документов",
      "Генерация изображений в проектах",
      "Аудит логи с пагинацией",
      "Загрузка файлов — исправлен 400 Bad Request",
    ]
  },
  {
    version: "1.0.0",
    date: "Ноябрь 2025",
    badge: null,
    changes: [
      "Аутентификация и роли (Admin, Manager, Editor, Viewer)",
      "Проекты, Quick Chats",
      "Личные, проектные, отделовские и глобальные источники",
      "Workflow одобрения источников",
      "Управление отделами и пользователями",
      "Tech News лента",
    ]
  }
];
