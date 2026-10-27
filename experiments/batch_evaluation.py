"""Compare two retrieval methods on the same fully labelled development queries."""

import argparse
import csv
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

project_root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--additional", action="store_true",
    help="Run the two additional assistant-labelled questions, saving a separate report.",
)
args = parser.parse_args()
query_path = "data/test_queries.csv" if args.additional else "data/evaluation_queries.csv"
label_path = "labels/test_relevance.csv" if args.additional else "labels/full_collection_relevance.csv"
report_prefix = "additional-evaluation" if args.additional else "evaluation"


def read_csv(relative_path):
    with (project_root / relative_path).open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


articles = read_csv("data/synthetic_articles.csv")
queries = read_csv(query_path)
label_rows = read_csv(label_path)
article_ids = {article["id"] for article in articles}
query_ids = {query["query_id"] for query in queries}
if len(article_ids) != len(articles) or len(query_ids) != len(queries):
    raise ValueError("Article and query IDs must be unique.")
if len(articles) < 5:
    raise ValueError("At least five articles are required for evaluation at K=5.")

# Reject missing, extra, duplicate or unresolved labels before loading the model.
labels = {}
for row in label_rows:
    pair = (row["query_id"], row["article_id"])
    if pair in labels or row["relevant"] not in {"yes", "no"}:
        raise ValueError(f"Duplicate or unresolved label: {pair}")
    labels[pair] = row["relevant"] == "yes"
expected_pairs = {(qid, aid) for qid in query_ids for aid in article_ids}
if set(labels) != expected_pairs:
    raise ValueError("Exactly one resolved label is required for every query/article pair.")

article_texts = [article["title"] + ". " + article["body"] for article in articles]
question_texts = [query["question"] for query in queries]

# Encode each article once. Neither retrieval method receives relevance labels.
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
article_embeddings = model.encode(article_texts)
question_embeddings = model.encode(question_texts)
embedding_scores = model.similarity(question_embeddings, article_embeddings).tolist()

vectorizer = TfidfVectorizer()
article_word_vectors = vectorizer.fit_transform(article_texts)
question_word_vectors = vectorizer.transform(question_texts)
tfidf_scores = cosine_similarity(question_word_vectors, article_word_vectors).tolist()

metric_rows = []
ranking_rows = []
for method, score_matrix in [("Embeddings", embedding_scores), ("TF-IDF", tfidf_scores)]:
    for query, scores in zip(queries, score_matrix):
        qid = query["query_id"]
        ranked = sorted(zip(articles, scores), key=lambda item: item[1], reverse=True)
        relevant_total = sum(labels[(qid, aid)] for aid in article_ids)
        for rank, (article, score) in enumerate(ranked, start=1):
            ranking_rows.append({
                "method": method, "query_id": qid, "rank": rank,
                "article_id": article["id"], "title": article["title"],
                "similarity": score, "relevant": labels[(qid, article["id"])],
            })
        for k in (1, 3, 5):
            found = sum(labels[(qid, article["id"])] for article, score in ranked[:k])
            metric_rows.append({
                "method": method, "query_id": qid, "k": k,
                "precision": found / k,
                "recall": found / relevant_total if relevant_total else None,
            })

output_dir = project_root / "docs"
output_dir.mkdir(exist_ok=True)
with (output_dir / f"{report_prefix}-rankings.csv").open("w", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=list(ranking_rows[0]))
    writer.writeheader()
    writer.writerows(ranking_rows)

report = [
    "# Retrieval development evaluation", "",
    f"Compared {len(queries)} questions across all {len(articles)} fictional articles.", "",
    "Labels are assistant-proposed judgements under strict direct-answer rules. "
    "Both questions and labels were prepared by the assistant before their rankings were run. "
    "The collection is familiar and includes an article constructed after earlier retrieval "
    "inspection. Even files named test_queries and test_relevance do not make this an "
    "independent human-reviewed held-out benchmark.", "",
    f"Question source: `{query_path}`. Label source: `{label_path}`.", "",
    "Both methods receive the same titles, bodies and questions. TF-IDF uses default "
    "TfidfVectorizer settings fitted on the 21 article texts only. Embeddings use "
    "sentence-transformers/all-MiniLM-L6-v2 on CPU; its exact model revision is not pinned.", "",
    "## Mean metrics across questions", "",
    "Each question has equal weight (macro average). Recall excludes questions with no relevant "
    "articles; precision includes them. This set has at least one relevant article per question.", "",
    "| Method | K | Mean precision | Mean recall |",
    "| --- | --- | --- | --- |",
]
print(f"Compared {len(queries)} questions, {len(articles)} articles, {len(labels)} labels.")
for method in ("Embeddings", "TF-IDF"):
    for k in (1, 3, 5):
        rows = [row for row in metric_rows if row["method"] == method and row["k"] == k]
        precision = sum(row["precision"] for row in rows) / len(rows)
        recalls = [row["recall"] for row in rows if row["recall"] is not None]
        recall_text = f"{sum(recalls) / len(recalls):.1%}" if recalls else "N/A"
        report.append(f"| {method} | {k} | {precision:.1%} | {recall_text} |")
        print(f"{method} @{k}: precision {precision:.1%}, recall {recall_text}")

report.extend(["", "## Per-question metrics", "",
               "| Query | Method | K | Precision | Recall |",
               "| --- | --- | --- | --- | --- |"])
for row in metric_rows:
    recall_text = f"{row['recall']:.1%}" if row["recall"] is not None else "N/A"
    report.append(
        f"| {row['query_id']} | {row['method']} | {row['k']} | "
        f"{row['precision']:.1%} | {recall_text} |"
    )
report.extend(["", "## Irrelevant articles in the top three", ""])
for query in queries:
    qid = query["query_id"]
    report.extend([f"### {qid}: {query['question']}", ""])
    for method in ("Embeddings", "TF-IDF"):
        false_matches = [row for row in ranking_rows if row["query_id"] == qid
                         and row["method"] == method and row["rank"] <= 3 and not row["relevant"]]
        details = "; ".join(f"#{row['rank']} {row['article_id']}: {row['title']}" for row in false_matches)
        report.append(f"- {method}: {details or 'none in the top three'}.")
    report.append("")
report.extend([
    "## Interpretation and next step", "",
    "A fixed top-K can include irrelevant results when fewer than K articles answer the question. "
    "Inspect the saved rankings and label reasons rather than assuming a high score is a useful match. "
    "These metrics describe this labelled development set only; they do not establish a production winner.", "",
    "Next: have a person review disputed labels, then add independently labelled questions that remain "
    "unseen while tuning. Do not fine-tune or choose a score threshold from this report alone.",
])
(output_dir / f"{report_prefix}-results.md").write_text("\n".join(report) + "\n", encoding="utf-8")
print(f"Saved docs/{report_prefix}-results.md and docs/{report_prefix}-rankings.csv")
