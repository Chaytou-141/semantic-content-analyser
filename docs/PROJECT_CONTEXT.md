# Semantic Content Analyser: current context

Updated 2 November 2026 (Australia/Sydney). No deployment or push.

Latest Phase4E (baseline fa1f52b): Caddy2.11.7 security rebuild uses Go1.26.10,
x/net0.62.0, Go JOSEv4 4.1.6 and a clean pinned Alpine runtime. Old executable lower
layers removed rather than ignored. Final proxy scan:6 rules/0 Critical/1 High;
Go JOSEv3 remains unfixed. Debian SQLite findings/range-disputed zlib remain recorded.
Official tags still matched4D; app/ML package versions unchanged. Fresh app extraction
failed for disk space; current-feed scan of its unchanged component inventory passes
(39 rules/5 High). Complete final Caddy Dockerfile build passes with cache; runtime
files/config match the tested artifact. No cache-free replay; new-app index pending.
175 distinct targeted tests and9 container checks pass, including76 auth/anonymous
HTTP exposure probes. All17 app/eight proxy filesystem layers inspected; no named
secret/path/default-env findings. Static allowlist/explicit asset copies/recursive
context exclusions prevent nested-secret packaging/serving. Backend stays readable
to image holders: private ECR required. Current data10 articles/29,303 chars/4 reviews
unchanged; web/rankings/history unchanged. See docs/phase4e-security-review.md,
phase4e-vulnerability-review.csv, phase4e-verification.json and phase4e-aws-plan.md.
Recommendation only: Lightsail8GB x86 VM aroundUSD50/month; EC2t3.large Sydney around
USD95 with richer IAM/SSM. No AWS provisioning/alerts/DNS or editorial/model work.
Public launch still needs advisory disposition, release provenance/new-app index, intended-
host egress/metadata, guest quotas/monitoring, capacity, ACME and recovery acceptance.
Stop after4E; no automatic infrastructure phase. Production requires explicit app,
owner and PROXY_IMAGE references. Current verifier needs --proxy-image for4E builds;
its historical default repeats the old4D proxy.

- Stack: FastAPI + vanilla JS/CSS; SQLite; one shared CPU MiniLM
  `all-MiniLM-L6-v2` (384 dimensions, pinned revision), TF-IDF baseline.
- Local mode retains the persistent demo. Visitor mode uses signed owner cookies,
  temporary per-visitor SQLite, revision checks, expiration and cleanup leases.
  Public visitors must not share local mode.
- One active executor task + two queued by default. Cooperative 60-second response
  timeout retains slots/leases until running work stops. No hard native-code sandbox.
- CollectionService atomically admits all import formats before replacing data/reviews.
  Limits unchanged: 100 articles, 20,000 characters/body, 250,000 collection characters,
  800 real-tokenizer passages. Passage offsets/ranking formulas remain unchanged.
- Phase 1B baseline/benchmarks preserved; Phase 2A atomic admission `3ea9b59`;
  Phase 2B visitor isolation `6df9b1c`; Phase 3A safe fetching `f93c03b`.
- Phase 3B adds staged website runs: WordPress REST pagination or XML sitemap indexes,
  candidate selection (max 40), inert HTML extraction/preview, explicit atomic import.
  Current implementation commit subject: `Add bounded website discovery and staged article import`.
- UI follow-up: website/CSV entry points, three-stage import workspace, searchable
  candidates, bounded bulk selection and persistent confirmation controls.
- Website-first UX: root/#home shows the URL form; it starts existing discovery directly.
  Import leads to article analysis (search/links/overlap). Management stays under Your
  articles, evaluation/CSV utilities under More; settings/topic overview are collapsed.
- Enable website UI/API explicitly with `ENABLE_WEBSITE_FETCH=true` before startup.
  Every network request uses SafeFetcher: full public DNS validation, numeric-IP pinning,
  verified TLS, robots, same-host redirects, byte/decompression/deadline limits.
- Website run: one per workspace, fixed 15-minute absolute lifetime plus 180 seconds
  cumulative fetch time (includes robots/DNS/pacing/failures), 60 attempts,
  20 MiB wire/decoded; each fetch <=20 seconds, <=2 MiB encoded/decoded, host pause >=1s.
  Discovery <=12 documents, <=10 REST pages, <=200 candidates, sitemap nesting <=3.
  No quota reset per page or automatic retries. Cancel takes effect between steps.
- Extraction requires UTF-8 server-rendered article/main markup; ignores navigation,
  scripts, forms and template elements. Canonical URLs stay in scope; selected internal
  links map to article IDs. Headings remain in body text/preview; no SQLite schema change.
- Phase 3C fixes WordPress has-post-comment state flags hiding whole articles and
  prefers nested entry-content/article-content bodies while retaining the outer H1.
  Capacity exclusions are distinguished from extraction failures; missing sitemaps show HTTP reasons.
- Untrusted markup is never rendered or executed. Explicit restrictions fail closed;
  no authentication, paywall bypass, general link crawler or browser rendering.
- Evidence: `docs/phase3b-verification.json`, design/limits `docs/phase3b-websites.md`,
  factual history `docs/development-journal.md`. `scripts/verify_phase3b.py` runs the final
  suite and local browser/offline MiniLM checks; `--focused-only` avoids repeating a
  valid full suite after a focused-verifier issue. Do not rerun historical benchmarks.
- Known gaps: www/cross-host redirects, RSS, compressed sitemap files, nonstandard REST
  authentication/query routing, JS-only/ambiguous layouts, resumable runs. Extraction is
  heuristic and needs human review; synthetic checks are not recommendation accuracy.
- Real evidence: authorised freezeedge.com.au (WordPress). 30 articles prepared in
  38 requests / 75.739s active fetching; 232,919 characters / 275 real-tokenizer passages.
  No model weights loaded. Advertised/native/post XML sitemap endpoints returned 404;
  no successful real sitemap/index or independent non-WordPress site is validated.
  See docs/phase3c-real-websites.md and docs/phase3c-verification.json; raw pages stay ignored.
- Phase 3D: same saved 30 real articles, no refetch; one offline MiniLM construction,
  275x384 embeddings, 140 exact evidence checks. Seven frozen tasks/210 assistant-only
  labels: related mean P@3/P@5 83.3%/75%, links 55.6%/40% for both methods. No independent
  labels; these are provisional, single-site development diagnostics, not accuracy.
- Review set/worksheets: evaluations/phase3d; private human packet and full text:
  runtime/phase3d/editorial-review.html. Details: docs/phase3d-real-content-evaluation.md.
- Phase 3E manual packet: runtime/phase3e/independent-review.html (open directly in browser).
  44 candidates +15 overlap pairs; human choices/CSV remain separate from optional AI notes.
  Guide: evaluations/phase3e/README.md. Export completed CSV, then scripts/score_phase3e.py
  calculates human-only precision from saved rankings; Unsure/unreviewed stay unresolved.
  No model/refetch/application changes. Actual independently attested human reviews: 0.
- Phase 3F (`5453900` baseline): supplied CSVs reconcile 14 screened user decisions
  (8/44 candidates, 6/15 overlap pairs) +45 AI-assisted assessments. All attestations
  are false; no complete user-only P@3/P@5 cutoff, no independent accuracy claim.
  Offline evaluator: scripts/phase3f_evaluation.py; portable inputs/results/error
  examples: evaluations/phase3f; report docs/phase3f-evaluation.md. No ranking changes.
- Phase 3G (`cad5b4a` baseline): runtime/phase3g/blind-review.html has 44 new unselected
  task/destination judgements (23 distinct destinations) across seven tasks; excludes
  the 15 overlap pairs. No method/rank/score/old judgement data in reviewer HTML.
  Coordinator mapping: evaluations/phase3g; build/score via scripts.build_phase3g and
  scripts.phase3g_review. Requires new human/exposure declarations; old CSVs incompatible.
  Complete eligible cutoffs only, paired complete-case comparisons; no formal blinded
  independence certification or new human accuracy results. Guide: evaluations/phase3g/README.md.
- Phase 4A (`1a276af` baseline): explicit extensionless/query sitemap endpoints preserved;
  XML mode at a bare root uses advertised maps/defaults without REST probing. Namespace-
  qualified loc paths prevent image/foreign extensions becoming articles; empty loc/href
  entries are ignored; queue/depth/200-location truncation warns. Fetch limits unchanged.
  Production Compose explicitly selects visitor mode/private root/website import while
  retaining password/secret gate; local demo defaults unchanged. No Docker/live fetch.
  Evidence and operational gaps: docs/phase4a-compatibility-readiness.md and verification.
- Human evaluation is intentionally deferred. Do not generate more packets or ask for
  labels during deployment-readiness work; earlier provenance/quality limitations remain.
- Phase 4B (`e08f8df` baseline): opt-in bounded DemoLimits, enabled in production Compose.
  Rolling API/client/global/session/wire-attempt budgets, concurrency and finite state;
  exact proxy-peer identity/scheme headers with Uvicorn proxy rewriting disabled.
  Optional exact fetch hosts retain DNS/SSRF checks; new runs do not reset outbound quotas.
  SQLite main-file page cap and soft file/free-space admission checks; reads/export/delete
  remain available. Docker app read-only/4GiB/2CPU/PID128 configured, not kernel-verified.
  Guide: docs/phase4b-demo-operations.md. New tests use fake encoders/local fixtures only.
- Release blockers: docs/release-readiness.md. Docker CLI unavailable; verifier explicitly
  skipped. Actual Linux/HTTPS/proxy/UID/quota/egress enforcement needs verification;
  counters reset on restart, storage totals are soft and native cancellation cooperative.
- UX refinement (`f93aed4` baseline): sample/website entry, visible Analysis/Articles/Import,
  persistent import-success actions, expandable evidence and grouped capacity exclusions.
  Limits unchanged; frontend/API/ranking isolation preserved. Source-origin citation
  markers are removed from labelled previews only; raw full text/offsets remain.
  Saved 32-article /249,162-character Freeze Edge collection untouched. Browser QA uses
  disposable visitor apps, fake encoder and controlled network; no real inference/fetch.
  Learning/evidence: docs/ux-refinement-learning-guide.md and docs/ux-refinement-verification.json.
- Homepage follow-up (`5e3ec22` baseline): imported-collection continuation has its own
  section; sample action says View sample options. Three accessible tool navigation
  cards use separate headings/descriptions with explicit gaps. About disclosure has a
  contained SVG/label and responsive gutters; no clipping reproduced in fresh Chromium
  before changes, so this is layout hardening rather than a proved fixed-position fix.
  Six static/mocked browser cases (sample/imported x1440/390/320), enlarged text and
  restoration cancellation pass with zero writes/inference. See docs/homepage-fixes-verification.json.
- Next: Phase 4C disposable local Linux release rehearsal and verified operational
  controls. Real XML/non-WordPress sites remain unvalidated;
  future live fetches require explicit authorisation. No deployment or push authorised.
  Not production-certified; no PostgreSQL, React, Redis or cloud changes are needed now.
- Discovery/progress follow-up (`4f04563` baseline): unsuccessful HTTP responses now
  retain safe source status/resource/stage/reference diagnostics; auth/robots/backoff
  and limits remain distinct, with no bypass fallback. Urban Turf's reported failure
  has no saved site-specific response evidence and was not live-tested. Wix-shaped
  standard sitemap indexes pass offline; real Wix extraction remains unvalidated.
  Extraction uses a painted 18px actual-count bar, last-confirmed stopped/cancelled
  counts, one modal body scroll and fixed actions. Four offline viewport cases pass;
  256 targeted tests pass, one Windows symlink privilege skip. Saved32 collection and
  historical evidence unchanged. See docs/discovery-progress-fixes.md.
- Homepage discovery follow-up (`8aeb44c` baseline): Auto prefers advertised maps when
  no REST API is advertised and focuses mixed indexes on conservative post/article
  filename hints, with an incomplete-website warning. All sitemap pages preserves
  explicit full XML mode; denials still fail closed without retries or changed limits.
  One separately authorised Urban Turf diagnostic found a public index/blog map, not
  the reported HTTP400. Cached replay now finds 14 posts from its homepage in six mock
  requests. No new live requests or extraction-quality claim. Current saved collection
  is 14 articles /39,693 characters and remains unchanged. 275 targeted tests pass,
  one Windows privilege skip; three offline browser viewports pass. See
  docs/homepage-discovery.md. Real-model and historical benchmarks were not rerun.
- Link Opportunities presentation (`0d10d70` baseline): per-method ranked destination
  tablist + selected evidence panel, stacked on mobile. Exact short Unicode-safe excerpts,
  expandable originals/offsets, source/destination URLs, prominent raw similarity with
  limitations, and review actions before evidence. Decisions/notes keep the existing API;
  source/revision-scoped drafts and selection survive navigation/saves and clear on
  collection invalidation. No AI/ranking/backend/database changes. 47 targeted tests
  pass, one Windows privilege skip; five offline browser viewports pass with mock reviews,
  zero actual writes/inference/fetch. All 1,899 protected hashes match. See
  docs/link-opportunities-ui.md; manual assistive-technology and other browsers untested.
