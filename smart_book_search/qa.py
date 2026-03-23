from __future__ import annotations

import re
from dataclasses import dataclass

from smart_book_search.retrieval import SearchHit, search_fragments


@dataclass
class AnswerResult:
    answer: str
    citations: list[SearchHit]
    confidence: float
    found: bool


STOP_WORDS = {
    "что",
    "кто",
    "где",
    "когда",
    "почему",
    "как",
    "ли",
    "в",
    "на",
    "и",
    "по",
    "о",
    "об",
    "про",
    "а",
    "но",
    "или",
    "с",
    "у",
    "к",
    "из",
    "это",
    "этого",
}


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


def _tokens(text: str) -> set[str]:
    terms = re.findall(r"[\wа-яА-ЯёЁ]{2,}", text.lower())
    return {_stem(t) for t in terms if t not in STOP_WORDS}


def _best_sentences(question: str, hits: list[SearchHit], top_k: int = 3) -> list[str]:
    q_tokens = _tokens(question)
    scored: list[tuple[float, str]] = []
    for hit in hits:
        sentences = re.split(r"(?<=[.!?])\s+", hit.text)
        for s in sentences:
            s_clean = s.strip()
            if len(s_clean) < 30:
                continue
            sent_tokens = _tokens(s_clean)
            overlap = len(sent_tokens & q_tokens)
            if overlap == 0:
                continue
            score = overlap / (len(sent_tokens) + 1)
            scored.append((score, s_clean))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in scored[:top_k]]


def answer_question(question: str, limit: int = 5) -> AnswerResult:
    hits = search_fragments(question, limit=limit)

    if not hits:
        return AnswerResult(
            answer="В загруженных книгах не удалось найти релевантные фрагменты для ответа.",
            citations=[],
            confidence=0.0,
            found=False,
        )

    best_sentences = _best_sentences(question, hits)
    if not best_sentences:
        return AnswerResult(
            answer="Найдены только косвенные упоминания. Надёжного ответа в загруженных книгах нет.",
            citations=hits[:3],
            confidence=0.25,
            found=False,
        )

    answer = " ".join(best_sentences)
    confidence = min(0.95, 0.4 + 0.15 * len(best_sentences))

    return AnswerResult(
        answer=answer,
        citations=hits[:3],
        confidence=confidence,
        found=True,
    )
