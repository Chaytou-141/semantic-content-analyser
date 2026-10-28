import csv
import io
import json
import sqlite3
import secrets
from contextlib import contextmanager
from pathlib import Path

from .config import ROOT
from .schemas import Article

MAX_ARTICLES = 100
MAX_TOTAL_CHARACTERS = 250000


def validate_collection(articles):
    if not 1 <= len(articles) <= MAX_ARTICLES:
        raise ValueError(f"A collection must contain between 1 and {MAX_ARTICLES} articles.")
    ids = [a.id for a in articles]
    if len(set(ids)) != len(ids):
        raise ValueError("Article IDs must be unique. No changes were saved.")
    if sum(len(a.title) + len(a.body) for a in articles) > MAX_TOTAL_CHARACTERS:
        raise ValueError("The collection exceeds the 250,000-character limit.")
    unknown = {link for a in articles for link in a.existing_links} - set(ids)
    if unknown:
        raise ValueError("Existing links reference unknown article IDs: " + ", ".join(sorted(unknown)))
    return articles


def parse_csv(text):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames or not {"id", "title", "body"} <= set(reader.fieldnames):
        raise ValueError("CSV requires id, title and body columns. Optional: topic, url, eligible, existing_links.")
    allowed = {"id", "title", "body", "topic", "url", "eligible", "existing_links"}
    if len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) - allowed:
        raise ValueError("CSV has duplicate or unsupported columns.")
    articles = []
    for number, row in enumerate(reader, start=2):
        if len(articles) >= MAX_ARTICLES:
            raise ValueError(f"CSV exceeds the {MAX_ARTICLES}-article limit.")
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"CSV row {number} has an unexpected number of fields.")
        flag = row.get("eligible", "true").strip().lower() or "true"
        if flag not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError(f"CSV row {number}: eligible must be true or false.")
        row["eligible"] = flag in {"true", "1", "yes"}
        row["existing_links"] = [part.strip() for part in row.get("existing_links", "").split(";") if part.strip()]
        articles.append(Article.model_validate(row))
    return validate_collection(articles)


def demo_articles():
    articles = parse_csv((ROOT / "data/synthetic_articles.csv").read_text(encoding="utf-8"))
    for article in articles:
        article.url = f"https://example.com/articles/{article.id.lower()}"
        if article.id == "A01":
            article.existing_links = ["A04"]
        if article.id == "A20":
            article.eligible = False
    return articles


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS articles (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reviews (
                    source_id TEXT NOT NULL, target_id TEXT NOT NULL, decision TEXT NOT NULL,
                    note TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (source_id, target_id)
                );
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            if not connection.execute("SELECT 1 FROM metadata WHERE key='initialised'").fetchone():
                connection.executemany("INSERT INTO articles VALUES (?, ?)",
                                       [(a.id, a.model_dump_json()) for a in demo_articles()])
                connection.execute("INSERT INTO metadata VALUES ('initialised', 'true')")
            connection.execute("INSERT OR IGNORE INTO metadata VALUES ('revision', ?)", (secrets.token_hex(16),))

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=1)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def revision(self):
        with self.connect() as connection:
            return connection.execute("SELECT value FROM metadata WHERE key='revision'").fetchone()[0]

    @staticmethod
    def bump_revision(connection):
        connection.execute("UPDATE metadata SET value=? WHERE key='revision'", (secrets.token_hex(16),))

    def articles(self):
        with self.connect() as connection:
            return [Article.model_validate_json(row[0]) for row in connection.execute("SELECT payload FROM articles ORDER BY id")]

    def replace(self, articles, before_commit=None):
        validate_collection(articles)
        with self.connect() as connection:
            connection.execute("DELETE FROM articles")
            connection.executemany("INSERT INTO articles VALUES (?, ?)", [(a.id, a.model_dump_json()) for a in articles])
            connection.execute("DELETE FROM reviews")
            self.bump_revision(connection)
            if before_commit:
                before_commit()
        return len(articles)

    def save_article(self, article, before_commit=None):
        with self.connect() as connection:
            collection = [Article.model_validate_json(row[0]) for row in connection.execute("SELECT payload FROM articles")]
            if article.id not in {a.id for a in collection}:
                raise KeyError(article.id)
            validate_collection([article if a.id == article.id else a for a in collection])
            connection.execute("UPDATE articles SET payload=? WHERE id=?", (article.model_dump_json(), article.id))
            connection.execute("DELETE FROM reviews WHERE source_id=? OR target_id=?", (article.id, article.id))
            self.bump_revision(connection)
            if before_commit:
                before_commit()

    def reviews(self):
        with self.connect() as connection:
            connection.row_factory = sqlite3.Row
            return [dict(row) for row in connection.execute("SELECT * FROM reviews ORDER BY updated_at DESC")]

    def review(self, review, before_commit=None):
        with self.connect() as connection:
            ids = {row[0] for row in connection.execute("SELECT id FROM articles")}
            if review.source_id not in ids or review.target_id not in ids:
                raise KeyError("Article not found")
            connection.execute("""INSERT INTO reviews (source_id,target_id,decision,note) VALUES (?,?,?,?)
                ON CONFLICT(source_id,target_id) DO UPDATE SET decision=excluded.decision,
                note=excluded.note,updated_at=CURRENT_TIMESTAMP""",
                (review.source_id, review.target_id, review.decision, review.note))
            if before_commit:
                before_commit()

    def export(self):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(Article.model_fields))
        writer.writeheader()
        for article in self.articles():
            row = article.model_dump()
            row["existing_links"] = ";".join(row["existing_links"])
            # Avoid spreadsheet formulas when opening a downloaded CSV.
            for key, value in row.items():
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                    row[key] = "'" + value
            writer.writerow(row)
        return stream.getvalue()
