import csv
from pathlib import Path

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

project_root = Path(__file__).resolve().parent.parent
with (project_root / "data" / "synthetic_articles.csv").open(
    encoding="utf-8", newline=""
) as file:
    articles = list(csv.DictReader(file))

# Human decisions from docs/relevance-review.md; never passed to the model.
examples = [
    {
        "id": "Q01",
        "question": (
            "How do I clean the shelves and glass of a refrigerated display cabinet "
            "used for cakes?"
        ),
        "labels": {"A21": "yes", "A04": "no", "A11": "no", "A07": "no"},
    },
    {
        "id": "Q02",
        "question": "What should I consider when buying an espresso machine for a small cafe?",
        "labels": {"A08": "yes", "A09": "no", "A11": "no", "A12": "no"},
    },
    {
        "id": "Q03",
        "question": (
            "Why does my loaf mixture expand while resting before it goes into the oven?"
        ),
        "labels": {"A13": "no", "A14": "yes", "A15": "no", "A16": "no"},
    },
    {
        "id": "Q04",
        "question": "What should I consider when choosing a refrigerated display for my cafe?",
        "labels": {
            "A01": "yes", "A03": "yes", "A04": "yes",
            "A05": "yes", "A06": "no", "A08": "no",
        },
    },
]

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")

for example in examples:
    question = example["question"]
    human_labels = example["labels"]
    total_relevant = sum(label == "yes" for label in human_labels.values())
    candidates = [article for article in articles if article["id"] in human_labels]
    article_texts = [article["title"] + ". " + article["body"] for article in candidates]

    # Encode the reader's question and candidate articles separately.
    question_embedding = model.encode([question])
    article_embeddings = model.encode(article_texts)
    embedding_scores = model.similarity(question_embedding, article_embeddings)[0].tolist()

    # Learn word weights from the candidate articles only, not the question or labels.
    vectorizer = TfidfVectorizer()
    article_word_vectors = vectorizer.fit_transform(article_texts)
    question_word_vector = vectorizer.transform([question])
    tfidf_scores = cosine_similarity(question_word_vector, article_word_vectors)[0].tolist()

    print("\nQuestion", example["id"] + ":", question)
    print(f"Exercise with {len(candidates)} reviewed candidates; not the full collection.")
    print("Human-labelled relevant articles:", total_relevant)
    for method, scores in [("Embeddings", embedding_scores), ("TF-IDF", tfidf_scores)]:
        ranked_candidates = sorted(
            zip(candidates, scores), key=lambda item: item[1], reverse=True
        )
        print("\nMethod:", method)
        print("Rank | ID | Similarity | Human: relevant? | Title")
        for rank, (article, score) in enumerate(ranked_candidates, start=1):
            label = human_labels[article["id"]]
            print(f"{rank} | {article['id']} | {score:.4f} | {label} | {article['title']}")

        # Measure usefulness using human labels, not the similarity score sizes.
        for k in (1, 2, 3):
            top_results = ranked_candidates[:k]
            relevant_count = sum(
                1 for article, score in top_results
                if human_labels[article["id"]] == "yes"
            )
            precision = relevant_count / k
            print(f"Precision@{k}: {precision:.0%} ({relevant_count}/{k} relevant)")
            # Recall covers only the human-reviewed candidates in this exercise.
            if total_relevant:
                recall = relevant_count / total_relevant
                print(
                    f"Recall@{k}: {recall:.0%} "
                    f"({relevant_count}/{total_relevant} relevant articles found)"
                )
            else:
                print(f"Recall@{k}: N/A (no candidates labelled relevant)")
