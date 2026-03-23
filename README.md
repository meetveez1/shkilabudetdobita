# Умный поиск по книгам (Telegram + n8n-ready)

Решение кейса «Умный поиск по книгам»: ядро поиска/QA на Python + 2 интерфейса:

1. `bot.py` — Telegram-бот на Python.
2. `api.py` — JSON API для интеграции с **n8n**.

## Функциональность

- Загрузка книг `.txt`.
- Поиск релевантных фрагментов (3–5 top matches) с указанием источника.
- Ответы на вопросы по книгам + цитаты-основания.
- Честный отказ, если ответа в текстах нет.

## Стек

- Python 3.11+
- SQLite + FTS5
- python-telegram-bot
- Flask (для JSON API и web-демо)

---

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Вариант A: Telegram-бот на Python

```bash
export TELEGRAM_BOT_TOKEN="<токен от BotFather>"
python bot.py
```

В боте есть кнопочное меню: **📚 Загрузить книгу**, **🔎 Поиск фрагментов**, **❓ Задать вопрос**, **ℹ️ Помощь**.

Команды тоже работают:
- `/addbook` → после этого отправь `.txt` файл
- `/search <запрос>`
- `/ask <вопрос>`
- `/menu` → показать меню

### Вариант B: n8n + Telegram

1. Запусти API:

```bash
python api.py
```

2. Импортируй готовый workflow `n8n/telegram_book_search_workflow.json` (или собери вручную по `N8N_SETUP.md`).
3. После импорта укажи Telegram credentials и проверь API URL в HTTP-нодах.

Подробно по полям **Workflow Settings** (Execution Logic, Timezone, Save executions, Timeout и т.д.) см. раздел 7 в `N8N_SETUP.md`.

---

## API для n8n

### `POST /api/upload`
`multipart/form-data`
- `book`: `.txt` файл (обязательно)
- `title`: строка (опционально)

### `POST /api/search`
`application/json`

```json
{
  "query": "Найди, где говорится про Наташу",
  "limit": 5
}
```

### `POST /api/ask`
`application/json`

```json
{
  "question": "Что произошло с Наташей и Пьером в эпилоге?",
  "limit": 5
}
```

---

## Файлы проекта

- `bot.py` — Telegram-бот.
- `api.py` — API для n8n.
- `N8N_SETUP.md` — пошаговая настройка n8n и код для узлов Code.
- `n8n/telegram_book_search_workflow.json` — готовый JSON для импорта в n8n.
- `smart_book_search/db.py` — БД и FTS5.
- `smart_book_search/ingestion.py` — загрузка/чанкование.
- `smart_book_search/retrieval.py` — поиск фрагментов.
- `smart_book_search/qa.py` — extractive QA.
- `examples/` — тестовые книги.

## Тестовые книги

- `examples/war_and_peace_excerpt.txt`
- `examples/idiot_excerpt.txt`

## Ограничения

- QA extractive (без внешней LLM): ответ формируется из найденных предложений.
- Для загрузки файлов через n8n из Telegram нужна отдельная ветка с получением файла (описано в `N8N_SETUP.md`).


## Troubleshooting (n8n + Telegram)

Ошибка:
`Because of limitations in Telegram Trigger, n8n can't listen for test executions at the same time as listening for production ones...`

Решение:
1. Временно **Deactivate/Unpublish** workflow.
2. Запусти **Execute workflow** для теста.
3. После теста снова **Activate/Publish**.

Подробно: см. раздел 8 в `N8N_SETUP.md`.

