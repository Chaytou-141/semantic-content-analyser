# Phase 3D: real-content evaluation and release gaps

29 October 2026, Australia/Sydney. Baseline `34b613d`. Local commit subject:
`Evaluate saved real content and document release gaps`.
Resolve with `git log -1 --format=%H --grep="Evaluate saved real content and document release gaps"`.

## Scope and evidence

Thirty authorised Freeze Edge articles were reused from Phase 3C's exact saved snapshot:
232,919 title/body characters, 275 passages, pinned 384-dimensional MiniLM plus unchanged
TF-IDF. No page was refetched and no historical benchmark rerun. Model access used
local cached files/offline flags; connect/DNS guards recorded zero network attempts.
The existing CollectionService admitted the collection into a new disposable SQLite
file under ignored runtime/phase3d, never the saved development database.

This phase adds offline evaluation scripts, review artifacts and documentation. There
are **no application, security-boundary, extraction, ranking, UI or infrastructure changes**.
Full source bodies and scored evidence stay local; portable results contain metadata,
counts, hashes, scores and explicit provisional judgements.

## Extraction review

An independent HTMLParser reference view was compared with the saved bodies. It does
not call the production extractor/hidden/text routines. The reader packet shows source
entry-content text beside saved text for human review.

| Check across 30 saved articles | Observation |
| --- | --- |
| Title matches a source H1 | 30/30 |
| Canonical matches source canonical | 30/30 |
| Body heading differences | None detected |
| Selected internal-link mapping differences | None detected; all 37 links remain mapped |
| Missing word occurrences | One per page: Contents from a role=navigation table of contents |
| Additional word occurrences | None detected |
| Source pages with two H1 elements | 5; source-authored structure, not an extraction-created heading |
| Contact/promotion text signal | 24 pages; heuristic signal, not 24 proven errors |

The Contents omission is intentional navigation removal, not missing article prose.
Word-count/heading comparisons cannot prove semantic completeness, correct order,
image/diagram coverage or faithful browser rendering. Five source examples cover
dimensions, glazing, basket/divider comparison, static sushi cooling and finance intent.
In-body calls to action, supplier promotion and generic buying advice remain visible.
Removing all contact/promotion text would also remove legitimate article context, so
no speculative boilerplate rule was added. Human review remains necessary.

Metadata and exact counts: `evaluations/phase3d/results.json`, `review-notes.json`.
Human packet: `runtime/phase3d/editorial-review.html`. No raw HTML is executed and no
external page resources are embedded in that packet.

## Editorial protocol and measured metrics

Four related-content questions and three source-specific internal-link tasks were
defined from the saved corpus before inference. Each has explicit yes/no judgements
for all 30 articles: **210 assistant-provisional labels**, plus four provisional
pre-ranking overlap relationships. Seven task definitions, criteria, reasons and the
frozen input/label SHA-256 are tracked in `evaluations/phase3d/editorial-review-set.json`.

These labels were not supplied or independently reviewed by a person. The same assistant
designed the tasks from one topical site: selection bias, ambiguous scope and correlated
articles limit interpretation. The results are development diagnostics, not accuracy
claims. Independent metrics remain unavailable; **independent judgements = 0**.

| Task group / method | Provisional mean P@3 | Provisional mean P@5 |
| --- | ---: | ---: |
| Related content, MiniLM (4 tasks) | 83.3% | 75.0% |
| Related content, TF-IDF (4 tasks) | 83.3% | 75.0% |
| Internal links, MiniLM (3 tasks) | 55.6% | 40.0% |
| Internal links, TF-IDF (3 tasks) | 55.6% | 40.0% |

The identical group values reflect identical counts of provisionally relevant results
at these cutoffs, not identical rankings or evidence that the methods perform equally
on general websites. P@k divides relevant top-k items by k; comparisons use complete
labels for each inspected result. R04 has only two positive articles, both found at
ranks 1–2 by both methods; its ceilings are P@3=66.7%, P@5=40%. Low P@5 there cannot
be interpreted as failure to find a third positive article that does not exist in the labels.

Label challenges are preserved rather than silently corrected after seeing rankings:
R01 provisionally excludes the ice-build-up page, but its load-line guidance may satisfy
the broad loading criterion. Marking that one result relevant would change MiniLM R01
P@3 from 2/3 to 1 and P@5 from 3/5 to 4/5, while leaving TF-IDF's inspected top five
unchanged. R04's positive sushi-model overview is contextual rather than necessarily
answering why no fan is used. Human adjudication can therefore change conclusions;
neither method is selected as the winner from this evidence.
The negative upright-fridge link judgement in L02 is also contestable because another
section includes fan/ventilation checks. A useful destination may be poorly represented
by its winning passage. Frozen negative labels are not objective proof of bad suggestions.

## Recommendation and overlap examples

- Chest basket/divider recommendations found organisation, loading and configuration
  articles. Both methods' top five contain four provisionally useful additions.
- From the running-cost article, MiniLM suggests a generic upright-cabinet article at
  rank 2 with 0.82363 similarity. Its matching buying checklist is thematically close
  but does not directly satisfy the frozen task's energy/load criterion. High scores
  are not editorial confidence or proof of a useful new link.
- From static/no-fan sushi guidance, TF-IDF rank 2 is generic internal-fan stocking
  guidance (0.33587). It shares words while addressing a different cabinet design.
  MiniLM rank 2 instead matches an open-display costs article via temperature-monitoring
  language (0.64323). Both require source-specific judgement before linking.
- Triple-glazed freezer articles have the highest inspected overlap (MiniLM 0.93711,
  TF-IDF 0.58155): a substantive overlap candidate, not an automatic merge decision.
- Supplier promotion versus finance/payment content scores 0.86721 / 0.57169 from shared
  product-range/contact passages despite different primary intent. This exposes the
  existing maximum-passage scorer's sensitivity to generic commercial content.

Overlap inspection deliberately requested each method's top ten at threshold zero,
not a validated duplicate threshold. The highest TF-IDF overlap is below the UI's
default 0.65, so that default would return no TF-IDF overlap pairs on this sample.
Method-specific calibration remains needed; scores are neither comparable probabilities
nor independently labelled duplicate detection. No thresholds/formulas were changed.

The blind review packet, 44-row top-five-union worksheet and 15-pair overlap worksheet
allow a small human review round. The full 210-row worksheet is also supplied. Rankings
are collapsed until the reviewer chooses to inspect them. Worksheet decisions have not
been ingested or claimed as reviewed labels in this phase.

## Real model and test evidence

Exactly **one** real MiniLM construction was used. Existing index/embedding reuse covered
all seven tasks, both methods and the overlap inspections. Embedding shape: **(275, 384)**.
Admission took **0.562 seconds**; admission plus analysis/evidence checks took
**9.278 seconds wall / 17.734 seconds process CPU** with two PyTorch threads, excluding
earlier dependency imports. CPU can exceed wall time because threads run concurrently.
This is one local evaluation observation, not a latency SLA or new historical benchmark.

**140** source/target passage references were checked as exact source substrings, and
link results respected self/existing-link exclusions. Metrics can be rescored from
cached rankings without loading the model; the human packet was regenerated from those
cached results when overlap sections were added.

Milestone suite: see `docs/phase3d-verification.json` for the final actual counts and skip.
The suite completed with **237 passed, 1 skipped in 30.68 seconds**; the skip needs
Windows symlink privileges. **1,081 protected files** were unchanged, including the
saved source corpus, development databases and historical evidence.
The suite runs once via `scripts/verify_phase3d.py` and does not repeat inference. New
focused tests cover denominators, missing labels/results, provenance, invalid inputs
and independent extraction-audit differences. Existing security/isolation/admission
tests remain in the full suite. Production source and earlier artifacts are hash/Git
checked for preservation. No packages, paid APIs, deployment or push were used.

## Compatibility and next step

This remains one authorised WordPress site. Phase 3C's sitemap endpoints returned 404;
successful real XML URL-set/index discovery and an independent non-WordPress platform
remain unvalidated. Local XML fixtures do not close that gap. Cross-host/www redirects,
JS-only content, non-UTF-8 HTML, gzip sitemap files, ambiguous layouts and authenticated
content retain the documented limitations; no bypass was introduced.

See `docs/release-readiness.md` for the concrete public-release checklist. Next: human
adjudication of the 44 retrieved candidates/15 overlap pairs, a functioning authorised
sitemap/non-WordPress sample, then narrowly scoped public deployment configuration and
abuse/egress/capacity work. No broad fine-tuning or ranking change is justified by these
small provisional metrics. The application is not declared ready for public users.
