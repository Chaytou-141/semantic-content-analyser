"""Offline real-model Phase 2A checks, only against disposable SQLite state.

Run from project root with the existing virtual environment. Results are written
under ignored runtime/phase2a; Phase 1B files are read, never regenerated.
"""

import csv
import hashlib
import io
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runtime/phase2a"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
os.environ.update({"DATABASE_PATH": str(OUT / "real-bootstrap.sqlite3"), "APP_ENV": "development",
                   "APP_PASSWORD": "", "PRELOAD_MODEL": "false", "HF_HUB_OFFLINE": "1",
                   "TRANSFORMERS_OFFLINE": "1", "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2",
                   "OPENBLAS_NUM_THREADS": "2", "TOKENIZERS_PARALLELISM": "false"})

import torch
from fastapi.testclient import TestClient

from semantic_analyser.api import create_app
from semantic_analyser.config import Settings
from semantic_analyser.engine import AnalysisEngine
from semantic_analyser.storage import parse_csv


def main():
    guard_path = OUT / "preservation-before.json"
    if not guard_path.exists():
        paths = [p for base in ["data", "labels", "benchmarks/phase1b", "web", "infra", "deploy"]
                 for p in (ROOT / base).rglob("*") if p.is_file() and ".terraform" not in p.parts]
        paths += [p for p in (ROOT / "docs").iterdir() if p.is_file()]
        paths += [p for p in (ROOT / "runtime").glob("workspace.sqlite3*") if p.is_file()]
        guard_path.write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                          for p in paths}, indent=2), encoding="utf-8")
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    engine = AnalysisEngine()
    path = OUT / f"real-check-{time.time_ns()}.sqlite3"
    app = create_app(Settings(database_path=path, password="", production=False), engine)
    measured = {}

    def timed(name, fn):
        start, cpu = time.perf_counter(), time.process_time()
        value = fn()
        measured[name] = {"wall_seconds": time.perf_counter() - start,
                          "cpu_seconds": time.process_time() - cpu}
        return value

    def snapshot(client):
        return client.get("/api/articles").json(), client.get("/api/reviews").json()

    def dense_csv(extra=False):
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(["id", "title", "body"])
        for i in range(100):
            writer.writerow([f"D{i}", "Boundary title", "x-" * 656 + ("x" if extra and i == 0 else "")])
        return stream.getvalue()

    with TestClient(app, headers={"X-Workspace-Request": "true"}) as client:
        text = (ROOT / "benchmarks/phase1b/articles.csv").read_text(encoding="utf-8")
        response = timed("cold_preflight_import_36", lambda: client.post("/api/articles/import", json={"csv_text": text}))
        assert response.status_code == 200 and response.json()["count"] == 36
        articles = app.state.store.articles()
        _, summary = timed("warm_preflight_36", lambda: app.state.collections.preflight(articles))
        assert summary["passage_count"] == 269
        assert engine.cache_key is None and not hasattr(engine, "embeddings")
        previous = json.loads((ROOT / "benchmarks/phase1b/results.json").read_text(encoding="utf-8"))
        query = "How should two baristas arrange the grinder, espresso machine and milk workspace to avoid crossing paths?"
        comparison = timed("real_comparison_search_36", lambda: client.post("/api/search", json={"query": query, "method": "compare", "top_k": 5}))
        assert comparison.status_code == 200
        payload = comparison.json()
        differences = {}
        for method in ["embeddings", "tfidf"]:
            baseline = next(r for r in previous["runs"] if r["count"] == 36 and r["method"] == method)["first_search_results"]
            actual = payload["results"][method]
            assert [r["id"] for r in actual] == [r["id"] for r in baseline]
            delta = max(abs(a["score"] - b["score"]) for a, b in zip(actual, baseline))
            assert delta <= 1e-5
            differences[method] = delta
            by_id = {a.id: a for a in articles}
            assert all(r["passage"] == by_id[r["id"]].body[r["passage_start"]:r["passage_end"]] for r in actual)
        chunks = [p for a in articles for p in engine.passages(a)]
        assert all(p["text"] == by_id[p["article_id"]].body[p["start"]:p["end"]] for p in chunks)
        for article in articles:
            assert [p for p in chunks if p["article_id"] == article.id][-1]["end"] == len(article.body)
        assert client.post("/api/links", json={"source_id": "B01", "method": "compare"}).status_code == 200
        assert client.post("/api/overlaps", json={"method": "embeddings", "threshold": 0.65}).status_code == 200
        assert client.post("/api/reviews", json={"source_id": "B01", "target_id": "B02", "decision": "useful", "note": "Keep after rejected import"}).status_code == 200
        before = snapshot(client)
        cache_key, cached_vectors = engine.cache_key, engine.embeddings
        rejected = timed("reject_801_passages", lambda: client.post("/api/articles/import", json={"csv_text": dense_csv(True)}))
        assert rejected.status_code == 422 and "800 passages" in rejected.json()["detail"]
        assert snapshot(client) == before
        assert engine.cache_key == cache_key and engine.embeddings is cached_vectors
        # Actual tokenizer confirms the engineered boundary, not just a test double.
        exactly = parse_csv(dense_csv())
        assert sum(len(engine.passages(a)) for a in exactly) == 800
        too_many = parse_csv(dense_csv(True))
        assert sum(len(engine.passages(a)) for a in too_many) == 801
        accepted = timed("accept_800_passages", lambda: client.post("/api/articles/import", json={"csv_text": dense_csv()}))
        assert accepted.status_code == 200
        assert client.get("/api/reviews").json()["reviews"] == []
        engine.prepare(app.state.store.articles())
        assert len(engine.chunks) == 800
        assert client.post("/api/reviews", json={"source_id": "D0", "target_id": "D1", "decision": "useful"}).status_code == 200
        before_edit = snapshot(client)
        edited = next(a for a in app.state.store.articles() if a.id == "D0").model_dump()
        edited["body"] += "x"
        edit = timed("reject_edit_801_passages", lambda: client.put("/api/articles/D0", json=edited))
        assert edit.status_code == 422 and snapshot(client) == before_edit
    protected = json.loads((OUT / "preservation-before.json").read_text(encoding="utf-8"))
    changed = [name for name, digest in protected.items() if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    assert not changed, changed
    result = {"baseline_commit": "8e2c99198d42a05696b0b362ef851c1c8932e559",
              "implementation": "Phase 2A working tree; no implementation commit created",
              "model_revision": engine.revision, "threads": 2, "offline": True,
              "measurements": measured, "corpus_preflight": summary,
              "real_tokenizer_boundary": {"accepted_passages": 800, "rejected_passages": 801},
              "phase1b_top5_ids_equal": True, "max_score_differences": differences,
              "real_offsets_and_tails_checked": len(chunks), "failed_import_and_edit_preserve_reviews": True,
              "cache_preserved_on_rejection": True, "protected_files_checked": len(protected), "changed_protected_files": changed}
    (OUT / "real-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
