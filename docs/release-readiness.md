# Public portfolio release checklist — Phase 4A update

29 October 2026. Phase 4A makes bounded sitemap compatibility fixes and corrects the
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

| Area | Existing evidence / boundary | Required before anonymous public release |
| --- | --- | --- |
| Visitor isolation | Signed cookie-owned SQLite, owner/revision checks, safe cleanup and two-session tests | Configure visitor mode explicitly and verify it on the intended runtime/HTTPS proxy; never expose shared local mode to unrelated visitors |
| Deployment template | Phase 4A explicitly sets visitor mode, private `/app/runtime/visitors` and website import; production/password/secret gate retained; local Compose unchanged | Static YAML and Settings validation passed. Still verify the Linux image/HTTPS proxy, named-volume UID/permissions, startup/cleanup and two actual browser sessions before deployment; no container was run locally |
| Abuse/fairness | One worker/two queued, finite workspaces, fetch counters and five-second same-workspace run cooldown; login attempt throttling | Bound anonymous session creation and repeated runs across identities/IPs; add assessed ingress rate/fairness policy and meaningful overload UX. Login throttling alone does not protect website/analysis capacity |
| Outbound requests | Production SafeFetcher checks all DNS answers, pins numeric peers, verifies TLS, bounds redirects/robots/time/bytes | Assess network-layer egress policy and operator-owned public IP deny ranges. Existing `infra/aws/main.tf` permits all IPv4 egress; application filtering is not a deployment firewall |
| Network trust | Loopback tests and pinned fetching; Docker exposes app internally through proxy | Assess host/VPC IPv4/IPv6 routing, resolver access and metadata paths. Restrict direct application access; review forwarded-header trust (`Dockerfile` currently trusts all forwarded peers) before relying on IP-based policy |
| Resource limits | 100 articles / 250k characters / 800 passages; website selection max 40; fetch 60 attempts / 180s active / 900s absolute / 20 MiB aggregate | Measure representative concurrent visitors and failure cases on target CPU/RAM/disk. Define container/OS limits, restart/supervision and alerts; cooperative threads cannot kill permanently stuck native calls |
| Temporary data | Visitor idle expiry 1h / absolute expiry 24h / sweep 60s; active leases defer removal; run access expires at 15min | Publish accurate retention/deletion notice and verify restart/cleanup failures, disk permissions/capacity and backups. Website expiry is not immediate secure erasure. Offline developer evaluation caches are separate and persist until deliberately removed |
| Hosting | CPU model pinned/cached in image; non-root user; one Uvicorn worker; HTTPS proxy configuration exists | Validate current Linux container, patch/scanning posture, model availability, startup/shutdown, health probes, storage, proxy timeouts and load on chosen host. No hosting/RAM guarantee follows from one local model run; no cloud resources were provisioned |
| Editorial quality | Earlier mixed/provisional evidence preserved; no complete independent metric cutoff; further review intentionally deferred | Describe the demo as experimental editorial suggestions, with evidence and manual decisions. Do not claim independently validated accuracy or automatic insertion/merge/deletion. Future ranking changes need separate evidence; no new labels requested in Phase 4A/4B |
| Compatibility | Freeze Edge WordPress evidence retained; Phase 4A offline XML root/endpoint/namespace/limit tests and 40-article workflows | No new live validation: authorised successful real sitemap/index and non-WordPress examples remain unverified. Document XML mode for sites whose REST route returns an HTML catch-all. Cross-host redirects, gzip sitemap files, JS-only/ambiguous articles remain unsupported |
| Operations/privacy | Existing sanitized fetch errors and bounded runtime storage | Define operator visibility for overload, timeouts and cleanup failures without logging secrets/full content unnecessarily; decide authorised evaluation-data retention/publication separately |

Relevant sources: `semantic_analyser/{config,workspaces,execution,fetch_policy,
fetch_transport,safe_fetch,collections,api}.py`, `Dockerfile`,
`deploy/aws/compose.production.yaml`, `infra/aws/main.tf`.

The next milestone is Phase 4B: assess and implement bounded abuse controls, proxy/egress
trust and container resource/retention controls, then verify a disposable local Linux
container when Docker is available. Keep live-site requests explicitly authorised and
deployment/push out of scope unless separately requested. Further editorial work is
deferred. Retain FastAPI, SQLite, the
shared MiniLM and TF-IDF. This assessment supplies no reason to introduce PostgreSQL,
Redis, a frontend framework or additional paid services.
