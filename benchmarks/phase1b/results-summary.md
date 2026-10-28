# Phase 1B measured results

Application commit: `8e2c99198d42a05696b0b362ef851c1c8932e559`.

All times are local Windows measurements with a cached, offline real model. See README.md for methodology and limitations. No production defaults changed.

## Capacity

| Scenario | Characters | Passages | Import accepted? |
| --- | ---: | ---: | --- |
| 30 articles | 198,653 | 225 | yes |
| 36 articles | 238,142 | 269 | yes |
| 40 articles | 268,013 | 302 | no: character limit |
| 36 articles, length ×1.25 | 297,257 | 337 | no: character limit |
| 36 articles, length ×1.5 | 356,393 | 402 | no: character limit |
| 36 articles, length ×2.0 | 474,663 | 531 | no: character limit |

The 40-article scenario uses four duplicated length fixtures with new IDs. Length multipliers duplicate prose for capacity only; neither is quality data.

All 269 original passages retain exact body offsets and final article tokens. Maximum encoded title/body input: 206 tokens (limit 256).

## Cold stages

Wall/CPU seconds; one fresh subprocess per profile. Collection tokenization diagnostic is timed separately and excluded from the reconstructed first-use total.

| Articles | Method | Imports wall/CPU | Model load wall/CPU | Prepare wall/CPU | Encode wall/CPU | First use total wall/CPU |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 30 | tfidf | 2.504/2.469 | 5.563/5.484 | 0.091/0.078 | not needed | 8.160/8.031 |
| 30 | embeddings | 2.408/2.359 | 5.450/5.438 | 0.093/0.078 | 6.854/13.688 | 14.817/21.562 |
| 36 | tfidf | 2.431/2.375 | 5.480/5.422 | 0.114/0.109 | not needed | 8.027/7.906 |
| 36 | embeddings | 2.408/2.359 | 5.472/5.484 | 0.105/0.094 | 7.989/16.016 | 15.983/23.984 |

The total is a sum of measured stages, not an independently timed HTTP request. Model load includes lazy Sentence Transformers imports. A first HTTP comparison on the 36-article collection, with model already loaded by UI checks but index cold, reported 7,901 ms.

## Warm operations

Median wall/CPU milliseconds. Search n=5; links/overlap n=3. Zero CPU measurements reflect timer granularity, not free computation.

| Articles | Method | Search wall/CPU | Links wall/CPU | Overlap wall/CPU |
| ---: | --- | ---: | ---: | ---: |
| 30 | tfidf | 1.466/0.000 | 2.924/0.000 | 11.147/0.000 |
| 30 | embeddings | 9.362/15.625 | 1.227/0.000 | 9.346/15.625 |
| 36 | tfidf | 1.816/0.000 | 4.037/0.000 | 15.947/15.625 |
| 36 | embeddings | 9.756/31.250 | 1.339/0.000 | 13.344/31.250 |

Raw JSON retains all individual samples; small n does not support p95/p99 claims.

## Process memory

MiB (1,048,576 bytes). Baseline includes measured cold/warm operations and matrix diagnostics, before the additional planted-paragraph probes.

| Articles | Method | OS peak working set | Current working set | Current private bytes | OS peak commit |
| ---: | --- | ---: | ---: | ---: | ---: |
| 30 | tfidf | 494.4 | 494.4 | 555.4 | 592.6 |
| 30 | embeddings | 690.1 | 647.4 | 774.0 | 797.7 |
| 36 | tfidf | 494.0 | 494.0 | 554.8 | 592.4 |
| 36 | embeddings | 690.0 | 603.9 | 701.0 | 798.2 |

Including the additional probes, the largest OS process peak was 697.1 MiB. These are per-process readings, not total system RAM or multi-visitor deployment sizing. TF-IDF still loads the model because the current passage splitter uses its tokenizer.

## Same-score matrix diagnostic

No production optimization was applied.

| Articles | Method | Full entries/bytes | Source-only entries/bytes | Full ms | Source-only ms | Equivalent? |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 30 | tfidf | 50,625/405,000 | 1,125/9,000 | 2.319 | 0.874 | True |
| 30 | embeddings | 50,625/202,500 | 1,125/4,500 | 0.253 | 0.064 | True |
| 36 | tfidf | 72,361/578,888 | 1,345/10,760 | 2.976 | 0.863 | True |
| 36 | embeddings | 72,361/289,444 | 1,345/5,380 | 0.282 | 0.125 | True |

Matrix timings are single micro-measurements and sensitive to scheduling/cache effects. They establish numerical equivalence and smaller allocation, not a reliable production speedup factor.

## Constructed intent-mismatch probes (36-article profiles)

The same cycling article is evaluated at three prefix lengths, with/without one 39-word espresso paragraph. The original cycling article B24 is replaced, keeping count constant. The query asks about two baristas' espresso layout. No independent human labels are used.

| Method | Words | Planted paragraph? | Passages | Max score | Mean score | Passage fraction ≥0.5 | Rank in top20 |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| tfidf | 174 | False | 2 | 0.0491 | 0.0333 | 0.00 | outside 20 |
| tfidf | 213 | True | 2 | 0.5931 | 0.3180 | 0.50 | 1 |
| tfidf | 787 | False | 6 | 0.0501 | 0.0425 | 0.00 | outside 20 |
| tfidf | 826 | True | 6 | 0.5075 | 0.1145 | 0.17 | 1 |
| tfidf | 1331 | False | 10 | 0.0823 | 0.0475 | 0.00 | 16 |
| tfidf | 1370 | True | 10 | 0.5445 | 0.0934 | 0.10 | 1 |
| embeddings | 174 | False | 2 | 0.1820 | 0.1423 | 0.00 | outside 20 |
| embeddings | 213 | True | 2 | 0.7115 | 0.4467 | 0.50 | 2 |
| embeddings | 787 | False | 6 | 0.2905 | 0.2091 | 0.00 | 13 |
| embeddings | 826 | True | 6 | 0.7285 | 0.2838 | 0.17 | 1 |
| embeddings | 1331 | False | 10 | 0.2905 | 0.1858 | 0.00 | 13 |
| embeddings | 1370 | True | 10 | 0.6598 | 0.2309 | 0.10 | 2 |

Length alone increased the semantic maximum from 0.1820 to 0.2905 in this case, without producing a high-scoring match. Planting one related paragraph moved both methods into the top two despite different whole-article intent. The longest planted case has MiniLM max 0.6598 versus mean 0.2309; TF-IDF max 0.5445 versus mean 0.0934. Scores are not monotonic with length because passage boundaries change and TF-IDF refits. This shows a risk for whole-article/link intent decisions, not a corpus-wide false-positive rate. A relevant passage can be a legitimate result for passage search. Do not replace max scoring with the mean or choose a threshold from this constructed case alone.

## Verification

- Existing pytest suite: 15 passed in 0.93s.
- Existing JavaScript syntax check passed.
- Latest UI browser smoke passed: comparison, links/exclusions/review save, overlap, live filters, shortcut, editor/unsaved guard, evaluation and mobile/import dialog.
- Real MiniLM HTTP search/links/overlap passed against the isolated 36-article collection.
- Real tokenizer: all 269 offsets/tails checked, no combined input above 256 tokens.
- Token-dense collection: import accepted (200), analysis rejected (422, >800 passages). This confirms the current delayed-admission defect in the disposable database only.
- Preservation: 42 original source/data/database files hashed; 0 changed.
- Temporary server stopped; no existing server/database reset; no infrastructure or deployment executed.

The corpus and probes are synthetic. Historical development metrics remain untouched, and this phase does not add an accuracy, recall or production recommendation-quality claim.
