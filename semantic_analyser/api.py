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
from .engine import AnalysisEngine
from .schemas import (Article, ImportRequest, LinkRequest, LoginRequest, OverlapRequest,
                      ReviewRequest, SearchRequest)
from .storage import Store, demo_articles, parse_csv


def create_app(settings=None, engine=None):
    settings = settings or Settings()
    settings.validate()
    store = Store(settings.database_path)
    engine = engine or AnalysisEngine(settings.model_revision)
    signing_key = settings.secret or secrets.token_hex(32)
    signer = URLSafeTimedSerializer(signing_key, salt="semantic-workspace")
    password_tag = hashlib.sha256(settings.password.encode()).hexdigest()
    attempts = defaultdict(deque)
    attempts_lock = threading.Lock()
    mutations_lock = threading.RLock()

    @asynccontextmanager
    async def lifespan(app):
        if settings.preload_model:
            await run_in_threadpool(engine.load)
        yield

    app = FastAPI(title="Semantic Content Analyser", version="1.0.0", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store
    app.state.engine = engine

    def authenticated(request):
        if not settings.password:
            return True
        try:
            token = signer.loads(request.cookies.get("workspace_session", ""), max_age=28800)
            return hmac.compare_digest(token.get("password_tag", ""), password_tag)
        except (BadSignature, SignatureExpired, AttributeError):
            return False

    @app.middleware("http")
    async def protect(request: Request, call_next):
        path = request.url.path
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 2000000:
            return JSONResponse({"detail": "Request exceeds the 2 MB limit."}, status_code=413)
        # Bound chunked requests too; never buffer unbounded input before schema validation.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("x-workspace-request") != "true":
                return JSONResponse({"detail": "Missing workspace request header."}, status_code=403)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 2000000:
                    return JSONResponse({"detail": "Request exceeds the 2 MB limit."}, status_code=413)
            request._body = bytes(body)
        if path.startswith("/api/") and path not in {"/api/session", "/api/login"} and not authenticated(request):
            return JSONResponse({"detail": "Sign in to your workspace."}, status_code=401)
        response = await call_next(request)
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

    @app.get("/health")
    def health():
        with store.connect() as connection:
            connection.execute("SELECT 1")
        return {"status": "ok", "model_loaded": engine.model is not None}

    @app.get("/api/session")
    def session(request: Request):
        return {"authenticated": authenticated(request), "password_required": bool(settings.password)}

    @app.post("/api/login")
    def login(data: LoginRequest, request: Request, response: Response):
        address = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with attempts_lock:
            # Bound the number of tracked addresses in a single-worker deployment.
            if len(attempts) > 2000:
                attempts.clear()
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
    def logout(response: Response):
        response.delete_cookie("workspace_session", secure=settings.production, samesite="strict")
        return {"authenticated": False}

    @app.get("/api/meta")
    def meta():
        articles = store.articles()
        return {"version": "1.0.0", "model": "all-MiniLM-L6-v2", "revision": settings.model_revision,
                "model_loaded": engine.model is not None, "dimensions": 384, "max_articles": 100,
                "article_count": len(articles), "topics": sorted({a.topic for a in articles if a.topic}),
                "review_count": len(store.reviews()), "single_workspace": True,
                "chunking": "192 body tokens, 32-token overlap; title capped at 40 tokens"}

    @app.get("/api/schema")
    def schema():
        return app.openapi()

    @app.get("/api/articles")
    def articles():
        return {"articles": [a.model_dump() for a in store.articles()]}

    @app.post("/api/articles/import")
    def import_articles(data: ImportRequest):
        parsed = parse_csv(data.csv_text)
        with mutations_lock:
            count = store.replace(parsed)
        return {"count": count, "message": "Collection replaced. Previous review decisions were cleared."}

    @app.post("/api/articles/reset")
    def reset_articles():
        with mutations_lock:
            count = store.replace(demo_articles())
        return {"count": count}

    @app.put("/api/articles/{article_id}")
    def update_article(article_id: str, data: Article):
        if article_id != data.id:
            raise HTTPException(422, "Article IDs cannot be changed while editing.")
        with mutations_lock:
            store.save_article(data)
        return data.model_dump()

    @app.get("/api/articles/export")
    def export_articles():
        return Response(store.export(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="articles.csv"'})

    @app.post("/api/search")
    def search(data: SearchRequest):
        start = time.perf_counter()
        collection = store.articles()
        methods = ["embeddings", "tfidf"] if data.method == "compare" else [data.method]
        results = {method: engine.search(collection, data.query, method, data.top_k, data.min_score) for method in methods}
        return {"results": results, "elapsed_ms": round((time.perf_counter() - start) * 1000),
                "query": data.query, "article_count": len(collection)}

    @app.post("/api/links")
    def links(data: LinkRequest):
        collection = store.articles()
        methods = ["embeddings", "tfidf"] if data.method == "compare" else [data.method]
        results = {method: engine.links(collection, data.source_id, method, data.top_k, data.min_score) for method in methods}
        decisions = [r for r in store.reviews() if r["source_id"] == data.source_id]
        return {"results": results, "reviews": decisions, "review_required": True}

    @app.post("/api/overlaps")
    def overlaps(data: OverlapRequest):
        return {"pairs": engine.overlaps(store.articles(), data.method, data.threshold, data.limit),
                "notice": "Similarity is a review signal. It does not establish identical intent, cannibalisation or merge eligibility."}

    @app.get("/api/reviews")
    def reviews():
        return {"reviews": store.reviews()}

    @app.post("/api/reviews")
    def save_review(data: ReviewRequest):
        with mutations_lock:
            store.review(data)
        return {"saved": True}

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
