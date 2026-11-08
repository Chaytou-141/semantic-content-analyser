"""Real-model baseline, isolated from the application database.

Run with the project venv: python -B benchmarks/phase1b/run_benchmark.py
No API import, network fetch, package install, or changes to application limits.
Fresh subprocesses distinguish process-cold/model-cache-warm from index-warm work.
"""

import argparse
import csv
import ctypes
import hashlib
import importlib.metadata
import json
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "runtime/phase1b"


def memory():
    """OS current/peak working set and private commit; no psutil dependency."""
    if os.name == "nt":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in ["PeakWorkingSetSize", "WorkingSetSize",
                "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage"]]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"rss_bytes": counters.WorkingSetSize, "peak_rss_bytes": counters.PeakWorkingSetSize,
                "private_bytes": counters.PrivateUsage, "peak_commit_bytes": counters.PeakPagefileUsage}
    import resource
    scale = 1 if sys.platform == "darwin" else 1024
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale
    rss = peak
    if Path("/proc/self/statm").exists():
        rss = int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    return {"rss_bytes": rss, "peak_rss_bytes": peak}


class Meter:
    def __init__(self):
        self.rows = []

    def run(self, name, function):
        stop = threading.Event()
        samples = [memory()["rss_bytes"]]

        def sample():
            while not stop.wait(0.02):
                samples.append(memory()["rss_bytes"])

        thread = threading.Thread(target=sample, daemon=True)
        thread.start()
        start, cpu = time.perf_counter(), time.process_time()
        try:
            value = function()
        finally:
            duration, cpu_duration = time.perf_counter() - start, time.process_time() - cpu
            stop.set()
            thread.join()
            end_memory = memory()
            self.rows.append({"operation": name, "wall_s": duration, "cpu_s": cpu_duration,
                              "sampled_peak_rss_bytes": max(samples + [end_memory["rss_bytes"]]),
                              **end_memory})
        print(f"{name}: {duration:.3f}s wall, {cpu_duration:.3f}s CPU", flush=True)
        return value


def configure_environment():
    for key in ["OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
        os.environ[key] = "2"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.path.insert(0, str(ROOT))


def worker(count, method):
    configure_environment()
    meter = Meter()

    def imports():
        global np, torch, AnalysisEngine, Article, validate_collection, cosine_similarity
        import numpy as np
        import torch
        from sklearn.metrics.pairwise import cosine_similarity
        from semantic_analyser.engine import AnalysisEngine
        from semantic_analyser.schemas import Article
        from semantic_analyser.storage import validate_collection
        torch.set_num_threads(2)
        torch.set_num_interop_threads(1)

    meter.run("imports_and_thread_configuration", imports)
    raw = list(csv.DictReader((HERE / "articles.csv").open(encoding="utf-8", newline="")))[:count]
    articles = [Article(**{**r, "eligible": r["eligible"] == "true", "existing_links": []}) for r in raw]
    engine = AnalysisEngine()
    query = "How should two baristas arrange the grinder, espresso machine and milk workspace to avoid crossing paths?"
    query2 = "How can I check a website backup by restoring files and the database in an isolated environment?"

    def accepted(collection):
        try:
            validate_collection(collection)
            return {"accepted": True}
        except ValueError as error:
            return {"accepted": False, "reason": str(error)}

    capacity = {"collection": accepted(articles), "title_body_characters": sum(len(a.title) + len(a.body) for a in articles)}
    meter.run("load_model_from_local_disk_cache", engine.load)
    per_article = meter.run("tokenize_capacity_and_offsets", lambda: [len(engine.passages(a)) for a in articles])
    capacity.update({"passages": sum(per_article), "passage_counts": dict(zip([a.id for a in articles], per_article)),
                     "words": {a.id: len(a.body.split()) for a in articles},
                     "each_article_schema_valid": True, "passage_limit_accepted": sum(per_article) <= 800})
    prefix = []
    for article in articles:
        if not accepted(prefix + [article])["accepted"]:
            break
        prefix.append(article)
    capacity["largest_valid_ordered_prefix"] = len(prefix)
    # Explicit diagnostic: engine methods don't call validate_collection. This
    # measures the requested count even if HTTP import would reject its size.
    meter.run("prepare_passages_and_tfidf", lambda: engine.prepare(articles))
    if method == "embeddings":
        vectors = meter.run("encode_collection_first_time", engine.semantic_vectors)
        capacity["embedding_shape"] = list(vectors.shape)
        capacity["embedding_bytes"] = vectors.nbytes
    cold = meter.run("first_search_after_index", lambda: engine.search(articles, query, method, 5, 0))
    warm = []
    for i in range(5):
        warm.append(meter.run(f"warm_search_{i + 1}", lambda: engine.search(articles, query if i % 2 == 0 else query2, method, 5, 0)))
    link_results = meter.run("links_first", lambda: engine.links(articles, "B01", method, 5, 0))
    for i in range(3):
        meter.run(f"links_warm_{i + 1}", lambda: engine.links(articles, "B01", method, 5, 0))
    overlap_results = meter.run("overlaps_first", lambda: engine.overlaps(articles, method, 0.65, 20))
    for i in range(3):
        meter.run(f"overlaps_warm_{i + 1}", lambda: engine.overlaps(articles, method, 0.65, 20))

    # Same exact vectors, benchmark-only candidate computation. Not a new scorer.
    source_positions = [i for i, p in enumerate(engine.chunks) if p["article_id"] == "B01"]
    if method == "embeddings":
        vectors = engine.semantic_vectors()
        full = meter.run("diagnostic_full_similarity_matrix", lambda: vectors @ vectors.T)
        narrow = meter.run("diagnostic_source_only_matrix", lambda: vectors[source_positions] @ vectors.T)
    else:
        vectors = engine.word_vectors
        full = meter.run("diagnostic_full_similarity_matrix", lambda: cosine_similarity(vectors, vectors))
        narrow = meter.run("diagnostic_source_only_matrix", lambda: cosine_similarity(vectors[source_positions], vectors))
    matrix = {"full_shape": list(full.shape), "full_bytes": full.nbytes,
              "source_shape": list(narrow.shape), "source_bytes": narrow.nbytes,
              "same_source_scores": bool(np.allclose(full[source_positions], narrow, atol=1e-6))}

    # Targeted failure probes: a short unrelated cycling article grows in length;
    # a separate version gets one deliberately planted relevant cafe paragraph.
    # These are stress cases with known construction, NOT human relevance labels.
    probes = []
    baseline_memory = memory()
    cyclist = next(a for a in articles if a.id == "B24")
    paragraphs = cyclist.body.split("\n\n")
    relevant = "Arrange the espresso machine, grinder and milk workspace in a single preparation zone. Two baristas should be able to reach cups and milk without crossing paths. Keep the order collection point away from the grinder and the steaming area."
    for length in sorted({4, 12, len(paragraphs)}):
        base = "\n\n".join(paragraphs[:length])
        for planted in [False, True]:
            distractor = Article(id="DISTRACTOR", title="Planning an ordinary bicycle commute", body=base + ("\n\n" + relevant if planted else ""), topic="cycling")
            collection = [a for a in articles if a.id != cyclist.id] + [distractor]
            ranking = engine.search(collection, query, method, 20, 0)
            scores = engine.scores(query, method)
            positions = [i for i, p in enumerate(engine.chunks) if p["article_id"] == distractor.id]
            best = max(positions, key=lambda i: float(scores[i]))
            probes.append({"body_words": len(distractor.body.split()), "planted_cafe_paragraph": planted,
                           "passages": len(positions), "max_similarity": float(scores[best]),
                           "mean_similarity": float(np.mean(scores[positions])),
                           "fraction_passages_ge_0_5": float(np.mean(scores[positions] >= 0.5)),
                           "rank_in_top20": next((i + 1 for i, r in enumerate(ranking) if r["id"] == distractor.id), None),
                           "best_passage": engine.chunks[best]["text"]})

    result = {"count": count, "method": method, "capacity": capacity, "measurements": meter.rows,
              "matrix_diagnostic": matrix, "synthetic_false_positive_probes": probes,
              "first_search_results": cold, "warm_search_results": warm,
              "link_results": link_results, "overlap_results": overlap_results,
              "baseline_process_memory_before_probes": baseline_memory,
              "final_process_memory": memory(),
              "versions": {p: importlib.metadata.version(p) for p in ["torch", "sentence-transformers", "transformers", "numpy", "scikit-learn"]}}
    (OUTPUT / f"{count}-{method}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def run_all():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    start = time.perf_counter()
    for count in [30, 36]:
        for method in ["tfidf", "embeddings"]:
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", "--count", str(count), "--method", method]
            with (OUTPUT / f"{count}-{method}.log").open("w", encoding="utf-8") as log:
                completed = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
            if completed.returncode:
                raise RuntimeError(f"Worker failed: {count}-{method}; see its log")
            print(f"Finished {count} {method}", flush=True)
    bundle = {"base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version, "logical_cpus": os.cpu_count(),
              "threads": {"torch_intraop": 2, "torch_interop": 1, "OMP_MKL_OPENBLAS": 2},
              "offline_model_cache": True, "wall_seconds_all_workers": time.perf_counter() - start,
              "corpus_sha256": hashlib.sha256((HERE / "articles.csv").read_bytes()).hexdigest(),
              "runs": [json.loads((OUTPUT / f"{n}-{m}.json").read_text(encoding="utf-8"))
                       for n in [30, 36] for m in ["tfidf", "embeddings"]]}
    (HERE / "results.json").write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    for run in bundle["runs"]:
        rows = run["measurements"]
        print(run["count"], run["method"], "chars", run["capacity"]["title_body_characters"],
              "passages", run["capacity"]["passages"], "import", run["capacity"]["collection"])
        for prefix in ["warm_search_", "links_warm_", "overlaps_warm_"]:
            print(prefix, "median wall", statistics.median(r["wall_s"] for r in rows if r["operation"].startswith(prefix)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--count", type=int, default=36)
    parser.add_argument("--method", choices=["embeddings", "tfidf"], default="embeddings")
    options = parser.parse_args()
    if options.worker:
        worker(options.count, options.method)
    else:
        run_all()
