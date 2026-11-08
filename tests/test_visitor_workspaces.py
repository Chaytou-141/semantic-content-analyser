import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from semantic_analyser.api import create_app
from semantic_analyser.config import Settings
from semantic_analyser.execution import BoundedExecutor
from semantic_analyser.workspaces import COOKIE, WorkspaceManager


@pytest.fixture
def visitor_settings(tmp_path):
    return Settings(database_path=tmp_path / "untouched-local.sqlite3", workspace_mode="visitor",
                    visitor_root=tmp_path / "visitors", password="", secret="test-only-ownership-key-" * 2,
                    production=False, preload_model=False, cleanup_interval_seconds=60)


@pytest.fixture
def visitors(visitor_settings, engine):
    app = create_app(visitor_settings, engine)
    with TestClient(app, headers={"X-Workspace-Request": "true"}) as client:
        yield app, client


def start(client):
    client.cookies.clear()
    response = client.get("/api/session")
    assert response.status_code == 200
    token = client.cookies.get(COOKIE)
    revision = client.get("/api/articles").json()["collection_revision"]
    return token, revision


def headers(token, revision=None):
    value = {"Cookie": f"{COOKIE}={token}", "X-Workspace-Request": "true"}
    if revision:
        value["If-Match"] = revision
    return value


def imported(client, token, revision, aid):
    response = client.post("/api/articles/import", headers=headers(token, revision),
                           json={"csv_text": f"id,title,body\n{aid},Coffee layout,Arrange a useful coffee preparation station"})
    assert response.status_code == 200, response.text
    return response.json()["collection_revision"]


def test_two_visitors_are_isolated_for_read_write_export_reviews_and_delete(visitors, visitor_settings):
    app, client = visitors
    a, ar = start(client)
    b, br = start(client)
    assert a != b
    ar = imported(client, a, ar, "ALICE")
    assert client.get("/api/articles", headers=headers(b)).json()["articles"][0]["id"] == "A01"
    assert "ALICE" not in client.get("/api/articles/export", headers=headers(b)).text
    assert client.put("/api/articles/ALICE", headers=headers(b, br), json={"id": "ALICE", "title": "Attack", "body": "Change another visitor"}).status_code == 404
    assert client.post("/api/reviews", headers=headers(b, br), json={"source_id": "ALICE", "target_id": "A02", "decision": "useful"}).status_code == 404
    assert client.post("/api/reviews", headers=headers(b, br), json={"source_id": "A01", "target_id": "A02", "decision": "useful", "note": "Private B"}).status_code == 200
    assert client.get("/api/reviews", headers=headers(a)).json()["reviews"] == []
    assert client.post("/api/reviews", headers=headers(a, ar), json={"source_id": "A01", "target_id": "A02", "decision": "not_useful", "note": "Overwrite B"}).status_code == 404
    assert client.get("/api/reviews", headers=headers(b)).json()["reviews"][0]["note"] == "Private B"
    assert client.get("/api/articles?workspace_id=ALICE", headers=headers(b)).json()["articles"][0]["id"] == "A01"
    assert client.delete("/api/workspace?workspace_id=ALICE", headers=headers(b, br)).status_code == 200
    assert client.get("/api/articles", headers=headers(a)).json()["articles"][0]["id"] == "ALICE"
    expired = client.get("/api/articles", headers=headers(b))
    assert expired.status_code == 410 and expired.headers["cache-control"] == "no-store"
    assert not visitor_settings.database_path.exists()


def test_unsigned_tampered_and_missing_cookies_do_not_authorize(visitors):
    app, client = visitors
    token, revision = start(client)
    identifier = next(iter(app.state.workspaces.entries))
    for invalid in [identifier, token + "tampered", "../workspace.sqlite3", app.state.workspaces.signer.dumps({"id": "../escape"}), app.state.workspaces.signer.dumps(["invalid"] )]:
        assert client.get("/api/articles", headers=headers(invalid)).status_code == 401
    client.cookies.clear()
    assert client.get("/api/articles").status_code == 401
    assert len(app.state.workspaces.entries) == 1


def test_production_visitor_cookie_is_signed_secure_and_not_an_auth_password(visitor_settings, engine):
    app = create_app(replace(visitor_settings, production=True), engine)
    with TestClient(app, base_url="https://testserver", headers={"X-Workspace-Request": "true"}) as client:
        response = client.get("/api/session")
        assert response.status_code == 200
        assert all(flag in response.headers["set-cookie"] for flag in ["Secure", "HttpOnly", "SameSite=strict"])
        assert "password" not in response.headers["set-cookie"]


def test_revision_required_and_stale_operations_rejected(visitors):
    app, client = visitors
    token, old = start(client)
    query = {"query": "coffee", "method": "tfidf"}
    assert client.post("/api/search", headers=headers(token), json=query).status_code == 428
    assert client.post("/api/search", headers=headers(token, old), json=query).json()["collection_revision"] == old
    new = imported(client, token, old, "NEW")
    assert new != old
    operations = [
        ("post", "/api/search", query),
        ("post", "/api/articles/reset", {}),
        ("post", "/api/articles/import", {"csv_text": "id,title,body\nx,title,body text"}),
        ("put", "/api/articles/NEW", {"id": "NEW", "title": "Changed", "body": "Body text"}),
        ("post", "/api/reviews", {"source_id": "NEW", "target_id": "A02", "decision": "useful"}),
    ]
    for method, path, body in operations:
        assert getattr(client, method)(path, headers=headers(token, old), json=body).status_code == 409
    assert client.delete("/api/workspace", headers=headers(token, old)).status_code == 409
    assert client.get("/api/articles", headers=headers(token)).json()["collection_revision"] == new


def test_parallel_same_revision_imports_have_one_winner(visitors):
    app, client = visitors
    token, revision = start(client)

    def change(aid):
        return client.post("/api/articles/import", headers=headers(token, revision),
                           json={"csv_text": f"id,title,body\n{aid},Title,Useful content"}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(change, ["ONE", "TWO"]))
    assert sorted(statuses) == [200, 409]


def test_parallel_distinct_imports_and_analysis_keep_indexes_separate(visitors):
    app, client = visitors
    a, ar = start(client)
    b, br = start(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(imported, client, a, ar, "ALICE")
        second = pool.submit(imported, client, b, br, "BOB")
        ar, br = first.result(), second.result()

    def search(pair):
        token, revision = pair
        return client.post("/api/search", headers=headers(token, revision), json={"query": "coffee", "method": "compare"}).json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(search, [(a, ar), (b, br)]))
    assert [r["id"] for r in results[0]["results"]["embeddings"]] == ["ALICE"]
    assert [r["id"] for r in results[1]["results"]["embeddings"]] == ["BOB"]
    entries = list(app.state.workspaces.entries.values())
    assert entries[0].engine is not entries[1].engine
    assert entries[0].engine.embeddings is not entries[1].engine.embeddings
    assert entries[0].engine.model is entries[1].engine.model is app.state.engine.model


def test_concurrent_edit_invalidates_queued_analysis_revision(visitors, monkeypatch):
    app, client = visitors
    token, revision = start(client)
    entry = next(iter(app.state.workspaces.entries.values()))
    entered, proceed = threading.Event(), threading.Event()
    original = entry.engine.preflight

    def slow(articles):
        entered.set()
        assert proceed.wait(5)
        return original(articles)

    monkeypatch.setattr(entry.engine, "preflight", slow)
    article = entry.store.articles()[0].model_dump()
    article["title"] = "Changed title"
    with ThreadPoolExecutor(max_workers=2) as pool:
        edited = pool.submit(client.put, "/api/articles/A01", headers=headers(token, revision), json=article)
        assert entered.wait(5)
        analysis = pool.submit(client.post, "/api/search", headers=headers(token, revision), json={"query": "coffee"})
        proceed.set()
        assert edited.result().status_code == 200
        assert analysis.result().status_code == 409


def test_expiry_skips_active_leases_then_cleans_and_does_not_revive(visitors):
    app, client = visitors
    token, revision = start(client)
    manager = app.state.workspaces
    entry, _ = manager.acquire(token)
    later = entry.touched + manager.settings.workspace_idle_seconds + 1
    manager.clock = lambda: later
    manager.cleanup()
    assert entry.store.path.exists()
    assert client.get("/api/articles", headers=headers(token)).status_code == 410
    manager.release(entry)
    manager.cleanup()
    assert not entry.store.path.parent.exists()
    assert entry.identifier not in manager.entries


def test_absolute_lifetime_cannot_be_extended_by_activity(visitors):
    app, client = visitors
    token, revision = start(client)
    manager = app.state.workspaces
    entry = next(iter(manager.entries.values()))
    later = entry.created + manager.settings.workspace_lifetime_seconds + 1
    entry.touched = later
    manager.clock = lambda: later
    assert client.get("/api/articles", headers=headers(token)).status_code == 410
    manager.cleanup()
    assert not entry.store.path.exists()


def test_restart_recovers_cookie_owned_data_and_revision(visitor_settings, engine):
    app = create_app(visitor_settings, engine)
    with TestClient(app, headers={"X-Workspace-Request": "true"}) as client:
        token, revision = start(client)
        revision = imported(client, token, revision, "PERSISTED")
    restarted = create_app(visitor_settings, engine)
    with TestClient(restarted, headers={"X-Workspace-Request": "true"}) as client:
        value = client.get("/api/articles", headers=headers(token))
        assert value.status_code == 200
        assert value.json()["articles"][0]["id"] == "PERSISTED"
        assert value.json()["collection_revision"] == revision
        assert next(iter(restarted.state.workspaces.entries.values())).engine.cache_key is None


def test_capacity_and_index_eviction_are_bounded(visitor_settings, engine):
    app = create_app(replace(visitor_settings, max_workspaces=2, max_cached_indexes=1), engine)
    with TestClient(app, headers={"X-Workspace-Request": "true"}) as client:
        a, ar = start(client)
        b, br = start(client)
        for token, revision in [(a, ar), (b, br)]:
            assert client.post("/api/search", headers=headers(token, revision), json={"query": "coffee"}).status_code == 200
        assert sum(e.engine.cache_key is not None for e in app.state.workspaces.entries.values()) == 1
        client.cookies.clear()
        response = client.get("/api/session")
        assert response.status_code == 503 and response.headers["retry-after"] == "60"
        assert len(app.state.workspaces.entries) == 2
        assert client.post("/api/search", headers=headers(a, ar), json={"query": "coffee"}).status_code == 200


def test_process_lock_rejects_second_manager(visitors, visitor_settings, engine):
    app, client = visitors
    other = WorkspaceManager(visitor_settings, engine)
    with pytest.raises(RuntimeError, match="another process"):
        other.start()


@pytest.mark.parametrize("changes", [{"secret": ""}, {"workspace_mode": "unknown"}, {"analysis_queue_size": -1},
                                      {"max_workspaces": 0}, {"max_cached_indexes": 0}, {"analysis_timeout_seconds": 0}])
def test_invalid_resource_or_ownership_configuration_is_rejected(visitor_settings, engine, changes):
    with pytest.raises(ValueError):
        create_app(replace(visitor_settings, **changes), engine)


@pytest.mark.parametrize("operation", ["replace", "edit"])
def test_precommit_failure_rolls_back_revision_and_content(visitors, operation):
    app, client = visitors
    token, revision = start(client)
    entry = next(iter(app.state.workspaces.entries.values()))
    assert client.post("/api/reviews", headers=headers(token, revision),
                       json={"source_id": "A01", "target_id": "A02", "decision": "useful"}).status_code == 200
    before = [a.model_dump() for a in entry.store.articles()], entry.store.reviews(), entry.store.revision()
    candidates = entry.store.articles()
    candidates[0].title = "Changed within transaction"

    def abort():
        # Called after article/review/revision SQL, immediately before commit.
        raise HTTPException(504, "Injected expired deadline")

    with pytest.raises(HTTPException):
        if operation == "replace":
            entry.store.replace(candidates, abort)
        else:
            entry.store.save_article(candidates[0], abort)
    assert ([a.model_dump() for a in entry.store.articles()], entry.store.reviews(), entry.store.revision()) == before


def test_cleanup_refuses_unexpected_contents_and_symlink(visitors, tmp_path):
    app, client = visitors
    token, revision = start(client)
    manager = app.state.workspaces
    entry = next(iter(manager.entries.values()))
    unexpected = entry.store.path.parent / "do-not-delete.txt"
    unexpected.write_text("Keep this")
    manager.clock = lambda: entry.created + manager.settings.workspace_lifetime_seconds + 1
    manager.cleanup()
    assert unexpected.read_text() == "Keep this" and entry.store.path.exists()


def test_cleanup_does_not_follow_symlinks(visitors, tmp_path):
    app, client = visitors
    start(client)
    manager = app.state.workspaces
    entry = next(iter(manager.entries.values()))
    outside = tmp_path / "outside.txt"
    outside.write_text("Protected outside file")
    link = entry.store.path.parent / "workspace.sqlite3-wal"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("This Windows account cannot create symbolic links")
    try:
        manager.clock = lambda: entry.created + manager.settings.workspace_lifetime_seconds + 1
        manager.cleanup()
        assert entry.store.path.exists() and outside.read_text() == "Protected outside file"
    finally:
        link.unlink()


def test_logout_revokes_cookie_and_expired_restart_cleans(visitor_settings, engine):
    app = create_app(visitor_settings, engine)
    with TestClient(app, headers={"X-Workspace-Request": "true"}) as client:
        token, revision = start(client)
        assert client.post("/api/logout", headers=headers(token), json={}).status_code == 200
        assert client.get("/api/articles", headers=headers(token)).status_code == 410
        other, _ = start(client)
        entry = next(iter(app.state.workspaces.entries.values()))
        with entry.store.connect() as db:
            db.execute("UPDATE metadata SET value='0' WHERE key IN ('created_at','last_used_at')")
    restarted = create_app(visitor_settings, engine)
    with TestClient(restarted, headers={"X-Workspace-Request": "true"}) as client:
        assert not restarted.state.workspaces.entries
        assert client.get("/api/articles", headers=headers(other)).status_code == 410


def test_queued_timeout_cancels_before_execution():
    async def scenario():
        executor = BoundedExecutor(1, .05)
        started, finish = threading.Event(), threading.Event()
        seen = []

        def slow(control):
            started.set()
            finish.wait(5)

        first = asyncio.create_task(executor.run(slow))
        await asyncio.to_thread(started.wait, 2)
        second = asyncio.create_task(executor.run(lambda control: seen.append("executed")))
        for task in [first, second]:
            with pytest.raises(HTTPException) as timeout:
                await task
            assert timeout.value.status_code == 504
        assert seen == [] and executor.outstanding == 1
        finish.set()
        await asyncio.to_thread(executor.close)
        assert executor.outstanding == 0
    asyncio.run(scenario())


def test_executor_overload_timeout_and_slot_retention():
    async def scenario():
        executor = BoundedExecutor(0, 0.05)
        started, finish = threading.Event(), threading.Event()

        def slow(control):
            started.set()
            finish.wait(5)

        pending = asyncio.create_task(executor.run(slow))
        await asyncio.to_thread(started.wait, 2)
        with pytest.raises(HTTPException) as overload:
            await executor.run(lambda control: None)
        assert overload.value.status_code == 503
        with pytest.raises(HTTPException) as expired:
            await pending
        assert expired.value.status_code == 504 and executor.outstanding == 1
        with pytest.raises(HTTPException):
            await executor.run(lambda control: None)
        finish.set()
        for _ in range(100):
            if executor.outstanding == 0:
                break
            await asyncio.sleep(.01)
        assert await executor.run(lambda control: "recovered") == "recovered"
        executor.close()
    asyncio.run(scenario())


def test_timed_out_mutation_never_commits_and_cleanup_waits(visitor_settings, engine, monkeypatch):
    app = create_app(replace(visitor_settings, analysis_timeout_seconds=.1, analysis_queue_size=0), engine)
    with TestClient(app, headers={"X-Workspace-Request": "true"}) as client:
        token, revision = start(client)
        entry = next(iter(app.state.workspaces.entries.values()))
        snapshot = [a.model_dump() for a in entry.store.articles()]
        finish = threading.Event()
        original = entry.engine.preflight

        def slow(articles):
            finish.wait(5)
            return original(articles)

        monkeypatch.setattr(entry.engine, "preflight", slow)
        response = client.post("/api/articles/reset", headers=headers(token, revision), json={})
        assert response.status_code == 504
        assert app.state.execution.outstanding == 1 and entry.active == 1
        overloaded = client.post("/api/search", headers=headers(token, revision), json={"query": "coffee"})
        assert overloaded.status_code == 503 and overloaded.headers["retry-after"] == "2"
        assert client.delete("/api/workspace", headers=headers(token, revision)).status_code == 423
        app.state.workspaces.clock = lambda: entry.created + visitor_settings.workspace_lifetime_seconds + 1
        app.state.workspaces.cleanup()
        assert entry.store.path.exists()
        finish.set()
        for _ in range(200):
            if app.state.execution.outstanding == 0:
                break
            time.sleep(.01)
        assert entry.store.revision() == revision
        assert [a.model_dump() for a in entry.store.articles()] == snapshot
        app.state.workspaces.cleanup()
        assert not entry.store.path.exists()


def test_timed_out_review_rolls_back_and_restart_keeps_original_revision(visitor_settings, engine, monkeypatch):
    settings = replace(visitor_settings, analysis_timeout_seconds=.1)
    app = create_app(settings, engine)
    with TestClient(app, headers={"X-Workspace-Request": "true"}) as client:
        token, revision = start(client)
        entry = next(iter(app.state.workspaces.entries.values()))
        finish = threading.Event()
        original = entry.store.review

        def slow(review, before_commit=None):
            finish.wait(5)
            return original(review, before_commit)

        monkeypatch.setattr(entry.store, "review", slow)
        result = client.post("/api/reviews", headers=headers(token, revision), json={"source_id": "A01", "target_id": "A02", "decision": "useful"})
        assert result.status_code == 504
        finish.set()
        for _ in range(200):
            if app.state.execution.outstanding == 0:
                break
            time.sleep(.01)
        assert entry.store.reviews() == []
    restarted = create_app(settings, engine)
    with TestClient(restarted, headers={"X-Workspace-Request": "true"}) as client:
        assert restarted.state.execution.outstanding == 0
        assert client.get("/api/articles", headers=headers(token)).json()["collection_revision"] == revision
        assert client.get("/api/reviews", headers=headers(token)).json()["reviews"] == []
