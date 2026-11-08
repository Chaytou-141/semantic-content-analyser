# Phase 3C: authorised real-site validation and bounded selection time

29 October 2026, Australia/Sydney. Baseline `278049d`. Local commit subject:
`Validate real-site extraction and bound website selection time`.
Resolve its hash with `git log -1 --format=%H --grep="Validate real-site extraction and bound website selection time"`.

## Sample and actual access

The user supplied **https://freezeedge.com.au/** as the authorised sample. It is a
WordPress site with a public REST posts endpoint. No other domain was authorised or
tested. Its WordPress API and article pages were fetched through production SafeFetcher:
real DNS, complete address validation, pinned connections, verified TLS, robots and
default pacing/limits. No browser, alternate HTTP client, proxy or authentication bypass
was used for live access. No restrictions were encountered on the selected posts.

The site's robots policy allowed the tested paths and advertised
`https://freezeedge.com.au/sitemap_index.xml`. XML discovery was attempted on this
same WordPress site; it is not an independent non-WordPress platform sample.

| Actual operation | Observed result |
| --- | --- |
| Initial auto discovery | 110 WordPress posts; 8 requests; 19.609 seconds |
| Baseline 40-post selection, old 180s wall-clock policy | 100.109 seconds; 48 requests; 31 prepared, 9 excluded by the collection character cap |
| `/sitemap.xml` | 301 to advertised `/sitemap_index.xml`, then 404; no candidates |
| `/wp-sitemap.xml` | 301 to the same index, then 404; no candidates |
| `/post-sitemap.xml` | 404; no candidates |
| Corrected 30-post selection, new bounded timing | 30 prepared; 38 requests; no extraction failures; 232,919 characters |

The XML attempts respected robots and normal redirect/scope validation. There was no
route hopping around auth/robots/anti-bot denials. The unavailable sitemap is a real
site/access finding, not proof that the sitemap parser is broken. Successful real XML
URL-set/index discovery and a separate non-WordPress site remain **unverified**. Local
sitemap fixtures passing in tests do not replace this missing real-world evidence.

## Measurements and capacity

| Measurement | Baseline 40 | Corrected 30 |
| --- | ---: | ---: |
| Discovery seconds | 15.578 | 15.469 |
| Selected-page extraction seconds | 84.531 | 60.766 |
| Discovery + extraction seconds | 100.109 | 76.235 |
| Network attempts, including robots/discovery | 48 | 38 |
| Raw HTTP wire bytes | 1,756,409 | 1,330,619 |
| Decoded response bytes | 8,106,774 | 6,134,579 |
| Prepared article count | 31 | 30 |
| Prepared title + body characters | 242,029 | 232,919 |
| Cumulative fetch time measured by new policy | Not available on old policy | 75.739 seconds |
| Real-tokenizer passage count | Not measured | 275 |

The corrected run's overall script wall time was **87.641 seconds**, including importing
the local tokenizer dependencies and capacity check. The timed tokenizer construction/
preflight block was **0.266 seconds**; that figure excludes earlier dependency imports.
No MiniLM weights or embedding inference were loaded. The exact pinned cached tokenizer
was used with the existing `AnalysisEngine.preflight` through a tokenizer-only wrapper.
This checks the real passage windows, vocabulary and 256-token constraints without
repeating an unrelated embedding benchmark. No public-site text was imported into the
development database. These observations are preparation/admission checks, not a live
embedding/recommendation-quality evaluation.

The 40 corrected pages collectively contain **330,836 title/body characters** before
collection template removal: 40 cannot simply be admitted under the unchanged 250,000
limit. All 40 pages were structurally extractable; the baseline's 9 exclusions were
collection capacity failures, not inaccessible pages or broken parsers. Keeping the
current limit was justified by the actual workload and avoids claiming that every
40-post selection fits. Thirty selected posts fit the character and 800-passage limits
in this one observation. No hosting-throughput or general-site capacity claim follows.

Under the old wall-clock rule, the measured 40-post network workflow left only
**79.891 seconds** of its 180 seconds for human selection/review. An otherwise reasonable
pause could therefore invalidate a healthy collection. No artificial human delay was
inserted into the live runs; delayed selection is tested with a controlled clock.

## Extraction audit and demonstrated fixes

The saved 40 real HTML responses were compared offline with the baseline extractor
and the corrected extractor. Replaying saved responses made this comparison repeatable
without refetching all 40 pages. Baseline and live-run source SHA-256 values are saved
with the local observations; raw HTML/plaintext stays in ignored runtime storage.

- Corrected extraction returned nonempty, size-valid bodies for **40/40** saved pages.
- Extracted titles matched a source H1 on **40/40**; canonical URLs matched their public
  source URLs on **40/40**. These are structural consistency checks, not human relevance labels.
- **39/40** baseline outputs contained an exact category or author/date block identified
  from the source DOM. The corrected outputs contained **0** of those identified blocks.
  This does not mean all boilerplate has been removed.
- The 30 prepared articles map **37 existing links** to selected article IDs across
  **23 articles**. Other same-site product/unselected links are extracted but intentionally
  excluded from `existing_links`, which references selected IDs only.
- Spot review of five saved pages checked titles, section headings, opening/closing
  prose and the content-region boundaries. The body can still contain editorial
  promotional/contact paragraphs within entry-content. Those are retained rather than
  guessing that every contact reference is disposable. Extraction quality is therefore
  partially heuristic and requires human preview; no extraction precision/recall was measured.

Root cause: the existing noise matcher treated the WordPress state class
`has-post-comment` as if it identified a comment region. This could hide an entire
article and force a broader fallback containing category/author chrome. The fix ignores
`has-*` class-state flags for noise matching, and prefers an explicit nested
`entry-content`/`article-content` body while retaining the article's outer H1 as the title.
Actual comment/nav/footer/related regions and explicit paywall protections remain active.
Small original synthetic regressions reproduce this structure; site prose was not added
to the tracked test corpus.

The UI now identifies excluded articles by discovered title, and capacity exclusions
carry `kind=capacity` separately from `kind=extraction`. The subset confirmation refers
to the articles actually included in the preview. Missing sitemap responses produce a
bounded HTTP 404/410 warning rather than only an unexplained empty selection.

## Timing decision and security trade-offs

Website runs now have **two independent fixed limits**:

1. A **900-second absolute lifetime**, created once at run start, for discovery,
   selection, extraction and review. No request renews it.
2. **180 seconds of cumulative active SafeFetcher time**, including DNS/TLS, robots,
   redirects, pacing, policy matching, reads/decompression and failed calls. Each call
   is charged in `finally` while its session lock is held. Human gaps are not charged.

Every fetch also ends at the earliest of its existing 20-second limit, remaining
active budget, absolute expiry and executor deadline. The **60-attempt** and **20 MiB
wire/decoded** budgets remain cumulative and never reset per page/selection. All other
fetch, concurrency, byte, decompression, DNS/SSRF and robots policies remain unchanged.
The diagnostic fetch endpoint retains the original default wall-clock session policy;
only server-created website sessions opt into the active-time accounting mode.

Rejected alternatives: extending a rolling expiry on every click/fetch would permit
indefinite runs; resetting quotas between discovery and extraction grants extra work;
a larger single wall timeout still penalizes reading. The selected split gives time
to choose/review while retaining finite network work and a hard session end. Website
CPU/parser work still uses the existing bounded executor and parser limits; it is not
included in the cumulative network-time counter. Native/OS scheduling is not hard real-time.

The same owner/revision guards apply, and expiry/exhaustion during admission prevents
the write. Fixed lifetime does not promise immediate memory deletion: expired run
state is cleared on access or existing workspace cleanup. Restart drops transient runs.
There is still no per-IP long-term fairness/abuse quota; explicit new runs can consume
more capacity over time, subject to existing cooldowns/workspace/executor limits.

## Source and verification

| Source | Change |
| --- | --- |
| `fetch_policy.py` `FetchSession.deadline`, `Budget` | Default wall-clock policy preserved; opt-in active and absolute deadline bounds |
| `safe_fetch.py` `SafeFetcher.fetch` | Charge successful/failed active elapsed time under session lock |
| `websites.py` `WebsiteRun.expired`, `start`, `step` | Fixed 15-minute website lifetime, quota-preserving metadata, failure classification and sitemap reasons |
| `extraction.py` `hidden`, `extract` | WordPress state/body compatibility correction |
| `api.py` `website_run` | Unified expiry/exhaustion checks, including the existing final commit guard |
| `web/app.js`, `web/index.html` | Honest omitted-article labels, subset copy and timing notice |
| `tests/test_websites.py` | Selection/review gaps, fixed expiry, spent quotas, failed-work charging, atomic expiry rollback and compatibility regressions |
| `scripts/validate_phase3c.py` | Explicitly authorised, bounded real observation; no database import |
| `scripts/verify_phase3c.py` | One final full suite + isolated deterministic UI follow-up; no model load |

Package source paths are relative to `semantic_analyser/`. Portable evidence is
`docs/phase3c-verification.json`; local observations, hashes, raw pages and logs are in
ignored `runtime/phase3c`. The final suite and skipped-test reason are recorded there
after execution. Historical benchmarks, Phase 3B evidence and saved SQLite data are
preserved. No infrastructure changes, push, deployment or paid service were used.

Final full suite (run once): **230 passed, 1 skipped in 30.24 seconds**. The skipped
test requires Windows symlink privileges unavailable to this account. The existing
real local TLS and adversarial network tests ran. The isolated deterministic UI check
passed both fixture workflows, filtering/bulk selection, CSV rollback/import/export
and mobile layout. No page errors; both fixture servers stopped. These UI results are
synthetic and separate from the live observations above. JavaScript syntax/whitespace
checks passed and **752 protected files remained unchanged**, including saved databases,
historical benchmark artifacts and earlier verification records. MiniLM weights were
not loaded during these checks.

## Remaining release blockers / next phase

Obtain an authorised functioning sitemap/index and an independent non-WordPress sample;
test compatibility and extraction diversity before generalizing this result. Evaluate
more hostile/ambiguous real layouts and in-body boilerplate with human labels. The
single-site sample and automated source checks are not an independent quality benchmark.

Public release also needs assessed egress policy/operator-public-IP denies, abuse/fairness
controls, maintained runtime/security patch levels, sustained load/hosting tests and an
explicit retention policy. Existing cross-host/www/JS-only/non-UTF-8/gzip-file limitations
remain. Review Phase 3C before moving to that next bounded validation/readiness stage;
passing local tests does not establish production readiness.
