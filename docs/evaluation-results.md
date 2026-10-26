# Retrieval development evaluation

Compared 5 questions across all 21 fictional articles.

Labels are assistant-proposed judgements under strict direct-answer rules. The questions revisit familiar development tasks, and the collection includes an article constructed after earlier retrieval inspection. This is not an independent held-out benchmark.

Both methods receive the same titles, bodies and questions. TF-IDF uses default TfidfVectorizer settings fitted on the 21 article texts only. Embeddings use sentence-transformers/all-MiniLM-L6-v2 on CPU; its exact model revision is not pinned.

## Mean metrics across questions

Each question has equal weight (macro average). Recall excludes questions with no relevant articles; precision includes them. This set has at least one relevant article per question.

| Method | K | Mean precision | Mean recall |
| --- | --- | --- | --- |
| Embeddings | 1 | 100.0% | 74.0% |
| Embeddings | 3 | 53.3% | 92.0% |
| Embeddings | 5 | 40.0% | 100.0% |
| TF-IDF | 1 | 100.0% | 74.0% |
| TF-IDF | 3 | 53.3% | 92.0% |
| TF-IDF | 5 | 36.0% | 96.0% |

## Per-question metrics

| Query | Method | K | Precision | Recall |
| --- | --- | --- | --- | --- |
| Q05 | Embeddings | 1 | 100.0% | 100.0% |
| Q05 | Embeddings | 3 | 33.3% | 100.0% |
| Q05 | Embeddings | 5 | 20.0% | 100.0% |
| Q06 | Embeddings | 1 | 100.0% | 50.0% |
| Q06 | Embeddings | 3 | 66.7% | 100.0% |
| Q06 | Embeddings | 5 | 40.0% | 100.0% |
| Q07 | Embeddings | 1 | 100.0% | 100.0% |
| Q07 | Embeddings | 3 | 33.3% | 100.0% |
| Q07 | Embeddings | 5 | 20.0% | 100.0% |
| Q08 | Embeddings | 1 | 100.0% | 20.0% |
| Q08 | Embeddings | 3 | 100.0% | 60.0% |
| Q08 | Embeddings | 5 | 100.0% | 100.0% |
| Q09 | Embeddings | 1 | 100.0% | 100.0% |
| Q09 | Embeddings | 3 | 33.3% | 100.0% |
| Q09 | Embeddings | 5 | 20.0% | 100.0% |
| Q05 | TF-IDF | 1 | 100.0% | 100.0% |
| Q05 | TF-IDF | 3 | 33.3% | 100.0% |
| Q05 | TF-IDF | 5 | 20.0% | 100.0% |
| Q06 | TF-IDF | 1 | 100.0% | 50.0% |
| Q06 | TF-IDF | 3 | 66.7% | 100.0% |
| Q06 | TF-IDF | 5 | 40.0% | 100.0% |
| Q07 | TF-IDF | 1 | 100.0% | 100.0% |
| Q07 | TF-IDF | 3 | 33.3% | 100.0% |
| Q07 | TF-IDF | 5 | 20.0% | 100.0% |
| Q08 | TF-IDF | 1 | 100.0% | 20.0% |
| Q08 | TF-IDF | 3 | 100.0% | 60.0% |
| Q08 | TF-IDF | 5 | 80.0% | 80.0% |
| Q09 | TF-IDF | 1 | 100.0% | 100.0% |
| Q09 | TF-IDF | 3 | 33.3% | 100.0% |
| Q09 | TF-IDF | 5 | 20.0% | 100.0% |

## Irrelevant articles in the top three

### Q05: How can I arrange the espresso preparation area so cafe staff can work efficiently?

- Embeddings: #2 A08: Choosing an espresso machine for a small cafe; #3 A09: Selecting a coffee grinder for espresso.
- TF-IDF: #2 A08: Choosing an espresso machine for a small cafe; #3 A16: Planning a bakery production schedule.

### Q06: How should I clean the glass and shelves of a refrigerated display cabinet?

- Embeddings: #3 A03: Open versus closed refrigerated displays.
- TF-IDF: #3 A01: Choosing a display fridge for a cafe.

### Q07: Why does bread dough expand while it rests before baking?

- Embeddings: #2 A15: Keeping pastry layers light and crisp; #3 A16: Planning a bakery production schedule.
- TF-IDF: #2 A15: Keeping pastry layers light and crisp; #3 A19: Reviewing two articles about the same topic.

### Q08: What should I compare when buying a refrigerated display cabinet for cakes and drinks in a cafe?

- Embeddings: none in the top three.
- TF-IDF: none in the top three.

### Q09: What should I consider before buying an espresso machine for a small cafe?

- Embeddings: #2 A12: Planning a cafe coffee station; #3 A09: Selecting a coffee grinder for espresso.
- TF-IDF: #2 A09: Selecting a coffee grinder for espresso; #3 A01: Choosing a display fridge for a cafe.

## Interpretation and next step

A fixed top-K can include irrelevant results when fewer than K articles answer the question. Inspect the saved rankings and label reasons rather than assuming a high score is a useful match. These metrics describe this labelled development set only; they do not establish a production winner.

Next: have a person review disputed labels, then add independently labelled questions that remain unseen while tuning. Do not fine-tune or choose a score threshold from this report alone.
