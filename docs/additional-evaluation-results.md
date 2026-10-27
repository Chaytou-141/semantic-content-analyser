# Retrieval development evaluation

Compared 2 questions across all 21 fictional articles.

Labels are assistant-proposed judgements under strict direct-answer rules. Both questions and labels were prepared by the assistant before their rankings were run. The collection is familiar and includes an article constructed after earlier retrieval inspection. Even files named test_queries and test_relevance do not make this an independent human-reviewed held-out benchmark.

Question source: `data/test_queries.csv`. Label source: `labels/test_relevance.csv`.

Both methods receive the same titles, bodies and questions. TF-IDF uses default TfidfVectorizer settings fitted on the 21 article texts only. Embeddings use sentence-transformers/all-MiniLM-L6-v2 on CPU; its exact model revision is not pinned.

## Mean metrics across questions

Each question has equal weight (macro average). Recall excludes questions with no relevant articles; precision includes them. This set has at least one relevant article per question.

| Method | K | Mean precision | Mean recall |
| --- | --- | --- | --- |
| Embeddings | 1 | 100.0% | 100.0% |
| Embeddings | 3 | 33.3% | 100.0% |
| Embeddings | 5 | 20.0% | 100.0% |
| TF-IDF | 1 | 100.0% | 100.0% |
| TF-IDF | 3 | 33.3% | 100.0% |
| TF-IDF | 5 | 20.0% | 100.0% |

## Per-question metrics

| Query | Method | K | Precision | Recall |
| --- | --- | --- | --- | --- |
| T01 | Embeddings | 1 | 100.0% | 100.0% |
| T01 | Embeddings | 3 | 33.3% | 100.0% |
| T01 | Embeddings | 5 | 20.0% | 100.0% |
| T02 | Embeddings | 1 | 100.0% | 100.0% |
| T02 | Embeddings | 3 | 33.3% | 100.0% |
| T02 | Embeddings | 5 | 20.0% | 100.0% |
| T01 | TF-IDF | 1 | 100.0% | 100.0% |
| T01 | TF-IDF | 3 | 33.3% | 100.0% |
| T01 | TF-IDF | 5 | 20.0% | 100.0% |
| T02 | TF-IDF | 1 | 100.0% | 100.0% |
| T02 | TF-IDF | 3 | 33.3% | 100.0% |
| T02 | TF-IDF | 5 | 20.0% | 100.0% |

## Irrelevant articles in the top three

### T01: What information should our cafe website show so visitors can find us and know when we are open?

- Embeddings: #2 A01: Choosing a display fridge for a cafe; #3 A04: Measuring space for a cafe display refrigerator.
- TF-IDF: #2 A03: Open versus closed refrigerated displays; #3 A16: Planning a bakery production schedule.

### T02: How can a baker preserve the separate layers in pastry before baking?

- Embeddings: #2 A16: Planning a bakery production schedule; #3 A21: Cleaning a refrigerated bakery display cabinet.
- TF-IDF: #2 A06: Cleaning a commercial display fridge; #3 A19: Reviewing two articles about the same topic.

## Interpretation and next step

A fixed top-K can include irrelevant results when fewer than K articles answer the question. Inspect the saved rankings and label reasons rather than assuming a high score is a useful match. These metrics describe this labelled development set only; they do not establish a production winner.

Next: have a person review disputed labels, then add independently labelled questions that remain unseen while tuning. Do not fine-tune or choose a score threshold from this report alone.
