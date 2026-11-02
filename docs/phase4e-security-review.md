# Phase 4E: image security and source exposure

## Fresh application index follow-up — 2 November 2026

The disk-blocked application scan is now complete. Docker Scout v1.27.0 indexed
191 packages from the local application image and reported 38 advisory rules across
13 vulnerable packages: **0 Critical, 4 High, 7 Medium, 27 Low**. Exit code 0 means
the scan completed, not that it found no vulnerabilities. No severity, fixed-only,
base-image or suppression filter was requested. The scanner's update-available
notice is informational; the recorded installed scanner completed successfully.

The existing Dockerfile was rebuilt using cached steps, with no new dependency or
model downloads/inference. All 17 filesystem layers match the previously verified
image. The new Docker manifest identity reflects image export/attestation metadata;
it is not evidence of a package update. The inspected local image is
`sha256:3334446d5b83c444bd1266f617bc844427fe26b16935fc920bd50e163d475257`.
Scout temporary storage was directed to `A:\semantic-content-analyser-scan-temp`
because moving Docker Desktop storage does not move Windows TEMP automatically.

| High advisory | Installed component | Fix status and remaining risk |
| --- | --- | --- |
| CVE-2026-119373, CVE-2026-119374 | SQLite source 3.46.1-7+deb13u2 | Scanner reports no fixed Debian version. Prior vendor evidence identifies upstream 3.54.0 fixes; app does not expose FTS5 SQL/database uploads. Retained findings, not a vulnerability-free claim |
| CVE-2026-119379 | SQLite source 3.46.1-7+deb13u2 | Scanner reports no fixed Debian version; upstream 3.54.0 fix previously documented. Session/changeset API is not used; library finding remains |
| CVE-2026-85091 | zlib source 1:1.3.dfsg+really1.3.1-1 (binary +b1) | Scanner reports no fixed Debian version. Previously documented upstream affected-range dispute remains unresolved; do not suppress or call fixed |

All 38 advisory records, package identifiers, descriptions, available scanner fix
versions and links are retained in `phase4e-app-fresh-scan.json`. Original SARIF,
fresh SBOM and logs remain under `runtime/phase4e/app-fresh-*`; the portable JSON
records their SHA256 hashes. The earlier cached-inventory report had 39 rules and
5 High. Only CVE-2026-119586 (SQLite CLI `.recover`) is absent from this fresh report.
The CLI was already absent and filesystem contents are unchanged: this difference
is a scanner/feed or inventory-matching difference, **not a remediation**. No manual
exception was applied. All historical reports are preserved.

This supersedes only the fresh-app-index blocker described later in this historical
report. Remaining gates include SQLite/zlib advisory disposition, the previously
recorded proxy findings (not rescanned here), release provenance, intended-host
network/metadata enforcement, quotas/monitoring, capacity, recovery and public TLS.
No application/security changes, extra test suite, deployment or push were needed.
The scan image and Scout cache were retained for reproducibility; no cleanup ran.

2 November 2026 (Australia/Sydney). Baseline `fa1f52b`. No deployment, push, paid
resources, website imports, model experiments or editorial evaluation. Historical
Phase4D evidence is unchanged. AWS recommendations are in `phase4e-aws-plan.md`.

## Decisions and actual findings

The official Python3.12-slim and Caddy2-alpine registry tags still resolve to the
Phase4D digests. A pull alone is not a patch. Python/ML dependencies remain unchanged;
all50 installed Python package versions match the audited4D inventory. No patched
stable Debian base covering these SQLite findings was confirmed, and neither mixing
Debian sid libraries nor replacing SQLite was justified for this application.

`phase4e-vulnerability-review.csv` records **53 image/package/CVE rows,42 distinct
baseline high/critical CVEs**, with installed source/module versions, fixes,
classification, mitigation limits and primary references. Debian source-package
versions differ from binary package suffixes: the inspected app has
`libsqlite3-0 3.46.1-7+deb13u2`, `zlib1g 1:1.3.dfsg+really1.3.1-1+b1`;
Python reports SQLite3.46.1 and zlib1.3.1.

| Finding | Evidence and disposition |
| --- | --- |
| SQLite CVE-2026-119373/119374 | Upstream fix3.54.0; Debian trixie remains marked vulnerable. Require malicious FTS5 SQL/index operations; our store has no FTS5 tables, arbitrary-SQL endpoint or database upload. Retained as unfixed library findings with unexposed current preconditions, not erased from the report |
| SQLite CVE-2026-119379 | Upstream fix3.54.0; session/changeset C API is not used. No confirmed stable backport; retain finding and reassess if database features change |
| SQLite CVE-2026-119586 | CLI `.recover` output piped into a shell-capable sqlite3 process. CLI absent in actual app image; no `.recover` execution. Shell-only advisory is not applicable to the installed library usage, while other library findings remain |
| zlib CVE-2026-85091 | Debian marks installed source vulnerable, but reported affected upstream range starts1.3.1.2, later than inspected1.3.1. Upstream issue1310 records the classification dispute. Retain pending vendor adjudication; app uses decompression, not nonblocking gzprintf writing. No acceptance or suppression claimed |
| curl24 baseline high/critical matches | Curl8.22.0-r0; Alpine fix8.23.0-r0. Vendor severities differ from scanner CVSS classifications (e.g.86411 is upstream Low, not Critical). Curl is unnecessary to this proxy and absent from the clean runtime, including inherited executable layers |
| C brotli CVE-2026-111497 | Baseline1.2.0-r0, fix1.2.1-r0; unnecessary C runtime package absent. This does not imply a similarly named Go module is the same package |
| Go stdlib and x/net | Caddy2.11.7 rebuilt using Go1.26.10 and x/net0.62.0. Binary build-info verifies versions. CSV uses package-specific fixes, not the scanner's ambiguous shared fixed-version field for stdlib/x/net |
| Go JOSE CVE-2026-116587 | v4 patched4.1.5 to 4.1.6. **v3 stays3.0.5 and upstream lists no v3 patch.** One High remains. No visitor JWK upload/parsing endpoint is configured, but issuer/transitive reachability and risk disposition remain outstanding; v4 patch cannot be assumed to fix incompatible v3 |

Primary sources: [Debian SQLite tracker](https://security-tracker.debian.org/tracker/CVE-2026-119373),
[Debian zlib tracker](https://security-tracker.debian.org/tracker/CVE-2026-85091),
[upstream zlib discussion](https://github.com/madler/zlib/issues/1310),
[curl vendor severity](https://curl.se/docs/CVE-2026-86411.html),
[Go release fixes](https://go.dev/doc/devel/release#go1.26.9),
[Go JOSE advisory](https://github.com/go-jose/go-jose/security/advisories/GHSA-mgcc-cww5-fp2q).
The CSV links additional package-specific records. No disputed finding is silently
treated as a vendor-approved false positive.

## Security rebuild and its limits

New `deploy/caddy/Dockerfile` builds the **same Caddy2.11.7 source release**, using
digest-pinned Go1.26.10, patches x/net to0.62.0 and Go JOSEv4 to4.1.6, verifies Go
modules and compares the resolved go.mod/go.sum against committed review locks.
`CustomVersion=v2.11.7-phase4e` distinguishes our build from an official binary.
Final runtime is digest-pinned Alpine3.23, with pinned CA, timezone, mailcap,
OpenSSL3.5.9 and TLS-health packages. No curl, C brotli, Go compiler or build cache
is copied. App architecture and ML versions/rankings are unchanged.

An intermediate build over the old official runtime ran the patched executable,
but Scout still found the old Go1.26.8 executable **in a lower layer**. SBOM paths,
layer ordinals/diffIDs and runtime build-info demonstrated both versions. This was
not fixed by ignoring the scanner: the runtime was rebuilt from clean Alpine so the
old executable bytes do not enter final layers. The old build remains private audit
evidence, not the release recommendation.

Verified Caddy executable SHA256:
`587738492764da66f0eb5e60a0cfc80c4e449391d01687bc467de601d807b3ad`.
The compiled artifact from the successful source build and the final fresh runtime
have identical hashes; final runtime checks use that artifact.

**Fresh runtime Scout:6 rules,0 Critical,1 High,4 Medium,1 Unspecified** versus the
frozen4D proxy snapshot48 rules/10 Critical/27 High. These are advisory snapshots,
not exploitability measurements or a claim that all security concerns are resolved.
Remaining: Go JOSEv3 CVEs116585/116586/116587; chi5.3.2 CVE114437 (fix5.4.0,
trusted-forwarded-IP middleware requires usage review); BusyBox CVE2025-60876;
x/crypto GO-2026-5932 (unsafe deprecated OpenPGP package, requires subpackage review).
None is suppressed. Go's main module reports `(devel)` because this is a custom
source build: the2.11.7 mapping is independently recorded, not assumed absent by a
scanner. Future official images with equivalent fixes are preferable to indefinite
ownership of a custom security rebuild.

Actual limitations: app-image fresh Scout extraction failed with insufficient Windows
disk space, and is **not** reported as passing. Fifty Python versions and unchanged
base/OS versions were verified. A current-advisory scan of the cached4D app SBOM
completed:39 rules/5 High. The new image has the same first11 dependency/base layers
and all50 Python versions. This reuses a verified unchanged component inventory; it
is not a fresh extraction/index of the new image. The owner was freshly scanned:40 rules, including
the same five High Debian findings. Python's existing zero-known-finding audit does
not resolve OS advisories. Full layer streaming inspection did complete separately.

The Go builder executed successfully. After its milestone-owned1.767GB compilation
cache was removed by exact cache ID, final runtime assembly reused the SHA-verified
compiled artifact instead of repeating compilation on a nearly full disk. The final
runtime stage and frozen dependency comparisons ran. After cleanup freed space, the
**complete final multistage Dockerfile build passed**
with trusted cached builder steps. Its eight runtime filesystem layers, binary SHA
and runtime configuration exactly match the container-tested artifact; a fresh scan
of this complete-source image also reports6 rules/1 High. A cache-free cold replay
was not performed; release provenance and adequate builder capacity remain required.
No global cache prune was used. Base/module/
direct APK versions are pinned; Go review locks are forced to LF on Windows.
Signed repositories/transitive artifacts still need
release provenance/retention, not an unsupported byte-for-byte reproducibility claim.

## Source and secret exposure

A synthetic context experiment confirmed that old `.dockerignore` rules excluded a
root `.env` but admitted **nested** `web/.env`, deployment release.env, Git metadata,
SQLite and key files. No real leaked credential was found. Fixes:

* Recursive context exclusions for env/Git/database/log/key files and editor settings,
  AWS/SSH/Docker credential directories and Terraform state/variables.
* App image copies six explicit public assets and no deployment directory.
* `PublicAssets` serves only the six intended filenames, even if a stray sensitive
  file exists inside web/. It retains Starlette's containment/symlink checks.

Post-fix synthetic context build excludes all injected secret files. Unit tests place
real synthetic private files in web/ and confirm404, including encoded traversal.
Production Caddy HTTPS was exercised with **76 raw HTTP requests**, authenticated and
anonymous. Backend paths, env, Git, SQLite, logs, proc/status paths, static traversal,
Swagger/ReDoc/OpenAPI/debug URLs returned400/401/403/404, not their contents. All six
intended public assets remained available. No runtime password/signing-key value or
traceback was returned. FastAPI debug is false and documentation routes are disabled.
Authenticated CSV/article exports and the saved-demo evaluation view remain intended
features; the audit does not misclassify them as debug routes or run new evaluation.

Streaming inspection covered **17 app filesystem layers/40,422 regular files** and
eight fresh-proxy layers/575 regular files, without extracting a multi-GB archive. Named secret canary,
sensitive first-party paths and nonempty deployment-secret image defaults were absent.
First-party credential-format checks and known credential-cache paths also found no
matches. A regression test proves an earlier-layer canary is still detected across a
read boundary even with a later whiteout. Tiny compressed layers and root credential
paths are also tested, and coverage must equal the inspected image RootFS layer count. These are explicit checks, not a universal
proof that an arbitrary unknown string could never be a credential. Metadata/history
and build inputs must still be reviewed for each release.

**Anyone who can pull the image can read Python backend source, frontend code, package
versions, model weights, synthetic datasets and build metadata**, including bytes in
old layers. Image access is not HTTP access. Use private ECR and least-privilege pull
permissions. The Docker administrator can additionally inspect runtime environment
secrets, volumes, logs and memory. Never mount Docker's socket into the application,
and never bake deployment passwords, AWS keys or client data into images. Deleting a
secret in a later layer would not remove it from earlier layers.

## Verification and reproduction

175 distinct targeted tests pass:172 Linux security/operations/static tests, plus a
final nine-test static/layer run containing six overlapping cases and three new layer
cases. Nine disposable-container checks pass on the final proxy: original kernel,
DNS, TLS, isolation, restart, stale-owner and quarantine checks plus HTTP exposure.
No full historical suite, model inference, live import or browser redesign was run.
All evidence and failed attempts remain under `runtime/phase4e`; portable metadata
and checksums: `docs/phase4e-verification.json`.

Cold-build commands (require sufficient builder disk; not an AWS deployment):

```powershell
docker build -t semantic-phase4e:app .
docker build -f deploy/egress/Dockerfile -t semantic-phase4e:egress .
docker build -f deploy/caddy/Dockerfile -t semantic-phase4e:caddy-final .
python scripts/verify_phase4d_egress.py --out runtime/phase4e/new-run --image semantic-phase4e:app --egress-image semantic-phase4e:egress --proxy-image semantic-phase4e:caddy-final --exposure-audit
python scripts/phase4e_image_audit.py semantic-phase4e:app --out runtime/phase4e/new-app-layers.json
```

Production Compose now requires explicit `PROXY_IMAGE` alongside app/owner image
references, so it cannot silently default to the old official proxy. Deployment must
use immutable reviewed digests; local test tags above are not an approved public
release. Historical4D verifier defaults intentionally reproduce the historical proxy;
pass the4E image explicitly for current security verification.

Launch remains blocked pending the remaining advisory dispositions, fresh full new-app
index/release provenance, intended-host egress and metadata tests, host quotas/monitoring,
public DNS/ACME, realistic capacity and recovery checks. No infrastructure phase or
deployment begins automatically.
