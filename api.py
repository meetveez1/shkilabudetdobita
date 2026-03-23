from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, request

from smart_book_search.db import init_db
from smart_book_search.ingestion import ingest_book
from smart_book_search.qa import answer_question
from smart_book_search.retrieval import search_fragments

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "books_storage"


def _ensure_ready() -> None:
    init_db()
    Path(app.config["UPLOAD_FOLDER"]).mkdir(exist_ok=True)


@app.post("/api/upload")
def upload_api():
    _ensure_ready()
    file = request.files.get("book")
    title = request.form.get("title", "").strip() or None

    if not file or not file.filename:
        return jsonify({"ok": False, "error": "file 'book' is required"}), 400

    if not file.filename.lower().endswith(".txt"):
        return jsonify({"ok": False, "error": "only .txt files are supported"}), 400

    path = Path(app.config["UPLOAD_FOLDER"]) / Path(file.filename).name
    file.save(path)
    result = ingest_book(path, title=title)
    return jsonify({"ok": True, "book": result})


@app.post("/api/search")
def search_api():
    _ensure_ready()
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    limit = int(data.get("limit") or 5)

    if not query:
        return jsonify({"ok": False, "error": "field 'query' is required"}), 400

    hits = search_fragments(query, limit=max(1, min(limit, 10)))
    return jsonify(
        {
            "ok": True,
            "query": query,
            "hits": [
                {
                    "book_title": h.book_title,
                    "chapter": h.chapter,
                    "chunk_index": h.chunk_index,
                    "text": h.text,
                    "score": h.score,
                }
                for h in hits
            ],
        }
    )


@app.post("/api/ask")
def ask_api():
    _ensure_ready()
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    limit = int(data.get("limit") or 5)

    if not question:
        return jsonify({"ok": False, "error": "field 'question' is required"}), 400

    result = answer_question(question, limit=max(1, min(limit, 10)))
    return jsonify(
        {
            "ok": True,
            "question": question,
            "found": result.found,
            "answer": result.answer,
            "confidence": result.confidence,
            "citations": [
                {
                    "book_title": h.book_title,
                    "chapter": h.chapter,
                    "chunk_index": h.chunk_index,
                    "text": h.text,
                }
                for h in result.citations
            ],
        }
    )


if __name__ == "__main__":
    _ensure_ready()
    app.run(host="0.0.0.0", port=8001, debug=True)
