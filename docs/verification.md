# Verification record

## Locally verified

- Python 3.12.1 on Windows, CPU-only inference.
- 15 focused pytest checks passed: demo loading, method comparison, ranking uniqueness, passage evidence, self/existing/disallowed-link exclusions, body offsets and chunk tail coverage, invalid import rollback, review persistence/invalidation, CSV export/import/reset, unique overlap pairs, request/query bounds, saved historical evaluation, login/header enforcement, secure production sessions and empty keyword results.
- `node --check web/app.js` passed.
- Real model HTTP search returned successful embedding and TF-IDF rankings.
- Chromium desktop and 390-pixel mobile checks passed for comparison search, link evidence/exclusions, review saving, overlap review, collection filtering, article editor, evaluation context and import dialog. No uncaught page errors; no horizontal document overflow at 390 pixels.
- Screenshots inspected locally and retained in ignored `runtime/browser/`.
- Terraform 1.13.4 `fmt -check` and `validate` passed with AWS provider 6.70.0. Provider checksums were locked for Windows and Linux amd64.
- Both AWS shell scripts passed Bash syntax checks. The pinned Compose x86_64 release checksum and Caddy image tag were verified against their release sources.
- `pip check` passed in the development environment.

## Deployment checks

The GitHub Actions workflow provides independent Linux unit/API, Docker build/integration and Terraform validation jobs. Consult the workflow run for its actual status; defining a workflow does not mean it has passed.

Docker Engine is not installed in the original Windows environment, so container execution could not be checked locally. No Terraform plan/apply, AWS resources, domain configuration, HTTPS production endpoint, load test or AWS backup/recovery drill was performed.

## Product limits

This is a deployable single-workspace demo, not a hardened multi-tenant service. It has bounded data, one worker and a single-node SQLite database. The current saved evaluation uses assistant-proposed labels and historical whole-article scoring; it is not independent validation of the application passage scorer. Human editorial review and representative independent evaluation remain necessary before relying on recommendations for real content decisions.
