# Link Opportunities visual redesign

1 November 2026 (Australia/Sydney). Baseline `0d10d70`.
Commit subject: **Redesign link opportunities as an editorial workbench**.
Resolve with `git log -1 --format=%H --grep="Redesign link opportunities as an editorial workbench"`.

## Layout decision

The old renderer repeated a full recommendation card, two evidence columns, notes and
actions for every destination. Its five-card list made it difficult to scan destinations
or keep an article relationship in view while reviewing. A carousel would hide candidates;
accordions alone would retain the repeated-card structure and make method comparison
harder. A master-detail workbench keeps ranking order visible while showing only the
selected recommendation's evidence.

Desktop/tablet:

```text
MiniLM candidates                                      reviewed count
exclusions (existing rules)
five ranked destination tabs   | source article
title / score / human decision  |    ↓ suggested destination       score
                               | human decision controls / note
                               | exact source and destination excerpts
                               | expandable originals / original URLs
```

Each method retains its own list/detail and selection; compare mode remains two method
sections, not a merged ranking. At <=760px, the list stacks above the detail. Clicking a
candidate with a pointer brings its detail into view. Back to destinations returns focus
to the selected tab. Keyboard navigation stays in the list until Inspect selected evidence
or Tab moves into the selected panel. No page-hash navigation is used for these controls.

Visual system: existing white `#ffffff`, paper `#f8f7fa`, ink `#342d3b`, accent `#724760`
and line `#e4dfe8`; Instrument Sans for controls/titles, Georgia for original quotations.
The strong accent marks selection, never model confidence. Useful and Not useful use
explicit human-decision text, small check/cross indicators and restrained badges/borders;
rejected items remain available. No red/green score bands, animated scores, new fonts,
external assets or packages were introduced. A small source node and downward arrow
communicate article direction without changing the application's existing visual language.

## Implementation

- `web/app.js:renderLinks`: same `/api/links` response and `/api/reviews` request. A
  vertical ARIA tablist controls one labelled tabpanel per method. ArrowUp/ArrowDown
  wrap; Home/End select boundaries; one tab per list is in the Tab sequence. Reviews
  capture the source ID and preserve the existing If-Match revision guard.
- Selections and unsaved note drafts are kept in `state.linkView`, scoped by source and
  collection revision; `invalidateResults` clears them. Notes/reviews belong to the
  source/destination pair across both methods. Draft input values synchronise when both
  method panels show that pair. Successful saves preserve selection/focus; failed saves
  retain the draft and prior decision. Navigating during a pending save does not force
  the old selection back when the request completes. Unsaved notes do not survive a
  full browser reload; their label explains they save with the next decision.
- `linkPassage` / `linkExcerpt`: up to 220 Unicode characters from the exact returned
  passage, preferring a complete sentence/word boundary. No citation cleanup, paraphrase,
  generated explanation, word highlighting, or extra text is inserted into the excerpt.
  The full original passage and original character offsets remain in native details.
  Source/destination URLs and article-body dialogs remain accessible. All untrusted text
  goes through existing textContent helpers; no fetched HTML is rendered.
- The score retains the existing three-decimal display and has contextual help: cosine
  similarity is not accuracy, probability or editorial confidence, and scores across
  methods are not directly comparable. The full passage pair is labelled evidence, not
  an explanation of why a link is useful. Review controls appear before the evidence,
  avoiding the need to scroll through the passage text to reach them.
- `web/styles.css`: scoped `.link-*` rules reuse tokens, focus outlines and button styles.
  Short excerpt reading width is capped at 70ch. No evidence-box nested scrollers are
  added. `web/index.html` versions the CSS/JS references to refresh cached clients.

No backend, API, model, TF-IDF, cosine computation, thresholds, ordering, SQLite schema,
saved articles or stored editorial decisions changed. Results are never reordered by
review status, and clearing a decision still uses the existing `pending` value.

## Verification

**47 targeted tests passed, 1 skipped (7.55s)**. The skip is the existing Windows account's
missing symbolic-link privilege. New pure-display tests protect exact whitespace/markup/
citation text, Unicode-safe truncation, length, original input and sentence boundaries.
Existing application/workspace tests exercise review persistence, import/export, revision
handling and isolation with fake encoders. No real model or benchmark ran.

Five offline Chromium viewports passed: 1440x1000, 1024x768, 768x1024, 390x844 and 320x800.
Each case uses the actual frontend and existing API shapes with original synthetic article
fixtures and controlled in-memory responses. All five candidates are traversed; the test
compares identities, URLs, all raw passage text, offsets, score strings and ranking payloads.
It checks keyboard focus and native full-evidence expansion, original source-body dialogs,
all decision values and notes, save failure, navigation during save, mock persistence after
reload, compare-mode pair synchronisation, and zero/singleton candidate boundaries.

Synthetic markup in original evidence remains inert text. No unexpected requests, browser
exceptions, real model runs, live fetching, actual review writes or horizontal overflow
occurred. ARIA snapshots are saved; this is keyboard/semantic browser verification, not
a formal screen-reader or WCAG certification. Firefox, Safari and real touch hardware were
not run. No claim about recommendation quality or new ML accuracy is made.

A display-only test initially assumed a third complete sentence would fall outside 220
characters; it actually fit. The test was corrected to use a genuinely partial next sentence.
An additional Unicode case then protected against cutting a surrogate pair; truncation now
counts full Unicode characters. These changes affect excerpts only, not original offsets.

The frozen baseline was also rendered offline. At 1440px, the first review action started
476.67px below its old card top and 310.31px below the new detail top in this synthetic
fixture. These are layout measurements, not a generalised usability/performance benchmark.

All **1,899 protected-file SHA-256 hashes** match the pre-edit baseline, including current
SQLite data/reviews, existing evaluation evidence and historical benchmarks. Untracked
`.vscode/` files are untouched. No deployment or GitHub push.

Reproduce from the repository root:

```powershell
.\.venv\Scripts\python.exe -B scripts/verify_link_opportunities.py
.\.venv\Scripts\python.exe -B scripts/verify_link_opportunities.py --baseline
.\.venv\Scripts\python.exe -B -m pytest -q --tb=short tests/test_link_presentation.py tests/test_ux_display.py tests/test_application.py tests/test_visitor_workspaces.py
node --check web/app.js
```

Portable measurements: `docs/link-opportunities-verification.json`.
Private before/after screenshots and accessibility snapshots: `runtime/link-opportunities-ui`.
The standalone browser verifier expects its local pre-edit preservation baseline in that
directory; it does not restore or fabricate saved data to satisfy an older fixture.
