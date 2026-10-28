import threading
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from semantic_analyser.api import create_app
from semantic_analyser.config import Settings
from semantic_analyser.fetch_policy import FetchLimits
from semantic_analyser.safe_fetch import SafeFetcher
from test_safe_fetch import FakeDNS, FakeTransport


@pytest.fixture
def fetch_api(tmp_path, engine):
    settings = Settings(database_path=tmp_path / "not-open.sqlite3", visitor_root=tmp_path / "visitors",
                        workspace_mode="visitor", secret="fetch-test-only-session-secret-" * 2, password="",
                        production=False, preload_model=False, website_fetch_enabled=True)
    transport = FakeTransport({"/": (200, b"public text", {})})
    fetcher = SafeFetcher(FetchLimits(delay_seconds=0), FakeDNS(), transport)
    app = create_app(settings, engine, fetcher)
    with TestClient(app, headers={"X-Workspace-Request": "true"}) as client:
        yield app, client, transport


def session(client):
    client.cookies.clear()
    assert client.get("/api/session").status_code == 200
    cookie = client.cookies.get("semantic_visitor")
    payload = client.get("/api/articles").json()
    return cookie, payload["collection_revision"]


def headers(cookie, revision=None):
    values = {"Cookie": "semantic_visitor=" + cookie, "X-Workspace-Request": "true"}
    if revision:
        values["If-Match"] = revision
    return values


def test_network_feature_is_disabled_by_default(client):
    assert client.post("/api/website/check", json={"url": "http://public.example/"}).status_code == 404
    assert client.app.state.engine.model is None


def test_fetch_metadata_and_budgets_are_owned_without_changing_articles(fetch_api):
    app, client, transport = fetch_api
    a, ar = session(client)
    b, br = session(client)
    old = client.get("/api/articles", headers=headers(a)).json()
    first = client.post("/api/website/check", headers=headers(a, ar), json={"url": "http://first.example/"})
    second = client.post("/api/website/check", headers=headers(b, br), json={"url": "http://second.example/"})
    assert first.status_code == second.status_code == 200
    assert first.json()["requests_used"] == second.json()["requests_used"] == 2
    assert "public text" not in first.text and "body" not in first.json()["fetch"]
    assert client.get("/api/articles", headers=headers(a)).json() == old
    assert client.get("/api/reviews", headers=headers(a)).json()["reviews"] == []
    entries = list(app.state.workspaces.entries.values())
    assert entries[0].fetch_session is not entries[1].fetch_session
    assert entries[0].fetch_session.owner != entries[1].fetch_session.owner
    assert app.state.engine.model is None  # Fetching does not initialize MiniLM.


def test_fetch_requires_owner_revision_and_does_not_leak_dns_addresses(fetch_api):
    app, client, transport = fetch_api
    token, revision = session(client)
    client.cookies.clear()
    assert client.post("/api/website/check", json={"url": "http://public.example/"}).status_code == 401
    assert client.post("/api/website/check", headers=headers(token), json={"url": "http://public.example/"}).status_code == 428
    assert client.post("/api/website/check", headers=headers(token, "stale"), json={"url": "http://public.example/"}).status_code == 409
    assert transport.calls == []
    app.state.fetcher.resolver.answers = [["8.8.8.8", "10.20.30.40"]]
    rejected = client.post("/api/website/check", headers=headers(token, revision), json={"url": "http://public.example/"})
    assert rejected.status_code == 400 and rejected.json()["code"] == "blocked_destination"
    assert "10.20.30.40" not in rejected.text and "8.8.8.8" not in rejected.text
    assert rejected.headers["cache-control"] == "no-store"


def test_workspace_change_starts_new_owned_fetch_run(fetch_api):
    app, client, transport = fetch_api
    token, revision = session(client)
    assert client.post("/api/website/check", headers=headers(token, revision), json={"url": "http://first.example/"}).status_code == 200
    assert client.post("/api/website/check", headers=headers(token, revision), json={"url": "http://second.example/"}).status_code == 400
    updated = client.post("/api/articles/reset", headers=headers(token, revision), json={})
    current = updated.json()["collection_revision"]
    assert client.post("/api/website/check", headers=headers(token, revision), json={"url": "http://second.example/"}).status_code == 409
    assert client.post("/api/website/check", headers=headers(token, current), json={"url": "http://second.example/"}).status_code == 200


def test_fetch_timeout_keeps_execution_lease_until_work_stops(tmp_path, engine):
    settings = Settings(database_path=tmp_path / "never-open.sqlite3", visitor_root=tmp_path / "visitors",
                        workspace_mode="visitor", secret="fetch-timeout-test-key-" * 2, password="", production=False,
                        preload_model=False, website_fetch_enabled=True, analysis_timeout_seconds=.1, analysis_queue_size=0)
    transport = FakeTransport({"/": (200, b"public text", {})})
    finish = threading.Event()
    original = transport.get

    def slow(*args):
        finish.wait(5)
        return original(*args)

    transport.get = slow
    app = create_app(settings, engine, SafeFetcher(FetchLimits(delay_seconds=0), FakeDNS(), transport))
    with TestClient(app, headers={"X-Workspace-Request": "true"}) as client:
        token, revision = session(client)
        entry = next(iter(app.state.workspaces.entries.values()))
        before = [a.model_dump() for a in entry.store.articles()]
        response = client.post("/api/website/check", headers=headers(token, revision), json={"url": "http://public.example/"})
        assert response.status_code == 504 and entry.active == 1
        overloaded = client.post("/api/search", headers=headers(token, revision), json={"query": "coffee"})
        assert overloaded.status_code == 503
        app.state.workspaces.clock = lambda: entry.created + settings.workspace_lifetime_seconds + 1
        app.state.workspaces.cleanup()
        assert entry.store.path.exists()
        finish.set()
        for _ in range(200):
            if app.state.execution.outstanding == 0:
                break
            time.sleep(.01)
        assert [a.model_dump() for a in entry.store.articles()] == before
        assert entry.store.revision() == revision
        app.state.workspaces.cleanup()
        assert not entry.store.path.exists()
