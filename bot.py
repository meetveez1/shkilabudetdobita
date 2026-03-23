from __future__ import annotations

import logging
import os
from pathlib import Path

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
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
MODE_KEY = "mode"

MENU_ADD_BOOK = "📚 Загрузить книгу"
MENU_SEARCH = "🔎 Поиск фрагментов"
MENU_ASK = "❓ Задать вопрос"
MENU_HELP = "ℹ️ Помощь"


def main_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(MENU_ADD_BOOK), KeyboardButton(MENU_SEARCH)],
        [KeyboardButton(MENU_ASK), KeyboardButton(MENU_HELP)],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def show_start_message(update: Update) -> None:
    msg = (
        "Привет! Я бот для умного поиска по книгам (.txt).\n\n"
        "Выбери действие кнопкой в меню ниже или используй команды:\n"
        "/addbook — загрузить книгу\n"
        "/search <запрос> — найти фрагменты\n"
        "/ask <вопрос> — ответить по текстам"
    )
    await update.message.reply_text(msg, reply_markup=main_menu())


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[MODE_KEY] = None
    await show_start_message(update)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_start_message(update)


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Открываю меню 👇", reply_markup=main_menu())


async def addbook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[AWAITING_BOOK_KEY] = True
    context.user_data[MODE_KEY] = None
    await update.message.reply_text(
        "Отправьте .txt файл следующим сообщением. "
        "Можно добавить подпись к файлу — она будет использована как название книги.",
        reply_markup=main_menu(),
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get(AWAITING_BOOK_KEY):
        await update.message.reply_text("Чтобы загрузить книгу, сначала отправьте /addbook или нажмите кнопку «📚 Загрузить книгу».")
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
        f"✅ Книга загружена: {result['title']}\n"
        f"Фрагментов в индексе: {result['chunks']}",
        reply_markup=main_menu(),
    )


async def _run_search(update: Update, query: str) -> None:
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

    await update.message.reply_text("\n".join(parts), reply_markup=main_menu())


async def _run_ask(update: Update, question: str) -> None:
    result = answer_question(question, limit=5)
    if not result.found:
        await update.message.reply_text(result.answer, reply_markup=main_menu())
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
    await update.message.reply_text(text, reply_markup=main_menu())


async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip()
    if not query:
        context.user_data[MODE_KEY] = "search"
        await update.message.reply_text("Введите поисковый запрос следующим сообщением.", reply_markup=main_menu())
        return

    context.user_data[MODE_KEY] = None
    await _run_search(update, query)


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = " ".join(context.args).strip()
    if not question:
        context.user_data[MODE_KEY] = "ask"
        await update.message.reply_text("Введите вопрос следующим сообщением.", reply_markup=main_menu())
        return

    context.user_data[MODE_KEY] = None
    await _run_ask(update, question)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()

    if text == MENU_ADD_BOOK:
        await addbook(update, context)
        return

    if text == MENU_SEARCH:
        context.user_data[MODE_KEY] = "search"
        await update.message.reply_text("Напишите, что найти в книгах.", reply_markup=main_menu())
        return

    if text == MENU_ASK:
        context.user_data[MODE_KEY] = "ask"
        await update.message.reply_text("Напишите ваш вопрос по книгам.", reply_markup=main_menu())
        return

    if text == MENU_HELP:
        await show_start_message(update)
        return

    mode = context.user_data.get(MODE_KEY)
    if mode == "search":
        context.user_data[MODE_KEY] = None
        await _run_search(update, text)
        return

    if mode == "ask":
        context.user_data[MODE_KEY] = None
        await _run_ask(update, text)
        return

    await update.message.reply_text(
        "Используйте кнопки меню или команды /search, /ask, /addbook.",
        reply_markup=main_menu(),
    )


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Нужна переменная окружения TELEGRAM_BOT_TOKEN")

    init_db()
    UPLOAD_DIR.mkdir(exist_ok=True)

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(CommandHandler("addbook", addbook))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
