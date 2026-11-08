# Semantic Content Analyser

An AI engineering portfolio application for exploring how website articles relate,
reviewing internal-link opportunities and comparing potentially overlapping content.

**Live demo:** [analyser.alichaytou.com](https://analyser.alichaytou.com)

The live demo runs on a **2 GB AWS Lightsail instance in Sydney**, as reported by
its maintainer. This preparation review did not access the AWS account or independently
verify the running host configuration. It is a limited portfolio/demo application,
not a production SEO platform or a claim of independently validated recommendation accuracy.

## Features

- **Semantic search:** pretrained `sentence-transformers/all-MiniLM-L6-v2` embeddings
  compare a question with article passages. TF-IDF provides a keyword baseline.
- **Internal-link opportunity review:** inspect source-to-destination passage evidence,
  exclude self/existing links and ineligible destinations, and save editorial decisions.
- **Content-overlap comparison:** compare passage pairs and inspect their original
  context. Rule-based Common terms highlighting is a reading aid, not model attribution.
- **Evidence-based PDF exports:** download a separate report for a completed search,
  link or overlap analysis, including settings, scores, excerpts, URLs and available
  editorial decisions. Exports reuse results without rerunning inference.
- **Website and CSV import:** bounded WordPress REST/XML sitemap discovery, article
  selection and extraction preview, followed by explicit collection replacement.
  CSV import/export and fictional sample articles remain available.
- **Temporary visitor workspaces:** signed ownership cookies isolate each browser's
  temporary SQLite collection and reviews. Admission checks and collection revisions
  prevent invalid imports and stale results from replacing current work.

**Editorial review is essential.** Cosine similarity measures vector closeness; it is
not accuracy, confidence, a relevance probability or a percentage of duplicated text.
High similarity alone does not establish duplicate content, keyword cannibalisation,
link usefulness or a reason to merge pages. The application does not insert website
links, merge pages, train a new model or modify the original website.

## Stack and processing

Python 3.12, FastAPI, SQLite, Sentence Transformers/MiniLM, scikit-learn TF-IDF,
vanilla HTML/CSS/JavaScript and ReportLab. Docker packages the application; Caddy
provides HTTPS reverse-proxy routing. MiniLM inference runs on CPU on the application
server, without a hosted LLM API. The first required model load can take time; subsequent
analyses can reuse collection indexes. Model weights are downloaded from Hugging Face
when not cached (or during the Docker build) and are pinned to a revision.

Local mode uses one persistent collection. Visitor mode shares one loaded model but
isolates collections and indexes, with bounded execution, workspace expiration and
cleanup. Treat downloaded reports and CSVs as potentially sensitive user data.

## Run locally on Windows

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:ENABLE_WEBSITE_FETCH = 'true'
.\.venv\Scripts\python.exe -m uvicorn semantic_analyser.api:app --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers
```

Open **http://127.0.0.1:8000**. A new local database starts with fictional sample
articles; an existing database retains its collection. Local source execution does
not automatically load `.env`. Keep local mode bound to loopback; it is a shared
workspace and must not be used for unrelated public visitors.

For isolated local visitors, set these before launching:

```powershell
$env:WORKSPACE_MODE = 'visitor'
$env:SECRET_KEY = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Keep deployment secrets out of Git. Production requires HTTPS, reviewed secrets,
visitor mode, suitable resource limits and enforced outbound protections. Only import
websites you own or are authorised to analyse; authentication, robots restrictions,
request budgets and SSRF protections must not be bypassed.

## Tests

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q
node --check web/app.js
```

Normal tests use controlled fixtures and a deterministic model test double. They do
not establish real-model quality or public-host capacity. Linux/root-only firewall
checks and privileged Windows checks need the appropriate environment. Existing
historical benchmarks and model evaluation are separate workflows, not steps to rerun
for every documentation change. See [the public-release review](docs/public-release-review.md)
for actual checks, failures, limitations and publication gates.

## Deployment and limits

The live 2 GB Lightsail configuration may differ from the checked-in production
Compose template, whose default application memory ceiling is 4 GB. Earlier EC2 and
8 GB hosting plans are historical engineering documents, not instructions to resize
the live demo or approved spending. Do not apply Terraform or deployment scripts
without reviewing their target, costs, secret handling and resource settings.

Application admission limits include 100 articles, 250,000 title/body characters,
20,000 body characters per article and 800 tokenizer passages; website selection is
limited to 40 pages. These ceilings are safeguards, not a claim that maximum-size
workloads fit every host. Public requests can be rejected when concurrency, time or
storage budgets are exhausted. Deployment settings determine retention; expiration
and explicit deletion can remove temporary workspaces. Export work you need to keep.

PDFs cover only the latest completed feature analysis for the current collection
revision. Reports cap results at 10 candidates per method, excerpts at 180 characters
and output at 2 MB, disclosing truncation. Restarting the server clears in-memory
analysis snapshots. Font coverage is limited; there is no universal multilingual or
tagged-PDF accessibility certification.

## Evaluation, third-party material and security

Fictional demo data and the synthetic benchmark support development. Real-site
experiments are single-site development evidence with carefully distinguished user,
AI-assisted and provisional judgements; do not describe them as independently
validated ground truth. Most real article bodies and generated reviewer packets live
under ignored `runtime/` and are not supplied in a fresh clone. Some evaluation scripts
therefore require private authorised caches and cannot reproduce those results from
public files alone. Permission to evaluate a site is not redistribution permission.

[Architecture](docs/architecture.md), [development journal](docs/development-journal.md),
[security findings](docs/phase4e-security-review.md) and
[security reporting](SECURITY.md) provide implementation context. Older dated reports
remain historical; passing tests or a live demo do not certify production readiness.

## Licence

Original project code is licensed under the [MIT License](LICENSE), copyright
2026 Ali Chaytou. Third-party packages, model weights, fonts and website material
retain their own terms; MIT does not relicense them. Instrument Sans includes its
[SIL Open Font License](web/fonts/OFL.txt). Publication-rights uncertainties are
listed in the release review and must be resolved before making the repository public.
