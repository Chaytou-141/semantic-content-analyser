"""Exercise unchanged application/tests against new disposable databases only."""

import csv
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "runtime/phase1b/verification"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, "DATABASE_PATH": str(OUT / "api-bootstrap.sqlite3"),
                   "APP_ENV": "development", "APP_PASSWORD": "", "SECRET_KEY": "",
                   "PRELOAD_MODEL": "false", "PYTHONDONTWRITEBYTECODE": "1",
                   "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                   "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2",
                   "TOKENIZERS_PARALLELISM": "false", "PYTHONPATH": str(ROOT)}
    results = {}

    def command(name, args, cwd=ROOT):
        completed = subprocess.run(args, cwd=cwd, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
        (OUT / f"{name}.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        results[name] = {"exit_code": completed.returncode, "output": completed.stdout + completed.stderr}
        if completed.returncode:
            raise RuntimeError(f"{name} failed; see {OUT / (name + '.log')}")
        print(name, "passed", flush=True)

    command("pytest", [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "--basetemp", str(OUT / "pytest-temp")])
    command("javascript", ["node", "--check", "web/app.js"])
    port = 8011
    with socket.socket() as check:
        check.bind(("127.0.0.1", port))
    origin = f"http://127.0.0.1:{port}"

    def request(path, data=None):
        raw = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(origin + path, data=raw, headers={"Content-Type": "application/json", "X-Workspace-Request": "true"})
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    with (OUT / "server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn", "semantic_analyser.api:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(120):
                if server.poll() is not None:
                    raise RuntimeError("Isolated verification server exited")
                try:
                    if request("/health")[0] == 200:
                        break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.5)
            else:
                raise RuntimeError("Server startup timeout")
            browser_dir = OUT / "browser"
            browser_dir.mkdir(exist_ok=True)
            command("browser", [sys.executable, "-B", str(ROOT / "scripts/browser_smoke.py"), "--url", origin], browser_dir)
            text = (HERE / "articles.csv").read_text(encoding="utf-8")
            status, imported = request("/api/articles/import", {"csv_text": text})
            assert status == 200 and imported["count"] == 36
            original = list(csv.DictReader(io.StringIO(text)))
            by_id = {row["id"]: row for row in original}
            status, search = request("/api/search", {"query": "arranging an espresso machine and grinder for two baristas", "method": "compare", "top_k": 5})
            assert status == 200
            for group in search["results"].values():
                assert len({r["id"] for r in group}) == len(group) == 5
                for row in group:
                    assert row["passage"] == by_id[row["id"]]["body"][row["passage_start"]:row["passage_end"]]
            status, links = request("/api/links", {"source_id": "B01", "method": "compare", "top_k": 5})
            assert status == 200
            for group in links["results"].values():
                assert all(r["id"] != "B01" for r in group["results"])
                for row in group["results"]:
                    assert row["source_passage"] == by_id["B01"]["body"][row["source_start"]:row["source_end"]]
            status, overlaps = request("/api/overlaps", {"method": "embeddings", "threshold": 0.65, "limit": 20})
            assert status == 200 and len(overlaps["pairs"]) <= 20
            results["real_model_http_36_articles"] = {"passed": True, "search": search, "links": links, "overlaps": overlaps}

            # Validate real tokenizer boundaries without changing production code.
            capacity = subprocess.run([sys.executable, "-B", str(HERE / "verify_capacity.py")], cwd=ROOT, env=environment, capture_output=True, text=True)
            (OUT / "capacity.log").write_text(capacity.stdout + capacity.stderr, encoding="utf-8")
            assert capacity.returncode == 0, capacity.stderr
            results["capacity"] = json.loads(capacity.stdout)

            # Character-valid but token-dense input exposes the existing delayed
            # passage-limit rejection. All writes stay in this throwaway database.
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow(["id", "title", "body"])
            for index in range(30):
                writer.writerow([f"STRESS{index}", "Token dense boundary fixture", "x-" * 3000])
            import_status, import_payload = request("/api/articles/import", {"csv_text": stream.getvalue()})
            analysis_status, analysis_payload = request("/api/search", {"query": "boundary check", "method": "tfidf"})
            assert import_status == 200 and analysis_status == 422 and "800 passages" in analysis_payload["detail"]
            results["token_dense_boundary"] = {"import_status": import_status, "analysis_status": analysis_status, "detail": analysis_payload}
        finally:
            server.terminate()
            server.wait(timeout=30)
    protected = json.loads((ROOT / "runtime/phase1b/preservation-before.json").read_text(encoding="utf-8"))
    changes = [name for name, digest in protected.items() if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    results["preservation"] = {"checked_files": len(protected), "changed": changes}
    assert not changes, changes
    (HERE / "verification.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print("36-article real API, capacity, delayed passage rejection and preservation checks passed")


if __name__ == "__main__":
    main()
