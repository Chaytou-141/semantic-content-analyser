# Public portfolio release checklist - Phase 4E image/plan review

9 November 2026 local remediation update: all three production images rebuilt
locally and freshly rescanned. App and egress now report zero High/Critical;
Caddy reports zero Critical and one unfixed High (Go JOSE v3, configuration-scoped
public reachability not identified). Patched Debian/Alpine zlib, Debian apt and Go
compression versions were checked in the rebuilt images. The production Caddy
admin endpoint is disabled. Windows suite: 440 passed, 14 skipped. See
`docs/public-release-review.md` for versions, limitations and scan evidence.
The images were not deployed; history privacy/rights, Linux CI, intended-host
checks and explicit residual-risk review remain open. Earlier dated records below
are historical snapshots, not the current scan outcome.

9 November 2026 maintainer decision: the historical personal email is intentionally
public; no history rewrite is requested. The remaining Go JOSE v3 High advisory is
accepted for a private merge review under the current Caddy configuration, with
admin disabled and no public JWK route. This is not a patch, scanner suppression,
deployment approval or permission to change repository visibility. Reassess on
configuration or upstream changes; independently review historical publication
material before making the repository public.

2 November 2026, Phase4E: clean-runtime Caddy security rebuild verified locally;
0 Critical/1 High proxy findings remain (six total rules).175 distinct targeted tests,
nine container checks and76 controlled HTTP exposure requests pass. All17 app/eight
proxy filesystem layers inspected. Nested build-context and static-file protections
added; no UI/model/ranking/data changes. Fresh app Scout scan failed for disk space;
complete final Caddy Dockerfile build passes with cache and identical tested runtime
files/config. Current-feed scan of unchanged app components passes39 rules/5 High;
this is not a fresh new-app index. No cache-free replay. Remaining OS/proxy advisories
are retained with package-level dispositions, not suppressed. No public readiness.
See docs/phase4e-security-review.md, phase4e-verification.json, vulnerability CSV and
phase4e-aws-plan.md for primary sources, scope, budgets and prelaunch gates.
Production now requires explicit PROXY_IMAGE; no fallback to the old proxy. AWS plan
is conditional: Lightsail8GB aroundUSD50/month, EC2 aroundUSD95; no resources created.
Earlier dated evidence below is historical and must not override this qualification.

2 November 2026. Phase4D verifies namespace kernel egress on disposable Linux Docker:
288 targeted tests and eight runtime checks passed, including public-classified local
IPv4/IPv6 HTTPS targets, private/metadata/loopback denial, isolated discovery/extraction,
restart, stale-owner503 and drift quarantine. No live website import or deployment.
Python audit reports zero known findings for50 installed packages, but image scans
still report high/critical advisories: app39, owner40 and Caddy48 rules. These are
package/advisory matches, not established exploitability or a clean bill of health.
Release remains blocked. Details/limits: docs/phase4d-local-egress.md and
portable evidence docs/phase4d-verification.json. Earlier dated evidence is historical.

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
| Image security (4E) | Clean Alpine Caddy2.11.7 rebuild, Go1.26.10/x-net0.62/v4JOSE4.1.6, six advisory rules/zero Critical/one High; frozen review locks; no suppressions | Disposition unfixed v3 JOSE/other advisory and Debian findings; complete fresh new-app index/release provenance on adequate disk |
| Source/secret exposure (4E) | Explicit six assets/static allowlist; recursive private-context exclusions;76 auth/anonymous HTTPS probes; all17 app/eight proxy layers inspected; known credential/history checks clean | Private ECR/least-privilege pulls; image holders can read backend source; Docker operators can read runtime environment/volumes. Unknown credentials require continuing review |
| AWS recommendation (4E) | Conditional Lightsail8GB x86 VM aboutUSD50/month; EC2t3.large Sydney aboutUSD95 with IAM/SSM advantages; no resources created | Agree budget/secrets/guest monitoring/quotas/selective recovery; separately authorise intended-host testing, public ACME and exposure. Managed services do not inherit the verified kernel policy |
| Visitor isolation | Signed cookie-owned SQLite; Phase4C verifies two HTTPS cookie clients, disposable sentinel review separation and cross-revision rejection; Linux ownership/cleanup tests pass | Retest on intended host/HTTPS chain; keep visitor mode explicit, never expose shared local mode to unrelated visitors |
| Deployment template | Phase4C release image runs non-root with private named storage and cached offline model; two real browser sessions use local HTTPS, static assets and controlled UI snapshots; production password gate retained | Public DNS/ACME, intended host, upstream proxies and load remain unverified. Local-CA TLS is not a public certificate; retain the gate |
| Abuse/fairness | Phase 4B bounds API concurrency/rates, new sessions and wire attempts across owners/runs, with global caps, finite accounting state and Retry-After; existing one-worker queue retained | Assess NAT/IPv6 behaviour and process-restart budget reset, upstream connection/DDoS policy and actual target load. Counters are single-process, not durable distributed enforcement; retain password gate |
| Outbound requests | Phase4D actually enforces namespace IPv4/IPv6 filters for app and proxy: public TCP80/443; narrow Docker DNS, own-health and IPv6 ND; raw private/metadata/loopback/other-port probes denied against reachable controls; SafeFetcher pinning unchanged | Retest intended host/DNS/routes, host-specific public control-plane denies, owner lifecycle and kernel support. Host/Docker daemon/DNS/owner/root proxy are trusted. AWS host/security-group egress is not verified; no host firewall claim |
| Network trust | App/proxy share the controlled namespace; only owner publishes frontend ports; localhost-only lab bindings; app has no capabilities or loopback-initiation exception. Caddy overwrites identity and app trusts exact127.0.0.1/32; root-only backend exception | Retest public ACME/CDN/intended host; privileged Docker access can bypass this trust boundary. No general HTTP3/UDP access. Recreate dependants with namespace owner |
| Resource limits | Phase4D inspects app4GiB/2CPU/PID128; owner96MiB/0.5CPU/PID32; Caddy256MiB/0.5CPU/PID128. Combined memory+swap equals memory. App/root owner read-only; capabilities restricted; readiness64KiB. Earlier4C reduced-limit OOM/throttle/PID evidence retained | No full-analysis load/capacity was measured. SQLite page ceiling and physical/WAL totals are not hard filesystem quotas. Caddy retains trusted root/writable filesystem and only bind capability; host quotas/monitoring remain required |
| Temporary data | Defaults idle1h/absolute24h/sweep60s retained; Phase4C observes a real shorter-retention container delete its workspace and return410; restart smoke and Linux lease/symlink protection pass | Default long windows were not wall-clock waited. Publish retention/deletion notice, verify operator backups/failure alerts and quotas. Cleanup is not secure erasure; developer evaluation caches persist separately |
| Hosting | Linux/amd64 Docker Desktop verified locally; same pinned CPU model/cache. Base/Caddy digests and Linux transitive constraints added; Python audit50 packages/0 known findings, image advisory reports retained | Resolve/triage remaining high/critical OS/proxy advisories, pin/hash release artifacts, validate intended host, startup/load, public ACME, disk/quota/recovery. No capacity or vulnerability-free claim |
| Editorial quality | Earlier mixed/provisional evidence preserved; no complete independent metric cutoff; further review intentionally deferred | Describe the demo as experimental editorial suggestions, with evidence and manual decisions. Do not claim independently validated accuracy or automatic insertion/merge/deletion. Future ranking changes need separate evidence; no new labels requested in Phase 4A/4B |
| Compatibility | Freeze Edge evidence and offline 40-article workflows retained. Separately authorised Urban Turf index/blog-map200 evidence and cached homepage-to14-candidate replay exist; Phase4C performs no new live fetches | Original transient HTTP400 remains unexplained. Article extraction quality/global Wix compatibility is not established by sitemap success. Cross-host redirects, gzip sitemap files and JS-only/ambiguous articles remain unsupported |
| Operations/privacy | Existing safe fetch diagnostic logging/expiry/lease cleanup retained; new bounded owner readiness/quarantine JSON events, rotated10MiB x3 logs/service; readiness failures503 and drift seals both families | Add operator alerting/retention/redaction policy (access logs may include query strings), host quotas and recovery rehearsal. Cleanup is not secure erasure; counters reset on app restart |

Relevant sources: `semantic_analyser/{config,workspaces,execution,fetch_policy,
fetch_transport,safe_fetch,collections,api}.py`, `Dockerfile`,
`deploy/aws/compose.production.yaml`, `infra/aws/main.tf`.

Fresh application-index follow-up (2 November 2026): the complete local image now
indexes successfully: 191 packages, 38 advisories (0 Critical/4 High/7 Medium/27 Low).
All 17 filesystem layers match the verified image. See `phase4e-app-fresh-scan.json`
and the security-review addendum. Fresh application indexing is no longer blocked;
remaining advisories and intended-host/release checks remain open. The proxy was
not rescanned by this narrowly scoped follow-up.

Phase4E planning is complete. Further work requires a separately approved scope:
remaining advisory dispositions, adequate builder space for release provenance/
release artifact retention, then authorised intended-host network/quotas/recovery/ACME tests. Phase4D's
local kernel enforcement is now measured; it does not establish AWS networking or
anonymous-public readiness. Retain FastAPI, SQLite, shared MiniLM/TF-IDF and the gate.
No deployment/push or further editorial evaluation is implied. No PostgreSQL, Redis,
frontend rewrite or paid service is needed. Current local reproduction uses
scripts/verify_phase4d_egress.py; historical Phase4C tools describe their old topology.
