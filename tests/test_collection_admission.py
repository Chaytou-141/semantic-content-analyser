import csv
import io
import sqlite3

import pytest
from pydantic import ValidationError

from semantic_analyser.schemas import Article


def csv_text(articles):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=["id", "title", "body"])
    writer.writeheader()
    writer.writerows({key: a[key] for key in writer.fieldnames} for a in articles)
    return stream.getvalue()


def seed_review(client):
    assert client.post("/api/reviews", json={"source_id": "A01", "target_id": "A02",
                                          "decision": "useful", "note": "Preserve this decision"}).status_code == 200
    return client.get("/api/articles").json(), client.get("/api/reviews").json()


def assert_preserved(client, before):
    assert client.get("/api/articles").json() == before[0]
    assert client.get("/api/reviews").json() == before[1]


class DenseTokenizer:
    """Deterministic punctuation-dense limit fixture, not the real-model test."""
    def __call__(self, text, **kwargs):
        return {"offset_mapping": [(i, i + 1) for i, char in enumerate(text) if not char.isspace()]}

    def encode(self, text, add_special_tokens=False):
        return [c for c in text if not c.isspace()] + (["[CLS]", "[SEP]"] if add_special_tokens else [])

    def decode(self, tokens, **kwargs):
        return "".join(tokens)


@pytest.fixture
def dense_engine(client):
    engine = client.app.state.engine
    engine.load().tokenizer = DenseTokenizer()
    return engine


def dense_articles(extra_token=False):
    # 1,312 body tokens => 8 passages each; one more token creates passage 801.
    return [{"id": f"D{i}", "title": "Boundary title", "body": "x-" * 656 + ("x" if extra_token and i == 0 else "")}
            for i in range(100)]


def test_exact_passage_limit_accepts_and_next_token_rejects_atomically(client, dense_engine):
    accepted = dense_articles()
    assert client.post("/api/articles/import", json={"csv_text": csv_text(accepted)}).status_code == 200
    summary = client.app.state.collections.preflight(client.app.state.store.articles())[1]
    assert summary["passage_count"] == 800
    assert client.post("/api/reviews", json={"source_id": "D0", "target_id": "D1", "decision": "useful"}).status_code == 200
    before = client.get("/api/articles").json(), client.get("/api/reviews").json()
    response = client.post("/api/articles/import", json={"csv_text": csv_text(dense_articles(True))})
    assert response.status_code == 422
    assert "800 passages" in response.json()["detail"]
    assert_preserved(client, before)


def test_edit_cannot_push_valid_collection_over_passage_limit(client, dense_engine):
    assert client.post("/api/articles/import", json={"csv_text": csv_text(dense_articles())}).status_code == 200
    assert client.post("/api/reviews", json={"source_id": "D0", "target_id": "D1", "decision": "useful"}).status_code == 200
    before = client.get("/api/articles").json(), client.get("/api/reviews").json()
    article = next(a for a in before[0]["articles"] if a["id"] == "D0")
    article["body"] += "x"
    assert client.put("/api/articles/D0", json=article).status_code == 422
    # The saved snapshot was copied before mutating the request dictionary.
    article["body"] = article["body"][:-1]
    assert_preserved(client, before)


@pytest.mark.parametrize("size,accepted", [(249999, True), (250000, True), (250001, False)])
def test_character_boundary_before_tokenizer(client, monkeypatch, size, accepted):
    calls = []
    original_preflight = client.app.state.engine.preflight

    def tracked(articles):
        calls.append(len(articles))
        return original_preflight(articles)

    monkeypatch.setattr(client.app.state.engine, "preflight", tracked)
    rows = [{"id": f"C{i}", "title": "T", "body": "a" * 19999} for i in range(12)]
    rows.append({"id": "last", "title": "T", "body": "b" * (size - 240000 - 1)})
    before = seed_review(client)
    response = client.post("/api/articles/import", json={"csv_text": csv_text(rows)})
    assert response.status_code == (200 if accepted else 422)
    assert calls == ([13] if accepted else [])
    if not accepted:
        assert_preserved(client, before)


@pytest.mark.parametrize("count,accepted", [(0, False), (1, True), (100, True), (101, False)])
def test_article_count_boundary(client, count, accepted):
    before = seed_review(client)
    rows = [{"id": f"C{i}", "title": "Valid title", "body": "Useful article content"} for i in range(count)]
    response = client.post("/api/articles/import", json={"csv_text": csv_text(rows)})
    assert response.status_code == (200 if accepted else 422)
    if not accepted:
        assert_preserved(client, before)


@pytest.mark.parametrize("text", [
    "id,title,body\nx,one,first\nx,two,second",
    "id,title,body,existing_links\nx,title,body,missing",
    "id,title,body,url\nx,title,body,javascript:alert(1)",
    "id,title,body\nx,title,",
    "id,title,body\nx,valid title," + "a" * 20001,
    "id,title,body\nx,!,!!!",
    "id,title,body,extra\nx,title,body,unsupported",
])
def test_invalid_import_preserves_articles_and_reviews(client, text):
    before = seed_review(client)
    assert client.post("/api/articles/import", json={"csv_text": text}).status_code == 422
    assert_preserved(client, before)


def test_service_accepts_non_csv_selected_article_mappings(client):
    service = client.app.state.collections
    candidates, summary = service.preflight([{"id": "WEB1", "title": "Website selection", "body": "Original extracted article content"}])
    assert candidates[0].id == "WEB1"
    assert summary["article_count"] == summary["passage_count"] == 1
    assert service.replace(candidates) == 1
    assert client.get("/api/articles").json()["articles"][0]["id"] == "WEB1"


def test_service_revalidates_constructed_article_instances(client):
    before = seed_review(client)
    invalid = Article.model_construct(id="invalid id", title="Valid", body="Article body")
    with pytest.raises(ValidationError):
        client.app.state.collections.replace([invalid])
    assert_preserved(client, before)


@pytest.mark.parametrize("combined_tokens,accepted", [(256, True), (257, False)])
def test_combined_model_input_boundary(client, monkeypatch, combined_tokens, accepted):
    before = seed_review(client)
    tokenizer = client.app.state.engine.load().tokenizer
    original_encode = tokenizer.encode

    def retokenized(text, add_special_tokens=False):
        if add_special_tokens:
            return list(range(combined_tokens))
        return original_encode(text, add_special_tokens=False)

    # Simulate a tokenizer whose reconstructed title/body expands at a boundary.
    monkeypatch.setattr(tokenizer, "encode", retokenized)
    response = client.post("/api/articles/import", json={"csv_text": "id,title,body\nx,Valid title,Valid article body"})
    assert response.status_code == (200 if accepted else 422)
    if not accepted:
        assert "256 model tokens" in response.json()["detail"]
        assert_preserved(client, before)


def test_preflight_does_not_encode_or_replace_active_index(client, monkeypatch):
    engine = client.app.state.engine
    collection = client.app.state.store.articles()
    engine.search(collection, "display fridge", "embeddings", 5, 0)
    fingerprint, chunks, vectors = engine.cache_key, engine.chunks, engine.embeddings

    def unexpected_encode(*args, **kwargs):
        raise AssertionError("Admission must not encode embeddings")

    monkeypatch.setattr(engine.model, "encode", unexpected_encode)
    service = client.app.state.collections
    service.preflight([{"id": "new", "title": "New title", "body": "Some valid new content"}])
    with pytest.raises(ValueError):
        service.preflight([{"id": "bad", "title": "!", "body": "!!!"}])
    assert engine.cache_key == fingerprint
    assert engine.chunks is chunks
    assert engine.embeddings is vectors


@pytest.mark.parametrize("error", [OSError("private model path"), RuntimeError("private runtime error")])
@pytest.mark.parametrize("operation", ["import", "reset", "edit"])
def test_unavailable_preflight_fails_closed(client, monkeypatch, error, operation):
    before = seed_review(client)

    def unavailable(articles):
        raise error

    monkeypatch.setattr(client.app.state.engine, "preflight", unavailable)
    if operation == "edit":
        response = client.put("/api/articles/A01", json=before[0]["articles"][0])
    elif operation == "reset":
        response = client.post("/api/articles/reset", json={})
    else:
        response = client.post("/api/articles/import", json={"csv_text": "id,title,body\nx,title,new content"})
    assert response.status_code == 503
    assert "No changes were saved" in response.json()["detail"]
    assert "private" not in response.text
    assert_preserved(client, before)


def test_database_failure_rolls_back_replacement_and_review_deletion(client):
    before = seed_review(client)
    store = client.app.state.store
    with store.connect() as connection:
        connection.execute("""CREATE TRIGGER fail_review_delete BEFORE DELETE ON reviews
            BEGIN SELECT RAISE(ABORT, 'injected transaction failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="injected transaction failure"):
        client.app.state.collections.replace([{"id": "new", "title": "New article", "body": "Valid replacement text"}])
    assert_preserved(client, before)


def test_database_failure_rolls_back_edit_and_review_deletion(client):
    before = seed_review(client)
    store = client.app.state.store
    with store.connect() as connection:
        connection.execute("""CREATE TRIGGER fail_review_delete BEFORE DELETE ON reviews
            BEGIN SELECT RAISE(ABORT, 'injected edit failure'); END""")
    article = store.articles()[0].model_copy(update={"title": "Valid edited article"})
    with pytest.raises(sqlite3.IntegrityError, match="injected edit failure"):
        client.app.state.collections.save_article(article)
    assert_preserved(client, before)


def test_valid_replacement_clears_reviews_and_remains_analysable(client):
    seed_review(client)
    response = client.post("/api/articles/import", json={"csv_text": "id,title,body\nx,Coffee workflow,Arrange the coffee preparation workspace"})
    assert response.status_code == 200
    assert client.get("/api/reviews").json()["reviews"] == []
    for method in ["embeddings", "tfidf"]:
        assert client.post("/api/search", json={"query": "coffee workspace", "method": method}).status_code == 200
