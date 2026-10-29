# Phase 3F — Evaluation consolidation and error analysis

29 October 2026 (Australia/Sydney). Baseline `5453900`; frozen inference `771c4cb`.
Local commit subject: **Consolidate screened editorial reviews and document evaluation gaps**.
No application, ranking, security, model, network or infrastructure changes.

## Inputs and validation

The two files supplied from Downloads are preserved byte-for-byte under
`evaluations/phase3f/inputs/`. Their SHA-256 values and the original registry,
manifest and portable rankings are recorded in `evaluations/phase3f/results.json`.
The originals were not edited. CSV reasons are evidence data, not instructions.

`scripts/phase3f_evaluation.py:load_csv` validates exact columns, packet/version,
known/unique item IDs, item type, original case/source/target IDs, supported decisions,
boolean values, reviewer/reason bounds and provenance enums. Unknown or missing columns
are rejected rather than inferred. `validate_frozen` cross-checks every case and ordered
ranking against Phase 3D results/manifest, and every overlap ID against its actual pair.
`reconcile` requires complete mixed-packet coverage and exact equality of every original
user field, including reason, identity, attestation and disclosure, across both files.

Both inputs pass these checks: 14 original user rows are preserved in the 59-row mixed
file; the remaining 45 rows are explicitly AI-assisted. No conflicting reconciliation,
unknown article/case or ranking identity mismatch was found. Current independent-human
attestations are **false in every row**. The user source explicitly says decisions were
communicated in chat, after AI screening; this is reported provenance, not identity
authentication or an independently audited transcript.

Compatibility findings are intentional, not errors to repair in the data:

- The user file has Phase 3E's standard columns, but its decisions cannot pass the
  independent-attestation requirement in the original scorer.
- The mixed file adds `review_origin`, includes different reviewers and is incompatible
  with Phase 3E's single-independent-reviewer schema. Do not remove that column or change
  attestations to make the old scorer accept it.
- Phase 3F uses a separate evaluator for this explicit mixed schema. The Phase 3E
  independent-review scorer remains unchanged. False `provisional_revealed` flags do
  not establish blindness when provenance itself records AI screening.

## Human-label coverage and available metrics

| Review type | All items | User-provided | AI-assisted |
| --- | ---: | ---: | ---: |
| Related/internal-link candidates | 44 | 8 (18.2%) | 36 |
| Overlap investigation pairs | 15 | 6 (40%) | 9 |
| Total | 59 | 14 (23.7%) | 45 |

The user decisions are seven Useful and seven Not useful: candidates have two Useful /
six Not useful; overlaps have five Useful / one Not useful. These are descriptive counts,
not precision denominators. The combined 29 Useful / 30 Not useful are not ground truth.
The 22 negative candidate judgements consist of six user decisions and 16 AI assessments;
the eight negative overlaps consist of one user decision and seven AI assessments.

`cutoff` and `consolidate` keep two scopes: user-only screened judgements (not independent)
and user judgements with independent attestation (also only self-reported). AI labels are
ineligible for either scope. A metric needs all k items resolved as Useful/Not useful;
Unsure, missing, AI-only and ineligible rows remain unresolved, never counted as negatives.

| Task | MiniLM user coverage @3 / @5 | TF-IDF user coverage @3 / @5 |
| --- | --- | --- |
| R01 | 0/3; 1/5 | 1/3; 1/5 |
| R02 | 0/3; 0/5 | 0/3; 1/5 |
| R03 | 0/3; 1/5 | 1/3; 1/5 |
| R04 | 0/3; 1/5 | 0/3; 1/5 |
| L01 | 0/3; 1/5 | 0/3; 0/5 |
| L02 | 0/3; 1/5 | 1/3; 1/5 |
| L03 | 1/3; 1/5 | 1/3; 1/5 |

**MiniLM P@3/P@5: unavailable. TF-IDF P@3/P@5: unavailable.** Zero of 28
case/method/cutoff combinations is fully user-labelled, even before requiring independent
attestation. There are zero independently attested user decisions. No group averages,
mixed-label precision or method superiority claims are calculated. Overlap top-3/top-5
user coverage is also incomplete; overlap usefulness is not duplicate/merge accuracy.
All individual gaps are listed in `results.json` as `unresolved_item_ids`.

Phase 3D's earlier assistant-provisional numbers remain unchanged and explicitly
provisional. They must not be reused as Phase 3F human evaluation scores.

## Disagreements and error analysis

`results.json:ranking_disagreements` compares frozen orders, without reranking.
Top-five sets share three or four destinations per task; none has identical top-five
ordering. R04's top three have identical ordering; other top-three orders differ.
For example R01 top-three sets share only one destination. Different candidate sets and
incomplete human labels prevent a defensible method-level comparison.

`evaluations/phase3f/error-analysis.json` contains **12 curated negative examples**:
seven user-derived (all six negative candidates and the one negative overlap), five
AI-assisted. Taxonomy and interpretation are assistant annotations, not new human labels.
Each carries article IDs/titles, original label provenance, method/rank/score and exact
saved passage hashes. They are a selected diagnostic subset, not a frequency estimate.

| Pattern | Observations and provenance | Limit on interpretation |
| --- | --- | --- |
| Search-intent mismatch | User rejects general buying/features pages in R01/R02 and self-service guidance in L02; user rejects O03 as an overlap flag despite MiniLM 0.91009 / TF-IDF 0.52570 | Related content, a helpful contextual link and substantive overlap are different editorial tasks |
| Topic / technical-application mismatch | User rejects forced-air stocking guidance for static/no-fan sushi in R04 and L03; L03 appears at MiniLM rank 3 / TF-IDF rank 2 | Shared vocabulary does not imply technically transferable advice |
| Generic buying/promotion text | AI-assisted L02 upright checklist at MiniLM rank 2 (0.82363); supplier/finance overlap O15 at MiniLM rank 8 (0.86721) / TF-IDF rank 2 (0.57169) | No independent confirmation or causal ablation; overlapping commercial copy is a plausible contributor, not a proven universal defect |

Two positive counterexamples constrain overbroad fixes. The user rejects destination
`Wc8d0057aff79b0bf` for R01 but accepts it for the contextual L01 link. In R03 the user
rejects one freezer-glazing article but accepts another despite both having a freezer
focus. A title keyword blacklist, blanket commercial-text deletion or coarse equipment
category filter would risk removing useful recommendations.

Source mechanics are unchanged: `semantic_analyser/engine.py:search` selects each
article's maximum query-to-passage match (lines 121–132); `links` chooses the highest
source/target passage match after self/existing-link exclusion (134–164); `overlaps`
uses the maximum passage-pair match (166–191). Broad checklists and reused commercial
sections can therefore dominate an article-level result. Scores are not editorial
confidence. This explains a mechanism consistent with examples, not measured causality.

## Does the evidence justify a ranking change?

It justifies a **targeted future experiment**, not a deployed formula/threshold change,
fine-tuning, a method winner or a claimed precision improvement. The simplest proposal
is an offline comparison of current maximum-passage evidence with candidate scoring that
reduces influence of near-repeated supplier/CTA passages while retaining original text
and passage offsets. Test whole-article/intent consistency as a separate experiment;
do not combine multiple interventions before attribution is possible.

Expected benefit: fewer high-scoring matches based only on reusable commercial sections.
Risks: legitimate supplier/finance intent, helpful generic contextual links and short
articles may be penalised; repeated safety guidance may be genuinely relevant. A single
site and selection of contentious cases invite overfitting. No benefit has been measured.

Before that experiment, obtain independently authored complete labels for the union of
both methods' top five in the same tasks, clarify contextual-link versus direct-answer
criteria, and reserve additional authorised examples for a later evaluation. Require
paired complete-case P@3/P@5, retained positive controls, no cross-task blacklist, unchanged
security/admission boundaries and explicit rejection of any regression before adoption.
Treat overlap-investigation usefulness separately from actual duplicate adjudication.

## Reproduce and verification

From the repository root (no model or private corpus needed for scoring):

```powershell
.\.venv\Scripts\python.exe -B -m scripts.phase3f_evaluation --output runtime\phase3f\reproduced-metrics.json
.\.venv\Scripts\python.exe -B -m pytest -q tests/test_phase3f_evaluation.py tests/test_phase3e_review.py
```

The runtime output parent must exist; use a new output filename each time. Default inputs
are the tracked, byte-preserved CSVs. `--users` / `--mixed` accept alternate explicit
paths; incompatible files fail rather than being normalised. Existing output is never
overwritten. An available private Phase 3D ranking cache is additionally hash-checked;
its absence causes no network/model fallback and does not alter metrics.

Final targeted counts/timing and preservation checks are recorded in
`docs/phase3f-verification.json`. The test suite uses clearly synthetic decisions for
arithmetic edge cases; these are not evaluation labels. No full application/historical
suite, browser checks, inference or website requests were justified by offline changes.
Original application/UI, SQLite/development data, historical benchmarks and Phase 3D/3E
evidence remain unchanged. This phase establishes no new extraction/platform validation,
public load limits or production readiness; see `docs/release-readiness.md`.
