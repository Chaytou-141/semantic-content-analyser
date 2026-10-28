# Phase 3A: bounded website-fetching foundation

Report prepared 29 October 2026 (Australia/Sydney). Baseline: `6df9b1c`, Phase 2B.
Implementation commit subject: `Add bounded SSRF-protected website fetch foundation`.
Resolve its local hash with `git log -1 --format=%H --grep="Add bounded SSRF-protected website fetch foundation"`.

## Scope and result

This phase adds a reusable, owner-bound HTTP fetching service and an opt-in diagnostic
API. It does not discover WordPress posts, extract articles, change the UI, save fetched
content, change infrastructure or deploy anything. Website discovery remains a core
release requirement for Phase 3B and subsequent work.

The MiniLM model, TF-IDF, passage offsets, semantic scoring, collection admission,
SQLite schema and existing CSV/review workflows are unchanged. Fetching does not load
the model. The existing 250,000-character and 800-passage admission limits remain.

## Architecture and source map

| Source / entry point | Responsibility |
| --- | --- |
| `semantic_analyser/fetch_policy.py:39` `FetchLimits` | Fixed resource defaults; no network I/O |
| `fetch_policy.py:81` `public_address` | Conservative public IPv4/IPv6 admission |
| `fetch_policy.py:117` `normalize_url` | Syntax, credentials, port and path normalization |
| `fetch_policy.py:178` `FetchSession`; `:190` `Budget` | Server-owned run scope, deadlines and cumulative counters |
| `semantic_analyser/fetch_transport.py:30` `ProcessResolver` | Killable, isolated OS DNS lookup |
| `fetch_transport.py:59` `resolve_public` | Validate every answer before any connection |
| `fetch_transport.py:75` `PinnedConnector` | Numeric-IP socket connection, peer verification and verified TLS |
| `fetch_transport.py:133` `DeadlineReader` | Bound socket reads, wire bytes and header input |
| `fetch_transport.py:180` `validate_headers`; `:206` `SocketTransport` | Strict HTTP/1.x response handling and bounded decompression |
| `semantic_analyser/robots_policy.py` `parse_robots`, `RobotsPolicy.allows` | Bounded robots parser and operation-limited matcher |
| `semantic_analyser/safe_fetch.py:24` `SiteGate` | Shared per-host concurrency, delay and backoff |
| `safe_fetch.py:73` `SafeFetcher` | Robots, redirect and request orchestration |
| `semantic_analyser/api.py:322` `check_website` | Existing workspace/executor integration; metadata-only response |
| `semantic_analyser/config.py`, `schemas.py`, `workspaces.py` | Feature flag, request schema and owner-local transient run state |
| `tests/test_safe_fetch.py`, `tests/test_safe_fetch_api.py` | Network, adversarial and API integration checks |
| `scripts/verify_phase3a.py` | Isolated full-suite/offline-model/browser verification |

Paths without the package prefix in the table are relative to `semantic_analyser/`.
Line references identify the implementation reviewed for this report.

The request path is:

1. FastAPI applies the existing session, same-origin header and body-size protections.
2. `execute` checks the workspace revision and enters the existing bounded executor
   with the workspace lock and cleanup lease.
3. `SafeFetcher.fetch` verifies the server-supplied owner, locks the run and checks its
   hostname scope. Caller-supplied workspace/run IDs are not accepted.
4. Robots and content requests both pass through the shared host gate. Each request
   resolves DNS again and validates the entire returned address set.
5. A socket connects directly to a validated numeric address. It never independently
   resolves a hostname or uses an environment proxy. Its peer address is checked.
   HTTPS uses the original hostname for SNI and certificate/hostname verification.
6. Response headers, framing, MIME, compression, byte limits and deadlines are checked.
   Every followed redirect repeats admission, DNS pinning and applicable robots checks.
7. The internal service returns bounded bytes for future adapters. The diagnostic API
   returns only URL, status, type, counts and SHA-256; it neither returns nor stores HTML.

The DNS child uses fixed Python code, `-I -S`, a small OS-only environment, no shell,
at most 64 answers and bounded output validation. Timeout kills and reaps the child.
This avoids leaving an uninterruptible resolver thread occupying the analysis worker.

## Destination policy

Only HTTP on port 80 and HTTPS on port 443 are accepted. URLs are limited to 2,048
characters after encoding. Credentials in URL authority and common credential query
parameters are refused; no cookies, authorization or proxy credentials are forwarded.
Nonpublic, scoped, mapped, transition, multicast, reserved, metadata and platform
addresses are refused. Mixed public/private DNS answer sets fail as a whole.

IDNA hostnames and canonical numeric IPv4/IPv6 are supported. Controls, ambiguous
numeric hosts, malformed escapes, encoded path separators and duplicate path slashes
are rejected. Literal and percent-encoded unreserved dot segments are normalized
before both robots matching and the actual request.

A run stays on one normalized hostname. Same-host HTTP-to-HTTPS upgrade is allowed;
HTTPS downgrade, cross-host redirects (including apex-to-www) and loops are rejected.
`FETCH_DENY_CIDRS` optionally adds operator-owned public infrastructure ranges to the
deny policy. This does not replace a future deployment-specific egress policy.

## Resource limits and rationale

Defaults are application policy, not proven hosting capacity or performance guarantees.

| Limit | Default | Reason |
| --- | --- | --- |
| DNS | 3 seconds | Bound OS resolver stalls with a killable child |
| Connection including TLS | 3 seconds across approved address attempts | Avoid multiplying connect time by DNS answer count |
| Read inactivity | 5 seconds | Refuse stalled headers/body |
| Entire `fetch` call | 20 seconds | Includes robots, DNS, delays, redirects, body and decompression; stops trickle streams |
| Owner run lifetime | 180 seconds, from creation | Bound a future multi-page workflow; not refreshed per fetch |
| Network attempts per run | 60 | Includes robots, redirects and failed DNS; no automatic retry loop |
| Content / robots redirects | 3 / 5 | Bound redirect work and loops |
| Response encoded / decoded body | 2 MiB / 2 MiB | Bound storage and expansion independently |
| Response headers | 32 KiB | Bound header parsing; conservative read-ahead may reject a near-limit response |
| Cumulative run wire / decoded | 20 MiB / 20 MiB | Includes failed attempts and robots; wire count includes HTTP overhead |
| Robots decoded body / rules | 512 KiB / 4,096 | Permit ordinary policies while bounding memory and parsing |
| Robots matching work | 200,000 scan steps per decision | Prevent attacker-controlled wildcard CPU explosions |
| Host concurrency | 1, shared across owners | Prevent simultaneous requests to the same host |
| Minimum host pause | 1 second after completion | Polite pacing, including after robots |
| Supported Crawl-delay | Up to 30 seconds | Larger delays are refused; applicable delay may exhaust the shorter call budget |
| Robots cache | Up to 300 seconds, owner-local | Respect no-store/no-cache and shorter max-age; no global content cache |
| Host bookkeeping | 256 states; inactive expiry 900 seconds | Bound memory; never evict active/backed-off hosts to bypass limits |

Up to one detection byte can be read beyond the raw wire/header limit before rejection.
Identity input is read in chunks of at most 8 KiB. zlib output uses an explicit output
cap rather than an unbounded `flush`. Transient buffers and Python parsing objects add
overhead; these byte limits do not claim a process-wide hard RAM sandbox.

429/503 responses impose a minimum 60-second host pause, extended by a valid larger
Retry-After. Requests are not automatically retried. A pause that will not fit the call
budget returns a controlled error. Fixed user-facing error messages omit resolved IPs,
raw socket exceptions, certificates, DNS details and upstream response bodies.

The existing executor remains one active task and two pending tasks by default.
Fetching shares that capacity with analysis; it does not introduce a second unbounded
thread pool. Cancellation/deadlines retain the worker slot and workspace lease until
work actually stops. These are conservative defaults for this phase.

## Robots behaviour

The product token is `SemanticContentAnalyser` (wire User-Agent
`SemanticContentAnalyser/0.1`). The parser merges matching product groups, otherwise
uses wildcard groups; it handles longest matching rule, Allow on ties, `*`, terminal
`$`, UTF-8 and percent normalization. Empty/comment lines do not discard group rules.
The matcher is explicitly work-bounded rather than an attacker-controlled regex.

404/410/204 permit access; 401/403 deny; unreachable/5xx/invalid policies fail closed.
Robots redirects use the same pinned transport and host scope. Excessive rule counts,
line lengths, matching work and unsupported delays fail closed. Crawl-delay is a
supported extension, not part of the RFC 9309 core requirements.

This is a conservative REP subset, not a claim of complete RFC conformance. In
particular, cross-authority robots redirects are refused and invalid UTF-8/oversized
policies are refused rather than recovered. Robots is a politeness signal, not an
authorization mechanism or proof of content ownership.

## API and ownership

`POST /api/website/check` is disabled by default (`ENABLE_WEBSITE_FETCH=false`). There
is no new UI. Enabling it permits a metadata-only diagnostic using the current signed
workspace cookie, `X-Workspace-Request: true`, and `If-Match` collection revision in
visitor mode. Local mode retains its existing trusted-demo semantics.

Each workspace holds its own `FetchSession`, robots cache and counters; no other
visitor can address it through a run ID. Site pacing is shared for politeness, not
content. Workspace expiry drops transient state and existing leases protect active
work. No fetch state/body is written into the saved SQLite collection. Restart clears
fetch runs and caches. A collection revision change starts a new owner-bound run;
an expired run on an unchanged collection is refused until a future explicit run-start
workflow is added. Phase 3B must provide that workflow without requiring a collection edit.

Do not expose the legacy shared local mode as a public multi-visitor service. Existing
visitor-mode signing/HTTPS/production configuration requirements still apply.

## Verification evidence

The final, measured record is [phase3a-verification.json](phase3a-verification.json).
The final suite passed **188 tests**, with **1 skipped**, in **23.47 seconds**. The skip
requires Windows symlink permission; the real TLS certificate tests ran successfully.
The runner's clock records 28 October; this report uses the 29 October client context.
The offline regression confirmed two independent browser contexts, one loaded model,
separate embedding arrays, 20 exact search passages and real link/overlap evidence.
Two queued real comparisons took **15.722 seconds** combined. Peak process working set
was **718.63 MiB**, excluding browser processes. These timings are regression observations,
not fetch throughput benchmarks or evidence of an inference performance improvement.
Run `./.venv/Scripts/python.exe -B scripts/verify_phase3a.py` from the repository root.
The script sets an isolated bootstrap database, offline model flags and ignored output
paths. It runs the full suite, then copies the historical Phase 2B real-model verifier
with asserted root/output-path overrides. Historical scripts and results are not edited.

The tests exercise:

- Public/private mixed DNS, rebinding between robots and content, numeric socket
  destinations, no second resolution, peer mismatches, IPv4/IPv6 and metadata ranges.
- Unsafe credentials/ports/protocols, scope escapes, redirect loops, upgrades/downgrades,
  dot-segment robots bypass attempts and ambiguous paths.
- Actual loopback HTTP/TLS parsing, certificate trust and hostname mismatch, proxy
  environment ignored, and absence of forwarded cookies/authorization.
- Header size/format, conflicting framing, duplicate critical headers, invalid chunks,
  interim responses, truncated bodies, unsupported MIME and authentication errors.
- Valid gzip/deflate, truncated/concatenated gzip, a 4 MiB decoded bomb rejected under
  a 1 KiB test cap, run budgets and request quotas.
- Stalled DNS child termination, connect/TLS timeouts, read inactivity and continuous
  slow headers/body bounded by the overall deadline.
- Robots status cases, merged groups, blank lines, encoding, wildcard work limits,
  Crawl-delay, shared-host concurrency and Retry-After without retries.
- Owner/revision checks, separate visitor counters, no model initialization, no article
  mutation, executor overload and timeout retaining cleanup leases.

Fixtures use a test-only connector to map logical public addresses to controlled
loopback servers. Production has no allow-private switch. Default numeric dialing and
peer checks are separately tested. TLS certificates are temporary test artifacts made
with the already-installed OpenSSL executable. No packages were installed.

The offline real-model regression checks two independent Chromium contexts, one shared
MiniLM construction with separate indexes, preserved Phase 1B rankings, passage/link/
overlap evidence, stale reviews and real-tokenizer 800/801-passage admission. It also
runs the existing visitor browser smoke. These are engineering checks on synthetic
content, not recommendation-quality measurements or a public-load benchmark.

518 protected files were hash-checked: existing development databases/sidecars,
datasets, benchmarks, UI, deployment artifacts and historical verification records.
No protected file changed. Detailed temporary logs remain under ignored runtime/phase3a.

## Remaining risks and limitations

- Address filtering/pinning cannot determine that an operator-owned public address is
  safe, prevent unusual network routes from mapping public IPs internally, or prove
  authorization. Deployment needs explicit public-infrastructure denies and assessed
  network-level egress restrictions; none were deployed in this phase.
- This implements a strict HTTP/1.x subset using the standard library, not a new
  general-purpose browser. HTTP/2/3, Brotli, raw deflate and concatenated gzip are not
  supported. Strict headers, MIME and redirect/path policy reject some legitimate sites.
  Independent security review and broader protocol fuzzing remain necessary.
- URL authority credentials/common query tokens are rejected and no auth is sent,
  but arbitrary secret query names or a 200-response login/paywall cannot be identified
  reliably. Future UI must ask for public unauthenticated content only.
- There is no per-IP fairness, bot defense or global long-term visitor quota. Finite
  queues/runs bound individual work, but repeated new sessions/revisions can consume
  ongoing capacity. Host pacing keys normalized hostnames, not registrable domains or
  shared IP addresses; aliases do not share one gate. Restart resets counters/backoff.
- DNS process startup/cleanup, OS scheduling and native TLS calls are not hard real-time
  guarantees. A severely unhealthy OS or permanently stuck native operation can still
  require an operator restart. Existing model-thread cancellation limitations remain.
- The metadata endpoint does not expose content, but URLs themselves may contain
  private information. No content retention policy or website-run UX exists yet.
- Certificate verification uses system trust and does not claim additional certificate
  revocation enforcement. No sustained multi-user load, container or hosting validation
  was performed here. Unit tests and local fixtures do not establish production readiness.

## Phase 3B integration proposal

1. Add an explicit signed-workspace-owned website run with a starting collection revision,
   bounded lifecycle and deliberate cancel/restart. Reuse `FetchSession` and the executor;
   never reset quotas per page or accept owner IDs from the browser.
2. Use bounded GET requests for WordPress REST discovery, starting with at most 10 pages
   of 20 post summaries (200 candidates). Add only necessary bounded response metadata
   such as `Link` and `X-WP-TotalPages` to the current header whitelist. The transport
   currently does not expose these headers. Require explicit handling of www redirects
   instead of silently weakening the host scope.
3. Show candidate titles/URLs and permit selection of approximately 30–40 posts (initial
   maximum 40). Deduplicate canonical URLs/post IDs and content hashes. Keep all selected
   fetches inside shared run request/byte/time budgets; report bounded partial failures.
4. Extract text server-side without running JavaScript, rendering external resources,
   or following embedded URLs. Bound HTML parser work, normalize useful paragraphs,
   and map same-site links to selected article IDs. Rendering any extracted text must
   retain output escaping. Hostile markup needs its own tests and parser choice review.
5. Preview candidate articles and run the existing real-tokenizer `CollectionService`
   preflight. Only an explicitly confirmed, valid snapshot replaces articles/reviews
   atomically using the original `If-Match`. Failure must preserve existing data.
6. Test pagination loops, duplicate URLs, auth/robots/redirect failures, malicious markup,
   partial extraction, stale collections and cross-visitor access. Verify actual 30–40
   article workloads before adjusting any fetch/admission/concurrency limits. Consider a
   small bounded I/O lane only if measured contention justifies it.

The service also accepts XML/RSS MIME types for future adapters, but no sitemap/RSS
parser is implemented. Such adapters need separate entity/DTD, document-size and
pagination controls. No PostgreSQL, Redis or external API is needed for this phase.

## Primary references used in design review

- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html): complete DNS answer validation and avoiding unchecked redirects.
- [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html): robots groups, matching, redirects and caching; deliberate stricter policies are noted above.
- [Python 3.12 http.client](https://docs.python.org/3.12/library/http.client.html), [ssl](https://docs.python.org/3.12/library/ssl.html) and [zlib](https://docs.python.org/3.12/library/zlib.html): transport/parser, verified TLS and bounded decompressor primitives.
