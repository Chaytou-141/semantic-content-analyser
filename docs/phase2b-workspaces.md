# Phase 2B — visitor workspace isolation and bounded execution

Date: 28 October 2026 (Australia/Sydney). Phase 2A prerequisite commit: `3ea9b59`.
Phase 2B implementation commit title: `Isolate visitor workspaces and bound analysis execution`.
Resolve its full hash with `git log -1 --format=%H --grep="Isolate visitor workspaces"`.
This report is committed with the implementation; no push or deployment is authorized.

## Scope and mode selection

The existing persistent local demonstration remains the default (`WORKSPACE_MODE=local`).
That mode opens the configured local SQLite file, uses the original demo articles and
preserves compatibility with old API clients that omit revisions. The browser supplies
revisions in both modes. Local mode is for loopback/trusted demonstrations, not independent
public visitors. Running the existing deployment template unchanged does not opt into
visitor isolation; this phase does not change that template or deploy anything.

`WORKSPACE_MODE=visitor` opts into temporary cookie-owned workspaces. A stable SECRET_KEY
of at least 32 characters is mandatory. The application does not open the local
DATABASE_PATH in this mode. The temporary root defaults to `<database parent>/visitors`,
or VISITOR_WORKSPACE_ROOT. Each visitor starts with a separate copy of the 21 fictional
articles, preserving the sample experience. CSV replacement affects only that visitor.

No PostgreSQL, Redis, external authentication, crawler or new cloud resource is introduced.
Website discovery/extraction remains a future mandatory release requirement.

## Ownership and data flow

1. Browser calls GET /api/session with X-Workspace-Request: true. A new authenticated
   visitor without an ownership cookie receives a workspace and signed cookie.
2. The manager generates 32 cryptographically random bytes encoded as 64 hex characters.
   A purpose-specific HMAC-SHA256 signature protects the identifier. Cookies are HttpOnly,
   SameSite=Strict and host-only. Production additionally uses Secure and the __Host-
   cookie prefix (path /, no Domain). Public visitor mode may omit the shared password;
   an optional configured workspace password still uses the existing sign-in gate.
3. Every workspace request resolves exclusively through the signed cookie. No query/body
   workspace ID, article ID or user-supplied filesystem path selects a different store.
   Invalid cookies return 401; missing/expired workspaces return 410 and clear the cookie.
   Error and normal API responses use no-store to avoid caching an expired session.
4. Requests lease the workspace. CPU operations acquire a second lease owned by the
   future, which outlives a timed-out HTTP response when native work is still running.
5. The entry owns a Store, a CollectionService, a reentrant lock and an AnalysisEngine.
   Articles, reviews, revisions and access timestamps live in that entry's SQLite file.
   Read/export/review/delete operations all use that same request-bound entry.
6. A process-wide base AnalysisEngine loads MiniLM once. Visitor engines use its load
   method as their model factory: the returned model object/weights are shared, while
   each visitor owns its own passage index, TF-IDF vectors and embedding array.

Cookie ownership is anonymous bearer access, not a user account or verified person.
Anyone who steals a complete valid cookie can impersonate its owner. HTTPS, a strong
stable key and the existing browser protections remain essential. Clearing browser
storage loses access; logout revokes the workspace, while cleanup waits for active work.
Key rotation invalidates old cookies; unexpired orphan data is eventually expired.

## Revision and mutation contract

The metadata table now stores an opaque random collection revision. Initialisation adds
it when a store is opened; no SQL table rebuild or article migration is required.
Replacement and article edits update it inside the same SQLite transaction as the
article/review changes. Failed transactions roll back the revision as well.

GET /api/articles and GET /api/reviews return collection_revision. Analysis results and
successful mutations include their revision. Visitor analysis/mutation/delete requests
must carry If-Match; missing revisions return 428 and mismatches return 409. The check
runs under the workspace lock when the operation actually starts, not merely when queued.
Two concurrent imports using one revision cannot both replace the collection.

Search and both methods of comparison run against one locked snapshot. Results are
evidence for that revision, not live subscriptions. The frontend retains the result's
revision for review buttons and the opening revision for article editors. A stale action
is rejected and collection/results are refreshed/invalidated. Other tabs can continue
displaying a prior snapshot until another request; they cannot apply a stale review or
edit using that snapshot. GET exports intentionally return the current owned collection.

Phase 2A preflight stays format-independent and atomic. It still checks the original
article, character, real-tokenizer passage, vocabulary and input constraints. This phase
does not raise the 250,000-character or 800-passage limits or alter similarity formulas.

## Execution limits and timeout semantics

Defaults:

| Control | Default |
| --- | --- |
| Native CPU/preflight worker | 1 per application |
| Pending operation capacity | 2, plus the active operation |
| HTTP operation deadline | 60 seconds including queue wait |
| Workspace lock wait | 1 second |
| SQLite busy wait | 1 second |
| Mutation body read deadline | 15 seconds; existing 2 MB byte bound retained |
| Visitor workspace count | 32 |
| Idle cached indexes | 4 (active/pinned indexes are not evicted) |
| Idle expiry | 1 hour |
| Absolute lifetime | 24 hours from creation |
| Expiry cleanup interval | 60 seconds |

Analysis, imports, edits, demo resets and review writes use one BoundedExecutor.
Admission to its ThreadPoolExecutor is guarded by a nonblocking finite semaphore;
the executor's otherwise unbounded queue cannot grow through this API. Full capacity
returns 503 with Retry-After: 2. Contended read/delete locks return 423 with a retry hint.
Workspace creation at the count cap returns 503 with Retry-After: 60.

The timeout is a **response/cooperative deadline**, not a hard CPU-time sandbox. Queued
timed-out jobs are cancelled. Running native inference cannot safely be killed by a
Python thread: its slot and lease stay occupied until it returns. Results arriving late
are discarded. Preflight/write operations check cancellation and expiry before writes
and immediately before transaction commit, including reviews. A timed-out preflight
therefore cannot subsequently replace the collection. As with ordinary HTTP mutations,
a deadline/disconnection at the tiny commit/acknowledgement boundary can leave an
uncertain client outcome; refresh revisions instead of automatically replaying writes.

A permanently stuck native call can leave the sole worker unavailable. Graceful shutdown
drains active work; a supervisor's hard process restart is the recovery for a true native
hang. A subprocess inference service with kill/restart semantics would be a separate
design if strict deadlines become a measured requirement. No hard RAM limit, per-IP
abuse protection or fair scheduling is claimed here.

## Expiration, cleanup and restart

Created/access timestamps persist in the existing metadata table. Activity updates the
idle clock without extending absolute lifetime. Expired workspaces refuse new requests.
Cleanup skips entries with active HTTP/job leases. Completion does not revive an expired
entry; a later sweep can delete it after the final lease is released.

Store.connect now explicitly commits/rolls back **and closes** each SQLite connection.
This matters on Windows: relying on garbage collection can retain handles and prevent
safe removal. Cleanup verifies the dedicated root/direct-child path, rejects symlinks,
and removes only workspace.sqlite3 and its WAL/SHM sidecars. Unexpected contents/errors
are logged and retained for inspection rather than recursively deleting arbitrary data.
The root must remain private to the application's OS account; this is not a defense
against an administrator changing files concurrently behind the process.

A kernel file lock permits one process to own the visitor root. A second owner fails
startup, preventing accidental multi-worker operation with independent Python locks.
After restart, unexpired text/reviews/revisions are reloaded under the same signing key,
expired workspaces are swept, and all indexes are cold. Pending HTTP work/results are
not persisted or resumed. Corrupted SQLite/metadata and unexpected directories are not
automatically repaired or removed. There is no recovery guarantee for arbitrary storage
corruption or a successful public deployment in this phase.

## Evidence and reproduction

Source map for independent review:

| File/function | Responsibility |
| --- | --- |
| `semantic_analyser/workspaces.py`, `WorkspaceManager.acquire/release` | Cookie ownership, persisted access times and leases |
| `workspaces.py`, `cleanup/_remove/start/close` | Expiry, guarded deletion, restart scan and process lock |
| `semantic_analyser/execution.py`, `BoundedExecutor.run`, `Deadline.check` | Queue admission, deadlines and late-work slot retention |
| `semantic_analyser/api.py`, `protect/execute/check_revision` | Request scoping and revision-checked execution |
| `api.py`, `delete_workspace/logout` | Owned deletion and revocation |
| `semantic_analyser/storage.py`, `connect/bump_revision/replace/save_article/review` | Closed connections, atomic revision and cancellation/expiry rollback |
| `semantic_analyser/collections.py`, `replace/save_article` | Existing preflight plus pre-commit guard |
| `semantic_analyser/engine.py`, `clear_index` | Cache eviction without unloading/copying the model |
| `tests/test_visitor_workspaces.py` | Ownership, race, timeout, cleanup and restart tests |
| `scripts/verify_phase2b.py` | Offline real model and two Chromium contexts |

See `docs/phase2b-verification.json` for the exact final local observations, including
test counts, memory counters and elapsed times. They are not production load-test or
recommendation-accuracy metrics. The independent-browser run checks:

- Two Chromium contexts, initially each with their own 21-article demo.
- Concurrent imports of 36 realistic-length synthetic articles per context, using
  distinct article IDs, followed by two submitted real MiniLM/TF-IDF comparisons.
- Exactly one model construction, identical parameter-storage pointer across engines,
  distinct embedding arrays, and original Phase 1B top-five IDs/scores after ID mapping.
- Exact search/link/overlap passage evidence, cross-session edit/review/export attempts,
  revision invalidation through a real UI review click, and deletion scoped to its owner.
- Real 801-passage rejection with data/revision preservation and 800-passage acceptance.
- The existing full browser smoke in visitor mode, without uncaught page errors.

The unit suite additionally exercises tampered/unsigned cookies, signed invalid IDs,
mandatory/stale revisions, concurrent same-revision imports and queued edit/analysis,
overload, active slot retention after timeout, cancelled queued work, rollback after a
timed-out review, cleanup while work is in flight, idle/absolute expiry, logout revocation,
cache eviction, app-instance restart recovery, expired restart cleanup and process locking.
The actual symlink creation test is skipped if the Windows account lacks that privilege;
unexpected-file cleanup refusal still runs. This is not a full hostile-filesystem audit.

Reproduce from repository root in the existing virtual environment:

```powershell
$env:WORKSPACE_MODE = 'local'
$env:DATABASE_PATH = Join-Path $PWD 'runtime\phase2b\test-bootstrap.sqlite3'
$env:APP_PASSWORD = ''
$env:APP_ENV = 'development'
$env:PRELOAD_MODEL = 'false'
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
node --check web/app.js
.\.venv\Scripts\python.exe -B scripts\verify_phase2b.py
```

The real verifier sets offline model mode, explicit two-thread CPU settings, a fresh
visitor root and localhost port 8013; that port must be free. It stops its server and
redirects screenshots/logs into runtime/phase2b. Native Windows process memory is
measured with GetProcessMemoryInfo; OS peak working set differs from private/commit
memory and excludes browser child processes. First import includes cached model-file
loading, not a download or dependency imports. Two submitted analyses execute serially
under the one-worker policy; their elapsed total is not per-request warm latency.

Preservation hashes cover the benchmark artifacts, sample/label data, existing deployment
files and older development SQLite files/sidecars. None is opened through the visitor
API or regenerated. Verification output is new Phase 2B evidence, not a replacement
for Phase 1B results or the Phase 2A verification record.

## Release limitations and next task

This is a single-node engineering baseline, **not production readiness**. Tests use
synthetic data and a small number of visitors. There is no hard native-work cancellation,
public abuse/fairness policy, independent relevance benchmark, sustained traffic test,
browser identity recovery, automatic backup, storage-corruption repair or new hosting
verification. Unexpected/file-locked cleanup may require operator attention. Idle LRU
limits do not constitute a hard process-memory ceiling.

The next required feature is the bounded, adversarially tested safe-fetch boundary,
followed by WordPress discovery, article selection, extraction and link mapping through
CollectionService. Network access must not be added by reusing Article.safe_url as an
SSRF defense. Existing isolation/revision/execution boundaries should be reused.

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
