"""Rank fictional internal-link candidates for a short source passage."""

import csv
import json
from pathlib import Path

from sentence_transformers import SentenceTransformer

project_root = Path(__file__).resolve().parent.parent
with (project_root / "data" / "synthetic_articles.csv").open(
    encoding="utf-8", newline=""
) as file:
    articles = list(csv.DictReader(file))

rules = json.loads(
    (project_root / "data" / "synthetic_link_rules.json").read_text(encoding="utf-8")
)
by_id = {article["id"]: article for article in articles}
if len(by_id) != len(articles):
    raise ValueError("Article IDs must be unique.")

source_id = rules["source_id"]
existing = set(rules["existing_target_ids"])
disallowed = set(rules["disallowed_target_ids"])
excluded = {source_id} | existing | disallowed
if not excluded <= set(by_id):
    raise ValueError("Every ID in the fictional link rules must exist in the collection.")

source = by_id[source_id]
# These articles have one short body paragraph; no long-article chunking yet.
passage = source["body"]
candidates = [article for article in articles if article["id"] not in excluded]
if not candidates:
    raise ValueError("No eligible destinations remain after exclusions.")

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
passage_embedding = model.encode([passage])
candidate_embeddings = model.encode([
    article["title"] + ". " + article["body"] for article in candidates
])
scores = model.similarity(passage_embedding, candidate_embeddings)[0].tolist()
ranked = sorted(zip(candidates, scores), key=lambda item: item[1], reverse=True)

print("\nSource:", source_id, source["title"])
print("Source passage:", passage)
print("\nFictional exclusions:")
print("Self-link:", source_id)
print("Already linked:", ", ".join(sorted(existing)) or "none")
print("Disallowed:", ", ".join(sorted(disallowed)) or "none")
print("Eligible destinations:", len(candidates))
print("\nCandidates for editorial review (example URLs only):")
for rank, (article, score) in enumerate(ranked[:3], start=1):
    print(f"\n{rank}. {article['id']} | {score:.4f} | {article['title']}")
    print(f"Target URL: https://example.com/articles/{article['id'].lower()}")
    print("Target evidence:", article["body"])

print(
    "\nReview whether a destination answers a useful follow-up question at this passage. "
    "A similarity score alone does not establish a useful link or SEO benefit. "
    "This script does not edit articles or contact websites."
)
