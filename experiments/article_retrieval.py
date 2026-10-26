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
