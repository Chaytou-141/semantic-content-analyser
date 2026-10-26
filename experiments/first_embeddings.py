from sentence_transformers import SentenceTransformer

model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2",
    device="cpu",
)

sentences = [
    "How to choose a display fridge for a cafe",
    "Selecting refrigeration displays for a retail shop",
    "How to clean a commercial chest freezer",
    "Choosing a refrigerated display cabinet for a coffee shop",
]

embeddings = model.encode(sentences)

print("Embedding shape:", embeddings.shape)
print("First embedding's first 5 numbers:", embeddings[0][:5])

scores = model.similarity(embeddings, embeddings)
print("Similarity matrix:")
print(scores)