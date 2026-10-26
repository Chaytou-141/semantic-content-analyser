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
