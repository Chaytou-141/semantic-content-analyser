# Phase 4C: local Linux Docker release rehearsal

1 November 2026 (Australia/Sydney). Actual baseline: `1f8ec8c`, retaining the verified
commits after the requested `7079926`, including the approved Link Opportunities UI.
Commit subject: **Verify local Linux Docker release rehearsal and parser compatibility**.
Resolve with `git log -1 --format=%H --grep="Verify local Linux Docker release rehearsal and parser compatibility"`.

## Outcome and boundaries

The existing release Dockerfile built and ran locally. The final image passed the
existing Phase 4B smoke, 309 targeted Linux tests, and nine extended runtime checks.
This closes several previously unverified local-runtime gaps. It does not establish
anonymous-public readiness, cloud capacity, public ACME TLS or a public-import-compatible
kernel egress policy. No AWS resources, push, deployment, public website imports, new
editorial judgements or model benchmarks were performed.

The current local development SQLite contained **32 articles /249,162 title/body
characters and zero stored reviews** at the preservation checkpoint. It was never
mounted into a container. Tests used uniquely owned disposable volumes/tmpfs and
synthetic fixtures. Sentinel review rows test separation/persistence mechanically;
they are not evaluation labels and were deleted with their volumes.

## Environment, build and downloads

Docker Desktop 4.97.0; Engine 29.9.2; Compose v5.6.1; Linux amd64 on WSL2 kernel
5.15.167.4. The daemon reported 12 CPUs and 8,142,376,960 memory bytes. No containers,
tagged images or named volumes existed at the initial inspection.

The unchanged Dockerfile downloaded Python 3.12-slim (actual Python **3.12.16**), the
pinned CPU PyTorch 2.14.1 and runtime requirements, and the pinned MiniLM revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. It loads weights during the image build;
production startup then loads the cached model with offline flags. No encode calls or
model-quality/performance experiments were run. The HF unauthenticated-download warning
was informational. Base digest:
`sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159`.

Both release builds succeeded. Docker writes build progress to stderr, which PowerShell
labels NativeCommandError in the captured log; the actual exit codes were zero and image
creation was verified. There was no dependency-resolution or image-build failure.
The corrected rebuild reused dependency/model layers rather than downloading/loading
them again. The final release image was **2,328,114,663 bytes** (layered disk image size,
not RAM), ID `sha256:3c01e321ae09424859cdc93c48369bc473b79bd28cde43cb28794d9223acbcdb`.
Caddy's existing `2.10.2-alpine` image was also downloaded. A separate test-only derivative
adds pytest/httpx; those tools were not added to the release requirements/image.

## Verified issue and minimal changes

The first Linux test selection had **301 passed, 2 failed**:

1. Python 3.12.16's HTMLParser silently ignored an unknown marked section that the
   older Windows parser rejected. `Document.unknown_decl` now explicitly rejects
   unknown status keywords, preserving the prior contract and retaining recognised
   CDATA/legacy conditional sections as inert. This is a compatibility/validation fix,
   not a claimed exploit or CVE. Six focused cases protect unknown and recognised forms.
2. An eight-minute-selection test mixed a mocked monotonic clock with the real timestamp
   factory captured by a dataclass at import. The test now anchors its session timestamp
   to the mocked origin. Application timeout/budget logic was not changed.

Only the verified parser contract required application code changes. No AI, ranking,
API, UI, collection, review persistence or production-security configuration was changed.
The Phase 4B verifier gained `--output-dir` so its old evidence is not overwritten.
New local-only Compose/test-image/runtime tooling provides reproduction and cleanup.

## Compose architecture and TLS

The rehearsal merges `deploy/aws/compose.production.yaml` with
`deploy/local/compose.rehearsal.yaml`. It retains production visitor mode, password gate,
preloaded cached model, one Uvicorn worker, exact proxy peer, read-only app root, dropped
capabilities and private storage. The override replaces public port bindings with
**127.0.0.1:8080 and 127.0.0.1:8443**, disables automatic restart for disposable tests,
and adds faster lab health probes. No app port is published.

Caddy uses `localhost:8443` and its **local CA**; no public DNS or ACME validation was
requested. Python trusted the extracted public root certificate and verified localhost
TLS/hostname. HTTP `/health` redirected to `https://localhost:8443/health`. Browser checks
used ignore_https_errors for the private lab CA only; independent Python TLS validation
was successful. No CA was installed into the host's trust store. This is not proof of
publicly trusted HTTPS.

Initially Caddy was on an internal-only network: both containers were healthy but Docker
Desktop left the requested published bindings inactive, and the host connection was
refused. A separate local ingress bridge now belongs only to Caddy. Caddy and app share
the internal demo network with the original exact `.3/32` proxy trust; app has no default
IPv4 route. This lab networking difference is explicit, not a production firewall change.

## Actual checks and measurements

| Area | Observed evidence |
|---|---|
| Existing Phase 4B verifier | Passed on the final image: source hashes, two cookie owners, disposable sentinel review separation, restart persistence, health and configured limits |
| Linux regression selection | **309 passed, zero failed/skipped in 16.92s**, including real loopback socket/TLS fixtures, Linux symlink/process-lock cleanup, queue/timeout/lease rollback, quotas, atomic admission and website workflows with fake encoders |
| Source/UI freshness | 22 application/UI files copied into the release image match the checkout hashes |
| Real startup | `/health` reported `model_loaded: true` with runtime HF offline flags; no semantic analysis/encode request was made |
| HTTP/auth | App/Caddy healthy; unauthenticated read 401, cross-owner revision mutation 409, unsupported URL scheme 400/422, missing route 404; signed Secure/HttpOnly/SameSite cookies |
| Ownership | Two HTTPS cookie clients had separate 21-article sample workspaces and isolated sentinel rows; browser sessions also started through the real HTTPS password/session flow |
| Container UI | Two Chromium widths, 1440x1000 and 390x844: current Link Opportunities five-candidate view and raw evidence; visible 18px extraction meter with actual fixture counts 1/36 then 2/36; stopped state after controlled failure |
| Request budget/proxy | A persistent HTTPS burst varying X-Forwarded-For, Forwarded and X-Demo-* reached 429 on attempt 220 after earlier admitted API calls. Retry-After was 2; another spoofed identity stayed 429 and health remained 200 |
| Expiration/cleanup | Separate network-none app with shortened idle=3s, sweep=0.2s: workspace directory count 1→0; existing cookie got 410. Default one-hour/24-hour retention was not wall-clock waited |
| App filesystem/UID | UID10001; attempted root write returned EROFS (errno30), /tmp write worked, CapEff=0, NoNewPrivs=1 |
| Memory/CPU/PIDs | Main app: 4,294,967,296-byte memory and mem+swap limits, CFS 200000/100000 (2 CPUs), PID128. This host uses cgroup **v1**; v2 was not executed |
| Resource observations | Startup checkpoint cgroup current=403,259,392, high-water=410,058,752 bytes. End Docker spot: app376.6MiB, proxy19.5MiB. These are not full-analysis peak/capacity measurements |
| CPU reduced-limit probe | 0.25-CPU quota: 20 throttled periods, 0.498 CPU seconds over 2.071 wall seconds. This is a tiny containment probe, not an AI benchmark |
| Memory reduced-limit probe | 32MiB container, 128MiB allocation attempt: exit137, OOMKilled=true. The production app's full 4GiB ceiling was not exhausted |
| PID reduced-limit probe | PID16 container permitted 15 children then fork errno11 (EAGAIN). Production PID128 was inspected, not exhausted |
| SQLite/storage | Linux tests exercise real SQLite page-limit full/507 rollback, soft physical totals and safe cleanup; no host disk was filled and no filesystem volume quota was established |

The UI checks serve real assets/authentication from the container through Caddy, but
inject original synthetic analysis/extraction snapshots in the browser. Semantic and
website API requests are blocked by the browser fixture guard. Real backend website
workflows run separately in the Linux tests with controlled DNS/transport and fake
encoders. This is not a live-site extraction-to-model end-to-end test.

Initial harness assumptions were corrected: this Docker host exposes cgroup v1 paths,
the invalid-scheme check needed If-Match to reach its intended guard, and an API-budget
test needed a persistent connection to avoid slow Windows IPv6 fallback spreading calls
over multiple rate windows. The first slow attempt was interrupted and its five owned
helpers/project were explicitly removed before the successful final run. No application
quota or security checks were relaxed to make the harness pass.

## Networking: what was and was not enforced

The app's internal bridge and route inspection showed **no IPv4 default route**; IPv6
routes were loopback-only. No external DNS, Internet IP or cloud-metadata probe was sent.
Consequently this does not prove a DNS-aware or public-host kernel allow/deny policy.
Caddy's separate ingress bridge has normal routing and is not asserted to block egress.

A controlled peer at the test network's `.4:18081` returned 200 to a raw request from the
app container. Therefore private peers and nonstandard ports are **not** blocked by a
general kernel firewall. The real SafeFetcher separately rejected a private destination
with `blocked_destination`, and the targeted Linux tests retain DNS pinning, mixed-address,
IPv4/IPv6, redirect, robots and decompression controls. A compromised process can bypass
that library. Production's normal bridge/AWS egress remains unverified/permissive; the
offline app network would break public imports and cannot simply be deployed unchanged.

## Reproduction and command explanations

From the project root, after ensuring the lab ports are free:

```powershell
# Build the actual release artifact: downloads base/packages/model on a cold cache.
docker build --progress=plain -t semantic-demo:phase4c-verified .
docker pull caddy:2.10.2-alpine

# Optional Linux test derivative: extra test tools, not the production image.
docker build --build-arg APP_IMAGE=semantic-demo:phase4c-verified -f deploy/local/Dockerfile.rehearsal -t semantic-demo:phase4c-tests-verified .

# Existing disposable HTTP/restart smoke, preserving historical Phase4B evidence.
.\.venv\Scripts\python.exe -B scripts/verify_phase4b_docker.py --image semantic-demo:phase4c-verified --output-dir runtime/phase4c-repeat/phase4b

# New state path: generates private lab-only credentials, merges/validates Compose,
# starts localhost app+proxy, runs runtime/browser checks, then removes its resources.
.\.venv\Scripts\python.exe -B scripts/verify_phase4c_runtime.py --start --image semantic-demo:phase4c-verified --state runtime/phase4c-repeat/rehearsal-state.json
```

The runtime verifier's `--prepare-only` path was separately validated without starting
containers. Its `--start` uses the same up command executed during this rehearsal.
Compose invokes this structure (substitute the generated private env/project):

```text
docker compose --env-file <lab.env> -p <unique-project> -f deploy/aws/compose.production.yaml -f deploy/local/compose.rehearsal.yaml config --quiet
docker compose <same flags> up -d --wait --wait-timeout 180
docker compose <same flags> down --volumes --remove-orphans
```

`config` validates without exposing credentials in console output. `up` starts the
services and waits for health; `down --volumes` removes only that uniquely named lab.
Do not omit the local override: the production template alone binds public host ports.
This override requires Compose supporting `!override` (tested v5.6.1).

The exact Linux test command and logs are preserved privately in the rehearsal evidence;
it used `--network none`, read-only root, 256MiB tmpfs, 2GiB/2CPU/PID128, and read-only
mounts of tests/Dockerfile/local templates, never runtime development data. Test results
were streamed to the host's new evidence folder. No full historical suite ran.

## Cleanup, learning and remaining blockers

Both Phase 4B projects and the extended lab removed their containers/volumes/networks.
All five created image tags were removed only after checking their recorded IDs. Final
Docker listings show no containers, images or volumes, and only bridge/host/none networks.
BuildKit's unused **2.521GB cache** remains; no global prune was used. Private evidence,
screenshots, package inventory and the extracted public CA certificate remain under
`runtime/phase4c`. Both disposable environment files were removed after verification;
credentials are not committed. Reproduction uses a fresh --start state path.

An **image** is the prepared filesystem/package/model artifact. A **container** runs
processes from it with isolation and writable state. **Compose services** describe app
and proxy and how to start them together. **Volumes** keep SQLite/CA state beyond a
container restart; these test volumes were disposable. **Networks** control connections
and published ports, but a bridge alone is not an egress firewall. **Resource limits**
are kernel ceilings: 2 CPUs is a quota, not dedicated cores, and 4GiB is a ceiling, not
a prediction of RAM demand or a safe visitor count.

Remaining release blockers: import-compatible tested egress including DNS/private/IPv6
rules; intended-host load/queue/storage capacity and disk quotas/monitoring; public
DNS/ACME/upstream proxy validation; image/dependency patch/advisory review and immutable
Linux build inputs; operational restart/cleanup/retention alerts and counter-reset abuse
assessment. Caddy still has its template root/writable filesystem and a 512MiB combined
memory+swap setting for 256MiB memory; these were observed, not silently hardened.
No independent recommendation-quality claim or anonymous-public readiness follows.

Recommended Phase 4D: bounded local egress/operational hardening and release-input audit,
then another targeted rehearsal. No cloud deployment or further editorial/model work is
implied. Source changes, failures and portable measurements are in
`docs/phase4c-verification.json` and the development journal.
