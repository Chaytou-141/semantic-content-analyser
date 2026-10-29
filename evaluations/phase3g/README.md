# Phase 3G — New editorial evaluation round

This round needs **44 task–destination judgements across seven tasks**, representing
23 distinct destinations (24 saved articles including source articles). A destination
can be Useful for one task and Not useful for another; do not collapse these decisions.

| Task | Required distinct recommendations |
| --- | ---: |
| R01 | 6 |
| R02 | 7 |
| R03 | 6 |
| R04 | 6 |
| L01 | 6 |
| L02 | 6 |
| L03 | 7 |

These are exactly the union of both frozen methods' top five for each task, not 44
different articles. The **15 overlap-investigation pairs remain separate** in the
earlier Phase 3D/3E material and do not contribute to this round's recommendation metrics.

## For the review coordinator

Give the reviewer **only** `runtime/phase3g/blind-review.html`, opened directly in
Chrome/Edge. This single offline file contains authorised saved text. No app/server,
login or model is needed. Do not publish the content or distribute it beyond the
authorised review. Do not send this repository, old review packets, Phase 3F files,
`coordinator-registry.json`, scores or model/ranking details before decisions are fixed.

Use a reviewer who has not previously seen these cases/assessments. Reviewers who took
part in the earlier AI-screened discussion must honestly select prior exposure. Their
new decisions can be preserved, but are ineligible for this round's no-prior-exposure
metrics. Do not copy the 14 earlier user decisions or the 45 AI-assisted assessments
into this round; no earlier answers are prefilled or accepted as a compatible import.

If the generated HTML is missing, the coordinator can rebuild it from the authorised
private Phase 3C/3D cache:

```powershell
.\.venv\Scripts\python.exe -B -m scripts.build_phase3g
```

The builder fails if that cache is unavailable or its fingerprints/evidence differ.
It never fetches content, loads a model or overwrites an existing HTML/changed registry.
Use `--output <new-file.html>` for another copy of the same round. A fresh Git checkout
contains the coordinator mapping/assets but not private article bodies. Scoring an
export needs only tracked metadata and the new CSV, not the private source cache.

## Reviewer instructions

1. Open the HTML. Enter your name/ID, human-judgement statement and prior-exposure answer
   honestly. None is selected initially. Prior exposure is not the same as using AI in
   general: it concerns earlier discussion, judgements or retrieval results for these cases.
2. Read each task criterion, question/source, destination and original passages. Expand
   full saved articles when needed. Existing-link status is from the saved snapshot.
3. Choose Useful, Not useful or Unsure and optionally explain. Similar topic alone is
   insufficient; consider the specific question and source intent. An additional useful
   link does not require the same criteria as a direct answer or duplicate-content flag.
4. Use task/status filters and Next unreviewed. Unsure stays unresolved; it is not forced
   to Not useful. You may revise your own choices before submitting.
5. Export CSV as a reliable backup. Browser drafts may persist and have no automatic
   expiry. Resume accepts only this new round's schema/fingerprint; invalid imports leave
   the current draft intact. Keep one reviewer per file. Exported files do not upload.
6. Send the CSV to the coordinator, who should preserve the submitted bytes/hash before
   revealing retrieval results. Later corrections/adjudication need a separate saved copy,
   not silent replacement of the first submission. No account or irreversible lock is
   provided by this offline tool.

Do not consult earlier packets, retrieval outputs, AI labels or another reviewer while
deciding. You may report uncertainty and lack of expertise; no synthetic test answer is
an editorial instruction. Clear this browser draft removes only this new round's draft.

## Score a submitted CSV

Save it as `runtime/phase3g/completed-review.csv`, then from the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m scripts.phase3g_review --reviews runtime\phase3g\completed-review.csv --output runtime\phase3g\human-metrics.json
```

Use a new output filename on subsequent runs. Existing files are never overwritten;
the output parent must exist. Preserve the submitted file's hash, e.g.
`Get-FileHash runtime\phase3g\completed-review.csv -Algorithm SHA256`.

Validation rejects wrong schemas/versions/packet fingerprints, missing/extra columns,
unknown/duplicate items, source/target/task mismatches, unsupported decisions/booleans/
exposure values, excessive file/field lengths, anonymous decisions and inconsistent
reviewer or provenance fields. CSV is UTF-8 (BOM accepted), strictly quoted and <=1 MiB.
Formula-leading reviewer/reason cells are escaped on export; quotes/newlines round-trip.

Eligible resolved labels require a named human attestation, reported `prior_exposure=none`
and Useful/Not useful. Screened/unsure/unreported exposure is preserved but ineligible;
Unsure, Unreviewed and missing rows remain explicitly unresolved. The score is Useful/k
only when all k results are resolved and eligible. Partial P@3 does not imply complete
P@5. No missing/AI label is substituted or counted negative.

Per-case metrics are reported independently. Related-content and internal-link summaries
stay separate. Comparative subset means use **the same paired complete cases for both
methods**, list their IDs and coverage, and do not replace all-case means until every
case is complete. Overlap usefulness/duplicate accuracy is not calculated here.

## What “blind” means here

The reviewer file omits method names, ranks, scores, old labels/decisions and the
coordinator ranking registry entirely. There is no button to reveal them. New opaque
item/article aliases and stable hash-based item/passage ordering avoid method-order
presentation. Unattributed duplicate passage pairs are deduplicated. Original text and
offsets/rankings in the source evidence are unchanged. The new round uses a distinct
packet fingerprint, schema and browser-storage namespace.

This supports a review blind to retrieval metadata **inside the delivered file**; it
does not certify formal blinded independence. Identity/exposure are self-reported,
external discussion cannot be prevented and there is no independent proctor or registry
access control. Both candidate and passage selection are model-derived; seven tasks from
one site are a development sample, not a held-out general SEO benchmark. Full article
access reduces dependence on selected passages but does not remove selection bias.

## Targeted verification

```powershell
.\.venv\Scripts\python.exe -B -m scripts.verify_phase3g
.\.venv\Scripts\python.exe -B -m pytest -q tests/test_phase3g_review.py tests/test_phase3e_review.py tests/test_phase3f_evaluation.py
```

This runs only Phase 3E/3F/3G review-tool tests and offline browser checks. Test CSVs under
`runtime/phase3g/synthetic-*` use explicitly synthetic choices, not human evidence. The
preservation snapshot is local verification scaffolding. No full suite, model inference,
historical benchmark or public request is run. Evidence: `docs/phase3g-verification.json`.
No actual new human judgements or accuracy results are claimed during packet preparation.
The verifier expects the local pre-change `runtime/phase3g/preservation-before.json`;
on a fresh checkout use the targeted pytest command above
instead of treating a missing local preservation snapshot as an application failure.
