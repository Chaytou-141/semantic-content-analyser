# Development journal

## Homepage-first automatic blog discovery

1 November 2026 (Australia/Sydney), baseline `8aeb44c`. Commit subject:
**Discover blog sitemaps automatically from homepage URLs**.
Normal users should not need to locate a sitemap manually. Auto mode now uses advertised
XML maps when no REST API is advertised, retaining advertised WordPress preference and
the existing no-metadata fallback. Mixed indexes focus on conservatively named blog/
post/article sections in automatic mode, with a visible incomplete-website warning.
All sitemap pages retains the previous explicit XML behaviour. Filename scope hints
are heuristic, not verified content classification; ambiguous names still traverse
normally, multiple post maps survive and unsafe hints cannot displace safe maps.

Continuing to other endpoints after HTTP400/401/403/429/503 was rejected. The chosen
scope decision precedes network requests; failures on chosen endpoints remain fatal.
No robots cache relaxation, retries, limit increases, AI changes or collection writes.
The previously authorised site's HTTP400 was not reproduced, so no root-cause claim
is made. A cached-response replay now finds 14 posts directly from that site's homepage
in six mocked requests, including no-cache robots checks. No further live requests ran.

275 targeted tests passed, one existing Windows symlink-privilege skip (29.81s).
Three offline browser viewport checks submit the real homepage form through the real
WebsiteService with controlled DNS/transport; 14 candidates, warning, selection and
visible extraction action pass. Node syntax and diff checks passed. No real model ran.
An earlier fixture's hardcoded 32-article assertion failed read-only because the live
collection now contains 14 articles /39,693 characters. Verification now reads the
current saved data and takes a fresh baseline; no data was restored or replaced.
All 1,835 protected-file hashes match. Details and reproduction commands are in
docs/homepage-discovery.md; current measurements in docs/homepage-discovery-verification.json.
Raw authorised responses and browser screenshots remain private under runtime. The
original transient HTTP400, actual extraction quality and public deployment remain
unverified. No push/deploy. Next: broader authorised compatibility testing when requested.

## Footer sizing and frontend cache follow-up

1 November 2026 (Australia/Sydney), baseline `7079926`. Commit subject:
**Bound footer icon and refresh frontend asset references**.
The footer SVG relied exclusively on stylesheet sizing. Its oversized appearance
was reproduced offline after removing the sizing rules: 1280x1280 at the default
test viewport. Explicit HTML width/height now bound it to 18x18 even with missing
footer CSS; eight current/missing-CSS cases passed at 1440/1024/390/320 widths,
including native disclosure keyboard toggling. Existing stylesheet URL is versioned.

A subsequent screenshot placed discovery errors in the sidebar while still showing
Finding public articles, matching older JavaScript rather than the current task
handler. Local access logs showed no new app.js transfer, which supports but does
not prove a cached-script cause. The app.js URL now includes an explicit release
version. The served homepage was checked for that reference. Offline browser checks
now explicitly require errors in the content panel, none in the sidebar, and Request
stopped status; all four viewport cases pass. Three focused UX tests pass (0.08s).
No new website requests, model runs or saved-collection writes occurred during this
UI follow-up; all 1,835 protected-file hashes still match. Private screenshots/results
are in runtime/footer-icon-fix and runtime/discovery-progress-fixes. Remote sitemap
HTTP400 remains a separate issue; refreshing frontend assets does not fix that response.

## Discovery diagnostics and extraction progress follow-up

Date: 1 November 2026 (Australia/Sydney). Baseline `4f04563`.
Commit subject: **Clarify discovery failures and extraction progress**.
Resolve with `git log -1 --format=%H --grep="Clarify discovery failures and extraction progress"`.

Users could not distinguish remote access denial from an absent endpoint, temporary
failure or application limits; a reported repeated Urban Turf discovery failure had
no saved site-specific endpoint/status evidence. The root cause of that live failure
remains unconfirmed. No live requests were made. Auto discovery probes REST even for
non-WordPress homepages and only falls back after 404/410. Automatically falling back
after 403 or bypassing restrictions was rejected. Explicit XML sitemap mode already
supports standard namespaced indexes/blog maps, verified with a Wix-shaped fixture.

The minimal change retains existing status codes, budgets and network policies while
adding safe HTTP-specific error text, resource/stage metadata and opaque diagnostic
references. Server warnings contain static stage/resource/code, known numeric status
and count, without URLs, response bodies, IPs or ownership tokens. This improves
future diagnosis, not a claim that a blocked website will become accessible. Offline
tests reproduce a possible successful first run (REST404 then XML) followed by REST403
on a new run, confirming that the latter stops safely; this is synthetic evidence.

The baseline extraction-specific progress element did render in fresh Chromium but
used a thin 12px track with only 2.78% fill at 1/36; total absence was not reproduced.
Independent sidebar and content scrollbars were confirmed. The bar now has explicit
18px track/fill painting below status, live backend counts and stopped/cancelled
last-confirmed wording. No synthetic progress or minimum percentage is introduced.
Cancellation clears backend previews, so the UI retains only the previous count for
the same run and explicitly labels it discarded/last confirmed. A separate capacity
meter stays hidden while accepted text totals are still unknown. One modal body
scroll replaces separate panel/text scrolling; source settings are collapsible and
the existing confirmation/cancel action bar remains outside the scroll region.

Validation: 256 targeted automated tests passed, one existing Windows symlink-privilege
test skipped, in 31.06s. This includes network/SSRF/DNS/robots/redirect/budget, workspace,
revision and atomic-import regressions. No historical benchmarks or real model ran.
After the final cancellation-only UI adjustment, the affected three UX tests and Node
syntax check passed again. Four offline Chromium viewport cases passed: 1440x900,
1366x768, 1024x600 and 390x844. Actual WebsiteService fixture snapshots show 110 found,
36 selected, 1/36, 2/36, then 36 processed/35 accepted/1 failed. Screenshot pixel checks
confirm a painted bar; stopped/cancelled states, partial acknowledgement, long lists,
open article reviews and visible action buttons passed. Zero browser exceptions,
unexpected/write/public requests or inference runs. This is snapshot-to-renderer
integration; not live-site verification or an entire server-driven browser workflow.

All 1,835 protected file hashes remain unchanged, including saved development SQLite,
evaluation data and benchmarks. The saved collection is still 32 articles /249,162
title/body characters. Existing untracked .vscode files are untouched. Detailed
diagnostics, alternatives, residual risks and reproduction commands are recorded in
docs/discovery-progress-fixes.md; portable results in docs/discovery-progress-verification.json;
private snapshots/screenshots in runtime/discovery-progress-fixes. No deployment/push.
Real Wix behaviour, the original browser-specific absence, Firefox paint rendering
and public deployment readiness remain unverified. Next: retain a failed response's
safe reference/stage/status if an authorised incident recurs; continue the existing
local Linux operational rehearsal rather than changing extraction or ML speculatively.

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

## Phase 3A - Secure, bounded website-fetching foundation

Report date: 29 October 2026, Australia/Sydney. The verification runner recorded
28 October on its local clock; measurements below are from that recorded run.
Starting architecture reviewed: Phase 2B `6df9b1c`; admission baseline `3ea9b59`;
historical benchmark `bc72066`.

### Problem and user impact

Website discovery is a core release requirement, but accepting visitor URLs introduces
server-side request forgery (SSRF), network scanning and resource-exhaustion risks.
A normal hostname check followed by a normal HTTP client request is insufficient:
DNS could change between validation and connection, redirects could target metadata,
and compressed or trickling responses could exhaust the shared analysis process.
The existing project had no reviewed network boundary for WordPress/sitemap/RSS work.

### Decision, alternatives and trade-offs

Implement a separate standard-library `SafeFetcher`, with explicit DNS pinning and
resource budgets, then integrate an opt-in metadata-only check through the existing
workspace/executor. The production socket connects to a validated numeric address;
TLS still verifies the original hostname. The complete DNS answer set must be public.

A hostname allow/deny check followed by independently resolving HTTP requests was
rejected because it leaves a rebinding gap. An ordinary thread-pool DNS lookup was
rejected because timeout cannot terminate a stuck OS resolver call. DNS instead runs
in a short-lived isolated, killable Python child. Adding a proxy service, Redis or
new infrastructure would expand operations before there is a demonstrated need.

A pinned third-party HTTP transport could be revisited after a separate dependency
and security review. The selected small HTTP/1.x transport has no automatic redirects,
proxy environment use, cookie jar or credential forwarding. This reduces implicit
behaviour but adds parser/transport maintenance and deliberately rejects some valid
websites. It is not a general-purpose browser or a claim of complete protocol support.

### Implementation

- `fetch_policy.py`: strict HTTP(S)/default-port URL admission, public IPv4/IPv6 rules,
  operator CIDR denies, fixed user-safe error taxonomy, owner/run/request/byte budgets.
- `fetch_transport.py`: per-request full DNS validation, numeric socket connection and
  peer checks, verified TLS/SNI, bounded socket reads, strict headers/framing, supported
  text MIME types and output-limited gzip/zlib-deflate decompression.
- `robots_policy.py`: bounded UTF-8 parser, combined product groups, longest matching
  rules, Allow ties, percent normalization and operation-capped wildcard matching.
  Final review found and corrected blank-line handling so later rules remain active.
- `safe_fetch.py`: same-host redirects only, robots handling/cache, one active request
  per host shared across visitors, polite delay, bounded state and Retry-After backoff.
- `/api/website/check`: disabled by default; enabled calls reuse signed workspace
  ownership, visitor If-Match, workspace lock, bounded executor, deadlines and cleanup
  leases. Only metadata is returned; no body or article is saved. Fetch runs and caches
  belong to the workspace and reset with its collection revision/restart.

Defaults: DNS/connect 3 seconds, read inactivity 5 seconds, total call 20 seconds,
run 180 seconds/60 attempts, content/robots redirects 3/5, encoded/decoded response
2 MiB each, headers 32 KiB, cumulative wire/decoded 20 MiB each, robots 512 KiB/4,096
rules/200,000 matching steps. Host pacing is at least 1 second after completion; 256
host states cap bookkeeping. These conservative policy choices need workload validation
in Phase 3B; no throughput improvement is claimed.

The MiniLM pipeline, TF-IDF, passage offsets, ranking, SQLite schema and existing UI
are unchanged. Admission remains 250,000 characters/800 passages. No crawler, extraction,
visitor-account system, cloud infrastructure or deployment was added.

### Tests and measured evidence

Portable evidence: `docs/phase3a-verification.json`. Reproduction:
`./.venv/Scripts/python.exe -B scripts/verify_phase3a.py`. Detailed design, source
references, policies and Phase 3B acceptance plan: `docs/phase3a-safe-fetch.md`.

- Full suite: **188 passed, 1 skipped in 23.47 seconds**. This includes the original
  71 passing Phase 2B tests and 117 new parameterized fetch/API cases. The skip needs
  symlink creation unavailable to this Windows account.
- Tests use controlled loopback HTTP/TLS fixtures and mocked DNS/transport, including
  rebinding, mixed public/private answers, numeric IPv6 dialing, peer mismatch, redirects,
  proxy variables, credentials, malformed HTTP, truncation, chunk framing, unsupported
  MIME, real certificate trust/hostname checks and owner/revision/error isolation.
- A 4 MiB decoded gzip fixture is rejected under a 1 KiB test cap. Slow headers and
  body trickles are stopped by a 0.2-second test deadline; inactivity and stalled TLS
  handshakes have separate checks. The deliberately stalled DNS child is terminated.
  These tests assert bounded outcomes, not exact wall-time guarantees on all hosts.
- Robots tests cover group/rule matching, blank lines, encodings, redirects, denial,
  unavailable policies, work limits, Crawl-delay and Retry-After without automatic retry.
- The fetch timeout test verifies that an occupied execution slot retains its workspace
  lease, overload is controlled, cleanup waits, and saved data/revision remain unchanged.
- Offline real MiniLM/Chromium regression passed: two independent browser contexts,
  exactly one loaded model/shared parameter storage, separate embedding arrays, unchanged
  recorded Phase 1B rankings, 20 exact returned passages, link/overlap evidence and stale
  review rejection. Real tokenizer accepts 800 passages and rejects 801 atomically.
- Two queued real comparisons took **15.722 seconds** combined. Peak process working
  set **718.63 MiB**, excluding browser processes. These are local regression observations
  on synthetic data, not recommendation accuracy, fetch throughput or a hosting guarantee.
- JavaScript syntax and whitespace checks passed. **518 protected files** were unchanged,
  including development SQLite/sidecars, UI, datasets, benchmark outputs and prior
  verification/deployment artifacts. Historical verification uses a copied script with
  isolated output/database paths; no original development database was opened by it.

No packages were installed, no arbitrary public websites were fetched, and no public
deployment or new model-quality evaluation occurred.

### Limitations and next task

Strict same-host redirects (including refusing www aliases), MIME/framing and robots
policies reduce compatibility. The robots implementation is a conservative REP subset;
HTTP/2/3, Brotli and JavaScript rendering are absent. Authentication-looking query
names are heuristic; a 200 login page cannot be reliably classified as inaccessible.

Application filtering does not protect operator-owned public IPs by itself, unusual
routing or all future network environments. Deployment-specific deny ranges, egress
controls, independent security review/fuzzing and sustained abuse/load testing remain.
Per-host gates do not merge aliases. There is no per-IP fairness or long-term abuse
quota; restarts/new runs reset transient counters. OS/native hangs are not hard-killed
by the executor. The endpoint is not a complete website-run UX and remains off by default.
Passing local tests does not establish production readiness.

Next: Phase 3B explicit owner/revision-bound website runs, bounded WordPress pagination,
candidate selection of approximately 30-40 posts, deduplication, safe text extraction
and existing atomic collection preflight before confirmed import. See the detailed plan;
do not weaken admission, hostname safety or workspace ownership to simplify discovery.

### Git reference

Local implementation commit subject: **Add bounded SSRF-protected website fetch foundation**.
Use `git log -1 --format=%H --grep="Add bounded SSRF-protected website fetch foundation"`
to resolve the commit containing this entry. The final review response records its hash.
No push or deployment is authorized/performed in this phase.

## Phase 3B - Bounded website discovery, extraction and staged import

29 October 2026, Australia/Sydney. Starting commit: `f93c03b` (Phase 3A).
Implementation commit subject: **Add bounded website discovery and staged article import**.
Resolve its hash with `git log -1 --format=%H --grep="Add bounded website discovery and staged article import"`.

### Problem and selected architecture

Visitors could analyse CSV/sample articles but could not build a collection from a
website. The task was to connect discovery and untrusted HTML extraction to the
existing pipeline without weakening SSRF defenses, visitor ownership or atomic admission.

One transient website run now belongs to each existing workspace. Its random run token
selects an operation but never authorizes access; the signed cookie still determines
ownership. The original collection revision is retained through discovery, selection,
preview and final import. Discovery/preview make no article/review writes. Only explicit
confirmation calls `CollectionService.replace`; real-tokenizer admission and a final
ownership/revision/expiry guard run before committing.

Instead of one long crawler request or a new job service, the browser advances one
fetch per step through the existing bounded executor/lease. This provides progress and
between-step cancellation while preserving Phase 3A's 180-second run, 60-attempt,
20-second per-fetch and byte limits. The budget includes human selection time. A larger
job infrastructure or silently renewed budgets were rejected as unnecessary or unsafe.

Discovery supports public WordPress REST pages (20 posts/page, <=10 pages) and XML URL
sets/indexes, including homepage/robots sitemap references. It caps discovery at 12
documents/200 candidates and sitemap nesting at three. Duplicates, cycles, unsafe URLs
and protected posts are filtered. Only 404/410 or a valid empty REST collection allows
fallback; auth/robots/anti-bot/error responses stop rather than trying bypass routes.

Extraction uses bounded inert standard-library HTML parsing. It prefers article/main
regions and omits navigation/footer/hidden/script/form/related/template regions.
Titles/headings/text, same-site canonicals and links are extracted; selected link targets
map to existing article IDs. Exact canonical/body duplicates collapse, and short exact
paragraphs repeated across >=80% of >=3 pages are removed with a visible warning.
This is a deliberately conservative heuristic, not general browser rendering/readability.
Ambiguous, short, oversized or explicitly restricted content is refused. Partial parser
failures are shown and require explicit subset consent before an import.

The UI extends the existing collection view without a framework change. It displays
candidates, selections, progress, full escaped plaintext previews and replacement
confirmation. CSV/sample workflows remain. `ENABLE_WEBSITE_FETCH=true` opts in; the
default remains off. There are no new dependencies, persisted tables or infrastructure.
MiniLM, TF-IDF, ranking, offsets and all original admission limits are unchanged.

### Verification, challenges and measured evidence

Details: `docs/phase3b-websites.md`; portable results: `docs/phase3b-verification.json`;
short future-session context: `docs/PROJECT_CONTEXT.md`. Disposable logs, HTTP fixtures,
screenshots and databases stay in ignored `runtime/phase3b`.

- During implementation, targeted new workflow/API tests ran first, then relevant
  SafeFetcher/robots tests after transport integration. No historical performance
  benchmark was rerun and no public website was fetched.
- Final full suite ran once: **222 passed, 1 skipped in 29.16 seconds**. The skipped
  Windows symlink test requires permissions unavailable to this account. Phase 3A's
  real local TLS, rebinding, compression and slow-response cases remain included.
- 34 new automated cases cover 40-article WordPress/sitemap workflows, pagination,
  nested/cyclic/unsafe sitemaps, UTF-16 DTD rejection, protected content, deduplication,
  template removal, capacity, visitor tokens/revisions, cancellation/expiry and rollback.
  Expiry during tokenizer admission is also checked before writing.
- Initial focused browser attempts exposed a fixture defect: posts advertised HTTPS
  while the controlled server served HTTP. The pinned TLS transport correctly refused
  it. Fixing fixture URLs, rather than weakening transport security, resolved the issue.
  Those attempts failed before model admission and did not load MiniLM.
- Focused verification then used actual loopback HTTP + mocked DNS/test-only connector,
  with two independent Chromium contexts. Each imported **36 articles**, via WordPress
  and via REST-404-to-sitemap-index fallback. Foreign run import/step/select were refused;
  previews did not change saved collections and each visitor retained its own site URLs.
- One shared offline MiniLM construction handled the real integration. The admitted
  synthetic collection contained **238,690 characters**, **270 passages**, embeddings
  **(270, 384)**. A both-method search took **7.828 seconds**, including collection encoding;
  source/target link evidence, exclusions and overlap checks also passed. This is one
  local integration observation, not an accuracy or throughput benchmark.
- Browser checks also passed invalid CSV rollback, valid CSV replacement, actual CSV
  download and a 390-pixel mobile layout, with no page errors.
- Final UI review found that reopening an imported run could still show its old commit
  button. The UI now renders its imported state before closing. An affected browser
  follow-up uses three fixture articles and a deterministic encoder to verify both
  workflows/reopened state/CSV/mobile without loading MiniLM again. The original full
  suite and real-model evidence are retained separately from this follow-up.
- Parser review replaced repeated summation of fragmented XML character callbacks with
  a linear running count, and translates HTMLParser's malformed-declaration assertion
  into an explicit extraction failure. The affected **34 tests passed in 5.37 seconds**,
  including adversarial XML entity-fragmented URL text and invalid HTML marked sections.
  The UI-only browser follow-up completed successfully with exit code 0.
- The successful real verifier wrote its completion JSON after all assertions; PowerShell
  classified Hugging Face's stderr progress display as NativeCommandError when redirected.
  There was no Python exception in that completed run. This shell/logging artifact did
  not justify another model load; the separate UI follow-up reports a normal exit.
- JavaScript syntax/whitespace checks pass. **651 protected files** remain unchanged,
  including saved development SQLite/sidecars, datasets, historical benchmarks, previous
  verification evidence and infrastructure. The original server/database was not used
  by verification. No packages were installed, pushed or deployed.

The realistic prose is authorised assistant-authored synthetic Phase 1B input, reused
as HTML fixtures only. Neither historical benchmark code nor results were rerun or
overwritten. These results do not establish extraction quality or recommendation
precision/recall, public-load capacity or production readiness.

### Limitations and next stage

General link crawling, RSS, compressed sitemap files, JavaScript-only pages, non-UTF-8
HTML, authenticated/private posts, cross-host/www redirects and nonstandard REST routes
are unsupported. A sitemap may list non-blog pages; human selection/preview is necessary.
HTML recovery and boilerplate removal are heuristic, and a 200 teaser/login response
cannot always be identified. Some valid sites will be refused by conservative policies.

Three minutes including selection can be restrictive; refresh does not resume a run.
40 long articles may exceed 250,000 characters or 800 passages. No limits were raised.
Public abuse fairness, runtime patch levels, deployment-specific egress and sustained
capacity testing still need assessment; inherited OS/native timeout limitations remain.

Next: review this phase, then evaluate a small authorised real-site sample and measured
completion under actual pacing before deciding on extraction/UX refinements and minimal
public hosting/abuse controls. No public deployment or push is performed in this phase.

## UI follow-up - Collection sources and website import

29 October 2026. Baseline: `30088d1`. Local commit subject:
**Refine collection and website import interface**.

The initial website workflow placed selection and long previews in a single scrolling
form. The collection screen also made website import hard to discover. Using the
frontend-design skill, this follow-up retains the established Instrument Sans/reading
type and plum palette, but gives the collection explicit website/CSV entry points and
the importer a three-stage workspace with a source sidebar and persistent action bar.
Candidates can be filtered by title/URL, selected in a bounded batch of 40 or cleared;
the extraction action displays the selection count. Preview copy and mobile layout
were refined. All fetched content remains escaped plaintext.

Changes: `web/index.html`, `web/styles.css`, `web/app.js`; focused browser assertions in
`scripts/verify_phase3b.py`. No backend, database, fetch limit or ML changes.

Verification: `--ui-only` passed both local fixture workflows, two browser contexts,
filter/empty/bulk/clear states, reopened dialog, CSV rollback/import/download and
390-pixel mobile layout with no page errors. Existing 651-file preservation check passed.
An initial added assertion assumed sitemap candidates already had extracted titles;
the verifier now filters by a known URL substring supported by both discovery sources.
No MiniLM load, public fetching, full-suite rerun or historical benchmark was needed.
JavaScript syntax and Git whitespace checks passed; desktop/mobile screenshots were
inspected in ignored runtime/phase3b. Portable follow-up evidence: `docs/ui-verification.json`.

A separate loopback preview on port 8001 uses temporary visitor data under
runtime/ui-preview. It does not open or replace the original development collection.
Website import remains opt-in for other installations. No push or deployment.

## Phase 3C - Real-site validation and bounded selection time

29 October 2026 (Australia/Sydney). Baseline `278049d`. Local commit subject:
**Validate real-site extraction and bound website selection time**.
Resolve the containing commit using `git log -1 --format=%H --grep="Validate real-site extraction and bound website selection time"`.

### Authorised observation and limitations

The user supplied freezeedge.com.au. This WordPress site was accessed using production
SafeFetcher, real DNS/pinning/TLS, robots and normal limits/pacing. No other domain was
authorised/tested. Initial REST discovery found 110 posts in 19.609 seconds/8 requests.
The advertised sitemap index returned 404; sitemap.xml and wp-sitemap.xml redirected
to it, and post-sitemap.xml also returned 404. This is recorded as failed real sitemap
discovery. Passing local XML fixtures is not a substitute for this missing coverage.
An independent non-WordPress site and functioning real XML index remain unvalidated.

A baseline 40-post run took 100.109 seconds/48 requests and prepared 31 articles;
9 valid page extractions could not fit the 250,000-character collection. Offline replay
of all 40 saved HTML responses confirmed structural extraction success. Their corrected
text totals 330,836 characters before collection template removal, so the cap remains
justified; it was not increased. The baseline left only 79.891 seconds for human
selection/review before the old 180-second wall deadline.

### Demonstrated compatibility fix

The noise matcher interpreted WordPress has-post-comment state flags as a comment
region and could hide the entire article. Fallback selected a broader post wrapper
with category and author/date text. The fix ignores has-* state flags for noise
classification and prefers a nested explicit entry-content/article-content body,
retaining the outer article H1 as its title. Real paywall/comment/nav/footer protections
remain. Original minimal fixtures reproduce the issue; no website prose was committed.

Comparing the saved real pages with baseline/corrected extractors found title/source-H1
and canonical/source-URL matches on 40/40 pages. Identified exact category/author blocks
were present in 39 baseline outputs and zero corrected outputs. Five source spot reviews
checked the content boundaries/headings/prose. Editorial marketing/contact text within
entry-content can remain; this is partial heuristic boilerplate handling, not an
independently labelled quality benchmark. No precision/recall or accuracy claim is made.

### Timing decision and UX

Website sessions now have a fixed 15-minute absolute lifetime and a separate cumulative
180-second active fetch budget. SafeFetcher charges DNS/TLS/robots/pacing/response work,
including failures, in finally under its session lock. Per-call deadlines take the
minimum of remaining active time, absolute lifetime, the existing 20-second cap and
executor control. The 60-request and 20 MiB wire/decoded counters do not reset.
Human selection/review gaps do not consume active time. Diagnostic sessions keep their
original wall-clock behaviour; only website sessions opt in. Fixed limits avoid a
rolling timeout or renewed per-page quotas that could enable indefinite fetching.

Ownership/revision/expiry guards still apply before final commit, and API admission
expiry rolls back. Capacity exclusions now have a separate failure kind and are shown
by article title; subset consent refers to the actual preview. Missing sitemap errors
now show HTTP reasons. No ranking, model, storage schema or infrastructure was changed.

### Measured corrected run and verification

A second live run prepared all 30 selected posts: 15.469 seconds discovery, 60.766
seconds extraction, **75.739 seconds active fetch time**, **38 requests**, 1,330,619 wire
bytes and 6,134,579 decoded bytes. The collection has **232,919 characters**. A single
offline cached real-tokenizer check through the existing preflight yielded **275 passages**;
no MiniLM weights/inference were loaded. Script wall time including dependency import
and this check was 87.641 seconds; the tokenizer/preflight block itself was 0.266 seconds.
It mapped 37 existing selected-article links across 23 articles. The prepared articles
were not imported into any development database.

Focused tests covered the changed fetch/website behaviour during development. The final
full suite ran once: **230 passed, 1 skipped in 30.24 seconds**. The skip requires Windows
symlink privileges unavailable here. Tests cover an eight-minute selection gap with a
controlled clock, fixed expiry at 900 seconds, spent time/request quotas, charging failed
work, expiry during admission/rollback and the demonstrated extraction/sitemap errors.
Existing SSRF/TLS/robots/timeout/isolation cases remain included. A separate deterministic
three-article/two-browser UI check passed the website and CSV workflows/mobile layout
with no page errors or model load. No synthetic check is claimed as real-site validation.

**752 protected files** were unchanged, including saved SQLite/sidecars, historical
benchmark artifacts and earlier evidence. JavaScript syntax and whitespace checks pass.
No historical benchmark, cloud deployment, push, package installation or paid service.
The previous local preview was not restarted or connected to the validation data.

Detailed report: docs/phase3c-real-websites.md. Portable results:
docs/phase3c-verification.json. Raw responses/plaintext and detailed logs remain ignored
under runtime/phase3c. The real observation helper restricts hosts to the user-authorised
site and refuses to overwrite earlier runs. Source hashes record each observed version.

Next: review Phase 3C, obtain an authorised functioning sitemap/index and non-WordPress
sample, then close extraction-quality/diversity, egress/abuse and sustained hosting
capacity gaps. Fifteen minutes is a bounded UX policy choice, not a measured universal
selection requirement. Public readiness is not established by one site's successful
30-post preparation or the automated suite.

## Phase 3D - Real-content evaluation and release gap assessment

29 October 2026, Australia/Sydney. Baseline `34b613d`. Local commit subject:
**Evaluate saved real content and document release gaps**. Resolve the containing hash
with `git log -1 --format=%H --grep="Evaluate saved real content and document release gaps"`.

### Problem and protocol

Real fetching had been measured, but source-text fidelity and recommendation quality
needed review on the actual saved articles. This phase reuses the exact authorised
Phase 3C snapshot instead of fetching pages again or changing the production pipeline.
It adds offline assessment artifacts only; application, ranking, security and deployment
source remain unchanged.

Four related-content tasks and three source-specific internal-link tasks were defined
before inspecting rankings. Each has an explicit provisional yes/no judgement for all
30 articles: 210 assistant-provisional labels, not independent human labels or a held-out
benchmark. Reasons, task criteria, corpus hashes and label provenance are versioned in
evaluations/phase3d. An independent review round can start with the blank 44-row union
of retrieved candidates and 15 overlap pairs; the full 210-row worksheet is also available.
No completed independent review was received, and no independent metrics are claimed.

### Extraction and actual model evidence

An independent HTMLParser source view found title/source-H1 and canonical matches on
all 30 articles; no body-heading or selected-link mapping differences were detected.
The one missing word per page was Contents inside a navigation region, intentionally
excluded by production extraction. Five source examples were spot reviewed in an inert
source/extraction packet. Five pages have two source-authored H1s; contact/promotion
signals appear in 24 bodies. These are review signals, not automatically incorrect text.
Word counts do not prove order, image coverage or rendered-page completeness.

The existing CollectionService admitted 30 real articles into a new disposable SQLite
database under runtime/phase3d: 232,919 characters / 275 passages. One offline MiniLM
construction produced (275, 384) embeddings and reused its index across all tasks and
both overlap inspections. There were zero guarded network attempts and 140 exact
source/target evidence substring checks, with self/existing-link exclusions preserved.

Local timing after dependency imports: 0.562 seconds admission; 9.278 seconds total
admission/analysis/evidence checking, 17.734 seconds process CPU with two PyTorch threads.
These are single cached-file evaluation observations, not cold-start or hosting SLAs.
The historical Phase 1B benchmark was not run. Cached rankings can be rescored and the
human packet rebuilt without another model load.

### Provisional results and trade-offs

Both methods have the same relevant-result counts at these cutoffs despite different
rankings. Related-task mean P@3/P@5: **83.3% / 75.0%** across four tasks. Internal-link
mean P@3/P@5: **55.6% / 40.0%** across three tasks. These are assistant-provisional,
single-site development diagnostics; independently reviewed judgements remain **0**.
The sushi task has only two positive labels, and both methods find both at ranks 1-2.

The frozen labels themselves have challenges: ice-build-up stock-line advice may satisfy
the chest loading question, while the sushi-model overview is only a contextual answer
to why no fan is used. Changing one contested label changes one method's measured score.
These challenges are recorded separately rather than silently altering labels after
observing scores. No model winner or fine-tuning recommendation follows from this sample.

High scores expose intent risks: generic upright-cabinet buying text is a running-cost
link suggestion (MiniLM 0.82363); fan-stock guidance appears from static/no-fan sushi
content (TF-IDF 0.33587). Supplier promotion versus finance scores 0.86721 / 0.57169
on a matching passage despite different main intent. Triple-glazed freezer articles
are a substantive-overlap candidate (0.93711 / 0.58155), not an automatic merge case.
The top TF-IDF overlap is below the existing 0.65 UI default; threshold calibration
needs independent review. No scoring formula, threshold or boilerplate rule was changed.

### Tests, preservation and release gaps

Focused metric/source-audit tests passed. The milestone full suite ran once:
**237 passed, 1 skipped in 30.68 seconds**. The skip requires Windows symlink permissions.
Tests verify metric denominators, incomplete labels/results, provenance distinctions,
invalid inputs and source-audit differences; existing security/isolation/admission
cases remain included. The human HTML packet renders and opens source examples without
HTTP/HTTPS resources. No model inference was repeated for verification or packet updates.

**1,081 protected files** remain unchanged, including development SQLite files, all
saved Phase 3C input/evidence and earlier benchmarks/results. No packages, public fetches,
infrastructure changes, paid services, deployment or push. Full source bodies/passages
remain ignored locally; only metadata, hashes and provisional review artifacts are tracked.

The release checklist identifies concrete configuration gaps: current production Compose
omits visitor mode and website enablement, so it defaults to the shared local workspace
with fetching off. Terraform currently permits all IPv4 egress. Public session/run abuse
fairness, egress/operator-address denies, retention notices, runtime patch posture and
host load/hard limits still require assessment/implementation. Infrastructure was reviewed,
not modified. Successful real sitemaps and independent non-WordPress platforms remain
unvalidated; local fixture results do not close that gap.

Details: docs/phase3d-real-content-evaluation.md, docs/release-readiness.md and
docs/phase3d-verification.json. Review worksheets/results: evaluations/phase3d.
Private source/ranking packet: runtime/phase3d/editorial-review.html.

Next: independent adjudication of the small candidate/pair set and authorised real
sitemap/platform validation, followed by a narrowly scoped deployment-readiness milestone.
Keep the existing stack/ranking and do not infer public readiness from provisional scores.

## Website-first UX follow-up

29 October 2026. Baseline `771c4cb`. User requested removing the complicated dashboard
entry and explicitly chose a website URL as the first-page input. Local commit subject:
**Replace dashboard entry with website-first workflow**.

The landing page now has one main action: enter a website and find articles. It submits
through the existing discovery form/API, with selection/preview/atomic confirmation
unchanged. The five-tab dashboard navigation is removed from the home screen. After
website or CSV import, users go directly to search/link/overlap tools. Your articles
opens management; More contains CSV utilities/development evaluation. Topic browsing
and search settings are collapsed. Sample prompts disappear for imported sites, source
selectors show titles, and generated IDs are omitted from ordinary result metadata.
Real collections without topic labels still get up to four preview articles.

The existing typography/palette was retained using the frontend-design skill. This was
a flow simplification rather than a framework/backend rewrite. No data or evaluation
functionality was deleted. Deep links still work; unknown routes return to the home page.
The existing website feature flag remains enforced, with a clear disabled-installation
fallback to CSV/sample tools.

Checks found/fixed an early-loading search shortcut switching to the old search view,
and task completion now restores each submit button's original disabled state instead
of accidentally enabling disabled website entry. Home URL controls stay disabled until
configuration is loaded. The / shortcut focuses the URL on home and article queries in
the analysis area.

Focused verification: 15 application tests passed in 0.99 seconds. Browser checks with
a deterministic encoder passed homepage URL -> WordPress/sitemap discovery -> selection
-> import -> analysis, CSV invalid-import rollback/valid import/export, four independent
browser sessions, disabled website installs after a search task, advanced evaluation,
editing/unsaved-change prompts, search/link/overlap and mobile navigation. No MiniLM
weights or public websites were used. One fixture assertion was corrected to expect
the existing four TF-IDF coffee matches rather than assuming every query returns five.
JavaScript syntax and Git whitespace checks passed. Desktop/390px mobile screenshots
were inspected; the real local preview also passed homepage/sample-entry/layout checks.

Existing verifier assertions were updated to the intentional new routes and disclosures;
their output was isolated under runtime/ux-home to preserve previous artifacts. The
application backend/security, original data, benchmarks and editorial history remain
unchanged. All 1,200 protected files passed the preservation check. The full model and
historical benchmark suites were not repeated for this client-only change.

An opt-in local visitor preview runs at http://localhost:8002 with separate temporary
storage and a stable local signing key under ignored runtime/ux-home/preview. Existing
servers/development data were left in place. Portable evidence: docs/home-ux-verification.json.
No public deployment, paid service or push.

## Phase 3E preparation - Independent SEO editorial review

29 October 2026. Frozen evidence from `771c4cb`; later website-first application
`036f173` retained. Local commit subject:
**Prepare independent SEO review packet and human-label scoring**.

Phase 3D had provisional AI judgements and blank worksheets but no convenient manual
submission path. This phase creates a separate, offline 59-item packet: 44 task/article
candidates and 15 overlap pairs, using only saved corpus/rankings. Source/target text,
supporting passages, existing-link status and optional AI notes are available for review.
Question-based tasks explicitly have no source article. No new AI labels were invented
for unlabelled overlap pairs, and no answers are preselected.

Useful/Not useful/Unsure plus optional reasons are human-only fields. AI notes never
populate them; disclosure is tracked. Browser drafts and CSV resume/export make a long
review recoverable. Packet fingerprints bind decisions to the frozen source/task/ranks.
Invalid imports are validated before replacing a draft. CSV reasons retain quotes and
newlines, and formula-sensitive free text is escaped. The private generated HTML uses
escaped data, textContent, CSP and no external resources; tracked files contain no
original article bodies. Application code/data and the earlier packet remain unchanged.

The small scorer computes human-only Precision@3/@5 when every item at a cutoff has a
resolved decision. Unsure and Unreviewed are reported rather than silently made negative.
Group means show completed/total coverage; all-case means remain unavailable until
complete. Overlap review precision is explicitly usefulness of investigation flags,
not duplicate or merge accuracy. One reviewer is accepted per file, with self-reported
identity/independence; external identity verification and multi-reviewer adjudication
are outside scope. Viewing AI notes is reported rather than hidden from the protocol.

Targeted verification only: 14 tests passed, plus offline browser checks for 59 initial
unreviewed items, AI/human separation, ratings/reasons, draft reload, CSV export and
fresh-browser resume, invalid-import rollback, filters and mobile layout. CSV/scorer
checks cover incomplete labels, provenance, metadata tampering, duplicate/mixed reviewer
rows, malformed quoting and refusing output overwrite. Test choices are synthetic;
no actual independent human reviews or new accuracy measurements were received.
The final CSV-focused run passed 14 tests in 0.54 seconds; browser verification had
zero page errors and external HTTP requests. Evidence: docs/phase3e-verification.json.

All 1,254 protected application/UI/data/history files remain unchanged. No model/tokenizer
load, public refetch, historical benchmark, full suite, infrastructure, deployment,
package installation or push. The earlier first-page UX was not reverted. The local
HTML and any drafts are separate from app visitor data/expiry and should stay private.

Guide: evaluations/phase3e/README.md. Open runtime/phase3e/independent-review.html,
export CSV, then run scripts/score_phase3e.py against the completed file. Next is an
actual independent reviewer round and adjudication of unresolved items, retaining the
frozen model outputs. Preparing the review workflow is not evidence of public readiness.

## Phase 3F — Evaluation consolidation and error analysis

29 October 2026 (Australia/Sydney). Baseline `5453900`; Phase 3D frozen inference
`771c4cb`. Local commit subject: **Consolidate screened editorial reviews and document
evaluation gaps**. Resolve the commit with
`git log -1 --format=%H --grep="Consolidate screened editorial reviews and document evaluation gaps"`.

The supplied review files combine 14 reported user decisions after AI screening and
45 AI-assisted assessments. Treating the whole completed-looking worksheet as human
ground truth would misstate recommendation quality. Every row explicitly has false
independent attestation. The existing Phase 3E scorer intentionally rejects these inputs:
the user file lacks attestation; the mixed file also adds provenance and multiple
reviewers. Neither file nor the original independent-review validator was weakened.

A separate standard-library consolidation script checks exact schemas, frozen
case/article/pair identities and ranking orders, supported values, duplicate/missing
rows and equality of every user field across the two files. The original Downloads
bytes are preserved under evaluations/phase3f/inputs for reproducibility, with hashes.
Alternative approaches—coercing false attestations, removing review_origin, or filling
human gaps from the 45 AI assessments—were rejected because they erase provenance.

Actual coverage: eight user-labelled candidates out of 44, six user-labelled overlap
pairs out of 15. User decisions are seven Useful / seven Not useful. Zero of 28
case/method/top-3-or-5 cutoffs is fully user-labelled; requiring independent attestation
also yields zero. MiniLM/TF-IDF human P@3 and P@5 therefore remain unavailable. The
mixed labels are only descriptive diagnostics, not an independently validated benchmark.
No new precision improvement, duplicate accuracy or method superiority is claimed.

The report compares frozen ranking disagreements and records 12 selected negative
examples: seven user-derived, five AI-assisted, with explicit annotation provenance and
method/rank/score/passage hashes. Examples cover generic commercial/buying language,
topic/technical-application mismatch and search-intent mismatch. Positive counterexamples
show why a global destination blacklist or freezer/chiller keyword filter is unsafe.
Maximum-passage scoring is consistent with shared commercial sections dominating some
matches, but there is no causal ablation or independently measured fix. The proposed
next experiment is narrow repeated-promotion evidence handling, after complete comparable
independent labels, with current rankings and positive cases retained as controls.

Verification: 45 targeted tests passed, zero failed/skipped, in 0.54 seconds (pytest
reported duration). Cases cover human-only denominators, unresolved/missing/AI labels,
CSV schema/value/identity tampering, reconciliation conflicts, frozen ranking/pair
changes, annotation evidence hashes, strict original scorer and output overwrite
protection. CLI reproduction exactly matches tracked results. All 1,662 protected
application/UI/data/history/runtime files remain unchanged; original Downloads CSVs
remain byte-identical. Portable evidence: docs/phase3f-verification.json. No full suite,
browser run, historical benchmark, model/tokenizer inference, website request, new
package, infrastructure, deployment or push. Scope did not justify those checks.

Detailed results and reproducible commands: docs/phase3f-evaluation.md and
evaluations/phase3f/README.md. Release-readiness and PROJECT_CONTEXT are updated;
security, hosting, abuse and unvalidated non-WordPress/sitemap blockers remain open.
Next: obtain complete independent labels under clear task-specific criteria, then
evaluate any targeted ranking experiment without training/tuning on the same test set.

## Phase 3G — New editorial evaluation packet

29 October 2026 (Australia/Sydney). Baseline `cad5b4a`; frozen rankings `771c4cb`.
Local commit subject: **Prepare metadata-blind editorial round for complete ranking evaluation**.
Resolve with `git log -1 --format=%H --grep="Prepare metadata-blind editorial round for complete ranking evaluation"`.

Phase 3F's 14 user decisions after AI screening and 45 AI-assisted assessments did not
complete any eligible human cutoff. Phase 3E also allowed optional retrieval/AI disclosure.
The new round needs a packet that covers the complete top-five union without exposing
that information while a reviewer decides. Editing old attestations, hiding labels with
CSS or filling the gaps from AI assessments would not solve the provenance problem.

The new builder reuses frozen evidence checks and original passages, then creates a
strictly whitelisted reviewer payload. There are 44 task/destination judgements across
R01–R04/L01–L03 (23 distinct destinations, 24 articles including sources). The 15 existing
overlap-investigation cases remain untouched and outside recommendation metrics.
The browser gets only question/criterion, source/destination text, original supporting
passages and saved existing-link facts. Method names, ranks, scores, earlier judgements
and coordinator mappings are not embedded. Opaque aliases, hash-based ordering and
deduplicated unattributed passages avoid presenting either method's order. Complete
saved articles remain available for checking selective passage evidence.

This is a new packet fingerprint/schema/draft namespace; no previous decision is imported
or preselected. Useful/Not useful/Unsure, optional reasons, CSV export/resume, task/status
filters and browser draft recovery are provided. Invalid imports validate completely
before replacing a draft. Untrusted text uses textContent/escaped JSON and hashed-script
CSP; no resources load over the network. Prior exposure and human attestation are explicit
and initially unset. Earlier screened participants must report exposure, not claim a fresh
review. They can still submit preserved judgements, but cannot supply eligible labels
for the new no-prior-exposure metric scope.

The separate scorer checks the coordinator mapping against frozen rankings, strict CSV
schema/identities and consistent reviewer/provenance. All k results need eligible
resolved human labels before P@k is reported. Unsure/missing/ineligible entries remain
explicit gaps. Related and internal-link groups stay separate; comparative subset means
use the same paired complete cases. Original Phase 3E/3F evaluators are unchanged.
No overlap duplicate/merge accuracy, current human precision or model improvement is
claimed. The coordinator protocol asks for preserving submitted CSV bytes/hash before
revealing results and separately versioning any later adjudication.

Verification: 68 targeted Phase 3E/3F/3G tests passed in 1.39 seconds in the final run,
zero failed/skipped. The mobile import control was widened after visual inspection;
the targeted tests and browser checks were rerun after this offline-template adjustment.
Offline desktop/390px browser checks passed for 44 initially unanswered cards, no retrieval
or AI controls, separate prior-draft storage, export/new-browser resume, quotes/newlines/
formula-safe reasons, invalid-import rollback, old-schema rejection, filters, reload and
mobile width. Screenshots were inspected. Test choices are explicitly synthetic; no new
human decisions were received. Browser errors and external HTTP requests were zero.
All 1,758 protected tracked/runtime files remain unchanged. Evidence:
docs/phase3g-verification.json; guide and protocol: evaluations/phase3g/README.md.

The delivered file supports blindness to retrieval metadata, not formal blinded
independence: identity/exposure are self-reported; external access/discussion cannot be
prevented; source/task/passage selection remains model-derived and limited to one site.
No application/model/ranking/security change, inference, website fetch, historical
benchmark, full suite, package installation, infrastructure, deployment or push.
Next: give only the standalone private HTML to a genuinely unexposed reviewer, collect
all 44 judgements and score complete eligible cutoffs without filling uncertainty.

## Phase 4A — Website compatibility and deployment readiness

29 October 2026 (Australia/Sydney). Baseline `1a276af`. Local commit subject:
**Fix bounded XML sitemap compatibility and prepare isolated demo configuration**.
Resolve with `git log -1 --format=%H --grep="Fix bounded XML sitemap compatibility and prepare isolated demo configuration"`.
Further human editorial evaluation is intentionally deferred. No new packet, request for
labels, inference, historical benchmark or ranking adjustment was made.

Inspection found explicit non-.xml sitemap URLs being replaced by /sitemap.xml, XML
mode ignoring advertised maps at a bare website root, and namespace stripping that could
mistake image extension loc fields for article destinations. Empty loc/href values could
also resolve to the homepage; depth/queue truncation was not always visible. These are
compatibility/data-quality problems before semantic analysis, not model-quality findings.
Original synthetic controlled-network fixtures reproduced ten failures and three passes
before fixes. No new public website was contacted and no live compatibility was claimed.

The selected changes preserve explicit endpoint URLs, use homepage/robots-advertised maps
without REST probing in root XML mode, match fully qualified standard sitemap element
paths, ignore empty references and show bounded-discovery warnings. Standard prefixed/
default namespaces, legacy no-namespace maps, UTF-8/UTF-16 XML and escaped queries remain
supported. Foreign extension entries cannot become articles; malformed primary loc
markup/foreign roots fail clearly. Existing DTD/entity rejection, byte/node/depth/URL
bounds and all SafeFetcher/DNS/robots controls remain. Limits were not raised, and no
gzip-file parsing, cross-host allowance, generic crawler or speculative extraction rule
was introduced. Existing auto/WordPress absence fallback stays restricted to genuine
404/410; explicit XML mode handles sites with an HTML catch-all REST route.

The production Compose template previously selected shared local mode implicitly and
disabled website import. It now explicitly selects visitor mode, /app/runtime/visitors
and bounded website fetching, retaining required password/secret, private app port,
privilege settings and proxy/volume configuration. Local source/Compose defaults remain.
No existing database was migrated or deleted and no runtime was reconfigured. The AWS
guide now identifies legacy single-database backup instructions as local-only; they do
not back up temporary visitor directories. Static YAML and production Settings validation
passed with dummy credentials. Docker CLI was absent, so no image pull/build/run, resolved
Compose validation or HTTPS/proxy claim was made.

Relevant regression tests: 235 passed, one existing Windows symlink test skipped, in
30.85 seconds (pytest duration). Selection covers website workflows, SafeFetcher/transport
adversarial cases, API ownership, visitor isolation/revisions/timeout/cleanup and atomic
collection admission/rollback. After a test-only route assertion was tightened, all 20
new compatibility tests passed in 1.32 seconds; production code was unchanged after the
broader relevant run. A controlled XML-root/index/URL-set workflow extracted 40 articles
using 44 requests including robots. Fake DNS/transport, zero pacing and test encoders
mean this is workflow evidence, not live performance, hosting capacity or model evaluation.

Preservation compared 1,773 snapshotted tracked/runtime files: 1,772 unchanged plus the
intentional AWS guide update, no unexpected changes. Planned website/parser/config and
current-documentation edits were excluded from that baseline as described in the phase
evidence; application ranking, security components, saved development data and historical
benchmark/evaluation artifacts were unchanged. Details: docs/phase4a-verification.json
and docs/phase4a-compatibility-readiness.md. No full suite, browser suite, package
installation, live fetch, cloud operation, expense, push or deployment occurred.

The template is an incremental basis for a password-gated limited demo, not a public
readiness certification. Network egress is still unrestricted at infrastructure level,
forwarded peers are broadly trusted, ingress/session fairness and container quotas need
work, and Linux/HTTPS/volume/cleanup verification is pending. Successful real XML/index/
non-WordPress validation is still absent; earlier Freeze Edge evidence remains unchanged.
Next Phase 4B: bounded demo operations, trusted-proxy/abuse/egress/resource/retention
controls and disposable local container verification when Docker is available. Do not
resume editorial work or infer permission to deploy from that recommendation.

## Phase 4B — Bounded demo operations and local Linux Docker verification

30 October 2026 (Australia/Sydney). Baseline `e08f8df`, retaining the Phase 4A
test-only advertised-map assertion. Local commit subject:
**Bound demo admission storage and outbound operations with explicit proxy trust**.
Resolve with `git log -1 --format=%H --grep="Bound demo admission storage and outbound operations with explicit proxy trust"`.

Existing per-run fetch/collection/executor bounds did not prevent repeatedly creating
visitor identities or fresh runs. Production also trusted all forwarded peers and had
no container resource or file-admission budgets. This phase adds a small single-process
policy layer rather than replacing SQLite, authentication, models or ranking. New limits
are opt-in for local source use and enabled explicitly in the production template.
Further editorial work, real-model evaluation and historical benchmarks remain deferred.

DemoLimits applies rolling per-client/global API and session admission, HTTP concurrency,
and per-owner/global wire-attempt budgets across runs. Accounting is locked and bounded;
full state does not evict/reset live buckets. Robots, redirects and failed DNS attempts
consume outbound budgets before transport. 429/503 responses have Retry-After. Budgets
are process-local and reset on restart; claiming durable or distributed abuse prevention
would be incorrect. Existing persisted workspace capacity/expiry and bounded executor
still apply. Login accounting likewise no longer clears all live entries at capacity.

Docker disables Uvicorn proxy rewriting, bounds connection concurrency/backlog/keep-alive,
and retains one worker. A configurable private bridge fixes an exact trusted Caddy peer.
Caddy overwrites client-identity/scheme headers; the app rejects malformed trusted headers,
ignores arbitrary forwarded headers and only restores scheme from that exact peer.
This preserves API HTTPS redirect behaviour without trusting client-controlled IP lists.
Broad proxy networks are rejected. A different upstream proxy/CDN requires a new review.

Visitor SQLite connections apply a main-file page cap. Actual database/WAL/SHM totals
and minimum free space guard creation/mutation; thresholds are soft, not filesystem
quotas. SQLite-full failures safely roll back and return 507, including after article/
review deletion inside a failed replacement. New partial database creation removes only
known regular files in the new server-chosen direct child. Existing reads/export/deletion
remain available at admission thresholds; actual disk failure may still need operator
recovery. Idle/absolute expiry, active leases, revision and cleanup policies are reused.

Optional exact fetch-host admission adds no exception to DNS/IP/SSRF/robots policy.
Application restrictions were tested; no kernel egress rule was applied or verified.
The network policy contract in docs/phase4b-demo-operations.md covers public HTTP(S),
controlled resolver access, private/metadata denial and operator-owned infrastructure.
A Docker bridge and application allowlist are not represented as a firewall.

Production Compose now declares app read-only root, private writable workspace volume,
bounded tmpfs, 4 GiB/no extra swap, two CPUs and PID 128; the proxy has smaller quotas.
These are containment defaults, not measured model capacity. Existing health checks now
also reject missing required model or visitor-cleanup readiness. No cold/warm inference
or memory benchmark was run. A disposable loopback-only local Compose/verifier uses an
already-built current-source image without pulls/builds, disables real model preload/
website fetching, checks owned review separation/restart and cgroup configuration, then
removes only its uniquely named verification project's volumes.

Actual Docker result: **skipped**, because no accessible Docker CLI was found (including
the standard Desktop location). No Linux container, Caddy HTTPS path, image-cache startup,
kernel quota exhaustion or network firewall test passed. Static YAML/network/command
consistency checks passed; they do not substitute for Docker execution. The verifier
writes linux_container_verified=false and a reason rather than claiming success.

Verification: the first relevant run found a SQLite lock inversion introduced by the
quota guard taking manager.lock inside a write transaction while acquisition held that
lock waiting to touch SQLite. The guard now scans without taking that lock and tolerates
another workspace's safe cleanup. Focused concurrency and the final relevant selection
passed: **271 passed, one existing Windows symlink test skipped, 31.79 seconds**. A test-
only strengthening of scheme/readiness checks then passed all **22 operations tests in
1.53 seconds**. Runs overlap, not additive. Tests use fake encoders and controlled local/
mock DNS/transport; coverage includes spoofing, rolling/global bounds, storage rollback,
partial-creation cleanup, expiry/leases, restart ownership, overload and late-write safety.
All 1,775 protected tracked/runtime files remain unchanged. Evidence and reproduction:
docs/phase4b-verification.json and docs/phase4b-demo-operations.md.

Remaining: durable/restart-resistant fairness, NAT/IPv6 and host load assessment, hard
volume limits, actual Linux/symlink/HTTPS/proxy enforcement, dependency/image validation,
monitored retention and kernel egress proof. Native cancellation remains cooperative.
Next Phase 4C is a disposable local Linux release rehearsal, not deployment or editorial
evaluation. No packages, public sites, AWS resources, paid services, push or public
exposure were used in this phase; saved development data and prior evaluation evidence
were preserved.

## UI/UX refinement and portfolio presentation after Phase 4B

1 November 2026 (Australia/Sydney). Baseline `f93aed4`; Phase 4A/4B work and existing
untracked .vscode files retained. Local commit subject:
**Refine onboarding import guidance and readable article evidence**.
Resolve with `git log -1 --format=%H --grep="Refine onboarding import guidance and readable article evidence"`.

The user reported a successful Freeze Edge journey: 110 discovered, 40 selected, 32
imported and eight excluded by the character budget. Read-only inspection independently
confirmed the current saved collection contains 32 articles /249,162 title/body characters.
Live discovery/inference was not repeated. The identified problem was discoverability,
navigation and evidence density, not a missing model/application pipeline.

The frontend-design skill was used to preserve the Instrument Sans/plum/paper identity
and existing components. The homepage now explains the three tools and offers sample
or website paths. Fresh seeded visitor workspaces can explore samples directly; custom
collections receive non-destructive continuation/sample options. An explicit restore
confirmation remains necessary. A parallel read-only sample backend was rejected as
unnecessary duplication; a fresh private browser isolates samples only in visitor mode,
not shared local mode. No saved real collection was restored or replaced by this work.

Analysis, Articles and Import are prominent navigation entries; Development evaluation
stays technical. Changed hashes are pushed rather than replacing browser history, with
existing routes, keyboard focus, aria-current, aria-busy and modal confirmations retained.
Successful imports show a persistent revision-bound article count and Explore analysis /
Manage articles actions. Collection management keeps table/filter/edit/export controls
while replacement choices are collapsed. Success state is frontend memory, not a new
persisted provenance field or a promise to survive reload.

The existing website wizard now explains discovery and filtered bulk selection, shows
native processed/capacity progress, and groups individual reasons into capacity exclusions
versus extraction failures. Accepted character totals are shown only when the backend
provides them; extraction uses an explicit calculating state. Other omitted articles are
not assigned fabricated duplicate reasons. Partial acceptance, cancellation, deadlines,
final admission and revision protection remain authoritative. No numerical limit changed.
The About section and learning guide explain 250k characters /100 articles /20k body
characters /800 passages /40 selected as application resource-management safeguards,
not MiniLM-imposed collection limits or accuracy claims.

Search/link/overlap evidence starts with short excerpts and expands to exact original
passages/offsets. Source/destination context and original HTTP(S) links are clearer;
fictional sample URLs are identified rather than presented as published articles.
Link decisions/notes still use the same API and persist on rerequest. Custom search
examples use loaded article titles, not generated recommendations. Overlap has no saved
review contract, so unsupported feedback/merge controls were not added. Similarity stays
a raw mathematical score, not confidence; historical synthetic evaluation is unchanged
and explicitly does not update for imported collections.

Citation investigation found the exact oaicite/contentReference markers in saved source
HTML response-012.bin/response-015.bin and corresponding stored articles. They originated
in cached site content, not a newly invented extractor token. Only labelled display
previews remove the narrow numeric pattern; full raw text is expandable. Saved bodies,
model input, offsets and historical evidence remain unchanged. Editing/stripping stored
content was rejected because it would change evidence and analysis outside this scope.

Changes concentrate in web/index.html, app.js and styles.css: entry/navigation/success
components; loadCollection, navigate, renderWebsite, renderSearch, renderLinks and
renderOverlaps; new evidence/displayText/importComplete helpers. scripts/browser_smoke.py
selectors reflect the new labels. docs/ux-refinement-learning-guide.md explains events,
API calls, revision/state handling, why limits exist and practical learning exercises.
No new framework, backend contract, ranking formula, second model or cloud service.

Verification: 163 relevant tests passed, one existing Windows symlink case skipped,
in 15.80 seconds. New tests bind UI values to backend limits, validate exact display-only
marker cleanup and prove raw extractor evidence remains. Node syntax passed. The complete
disposable browser walkthrough passed using the existing deterministic fake encoder and
controlled DNS/transport: sample analysis/compare, saved review-note persistence, overlaps,
development provenance, 110/40/32/8 WordPress fixture, XML import, filtered selection,
partial acceptance, success navigation, article edit/export, valid CSV replacement and
invalid CSV rollback, independent visitors, Back/keyboard/390px layout and empty/error
states. Budget/expiry/empty-link/overlap presentation checks use explicit simulated
responses, not claims of additional backend failures. Screenshots were inspected.

The first browser run completed its journeys but preservation hit disappearing live
SQLite sidecars; these are now separately excluded from byte comparisons because normal
connection closure removes them. A later test-harness response callback signature was
corrected before the final full walkthrough. Final browser errors/external requests are
zero. 1,793 protected files and the main SQLite hash are unchanged, with logical saved
32/249,162 state confirmed. A read-only check of the running localhost UI also preserved
sample options and current analysis navigation, without search/reset/import/review calls.
Detailed evidence: docs/ux-refinement-verification.json; private screenshots/logs remain
under runtime/ux-refinement. No historical benchmark/evaluation artifacts were rewritten.

Remaining: imported/source classification is an existing ID/URL-based UI distinction;
success status is not durable across reload; a separate sample workspace for shared local
mode was not introduced. Docker/Linux/HTTPS/UID/quota/egress and hosting verification remain
pending from Phase 4B. Restart counters, soft storage and cooperative timeout limitations
remain. No real model benchmark, new editorial label/packet, live website request,
LinkedIn publication, paid resource, AWS deployment or GitHub push occurred. Public release
readiness is not established by UI QA; the next operational milestone remains Phase 4C.

## Targeted homepage follow-up after UX commit 5e3ec22

Baseline `5e3ec22`. Local commit subject:
**Separate homepage continuation samples and accessible tool navigation**.
Resolve with `git log -1 --format=%H --grep="Separate homepage continuation samples and accessible tool navigation"`.

The imported collection's continuation link was inside a section headed Explore sample
analysis, mixing distinct choices. It now has its own labelled continuation section with
the current article count and primary action. Samples remain a separate section: existing
collections get View sample options as a secondary action; fresh sample collections can
explore directly. No backend/reset contract changed; restoration still delegates to the
existing explicit confirmation. Tests dismiss that confirmation and observe zero writes.

The three feature descriptions previously shared paragraph nodes with strong headings.
Fresh Chromium computed block headings and a 5px gap, rather than a literal missing gap.
They now use separate h2/p elements within named, keyboard-operable navigation cards,
with explicit 12px flex gaps and a one-column layout at narrow widths. Routes/history,
focus styling, fonts and palette are reused. Sample/current section headings also align.

The reported footer clipping was not reproduced in fresh Chromium at 1440/390/320:
computed summary bounds were already within the viewport width and no horizontal overflow
was present. No fixed-position or overflow-hiding root cause was verified. Instead of
claiming one, the native-marker layout was hardened: an aria-hidden contained SVG and
wrapping label replace browser-specific marker placement; explicit gutters, minimum
target height and in-flow layout retain the native details keyboard/expanded behaviour.
Both closed/open and 30px enlarged-summary text were tested. The first harness check
hit fractional nearest-scroll rounding; centring the focused disclosure before measuring
removed that measurement artefact without changing the production layout to mask it.
Different browser/cache-specific reports remain unverified, not claimed resolved by proof.

Changes are limited to web/index.html, web/app.js, web/styles.css, the focused standalone
scripts/verify_homepage_fixes.py and current documentation. The script fulfils API/assets
inside the browser from read-only saved 32-article data and fictional sample fixtures;
it starts no backend, runs no encoder, performs no public requests and rejects any write.
Six collection/viewport cases passed (sample and imported x1440/390/320), including all
three cards via keyboard/Back, continuation versus sample choices, dismissed restoration,
and normal/enlarged About bounds/Enter/Space toggling. Browser errors, write requests and
external/unhandled requests were zero. Three existing targeted UX tests passed in 0.07s;
Node syntax passed. Screenshots were inspected. No broad suite or model inference ran.

All 1,819 protected files, including the main saved SQLite file, are unchanged. Inspection
also confirmed the saved collection remains 32 articles /249,162 title/body characters.
Transient live SQLite WAL/SHM files were excluded from the baseline; normal read-only
connection closure can remove them. Existing untracked .vscode files were untouched.
Evidence: docs/homepage-fixes-verification.json; private before/after screenshots and
layout measurements: runtime/homepage-fixes. No backend, security, numerical limits,
analysis logic, model/evaluation evidence, deployment, live-site fetching or GitHub push
changed. Docker/public-launch blockers remain those recorded after Phase 4B.
