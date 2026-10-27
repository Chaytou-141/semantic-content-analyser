import csv
import io

import pytest
from fastapi.testclient import TestClient

from semantic_analyser.api import create_app
from semantic_analyser.config import Settings
from semantic_analyser.schemas import Article


def test_demo_and_interface(client):
    assert client.get("/").status_code == 200
    assert "Semantic Content Analyser" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200
    articles = client.get("/api/articles").json()["articles"]
    assert len(articles) == 21
    assert next(a for a in articles if a["id"] == "A01")["existing_links"] == ["A04"]
    assert "frame-ancestors 'none'" in client.get("/").headers["content-security-policy"]


def test_comparison_returns_ranked_unique_articles(client):
    response = client.post("/api/search", json={"query": "cleaning refrigerated display cabinet", "method": "compare", "top_k": 5})
    assert response.status_code == 200
    for results in response.json()["results"].values():
        assert len({row["id"] for row in results}) == len(results)
        assert all(row["passage"] for row in results)
        assert [row["score"] for row in results] == sorted([row["score"] for row in results], reverse=True)


def test_link_exclusions_and_evidence(client):
    response = client.post("/api/links", json={"source_id": "A01", "method": "compare", "top_k": 20})
    assert response.status_code == 200
    source = client.get("/api/articles").json()["articles"][0]
    for group in response.json()["results"].values():
        assert not {row["id"] for row in group["results"]} & {"A01", "A04", "A20"}
        assert group["results"]
        for row in group["results"]:
            assert row["source_passage"] == source["body"][row["source_start"]:row["source_end"]]
            assert row["review_required"] is True


def test_passage_window_preserves_offsets_and_tail(engine):
    article = Article(id="long", title="Long title", body=" ".join(f"word{i}" for i in range(600)))
    chunks = engine.passages(article)
    assert len(chunks) > 1
    assert "word599" in chunks[-1]["text"]
    for chunk in chunks:
        assert chunk["text"] == article.body[chunk["start"]:chunk["end"]]
        assert len(engine.model.tokenizer.encode(chunk["model_text"], add_special_tokens=True)) <= 256


def test_invalid_import_is_atomic(client):
    before = client.get("/api/articles").json()
    for data in ["id,title,body\nx,one,first\nx,two,second", "wrong,columns\na,b", "id,title,body,url\nx,x,text,javascript:alert(1)"]:
        assert client.post("/api/articles/import", json={"csv_text": data}).status_code == 422
        assert client.get("/api/articles").json() == before


def test_review_persists_and_edit_invalidates_it(client):
    review = {"source_id": "A01", "target_id": "A02", "decision": "useful", "note": "Useful for cabinet layout"}
    assert client.post("/api/reviews", json=review).status_code == 200
    assert client.get("/api/reviews").json()["reviews"][0]["decision"] == "useful"
    article = client.get("/api/articles").json()["articles"][0]
    article["title"] = "Updated display fridge guide"
    assert client.put("/api/articles/A01", json=article).status_code == 200
    assert client.get("/api/reviews").json()["reviews"] == []


def test_import_export_and_reset(client):
    data = "id,title,body,topic,url,eligible,existing_links\nx,One article,Useful article about coffee,coffee,https://example.com/x,true,"
    assert client.post("/api/articles/import", json={"csv_text": data}).json()["count"] == 1
    exported = list(csv.DictReader(io.StringIO(client.get("/api/articles/export").text)))
    assert exported[0]["id"] == "x"
    assert client.post("/api/articles/reset", json={}).json()["count"] == 21


def test_overlap_pairs_are_distinct_and_bounded(client):
    data = client.post("/api/overlaps", json={"threshold": 0, "limit": 10}).json()
    pairs = [tuple(sorted((pair["left"]["id"], pair["right"]["id"]))) for pair in data["pairs"]]
    assert len(pairs) == len(set(pairs)) == 10
    assert all(left != right for left, right in pairs)
    assert all(pair["review_required"] for pair in data["pairs"])


def test_missing_articles_and_query_limits(client):
    assert client.post("/api/links", json={"source_id": "missing"}).status_code == 404
    assert client.post("/api/search", json={"query": "  "}).status_code == 422
    assert client.post("/api/search", json={"query": "coffee", "top_k": 101}).status_code == 422
    assert client.post("/api/search", json={"query": "word " * 270}).status_code == 422


def test_evaluation_is_historical_not_current_corpus(client):
    result = client.get("/api/evaluation").json()
    assert result["historical"] is True
    assert result["label_source"] == "assistant"
    assert len(result["metrics"]) == 6
    assert len(result["queries"]) == 5


def test_password_session_and_csrf_header(tmp_path, engine):
    settings = Settings(database_path=tmp_path / "secure.sqlite3", password="correct-password", secret="x" * 40, production=False)
    with TestClient(create_app(settings, engine)) as secure:
        assert secure.get("/api/articles").status_code == 401
        assert secure.post("/api/login", json={"password": "correct-password"}).status_code == 403
        headers = {"X-Workspace-Request": "true"}
        assert secure.post("/api/login", json={"password": "wrong"}, headers=headers).status_code == 401
        login = secure.post("/api/login", json={"password": "correct-password"}, headers=headers)
        assert login.status_code == 200
        assert "HttpOnly" in login.headers["set-cookie"]
        assert secure.get("/api/articles").status_code == 200
        assert secure.post("/api/logout", json={}, headers=headers).status_code == 200
        assert secure.get("/api/articles").status_code == 401


def test_production_refuses_missing_secrets(tmp_path):
    with pytest.raises(ValueError, match="Production requires"):
        create_app(Settings(database_path=tmp_path / "prod.sqlite3", password="", secret="", production=True))


def test_production_cookie_is_secure(tmp_path, engine):
    settings = Settings(database_path=tmp_path / "prod.sqlite3", password="production-password",
                        secret="s" * 40, production=True)
    with TestClient(create_app(settings, engine), base_url="https://testserver") as secure:
        login = secure.post("/api/login", json={"password": "production-password"},
                            headers={"X-Workspace-Request": "true"})
        assert login.status_code == 200
        assert "Secure" in login.headers["set-cookie"]
        assert "SameSite=strict" in login.headers["set-cookie"]
        assert secure.get("/api/articles").status_code == 200


def test_empty_keyword_match_does_not_invent_results(client):
    response = client.post("/api/search", json={"query": "qzxvnonexistentword", "method": "tfidf"})
    assert response.status_code == 200
    assert response.json()["results"]["tfidf"] == []


def test_request_size_limit(client):
    response = client.post("/api/articles/import", content=b"x" * 2000001,
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 413
