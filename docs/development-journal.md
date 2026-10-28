# Development journal

## Phase 2A — atomic collection validation and reliability

Date: 28 October 2026 (Australia/Sydney).

Baseline Git commit: `8e2c99198d42a05696b0b362ef851c1c8932e559`
(`Redesign content review workspace and improve accessibility`), on
`feature/deployable-aws-app`. Phase 1B fixtures/results were already present in the
working tree when this phase started. Phase 2A is an **uncommitted working-tree
implementation prepared for review**; there is no new implementation commit hash
to report yet. No commit or push was performed for this phase.

### Problem and user impact

Phase 1B reproduced a collection that passed CSV/schema/character validation but
exceeded the engine's 800-passage limit. Import returned success and replaced the
saved collection, clearing editorial reviews. Analysis then returned 422. A valid
article edit could similarly move the collection over the limit and invalidate
related reviews before a later analysis discovered the problem.

For a user, successful import should mean the collection meets the application's
known input constraints. It should not discard a usable collection and its editorial
decisions merely to discover a predictable capacity problem on the next action.
The same contract is needed for eventual website-selected articles, not only CSV.

### Root cause in the previous implementation

`storage.parse_csv()` and `validate_collection()` checked schema fields, unique IDs,
article count, total characters and known existing-link IDs. `Store.replace()` then
replaced articles and cleared reviews in a transaction. Passage count, tokenisable
content and TF-IDF vocabulary were checked separately by `AnalysisEngine.prepare()`
when analysis was requested. The database transaction was atomic, but admission was
incomplete. The problem was the validation boundary, not missing SQLite rollback.

### Alternatives considered

1. **Raise the limits:** does not repair inconsistent admission. Phase 1B only measured
   one local laptop and synthetic length fixtures, not concurrent hosting capacity.
2. **Add tokenization to CSV parsing:** catches that route but couples parsing to the
   model and leaves non-CSV selections and edits with separate admission rules.
3. **Call engine.prepare before every write:** reuses analysis checks but replaces the
   active cache before a successful database commit. A rejected write/database failure
   should not publish a candidate index as the current one.
4. **Build an independent passage counter:** risks divergence from real chunking,
   overlap, title prefix and tokenizer semantics, and misses vocabulary failures.
5. **Selected: format-independent service plus side-effect-free index preflight.**
   Reuse the actual passage/TF-IDF build code, then commit through existing transactions.

### Implementation

- `semantic_analyser/collections.py`: `CollectionService.preflight()` accepts Article
  instances or mappings, revalidates the schema even for constructed/mutated instances,
  applies the existing structural limits and calls engine preflight. `replace()` and
  `save_article()` serialize validation/writes with the same process mutation lock used
  by editorial review saves. They do not open a database write transaction during
  tokenization. Edits validate the complete resulting collection.
- `semantic_analyser/engine.py`: `_build_index()` is the shared local candidate builder
  used by analysis and preflight. It preserves the existing passage generation and
  TF-IDF configuration, rejects above 800 passages, and stops building further articles
  after that bound is exceeded. `preflight()` additionally checks the actual combined
  title/body input against 256 model tokens and returns article/character/passage counts.
  It does not encode embeddings or replace the active chunks, fingerprint or vectors.
- `semantic_analyser/api.py`: imports, demo resets and article updates use the service.
  Existing success response shapes are retained. Invalid candidates return 422 before
  persistence. Caught model I/O/runtime failures return a generic 503 with a retry message
  and no private error details. Storage exceptions still use the existing server-error
  behaviour; the transaction rolls back.
- `tests/test_collection_admission.py`: focused admission, boundary, cache-preservation,
  dependency-failure and transaction-rollback tests.
- `scripts/verify_phase2a.py`: reproducible offline real-MiniLM checks using new SQLite
  files under ignored `runtime/phase2a/`; never imports the API against the existing DB.
- `README.md`: explains the earlier model-loading point and atomic preflight behaviour.

The service is the future import boundary for selected website article mappings. There
is no website fetcher, new ingestion endpoint or visitor-isolation implementation here.
`Store` deliberately remains a low-level persistence layer; future adapters must use
the collection service rather than call Store mutation methods directly.

### Limits and trade-offs

Keep **250,000 title/body characters**, **100 articles**, **20,000 body characters per
article**, **800 passages**, existing request limits and the current model revision.
Phase 1B's 36 articles fit (238,142 characters, 269 passages), while a 40-article length
fixture exceeded characters with only 302 passages. This identifies a future policy
decision, not sufficient justification to increase a public-service limit today.

Preflight now requires the model/tokenizer on the first import, edit or reset. It fits
a temporary TF-IDF index and discards it, then analysis builds its normal cache later.
This duplicates a small amount of work and shifts model availability/loading cost to
admission. It avoids calculating embeddings merely to validate an import, avoids
publishing uncommitted candidate caches, and keeps one source of passage/vocabulary
rules. It does not change ranking formulas, chunk offsets, the model or the frontend.

### Validation performed

All runs used disposable databases. Environment DATABASE_PATH was set **before** API
import because the module-level app initializes a Store. No existing application server
was restarted. The UI smoke server used localhost port 8012 and was stopped afterward;
screenshots/logs were redirected to `runtime/phase2a/ui/`.

Automated coverage includes:

- Original API suite, including search, links, overlap, sessions and request bounds.
- 0/1/100/101 article boundaries and 249,999/250,000/250,001 character boundaries.
- Exactly 800 passages accepted and the next token creating passage 801 rejected.
- An edit that would cross the same passage boundary.
- Combined model-input boundary at 256/257 tokens using an explicit tokenizer fixture.
- Invalid schemas, duplicate IDs, unknown links, unsafe URL schemes, excessive body
  length, unsupported CSV columns and empty TF-IDF vocabulary.
- Failed admissions preserve the complete saved article and review snapshots.
- Successful replacements clear reviews and remain analysable by both methods.
- Non-CSV mappings and revalidation of constructed invalid Article instances.
- Preflight performs no embedding calls and preserves an existing analysis cache.
- Model I/O/runtime unavailability fails closed for imports, resets and edits.
- Injected SQLite triggers fail review deletion *after* an article replacement/update
  begins; both tests confirm rollback restores the original articles and reviews.

The fast suite uses the existing deterministic encoder/tokenizer plus explicit dense
tokenizer fixtures. These tests do not establish real model quality. Separate offline
checks exercised the actual pinned MiniLM tokenizer/model and HTTP routes:

| Check | Measured result |
| --- | --- |
| Original 36-article Phase 1B corpus | Accepted: 238,142 characters, 269 passages |
| First preflight/import, cached model files but model not loaded | 6.946 s wall; 6.250 s process CPU |
| Warm preflight, same corpus | 0.190 s wall; 0.188 s process CPU |
| First semantic/TF-IDF comparison after admission | 8.057 s wall; 15.828 s process CPU |
| Real-tokenizer boundary | 800 passages accepted; 801 rejected at import |
| Real over-limit edit | Rejected; articles/reviews preserved |
| Warm 801-passage rejection | 0.100 s wall |
| Warm 800-passage import | 0.219 s wall |
| One recorded Phase 1B query, top five | Identical IDs for both methods |
| Maximum saved top-five score difference | 0.0 for both methods |
| Original body evidence | All 269 passage offsets and final article tails preserved |
| Protected existing files | 48 hashed; none changed |

These are single local Windows observations on the Phase 1B laptop with two CPU
threads and local model files, not performance improvements, a latency SLA or a
recommendation-quality evaluation. First-request dependency imports occurred before
the preflight timer. Full JSON is in `runtime/phase2a/real-results.json`; original
Phase 1B JSON/Markdown results were not regenerated or overwritten.

Final execution: **45 tests passed in 3.65 seconds**, comprising the original 15 and
30 additional parametrized cases. JavaScript syntax and Git whitespace checks passed.
The unchanged latest UI browser smoke passed comparison search, link exclusions and
review saving, overlap, live filters, keyboard shortcut, editor/unsaved-change handling,
historical evaluation and mobile/import dialog. No uncaught browser error was reported.
The isolated server was stopped after the run. A portable verification record is saved
as `docs/phase2a-verification.json`.

### Reproduction

From project root, with the existing virtual environment and cached model:

```powershell
# Isolate the module-level app before pytest imports it.
$env:DATABASE_PATH = Join-Path $PWD 'runtime\phase2a\test-bootstrap.sqlite3'
$env:APP_ENV = 'development'
$env:APP_PASSWORD = ''
$env:PRELOAD_MODEL = 'false'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B scripts\verify_phase2a.py
node --check web/app.js
```

The real verification also checks the recorded preservation hashes. In a fresh checkout
without `runtime/phase2a/preservation-before.json`, it captures hashes of existing
`data/`, `labels/`, `benchmarks/phase1b/`, `web/`, `infra/`, `deploy/`, docs and
`runtime/workspace.sqlite3*` before its checks. It does not overwrite an existing guard.
For this development run the guard was captured before any implementation changes;
the new journal/results files were not part of that original 48-file snapshot.
The historical Phase 1B verification script intentionally expects the old delayed
rejection; use the Phase 2A script for the new admission contract rather than overwrite
Phase 1B results with a run against changed application behaviour.

### Remaining limitations and next task

- Admission verifies known input/analysis constraints, not available RAM, disk space,
  future model execution success, recommendation quality or deployment capacity.
- Pre-existing unsupported collections are not migrated or automatically replaced.
- Locks remain per-process. There is still one shared workspace, no cross-process
  authorization/coordination and no protection against direct out-of-band DB edits.
- Direct low-level Store callers can bypass engine admission; use CollectionService.
- New import/reset/edit operations may wait behind ongoing analysis or model loading.
- Temp preflight index construction is repeated at first analysis. No cache promotion,
  performance improvement or resource-capacity expansion is claimed.

Recommended next phase: per-visitor run ownership/isolation using temporary SQLite
workspaces, one shared model, bounded caches/queue and revision checks. Then implement
and adversarially test the safe-fetch boundary before WordPress discovery/extraction.
Website URL analysis remains a core release requirement; neither crawler nor visitor
isolation, cloud infrastructure or deployment was implemented during Phase 2A.
