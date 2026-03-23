from __future__ import annotations

import re
from dataclasses import dataclass

from smart_book_search.db import get_connection


@dataclass
class SearchHit:
    chunk_id: int
    book_title: str
    chapter: str | None
    chunk_index: int
    text: str
    score: float


STOP_WORDS = {"где", "что", "когда", "как", "найди", "про", "это", "этот", "или", "для", "есть"}


def _stem(token: str) -> str:
    token = token.lower().replace("ё", "е")
    for suffix in (
        "иями",
        "ями",
        "ами",
        "его",
        "ого",
        "ему",
        "ому",
        "иях",
        "ии",
        "ий",
        "ый",
        "ой",
        "ая",
        "яя",
        "ое",
        "ее",
        "ых",
        "их",
        "ам",
        "ям",
        "ах",
        "ях",
        "ом",
        "ем",
        "ов",
        "ев",
        "а",
        "я",
        "у",
        "ю",
        "е",
        "ы",
        "и",
    ):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _query_terms(text: str) -> list[str]:
    words = re.findall(r"[\wа-яА-ЯёЁ]{2,}", text.lower())
    words = [w for w in words if w not in STOP_WORDS]
    stems = [_stem(w) for w in words]
    return [s for s in dict.fromkeys(stems) if len(s) >= 3]


def _sanitize_query(text: str) -> str:
    stems = _query_terms(text)
    if not stems:
        return text.strip()
    terms = [f"{w}*" for w in stems]
    return " OR ".join(terms)


def _fallback_search(query: str, limit: int) -> list[SearchHit]:
    q_terms = set(_query_terms(query))
    if not q_terms:
        return []

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT c.id, b.title, c.chapter, c.chunk_index, c.text
        FROM chunks c
        JOIN books b ON b.id = c.book_id
        """
    ).fetchall()
    conn.close()

    scored: list[SearchHit] = []
    for row in rows:
        chunk_terms = {_stem(t) for t in re.findall(r"[\wа-яА-ЯёЁ]{2,}", row["text"].lower())}
        overlap = len(q_terms & chunk_terms)
        if overlap == 0:
            continue
        score = overlap / (len(q_terms) + 0.5)
        scored.append(
            SearchHit(
                chunk_id=row["id"],
                book_title=row["title"],
                chapter=row["chapter"],
                chunk_index=row["chunk_index"],
                text=row["text"],
                score=score,
            )
        )

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:limit]


def search_fragments(query: str, limit: int = 5) -> list[SearchHit]:
    q = _sanitize_query(query)
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT c.id, b.title, c.chapter, c.chunk_index, c.text, bm25(chunks_fts) AS rank
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.rowid
        JOIN books b ON b.id = c.book_id
        WHERE chunks_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (q, limit),
    ).fetchall()
    conn.close()

    hits = [
        SearchHit(
            chunk_id=row["id"],
            book_title=row["title"],
            chapter=row["chapter"],
            chunk_index=row["chunk_index"],
            text=row["text"],
            score=float(-row["rank"]),
        )
        for row in rows
    ]

    if hits:
        return hits
    return _fallback_search(query, limit)
