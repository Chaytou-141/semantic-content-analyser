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
