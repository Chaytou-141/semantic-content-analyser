# Public GitHub release preparation

8–9 November 2026 (Australia/Sydney). Reviewed `feature/deployable-aws-app` at
`0a7f2d0`. This is a local preparation review, not publication approval, legal
clearance, an AWS audit or a certification of production security. Nothing was
committed, merged, pushed, made public or deployed. No production secrets, DNS,
services or AWS resources were accessed or changed.

## Working tree and proposed changes

Initial working tree: only `.vscode/settings.json` staged as a new file. It was
removed from the index with `git restore --staged`; the local file remains intact.
`.vscode/` is now ignored. No project requirement for this personal editor setting
was found. No other pre-existing working changes were overwritten.

Files changed/proposed:

| File | Purpose |
| --- | --- |
| `README.md` | Current features, live demo, maintainer-reported 2 GB Sydney Lightsail hosting, temporary workspaces, setup, limitations, licence scope and links |
| `LICENSE` | Standard MIT text; copyright 2026 Ali Chaytou, covering original project material only |
| `SECURITY.md` | Private GitHub reporting instructions with a safe fallback; no private contact details; no claim reporting is already enabled |
| `.gitignore` | Exclude `.vscode/` |
| `.github/workflows/ci.yml` | Install Chromium and its OS dependencies before running existing offline browser tests |
| `semantic_analyser/public_assets.py` | Accept Windows-native separators for intended font paths while retaining exact asset allowlisting and Starlette containment checks |
| `tests/test_public_assets.py` | Add encoded Windows-separator traversal regressions |
| `evaluations/phase3f/inputs/*.csv`, `evaluations/phase3f/results.json` | Anonymise reviewer identities and free-text reasons; regenerate derived report and input hashes without changing labels or metrics |
| `evaluations/phase3d/review-notes.json`, `evaluations/phase3f/error-analysis.json` | Generalise case-specific editorial prose, retaining IDs, categories, scores and evidence hashes |
| `evaluations/phase3g/coordinator-registry.json` | Refresh derived Phase 3F hash and packet ID; all 44 candidate mappings and rankings remain identical |
| `evaluations/phase3f/README.md`, `docs/phase3f-evaluation.md` | Explain current anonymised copies and historical provenance |
| `docs/phase4e-app-fresh-scan.json` | Replace copied advisory descriptions with original summaries; retain scanner identifiers, package/version, severity, fix and source fields |
| `docs/public-release-review.md` | This factual review, unresolved decisions and recommended release steps |

The live deployment description is supplied by the maintainer, not independently
verified here. The checked-in Compose default app memory ceiling remains 4 GB;
earlier EC2/8 GB plans are historical and are not the actual 2 GB live-host settings.
No production capacity, pricing or spending guarantee is implied.

## Secret and history audit

- Gitleaks **v8.30.1**, obtained from its official GitHub release; executable SHA256
  matched the checksum in the release's checksum file. This checks download integrity,
  not an independent signature/trust-chain attestation. Tool stays in ignored runtime.
- All **41 commits reachable from local refs** scanned using `--all --full-history`.
  Supplemental inspection enumerated **413 distinct reachable blobs**: 412 text blobs
  and one binary font. Commit messages/metadata were separately checked. This does
  not audit remote refs not present locally, unreachable objects or untracked secrets.
- Current tracked snapshot plus proposed LICENSE/SECURITY files: **223 files** scanned
  after excluding the unstaged editor file. The final pass includes this report
  as well: **224 files**.
- Both history and current-file Gitleaks reports flag **one generic-api-key candidate**:
  `docs/phase4b-verification.json:64` (introduced at `f93aed4`). Manual structural
  inspection identifies the value as a 64-hex source fingerprint under
  `source_sha256/semantic_analyser/api.py`, not a service credential. Finding retained;
  no ignore rule, suppression or report editing was used to conceal it.
- Supplemental provider-token/private-key/account-locator/credential-URL/assignment,
  email, local-path and phone-pattern checks found no confirmed live credential.
  AWS registry examples in `docs/aws-deployment.md` use the standard fictional
  account number. Credential assignments and authenticated URLs are synthetic test
  or controlled verifier inputs. No secret values are printed in this review.
- No reachable `.env`, runtime directory, database, private-key file, Terraform state
  or source ZIP was found. `.env.example` contains blank secret fields. The font's
  existing SIL Open Font License is retained. The proposed MIT licence does not
  relicense fonts, model weights, dependencies or third-party website material.

**No confirmed credential leak found is not proof of secret absence.** Scanners miss
unsupported formats and context-dependent secrets. Credentials used outside tracked
history, real deployment files and production layers were not accessed. If any actual
credential is later identified, rotate/revoke it before coordinated history cleanup;
merely deleting the current file does not remove prior commits.

## Personal information and content rights: decisions still needed

Publication dispositions from the follow-up review (no material was removed):

| Concern | Classification | Reason / next action |
| --- | --- | --- |
| Personal author email in Git history | **Requires my decision** | It identifies the maintainer across reachable commits. Approve publication as-is or separately authorise a backed-up, coordinated history rewrite. Future `noreply` settings do not remove it. |
| Human review contributions | **Requires my decision** | The 14 user-provided decisions and conversation-derived reasons may identify or quote a contributor. Confirm consent or approve a scoped anonymised replacement, including history if necessary. AI-assisted decisions must remain labelled as such. |
| Public website URLs and article titles | **Safe to publish** for factual URLs/titles alone; **requires my decision** for case-specific editorial notes or redistribution of any longer original text | The tracked evidence contains public identifiers and short title metadata, not an identified article-body corpus. Testing authorisation alone is not permission to republish source prose. Confirm the site-specific notes are acceptable before publication. |
| Copied security-advisory descriptions in `docs/phase4e-app-fresh-scan.json` | **Should be removed or anonymised** before publication | The verbatim upstream descriptions and contact-like/example path text are unnecessary for the public case study; retain CVE/package/version/severity/source links and write brief original summaries. Do not delete the historical record without explicit approval and a history plan. |
| Gitleaks 64-hex source fingerprint finding | **Safe to publish** | The flagged field is a SHA-256 of `semantic_analyser/api.py`, not an authentication secret. Keep the unmodified scanner finding and documented manual disposition; do not suppress it. |

These classifications are a publication recommendation, not legal clearance. The
personal email, contribution consent, editorial notes and advisory replacement
require owner decisions before a visibility change.

| Material | Finding and required review |
| --- | --- |
| Git author/committer metadata | One personal Gmail address is present across local history. Value withheld here. Owner must approve publishing that identity, or explicitly authorise a backed-up history rewrite before visibility changes. Changing future Git settings alone does not alter old commits. No rewrite performed |
| `evaluations/phase3f/inputs/phase3e_user_decisions_14.csv` and reconciled review input | Human judgements and conversation-derived reasons are present, labelled by reviewer role. Obtain approval to publish these contributions. No private reviewer email was identified; role labels do not establish redistribution consent |
| Freeze Edge references in seven tracked files | Primarily URLs, titles, IDs, hashes, metrics and provisional editorial notes. Testing permission is recorded; it does not establish public redistribution rights. No long body/passage JSON fields were found in tracked evaluation/docs JSON |
| `evaluations/phase3f/error-analysis.json` | Exact 12-word-window comparison against the saved 30-article corpus found one match, in `examples[11].target_title` (68 characters). This is a title match, not a discovered copied article body and not an automatic legal violation. Titles, quotations and evaluative notes still need owner review |
| Urban Turf references | Public URLs/diagnostic metadata in `docs/discovery-progress-fixes.md` and `docs/homepage-discovery-verification.json`; no raw article corpus identified in tracked files |
| Offline reviewer HTML | Tracked Phase 3E/3G HTML contains unfilled template markers, not embedded full review packets. Generated packets and real article bodies remain under ignored `runtime/`. Review-build scripts fail without the private cache rather than downloading content |
| `docs/phase4e-app-fresh-scan.json` | Contains copied public advisory descriptions, including a contact-like string and an example local-user path inside upstream advisory text. Not identified as the maintainer's secret or private address. Attribution/redistribution terms and necessity should be reviewed before publication |
| Synthetic demo and benchmarks | Explicit fictional/generated development content; preserve provenance. These do not provide independently validated real-world accuracy |

The wording comparison is a heuristic against one saved authorised sample, not a
comprehensive copyright/plagiarism assessment. Other short copied phrases, public
names, published business details or personal identifiers can escape these checks.
Uncertain material was **not deleted or silently rewritten**. If anything needs
removal, review all reachable branches/history as well as the current tree.

## Verification actually run

- Initial Windows suite: **437 passed, 14 skipped, 1 failed** in **55.93 s**.
  The failing intended-font test received Windows-native `fonts\\...` paths while
  the exact public allowlist used `/`. Both font files existed.
- Follow-up fix in `PublicAssets.get_response`: convert separators **only for the
  exact allowlist comparison**, and pass the original path to Starlette's file
  resolution, containment and symlink checks. Encoded traversal regression cases
  were added. Focused public-asset tests: **8 passed**. Complete Windows suite after
  the fix: **440 passed, 14 skipped, 0 failed** in **42.08 s**.
- Skips: 13 Linux/root-only firewall fixtures and one Windows symlink privilege case.
  No new container, network-policy, live-host or real-model verification ran.
- `node --check` passed for `web/app.js` and the Phase 3E/3G reviewer JavaScript.
- `git diff --check` passed. Personal editor file is unstaged and ignored. Apart
  from the stated asset-path fix and focused test, application/model/ranking, data,
  evaluation, benchmark and deployment source files are unchanged.
- CI's Chromium installation step is prepared but **GitHub CI has not been run** here.
  A public PR/branch run remains required. Terraform and container jobs were not rerun;
  no Docker builds, model benchmarks or AWS calls were made for this task.

Redacted audit reports, scanner provenance, heuristic results, test output and protected
file hashes remain in ignored `runtime/public-release/`. They are local evidence,
not files to upload with a bulk `git add`. Scanned history and current files produced
one retained source-hash false positive each; no claim of zero scanner findings.

Existing application/proxy image advisories remain documented and open in
`phase4e-security-review.md`. This source-publication audit does not patch, suppress
or rescan them, nor verify the live image or the newer PDF dependency inventory.
The 2 GB live-host capacity and intended-host security configuration were not checked.
Source publication and production security acceptance remain separate decisions.

The last recorded fresh application scan reported **0 Critical / 4 High**. Three
High findings are in the installed Debian SQLite library's FTS5 or changeset paths;
the current application uses ordinary parameterised tables and exposes neither
feature to visitors. The fourth is Debian zlib's gzip **write** path, whereas the
website fetcher uses bounded decompression. Debian's affected-range classification
for the installed zlib version remains disputed. These are open base-image findings,
not evidence of a currently reachable visitor exploit or proof of safety. The older
SQLite CLI `.recover` advisory does not apply to the app runtime without the CLI.
The last recorded proxy scan reported **0 Critical / 1 High**: unpatched transitive
Go JOSE v3 in Caddy. No visitor JWK endpoint is configured, but issuer/transitive
reachability is unresolved. Previously patched proxy findings are not silently
counted as current. Development-only audit tooling does not enter the reviewed
runtime images. No new image scan or live-host verification ran in this follow-up;
actual deployed-image versions and current-feed status still need confirmation.

## Merge and publication recommendation

Local `main` matches its cached `origin/main` and is an ancestor of the feature branch:
**0 main-only / 33 feature-only commits**. The feature branch matches its cached
upstream. No remote refresh was performed, so reassess immediately before any merge.
Graphically a fast-forward is possible, but the branch is **not yet an unconditional
merge/publication recommendation**: pending Linux CI and publication
privacy/rights decisions remain unresolved.

After the owner reviews these proposed files:

1. Review the narrow font-path fix and passing focused/full Windows tests. Run Linux
   CI, including the prepared browser installation step, before merging.
2. Approve publication of historical author contact, human judgements, source titles/
   metadata and advisory material, or explicitly authorise scoped changes/history
   cleanup. Keep private source caches, generated packets and visitor data excluded.
3. Commit only reviewed release files. Do not add `.vscode/`, runtime, databases,
   `.env`, credentials or evaluation caches. No commit is performed by this review.
4. With approval, refresh remote refs, rerun the redacted secret scan against final
   history, and open a PR from `feature/deployable-aws-app` to `main`. Obtain passing
   Linux CI and review its test, browser, container and Terraform outcomes. CI downloads
   and image builds use runner resources; review private-repository Actions allowances.
5. Merge only after the PR/release checks and rights/privacy decisions are satisfied.
   Preserve a reviewed backup before any separately approved history rewrite.
6. As a separate approved action, change GitHub visibility and configure private
   vulnerability reporting when available; verify the private reporting link and
   monitor it. Enable available secret/push-protection and dependency alerts, subject
   to the account's supported features. Add a release tag after reviewing its contents.
7. Repository publication does not deploy the app. Do not run deployment hooks, change
   live services, expose local ports or provision AWS resources as part of these steps.

GitHub private vulnerability reporting setup:
https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository

## Private-release follow-up — 9 November 2026

This section supersedes earlier test and advisory snapshots above. The follow-up
still made no commit, push, PR, merge, deployment, history rewrite or visibility
change. All proposed files remain unstaged pending review because the fresh scans
and historical publication issues below are unresolved.

**Historical identity.** The same personal author and committer address,
withheld from this publishable report, appears in **all 41 commits reachable from local refs**:

`0a7f2d0 84bb6ba 5a127fd 96f03a1 ca42828 ba6ed34 bc079df fa1f52b
1ef3578 1f8ec8c 0d10d70 c859346 8aeb44c 7079926 4f04563 5e3ec22
f93aed4 e08f8df 1a276af cad5b4a 5453900 036f173 771c4cb 34b613d
278049d 30088d1 f93c03b 6df9b1c 3ea9b59 bc72066 8e2c991 229cf4a
34e4a07 50f14f9 b9ea0e0 b3312c3 bfb67e2 63d4459 caff561 db4d3b9
62724fd`. No tags were found locally. Remote-only refs, forks and unreachable
objects were not inventoried. The address is personal information, not a credential.

**Proposed history procedure; not executed:** decide on a public GitHub noreply
identity and obtain the owner's explicit approval. Inventory/fetch all remote refs
only after approval; coordinate a write freeze and collaborators. Create and verify
an offline `git bundle --all` backup in a private location. In a separate clone,
use `git filter-repo --mailmap` with a scoped author/committer mapping, then inspect
all resulting author/committer/tagger fields, messages, trees and both secret and
content audits. Verify build, tests and signed-commit/tag implications. Review the
changed commit graph and PR/release references before any coordinated
`--force-with-lease` update. Tell collaborators to re-clone/rebase; old clones,
forks, caches and copied artifacts may continue to expose the previous history.
Changing Git config alone is insufficient. No history rewrite or backup was created.

**Current-tree publication edits.** Both Phase 3F CSVs now use anonymous screened
contributor/AI-assisted roles and neutral reasons. The derived Phase 3F report was
regenerated from those CSVs. A structural comparison confirmed unchanged provenance
counts (**14 screened-user, 45 AI-assisted**), decision counts, coverage (**44
candidate and 15 overlap cases**), all candidate/overlap metrics, ranking
disagreements, and zero eligible complete human P@3/P@5 cutoffs. The 12 Phase 3F
error-analysis examples retain IDs, categories, evidence hashes and scores while
their interpretation prose is generalised. Phase 3D review-note prose is also
generalised. The frozen Phase 3D manifest/rankings were deliberately left intact to
preserve hashes and reproducibility; its short assistant-proposed rationales and
public titles remain, and no copied article-body corpus was identified there.

Phase 3G's coordinator registry changed only its derived Phase 3F-results hash and
packet ID; its 44 item mappings, aliases and ranking lists are unchanged. Previously
generated Phase 3G HTML/CSV packets using the old ID will fail the new packet check.
No independent Phase 3G judgements were added or relabelled. The original comments,
advisory prose and personal address **remain in existing Git history**. Current-tree
anonymisation is therefore not enough for a public visibility change without an
explicit decision to publish that history or a separately approved rewrite.

The tracked historical app-scan JSON now uses original one-sentence advisory
summaries. Its 38 original advisory IDs, severities, package identifiers, fixes and
source URLs are retained, with a notice that the descriptions are publication edits.
No scanner finding was suppressed. The earlier raw prose remains in Git history.

**Verification.** Focused Phase 3F/3G tests passed **54/54** after refreshing the
derived packet fingerprint. The complete Windows suite passed **440, skipped 14,
failed 0** in **44.32 seconds**. Skips remain 13 Linux root-only fixtures and one
Windows symlink-privilege case. No calculation or application/ranking code changed
in this follow-up; the earlier narrow font allowlist fix remains the only app-code
change in the release draft. Current tracked/proposed file snapshot Gitleaks v8.30.1
again reported only the previously reviewed SHA-256 source-fingerprint false
positive at `docs/phase4b-verification.json:64`; the redacted report is ignored at
`runtime/public-release/gitleaks-publication.json`. `git diff --check` passed.

**Local production image builds and fresh Scout v1.27.0 scans:**

| Image tag | Build | Indexed packages | Fresh advisories | High/critical action |
| --- | --- | ---: | --- | --- |
| `semantic-release-review:app` | Passed; newly built Python layers | 219 | 32: 3 High, 1 Medium, 28 Low | Debian apt 3.0.3 (fixed 3.0.4); Debian zlib 1:1.3.dfsg+really1.3.1-1 (fixed in deb13u1) has two High findings |
| `semantic-release-review:egress` | Passed; cached policy/base layers | 138 | 33: 3 High, 1 Medium, 29 Low | Same apt and zlib findings; egress host protection does not make base-library findings disappear |
| `semantic-release-review:caddy` | Passed; cached pinned Caddy build | 183 | 8: 1 Critical, 2 High, 4 Medium, 1 Unspecified | Alpine zlib 1.3.2-r1 Critical (fixed 1.4-r0); Go `klauspost/compress` 1.20.1 High (fixed 1.20.2); Go JOSE v3 3.0.5 High (no scanner-listed fix) |

Raw SARIF reports remain under ignored `runtime/public-release/`.
The scans completed using current Scout data on the locally built images; they are
not proof that these exact images or dependency versions run on the live host. The
scanner also announced a newer CLI version; v1.27.0 completed without filters or
advisory suppressions. No image was pushed and no container service was deployed.

**Risk distinction:** `apt` is a base-image package not invoked by app endpoints,
but it is present and has an available Debian fix. The Python fetcher uses zlib
decompression on untrusted website responses; the new zlib advisory must be
assessed and the vendor fix adopted in a reviewed image update. The older
gzip-write advisory's exact app path remains unexposed, but the current scanner
now lists a Debian fixed package, so historical “no stable fix” guidance is stale.
Caddy's configured `encode zstd gzip` means the Go compression finding cannot be
dismissed as a development-only package without further reachability review.
Alpine zlib is present in the runtime proxy image and the Critical finding is a
release blocker until remediated or defensibly dispositioned. Go JOSE v3 remains
unfixed with previously noted uncertain transitive reachability. Development test
tools are outside the built runtime images. These are current scanner findings,
not an exploit demonstration or formal risk acceptance.

**Decision:** the code/docs/evaluation draft is testable, but the branch is **not
ready for a public visibility change or a clean release approval**. First decide
whether historical personal/reviewer/advisory material may be public or authorise
the coordinated rewrite. Then remediate/reassess the newly actionable image
findings, rebuild and rescan, and obtain passing Linux CI and intended-host checks.
A private review commit/PR can be proposed after those decisions; no files were
staged or committed in this follow-up.

## Local image remediation follow-up — 9 November 2026

This supersedes only the image-finding snapshot above. It does **not** resolve
historical privacy/rights decisions, prove the deployed host uses these images or
approve publication. Nothing was staged, committed, pushed, merged or deployed.

- Pinned a newer official Python 3.12-slim digest in both app and egress Dockerfiles.
  Its installed Debian `apt` is 3.0.4. Both images explicitly install the trixie
  security update `zlib1g 1:1.3.dfsg+really1.3.1-1+deb13u1`, which covers the
  website fetcher's untrusted-response decompression path. The package versions
  were checked inside disposable containers with networking disabled.
- Pinned a newer Alpine 3.23 digest and `zlib=1.4-r0` in the Caddy runtime image;
  checked the installed package in the rebuilt image. Updated the Caddy Go
  compression dependency from 1.20.1 to 1.20.2 and regenerated the reviewed
  `go.mod`/`go.sum` locks from the actual builder. Caddy stays at v2.11.7.
- `go mod why -m github.com/go-jose/go-jose/v3` traces v3 through
  `caddypki -> smallstep/certificates/authority -> go.step.sm/crypto/jose`.
  The production Caddyfile has no PKI/ACME-server/JWK HTTP handler and uses a public
  domain with automatic public ACME certificates. A dry-run adaptation with a
  placeholder domain yielded only the HTTP app. The production Caddyfile now has
  `admin off`; `caddy validate` passed, and a disposable network-isolated Caddy
  container started with the admin endpoint disabled. This removes the local admin
  request path but also means changes require a restart rather than `caddy reload`.
  The v3 library remains compiled in, so this is a **configuration-scoped
  reachability assessment**, not removal, patching or a scanner suppression.

Docker Scout v1.27.0 completed fresh, unfiltered SARIF scans of **all three
rebuilt local runtime images**:

| Runtime image | Before | After | Remaining High/Critical |
| --- | --- | --- | --- |
| App | 32 rules: 3 High, 1 Medium, 28 Low | 28 rules: 0 Critical, 0 High, 1 Medium, 27 Low | None reported |
| Egress | 33 rules: 3 High, 1 Medium, 29 Low | 29 rules: 0 Critical, 0 High, 1 Medium, 28 Low | None reported |
| Caddy | 8 rules: 1 Critical, 2 High, 4 Medium, 1 Unspecified | 6 rules: 0 Critical, 1 High, 4 Medium, 1 Unspecified | `CVE-2026-116587`, Go JOSE v3 3.0.5, no upstream v3 fix listed |

The Caddy zlib Critical and Go compression High findings, plus Debian zlib and apt
High findings, disappeared from the **new runtime scans** after version checks.
Other Medium/Low/Unspecified findings remain. Scan exit code 0 means completion,
not vulnerability-free status. Raw SARIF reports are ignored under
`runtime/public-release/scout-remediated-*.sarif.json`; the earlier reports remain
there for comparison. No scanner exceptions or severity filters were used.

The complete Windows suite passed **440 tests, 14 skips, 0 failures** in **41.19 s**
after the Dockerfile and Caddyfile changes. The skips are the same Linux-root
fixtures and Windows symlink privilege case. Caddy config adaptation/validation,
installed-package checks and a disposable admin-disabled startup passed. No new
model inference, public website fetch, Linux CI or intended-host networking test
was run. Existing local runtime data was not changed.

Vendor references checked for this follow-up:
[Debian zlib security update](https://security-tracker.debian.org/tracker/DSA-6613-1),
[Debian apt security update](https://security-tracker.debian.org/tracker/DSA-6607-1),
[Alpine zlib 1.4-r0](https://pkgs.alpinelinux.org/package/v3.23/main/x86_64/zlib),
[Go compression advisory](https://github.com/klauspost/compress/security/advisories/GHSA-fpmh-frq8-7rj8),
[Go JOSE advisory](https://github.com/go-jose/go-jose/security/advisories/GHSA-mgcc-cww5-fp2q),
[Caddy admin behavior](https://caddyserver.com/docs/caddyfile/options).

Remaining release gates: decide how to handle personal/review/advisory material in
Git history; review the unfixed v3 finding and future PKI/configuration changes;
run Linux CI and intended-host checks; verify the actual deployed image digests
before making any claim about the live service. No history rewrite or public
release is authorised by these local findings.

## Maintainer decision for private merge review — 9 November 2026

The maintainer states that the personal email in existing Git history is
intentionally public and instructs us **not** to rewrite history. The maintainer
also accepts the residual Go JOSE v3 finding for this configuration-scoped,
limited-demo review: the library remains in the Caddy binary, its upstream v3
branch has no listed fix, the production Caddyfile exposes no JWK endpoint and
disables the admin API. This acceptance must be revisited if the Caddy/PKI
configuration changes or new upstream guidance appears. It does not mean the
scanner finding is patched or suppressed.

The maintainer authorised a private pull request and conditional merge after all
required checks pass. This is **not** authorisation to deploy these images or
change repository visibility. Earlier uncertainty about historical reviewer and
advisory text should be reviewed again before a separate public-visibility action.
