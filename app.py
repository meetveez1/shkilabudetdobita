from __future__ import annotations

from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

from smart_book_search.db import init_db, get_connection
from smart_book_search.ingestion import ingest_book
from smart_book_search.qa import answer_question
from smart_book_search.retrieval import search_fragments

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "books_storage"


@app.before_request
def setup_once() -> None:
    init_db()
    Path(app.config["UPLOAD_FOLDER"]).mkdir(exist_ok=True)


@app.get("/")
def home():
    conn = get_connection()
    books = conn.execute("SELECT title, created_at FROM books ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("index.html", books=books)


@app.post("/upload")
def upload_book():
    file = request.files.get("book")
    title = request.form.get("title", "").strip()

    if not file or not file.filename:
        return redirect(url_for("home"))

    path = Path(app.config["UPLOAD_FOLDER"]) / Path(file.filename).name
    file.save(path)
    ingest_book(path, title=title or None)

    return redirect(url_for("home"))


@app.post("/search")
def search():
    query = request.form.get("query", "").strip()
    if not query:
        return render_template("results.html", mode="search", query=query, hits=[], no_data=True)

    hits = search_fragments(query, limit=5)
    return render_template("results.html", mode="search", query=query, hits=hits, no_data=(len(hits) == 0))


@app.post("/ask")
def ask():
    question = request.form.get("question", "").strip()
    if not question:
        return render_template("results.html", mode="qa", query=question, result=None, no_data=True)

    result = answer_question(question, limit=5)
    return render_template("results.html", mode="qa", query=question, result=result, no_data=not result.found)


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
