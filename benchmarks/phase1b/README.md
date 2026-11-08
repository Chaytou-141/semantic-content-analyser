# Phase 1B engineering benchmark

This directory is separate from `data/synthetic_articles.csv`, the saved development
labels/rankings, and the application database. No production application, infrastructure
or crawler implementation is changed by this work.

## Corpus and scope

`articles.csv` contains 36 original synthetic blog articles across cafe operations,
bakery production, community gardening, cycle commuting, website maintenance and
freelance project management. Lengths span 641–1,363 whitespace-separated body words.
`manifest.json` records provenance, lengths and the exact CSV hash.

The prose is intentionally correlated: sibling articles share topic sections and
process templates. This exercises long inputs, related material and repeated passages.
It is a realistic-length engineering fixture, **not** an independent sample of web
writing or an editorially labelled recommendation-quality benchmark. No external
website/customer text was copied or fetched. `.invalid` URLs are metadata only.

## Reproduce on the existing Windows environment

From the repository root, using the existing project virtual environment:

```powershell
# Regenerate only the separate fixture (not necessary to run the saved fixture).
.\.venv\Scripts\python.exe -B benchmarks\phase1b\build_corpus.py

# Model must already exist in the local Hugging Face cache; network is disabled.
.\.venv\Scripts\python.exe -B benchmarks\phase1b\run_benchmark.py
```

The benchmark uses fresh sequential child processes for 30 and 36 articles, each
with TF-IDF and MiniLM. CPU settings are explicit: two intra-op/BLAS threads, one
PyTorch inter-op thread, tokenizer parallelism disabled. This is a controlled
Windows baseline, not a measurement of unconfigured local defaults or AWS capacity.
Imports, cached-file model loading, tokenization, TF-IDF fitting, first embedding,
five warm searches and three warm link/overlap calls are measured separately.

"Cold" means a fresh Python process with model files already cached and potentially
warm OS file pages. It does not mean a reboot, cleared disk cache or model download.
The five warm searches alternate two questions; collection embeddings/TF-IDF are
reused, but query embeddings are not cached. No concurrency/load benchmark is claimed.

`time.perf_counter()` measures elapsed time. `time.process_time()` measures summed
process CPU time, which may exceed wall time with multiple threads. Windows
GetProcessMemoryInfo provides current/OS lifetime peak working set and peak commit;
a 20 ms sampler approximates the RSS peak of each operation. Small CPU timings can
quantize to zero and sampled per-operation peaks can miss short spikes. RSS includes
shared libraries and is not total host memory. Use OS lifetime peak and private/commit
counters alongside sampled RSS. All values are bytes/seconds in the raw JSON.

`results.json` is the portable measured record. Per-worker logs/raw files go to
ignored `runtime/phase1b/`. No new runtime dependency is required. CPU/memory
instrumentation is native Windows ctypes with a Unix resource fallback.

The source-only matrix experiment uses the exact same cached vectors and checks
numerical equivalence against the current full matrix. It does not replace the
production scorer. The false-positive probes append one deliberately relevant
espresso paragraph to a cycling article at different prefix lengths. Their rankings
show sensitivity to article composition, not a measured population false-positive rate.

## Regression verification

Before the verification script, capture preservation hashes for the existing files
and database files (the recorded run did this before any execution):

```powershell
@'
import hashlib, json, pathlib, subprocess
names = subprocess.check_output(['git','ls-files','data','labels','docs','semantic_analyser','web','infra','deploy'], text=True).splitlines()
names += [str(p) for p in pathlib.Path('runtime').glob('workspace.sqlite3*') if p.is_file()]
out = pathlib.Path('runtime/phase1b'); out.mkdir(parents=True, exist_ok=True)
(out / 'preservation-before.json').write_text(json.dumps({n: hashlib.sha256(pathlib.Path(n).read_bytes()).hexdigest() for n in names}), encoding='utf-8')
'@ | .\.venv\Scripts\python.exe -B -

.\.venv\Scripts\python.exe -B benchmarks\phase1b\verify_baseline.py
```

The verification runs the existing pytest suite and browser smoke script, then real
36-article HTTP checks. It explicitly sets DATABASE_PATH **before API import**, so
the module-level application cannot initialise the existing database. A disposable
server binds to 127.0.0.1:8011 and is terminated afterward. Browser screenshots are
redirected to the new verification working directory; old screenshots are preserved.
The script intentionally mutates only its disposable workspace and tests delayed
passage-limit rejection with a token-dense engineering input. `verification.json`
contains the results, including real-tokenizer offset/tail checks and capacity probes.
The capacity probes duplicate prose solely to explore limits; they are not quality data.

Running verification creates test files in `runtime/phase1b/verification/`. Do not run
the original browser smoke script against an important workspace: it saves a review.
Do not run performance and verification scripts simultaneously if comparing timings.

See `docs/phase1b-engineering-baseline.md` for findings and the proposed release path.
