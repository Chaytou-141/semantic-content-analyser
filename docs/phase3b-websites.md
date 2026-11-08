# Phase 3B: website URL to an admitted analysis collection

Baseline `f93c03b`; report date 29 October 2026, Australia/Sydney.
Commit subject: `Add bounded website discovery and staged article import`.
Resolve the hash using `git log -1 --format=%H --grep="Add bounded website discovery and staged article import"`.

## What changed

The existing collection screen gains an opt-in **Import website** workflow. It discovers
WordPress posts or sitemap URLs, lets a visitor choose up to 40, fetches their public
HTML, previews extracted text and replaces the collection only after confirmation and
the existing real-tokenizer admission checks. CSV/sample workflows remain available.
Importing clears previous editorial decisions, with the same explicit warning as CSV.

Set `ENABLE_WEBSITE_FETCH=true` in the server environment before starting the existing
Uvicorn command. The feature remains disabled by default. There are no new packages,
database tables, ML formulas, external services or infrastructure changes.

## Sources and API

| Source | Important entry points |
| --- | --- |
| `semantic_analyser/websites.py` | `WebsiteRun`, `WebsiteService.start`, `step`, `read_wp`, `read_map`, `select`, `assemble` |
| `semantic_analyser/extraction.py` | `Document`, `site_url`, `extract`, `sitemap` |
| `semantic_analyser/api.py` | `website_run`, `/api/website/start`, `/step`, `/select`, `/cancel`, `/import` |
| `semantic_analyser/schemas.py` | WebsiteStart/Action/Selection/Import; extra fields forbidden |
| `semantic_analyser/workspaces.py` | One transient `website_run` field per existing owned workspace |
| `semantic_analyser/fetch_transport.py` | Bounded `X-WP-TotalPages` header whitelist addition |
| `semantic_analyser/safe_fetch.py` | Server-side response headers; internal upstream status for 404/410 fallback only |
| `semantic_analyser/robots_policy.py` | Bounded collection of up to 10 Sitemap directives; unchanged Allow/Disallow policy |
| `web/index.html`, `web/app.js`, `web/styles.css` | Existing UI extended with selection, progress, inert previews and confirmation |
| `tests/test_websites.py`, `tests/website_fixtures.py` | Deterministic new workflow/security/data-integrity fixtures |
| `scripts/verify_phase3b.py` | Final suite plus controlled local HTTP/browser/offline MiniLM integration |

`start` accepts `{url, method: auto|wordpress|sitemap}` and returns a random run token.
`step`, `cancel` and `import` take `{run_id}`; `select` also takes `ids`, and import may
take explicit `accept_partial: true` when extraction failures are shown in the preview.
All endpoints reuse the existing workspace request header, owner cookie, revision
checks, lock, executor and lease. Visitor requests require `If-Match`. Run tokens are
not ownership credentials: foreign tokens return 404. A changed collection invalidates
the run; expiry is checked again before the actual import commit.

Only one page is fetched per step, allowing bounded requests/progress rather than a
long background crawler. Cancellation takes effect between steps; active I/O still
obeys SafeFetcher deadlines. Refresh/restart does not resume the client workflow.
Discovery/preview make no SQLite writes. Import invokes `CollectionService.replace`
once, keeping character/tokenizer/passage checks and rollback unchanged. Headings are
preserved as text blocks in article bodies and listed in the preview, rather than
adding a new persisted schema. Existing passage offsets refer to this extracted text.

## Discovery and extraction policies

- Auto mode reads the entered homepage and its same-host WordPress API link, or tries
  `/wp-json/wp/v2/posts`. It uses 20 posts/page, at most 10 pages and bounded pagination
  metadata. Duplicate IDs/URLs and protected WordPress posts are excluded. A 404/410
  or a valid empty REST collection permits sitemap fallback; 401/403/429/5xx, invalid
  JSON or an HTML challenge do not trigger route-hopping around restrictions.
- XML sources include a supplied `.xml` URL, a homepage sitemap link, bounded robots
  Sitemap directives, `/sitemap.xml`, `/sitemap_index.xml`, `/wp-sitemap.xml`. Nested
  indexes use a visited set, depth <=3 and a queue cap. Namespaced URL sets/indexes
  are supported. Only same-host safe HTTP(S) references enter the queue.
- Discovery is capped at 12 fetched discovery documents and 200 unique candidates.
  Each sitemap retains at most its first 200 locations and parses <=20,000 elements,
  depth <=32. These caps mean a large sitemap/site may be only partially represented;
  this is not a complete-site audit. A sitemap can include non-blog pages.
- XML DTD/entity declarations are rejected by Expat callbacks before expansion,
  including UTF-16 declarations. No external entities or secondary URLs are resolved
  by the parser. HTTP-level gzip is bounded by SafeFetcher; `.xml.gz` files are not
  separately decompressed by discovery.
- HTML must be UTF-8, <=2 MiB, <=30,000 nodes, depth <=96. It is parsed inertly using
  HTMLParser. No browser/JS/images/styles/embedded resources are fetched or executed.
- The longest explicit article region is preferred, otherwise main/role=main or
  entry-content/post-content/article-content. Navigation, footer, sidebar, forms,
  scripts, related/share/cookie/template regions and hidden content are omitted.
  Ambiguous layouts without such a region are refused; title uses H1 then HTML title.
- Articles need >=200 characters/35 words and <=20,000 body characters. There is no
  silent truncation. Explicit paywall/password/free-access-false markers are refused.
  Authentication/robots/network failures stop the run. Short/unsupported article
  extraction can be shown as a failed item; importing the successful subset requires
  explicit consent. An empty result is never imported.
- Canonicals and internal references use the same hostname and safe URL normalization.
  Tracking parameters/fragments are removed; meaningful sorted query parameters remain.
  Duplicate canonical URLs/exact body hashes collapse. Source/canonical aliases map
  existing links to selected IDs, excluding self-links/unselected URLs.
- Short identical paragraph blocks (20–240 characters) occurring on >=80% of at least
  three extracted articles are removed as potential templates. Headings remain. This
  heuristic can remove a legitimate repeated paragraph and miss longer boilerplate;
  the full plaintext preview and human review are essential.

## Unchanged safety and capacity boundaries

All requests use Phase 3A SafeFetcher, including WordPress, robots, sitemap and selected
article pages. No alternate HTTP library or allow-private production flag is added.
DNS pinning, complete answer validation, address denies, verified TLS, HTTP-only default
ports, same-host redirects, robots matching, host pacing, request/time/byte limits and
safe errors remain in force. TLS downgrade and cross-host www redirects remain refused.

The **180-second/60-attempt run budget includes human selection and all fetches**;
per-page calls do not reset it. Fetch budgets remain 20 seconds, 2 MiB encoded/decoded,
and 20 MiB cumulative wire/decoded. Header cap remains 32 KiB. One host request at a
time with a minimum one-second pause is unchanged. API start has a five-second local
restart cooldown; this is not a public-abuse protection system.

The existing analysis executor is shared with fetch work. No new thread pool, unlimited
job queue or per-visitor model is introduced. Model construction occurs during final
admission/analysis, not discovery. Existing local mode remains a trusted shared demo;
public visitors require the existing visitor mode/HTTPS configuration.

The final admission limits remain 100 articles, 20,000 characters/body, 250,000 total
characters and 800 real-tokenizer passages. A 40-article selection can still be too
large. Errors preserve the current collection/reviews. Expiry during model admission
also prevents the write. No ML thresholds, TF-IDF formulas or semantic ranking changed.

## Verification and evidence

Measured results are in [phase3b-verification.json](phase3b-verification.json). Detailed
ignored logs, disposable databases and screenshots are under `runtime/phase3b/`.
The full suite runs once in `scripts/verify_phase3b.py`; focused checks can be rerun
with `--focused-only` after a focused failure without inventing/repeating suite results.
The recorded final suite and any follow-up checks are documented in the journal.
The suite passed **222 tests**, with **1 Windows symlink-permission skip**, in
**29.16 seconds**. After final parser review, the affected **34 tests passed in
5.37 seconds**; the dialog follow-up used a deterministic encoder and three pages
per visitor, without another MiniLM load. Both 36-article real browser workflows
passed. The real collection contained **238,690 characters / 270 passages** with
embedding shape **(270, 384)** and one shared model construction. Its both-method
search took **7.828 seconds**, including article encoding. **651 protected files**
were unchanged. These are local observations, not production capacity claims.

Fixtures exercise WordPress and non-WordPress 40-article service workflows, pagination
cycles, nested sitemap cycles/depth/breadth, unsafe references, UTF-16 DTDs, malformed
markup, protected content, duplicate canonicals, repeated templates, character limits,
selection limits, owner/revision/expiry/cancellation checks and atomic review rollback.
Phase 3A adversarial DNS/transport/robots tests remain part of the full suite.

The focused verifier uses real loopback HTTP and production SocketTransport with
mocked public DNS and a test-only connector to loopback. Production peer/admission
rules remain unchanged and are tested separately. Two independent Chromium contexts
each import 36 realistic-length articles using WordPress and sitemap workflows. The
prose is the authorised synthetic Phase 1B corpus, reused as input only; no historical
benchmark runner or output is invoked/overwritten. One shared offline MiniLM load is
used for both admissions and one realistic collection's embedding/TF-IDF/link/overlap
integration checks. Browser CSV rollback, valid import/download and mobile layout are
also checked. Zero polite delay is used only for controlled local fixture speed;
actual configured run/time/byte caps remain. No public website is fetched.

These are synthetic engineering checks, not extraction precision/recall, recommendation
accuracy or hosting capacity measurements. The browser/server/fixtures are stopped
after verification; the user's existing local server is not restarted or modified.

## Limitations and next stage

Supported: public standard WordPress REST APIs (including advertised subdirectory API
roots), static/server-rendered articles exposed through XML URL sets/indexes, same-host
HTTP(S), bounded pagination and explicit article/main layouts. General page crawling,
RSS discovery, arbitrary APIs, authenticated/private posts, paywalls, anti-bot bypass,
cross-host canonical/www routing, JS rendering, compressed sitemap files and non-UTF-8
HTML are unsupported. A 200-response teaser/login page cannot always be recognized.
Malformed HTML repair is conservative and this is not a general readability engine.

The current UI cannot resume after refresh or extend an expired fetch run. Human
selection time may exhaust the fixed three-minute budget. Site aliases have separate
pacing gates. There is no per-IP fairness/global long-term quota or independent egress
firewall. Python/Expat/TLS runtime patch levels and deployment-specific routing need
security review before public hosting. Local unit/browser checks do not prove public
readiness or protection against all malicious websites.

Next: review Phase 3B, evaluate extraction quality on a small authorised real-site sample,
measure representative 30–40 article completion under real delays/budgets, and assess
whether run UX/bounds need adjustment with evidence. Then implement the minimal public
hosting/egress/abuse controls and capacity validation. Do not weaken SSRF, collection
admission or visitor ownership to improve compatibility.

Primary protocol references: [WordPress pagination](https://developer.wordpress.org/rest-api/using-the-rest-api/pagination/),
[posts](https://developer.wordpress.org/rest-api/reference/posts/), [Sitemap protocol](https://www.sitemaps.org/protocol.html),
[Expat callbacks](https://docs.python.org/3.12/library/pyexpat.html). Phase 3A's security
design and remaining transport risks are retained in `docs/phase3a-safe-fetch.md`.
