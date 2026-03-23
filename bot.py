from __future__ import annotations

import logging
import os
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from smart_book_search.db import init_db
from smart_book_search.ingestion import ingest_book
from smart_book_search.qa import answer_question
from smart_book_search.retrieval import search_fragments

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    level=logging.INFO,
)

UPLOAD_DIR = Path("books_storage")
AWAITING_BOOK_KEY = "awaiting_book"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = (
        "Привет! Я бот для умного поиска по книгам (.txt).\n\n"
        "Команды:\n"
        "/addbook — загрузить книгу\n"
        "/search <запрос> — найти фрагменты\n"
        "/ask <вопрос> — ответить по текстам\n"
        "/help — подсказка"
    )
    await update.message.reply_text(msg)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, context)


async def addbook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[AWAITING_BOOK_KEY] = True
    await update.message.reply_text(
        "Отправьте .txt файл следующим сообщением. "
        "Можно добавить подпись к файлу — она будет использована как название книги."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get(AWAITING_BOOK_KEY):
        await update.message.reply_text("Чтобы загрузить книгу, сначала отправьте /addbook.")
        return

    document = update.message.document
    if not document:
        await update.message.reply_text("Не вижу файла в сообщении.")
        return

    if not document.file_name.lower().endswith(".txt"):
        await update.message.reply_text("Поддерживаются только файлы .txt")
        return

    UPLOAD_DIR.mkdir(exist_ok=True)
    safe_name = Path(document.file_name).name
    out_path = UPLOAD_DIR / safe_name

    tg_file = await context.bot.get_file(document.file_id)
    await tg_file.download_to_drive(custom_path=str(out_path))

    custom_title = (update.message.caption or "").strip() or None
    result = ingest_book(out_path, title=custom_title)
    context.user_data[AWAITING_BOOK_KEY] = False

    await update.message.reply_text(
        f"Книга загружена: {result['title']}\n"
        f"Фрагментов в индексе: {result['chunks']}"
    )


async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Использование: /search <ваш запрос>")
        return

    hits = search_fragments(query, limit=5)
    if not hits:
        await update.message.reply_text("Релевантных фрагментов не найдено.")
        return

    parts: list[str] = [f"Найдено фрагментов: {len(hits)}"]
    for i, hit in enumerate(hits, start=1):
        excerpt = hit.text[:450] + ("..." if len(hit.text) > 450 else "")
        parts.append(
            f"\n{i}) Книга: {hit.book_title}\n"
            f"Место: {hit.chapter or '—'}, фрагмент #{hit.chunk_index}\n"
            f"Текст: {excerpt}"
        )

    await update.message.reply_text("\n".join(parts))


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text("Использование: /ask <ваш вопрос>")
        return

    result = answer_question(question, limit=5)
    if not result.found:
        await update.message.reply_text(result.answer)
        return

    citations = []
    for i, hit in enumerate(result.citations, start=1):
        excerpt = hit.text[:280] + ("..." if len(hit.text) > 280 else "")
        citations.append(
            f"{i}) {hit.book_title}, {hit.chapter or '—'}, фрагмент #{hit.chunk_index}\n"
            f"{excerpt}"
        )

    text = (
        f"Ответ:\n{result.answer}\n\n"
        f"Уверенность: {result.confidence:.2f}\n\n"
        f"Цитаты-основания:\n" + "\n\n".join(citations)
    )
    await update.message.reply_text(text)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Нужна переменная окружения TELEGRAM_BOT_TOKEN")

    init_db()
    UPLOAD_DIR.mkdir(exist_ok=True)

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("addbook", addbook))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
