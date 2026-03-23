from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from smart_book_search.db import get_connection

CHUNK_SIZE = 900
OVERLAP = 180


CHAPTER_PATTERNS = [
    re.compile(r"^\s*(глава|chapter)\s+([\w\-]+)", re.IGNORECASE),
    re.compile(r"^\s*(часть|part)\s+([\w\-]+)", re.IGNORECASE),
]


def detect_chapter(line: str) -> str | None:
    for pattern in CHAPTER_PATTERNS:
        m = pattern.match(line)
        if m:
            return m.group(0).strip()
    return None


def chunk_text(text: str) -> Iterable[tuple[str | None, str]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [p.strip() for p in normalized.split("\n\n") if p.strip()]

    current_chapter: str | None = None
    stream = []
    for p in paragraphs:
        maybe_chapter = detect_chapter(p.splitlines()[0])
        if maybe_chapter:
            current_chapter = maybe_chapter
        stream.append((current_chapter, p))

    buffer = ""
    buffer_chapter: str | None = None
    for chapter, paragraph in stream:
        if buffer and len(buffer) + len(paragraph) + 2 > CHUNK_SIZE:
            yield buffer_chapter, buffer.strip()
            tail = buffer[-OVERLAP:]
            buffer = f"{tail}\n\n{paragraph}"
            buffer_chapter = chapter
        else:
            if not buffer:
                buffer_chapter = chapter
            buffer = f"{buffer}\n\n{paragraph}".strip()

    if buffer:
        yield buffer_chapter, buffer.strip()


def ingest_book(file_path: Path, title: str | None = None) -> dict:
    if file_path.suffix.lower() != ".txt":
        raise ValueError("Поддерживаются только .txt файлы")

    text = file_path.read_text(encoding="utf-8")
    book_title = title or file_path.stem

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO books(title, file_path) VALUES (?, ?)",
        (book_title, str(file_path.resolve())),
    )
    book_id = cur.execute("SELECT id FROM books WHERE title = ?", (book_title,)).fetchone()[0]

    cur.execute("DELETE FROM chunks WHERE book_id = ?", (book_id,))

    count = 0
    for idx, (chapter, chunk) in enumerate(chunk_text(text)):
        cur.execute(
            "INSERT INTO chunks(book_id, chunk_index, chapter, text) VALUES (?, ?, ?, ?)",
            (book_id, idx, chapter, chunk),
        )
        count += 1

    conn.commit()
    conn.close()

    return {"title": book_title, "chunks": count, "path": str(file_path)}
