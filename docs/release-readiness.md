# Public portfolio release checklist — Phase 3F update

Assessment only, 29 October 2026. No infrastructure/configuration was changed or deployed.
Tests and one-site evaluation establish specific behaviour, not production readiness.

Phase 3F: 14 user decisions after AI screening and 45 AI-assisted assessments reconcile
with the frozen packet. Only 8/44 candidates and 6/15 overlap pairs have user decisions;
all independent attestations are false. No complete human top-3/top-5 cutoff exists,
so neither method has human precision metrics. The combined file is not independently
validated ground truth. Evidence: `docs/phase3f-evaluation.md`,
`evaluations/phase3f/results.json` and `error-analysis.json`. No release blocker below
was closed merely by consolidating these reviews.

| Area | Existing evidence / boundary | Required before anonymous public release |
| --- | --- | --- |
| Visitor isolation | Signed cookie-owned SQLite, owner/revision checks, safe cleanup and two-session tests | Configure visitor mode explicitly and verify it on the intended runtime/HTTPS proxy; never expose shared local mode to unrelated visitors |
| Deployment template | `deploy/aws/compose.production.yaml` supplies production/password/secret but omits WORKSPACE_MODE and ENABLE_WEBSITE_FETCH | Template currently defaults to a shared local collection with website import disabled. Review/correct public-visitor configuration, private storage roots, stable secrets and secure cookies; do not deploy unchanged for this product |
| Abuse/fairness | One worker/two queued, finite workspaces, fetch counters and five-second same-workspace run cooldown; login attempt throttling | Bound anonymous session creation and repeated runs across identities/IPs; add assessed ingress rate/fairness policy and meaningful overload UX. Login throttling alone does not protect website/analysis capacity |
| Outbound requests | Production SafeFetcher checks all DNS answers, pins numeric peers, verifies TLS, bounds redirects/robots/time/bytes | Assess network-layer egress policy and operator-owned public IP deny ranges. Existing `infra/aws/main.tf` permits all IPv4 egress; application filtering is not a deployment firewall |
| Network trust | Loopback tests and pinned fetching; Docker exposes app internally through proxy | Assess host/VPC IPv4/IPv6 routing, resolver access and metadata paths. Restrict direct application access; review forwarded-header trust (`Dockerfile` currently trusts all forwarded peers) before relying on IP-based policy |
| Resource limits | 100 articles / 250k characters / 800 passages; website selection max 40; fetch 60 attempts / 180s active / 900s absolute / 20 MiB aggregate | Measure representative concurrent visitors and failure cases on target CPU/RAM/disk. Define container/OS limits, restart/supervision and alerts; cooperative threads cannot kill permanently stuck native calls |
| Temporary data | Visitor idle expiry 1h / absolute expiry 24h / sweep 60s; active leases defer removal; run access expires at 15min | Publish accurate retention/deletion notice and verify restart/cleanup failures, disk permissions/capacity and backups. Website expiry is not immediate secure erasure. Offline developer evaluation caches are separate and persist until deliberately removed |
| Hosting | CPU model pinned/cached in image; non-root user; one Uvicorn worker; HTTPS proxy configuration exists | Validate current Linux container, patch/scanning posture, model availability, startup/shutdown, health probes, storage, proxy timeouts and load on chosen host. No hosting/RAM guarantee follows from one local model run; no cloud resources were provisioned |
| Editorial quality | Real saved content, exact evidence, provisional metrics; 14 screened user decisions and 45 AI-assisted assessments, no complete human metric cutoff | Obtain independent complete top-five-union labels, clarify intent/scope criteria and separately adjudicate overlaps. Test any promotion/intent ranking hypothesis offline before changes; calibrate thresholds only with eligible evidence. No automatic insertion, merge or deletion decisions |
| Compatibility | Public WordPress REST on Freeze Edge measured; local XML/security fixtures | Obtain authorised functioning sitemap/index and independent non-WordPress examples; assess nested indexes, malformed/large inputs, canonical/redirect differences and actual article layouts without weakening SSRF |
| Operations/privacy | Existing sanitized fetch errors and bounded runtime storage | Define operator visibility for overload, timeouts and cleanup failures without logging secrets/full content unnecessarily; decide authorised evaluation-data retention/publication separately |

Relevant sources: `semantic_analyser/{config,workspaces,execution,fetch_policy,
fetch_transport,safe_fetch,collections,api}.py`, `Dockerfile`,
`deploy/aws/compose.production.yaml`, `infra/aws/main.tf`.

The simplest next step is a bounded readiness milestone: independent editorial review
plus the missing sitemap/platform validation, followed by reviewed visitor-mode deployment
configuration and measured abuse/egress/hosting controls. Retain FastAPI, SQLite, the
shared MiniLM and TF-IDF. This assessment supplies no reason to introduce PostgreSQL,
Redis, a frontend framework or additional paid services.
