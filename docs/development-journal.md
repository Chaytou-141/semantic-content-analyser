# Development journal

## Phase 2A — atomic collection validation and reliability

Date: 28 October 2026 (Australia/Sydney).

Baseline Git commit: `8e2c99198d42a05696b0b362ef851c1c8932e559`
(`Redesign content review workspace and improve accessibility`), on
`feature/deployable-aws-app`. Phase 1B fixtures/results were already present in the
working tree when this phase started. Phase 2A was initially prepared as an uncommitted
working-tree implementation. Before Phase 2B, its 45 tests were rerun (45 passed in
3.56 seconds) and reviewed changes were committed as `3ea9b59` (`Validate collection
admission atomically before persistence`). Supporting Phase 1B evidence was recorded
separately as `bc72066`. Neither commit was pushed.

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

## Phase 2B — per-visitor isolation and bounded execution

Date: 28 October 2026 (Australia/Sydney).

Prerequisites verified and committed locally: Phase 1B evidence `bc72066`; Phase 2A
`3ea9b59`. Phase 2A's reviewed source, tests, journal and verification record were staged
explicitly after a fresh 45-test pass. No secrets, runtime databases or cloud state were
staged. Neither commit was pushed. The Phase 2B development commit is titled
`Isolate visitor workspaces and bound analysis execution`; this entry is included in
that commit. Resolve its hash with `git log -1 --format=%H --grep="Isolate visitor workspaces"`.

### Problem and decision

The shared Store/engine meant every authorized visitor could replace the same collection
and read/edit the same reviews. Engine locking prevented cache races but did not provide
ownership. Unbounded submitted work could accumulate and stalled requests had no response
deadline. A saved review had no collection revision identifying the evidence it judged.

Selected design: preserve the persistent local mode, add explicit visitor mode with one
temporary SQLite file per cookie-owned visitor, share one read-only loaded model and keep
indexes separate. A finite single-worker executor bounds CPU/preflight work. Existing
CollectionService and SQLite transactions remain the write boundary.

Alternatives considered: shared tables with workspace IDs (more pervasive query scoping),
one database/model/process per visitor (unnecessary memory/startup cost), external accounts
or PostgreSQL/Redis (not required for this bounded single-node phase), and process-based
inference with forced termination (stronger native deadlines, substantially more lifecycle
and IPC complexity). Cookie-owned temporary files are the smallest fit for anonymous
portfolio visitors. They are not a complex or horizontally scalable tenant platform.

### Implementation and trade-offs

- `workspaces.py`: 256-bit random IDs; purpose-specific HMAC-SHA256 signed HttpOnly,
  SameSite cookies; production Secure/__Host- protection; cookie-only store selection.
  Each visitor gets the original fictional demo. Missing/tampered/expired ownership is
  rejected, and logout revokes it. No caller-provided path/ID selects another store.
- `api.py`: request-scoped workspace leases, owned reads/exports/reviews/deletion,
  revision preconditions, bounded execution, no-store API errors and expired-cookie
  handling. Local mode remains compatible with existing API callers; the UI sends
  revisions in both modes. Public visitors must use explicit visitor mode.
- `storage.py`: opaque metadata revision changes atomically with imports/edits; SQLite
  connections explicitly close; one-second busy wait; cancellation checks before commit.
- `execution.py`: one worker plus two pending slots by default; controlled 503/Retry-After,
  60-second response deadline, queued cancellation and leases retained for running native
  work after HTTP timeout. Writes check deadlines/expiry before committing. A tiny
  commit/acknowledgement race still requires client reconciliation, not automatic retries.
- Manager lifecycle: one-hour idle/24-hour absolute expiry, 60-second sweeps, max 32
  workspaces and four idle cached indexes. Active jobs protect their files. Safe cleanup
  recognizes only owned SQLite/sidecar files and refuses unexpected/symlink contents.
  An OS file lock prevents multiple application processes owning one root. Restart
  reloads unexpired data/revisions, clears indexes and does not resume pending requests.
- `engine.py`: only adds index eviction; passage segmentation, MiniLM normalization,
  TF-IDF and ranking formulas are unchanged. Visitor engine factories return the same
  loaded model object; their chunks/vectors are separate.
- `web/app.js`: propagates If-Match, retains the original revision for an editor/review,
  rejects stale results/actions and refreshes after conflicts. The interface and CSV
  workflows remain in place, with a temporary-data notice in visitor mode.

The original 250,000-character/800-passage limits remain. No crawler, visitor account
provider, PostgreSQL, Redis, infrastructure change or deployment is included.

### Test evidence and measurements

The portable record is `docs/phase2b-verification.json`; detailed architecture and
reproduction instructions are in `docs/phase2b-workspaces.md`. The final local suite
and real-model measurements are recorded there after execution. Test databases and
browser screenshots/logs live only under ignored runtime/phase2b.

Tests cover two or more isolated cookie sessions, cross-session reads/edits/reviews/
exports/deletion, malformed ownership, production cookie flags, exact revision conflicts,
parallel same/different workspace imports and analysis, a queued stale analysis after
an edit, overload, timed-out slot retention, queued cancellation, late-review rollback,
active cleanup protection, idle/absolute expiry, restart data/revision recovery, expired
restart cleanup, process locking and LRU eviction. A real Chromium stale review click
is rejected after a collection edit, with no editorial decision applied.

The real-model run uses two independent Chromium contexts and 36 articles each. It
checks exactly one MiniLM construction and shared parameter storage with separate
embedding arrays, Phase 1B ranking/score equivalence for one recorded query, exact
passage evidence and real-tokenizer 800/801 admission. These are engineering checks
on synthetic content, not a recommendation-quality or public-load evaluation.

### Limitations and next phase

Thread deadlines do not kill native PyTorch execution. Timed-out running work keeps its
slot and lease; a permanently stuck call can require a hard process restart. Graceful
shutdown waits for active work. There is no hard RAM sandbox, fair scheduling/per-IP
abuse policy, identity recovery, storage-corruption repair or sustained multi-user
capacity guarantee. Old tabs can show snapshot results until another request, but
revisions prevent stale reviews/edits in visitor mode. Local legacy callers that omit
If-Match retain their old trusted-demo semantics. Cleanup failures can need operator
attention; the workspace root must be private to the application's OS account.

Next: implement and adversarially test the bounded safe-fetch boundary before mandatory
WordPress discovery/extraction and article selection. Do not declare public readiness
from unit tests or the two-browser synthetic demonstration. No push is performed.

### Recorded local results

- Full suite: **71 passed, 1 skipped in 10.80 seconds**, including all 45 Phase 2A tests.
- The skipped test requires actual symlink creation, unavailable to this Windows account.
- Two independent Chromium contexts each imported 36 synthetic articles.
- Their concurrent import requests completed in **8.157 seconds** total, including the first cached-file model load.
- Two submitted real MiniLM/TF-IDF comparison requests completed in **17.245 seconds** total; native inference was intentionally serial.
- Model construction count: **1**; model parameter storage shared; embedding arrays distinct.
- Peak process working set after the two indexes: **719.02 MiB**; peak commit **817.72 MiB**. These exclude browser child processes and are not hosting-size guarantees.
- Both methods retained Phase 1B top-five IDs/scores for the recorded query (with the second visitor's ID prefix mapped).
- Exact search evidence: **20** returned passages checked, plus source/destination link and overlap evidence.
- Actual model tokenizer: **800 passages imported**, **801 rejected** without changing data/revision.
- Existing full browser smoke passed in both visitor mode and a separate disposable local-demo instance; no page errors.
- Preservation: **172 files** unchanged, including benchmark/deployment data and **145 older SQLite/sidecar files**.
- JavaScript syntax and Git whitespace checks passed. All verification servers were stopped.

These are single-laptop observations (Phase 1B i5-11400H Windows environment, two PyTorch threads, offline cached model), not sustained traffic measurements or accuracy claims.
