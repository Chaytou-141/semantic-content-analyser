# Application architecture and decisions

The browser interface and JSON API share one FastAPI origin. A single server process owns a bounded in-memory retrieval cache; SQLite persists article text, eligibility, existing-link IDs and editorial decisions. Docker packages the service; EC2 runs it behind a Caddy HTTPS proxy.

## Request flow

1. Validate the request, workspace session and custom request header.
2. Read the collection from SQLite. Validate imported collections before a transactional replacement.
3. Fingerprint article content and link metadata. Rebuild the passage index only when the collection changes.
4. Split bodies using the model tokenizer, retaining character offsets and overlapping windows.
5. Compare normalised embeddings or TF-IDF vectors with cosine similarity.
6. Apply destination exclusions and aggregate the best passage per article/pair.
7. Return bounded candidates with evidence for human judgement.

## Why these choices

- **One service:** avoids a frontend build pipeline, cross-origin credentials and multiple deployment units for the first AWS learning project.
- **SQLite:** adequate for one workspace and one process. Database writes are serialised and review decisions are cleared when relevant text changes. This is not designed for horizontal scaling.
- **In-memory vectors:** bounded collection; no reason to introduce pgvector infrastructure yet. The cache is lost on restart and rebuilt from persistent text.
- **A pinned model revision:** prevents an upstream model update from silently changing application embeddings. Dependencies and deployment images also need deliberate update/testing.
- **CPU-only runtime:** no GPU required. The first cold start and larger imports can be slow; measure real memory/latency before expanding limits.
- **Single process lock for model/cache operations:** avoids duplicate loads and inconsistent cache state during concurrent analyses. Requests queue behind analysis; there is no distributed job queue or cancellation support.
- **Same-origin password session:** appropriate for this single-workspace learning demo. It is not account management or tenant authorisation.

## Quality limits

English is the initial language. Query length is bounded at 256 model tokens for semantic search. Titles are capped at 40 tokens; source bodies are chunked at 192 tokens with 32-token overlap. Passage matching can overvalue a small related fragment of a long document, and max-score aggregation gives longer articles more opportunities to match. Thresholds are user controls, not calibrated relevance guarantees.

Stored historical evaluation uses the earlier whole-article scripts; it is not a measured evaluation of the new passage index. Assistant-proposed labels are development evidence, not independent human ground truth. Before production decisions, have editors label a representative set, evaluate the application's passage scorer on held-out questions and source/destination opportunities, measure failures and compare methods under identical constraints.

## Scope

This application suggests candidates. It does not crawl sites, resolve article URLs, call WordPress, insert links, change content, merge/delete pages, infer SEO ranking benefits, or treat zero traffic as low value. Real content needs explicit authorisation. Multi-user auth, a scalable vector index, automated backups, deployment monitoring and a full editorial audit workflow would be separate extensions.
