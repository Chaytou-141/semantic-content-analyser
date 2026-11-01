# Semantic Content Analyser

A working application for exploring related content using local CPU embeddings and a keyword baseline, with persistent local-demo or isolated temporary visitor workspaces. Built as an AI engineering learning project, with an AWS EC2 deployment path.

## What it does

- **Semantic search:** search the collection using MiniLM embeddings, TF-IDF or both. Results include the best matching passage, score and article details.
- **Internal-link review:** select a source article, exclude self-links, existing links and ineligible pages, and inspect source/destination passage evidence. Save useful/not-useful decisions and editorial notes without inserting links.
- **Content-overlap review:** inspect related passage pairs, with thresholds and result limits. Similarity is evidence to review, not a merge or deletion decision.
- **Collection management:** import/export CSV, edit article text and link eligibility, and restore the fictional demo collection. Invalid imports leave existing data intact.
- **Evaluation:** view the saved, honestly labelled development comparison. The earlier Python experiments remain available.
- **Deployment:** Docker image with a pinned CPU model, HTTPS proxy configuration, Terraform for AWS EC2/ECR, and CI checks.

This is a bounded learning/demo application. Local mode has one persistent collection; visitor mode isolates temporary collections with signed ownership cookies. Independent human evaluation, large-scale retrieval, public abuse controls and production load testing remain future work.

## Run locally on Windows

From this project folder, use the environment's Python explicitly:

```powershell
# Only needed on a fresh checkout:
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# Launch the application:
.\.venv\Scripts\python.exe -m uvicorn semantic_analyser.api:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. The 21 fictional demo articles load automatically into an ignored SQLite database at `runtime/workspace.sqlite3`. The first import/edit preflight or analysis loads the model. Imports and edits check real-tokenizer passage limits before saving; collection embeddings are built on the first semantic analysis and reused until the collection changes. Model files are fetched from Hugging Face if not cached. Article/query text is processed on the machine running the app, not sent to a hosted inference API.

The first page offers sample analysis or your website. Existing custom collections have
a non-destructive continuation path; restoring samples always requires confirmation.
Enable website import with
`$env:ENABLE_WEBSITE_FETCH = 'true'` before starting the server, as described below.
You can also choose **Try the sample articles** or import CSV. After import, the app
opens article analysis; collection management is under **Articles** and development
evaluation is under **More**. Starting discovery does not replace saved data.

Analysis, Articles and Import are visible in the main navigation. Website/CSV imports
show a count-bearing success state with Explore analysis and Manage articles. Matching
passages start short and expand to unchanged full evidence. The import wizard groups
capacity exclusions separately from extraction failures and shows the accepted character
budget. [UI workflow and frontend learning guide](docs/ux-refinement-learning-guide.md)
explains state, events, API interactions and the resource-management rationale.

Local mode has no password by default and binds to the loopback address. To test sign-in locally, set environment variables before launching:

```powershell
$env:APP_PASSWORD = Read-Host "Workspace password"
$env:SECRET_KEY = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Do not set `APP_ENV=production` for plain HTTP localhost: production sessions require HTTPS. Local source execution does not automatically read `.env`; Docker Compose reads the relevant environment files.

## Temporary visitor workspaces (Phase 2B)

The default `WORKSPACE_MODE=local` retains the existing persistent local demo and its
SQLite file. Use it on loopback or as a trusted private demonstration. To test isolated
visitors locally in a new PowerShell terminal:

```powershell
$env:WORKSPACE_MODE = 'visitor'
$env:SECRET_KEY = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
.\.venv\Scripts\python.exe -m uvicorn semantic_analyser.api:app --host 127.0.0.1 --port 8000 --workers 1
```

Use two browser profiles or private sessions to test different visitors. Each starts
with its own copy of the fictional demo and can import its own CSV. Visitor mode does
not open the original `DATABASE_PATH`; its default temporary root is a `visitors`
directory beside that path, or `VISITOR_WORKSPACE_ROOT` when set explicitly. Keep the
same strong SECRET_KEY across restarts to retain ownership of unexpired workspaces.
HTTPS with `APP_ENV=production` is required for secure public cookies; no public
deployment is performed or certified by this implementation.

Defaults: 32 workspaces, one CPU analysis/preflight worker, two pending operations,
four idle cached indexes, a 60-second operation response deadline, one-hour idle
expiry, 24-hour absolute expiry, and cleanup every 60 seconds. Configure with
`MAX_VISITOR_WORKSPACES`, `ANALYSIS_QUEUE_SIZE`, `MAX_CACHED_INDEXES`,
`ANALYSIS_TIMEOUT_SECONDS`, `WORKSPACE_IDLE_SECONDS`, `WORKSPACE_LIFETIME_SECONDS`
and `WORKSPACE_CLEANUP_SECONDS`. Workspace locks and SQLite busy waits are bounded
at one second by default (`WORKSPACE_LOCK_SECONDS` controls the former).

Native inference cannot be force-cancelled by a Python thread. A timed-out running
operation keeps its slot and workspace lease until it finishes; excess work gets 503
with Retry-After. Writes check cancellation/ownership before committing. After a
timeout refresh the collection to reconcile state; do not automatically replay writes.
Graceful shutdown waits for running work. A permanently stuck native call requires a
supervisor/process restart. This is not a hard CPU-time or RAM sandbox.

Visitor API clients first call `GET /api/session` with `X-Workspace-Request: true`,
retain the ownership cookie, then read `/api/articles`. Supply its `collection_revision`
as `If-Match` on analysis and mutation requests. Missing/stale revisions return 428/409.
Results carry their snapshot revision; review actions and article editors retain that
revision. `DELETE /api/workspace` deletes only the current visitor's idle workspace;
logout revokes ownership, with active work protected until it exits. Expired sessions
return 410 and clear the cookie; reload to begin again. No workspace ID/path is accepted
as an authorization override. Local-mode legacy calls may omit If-Match, but the UI
sends revisions in both modes.

One process owns a visitor root; a second owner fails startup. Restarts retain unexpired
SQLite text/reviews/revisions but discard indexes and pending HTTP work. Cleanup closes
SQLite handles and deletes only recognized, unleased workspace files; unexpected
contents are retained for inspection. This phase adds no crawler, external identity
provider, PostgreSQL, Redis or cloud infrastructure.

Run the full tests and `scripts/verify_phase2b.py` using the existing virtual environment
for offline real-model/two-browser verification. That script uses localhost port 8013,
disposable data under `runtime/phase2b/` and never regenerates Phase 1B results.

## Use Docker locally

Install Docker Desktop and select Linux containers first; Docker is not currently installed in the original development environment.

```powershell
docker compose up --build -d
docker compose logs -f app
```

Open **http://127.0.0.1:8000**. The image downloads the pinned model during its build and uses offline model access at runtime. The first build is substantial because it includes CPU PyTorch and model weights. Named volume `workspace` preserves article data and review decisions across container restarts.

```powershell
docker compose down
```

This stops containers without deleting the data volume. Do not add `--volumes` unless you intend to discard that local database.

## CSV format

Required columns: `id,title,body`. Optional: `topic,url,eligible,existing_links`.

```csv
id,title,body,topic,url,eligible,existing_links
A01,Choosing a display fridge,Compare capacity and counter space.,refrigeration,https://example.com/a01,true,A02
A02,Measuring cabinet space,Measure the counter and ventilation clearance.,refrigeration,https://example.com/a02,true,
```

- IDs must be unique and contain only letters, numbers, hyphens or underscores.
- Existing links use article IDs separated by semicolons and must reference articles in the collection.
- `eligible=false` excludes a page as a link destination; it remains searchable and available for overlap review.
- Import replaces the full collection and clears previous review decisions. Export first if you need the old collection.
- Limits: 100 articles, 20,000 characters per body, 250,000 total text characters, and 800 model passages. HTTP requests are limited to 2 MB.
- Imports, demo resets and article edits run full preflight before any collection write. Invalid candidates preserve the existing articles and reviews; model-validation unavailability returns a retryable error. The 250,000-character limit remains unchanged.
- Export escapes spreadsheet formula prefixes. If a text field begins with `=`, `+`, `-` or `@`, a leading apostrophe is added to the exported value.
- The demo's A01 → A04 existing link and A20's ineligible status are fictional test conditions, not observed website data.

## Model and scoring

Model: `sentence-transformers/all-MiniLM-L6-v2`; revision: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`; licence: Apache 2.0. It produces 384-dimensional English-language embeddings with a 256-word-piece model input limit. See the [model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).

The application splits bodies into 192-token windows with a 32-token overlap, caps the title at 40 tokens, and retains character offsets so displayed evidence is an actual source substring. This is a simple chunking baseline, not a validated solution for every article type. It can cut across sentences and longer articles have more chances to produce a high-scoring passage.

Search returns each article's highest scoring passage. Link discovery uses the strongest source/destination passage pair. Overlap review uses the strongest cross-article passage pair, not a claim that entire articles are duplicates. TF-IDF and embeddings use the same passages in the application. Scores are not probabilities and their sizes are not directly comparable between methods.

The application passage scorer differs from the original whole-article evaluation experiments. The Evaluation page explicitly shows **historical development results**, not live metrics for edited collections or a validated measurement of the new chunking method. Model/query/threshold changes should be evaluated separately before claiming improvement.

## Check the application

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check web/app.js

# With the server running against a disposable 21-article demo workspace:
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts/browser_smoke.py
```

Unit/API tests use a deterministic test encoder and do not download the model. Browser checks exercise the real running service and save screenshots in ignored `runtime/browser/`. They save one demo link review. GitHub Actions checks the tests, builds and smoke-tests the Docker image, and validates Terraform.

The original `requirements-lock.txt` is a snapshot of the tested Windows environment including development dependencies, not a Linux lockfile. `requirements.txt` pins direct runtime dependencies; the Docker build installs CPU PyTorch separately. Container validation runs in CI; see [verification notes](docs/verification.md) for what was actually tested locally.

## API

The frontend and API are served from the same origin. Authenticated callers can retrieve the OpenAPI schema at `/api/schema`.

| Route | Purpose |
| --- | --- |
| `GET /health` | Process/database health and model-loaded status |
| `GET /api/session` | Sign-in state |
| `POST /api/login`, `/api/logout` | Workspace session |
| `GET /api/articles` | Current article collection |
| `POST /api/articles/import`, `/api/articles/reset` | Atomic replacement / restore demo |
| `PUT /api/articles/{id}` | Edit text and link rules |
| `GET /api/articles/export` | Download CSV |
| `POST /api/search` | Search or compare methods |
| `POST /api/links` | Source-specific link candidates |
| `POST /api/overlaps` | Passage overlap pairs |
| `GET /api/reviews`, `POST /api/reviews` | Saved editorial decisions |
| `GET /api/evaluation` | Saved original development metrics |
| `POST /api/website/check` | Optional bounded fetch check; metadata only, disabled by default |

All state-changing and analysis POST/PUT calls require `X-Workspace-Request: true`. This custom header, same-origin requests and strict same-site cookies prevent ordinary cross-site form submissions. The production deployment template requires a 12+ character `APP_PASSWORD` and 32+ character `SECRET_KEY`; the deployment helper enforces a longer password. Sign-in sessions expire after eight hours; visitor ownership and idle-expiry limits are separate. The single-worker process throttles sign-in attempts; this is not a distributed abuse-prevention system.

## Website import (Phase 3B)

Set `$env:ENABLE_WEBSITE_FETCH = 'true'` before launching Uvicorn to enable the website
URL workflow on the first page. Enter a public website or published XML sitemap URL,
discover WordPress posts or sitemap URLs, select up to 40 articles, and review the
extracted text before replacing your collection. Existing CSV/sample workflows remain.

Phase 4A fixes explicit extensionless/query-based sitemap URLs and namespace extensions.
In **XML sitemap** discovery mode, a bare website root uses homepage/robots-advertised
maps (or conventional defaults) without probing WordPress. A non-root/query URL is
treated as the explicit sitemap endpoint and is preserved. Standard namespace-qualified
URL sets/indexes and legacy namespace-free maps are supported; image/alternate-language
extensions do not become article candidates. Discovery-limit warnings describe partial
results. This is offline-fixture coverage, not new live-site validation.

Only public server-rendered UTF-8 pages with an article/main region are supported.
No authentication, paywall bypass, JavaScript rendering or cross-host redirects are
supported. Each run has a fixed 15-minute selection/review lifetime and a separate
180-second cumulative fetch budget, with 60 network attempts. Waiting does not reset
requests, bytes or fetch time. Oversized collections still fail the existing character/passage
checks without replacing your articles or reviews. This is not a complete-site crawl.

See [workflow, supported structures and limitations](docs/phase3b-websites.md),
[verification evidence](docs/phase3b-verification.json) and the short
[project context](docs/PROJECT_CONTEXT.md).

Phase 3C [real-site findings and bounded selection-time changes](docs/phase3c-real-websites.md)
record the authorised FreezeEdge sample. WordPress extraction was measured; that site's
advertised sitemap returned 404, so independent real sitemap coverage is still missing.

The [Phase 3D offline editorial evaluation](docs/phase3d-real-content-evaluation.md)
reuses those saved pages with provisional labels and human-review worksheets. Its
research artifacts are separate from the application's original Evaluation page.
See the [release-readiness checklist](docs/release-readiness.md) before planning public hosting.

[Phase 4A compatibility and container assessment](docs/phase4a-compatibility-readiness.md)
records the targeted tests and remaining deployment blockers. The production Compose
template now explicitly enables visitor isolation and website import while retaining
the password gate. The local Compose/demo defaults are unchanged. Docker has not been
run locally; the template is not approval to deploy or expose anonymous access.
Further human editorial evaluation is intentionally deferred; existing evidence is preserved.

Phase 4B adds opt-in demo admission and storage safeguards, enabled in production Compose:
API/session/outbound budgets, bounded HTTP concurrency, SQLite page limits and physical
storage admission thresholds. Trusted proxy identity uses exact peers and overwritten
custom headers; Docker disables Uvicorn forwarded-header rewriting. Keep that
`--no-proxy-headers` setting when enabling demo limits in a custom source launch.
The image remains single-worker; existing rankings and model behaviour are unchanged.

See [Phase 4B architecture, limits and reproduction steps](docs/phase4b-demo-operations.md).
Docker verification was **skipped because Docker is unavailable**, not passed. No live
sites, new editorial labels, real-model benchmarks, cloud services or public exposure
were used. The optional loopback-only verifier uses an already-built local image:

```powershell
.\.venv\Scripts\python.exe -B scripts/verify_phase4b_docker.py --image semantic-demo:local
```

Read its JSON status: a skipped check is not container verification. It never pulls or
builds an image. Network-layer egress, Linux/HTTPS behaviour, actual cgroup exhaustion and
hosting capacity remain unverified; physical storage thresholds are not filesystem quotas.

## Website fetching foundation (Phase 3A)

The reusable safe-fetch service validates and pins public DNS destinations, checks
robots.txt, and bounds time, bytes, redirects and requests. Phase 3A introduced the
diagnostic API; Phase 3B adds the website workflow described above. Both use the existing
workspace cookie, request header and visitor collection revision. Keep public
multi-visitor use in visitor mode.
`FETCH_DENY_CIDRS` can add comma-separated operator infrastructure ranges to the deny
policy. Existing data, semantic scoring and admission limits are unchanged. Phase 3B
reuses this service for discovery and article import; the Phase 3A report describes
the foundation at its original milestone.

See [architecture, limits, security limitations and the Phase 3B plan](docs/phase3a-safe-fetch.md)
and [measured verification evidence](docs/phase3a-verification.json). Local fixtures
and offline regression checks do not establish public deployment readiness.

## Deploy to AWS

Follow [the AWS learning and deployment guide](docs/aws-deployment.md). It explains EC2, ECR, security groups, IAM roles, HTTPS, persistent volumes, backup, updates and cleanup. No AWS resources have been created by preparing this repository.

The Terraform configuration uses `ap-southeast-2` (Sydney), a `t3.medium` CPU instance, an encrypted 40 GB EBS root volume, an Elastic IP, and a private ECR repository. These resources incur AWS charges. Review an AWS pricing estimate and budget before applying the plan; this is not promised to fit a free tier.

## Project map

```text
semantic_analyser/     Python API, retrieval engine, validation and SQLite storage
web/                   Browser interface; no separate Node build required
experiments/           Original learning scripts and evaluation runs
data/                  Fictional articles and development questions
labels/                Relevance labels, provenance and reasons
tests/                 Focused API, retrieval, persistence and auth checks
scripts/               Browser verification
deploy/aws/            Production Compose, HTTPS proxy and release helper
infra/aws/             Terraform infrastructure
docs/                  Learning journal, evaluation evidence and deployment guide
```

The original brief remains in `Semantic_Content_Analyser_Starter_Docs/`. At the user's later request, scope expanded from guided experiments to a deployable demo application. WordPress/sitemap import is opt-in; SocialBuzz integration and automatic publishing, merging or deletion are not implemented.
