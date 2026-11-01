import asyncio
import csv
import hashlib
import hmac
import io
import json
import secrets
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .config import ROOT, Settings
from .collections import PreflightUnavailable
from .engine import AnalysisEngine
from .schemas import (Article, ImportRequest, LinkRequest, LoginRequest, OverlapRequest,
                      ReviewRequest, SearchRequest, FetchRequest, WebsiteStart, WebsiteAction,
                      WebsiteSelection, WebsiteImport)
from .storage import Store, demo_articles, parse_csv
from .execution import BoundedExecutor
from .workspaces import COOKIE, Workspace, WorkspaceManager
from .safe_fetch import SafeFetcher
from .fetch_policy import FetchError
from .websites import WebsiteService
from .demo_limits import DemoLimits
import sqlite3


def create_app(settings=None, engine=None, fetcher=None):
    settings = settings or Settings()
    settings.validate()
    demo = DemoLimits(settings)
    engine = engine or AnalysisEngine(settings.model_revision)
    local = Workspace(Store(settings.database_path), engine) if settings.workspace_mode == "local" else None
    store = local.store if local else None
    manager = WorkspaceManager(settings, engine) if local is None else None
    execution = BoundedExecutor(settings.analysis_queue_size, settings.analysis_timeout_seconds)
    fetcher = fetcher or SafeFetcher(denied_networks=settings.fetch_deny_cidrs, allowed_hosts=settings.fetch_allowed_hosts)
    fetcher.request_guard = demo.outbound
    websites = WebsiteService(fetcher)
    cookie_name = "__Host-" + COOKIE if settings.production else COOKIE
    signing_key = settings.secret or secrets.token_hex(32)
    signer = URLSafeTimedSerializer(signing_key, salt="semantic-workspace")
    password_tag = hashlib.sha256(settings.password.encode()).hexdigest()
    attempts = defaultdict(deque)
    attempts_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        if manager:
            await run_in_threadpool(manager.start)
        try:
            if settings.preload_model:
                await run_in_threadpool(engine.load)
            yield
        finally:
            await run_in_threadpool(execution.close)
            if manager:
                await run_in_threadpool(manager.close)

    app = FastAPI(title="Semantic Content Analyser", version="1.0.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    app.state.engine = engine
    app.state.collections = local.collections if local else None
    app.state.workspaces = manager
    app.state.execution = execution
    app.state.fetcher = fetcher
    app.state.demo_limits = demo

    def authenticated(request):
        if not settings.password:
            return True
        try:
            token = signer.loads(request.cookies.get("workspace_session", ""), max_age=28800)
            return hmac.compare_digest(token.get("password_tag", ""), password_tag)
        except (BadSignature, SignatureExpired, AttributeError):
            return False

    def rejected(detail, status, headers=None):
        return JSONResponse({"detail": detail}, status_code=status,
                            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", **(headers or {})})

    @app.middleware("http")
    async def protect(request: Request, call_next):
        if not request.url.path.startswith('/api/'):
            return await protect_impl(request, call_next)
        entered = False
        try:
            request.state.demo_identity = demo.identity(request)
            demo.enter(request.state.demo_identity)
            entered = True
            return await protect_impl(request, call_next)
        except HTTPException as error:
            return rejected(error.detail, error.status_code, error.headers)
        except sqlite3.DatabaseError as error:
            if getattr(error, 'sqlite_errorcode', None) == sqlite3.SQLITE_FULL:
                return rejected('Temporary database storage is full. Export or delete your workspace.', 507)
            raise
        finally:
            if entered:
                demo.leave()

    async def protect_impl(request: Request, call_next):
        path = request.url.path
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 2000000:
            return rejected("Request exceeds the 2 MB limit.", 413)
        # Bound chunked requests too; never buffer unbounded input before schema validation.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("x-workspace-request") != "true":
                return rejected("Missing workspace request header.", 403)
            body = bytearray()
            try:
                async with asyncio.timeout(15):
                    async for chunk in request.stream():
                        body.extend(chunk)
                        if len(body) > 2000000:
                            return rejected("Request exceeds the 2 MB limit.", 413)
            except TimeoutError:
                return rejected("Request body timed out.", 408)
            request._body = bytes(body)
        if path.startswith("/api/") and path not in {"/api/session", "/api/login"} and not authenticated(request):
            return rejected("Sign in to your workspace.", 401)
        entry, visitor_token = local, None
        leased = False
        if path.startswith("/api/") and path not in {"/api/login", "/api/logout", "/api/schema", "/api/evaluation"} and authenticated(request):
            if manager:
                try:
                    if path == "/api/session" and not request.cookies.get(cookie_name) and request.headers.get("x-workspace-request") != "true":
                        return rejected("Missing workspace request header.", 403)
                    if path == '/api/session' and not request.cookies.get(cookie_name):
                        demo.session(request.state.demo_identity)
                    entry, visitor_token = await run_in_threadpool(manager.acquire, request.cookies.get(cookie_name), path == "/api/session")
                    leased = True
                except HTTPException as error:
                    response = rejected(error.detail, error.status_code, error.headers)
                    if error.status_code in {401, 410}:
                        response.delete_cookie(cookie_name, secure=settings.production, samesite="strict")
                    return response
        request.state.workspace = entry
        try:
            response = await call_next(request)
            if manager:
                if response.status_code in {401, 410}:
                    response.delete_cookie(cookie_name, secure=settings.production, samesite="strict")
                elif visitor_token and not getattr(request.state, "deleted_workspace", False):
                    response.set_cookie(cookie_name, visitor_token, httponly=True, secure=settings.production,
                                        samesite="strict", max_age=int(settings.workspace_lifetime_seconds))
        finally:
            if leased:
                await run_in_threadpool(manager.release, entry)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def invalid_value(request, error):
        detail = "Invalid article fields. Check required text, IDs and URLs." if isinstance(error, ValidationError) else str(error)
        return JSONResponse({"detail": detail}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing_item(request, error):
        return JSONResponse({"detail": "Article not found in this collection."}, status_code=404)

    @app.exception_handler(PreflightUnavailable)
    async def unavailable_preflight(request, error):
        return JSONResponse({"detail": str(error)}, status_code=503)

    @app.exception_handler(FetchError)
    async def rejected_fetch(request, error):
        details = {"detail": error.message, "code": error.code}
        for attr, field in [('upstream_status','source_http_status'), ('fetch_resource','fetch_resource'),
                            ('discovery_stage','discovery_stage'), ('diagnostic_reference','diagnostic_reference')]:
            if hasattr(error, attr):
                details[field] = getattr(error, attr)
        return JSONResponse(details, status_code=error.status,
                            headers={"Retry-After": "60"} if error.status in {429, 503} else None)

    @app.get("/health")
    def health():
        if (settings.preload_model and engine.model is None) or (manager and
                (manager.file_lock is None or not manager.thread or not manager.thread.is_alive())):
            raise HTTPException(503, 'Application is not ready.')
        if store:
            with store.connect() as connection:
                connection.execute("SELECT 1")
        return {"status": "ok", "model_loaded": engine.model is not None}

    def check_revision(request, entry):
        expected = request.headers.get("if-match")
        if manager and expected is None:
            raise HTTPException(428, "Read the collection and supply its revision in If-Match.")
        if expected is not None and expected.strip('"') != entry.store.revision():
            raise HTTPException(409, "Collection changed. Reload it and run the analysis again.")

    async def execute(request, operation):
        entry = request.state.workspace

        def work(control):
            def ownership_guard():
                if manager and manager._expired(entry):
                    raise HTTPException(410, "Temporary workspace expired. Reload to start a new one.")
                if manager and (request.url.path.startswith('/api/articles') or request.url.path in {'/api/reviews','/api/website/import'}):
                    # May run inside a SQLite transaction. Never take manager.lock:
                    # an acquiring request can hold it while updating last-used metadata.
                    manager.check_storage(entry)
            control.guard = ownership_guard
            with entry.locked(settings.workspace_lock_seconds):
                control.check()
                check_revision(request, entry)
                result = operation(entry, control)
                control.check()
                if manager and manager._expired(entry):
                    raise HTTPException(410, "Temporary workspace expired. Reload to start a new one.")
                return result

        return await execution.run(work, (lambda: manager.pin(entry)) if manager else lambda: None,
                                   (lambda: manager.release(entry)) if manager else lambda: None)

    @app.get("/api/session")
    def session(request: Request):
        return {"authenticated": authenticated(request), "password_required": bool(settings.password),
                "workspace_mode": settings.workspace_mode}

    @app.post("/api/login")
    def login(data: LoginRequest, request: Request, response: Response):
        address = request.state.demo_identity
        now = time.monotonic()
        with attempts_lock:
            # Never clear live budgets to admit new identities.
            for peer, queue in list(attempts.items()):
                while queue and now - queue[0] > 60:
                    queue.popleft()
                if not queue:
                    del attempts[peer]
            if address not in attempts and len(attempts) >= 2000:
                raise HTTPException(503, "Sign-in admission capacity is full.", headers={"Retry-After":"60"})
            entries = attempts[address]
            while entries and now - entries[0] > 60:
                entries.popleft()
            if len(entries) >= 10:
                raise HTTPException(429, "Too many sign-in attempts. Wait one minute.")
            entries.append(now)
        if settings.password and not hmac.compare_digest(data.password.encode(), settings.password.encode()):
            raise HTTPException(401, "The workspace password is incorrect.")
        response.set_cookie("workspace_session", signer.dumps({"password_tag": password_tag}),
                            httponly=True, secure=settings.production, samesite="strict", max_age=28800)
        return {"authenticated": True}

    @app.post("/api/logout")
    async def logout(response: Response, request: Request):
        if manager and request.cookies.get(cookie_name):
            await run_in_threadpool(manager.revoke, request.cookies[cookie_name])
        response.delete_cookie("workspace_session", secure=settings.production, samesite="strict")
        response.delete_cookie(cookie_name, secure=settings.production, samesite="strict")
        return {"authenticated": False}

    @app.get("/api/meta")
    def meta(request: Request):
        entry = request.state.workspace
        with entry.locked(settings.workspace_lock_seconds):
            articles = entry.store.articles()
            reviews = entry.store.reviews()
        return {"version": "1.0.0", "model": "all-MiniLM-L6-v2", "revision": settings.model_revision,
                "model_loaded": engine.model is not None, "dimensions": 384, "max_articles": 100,
                "article_count": len(articles), "topics": sorted({a.topic for a in articles if a.topic}),
                "review_count": len(reviews), "single_workspace": manager is None,
                "workspace_mode": settings.workspace_mode, "idle_seconds": settings.workspace_idle_seconds,
                "website_fetch_enabled": settings.website_fetch_enabled,
                "chunking": "192 body tokens, 32-token overlap; title capped at 40 tokens"}

    @app.get("/api/schema")
    def schema():
        return app.openapi()

    @app.get("/api/articles")
    def articles(request: Request):
        entry = request.state.workspace
        with entry.locked(settings.workspace_lock_seconds):
            return {"articles": [a.model_dump() for a in entry.store.articles()],
                    "collection_revision": entry.store.revision()}

    @app.post("/api/articles/import")
    async def import_articles(data: ImportRequest, request: Request):
        parsed = parse_csv(data.csv_text)
        def operation(entry, control):
            count = entry.collections.replace(parsed, control.check)
            return {"count": count, "collection_revision": entry.store.revision(),
                    "message": "Collection replaced. Previous review decisions were cleared."}
        return await execute(request, operation)

    @app.post("/api/articles/reset")
    async def reset_articles(request: Request):
        def operation(entry, control):
            count = entry.collections.replace(demo_articles(), control.check)
            return {"count": count, "collection_revision": entry.store.revision()}
        return await execute(request, operation)

    @app.put("/api/articles/{article_id}")
    async def update_article(article_id: str, data: Article, request: Request):
        if article_id != data.id:
            raise HTTPException(422, "Article IDs cannot be changed while editing.")
        def operation(entry, control):
            entry.collections.save_article(data, control.check)
            return {**data.model_dump(), "collection_revision": entry.store.revision()}
        return await execute(request, operation)

    @app.get("/api/articles/export")
    def export_articles(request: Request):
        entry = request.state.workspace
        with entry.locked(settings.workspace_lock_seconds):
            exported = entry.store.export()
        return Response(exported, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="articles.csv"'})

    @app.post("/api/search")
    async def search(data: SearchRequest, request: Request):
        start = time.perf_counter()
        methods = ["embeddings", "tfidf"] if data.method == "compare" else [data.method]
        def operation(entry, control):
            collection = entry.store.articles()
            results = {}
            for method in methods:
                control.check()
                results[method] = entry.engine.search(collection, data.query, method, data.top_k, data.min_score)
            return {"results": results, "elapsed_ms": round((time.perf_counter() - start) * 1000),
                    "query": data.query, "article_count": len(collection), "collection_revision": entry.store.revision()}
        return await execute(request, operation)

    @app.post("/api/links")
    async def links(data: LinkRequest, request: Request):
        methods = ["embeddings", "tfidf"] if data.method == "compare" else [data.method]
        def operation(entry, control):
            collection = entry.store.articles()
            results = {}
            for method in methods:
                control.check()
                results[method] = entry.engine.links(collection, data.source_id, method, data.top_k, data.min_score)
            decisions = [r for r in entry.store.reviews() if r["source_id"] == data.source_id]
            return {"results": results, "reviews": decisions, "review_required": True,
                    "collection_revision": entry.store.revision()}
        return await execute(request, operation)

    @app.post("/api/overlaps")
    async def overlaps(data: OverlapRequest, request: Request):
        def operation(entry, control):
            return {"pairs": entry.engine.overlaps(entry.store.articles(), data.method, data.threshold, data.limit),
                    "collection_revision": entry.store.revision(),
                    "notice": "Similarity is a review signal. It does not establish identical intent, cannibalisation or merge eligibility."}
        return await execute(request, operation)

    @app.post("/api/website/check")
    async def check_website(data: FetchRequest, request: Request):
        if not settings.website_fetch_enabled:
            raise HTTPException(404, "Website fetching is not enabled on this installation.")

        def operation(entry, control):
            revision = entry.store.revision()
            owner = entry.identifier or "local"
            if entry.fetch_session is None or entry.fetch_revision != revision:
                entry.fetch_session = fetcher.new_session(owner)
                entry.fetch_revision = revision
            result = fetcher.fetch(entry.fetch_session, data.url, owner, control)
            return {"fetch": result.metadata(), "collection_revision": revision,
                    "requests_used": entry.fetch_session.requests,
                    "notice": "Fetch check only; no articles were extracted or saved."}

        return await execute(request, operation)

    def website_run(entry, run_id):
        if not settings.website_fetch_enabled:
            raise HTTPException(404, 'Website importing is not enabled on this installation.')
        run = entry.website_run
        if run is None or run.identifier != run_id or run.owner != (entry.identifier or 'local'):
            raise HTTPException(404, 'Website run not found in this workspace.')
        if run.revision != entry.store.revision():
            raise HTTPException(409, 'Collection changed. Start website discovery again.')
        if run.expired():
            entry.website_run = None
            raise HTTPException(410, 'Website run expired or exhausted its fetch-time budget. Start a new discovery.')
        return run

    @app.post('/api/website/start')
    async def website_start(data: WebsiteStart, request: Request):
        if not settings.website_fetch_enabled:
            raise HTTPException(404, 'Website importing is not enabled on this installation.')
        def operation(entry, control):
            if entry.website_run and time.monotonic() - entry.website_run.session.started < 5:
                raise HTTPException(429, 'Wait briefly before starting another website run.', headers={'Retry-After': '5'})
            run = websites.start(entry.identifier or 'local', entry.store.revision(), data.url, data.method)
            control.check()
            entry.website_run = run
            return run.view()
        return await execute(request, operation)

    @app.post('/api/website/step')
    async def website_step(data: WebsiteAction, request: Request):
        return await execute(request, lambda entry, control: websites.step(website_run(entry, data.run_id), control))

    @app.post('/api/website/select')
    async def website_select(data: WebsiteSelection, request: Request):
        return await execute(request, lambda entry, control: websites.select(website_run(entry, data.run_id), data.ids))

    @app.post('/api/website/cancel')
    async def website_cancel(data: WebsiteAction, request: Request):
        def operation(entry, control):
            run = website_run(entry, data.run_id)
            run.phase = 'cancelled'
            run.pending.clear()
            run.articles.clear()
            run.extracted.clear()
            return run.view()
        return await execute(request, operation)

    @app.post('/api/website/import')
    async def website_import(data: WebsiteImport, request: Request):
        def operation(entry, control):
            run = website_run(entry, data.run_id)
            if run.phase != 'ready' or not run.articles:
                raise HTTPException(409, 'Finish extraction and review the articles before importing.')
            if run.failures and not data.accept_partial:
                raise HTTPException(422, 'Some articles failed extraction. Explicitly accept the successful subset or start again.')
            # The format-independent admission service checks real-tokenizer limits
            # before any transaction; failures preserve articles and editorial reviews.
            def admission_guard():
                control.check()
                website_run(entry, data.run_id)  # Expiry during tokenization also prevents a late write.
            count = entry.collections.replace(run.articles, admission_guard)
            run.phase = 'imported'
            return {'count': count, 'collection_revision': entry.store.revision()}
        return await execute(request, operation)

    @app.get("/api/reviews")
    def reviews(request: Request):
        entry = request.state.workspace
        with entry.locked(settings.workspace_lock_seconds):
            return {"reviews": entry.store.reviews(), "collection_revision": entry.store.revision()}

    @app.post("/api/reviews")
    async def save_review(data: ReviewRequest, request: Request):
        def operation(entry, control):
            control.check()
            entry.store.review(data, control.check)
            return {"saved": True, "collection_revision": entry.store.revision()}
        return await execute(request, operation)

    @app.delete("/api/workspace")
    def delete_workspace(request: Request):
        if not manager:
            raise HTTPException(403, "Local demo workspace cannot be deleted through this endpoint.")
        entry = request.state.workspace
        with entry.locked(settings.workspace_lock_seconds):
            check_revision(request, entry)
            manager.delete(entry)
        request.state.deleted_workspace = True
        response = JSONResponse({"deleted": True})
        response.delete_cookie(cookie_name, secure=settings.production, samesite="strict")
        return response

    @app.get("/api/evaluation")
    def evaluation():
        rows = []
        report_path = ROOT / "docs/evaluation-rankings.csv"
        if report_path.exists():
            with report_path.open(encoding="utf-8", newline="") as file:
                rows = list(csv.DictReader(file))
        summaries = []
        for method in sorted({r["method"] for r in rows}):
            method_rows = [r for r in rows if r["method"] == method]
            qids = sorted({r["query_id"] for r in method_rows})
            for k in (1, 3, 5):
                precisions, recalls = [], []
                for qid in qids:
                    selected = [r for r in method_rows if r["query_id"] == qid]
                    relevant = sum(r["relevant"].lower() == "true" for r in selected)
                    found = sum(r["relevant"].lower() == "true" and int(r["rank"]) <= k for r in selected)
                    precisions.append(found / k)
                    if relevant:
                        recalls.append(found / relevant)
                summaries.append({"method": method, "k": k, "precision": sum(precisions) / len(precisions),
                                  "recall": sum(recalls) / len(recalls) if recalls else None, "questions": len(qids)})
        queries = []
        with (ROOT / "data/evaluation_queries.csv").open(encoding="utf-8", newline="") as file:
            queries = list(csv.DictReader(file))
        return {"metrics": summaries, "queries": queries, "article_count": 21,
                "label_source": "assistant", "historical": True,
                "notice": "Saved development results for the original 21 synthetic articles. Labels are assistant-proposed, not independently human-reviewed. These results do not update when you edit the current collection, and are not a production benchmark."}

    @app.get("/")
    def index():
        return FileResponse(ROOT / "web/index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
    return app


app = create_app()
