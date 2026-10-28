"""Real-model and independent Chromium-session verification on disposable data.

No deployment, external website access, changes to old databases, or Phase 1B writes.
"""

import asyncio
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runtime/phase2b/real"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
os.environ.update({"DATABASE_PATH": str(OUT / "bootstrap.sqlite3"), "WORKSPACE_MODE": "local",
                   "APP_ENV": "development", "APP_PASSWORD": "", "PRELOAD_MODEL": "false",
                   "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "OMP_NUM_THREADS": "2",
                   "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "TOKENIZERS_PARALLELISM": "false"})

import torch
import uvicorn
from playwright.async_api import async_playwright, expect

from benchmarks.phase1b.run_benchmark import memory
from semantic_analyser.api import create_app
from semantic_analyser.config import Settings
from semantic_analyser.engine import AnalysisEngine


class CountingEngine(AnalysisEngine):
    loads = 0

    def load(self):
        with self.lock:
            was_missing = self.model is None
            model = super().load()
            if was_missing:
                self.loads += 1
            return model


async def check(app, shared):
    base = "http://127.0.0.1:8013"
    raw = (ROOT / "benchmarks/phase1b/articles.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(raw)))
    second = io.StringIO()
    writer = csv.DictWriter(second, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows({**r, "id": "V" + r["id"]} for r in rows)
    baseline = json.loads((ROOT / "benchmarks/phase1b/results.json").read_text(encoding="utf-8"))
    result = {"phase2a_commit": "3ea9b59", "real_model": True, "offline": True, "torch_threads": 2}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chromium", args=["--disable-gpu"])
        a, b = await browser.new_context(), await browser.new_context()
        page_a, page_b = await a.new_page(), await b.new_page()
        errors = []
        for page in [page_a, page_b]:
            page.on("pageerror", lambda error: errors.append(str(error)))
        await asyncio.gather(page_a.goto(base), page_b.goto(base))
        await expect(page_a.locator("#collection-count")).to_have_text("21 articles in your collection")
        await expect(page_b.locator("#collection-count")).to_have_text("21 articles in your collection")
        assert "own temporary workspace" in await page_a.locator("#workspace-notice").inner_text()

        async def revision(context):
            response = await context.request.get(base + "/api/articles")
            assert response.status == 200
            return (await response.json())["collection_revision"]

        async def post(context, path, payload, rev):
            return await context.request.post(base + path, data=payload, headers={"X-Workspace-Request": "true", "If-Match": rev})

        ar, br = await asyncio.gather(revision(a), revision(b))
        begin = time.perf_counter()
        imported = await asyncio.gather(post(a, "/api/articles/import", {"csv_text": raw}, ar),
                                        post(b, "/api/articles/import", {"csv_text": second.getvalue()}, br))
        assert all(r.status == 200 for r in imported)
        result["concurrent_import_wall_seconds"] = time.perf_counter() - begin
        ar, br = [(await r.json())["collection_revision"] for r in imported]
        after_preflight = memory()
        query = "How should two baristas arrange the grinder, espresso machine and milk workspace to avoid crossing paths?"
        begin = time.perf_counter()
        searched = await asyncio.gather(post(a, "/api/search", {"query": query, "method": "compare"}, ar),
                                       post(b, "/api/search", {"query": query, "method": "compare"}, br))
        result["two_queued_real_comparisons_wall_seconds"] = time.perf_counter() - begin
        assert all(r.status == 200 for r in searched)
        results = [await r.json() for r in searched]
        evidence_checked = 0
        for i, payload in enumerate(results):
            bodies = {("V" if i else "") + row["id"]: row["body"] for row in rows}
            for method in ["embeddings", "tfidf"]:
                old = next(r for r in baseline["runs"] if r["count"] == 36 and r["method"] == method)["first_search_results"]
                assert [r["id"] for r in payload["results"][method]] == [("V" if i else "") + r["id"] for r in old]
                assert max(abs(x["score"] - y["score"]) for x, y in zip(payload["results"][method], old)) <= 1e-5
                for row in payload["results"][method]:
                    assert row["passage"] == bodies[row["id"]][row["passage_start"]:row["passage_end"]]
                    evidence_checked += 1
        entries = [e for e in app.state.workspaces.entries.values() if e.engine.cache_key]
        assert len(entries) == 2
        assert entries[0].engine.model is entries[1].engine.model is shared.model
        assert entries[0].engine.embeddings is not entries[1].engine.embeddings
        pointers = [next(e.engine.model.parameters()).untyped_storage().data_ptr() for e in entries]
        assert pointers[0] == pointers[1]
        result.update({"model_constructions": shared.loads, "same_parameter_storage": True,
                       "independent_embedding_arrays": True, "phase1b_top5_ids_scores_preserved": True,
                       "memory_after_preflight": after_preflight, "memory_after_two_indexes": memory()})
        assert shared.loads == 1
        bodies = {row["id"]: row["body"] for row in rows}
        linked = await post(a, "/api/links", {"source_id": "B01", "method": "compare"}, ar)
        assert linked.status == 200
        for group in (await linked.json())["results"].values():
            for row in group["results"]:
                assert row["source_passage"] == bodies["B01"][row["source_start"]:row["source_end"]]
                assert row["passage"] == bodies[row["id"]][row["passage_start"]:row["passage_end"]]
        overlapping = await post(a, "/api/overlaps", {"method": "embeddings", "threshold": .65}, ar)
        assert overlapping.status == 200
        for pair in (await overlapping.json())["pairs"]:
            for row in [pair["left"], pair["right"]]:
                assert row["passage"] == bodies[row["id"]][row["passage_start"]:row["passage_end"]]
        result["real_search_evidence_checked"] = evidence_checked
        result["real_link_and_overlap_evidence"] = "passed"
        # The two actual browser contexts own different articles and exports.
        exported_b = await (await b.request.get(base + "/api/articles/export")).text()
        assert "VB01" in exported_b
        attack = await b.request.put(base + "/api/articles/B01", data={"id": "B01", "title": "Attack", "body": "Alter another visitor"},
                                     headers={"X-Workspace-Request": "true", "If-Match": br})
        assert attack.status == 404
        attempt = await post(b, "/api/reviews", {"source_id": "B01", "target_id": "B02", "decision": "useful"}, br)
        assert attempt.status == 404

        # Render real link results, then invalidate their revision from another tab/request.
        await page_a.reload()
        await expect(page_a.locator("#collection-count")).to_have_text("36 articles in your collection")
        await page_a.get_by_role("link", name="Link opportunities", exact=False).click()
        await page_a.locator("#links-source").select_option("B01")
        await page_a.locator("#links-form").get_by_role("button", name="Find opportunities").click()
        await expect(page_a.locator("#links-results .result-card")).to_have_count(5, timeout=60000)
        article = (await (await a.request.get(base + "/api/articles")).json())["articles"][0]
        article["title"] = "A-only edited coffee station"
        edited = await a.request.put(base + "/api/articles/B01", data=article,
                                    headers={"X-Workspace-Request": "true", "If-Match": ar})
        assert edited.status == 200
        ar = (await edited.json())["collection_revision"]
        await page_a.locator("#links-results .result-card").first.get_by_role("button", name="Useful candidate", exact=True).click()
        await expect(page_a.locator("#app-error")).to_contain_text("Collection changed")
        assert (await (await a.request.get(base + "/api/reviews")).json())["reviews"] == []
        exported_b = await (await b.request.get(base + "/api/articles/export")).text()
        assert "A-only edited" not in exported_b
        result["browser_stale_review_rejected"] = True

        dense = io.StringIO()
        writer = csv.writer(dense)
        writer.writerow(["id", "title", "body"])
        for index in range(100):
            writer.writerow([f"D{index}", "Boundary title", "x-" * 656 + ("x" if index == 0 else "")])
        before = await (await a.request.get(base + "/api/articles")).json()
        rejection = await post(a, "/api/articles/import", {"csv_text": dense.getvalue()}, ar)
        assert rejection.status == 422 and "800 passages" in (await rejection.json())["detail"]
        assert await (await a.request.get(base + "/api/articles")).json() == before
        result["real_801_passage_rejection_preserves_revision_and_data"] = True
        valid_dense = dense.getvalue().replace("x-" * 656 + "x", "x-" * 656, 1)
        accepted = await post(a, "/api/articles/import", {"csv_text": valid_dense}, ar)
        assert accepted.status == 200
        ar = (await accepted.json())["collection_revision"]
        result["real_800_passage_import"] = "accepted"

        # Delete can only target the request's own workspace, regardless of supplied ID.
        deleted = await a.request.delete(base + "/api/workspace?workspace_id=other", headers={"X-Workspace-Request": "true", "If-Match": ar})
        assert deleted.status == 200
        assert (await b.request.get(base + "/api/articles")).status == 200
        result["independent_browser_contexts"] = 2
        result["cross_session_read_write_review_export_delete_checks"] = "passed"
        result["browser_errors"] = errors
        assert not errors
        await browser.close()
    return result


def main():
    guard = ROOT / "runtime/phase2b/preservation-before.json"
    if not guard.exists():
        paths = [p for base in ["data", "labels", "benchmarks", "infra", "deploy"]
                 for p in (ROOT / base).rglob("*") if p.is_file() and ".terraform" not in p.parts]
        paths += [p for p in (ROOT / "runtime").rglob("*.sqlite3*") if p.is_file() and "phase2b" not in p.parts]
        guard.write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in paths}, indent=2), encoding="utf-8")
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    shared = CountingEngine()
    settings = Settings(database_path=OUT / "never-open-local.sqlite3", visitor_root=OUT / f"workspaces-{time.time_ns()}",
                        workspace_mode="visitor", secret="verification-only-ephemeral-key-" * 2,
                        password="", production=False, preload_model=False)
    app = create_app(settings, shared)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8013, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(200):
            if server.started:
                break
            if not thread.is_alive():
                raise RuntimeError("Verification server failed to start")
            time.sleep(.1)
        else:
            raise RuntimeError("Verification startup timeout")
        result = asyncio.run(check(app, shared))
        smoke = OUT / "ui-smoke"
        smoke.mkdir(exist_ok=True)
        completed = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/browser_smoke.py"), "--url", "http://127.0.0.1:8013"],
                                   cwd=smoke, capture_output=True, text=True, encoding="utf-8", errors="replace")
        (OUT / "browser-smoke.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        assert completed.returncode == 0, completed.stdout + completed.stderr
        result["existing_browser_smoke"] = "passed in visitor mode"
        result["model_constructions_after_smoke"] = shared.loads
        result["final_process_memory"] = memory()
        assert shared.loads == 1
    finally:
        server.should_exit = True
        thread.join(timeout=90)
        assert not thread.is_alive(), "Verification server did not stop"
    guard = ROOT / "runtime/phase2b/preservation-before.json"
    protected = json.loads(guard.read_text(encoding="utf-8"))
    changed = [name for name, digest in protected.items() if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    assert not changed, changed
    result.update({"protected_files_checked": len(protected), "changed_protected_files": changed,
                   "server_stopped": True, "existing_local_database_opened": False})
    (OUT / "results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
