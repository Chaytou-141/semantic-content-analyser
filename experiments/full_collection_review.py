import csv
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

project_root = Path(__file__).resolve().parent.parent
question = "How can I arrange the espresso preparation area so cafe staff can work efficiently?"

with (project_root / "data" / "synthetic_articles.csv").open(
    encoding="utf-8", newline=""
) as file:
    articles = list(csv.DictReader(file))

with (project_root / "labels" / "q05_relevance.csv").open(
    encoding="utf-8", newline=""
) as file:
    label_rows = list(csv.DictReader(file))

# Missing labels must never silently become "not relevant".
article_ids = [article["id"] for article in articles]
label_ids = [row["article_id"] for row in label_rows]
if len(set(article_ids)) != len(article_ids):
    raise ValueError("Article IDs must be unique.")
if len(set(label_ids)) != len(label_ids):
    raise ValueError("Each article must have exactly one Q05 label.")
if set(article_ids) != set(label_ids):
    raise ValueError("Q05 labels must cover every article, with no extra IDs.")
if any(row["query_id"] != "Q05" or row["relevant"] not in {"yes", "no"} for row in label_rows):
    raise ValueError("Resolve every Q05 label to yes or no before evaluation.")

labels = {row["article_id"]: row["relevant"] for row in label_rows}
total_relevant = sum(label == "yes" for label in labels.values())
article_texts = [article["title"] + ". " + article["body"] for article in articles]

# Both methods search the same full collection and receive no relevance labels.
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
article_embeddings = model.encode(article_texts)
question_embedding = model.encode([question])
embedding_scores = model.similarity(question_embedding, article_embeddings)[0].tolist()

vectorizer = TfidfVectorizer()
article_word_vectors = vectorizer.fit_transform(article_texts)
question_word_vector = vectorizer.transform([question])
tfidf_scores = cosine_similarity(question_word_vector, article_word_vectors)[0].tolist()

print("\nQ05:", question)
print("Articles searched:", len(articles))
print("Embedding shape:", article_embeddings.shape)
print("Relevant articles according to the recorded labels:", total_relevant)
print("Label sources:", ", ".join(sorted({row["label_source"] for row in label_rows})))
print("Development exercise; assistant-proposed labels, not a held-out benchmark.")

for method, scores in [("Embeddings", embedding_scores), ("TF-IDF", tfidf_scores)]:
    ranked = sorted(zip(articles, scores), key=lambda item: item[1], reverse=True)
    print("\nMethod:", method)
    print("Rank | ID | Similarity | Label: relevant? | Title")
    for rank, (article, score) in enumerate(ranked[:5], start=1):
        label = labels[article["id"]]
        print(f"{rank} | {article['id']} | {score:.4f} | {label} | {article['title']}")

    for k in (1, 3, 5):
        if len(ranked) < k:
            raise ValueError(f"At least {k} articles are needed for metrics at K={k}.")
        relevant_count = sum(labels[article["id"]] == "yes" for article, score in ranked[:k])
        print(f"Precision@{k}: {relevant_count / k:.0%} ({relevant_count}/{k} relevant)")
        if total_relevant:
            print(
                f"Recall@{k}: {relevant_count / total_relevant:.0%} "
                f"({relevant_count}/{total_relevant} relevant articles found)"
            )
        else:
            print(f"Recall@{k}: N/A (no articles labelled relevant)")
