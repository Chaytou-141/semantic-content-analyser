# Homepage-first automatic discovery

1 November 2026 (Australia/Sydney). Baseline `8aeb44c`.
Commit subject: **Discover blog sitemaps automatically from homepage URLs**.
Resolve with `git log -1 --format=%H --grep="Discover blog sitemaps automatically from homepage URLs"`.

## Problem and decision

Asking users to locate `/blog-posts-sitemap.xml` is a workaround, not an acceptable
default workflow. Previously auto mode guessed a WordPress endpoint even when robots
advertised a sitemap and the homepage advertised no REST API. Explicit sitemap mode
walked a mixed index in document order, including products/categories before blog posts.
Any fatal child-map error stopped discovery. The source of the earlier live HTTP400
is still unconfirmed; the authorised diagnostic did not reproduce it.

`WebsiteService.step` now uses published sitemap information in automatic mode when
no WordPress REST API was advertised. An advertised WordPress API remains preferred;
explicit WordPress mode and the no-metadata fallback retain their previous behaviour.
All requests still pass through SafeFetcher. This decision happens before requesting
an endpoint, not as a fallback after a denied request.

`WebsiteService.read_map` checks index child filenames for conservative blog/post/article
hints, excludes category/tag/product/event/author names, and validates site scope before
using hints. If some child maps look article-focused, automatic mode queues those branches
and displays an explicit incomplete-website warning. It does not claim the filename proves
article content. Multiple post maps are retained; generic/ambiguous map names still follow
the existing bounded traversal. Exact URLs are not hardcoded for Wix or Urban Turf.

The UI calls the default **Automatic (recommended)** and explains that entering a homepage
is enough. **All sitemap pages** retains explicit XML mode for users who want other page
types; its request value remains `sitemap`. No backend contract/schema was changed. Users
still review candidates, extraction and final replacement confirmation. The default path
can miss articles in ambiguously named branches; the warning and broader mode make this
trade-off explicit. JS-only article extraction and arbitrary website compatibility are
not established by sitemap discovery.

No retries, alternate requests after denial, cached robots policy changes or resource-limit
increases were added. HTTP400/401/403/429/503 on a selected map still stops the run. Robots
denials, public DNS/IP pinning, same-site restrictions, budgets, leases and atomic admission
remain unchanged. An unrelated branch skipped up front is not asserted to be accessible.

## Evidence

An earlier, separately authorised live diagnostic made 12 requests in 13.515s and stopped
at its intentionally stricter 12-request cap. The homepage, index and blog map returned
200; six child sitemaps were advertised and 14 blog post locations were parsed. Repeated
robots checks respected the actual `max-age=0,must-revalidate` header. The run did not prove
the source of the user's HTTP400 or verify real article extraction. Raw captured evidence
remains private under `runtime/urban-turf-diagnostic`; no further live requests were made.

Replaying those saved homepage/robots/index/blog responses with the new code reaches
`selecting` from the homepage in **6 mocked wire requests**, including all three robots
checks, and finds 14 candidates. Store/category maps and guessed WordPress are not requested.
This is cached-response compatibility evidence, not a new live performance benchmark.

Synthetic regressions cover mixed indexes, multiple post maps, generic filenames, explicit
all-page mode, advertised REST priority, untrusted off-site/private hints, robots denial
and fatal selected-map HTTP400/401/403/429/503. The existing diagnostic tests now explicitly
exercise advertised REST or explicit WordPress mode when testing REST denial, rather than
assuming that sitemap-advertising sites must receive a guessed WordPress request.

**275 targeted tests passed, 1 skipped, in 29.81s**. The skip is the existing Windows
symbolic-link privilege test. This run includes SafeFetcher, website/API, workspace,
operations, UI and data-integrity regressions; no full historical suite or real encoder ran.

Three offline Chromium cases (1440x900, 1024x600, 390x844) submit the actual homepage form,
route controlled API calls through the real WebsiteService and reach 14 selectable articles.
The warning, selected count and visible extraction action pass. No import or extraction
button is submitted. Network is intercepted, with zero unexpected requests or browser errors.

The previous browser fixture expected exactly 32 saved articles and initially failed its
read-only assertion because the live saved collection now has **14 articles /39,693 title/body
characters**. No restoration was attempted. The new harness reads the current saved data
read-only and establishes a fresh preservation baseline, without overwriting older evidence.
All 1,835 protected-file hashes match that baseline after verification, including SQLite,
benchmarks and evaluation evidence. The model, analysis rankings and saved articles are unchanged.

Reproduce:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q --tb=short tests/test_homepage_discovery.py tests/test_discovery_diagnostics.py tests/test_safe_fetch.py tests/test_safe_fetch_api.py tests/test_websites.py tests/test_website_compatibility.py tests/test_demo_operations.py tests/test_visitor_workspaces.py tests/test_ux_display.py tests/test_application.py
.\.venv\Scripts\python.exe -B scripts/verify_homepage_discovery.py
```

Private browser screenshots, hash baseline and replay results: `runtime/homepage-discovery`.
Portable summary: `docs/homepage-discovery-verification.json`. No deployment or GitHub push.
