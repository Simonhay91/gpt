export const APP_VERSION = "2.3.3";

export const CHANGELOG = [
  {
    version: "2.3.3",
    date: "Март 2026",
    badge: "new",
    changes: [
      "Excel скачивание — файл больше не удаляется после первого скачивания",
      "Excel из чата — работает с любым запросом при активном источнике",
      "Claude не генерирует фейковый XML в ответах",
      "Edit сообщений — исправлен дублирующий user message в DB",
      "Edit сообщений — Message not found устранён (реальный UUID из базы)",
      "Новый чат — создаётся мгновенно, авто-переименование по первому сообщению",
    ]
  },
  {
    version: "2.3.2",
    date: "Март 2026",
    badge: null,
    changes: [
      "Кнопка + в поле ввода — меню с Upload, Add URL, Generate Image, Save Context, Project Memory",
      "Scroll-to-bottom кнопка по центру экрана",
      "Уточняющие вопросы — клик сразу отправляет ответ",
      "Project Memory — исправлена ошибка пустого JSON от AI",
      "Auto-save контекста каждые 10 AI-ответов",
      "Оптимизация DB запросов — проекции полей, лимиты",
    ]
  },
  {
    version: "2.3.0",
    date: "Март 2026",
    badge: null,
    changes: [
      "Excel/CSV Assistant — обработка таблиц через AI прямо в диалоге",
      "Excel из чата — AI трансформирует файл и встраивает кнопку скачивания в ответ",
      "Поддержка NaN/Inf — пустые ячейки не ломают обработку",
    ]
  },
  {
    version: "2.2.0",
    date: "Февраль 2026",
    badge: null,
    changes: [
      "Changelog модал — история обновлений прямо в интерфейсе",
      "Версия приложения в футере",
      "Image Generator — загрузка фото-референса",
      "Project Memory — исправлена работа извлечения фактов",
      "Заголовок вкладки: PLANET KNOWLEDGE + новый favicon",
    ]
  },
  {
    version: "2.1.0",
    date: "Январь 2026",
    badge: null,
    changes: [
      "Авто-чтение HTML/PDF из URL прямо в чате",
      "Добавление PDF по ссылке как источника",
      "Личные источники — бейдж с проектами",
      "Авторизация — токен действует 7 дней",
    ]
  },
  {
    version: "2.0.0",
    date: "Декабрь 2025",
    badge: null,
    changes: [
      "Brave Web Search — веб-поиск прямо из чата",
      "Редактирование сообщений с регенерацией ответа AI",
      "Уточняющие вопросы от AI",
      "Save Context — суммаризация в AI Profile",
      "Project Memory — AI помнит факты проекта",
    ]
  },
  {
    version: "1.5.0",
    date: "Ноябрь 2025",
    badge: null,
    changes: [
      "RAG Pipeline — Voyage AI semantic search",
      "Semantic Cache",
      "Source Insights — AI анализ документов",
      "Генерация изображений в проектах",
    ]
  },
  {
    version: "1.0.0",
    date: "Октябрь 2025",
    badge: null,
    changes: [
      "Аутентификация и роли (Admin, Manager, Editor, Viewer)",
      "Проекты, Quick Chats",
      "Источники: личные, проектные, отделовские, глобальные",
      "Workflow одобрения источников",
      "Tech News лента",
    ]
  }
];
