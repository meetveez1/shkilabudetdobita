# Как собрать Telegram-бота в n8n (пошагово)

## 0) Готовый JSON workflow

В репозитории добавлен готовый файл:

- `n8n/telegram_book_search_workflow.json`

Импорт в n8n:
1. **Workflows → Import from File**.
2. Выбери `n8n/telegram_book_search_workflow.json`.
3. Открой импортированный workflow.
4. Укажи Telegram credentials в узлах `Telegram Trigger`, `Telegram Send ASK`, `Telegram Send SEARCH`, `Telegram Send HELP`.
5. Проверь URL в узлах `HTTP ASK API` и `HTTP SEARCH API`.

Ниже — самый простой рабочий вариант: **n8n принимает сообщения из Telegram**, а поиск/QA делает наш Python API.

## 1) Что запустить локально

1. Запусти API сервиса:

```bash
python api.py
```

API будет на `http://localhost:8001`.

2. Если n8n в Docker, используй адрес хоста вместо `localhost`, обычно:
- `http://host.docker.internal:8001` (Mac/Windows)
- или IP хоста в Linux.

## 2) Создай бота в Telegram

1. В Telegram открой `@BotFather`.
2. Команда `/newbot`.
3. Скопируй токен вида `123456:ABC...`.

## 3) Настрой credentials в n8n

1. В n8n: **Credentials → New → Telegram API**.
2. Вставь токен бота.
3. Сохрани.

## 4) Собери workflow

### Узлы

1. **Telegram Trigger**
   - Updates: `message`
   - Credentials: твой Telegram API

2. **Code (Parse Command)**
   - Mode: Run Once for Each Item
   - Вставь код:

```javascript
const msg = $json.message || {};
const text = (msg.text || '').trim();
const chatId = msg.chat?.id;

let action = 'help';
let payload = '';

if (text.startsWith('/ask ')) {
  action = 'ask';
  payload = text.replace('/ask', '').trim();
} else if (text.startsWith('/search ')) {
  action = 'search';
  payload = text.replace('/search', '').trim();
} else if (text === '/start' || text === '/help') {
  action = 'help';
}

return [{ json: { action, payload, chatId } }];
```

3. **Switch (By action)**
   - Property: `={{$json.action}}`
   - Cases: `ask`, `search`, `help`

4. Ветка `ask`:
   - **HTTP Request (ASK API)**
     - Method: `POST`
     - URL: `http://host.docker.internal:8001/api/ask` (или твой адрес)
     - Send Body: JSON
     - JSON Body:

```json
{
  "question": "={{$json.payload}}",
  "limit": 5
}
```

   - **Code (Format ASK text)**

```javascript
const data = $json;
let txt = `Ответ:\n${data.answer}\n\nУверенность: ${Number(data.confidence).toFixed(2)}`;

if (Array.isArray(data.citations) && data.citations.length) {
  txt += '\n\nЦитаты:';
  data.citations.slice(0,3).forEach((c, i) => {
    const chunk = (c.text || '').slice(0, 220);
    txt += `\n${i+1}) ${c.book_title}, ${c.chapter || '—'}, #${c.chunk_index}\n${chunk}`;
  });
}

return [{ json: { chatId: $('Code (Parse Command)').item.json.chatId, text: txt } }];
```

   - **Telegram (Send Message)**
     - Operation: Send Message
     - Chat ID: `={{$json.chatId}}`
     - Text: `={{$json.text}}`

5. Ветка `search`:
   - **HTTP Request (SEARCH API)**
     - Method: `POST`
     - URL: `http://host.docker.internal:8001/api/search`
     - JSON Body:

```json
{
  "query": "={{$json.payload}}",
  "limit": 5
}
```

   - **Code (Format SEARCH text)**

```javascript
const data = $json;
const hits = data.hits || [];

if (!hits.length) {
  return [{ json: { chatId: $('Code (Parse Command)').item.json.chatId, text: 'Ничего не найдено.' } }];
}

let txt = `Найдено: ${hits.length}`;
hits.slice(0,5).forEach((h, i) => {
  const chunk = (h.text || '').slice(0, 220);
  txt += `\n\n${i+1}) ${h.book_title}, ${h.chapter || '—'}, #${h.chunk_index}\n${chunk}`;
});

return [{ json: { chatId: $('Code (Parse Command)').item.json.chatId, text: txt } }];
```

   - **Telegram (Send Message)**
     - Chat ID: `={{$json.chatId}}`
     - Text: `={{$json.text}}`

6. Ветка `help`:
   - **Telegram (Send Message)**
     - Chat ID: `={{$json.chatId}}`
     - Text:

```text
Команды:
/ask <вопрос>
/search <запрос>
```

## 5) Где именно «ставить код» в n8n

Код ставится в узлы типа **Code**:
- `Code (Parse Command)`
- `Code (Format ASK text)`
- `Code (Format SEARCH text)`

Открой узел → поле JavaScript → вставь соответствующий блок выше.

## 6) Как загружать книги

Пока проще загружать книги напрямую через API/локально:
- через `python bot.py` (если используешь Telegram-бот на Python),
- или POST на `/api/upload`.

Для полной загрузки файлов через n8n из Telegram можно добавить отдельную ветку с `Telegram getFile + HTTP download + multipart upload`.
