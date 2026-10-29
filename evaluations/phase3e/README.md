# Phase 3E: independent SEO editorial review

This prepares a **new human review round** from Phase 3D's saved 44 candidate judgements
and 15 overlap pairs. It preserves the original AI labels, worksheets, article snapshot,
rankings and HTML packet. Later homepage changes are also preserved. No application
code, network requests, model inference or new relevance labels are involved.

## Open and review

Open `runtime/phase3e/independent-review.html` directly in Chrome or Edge. No server,
account, package installation or running Semantic Content Analyser instance is needed.
If the file is missing, rebuild from the existing authorised local cache:

```powershell
.\.venv\Scripts\python.exe -B scripts\build_phase3e.py
```

Existing output is protected unless you explicitly pass `--overwrite`. Rebuilding the
same packet preserves its fingerprint and compatible browser draft. The source cache
is private/untracked; a fresh checkout without Phase 3D artifacts fails rather than
downloading pages or loading a model. The generated packet contains full saved article
text: do not publish/share it beyond the authorised review without permission.

1. Enter your name or reviewer ID. Tick the independent-human statement when it is true.
2. Filter by task or review status. Each item shows the task criterion, source/target
   titles and saved URLs, full article text on expansion, supporting passages and
   recorded existing-link status. Question-based tasks explicitly have no source article.
3. Choose **Useful**, **Not useful** or **Unsure**. Reasons are optional. Nothing is
   selected initially; Next unreviewed moves to the next item. A selected item remains
   visible long enough to add a reason before moving on, even in the Unreviewed filter.
4. Make your decision before opening optional AI notes. Those notes remain separate,
   never fill your answer, and disclosure is recorded in the CSV. Unknown AI overlap
   labels are explicitly unlabelled, not invented. Method/rank/score details are optional.
5. Click **Export review CSV**. Export includes all 59 items, including unresolved ones.

For related articles, Useful means relevant to the source question/task. For internal
links, Useful means an appropriate additional destination for the source article and
criterion. Existing links refer only to the saved selected collection, not a live check.
For overlap, Useful means a pair worth investigating for substantive overlap, not
permission to merge/delete or a confirmed duplicate label.

Drafts are saved in this browser's local storage when supported. Export for reliable
backup or transfer, and use **Resume from CSV** in another browser. Draft storage is not
the application's visitor workspace and has no automatic expiry. Clear this browser
draft asks for confirmation; it does not delete downloaded CSVs. One reviewer per file.
Do not manually change packet/version/item/source/target columns. Optional free-text
fields beginning with spreadsheet formula characters are prefixed with an apostrophe
on export for spreadsheet safety; reasons, quotes and newlines otherwise round-trip.

## Submit and calculate metrics

Send the exported CSV to the person coordinating the review (or attach it in this chat).
The packet does not upload anything. Alternatively save a copy as
`runtime/phase3e/completed-review.csv` and run:

```powershell
.\.venv\Scripts\python.exe -B scripts\score_phase3e.py --reviews runtime\phase3e\completed-review.csv --output runtime\phase3e\human-metrics.json
```

Use a new output filename for subsequent runs: existing metrics files are never
overwritten. No MiniLM, tokenizer, database import or website request is needed.
The scorer uses tracked `packet-registry.json`, which contains only frozen task/ranking
identifiers and fingerprints, not AI relevance decisions or original article bodies.

- Useful = positive; Not useful = negative. **Unsure and Unreviewed remain unresolved**.
- P@3/P@5 is available only when every result in that cutoff has a resolved human
  decision and the original ranking supplies enough results. Missing rows are unreviewed.
- Example: Useful/Not useful/Useful gives P@3=2/3. Replacing one decision with Unsure
  makes that metric unavailable; it is not silently counted as negative.
- Related and internal-link means are separate. `all_case_mean` remains unavailable
  until every case in that group is complete. `completed_case_mean` includes an explicit
  completed/total count and must not be presented as a complete-set comparison.
- Overlap P@3/P@5 is separate **usefulness of investigation flags**, not duplicate or
  merge accuracy. It is not pooled into article/link means.
- A reviewer name and human-independence attestation are required for scored decisions.
  Identity/independence is self-reported, not externally authenticated. AI-label exposure
  is reported; the presence of hidden notes is not a claim of a formally blinded study.
- CSV/schema/fingerprint/source-target mismatches, duplicate rows, mixed reviewer names
  and malformed values are rejected. A failed browser import preserves the current draft.

No actual independent human labels have been submitted during preparation. Automated
test CSVs under runtime/phase3e are explicitly synthetic and are not evaluation evidence.
Human disagreements/adjudication and multiple-reviewer aggregation remain a later step.

## Targeted verification only

```powershell
.\.venv\Scripts\python.exe -B scripts\verify_phase3e.py
```

This runs only the review-tool tests and offline browser export/resume checks, using
synthetic decisions, not the application/full suite or model inference. Details and
preservation evidence are in `docs/phase3e-verification.json`. The original Phase 3D
provisional metrics are unchanged; Phase 3E human results remain pending.
