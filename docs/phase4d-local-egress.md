# Phase 4D — local egress and operational hardening

2 November 2026, Australia/Sydney. Baseline commit `1ef3578`. Local Linux Docker
verification only: no AWS, public exposure, live website imports, model evaluation,
ranking changes or GitHub push. This report and its journal entry ship in the commit
`Enforce container egress policy and record local security verification`.

## Problem and selected architecture

Phase 4C demonstrated that the app's private Docker bridge was not an outbound
firewall. SafeFetcher rejected private URLs, but another socket in that container
could still reach a controlled private peer. A public-import-compatible boundary
must independently constrain sockets without undoing SafeFetcher's DNS pinning.

Production Compose now has three roles sharing **one network namespace**:

* **egress** owns the namespace and installs IPv4/IPv6 kernel filter rules. Only
  this small, read-only, standard-library service has `NET_ADMIN`.
* **app** runs as UID10001, drops all capabilities, has no new privileges, and
  mounts the policy status read-only. Article/model/SQLite code is unchanged.
* **proxy** retains official Caddy, UID0, but drops capabilities except
  `NET_BIND_SERVICE` required by its file-capability-bearing binary. It has no
  network-admin/raw capability and no workspace mount. It forwards to
  `127.0.0.1:8000`; only root may initiate that loopback connection.

Published ports belong to the namespace owner. The application trusts proxy identity
only from `127.0.0.1/32`, and Caddy overwrites client-supplied identity/scheme headers.
The app cannot initiate connections to that trusted loopback port. Caddy and the
monitor are trusted components, not independent hostile tenants.

Alternatives considered: application-only checks retain the Phase4C gap; a bridge
with no default route prevents public imports; an HTTP proxy risks independently
resolving DNS and breaking numeric destination pinning; host-wide firewall edits
would affect unrelated workloads. The namespace owner preserves the existing raw
socket/TLS implementation and limits administration to this stack's namespace.
It adds a trusted privileged component and requires Linux netfilter support.

## Enforced policy and failure behaviour

`deploy/egress/policy.py`: `rules`, `namespace_prerequisites`, `monitor`, `sealed`.

| Traffic | Policy |
| --- | --- |
| New public website connections | TCP80/443 only; explicit IPv4 nonpublic/reserved ranges rejected; IPv6 limited to global-unicast `2000::/3` minus denied ranges |
| Private, loopback, link-local, metadata | Rejected for new web connections, including RFC1918, CGNAT, `169.254/16`, Azure `168.63.129.16`, IPv4-mapped/NAT64/transition ranges, IPv6 ULA/link-local/reserved |
| Own backend/health | Root-only `127.0.0.1:8000`; root-only own TLS health port443 (8443 only in the lab), IPv4/IPv6; no general loopback exception for the app |
| DNS | Only Docker's `127.0.0.11`, UDP/TCP, original destination port53. Conntrack matching survives Docker's ephemeral resolver-port DNAT; a narrow local INPUT exception delivers the query |
| IPv6 neighbour discovery | Only solicitation/advertisement with required hop limit255; needed to reach public IPv6 peers. No general private-IPv6 TCP exception |
| Replies/ingress | Established/related replies; new HTTP/TLS frontend connections; backend8000 not publicly admitted; forwarding defaults DROP |
| Other ports/protocols | Default DROP. No arbitrary UDP, DNS server, SSH or alternate web-port exception. HTTP/3 is not enabled by this network policy |
| Operator additions | `FETCH_DENY_CIDRS` also populates kernel denies; it cannot open extra destinations |

Before touching filter rules, the owner verifies its configured local private address
and Docker's embedded resolver. Both families first get DROP policies, then the
bounded exceptions. Missing capabilities/unsupported rule installation cannot become
healthy; Compose waits for owner health before starting the app.

The owner checks filter snapshots each cycle (normally one second plus command/probe
time). A mismatch or command failure seals **both** families and remains quarantined,
unhealthy, until operator intervention. It does not silently retry an altered policy.
Do not interpret the polling interval as a hard real-time guarantee.

`semantic_analyser/egress_status.py` accepts only a regular, root-owned, non-writable-
by-group/others record, <=4096bytes, bound to this network namespace and <=5 seconds
old. Symlinks, invalid/NaN/future timestamps and incompatible records fail closed.
Production website imports require this interlock. Each wire attempt charges existing
budgets and checks readiness **before DNS/transport**. Failures return a safe503
`egress_unavailable`, without infrastructure details.

The status file is an operational interlock, **not the firewall**. Pausing the owner
leaves kernel restrictions installed; after freshness expires, new SafeFetcher
attempts stop. Existing in-flight work retains its existing deadlines. The root
monitor's own health subprocess has a two-second overall timeout and a <=1024byte
body, with no redirect following. App container health reads the file instead of
granting the app a loopback exception.

## Measured verification

Docker Engine29.9.2, Compose5.6.1, Linux/amd64 on Docker Desktop/WSL2. Targeted tests:

* **264 passed in17.63s** as the app user: safe fetch/API, demo operations, visitor
  workspaces, websites/sitemap compatibility and collection admission.
* **24 passed in0.36s** as root in a separate disposable test container: firewall
  contracts and actual root-owned readiness fixtures, including API rejection before
  mocked DNS/transport. No skips. Test containers had network disabled, read-only root,
  2GiB/2CPU/PID128, bounded tmpfs and read-only test mounts.
* **Eight real container checks passed**: namespace/configuration; raw kernel
  allow/deny; unprivileged status protection; HTTPS discovery/extraction/session
  separation; app restart; paused-owner interlock; drift quarantine; missing
  `NET_ADMIN` readiness failure. Exact evidence is in `docs/phase4d-verification.json`.

The lab uses original synthetic pages and a throwaway locally trusted certificate.
Public-classified IPs are assigned **only to owned internal Docker networks**;
hard prerequisites verify target ownership/internal networks before probes. A separate
unrestricted control reaches the same listeners. This distinguishes firewall denial
from an absent service. The protected app and root proxy namespace reach public-
classified HTTP/HTTPS peers over IPv4 and IPv6, but cannot reach private v4/v6,
loopback v4/v6, the simulated `169.254.169.254`, SSH, alternate ports or alternate DNS.
Docker DNS and its UDP/TCP exceptions are exercised separately. No real cloud metadata
or third-party website is contacted.

Real SafeFetcher performs verified-TLS discovery of two sitemap candidates and extracts
two distinct articles, using four requests (robots, map, two pages). Progress comes from
backend counts. A second visitor gets404 for the first visitor's run. Both disposable
saved collections remain unchanged. The import/admission transaction is covered by
targeted admission/rollback tests; this runtime exercise stops at preview to avoid
loading the model/tokenizer. App restart preserves both visitor collections/cookies.

Pausing the owner for seven seconds produces503 before a new fetch, with metadata
still blocked. A deliberately injected operator firewall change is detected and
quarantined; public, private and metadata probes then all fail. An owner without
`NET_ADMIN` never reports readiness. These are actual kernel/socket tests, not only
mocked URL-validation assertions. Raw counter snapshots are retained privately.

Important implementation corrections found in the rehearsal: quote comma-containing
Compose tmpfs values; retain Caddy's required bind capability; allow its own IPv6 TLS
health check; deliver Docker resolver queries through INPUT as well as OUTPUT; permit
narrow IPv6 neighbour discovery. An early fixture had duplicate article text: the
existing deduplication correctly collapsed it; the fixture was corrected, not the
application's deduplication. Earlier unsuccessful lab attempts remain in private evidence.

No full historical suite, browser redesign test, new model inference or performance
benchmark ran. UI/application/ML source hashes and historical data are preserved.
Runtime model preloading was disabled for network tests; the existing Docker build
still prepares the same pinned MiniLM cache when that build layer is not cached.

## Operations, retention and storage review

Existing safeguards are retained rather than replaced: idle1h/absolute24h workspace
expiry, a60s cleanup sweep, persisted timestamps, one-process directory ownership,
active execution leases, revision checks, safe known-file deletion and symlink refusal
(`workspaces.py`). Tests cover expiry during work, timeout/slot retention, restart,
overload, failed import rollback, unsafe cleanup paths, free-disk and507 behaviour.

SQLite's16MiB page ceiling and128MiB aggregate admission checks are not a hard volume
quota; WAL/SHM and concurrent writes still require host filesystem quotas/monitoring.
The128MiB minimum-free check is admission protection, not reserved disk capacity.
Deletion is not secure erasure; backups, Docker layers and separately retained editorial
evidence have their own retention. No retention settings or development data were changed.

The owner adds sanitized JSON policy/readiness/quarantine events, with no article text,
URLs, cookies or secrets. Existing fetch logs use a diagnostic reference/stage/code and
request count; cleanup failures remain operator-visible exceptions. Docker logs rotate
at10MiB x3 per configured service. Uvicorn access logs may contain query strings;
restrict operator access and define retention/redaction before public release. Logs do
not replace alerts for disk fullness, cleanup failure,503s or container restarts.

| Service | Memory / combined memory+swap | CPU quota | PIDs |
| --- | --- | --- | --- |
| app | 4GiB /4GiB | 2 | 128 |
| egress | 96MiB /96MiB | 0.5 | 32 |
| Caddy | 256MiB /256MiB | 0.5 | 128 |

The owner has8MiB tmpfs; readiness has a separate64KiB tmpfs volume, read-only to
the app. Caddy's prior implicit extra swap allowance is removed. These limits were
inspected in actual containers. This phase does not establish model-analysis peak
memory, safe visitor capacity or host load tolerance. Existing counters remain
single-process/in-memory and reset on restart; the password gate remains required.

## Dependency/image audit and reproducibility

Supported tools actually executed: **pip-audit2.10.1** and **Docker Scout1.27.0**.
Audit metadata/package downloads are separate from website-import testing. Full JSON,
SARIF, logs, package inventories and checksums stay under `runtime/phase4d`; portable
counts/limitations are committed with this report.

Baseline Python inventory had51 packages including pip, with17 raw finding entries
across pip25.0.1/setuptools78.1.0, representing **nine distinct advisory IDs**, not17
independent vulnerabilities. Duplicate IDs/aliases and Windows/build-time applicability
must be retained when interpreting them. pip26.2.2/setuptools84.1.0 are used for the
trusted build; pip and ensurepip are removed from the runtime filesystem, and setuptools
84.1.0 remains for torch. **Final pip-audit:50 packages, zero known findings** in its
advisory snapshot. CPU torch's `+cpu` suffix is mapped to its upstream release for the
PyPI advisory lookup. This does not scan every OS library or prove safety.

Final merged-image Scout counts, rather than intermediate installer-vendor SBOM matches:

| Image | Vulnerable package identifiers | Advisory rules | Reported severities |
| --- | --- | --- | --- |
| app | 13 | 39 | 5high,7medium,27low |
| egress | 14 | 40 | 5high,7medium,28low |
| official Caddy2.11.7 | 10 | 48 | 10critical,27high,8medium,3unspecified |

The older Caddy2.10.2 snapshot reported227 rules/30 packages. Compose now pins the
tested official2.11.7 digest. It is **not vulnerability-free**. Reported remaining
app/owner high findings include zlib `CVE-2026-85091` and SQLite
`CVE-2026-119373`, `119374`, `119379`, `119586`, with no vendor fix listed in that
snapshot. Caddy reports Go stdlib/transitive and Alpine findings. These are scanner
package/advisory matches; exploit reachability has not been established or dismissed.
Do not add an unrelated top-level Python package to 'fix' a vendored component.

Advisory feeds changed during the exercise: an earlier app/owner scan reported one
additional high rule with identical dependencies. Freeze report hashes and rescan
before release; do not attribute feed reclassification to a code improvement.
The `--no-deps`/missing-hashes message is a reproducibility warning, not a vulnerability;
the input is a complete installed inventory, with versions but not artifact hashes.
The available newer Scout-version notice is not a scan failure. No runtime OS CVE
was silently accepted as safe, and no public-readiness claim follows from Python's
zero-findings result.

Python base and Caddy are digest-pinned; `requirements-linux.lock` constrains Linux
transitive versions to the Phase4C CPU inventory plus audited build-tool changes.
ML versions, model revision and Windows environment are unchanged. Audit/test tooling
stays out of the production image; test dependencies use the same Linux constraints.
Remaining reproducibility work: hashed artifacts, OS repository snapshots/transitive
apt inputs, signed/provenance-verified release artifacts and intended architecture.
Deleted installer bytes can remain in lower immutable image/build-cache layers;
runtime removal is not secure erasure or a guarantee of reduced image download size.

Measured logical image sizes: app2,339,678,440bytes, owner188,257,058bytes,
Caddy92,791,989bytes (see JSON for exact inspected values). Shared layers mean these
cannot simply be added to infer unique disk use. Historical Phase4C cache was retained;
there was no global image/cache/volume prune. Only this phase's recorded tags and
labelled disposable resources are eligible for cleanup. Unrelated resources created
while the rehearsal was running are left alone. Disk/cache listings and ownership
checks remain in private evidence; no byte-for-byte rebuild guarantee is claimed.

Cleanup completed: all phase-owned containers/networks/volumes, six recorded image
tags and disposable TLS keys/environment files were removed. Two unrelated images
remain untouched. Final global Docker snapshot:512.5MB images and5.212GB shared
BuildKit cache; host C: free7,707,480,064bytes at that observation. Other local work
ran concurrently, so global disk deltas are not attributed solely to this phase.
No unrelated image, cache or volume was deleted and no global prune ran.

Preservation checks compare1,968 baseline files: only ten intended existing code/config/
documentation files changed; the other1,958 match their original hashes. All saved
SQLite files, web assets, model/ranking sources, datasets and historical benchmark/
evaluation artifacts match. The current developer database remains10 articles,
29,303 title/body characters and4 reviews. This is the measured Phase4D baseline,
not a restoration of the historical Phase4C32-article collection.

## Reproduction and release requirements

From the project root, with Linux Docker running:

```powershell
docker build -t semantic-phase4d:app .
docker build -f deploy/egress/Dockerfile -t semantic-phase4d:egress .
docker build -f deploy/local/Dockerfile.rehearsal --build-arg APP_IMAGE=semantic-phase4d:app -t semantic-phase4d:test .
python scripts/verify_phase4d_egress.py --out runtime/phase4d/new-owned-run
```

Builds obtain trusted package/model artifacts if uncached. The verifier creates a
unique Compose project and throwaway local TLS key, publishes only127.0.0.1:8080/8443,
uses controlled internal targets, writes evidence, and removes only its resources.
It refuses to overwrite an evidence directory. Test commands are recorded privately;
run the named pytest files with network-none/read-only test mounts, and run the
root-owned readiness file as root in that disposable test image. No host database is
mounted. Phase4C's verifier/override describe its earlier topology; use the new Phase4D
profile with current production Compose, or checkout its historical commit to repeat4C.

For production Compose, `IMAGE`, `EGRESS_IMAGE`, `DOMAIN`, gate password and secret
must be supplied explicitly. The existing AWS helper has not been executed or
validated for deployment; do not treat these commands as AWS release approval.
The verified boundary is this Linux namespace/netfilter configuration, not Terraform's
currently broad host/security-group egress policy. Recreate app/proxy together with
the namespace owner when changing/recreating that owner; do not leave dependants
attached to an obsolete namespace.

Remaining blockers / next milestone (Phase4E):

1. Obtain patched base/proxy artifacts or complete documented advisory/reachability
   triage before public exposure; rerun targeted functional/security checks on them.
2. Plan intended-host testing: rootful Linux Docker/netfilter/capability support,
   actual DNS, IPv4/IPv6 routes, host-specific public control-plane IP deny ranges,
   namespace owner restart/recreation, quotas, alerts and fail-closed recovery.
3. Independently review AWS host/network egress and IMDS settings before any deployment;
   the host/Docker daemon, trusted DNS, namespace owner and root proxy remain trusted.
   This is not a sandbox against a compromised Docker host or privileged operator.
4. Validate public DNS/ACME/proxy trust, load/analysis resource needs, durable abuse
   controls and retention/privacy notices. No public certificate, live Internet import,
   intended-host firewall or default24h wall-clock retention test was performed here.

Outbound security limits **where a process can connect**. DNS turns a hostname into
addresses; SafeFetcher validates every answer and pins the socket to an approved one.
SSRF is tricking the server into making an unintended request, often to private or
metadata services. A Docker network namespace gives these services their own sockets,
routes and firewall tables; its bridge alone is not a firewall. The kernel policy and
SafeFetcher protect different layers and remain necessary together.
