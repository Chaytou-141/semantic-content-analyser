# UI/UX refinement: workflow and learning guide

1 November 2026 (Australia/Sydney). Baseline `f93aed4`; current Phase 4A/4B architecture
retained. Commit subject: **Refine onboarding import guidance and readable article evidence**.
This milestone changes presentation, not backend contracts, limits, rankings or models.

## Before and after

| Journey | Previously | Now |
| --- | --- | --- |
| First visit | Website input dominated; capabilities were implicit | Sample analysis and website analysis are distinct paths, with descriptions of search, links and overlap |
| Existing collection | Sample/current wording could be confused; generic fictional-data notice | Current collection has a continuation path, website-linked/sample distinction and non-destructive sample options |
| Import completion | Brief toast; collection-to-analysis action easy to miss | Persistent count-bearing success state with Explore analysis / Manage articles; analysis is opened and search focused |
| Navigation | Collection link and utility menu; route changes replaced history | Analysis, Articles and Import visible; existing hash routes retained with Back/Forward history |
| Collection management | Large import panels competed with existing articles | Primary analysis action and editing/table/export remain; replacement choices are collapsed until requested |
| Extraction | Processed text count, individual failure paragraphs | Accessible progress, accepted character budget, separate capacity exclusions and failures in expandable groups |
| Results | Long passages immediately visible | Short previews with native Expand/Collapse details, exact full evidence and saved offsets |
| Evaluation | Technical feature could be interpreted as current accuracy | Clearly labelled historical Development evaluation, separate from imported content and unchanged |

The user reported 110 discovered / 40 selected / 32 imported / eight capacity exclusions.
Read-only inspection confirmed the saved collection has **32 articles and 249,162
title/body characters**. No live discovery, extraction, search or model run was repeated
against Freeze Edge. Do not treat the user's observation as a new automated benchmark.

## Use the updated workflow

1. A fresh visitor workspace contains the 21 fictional samples. Explore sample analysis
   opens the normal tools, without fetching a website or creating another AI pipeline.
2. On an existing custom collection, sample options explain the replacement risk and
   offer Explore my current collection. Nothing is reset automatically. To explore samples
   while retaining data, use a fresh private browser context **in visitor mode**. In shared
   local mode another browser still sees the same data; restoration requires explicit
   confirmation and clears articles/reviews. A second parallel local sample workspace was
   not added just for this UI milestone.
3. Website input opens the existing Find → Choose → Review/import wizard. Discovery
   explanations describe automatic, WordPress and XML options. Select first 40 shown
   replaces the selection with the first visible filtered matches, clearing hidden choices.
4. Processed progress includes unsuccessful items. The backend only supplies the final
   accepted character total, so capacity is labelled as calculating during extraction,
   then shows the accepted title/body total. No intermediate usage is invented.
5. Capacity exclusions are not extraction failures. All reasons remain accessible.
   Other omissions inferred from selected-minus-ready-minus-failures are described
   without asserting an unsupported duplicate reason. Warnings and partial acceptance
   remain. Final model-tokenizer admission is authoritative and can reject the import.
6. Confirm replacement, then Explore analysis or Manage articles. Search examples for
   custom content use actual article titles, not invented questions/recommendations.
   Open original article appears only for public HTTP(S) URLs; sample example.com URLs
   are explicitly fictional. Link reviews still save notes and decisions through the API.
7. Compare overlap evidence, not only its score. No overlap-specific saved-decision API
   exists, so no unsupported review control or automatic merge/delete action was added.

Collection origin is a display distinction based on existing article IDs/URLs and the
sample heuristic; the backend does not persist a new import-origin field. It is not a
new provenance guarantee. Import-success state is revision-bound frontend memory and
does not survive reload; collection and saved editorial decisions do survive normally.

## Why the application has limits

Verified against storage/schemas/engine/websites code: 250,000 collection characters,
100 articles, 20,000 body characters/article, 800 model passages, 40 selected website
articles. `tests/test_ux_display.py` binds frontend constants to these existing values.
These are **application resource-management limits**, not limits imposed by MiniLM.
They keep memory, tokenisation, embedding workloads and processing time bounded for
multiple visitors in a small demo. No numerical limit changed, and no text is shortened
to make admission pass. Token window constraints and collection passage count are distinct.
The About this demo section gives this rationale without presenting similarity as accuracy.

## Citation artifact investigation

Saved authorised HTML `runtime/phase3c/corrected30/response-012.bin` and `response-015.bin`
already contain the exact `:contentReference[oaicite:N]{index=N}` pattern. The corresponding
articles `Wb759d5121095c6e0` and `Wb092510eb9d3d03b` retain it in the saved collection and
older evidence. This establishes a source-origin artifact in the cached sample; it does
not assert the current live site still contains it. No refetch occurred.

`displayText` removes only that exact numeric marker from display previews. It does not
edit data. Matching evidence shows a notice and expands to the original passage with
unchanged offsets. Newly extracted article previews show cleaned prose plus an explicit
original-text disclosure when applicable. The editor, API, SQLite, model input and old
evaluation/source files remain raw. Other strings resembling citations are preserved.
This is a presentation choice, not a claim that extraction or ranking quality improved.

## How the frontend works

- `web/index.html` defines the stable views, forms, dialogs, success status, progress
  controls and About section. `web/styles.css` retains Instrument Sans, reading serif,
  plum/paper tokens and existing components, adding scoped responsive layout/evidence rules.
- `el()` creates DOM nodes and uses `textContent` for untrusted prose. No fetched HTML
  is executed. `safeTarget` restricts outgoing UI links to HTTP(S) and keeps noopener.
- `state` holds the current articles, metadata, collection revision, view and result state.
  It is not another database. `loadCollection()` reads `/api/articles` and `/api/meta`,
  updates counts, examples and source choices, and invalidates stale import status.
- Event listeners intercept forms, gather values and call the unchanged API. `task()`
  serialises client actions, sets aria-busy, disables submit buttons, and shows actionable
  errors inside the current dialog as well as the page. Cancellation remains available.
- `api()` preserves X-Workspace-Request/If-Match and revision handling. Session expiry and
  budget errors explain reload/wait; unexpected transport/results advise checking state
  before retrying, rather than falsely promising a write never happened.
- `navigate()` updates visible sections and aria-current, pushes a changed hash into browser
  history and responds to hash changes. Main-navigation actions focus the main landmark;
  slash focuses search. Dialog focus/unsaved-change confirmations are retained.
- `renderWebsite()` consumes backend snapshots; it does not infer fabricated success
  labels. `advanceWebsite()` performs bounded steps with the existing run/revision token.
  `importComplete()` records a success message only after import and collection reload.
- `evidence()` clips only the initial display, then keeps full raw passage text in details.
  `renderLinks()` saves the note/decision against the original revision and rereads saved
  decisions on another request. `renderOverlaps()` remains an inspection view.

Small learning exercises: trace a search submit to api() and back to renderSearch();
watch an If-Match header in DevTools on the disposable demo; expand a source passage and
compare raw text/offsets; use Back after navigating Articles; filter before bulk selection.
Do not perform destructive exercises on the saved Freeze Edge collection.

## Verification and practical limits

Relevant tests: **163 passed, one existing Windows symlink test skipped, 15.80s**. New
checks cover backend/frontend limit agreement, exact display cleanup and preservation of
raw extraction markers; existing API, website, admission, visitor and demo-operation
regressions cover the backend/security controls. Node syntax check passed.

`scripts/verify_ux_refinement.py` starts a disposable visitor app on loopback with a
deterministic fake encoder and controlled DNS/transport. It exercises sample search/
comparison, raw evidence, saved note persistence, overlaps, historical evaluation,
filtered selection, WordPress discovery (110), capacity-limited extraction (40 → 32/8),
XML import, partial acceptance, success guidance, editing/export/valid and invalid CSV,
visitor separation, keyboard/history and 390px layout. Empty-link/overlap and 429/410
presentation cases use explicitly simulated valid-shaped responses. No JavaScript errors,
external browser requests or public fetches occurred. Synthetic QA feedback is not new
editorial/model evaluation. Desktop/mobile screenshots are private under runtime/ux-refinement.

The live localhost app was inspected read-only for home/sample protection and navigation
back to its actual 32-article analysis. No search/import/reset/review write was requested.
1,793 protected files, including the main saved SQLite file, remain unchanged. Two live
SQLite WAL/SHM sidecars are excluded because normal connection closure can remove them;
the main DB hash and logical 32/249,162 state are checked. `.vscode/` is untouched.

Reproduce only against disposable fixtures:

```powershell
.\.venv\Scripts\python.exe -B scripts/verify_ux_refinement.py
.\.venv\Scripts\python.exe -B -m pytest -q tests/test_ux_display.py tests/test_application.py tests/test_websites.py tests/test_website_compatibility.py tests/test_safe_fetch_api.py tests/test_demo_operations.py tests/test_collection_admission.py tests/test_visitor_workspaces.py
node --check web/app.js
```

The verifier expects the local pre-change preservation snapshot. On a fresh checkout,
targeted pytest works independently; full preservation checks require a new coordinator
baseline. `scripts/browser_smoke.py` selectors are updated for the new labels and remains
a separate opt-in smoke for a disposable sample workspace, not the saved real collection.
Historical benchmark verifiers/evidence were not rerun or overwritten.

Docker/HTTPS/UID, actual kernel quota/egress enforcement, dependency/image validation
and hosting capacity remain pending from Phase 4B. Restart budgets are process-local,
storage totals soft, native cancellation cooperative, real non-WordPress/sitemap coverage
unvalidated. UI improvements do not close those release blockers or certify recommendation
quality. No new model, model benchmark, editorial review packet, LinkedIn publication,
live site, AWS resource, paid service, GitHub push or deployment is part of this milestone.
