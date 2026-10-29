# Phase 3D editorial development review

This is a single-site, assistant-provisional evaluation of the **saved** authorised
Freeze Edge collection. It is not a held-out benchmark, independently reviewed labels,
or evidence of general SEO recommendation accuracy. No weights/ranking were changed.

- `editorial-review-set.json`: frozen input fingerprint, 30 article IDs/URLs/body hashes,
  four related-content tasks, three internal-link tasks and 210 explicit provisional
  judgements with reasons. These labels were written before inspecting Phase 3D rankings.
- `independent-review-template.csv`: blank full-corpus worksheet (210 rows).
- `top5-independent-review-template.csv`: blank union of both methods' top-five results,
  sorted by ID rather than rank (44 rows). Enough to adjudicate P@3/P@5, not recall.
- `overlap-independent-review-template.csv`: blank worksheet for 15 pairs from the union
  of the inspected top-ten overlap lists. Relationship categories need human judgement;
  similarity is not a duplicate/merge label.
- `review-notes.json`: exploratory false positives, overlap examples, source spot checks
  and challenges to frozen provisional labels. These notes were written after viewing
  scores and do not silently revise the primary metrics.
- `results.json`: measured metrics, ranking IDs/scores/passage hashes and extraction audit
  counts. Source article text and full scored passages are deliberately not redistributed.

Human-readable packet: `runtime/phase3d/editorial-review.html`. It shows inert saved
source text beside extracted text, task criteria, and collapsed model/overlap evidence.
Review source/tasks before opening rankings. Worksheets contain no assistant decisions.
No completed independent worksheet was received: **independently reviewed labels = 0**.

Reproduce locally from the existing authorised cache:

```powershell
# One offline model construction; new disposable SQLite, never the development DB:
.\.venv\Scripts\python.exe -B scripts\evaluate_phase3d.py
# Recompute scores from frozen labels/cached rankings without a model load:
.\.venv\Scripts\python.exe -B scripts\score_phase3d.py
# Full automated suite and preservation checks; does not rerun inference:
.\.venv\Scripts\python.exe -B scripts\verify_phase3d.py
```

The first command requires `runtime/phase3c/corrected30/prepared.json`, its saved
response files and the exact cached pinned MiniLM revision. Input/label hashes are
checked. Missing source/model caches fail; no refetch/download fallback is provided.
The corpus is not part of a fresh Git checkout, so this is reproducible with the frozen
authorised local artifacts, not a self-contained public dataset. Do not publish original
page bodies without appropriate permission. Completed human worksheets must be checked
and versioned as a distinct review round; this phase has no automated human-label import.

P@k = relevant reviewed results / k. Missing labels, fewer than k returned results or
insufficient provenance yield unavailable metrics rather than invented negative labels
or independent accuracy. Group summaries average four related tasks and three link
tasks separately. R04 has only two positive labels, so its maximum P@3/P@5 is 2/3 and
2/5. Both methods found those two in their first two results.

See `docs/phase3d-real-content-evaluation.md` and `docs/release-readiness.md` for findings,
label sensitivity and remaining release work. Earlier learning/benchmark data is unchanged.
