# Learning journal

## Phase 1: Local embeddings and cosine similarity

Date: 26 October 2026

I ran a pretrained Sentence Transformers model locally on my CPU to compare three example sentences, then added a fourth sentence. The model produces an embedding of 384 numbers for each sentence, giving a 4 x 384 embedding matrix and a 4 x 4 similarity matrix for four sentences. Sentences 1, 2, and 4, which discuss selecting refrigeration displays, had higher similarity scores with each other (0.7368, 0.7697, and 0.7689) than with the sentence about cleaning a freezer. I also calculated cosine similarity for [1, 0] and [1, 1], obtaining approximately 0.7071 by dividing their dot product by the product of their lengths. High similarity is a clue to related meaning; recommending an article merge also requires reviewing reader intent and unique information.

### Working environment

- Python: 3.12.1
- sentence-transformers: 6.2.0
- torch: 2.14.1
- transformers: 5.20.2
- Model: sentence-transformers/all-MiniLM-L6-v2
- Device: CPU
- Installed dependency snapshot: ../requirements-lock.txt

### Troubleshooting and limitations

- The saved sentence list initially contained only three items, so the similarity matrix remained 3 x 3. Adding and saving a fourth item produced 4 x 4 scores.
- Leaving `similarity = ...` printed `Ellipsis`. Replacing the placeholder with the formula produced the expected numerical result.
- This was inference with an existing model, not model training.
- Scores are not percentages or proof that articles should be merged.
- The reported model scores came from the terminal output shared during this session. The exact model revision was not recorded, so the dependency snapshot alone does not fully reproduce the model setup.
- Next improvement: record the model revision and test additional sentence pairs with deliberately different reader intents.

## Phase 1: Top-5 article retrieval

Date: 27 October 2026

I embedded the titles and bodies of 20 fictional articles, leaving their IDs and topic labels out of the model input. I selected a source article, calculated cosine similarity against the collection, excluded the source itself and sorted the remaining scores to return five results. For A01, an espresso-machine buying guide appeared fifth at 0.5528: it shared the cafe equipment buying context but concerned different equipment. For A06, a cleaning guide, the original top result was a refrigerator sizing article at 0.6046, showing that the available matches shared equipment rather than the reader's cleaning task. After adding A21 about cleaning a refrigerated bakery display cabinet, it ranked first for A06 at 0.6782 without changing or training the model.

### Verified A06 results after adding A21

The collection now contains 21 articles, producing an embedding matrix of shape (21, 384).

| Rank | ID | Title | Cosine similarity |
| --- | --- | --- | --- |
| 1 | A21 | Cleaning a refrigerated bakery display cabinet | 0.6782 |
| 2 | A04 | Measuring space for a cafe display refrigerator | 0.6046 |
| 3 | A01 | Choosing a display fridge for a cafe | 0.5295 |
| 4 | A05 | Comparing running costs of display fridges | 0.5281 |
| 5 | A03 | Open versus closed refrigerated displays | 0.4979 |

### Lessons and next improvement

- Retrieval quality depends on which articles are available as well as the model. This one constructed example is not a general evaluation of model quality.
- Top-5 returns five candidates even when some do not answer the source article's reader need. Scores are not relevance percentages.
- Adding A21 left the displayed scores for existing pairs unchanged; it supplied a new candidate rather than training the model.
- The terminal's `python` command could not find Sentence Transformers despite showing `(.venv)`. Running the project's `.venv/Scripts/python.exe` explicitly used the project environment successfully.
- Next improvement: record expected matches for more examples before changing the model or choosing a relevance threshold.

## Comparing embeddings with a TF-IDF baseline

I labelled relevant articles for three questions before inspecting the question rankings, then compared embeddings and TF-IDF using the same four candidates per question. Both methods ranked the relevant article first for the display-cabinet cleaning question and the espresso-machine buying question. For the loaf-expansion question, embeddings ranked A14 first at 0.5638, while TF-IDF ranked A13 first at 0.2110 and the relevant A14 second at 0.1895. Across these three exercises, mean Precision@1 was 100% for embeddings and about 66.7% for TF-IDF; Precision@2 was 50% for both methods on every question because each top-two list contained exactly one relevant article. These selected examples illustrate different behaviour, but do not establish which method is best for the full collection or future questions.

- Labels are human reference judgements, not predictions or inputs to either ranking method.
- TF-IDF word weights are fitted on each question's four candidate articles, with the question transformed using that vocabulary.
- Comparing raw similarity scores across methods does not establish retrieval quality.
- These are teaching examples with restricted candidate sets, not an independent held-out benchmark; A21 was constructed after earlier retrieval inspection.
- The automatic Precision@1 and Precision@2 calculations were run and matched the manual counts above.

## Milestone 2 checkpoint: Precision, recall and multiple relevant articles

Date: 27 October 2026

I extended the comparison to four labelled questions and added automatic precision and recall at K = 1, 2 and 3. Precision measures the fraction of displayed results labelled relevant, while recall measures the fraction of all relevant candidates found within that result limit. For Q04 about choosing a cafe display fridge, I marked A01, A03, A04 and A05 relevant within a six-article candidate set before inspecting the rankings. Embeddings returned three relevant articles in its first three results, while TF-IDF returned two relevant articles and an espresso-machine article. This shows how a method can have perfect precision at a chosen result limit while still missing relevant articles beyond that limit.

### Q04 results verified from the learner's terminal output

| Method | Top three IDs | Relevant in top three | Precision@3 | Recall@3 |
| --- | --- | --- | --- | --- |
| Embeddings | A01, A04, A03 | 3 | 3/3 = 100% | 3/4 = 75% |
| TF-IDF | A01, A08, A04 | 2 | 2/3 = 66.7% | 2/4 = 50% |

The script rounds displayed percentages to whole numbers, so TF-IDF Precision@3 appears as 67%.

### Limits and next step

- Q01-Q03 each search four reviewed candidates; Q04 searches six. None searches all 21 articles.
- Both methods use identical article text, questions, labels and result limits within each exercise. TF-IDF is fitted separately on each exercise's candidate articles.
- Labels are human judgements for a defined reader task. They are not fed into the ranking methods and do not train the embedding model.
- These examples are for learning, not a held-out benchmark. They do not prove one method is best for the final product.
- Next: write new questions, review every article in the 21-article collection for each question before inspecting rankings, and evaluate both methods on that shared collection. Record uncertainty and false matches before considering model changes.

## Full-collection development evaluation

I first ran Q05 against all 21 articles, and both methods ranked the relevant A12 first. At my request, the assistant then prepared four more questions and complete relevance judgements before running those rankings, producing 105 assistant-proposed labels across five development questions. The batch script embeds the articles once, fits TF-IDF on the same full collection and writes a report with rankings and precision/recall at 1, 3 and 5. Averaged equally across questions, both methods achieved Precision@1 of 100%, Precision@3 of 53.3% and Recall@3 of 92%; at five results, embeddings achieved precision/recall of 40%/100%, versus 36%/96% for TF-IDF. These familiar synthetic tasks and assistant-proposed labels are a development check, so the next evaluation improvement is independent human review and questions kept separate from tuning.

- Run: `.venv/Scripts/python.exe experiments/batch_evaluation.py`.
- Questions: `data/evaluation_queries.csv`.
- Labels and reasons: `labels/full_collection_relevance.csv`.
- Generated report: `docs/evaluation-results.md`.
- All ranked pairs: `docs/evaluation-rankings.csv`.
