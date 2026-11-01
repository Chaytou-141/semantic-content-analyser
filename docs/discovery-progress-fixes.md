# Discovery diagnostics and extraction progress

1 November 2026, Australia/Sydney. Baseline `4f04563`.
Local commit subject: **Clarify discovery failures and extraction progress**.
Resolve the final commit with `git log -1 --format=%H --grep="Clarify discovery failures and extraction progress"`.

## Reported Urban Turf failure: not confirmed

The user reported an initial success followed by “The requested public content is
unavailable or requires authentication” for https://www.urbanturfsolutions.com.au/.
Searches of existing local runtime/document log and JSON/text evidence found no
site-specific record of the failing outbound response. Website runs are in memory;
the old generic error did not identify the discovery stage or upstream HTTP status.
No live requests were made. Wix identification, authentication requirements, anti-bot
behaviour, and the exact failing endpoint remain unverified.

The old message was emitted for unsuccessful content HTTP responses other than 429.
It did not prove authentication. Auto discovery fetches the homepage, then probes
`/wp-json/wp/v2/posts?per_page=20&page=1&_fields=id,link,title,content.protected`
(or a homepage-advertised REST base). Only a genuine 404/410 permits sitemap fallback.
A 401/403/429/503 must stop; accessing the homepage in a browser says nothing conclusive
about that REST endpoint, robots response, or automated access restrictions.

Explicit XML discovery supports namespaced sitemap indexes and blog URL lists,
including a Wix-shaped `/blog-posts-sitemap.xml` fixture. This verifies generic XML
compatibility, not this site's live sitemap, HTML extraction or Wix JS rendering.
It does not add a Wix API, force fallback after access denial, or weaken scope checks.

Each new website run has its own session budget, but selection never resets its
remaining requests/active-fetch time. Replacing a run invalidates its old ID;
workspace revision checks still apply. Server-wide visitor/outbound budgets and
host pacing/backoff can affect a second attempt. Redirects consume the same budget;
www/non-www cross-host redirects remain blocked. Those errors have separate codes.
No observed log proves that any of these caused this incident.

## Safe diagnostic changes

- `fetch_policy.FetchError.http_status` supplies safe messages for 401, 403, 404,
  410, 429, 503 and other unsuccessful content HTTP statuses. Existing application
  error codes and response statuses remain unchanged (e.g. upstream 403 is API 502).
- `SafeFetcher.fetch` attaches a static resource category: request, robots or content.
  Robots denials/unavailability, network failures, timeout, scope and budget exhaustion
  retain their distinct codes. A robots-policy denial is not presented as content 403.
- `WebsiteService.step` adds a static discovery stage and random diagnostic reference
  on fatal FetchError. The warning log contains only reference, stage, resource, code,
  numeric upstream status when known, and request count. No upstream body, URL, query,
  DNS address, ownership cookie or run identifier is logged.
- `api.rejected_fetch` returns additive safe metadata. The UI shows the reference.
  Tests verify HTTP403 does not fall through to sitemap requests or leak upstream text.

Error interpretation:

| Situation | Existing code | Safe distinction |
|---|---|---|
| Content HTTP401/403 | inaccessible | Actual HTTP status, discovery stage; no bypass |
| Absent HTTP404/410 | inaccessible | Existing permitted fallback/warning, HTTP reason |
| Content HTTP429 | backoff | Remote pause, numeric 429; no automatic retry |
| Content HTTP503 | inaccessible | Temporary remote failure; existing host backoff preserved |
| Robots Disallow / robots401/403 | robots | Robots-policy denial; HTTP401/403 policy remains deny-all |
| Uncheckable robots, e.g.503 | robots_unavailable | Robots could not be checked; fail closed |
| Connection/TLS/DNS failure | network or unsafe_host | Secure reachability/public-address checks |
| Request timeout | timeout | Deadline exceeded, not authentication |
| Per-run limits | limit | Resource/run budget exhausted, not remote HTTP429 |
| Host pause or application admission | backoff/busy/capacity | Existing bounded service response, not guessed upstream status |

For a future authorised incident, retain the **already failing** browser API response's
`code`, `detail`, `source_http_status` if present, `fetch_resource`, `discovery_stage`,
`diagnostic_reference`, API status and Retry-After. Correlate the reference with the
server warning. Record discovery mode, exact entered URL, timestamp, run request count
and whether the first attempt used identical settings. Never share cookies or tokens.
Older responses without this evidence cannot retrospectively identify the endpoint.
No repeated live retries are requested by this report.

## Extraction and layout findings

The baseline already implemented an extraction-specific native `<progress>` using
backend processed/selected counts. In fresh Chromium at 1366x768 it rendered a thin
12px track with a 2.78% fill at 1/36. Complete absence in the user's browser was not
reproduced, so browser/cache-specific absence remains unexplained. It was not only a
discovery indicator. Separate sidebar/content overflow regions were confirmed.

The track now has explicit WebKit/Firefox paint styles, an 18px height and contrasting
fill directly below status. The unrelated indeterminate capacity meter is hidden during
extraction; accepted character totals still appear after assembly. No timer animates
article progress. Text and aria-valuetext distinguish processed, failed/excluded and
actually imported articles. Interrupted requests retain the last confirmed response;
cancelled runs retain only their own previous reported count, labelled “Preview discarded.
Last confirmed”, because cancellation intentionally clears backend previews.

The modal has one scrolling body spanning both columns. Source settings collapse after
discovery, remain keyboard-expandable, and reopen for a new discovery phase. Long article
previews use the same body scroll instead of independent text scroll areas. The status
area is sticky and the existing action bar remains outside the scrolling body. Selection,
partial-import acknowledgement, final replacement confirmation and atomic admission are
unchanged. No database writes or server restart were needed for verification.

## Reproduction and evidence

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q --tb=short tests/test_discovery_diagnostics.py tests/test_safe_fetch.py tests/test_safe_fetch_api.py tests/test_websites.py tests/test_website_compatibility.py tests/test_demo_operations.py tests/test_visitor_workspaces.py tests/test_ux_display.py tests/test_application.py
.\.venv\Scripts\python.exe -B scripts/verify_discovery_progress.py
node --check web/app.js
```

Results: **256 passed, 1 skipped in 31.06s**. The skip is the existing Windows symbolic-link
privilege test, not an ignored security failure. No full historical/model suite ran.
The new diagnostic file contributes 11 passing cases, including synthetic first-success/
second-403, explicit Wix-shaped maps, safe API/log fields and distinct failure categories.
Existing regression tests cover DNS rebinding, mixed/unsafe addresses, redirects, robots,
compressed resources, run limits, isolation, expiry, stale revisions and failed imports.

Offline Chromium passed at 1440x900, 1366x768, 1024x600 and 390x844. Snapshots came from
the actual WebsiteService with controlled DNS/transport: 110 found, 36 selected, 1 then 2
processed, then 36 processed/35 accepted/1 failed. Native bar screenshot pixels were decoded
in a browser canvas and verified to include real accent fill, with no fabricated minimum
fill. Cancellation, request failure, long selection/review scrolling and visible footer
actions passed. Browser exceptions, unexpected/write/public requests and model runs: zero.
Cancellation snapshot mirrors API preview clearing; errors use the real frontend task handler.
This is controlled renderer/backend-snapshot integration, not a live-site end-to-end test.

Private snapshots/screenshots/before measurements: `runtime/discovery-progress-fixes`.
Portable measurements: `docs/discovery-progress-verification.json`.
SHA-256 checks confirm all **1,835** protected files are unchanged, including saved SQLite,
development evidence and benchmarks. Read-only inspection confirms **32 articles /249,162
title/body characters** remain. Transient SQLite WAL/SHM and new evidence output are excluded
from the baseline; existing untracked `.vscode/` is not staged.

No ranking, model, extraction, security limit, deployment or infrastructure change.
Remaining limits: actual site cause unproven; Wix JS-only content may be unsupported;
only Chromium was executed (Firefox paint styles were not browser-tested); cancellation
remains cooperative between requests. No claim of production readiness.
