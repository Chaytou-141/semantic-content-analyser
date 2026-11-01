# Public portfolio release checklist — Phase 4C local rehearsal update

1 November 2026. Phase 4C built and ran the existing app in disposable local Linux
containers: final Phase4B smoke passed, 309 targeted Linux tests passed without skips,
and nine extended runtime checks passed. Caddy local-CA TLS, visitor separation, short
expiry/cleanup, configured cgroupv1 limits, reduced-limit enforcement and offline UI
fixtures are now measured. No public deployment/ACME, live import, model benchmark or
production-compatible egress firewall was verified. Detailed limits and reproduction:
`docs/phase4c-local-docker.md`, portable evidence `docs/phase4c-verification.json`.
Earlier dated paragraphs below remain historical; Docker-unavailable claims apply to
Phase4B, not the current rehearsal.

30 October 2026. Phase 4A makes bounded sitemap compatibility fixes and corrects the
production Compose environment for isolated visitor workspaces/website import. No
infrastructure was provisioned and nothing was deployed. Tests and one-site evidence
establish specific behaviour, not production readiness. Further human editorial
evaluation is intentionally deferred; no new packets or labels are required for Phase 4B.

Phase 3F: 14 user decisions after AI screening and 45 AI-assisted assessments reconcile
with the frozen packet. Only 8/44 candidates and 6/15 overlap pairs have user decisions;
all independent attestations are false. No complete human top-3/top-5 cutoff exists,
so neither method has human precision metrics. The combined file is not independently
validated ground truth. Evidence: `docs/phase3f-evaluation.md`,
`evaluations/phase3f/results.json` and `error-analysis.json`. No release blocker below
was closed merely by consolidating these reviews. Phase 3G prepared a new metadata-blind
packet but supplied no new human labels. Historical review evidence remains unchanged.
Phase 4A results: `docs/phase4a-compatibility-readiness.md` and
`docs/phase4a-verification.json`.

Phase 4B adds configurable single-process API/session/wire-attempt budgets, exact-peer
proxy identity, SQLite/storage admission and container resource settings. Relevant tests:
271 passed, one Windows symlink test skipped. Docker CLI was unavailable; no Linux
container verification or network firewall test passed. See `docs/phase4b-demo-operations.md`
and `docs/phase4b-verification.json`. This remains preparation for a limited gated demo.

| Area | Existing evidence / boundary | Required before anonymous public release |
| --- | --- | --- |
| Visitor isolation | Signed cookie-owned SQLite; Phase4C verifies two HTTPS cookie clients, disposable sentinel review separation and cross-revision rejection; Linux ownership/cleanup tests pass | Retest on intended host/HTTPS chain; keep visitor mode explicit, never expose shared local mode to unrelated visitors |
| Deployment template | Phase4C release image runs non-root with private named storage and cached offline model; two real browser sessions use local HTTPS, static assets and controlled UI snapshots; production password gate retained | Public DNS/ACME, intended host, upstream proxies and load remain unverified. Local-CA TLS is not a public certificate; retain the gate |
| Abuse/fairness | Phase 4B bounds API concurrency/rates, new sessions and wire attempts across owners/runs, with global caps, finite accounting state and Retry-After; existing one-worker queue retained | Assess NAT/IPv6 behaviour and process-restart budget reset, upstream connection/DDoS policy and actual target load. Counters are single-process, not durable distributed enforcement; retain password gate |
| Outbound requests | Existing DNS/IP/TLS/robots controls retained; optional exact FETCH_ALLOWED_HOSTS, operator deny CIDRs and cross-run/global wire budgets tested with controlled fixtures | Enforce/test kernel/network egress including DNS resolver exceptions and IPv4/IPv6 metadata/private destinations. AWS Terraform still permits all IPv4 egress; bridge/application policy is not a firewall |
| Network trust | Phase4C verifies no published app port, loopback-only Caddy bindings, local TLS/HTTP redirect and API429 despite varying forwarded/custom identity headers; Uvicorn no-proxy-headers retained | Upstream CDN/proxy changes require new trust review. The lab's Caddy-only ingress bridge is not production egress containment; intended network/subnet must be checked |
| Resource limits | Phase4C inspects cgroupv1 app4GiB/2CPU/PID128, UID10001, read-only root, dropped caps/no-new-privileges; reduced probes demonstrate throttling/OOM/PID exhaustion; Linux tests cover SQLite507 rollback and cooperative deadlines | No full-analysis capacity/load or app4GiB exhaustion was measured. Physical/WAL totals remain soft; supply filesystem quota/monitoring. Caddy remains root/writable with its observed default swap allowance; hardening review outstanding |
| Temporary data | Defaults idle1h/absolute24h/sweep60s retained; Phase4C observes a real shorter-retention container delete its workspace and return410; restart smoke and Linux lease/symlink protection pass | Default long windows were not wall-clock waited. Publish retention/deletion notice, verify operator backups/failure alerts and quotas. Cleanup is not secure erasure; developer evaluation caches persist separately |
| Hosting | Linux Docker Desktop startup/health and cached model load verified; app working-set spot376.6MiB and proxy19.5MiB, not analysis peak. No inference/benchmark ran | Validate intended host, immutable base/transitive dependencies, advisory scan, reverse-proxy timeouts, load and operator recovery. Idle observations are not a RAM/visitor-capacity guarantee; no cloud resources provisioned |
| Editorial quality | Earlier mixed/provisional evidence preserved; no complete independent metric cutoff; further review intentionally deferred | Describe the demo as experimental editorial suggestions, with evidence and manual decisions. Do not claim independently validated accuracy or automatic insertion/merge/deletion. Future ranking changes need separate evidence; no new labels requested in Phase 4A/4B |
| Compatibility | Freeze Edge evidence and offline 40-article workflows retained. Separately authorised Urban Turf index/blog-map200 evidence and cached homepage-to14-candidate replay exist; Phase4C performs no new live fetches | Original transient HTTP400 remains unexplained. Article extraction quality/global Wix compatibility is not established by sitemap success. Cross-host redirects, gzip sitemap files and JS-only/ambiguous articles remain unsupported |
| Operations/privacy | Existing sanitized fetch errors and bounded runtime storage | Define operator visibility for overload, timeouts and cleanup failures without logging secrets/full content unnecessarily; decide authorised evaluation-data retention/publication separately |

Relevant sources: `semantic_analyser/{config,workspaces,execution,fetch_policy,
fetch_transport,safe_fetch,collections,api}.py`, `Dockerfile`,
`deploy/aws/compose.production.yaml`, `infra/aws/main.tf`.

The next milestone is Phase4D: local public-import-compatible egress/operations and build
input audit, followed by targeted runtime checks. The offline app's lack of a default
route is not a deployable fetching firewall: a raw controlled private-peer/nonstandard-port
connection succeeded while SafeFetcher rejected private destinations. No public/DNS/metadata
target was probed. Retain FastAPI, SQLite, shared MiniLM/TF-IDF and the password gate.
No deployment/push or further editorial evaluation is implied; live requests still need
explicit authorisation. No PostgreSQL, Redis, frontend rewrite or paid service is needed.
