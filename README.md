# Semantic Content Analyser

A working, single-workspace application for exploring related content using local CPU embeddings and a keyword baseline. Built as an AI engineering learning project, with an AWS EC2 deployment path.

## What it does

- **Semantic search:** search the collection using MiniLM embeddings, TF-IDF or both. Results include the best matching passage, score and article details.
- **Internal-link review:** select a source article, exclude self-links, existing links and ineligible pages, and inspect source/destination passage evidence. Save useful/not-useful decisions and editorial notes without inserting links.
- **Content-overlap review:** inspect related passage pairs, with thresholds and result limits. Similarity is evidence to review, not a merge or deletion decision.
- **Collection management:** import/export CSV, edit article text and link eligibility, and restore the fictional demo collection. Invalid imports leave existing data intact.
- **Evaluation:** view the saved, honestly labelled development comparison. The earlier Python experiments remain available.
- **Deployment:** Docker image with a pinned CPU model, HTTPS proxy configuration, Terraform for AWS EC2/ECR, and CI checks.

This is a bounded learning/demo application, not a multi-tenant commercial platform. It has one shared article collection and one optional workspace password. Independent human evaluation, multi-user authorisation, large-scale retrieval and production load testing remain future work.

## Run locally on Windows

From this project folder, use the environment's Python explicitly:

```powershell
# Only needed on a fresh checkout:
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# Launch the application:
.\.venv\Scripts\python.exe -m uvicorn semantic_analyser.api:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. The 21 fictional demo articles load automatically into an ignored SQLite database at `runtime/workspace.sqlite3`. The first analysis loads the model and builds the collection index; subsequent requests reuse it. Model files are fetched from Hugging Face if not cached. Article/query text is processed on the machine running the app, not sent to a hosted inference API.

Local mode has no password by default and binds to the loopback address. To test sign-in locally, set environment variables before launching:

```powershell
$env:APP_PASSWORD = Read-Host "Workspace password"
$env:SECRET_KEY = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Do not set `APP_ENV=production` for plain HTTP localhost: production sessions require HTTPS. Local source execution does not automatically read `.env`; Docker Compose reads the relevant environment files.

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

All state-changing and analysis POST/PUT calls require `X-Workspace-Request: true`. This custom header, same-origin requests and strict same-site cookies prevent ordinary cross-site form submissions. Production requires a 12+ character `APP_PASSWORD` and 32+ character `SECRET_KEY`; the deployment helper enforces a longer password. Sessions expire after eight hours. The single-worker process throttles sign-in attempts; this is not a distributed abuse-prevention system.

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

The original brief remains in `Semantic_Content_Analyser_Starter_Docs/`. At the user's later request, scope expanded from guided experiments to a deployable demo application. No SocialBuzz or WordPress integration, client-site access, automatic publishing, merging or deletion is implemented.
