# Phase 1B — realistic analysis benchmark and engineering baseline

Inspection and execution date: 28 October 2026 (Australia/Sydney).
Application baseline: `8e2c99198d42a05696b0b362ef851c1c8932e559`, branch
`feature/deployable-aws-app`. The UI commit is local and one ahead of the tracked remote.

Website URL analysis remains a **core release requirement**. This phase validates the
existing engine before implementing discovery/extraction. No crawler, production
scorer, schema, infrastructure or deployment change is included.

## Evidence and methodology

The original application, demo CSV, saved labels/rankings and database files are
protected by before/after hashes. Tests and HTTP verification use a new disposable
SQLite file and a separate localhost port. Portable fixtures/results live under
`benchmarks/phase1b/`; raw logs and screenshots under ignored `runtime/phase1b/`.

The corpus contains 36 assistant-authored synthetic articles in six topic groups,
641–1,363 words each. The complete title/body character count is 238,142. Sibling
articles share substantive domain sections and process text by construction. This
is suitable for engineering stress and overlap probes, not a representative sample
of real website language or an independently labelled accuracy benchmark.

Fresh sequential subprocesses run 30- and 36-article profiles for each method. Model
files are cached locally and networking is explicitly disabled. Two CPU/BLAS threads
and one PyTorch inter-op thread are used on Windows. The machine is an Intel Core
i5-11400H (6 cores/12 logical processors), with 16,800,153,600 bytes of installed RAM
(approximately 15.65 GiB). Existing applications may affect elapsed time.

"Process cold" includes Python dependency import and loading a cached model, not a
model download or cleared OS cache. Operations are timed separately. Warm search
has five samples (two alternating queries); warm links and overlaps have three each.
These small sample counts establish a baseline, not stable tail-latency estimates.
Process CPU time includes all its threads. Windows CPU timer granularity can report
zero for very short operations. Native OS lifetime peak working set supplements
20 ms sampled operation RSS; private/peak commit are also captured in raw JSON.

## Measured findings

The complete measured tables, CPU/memory counters, constructed matching probes and
test results are in [the measured results](../benchmarks/phase1b/results-summary.md).
Machine-readable evidence is in `benchmarks/phase1b/results.json` and
`benchmarks/phase1b/verification.json`.

| Profile | Characters | Passages | Fits current limits? |
| --- | ---: | ---: | --- |
| 30 original articles | 198,653 | 225 | yes |
| 36 original articles | 238,142 | 269 | yes; only 11,858 characters remain |
| 40, adding four length fixtures | 268,013 | 302 | no; character bound |
| 36 with 25% longer bodies | 297,257 | 337 | no; character bound |
| 36 with doubled bodies | 474,663 | 531 | no; character bound |

The 40-article and expanded-body cases duplicate fixture prose only for capacity
measurement; they are not additional realistic independent articles. The current
character policy constrains normal long-form English before the passage policy in
these fixtures. This does **not** establish that raising the character bound alone
would accommodate arbitrary extracted pages. Token density varies markedly.

For 36 articles, cached-model load took 5.47 seconds, passage/TF-IDF preparation
0.105 seconds and first MiniLM collection encoding 7.99 seconds (16.02 process CPU
seconds). Median warm searches were 9.76 ms for MiniLM and 1.82 ms for TF-IDF. Warm
link calls were 1.34/4.04 ms; overlap calls 13.34/15.95 ms respectively. Dependency
imports add about 2.4 seconds to a fresh process. These are local single-process
results with explicit thread settings, not an AWS/concurrency SLA.

OS peak working set before adversarial probes was approximately 690 MiB for MiniLM
and 494 MiB for TF-IDF; MiniLM peak commit was approximately 798 MiB. Budget above
these observations for the FastAPI process, extraction buffers, active indexes,
operating system and traffic. Do not select a memory limit exactly at the observed
peak. This run supports keeping one shared model and a bounded queue, but does not
measure a safe number of simultaneous visitors. Including the separate matching
probes, the largest process peak was 697.1 MiB.

The source-only diagnostic reproduced the current source scores within 1e-6 while
reducing the 36-article link matrix from 72,361 to 1,345 entries. Both current full
matrices were already inexpensive; initial encoding dominates latency. No scorer
or ranking computation was changed.

Length-only cycling prefixes increased the semantic max from 0.1820 to 0.2905 without
creating a high match. Adding one 39-word espresso paragraph made the cycling article
rank first or second. The longest case scored 0.6598 (max) versus 0.2309 (mean) for
MiniLM; TF-IDF also promoted it to first. Max scoring captures a relevant fragment
without evaluating the article's overall intent. It is a constructed intent-mismatch
probe, not labelled evidence that every such passage result is wrong. Length effects
were not monotonically increasing because chunk boundaries and TF-IDF fitting change.
Do not infer a general false-positive rate, change scoring or tune thresholds here.

The unchanged latest-local UI/API passed the existing 15 tests (0.93 seconds), JavaScript
syntax, browser smoke, real-model 36-article HTTP analysis and all 269 real-tokenizer
offset/tail checks (largest combined input 206 tokens). A separate token-dense fixture
confirmed a real admission gap: import returns 200 but analysis returns 422 above
800 passages. All 42 protected original source/data/database-file hashes were unchanged.

## Existing engine and bottleneck interpretation

- `semantic_analyser/engine.py:21`, `load`: lazy CPU MiniLM pinned to revision
  `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
- `engine.py:33`, `passages`: 192 body tokens, stride 160, 40-token title prefix,
  original character offsets. Windowing is not paragraph-aware.
- `engine.py:53`, `prepare`: complete collection fingerprint and TF-IDF fitting;
  maximum 800 passages. Metadata changes also invalidate the entire index.
- `engine.py:73`, `semantic_vectors`: normalized 384-dimensional vectors in RAM.
- `engine.py:95`, `search`: maximum passage score per article.
- `engine.py:108`, `links`: strongest source/target passage pair; excludes self,
  supplied existing destinations and ineligible targets.
- `engine.py:140`, `overlaps`: full passage matrix, Python upper-triangle scan and
  maximum score for each article pair; not a calibrated duplicate classifier.
- `storage.py:14`, `validate_collection`: 100 articles, 250,000 title/body characters;
  `schemas.py:10` additionally limits individual body length to 20,000 characters.

The first optimization candidate is the **admission contract**, not a vector database:
estimate/tokenize selected articles before committing them, report all limits and
reject atomically. A character-valid collection can still fail the passage limit
only when analysis begins. Do not silently truncate articles or raise limits globally.
Propose a separate public-run policy after measuring a wider length distribution.

For link discovery, compute source passages by all target passages rather than an
all-by-all matrix, preserving exactly the current score and tie rules. At this corpus
size matrix multiplication is already cheap, so this is a low-risk scaling improvement,
not a demonstrated user-visible performance emergency. For overlap, a future grouped
reduction of the upper triangle should preserve pair identity, exact best evidence and
tie ordering; profile before replacing the clear implementation.

Keep one loaded model shared by bounded per-run indexes, not one model per visitor.
Add cold-index progress and bounded execution before pursuing persistence of vectors.
TF-IDF currently loads the full model to access its tokenizer; loading only the pinned
tokenizer is a future separation to test against identical chunk offsets. There is no
need to change the embedding model, adopt pgvector, fine-tune or change default scoring
from this engineering fixture alone.

## Simplest per-visitor isolation with the existing stack (proposal only)

Use one FastAPI service and one bounded worker, with a shared read-only loaded MiniLM
model. Assign a server-generated 256-bit random visitor ID through a signed, HttpOnly,
Secure, SameSite cookie. A visitor owns a bounded analysis run; never accept a raw
filesystem path or an arbitrary visitor ID as authorization from a request body.

Store temporary run articles and reviews in a dedicated SQLite file beneath
`runtime/visitor_workspaces/<server-generated-id>/`. Keep the existing administrative
workspace and its initialization behaviour separate. Add explicit empty initialization
for new public runs so Store's existing demo seeding remains the default for the old
workflow. Resolve store/engine through a request-scoped context; never swap one global
Store or the global engine cache between visitors. Scope import, export, article lookup,
review, discovery, results and job polling to the owning cookie.

Use a small LRU of indexes referencing the same loaded model. Start with one active
CPU analysis job and a short bounded pending queue; reject excess work with a retryable
status instead of silently accumulating requests. Set per-visitor/per-IP run quotas,
disk/cache byte budgets and idle/absolute expiry. Proposed initial retention: one hour
idle, 24 hours absolute, displayed clearly and tested. Rebuild an evicted index from its
run's stored text. Cleanup must lock a run and close SQLite handles before deleting its
directory; an active job cannot be deleted underneath analysis.

Each successful selection commit creates a collection revision. Results carry that
revision; a review based on stale content receives 409. Keep articles immutable while
one analysis snapshot is running, then publish the new revision atomically. On restart,
mark interrupted jobs failed/retryable and rebuild caches lazily. A minimal run-state
record in SQLite can support polling; Redis/Celery and PostgreSQL are not prerequisites
for a single-node portfolio release. Multiple replicas would require a different shared
storage/execution design. Anonymous cookies are bearer credentials, not user accounts.

Acceptance tests: two independent cookie jars cannot read/change each other's articles,
reviews, exports or job IDs; invalid/missing/expired cookies fail safely; guessed IDs
do not authorize access; one run's import cannot affect another; stale reviews fail;
eviction and expiry do not leak data; restart and overload have defined behaviour.

## Bounded WordPress discovery/extraction architecture (proposal only)

Release scope: public published WordPress posts discoverable through its REST API.
Unsupported/disabled APIs produce an explicit limitation, not a headless-browser or
unbounded-crawl fallback. Sitemap/RSS adapters can follow if required; URL analysis
itself is mandatory for release. Obtain the visitor's confirmation they may process
the site; robots permission and public access do not establish copyright ownership.

Flow:

1. Visitor starts an isolated run and submits a site URL. Parse/normalize it, reject
   credentials, control characters, IP literals, fragments, unexpected ports and all
   schemes except HTTPS (optional HTTP on port 80 only with explicit policy). Handle
   IDNA consistently; never use a string prefix as an origin comparison.
2. A single safe-fetch boundary resolves DNS, validates **every** A/AAAA result as a
   public unicast address, blocks private/loopback/link-local/reserved/multicast,
   IPv4-mapped IPv6 and cloud metadata targets, and connects only to a validated IP.
   Preserve original Host/TLS SNI/certificate verification. Validate the actual peer;
   never do a second unchecked DNS lookup in the HTTP client. Disable environment
   proxy inheritance and automatic redirects. A URL regex plus HTTPX defaults is
   not a complete implementation of this boundary.
3. Fetch robots.txt using the same boundary. Identify the crawler, parse the correct
   user-agent group, respect path rules and implement RFC 9309 error/cache behaviour.
   Apply a separate conservative rate limit; Crawl-delay is not standardized by the
   RFC. Robots checks do not replace SSRF protection or site authorization.
4. Discover the REST root through WordPress Link headers/HTML discovery and a bounded
   conventional probe. Support subdirectory installations and `?rest_route=/`.
   Every discovered URL is untrusted. Enforce the established origin; a cross-origin
   www/apex transition requires a narrowly verified new origin, not wildcard trust.
5. Retrieve public post metadata with explicit page/per_page and deterministic ordering.
   Suggested initial budget: 200 candidates, 20 posts/page, 10 pages. Use `X-WP-Total`
   and `X-WP-TotalPages` as hints, never permission to exceed budgets. Do not follow
   arbitrary pagination links. Deduplicate by normalized origin/post ID and approved
   canonical URL. Strip fragments/default ports and normalize hostnames without
   treating all query strings or slash differences as equivalent. Detect repeated
   pages and concurrent publication changes; the API is not a database snapshot.
6. Display titles, URLs, dates and a short excerpt. Visitor selects up to 40 articles
   (30–40 is the target, not a minimum). Fetch full `content.rendered` only for selected
   post IDs, in small batches to keep individual responses bounded. Exclude protected,
   empty or non-public content. Treat an unavailable post as a visible per-item error.
7. Parse rendered content as untrusted HTML **without executing it** or fetching images,
   scripts, styles or embeds. Preserve headings, paragraphs, lists and anchor hrefs;
   discard script/style/navigation/shortcode residue with tested rules. Decode entities,
   normalize whitespace and retain extraction provenance. Never render raw imported
   HTML. WordPress API content is often cleaner than full page HTML but plugins and
   excerpts still need fixture-based validation. Flag insufficient/partial content.
8. Resolve approved same-site anchors against post URLs, canonicalize them and map only
   selected destinations into existing_links. Ignore off-selection targets for that
   field while retaining aggregate extraction diagnostics separately. No linked target
   is fetched just because an anchor mentions it. Record exact duplicate body hashes
   separately from semantic overlap; do not silently remove different URLs.
9. Preflight article count, per-body/total characters, actual tokenizer passages and
   planned memory/queue budgets. Show omissions and failures before atomic run commit.
   Reuse the current Article schema, offset-preserving engine, link exclusions and UI
   evidence. No automatic publishing, insertion, merging or deletion.

Initial **proposed, unmeasured** fetch budgets: 3-second DNS/connect, 10-second read
inactivity, 20-second total request deadline, 180-second import-run deadline, at most
3 manually validated redirects, a hard total of 60 requests including retries/redirects,
two concurrent requests per origin and at least one
second between request starts. Respect Retry-After and use at most one bounded retry.
Cap decoded response bodies at 2 MiB, compressed transfer bytes independently, aggregate
run bytes at 20 MiB and robots input at a bounded RFC-compatible size (at least 500 KiB
parser support). Tighten limits after real fixtures; report unsupported oversized
responses rather than decompressing/buffering without a bound. DNS also needs a real
deadline: a timeout around an uncancellable resolver thread is not sufficient under
load. Verify HTTP content types, TLS certificates and allowed response status codes.

Preventive egress restrictions are recommended defense in depth for a future public
deployment, especially cloud metadata/internal networks. No infrastructure changes
are made here. The connector must not inherit AWS/application secrets or forward a
visitor's cookies/authentication headers to arbitrary sites. Log bounded status/timing
metadata, not full bodies, query secrets or rendered content.

Security acceptance fixtures must cover redirects into private networks, DNS rebinding,
mixed public/private DNS, IPv6/mapped addresses, IP encoding tricks, hostname suffix
tricks, credentials, proxy environment variables, TLS errors, decompression bombs,
slow streaming/DNS, excessive pagination, repeated pages, 429/Retry-After, robots rules,
malicious HTML and cross-run access. Use a fake resolver/transport or local fixtures
with an explicit test-only policy; never weaken production address checks to test them.

Primary design references (checked during this phase):

- WordPress posts: https://developer.wordpress.org/rest-api/reference/posts/
- WordPress discovery: https://developer.wordpress.org/rest-api/using-the-rest-api/discovery/
- WordPress pagination: https://developer.wordpress.org/rest-api/using-the-rest-api/pagination/
- OWASP SSRF prevention: https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html
- Robots Exclusion Protocol: https://www.rfc-editor.org/rfc/rfc9309

## Implementation sequence and release gates

1. **Admission and regression baseline (medium):** preserve existing defaults, add an
   analysis preflight/atomic selection contract and real-tokenizer fixtures. Use measured
   limits, visible rejection and unchanged ranking/evidence semantics.
2. **Visitor run isolation (medium/high):** cookie ownership, separate temporary SQLite,
   shared model, bounded index caches, job revision/expiry and a finite work queue.
   Pass independent-client isolation, overload, restart and cleanup tests.
3. **Safe fetch boundary (high):** pinned validated connections, redirect/robots/byte/time
   budgets and adversarial network fixtures. This must pass before arbitrary URL access.
4. **WordPress discovery and selection (medium):** bounded pagination, clear unsupported
   states, canonical identity, metadata listing and visitor-selected IDs.
5. **Extraction and analysis integration (medium/high):** sanitized structured text,
   existing-link mapping, complete preflight, atomic commit and real 30–40-article
   end-to-end fixtures. Benchmark actual extracted text; do not assume this synthetic
   corpus establishes sufficient capacity for arbitrary sites.
6. **Release verification (medium):** independent human judgements for search/link/overlap,
   measured cold/warm RAM/latency under a small concurrent visitor load, host secret/HTTPS
   and writable-storage checks, retention/privacy notice and recovery test. Website URL
   discovery, selection, extraction and analysis must all work before declaring release.

Keep FastAPI, vanilla frontend, SQLite, the pinned MiniLM model, TF-IDF baseline and
human review. The benchmark justifies engineering decisions; it cannot justify an
accuracy claim, an automatic merge policy or a production relevance threshold.
