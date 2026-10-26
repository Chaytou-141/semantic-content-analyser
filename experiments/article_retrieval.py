import csv
from pathlib import Path

from sentence_transformers import SentenceTransformer

# Find the project folder from this script's location.
project_root = Path(__file__).resolve().parent.parent
data_path = project_root / "data" / "synthetic_articles.csv"

# Read each CSV row as a dictionary with named fields.
with data_path.open(encoding="utf-8", newline="") as file:
    articles = list(csv.DictReader(file))

print("Articles loaded:", len(articles))
print("First title:", articles[0]["title"])

# Give the model each article's title and body, without the ID or topic label.
article_texts = [
    article["title"] + ". " + article["body"]
    for article in articles
]

model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device="cpu",
)

embeddings = model.encode(article_texts)
print("Embedding shape:", embeddings.shape)

# Python counts list positions from zero: position 0 is article A01.
source_index = 5
source_article = articles[source_index]

# Compare the selected embedding with every article embedding.
scores = model.similarity(embeddings[source_index], embeddings)[0].tolist()

# Keep each candidate's position and score, excluding the source itself.
candidates = [
    (index, score)
    for index, score in enumerate(scores)
    if index != source_index
]

# Each candidate is (index, score), so item[1] selects its score.
ranked_candidates = sorted(candidates, key=lambda item: item[1], reverse=True)
top_five = ranked_candidates[:5]

print("\nSource:", source_article["id"], source_article["title"])
print("Top 5 similar articles:")
for rank, (index, score) in enumerate(top_five, start=1):
    article = articles[index]
    print(f"{rank}. {article['id']} | {score:.4f} | {article['title']}")
