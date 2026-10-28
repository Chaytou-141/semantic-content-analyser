# Semantic Content Analyser: current context

Updated 29 October 2026 (Australia/Sydney). Phase 3B; no deployment or push.

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
- Enable website UI/API explicitly with `ENABLE_WEBSITE_FETCH=true` before startup.
  Every network request uses SafeFetcher: full public DNS validation, numeric-IP pinning,
  verified TLS, robots, same-host redirects, byte/decompression/deadline limits.
- Website run: one per workspace, 180 seconds INCLUDING human selection, 60 attempts,
  20 MiB wire/decoded; each fetch <=20 seconds, <=2 MiB encoded/decoded, host pause >=1s.
  Discovery <=12 documents, <=10 REST pages, <=200 candidates, sitemap nesting <=3.
  No quota reset per page or automatic retries. Cancel takes effect between steps.
- Extraction requires UTF-8 server-rendered article/main markup; ignores navigation,
  scripts, forms and template elements. Canonical URLs stay in scope; selected internal
  links map to article IDs. Headings remain in body text/preview; no SQLite schema change.
- Untrusted markup is never rendered or executed. Explicit restrictions fail closed;
  no authentication, paywall bypass, general link crawler or browser rendering.
- Evidence: `docs/phase3b-verification.json`, design/limits `docs/phase3b-websites.md`,
  factual history `docs/development-journal.md`. `scripts/verify_phase3b.py` runs the final
  suite and local browser/offline MiniLM checks; `--focused-only` avoids repeating a
  valid full suite after a focused-verifier issue. Do not rerun historical benchmarks.
- Known gaps: www/cross-host redirects, RSS, compressed sitemap files, nonstandard REST
  authentication/query routing, JS-only/ambiguous layouts, resumable runs. Extraction is
  heuristic and needs human review; synthetic checks are not recommendation accuracy.
- Next: review Phase 3B, then assess authorised real-site extraction quality and capacity,
  deployment-specific egress/abuse controls, retention/UX and hosting requirements.
  Not production-certified; no PostgreSQL, React, Redis or cloud changes are needed now.
