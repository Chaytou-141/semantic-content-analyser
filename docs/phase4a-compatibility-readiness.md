# Phase 4A — Website compatibility and deployment readiness

29 October 2026 (Australia/Sydney). Baseline `1a276af`. Commit subject:
**Fix bounded XML sitemap compatibility and prepare isolated demo configuration**.
Local-only preparation; no push, deployment, live fetch, paid service or model run.
Further human evaluation is deferred: no new review packet, judgement request or ranking
change is included. Existing evidence and saved development databases are preserved.

## Minimum viable demo and changes

Reuse FastAPI, SQLite visitor workspaces, the shared MiniLM model, TF-IDF, CollectionService
atomic admission, SafeFetcher and the existing select/preview/import UI. Keep the local
CSV/sample experience. The smallest initial audience is a **password-gated, limited
portfolio demo with separate browser-owned workspaces**, rather than an unbounded
anonymous service. A shared password is an entry gate, not per-user authentication or
sufficient abuse prevention.

### XML compatibility

`semantic_analyser/websites.py:WebsiteService.start` previously replaced any explicit
non-`.xml` sitemap with `/sitemap.xml`. Query endpoints and extensionless maps could
therefore silently analyse the wrong sitemap. It now preserves the normalised explicit
URL. In XML mode, a bare origin/root without query is treated as a homepage to discover
same-host HTML/robots-advertised maps, using conventional sitemap defaults when none are
advertised. This mode never inserts a WordPress REST request. Non-root/query URLs are
treated as explicit map documents. Auto/WordPress behaviour retains the existing REST
preference and 404/410-only absence fallback; no auth/robots/backoff failure is bypassed.

`semantic_analyser/extraction.py:sitemap` used local tag names after discarding namespaces.
An image extension's `<image:loc>` directly under `<url>` could become an article URL;
foreign locations could also reset the primary URL buffer or hit its limit. The parser
now matches the exact namespace-qualified root/entry/loc path. Standard sitemap namespace
`http://www.sitemaps.org/schemas/sitemap/0.9`, default/prefixed forms and legacy namespace-free
maps work. Image/news/alternate-language extension data is not interpreted as article
locations. UTF-8/UTF-16 XML and entity-escaped query strings remain supported.

Empty locations no longer create a homepage candidate. A foreign namespace root and
nested markup inside a primary loc fail explicitly. Foreign extension text still counts
toward overall bytes/nodes/depth, but not the primary 2,048-character URL limit. DTDs,
custom/external entities and malformed XML remain rejected; stylesheet processing
instructions never fetch resources. `homepage_metadata` also skips link elements with
no href, instead of treating them as references to the current page.

`queue_maps` now warns when bounded queue/depth truncation excludes an unvisited map;
`read_map` warns when a document reaches 200 returned locations, even without pending
documents. At exactly 200 this is deliberately “may not be complete”, not an invented
claim that more URLs were observed. No discovery/capacity limit was increased.

The existing UI already exposes an XML sitemap method; no frontend rewrite/change was
needed. XML maps can list non-article pages; visitors must select the intended articles
and inspect extracted previews. This is not a general crawler or article classifier.

### Deployment configuration

`deploy/aws/compose.production.yaml` previously defaulted to shared local mode with
website fetching disabled. It now explicitly sets:

```text
WORKSPACE_MODE=visitor
VISITOR_WORKSPACE_ROOT=/app/runtime/visitors
ENABLE_WEBSITE_FETCH=true
```

Production mode, required password/signing-secret substitutions, no published app port,
Caddy entry point, named volume, privilege restrictions, restart and log rotation remain.
The previous local SQLite file is not removed, reused as a shared public collection or
migrated. New visitor directories use the existing ownership/revision/cleanup policies.
The local `compose.yaml` and source defaults are unchanged. No runtime environment was
switched and no container was started by editing the template.

YAML parsed with already-installed PyYAML, environment assertions and explicit production
`Settings.validate()` passed using dummy credentials. This is **static validation**, not
`docker compose config`, a resolved Linux image build or a successful public deployment.
Docker CLI is unavailable on this machine. `docs/aws-deployment.md` now distinguishes
browser-owned temporary data from the legacy local-only SQLite backup example.

## Verification and measurements

Reproductions before source changes: **10 new tests failed / 3 passed in 1.50s**,
demonstrating rewritten endpoints, missed advertised index, namespace confusion, empty
metadata/invalid URL structure and silent depth truncation. After fixes, the focused
website set passed 55 tests in 7.73s. Additional cases were then added for encoding,
stylesheets, candidate-cap visibility and root access denials.

Final relevant regression selection: **235 passed, 1 skipped in 30.85s**. Files:

- `tests/test_website_compatibility.py`: new endpoint/root/namespace/metadata/cap cases,
  explicit robots/access denial, 40-article sitemap flow and visitor API import/rollback.
- `tests/test_websites.py`: existing WordPress and XML workflows, extraction, source/link
  mapping, request/selection/depth/character bounds, ownership, revision and expiry.
- `tests/test_safe_fetch.py`: all-address DNS validation/pinning, rebinding, IPv4/IPv6,
  unsafe redirects, robots, timeouts, TLS and encoded/decoded/compression bounds.
- `tests/test_safe_fetch_api.py`: owner/revision checks, bounded execution and safe errors.
- `tests/test_visitor_workspaces.py`: cross-browser access, concurrent edits/imports,
  queue/timeouts, restart, eviction, expiration and cleanup.
- `tests/test_collection_admission.py`: input/tokenizer passage constraints, preflight
  failure, atomic replacement and editorial-review rollback, using test models.

The skip is the existing symlink cleanup case at `tests/test_visitor_workspaces.py:295`:
this Windows account cannot create symbolic links. It must be exercised on Linux; other
cleanup/ownership tests passed. No full suite, browser suite, actual MiniLM loading,
ranking evaluation or historical performance benchmark was run. A follow-up assertion
tightened the homepage-advertised-map route check; only the affected new file was rerun
after that test-only edit. Exact final evidence is in `docs/phase4a-verification.json`.

The synthetic XML-root/index/URL-set fixture extracts **40 articles in 44 requests**
(robots, homepage, index, URL set, 40 articles). This proves bounded offline workflow
behaviour with the existing parser/limits; delay is disabled and DNS/transport are
controlled. It is not a real-site latency, memory, real-tokenizer capacity or throughput
benchmark. The API fixture also rejects cross-session selection, preserves the original
collection on simulated preflight failure and commits only after successful admission.

Reproduce the relevant tests without network/model downloads:

```powershell
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
.\.venv\Scripts\python.exe -B -m pytest -q --tb=short tests/test_website_compatibility.py tests/test_websites.py tests/test_safe_fetch.py tests/test_safe_fetch_api.py tests/test_visitor_workspaces.py tests/test_collection_admission.py
```

## Bounds retained

- Network: public HTTP(S) only; all DNS answers validated, numeric peer pinning and TLS
  verification; same-host redirects, no HTTPS downgrade, auth/robots/backoff fail closed.
- Per run: 60 attempts, 180 active-fetch seconds, fixed 15-minute absolute lifetime,
  20 MiB aggregate wire/decoded, shared per-site pacing/concurrency. Per fetch: 20 seconds,
  2 MiB encoded/decoded; existing DNS/connect/read limits unchanged.
- Discovery: 12 documents, 10 REST pages, 200 candidates/returned locs, index depth <=3;
  XML input <=2 MiB, <=20,000 elements, depth <=32, <=100 attributes/element.
- Import: selection <=40; collection <=100 articles, <=20,000 body characters/article,
  <=250,000 collection characters and <=800 real-tokenizer passages at atomic admission.
- Visitor/executor: signed secure production cookies, revision checks, one active task
  with two queued by default, cooperative timeout and cleanup leases. No model copies
  per visitor or changes to ranking, offsets, SQLite schema or editorial decisions.

## Docker assessment and remaining release blockers

The architecture is a reasonable basis for a limited demo: one worker, non-root image,
CPU-only pinned model revision baked into its cache, offline model flags, bounded app
execution, HTTPS reverse proxy, internal app port, persistent private volume and health
check. This static assessment does not establish that pinned dependencies resolve/build
on Linux or that the image is patched, scanned, correctly sized or production-safe.

Before exposing the demo, address/verify:

1. **Local Linux container proof:** resolve/build the image and test startup/model cache,
   health checks, proxy HTTPS/secure cookies, two real browser workspaces, website/CSV
   workflows, restart and UID 10001 volume ownership. Docker is unavailable here and no
   image/package pulls were attempted. Existing CI configuration is not proof of a passed
   run for this commit; its current container smoke uses default local mode, not the new
   visitor/website configuration.
2. **Abuse/fairness:** password protection and bounded queues are insufficient for public
   visitors. Assess ingress/session-creation/run throttles and overload UX. Existing
   32-workspace cap/five-second run cooldown can still be exhausted by repeated identities.
3. **Proxy trust:** Docker CMD still allows forwarded headers from `*`. App port is not
   published in production Compose, but trust must be narrowed to the actual proxy path
   before deriving rate-limit identity from IP headers. Do not expose direct app access.
4. **Egress:** application DNS/SSRF checks are necessary but not a firewall. Terraform
   currently permits all IPv4 outbound traffic; assess IPv4/IPv6/private/metadata denial,
   controlled DNS access, public HTTP(S) egress and operator public IP deny ranges. No
   firewall/VPC configuration was changed or claimed verified.
5. **Capacity/containment:** Docker Compose does not set CPU/memory/PID/disk quotas. Measure
   concurrent visitors on the intended runtime, configure limits/supervision and monitor
   memory, queue delay and disk. Cooperative thread deadlines cannot kill stuck native
   work. Earlier single-user benchmarks do not establish hosting capacity.
6. **Retention/operations:** verify cleanup/restart and failure paths on Linux, retain
   stable private signing keys, disclose idle/absolute expiry and delayed active-work
   cleanup, decide whether temporary visitor content is backed up at all, and prevent
   logs/backups from accidentally retaining content. No new privacy or uptime guarantees.
7. **Compatibility/quality limits:** no new live sites were contacted. Earlier successful
   real WordPress evidence is Freeze Edge only; its sitemap endpoints returned 404.
   Real XML/index/non-WordPress validation is still absent. Gzip sitemap files, cross-host
   www redirects, RSS, JS-only/ambiguous HTML, non-UTF-8 article HTML, protected content
   and nonstandard REST routing remain unsupported. An HTML catch-all at the REST route
   still needs explicit XML mode rather than a speculative automatic bypass.

## Recommended Phase 4B

Make the next phase **bounded demo operations and local container verification**, not
further editorial work: implement narrowly scoped ingress/session/run fairness and
trusted-proxy handling; define a demonstrable egress/resource/retention policy; update
the disposable container smoke to visitor mode with controlled local fixtures and verify
the above operational cases when Docker is available. Keep anonymous exposure gated
until those controls are validated. No ranking/model changes, architecture replacement,
live fetch or deployment should be inferred from that recommendation. Public-site
validation remains a separate explicitly authorised action. No AWS resources are needed
to verify the application/container locally.
