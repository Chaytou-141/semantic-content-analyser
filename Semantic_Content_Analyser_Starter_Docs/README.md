# Semantic Content Analyser

**A hands-on Python + Hugging Face AI engineering project with a future SEO use case**

**Project status:** Planned / learning project. Features listed below are goals, not implemented functionality.  
**Development environment:** Windows + Visual Studio Code (VS Code)  
**Initial mode:** Local, CPU-friendly, synthetic data only  
**Relationship to SocialBuzz SEO Studio:** An independent project first. Possible, separately approved integration later.

---

## 1. Why am I building this?

The goal is to become more confident in **applied AI engineering**, while building a portfolio project that solves a realistic SEO problem.

A semantic analyser compares the *meaning* of texts rather than only exact matching words. It will eventually help an SEO professional:

1. **Discover internal-link opportunities:** suggest related pages and relevant *source passages*, not automatically insert links.
2. **Identify possible content overlap:** surface articles with similar topics or potentially competing search intent for human review.
3. **Support content audits:** propose **keep / improve / consolidate / investigate removal** decisions using semantic evidence *plus* performance, quality, backlinks, and business context.
4. **Search content by meaning:** retrieve relevant articles from a natural-language query.

**Not the goal:** Build a bot that deletes articles, guarantees SEO rankings, scrapes unapproved websites, or edits production WordPress automatically.

The initial version will use **fictional articles** and no client data. Any future use of real client content must be explicitly authorised and scoped.

### What a successful portfolio demonstration should prove

> I can select a language model, convert text to embeddings, measure semantic similarity, compare it against a non-ML baseline, evaluate retrieval quality, expose an API, write tests, document trade-offs, and deploy a safe reproducible application.

---

## 2. What do I need to understand?

Do not rush past these terms. I should be able to explain them in plain language and show a working example.

| Concept | Simple meaning | Evidence that I understand it |
|---|---|---|
| Python virtual environment (`venv`) | A separate set of Python packages for this project | Create `.venv`, select it in VS Code, run from it |
| Git / GitHub | Local version history / remote collaboration hosting | Commit, branch, push, open PR, revert safely |
| Tokenisation | How models split text into pieces | Inspect tokens and a model's input limit |
| Transformer encoder | A neural-network model that creates contextual text representations | Explain why a pretrained encoder is suitable |
| Inference vs. training | Using a model vs. changing its weights | Run inference; explain why it is not fine-tuning |
| Embedding | A vector that represents text numerically | Print shape, inspect values and describe dimensions |
| Cosine similarity | Compare vector direction, not exact words | Calculate by library and once by hand/code |
| TF-IDF | A statistical, mostly keyword-based text representation | Build and evaluate a baseline |
| Top-K retrieval | Return the K most relevant results | Implement, sort and validate top-5 retrieval |
| Clustering | Group similar items without preassigned labels | Inspect clusters, including false matches |
| Precision@K / Recall@K | Measures how good retrieval results are against labels | Report metrics on held-out, manually labelled examples |
| Search intent | The user need behind a query | Explain why semantic overlap != same search intent |
| REST API / FastAPI | A way for another application to request analysis | Build and test endpoint(s) |
| Vector database | Storage/indexing for large-scale vector retrieval | Understand when in-memory search stops being enough |
| Docker / CI | Reproducible execution and automated checks | Containerise and run tests in GitHub Actions |
| Model card / licence | Intended uses, limitations, origin, permitted reuse | Record model name, revision, licence and limitations |

**Personal learning rule:** After each milestone, write 3–5 sentences explaining what I built, how it works, what failed, and what I would improve. Keep these in `docs/learning-journal.md`.

---

## 3. Planned technology stack

### Start small

- **Python:** Prefer Python 3.11 or 3.12 for a conservative starting environment; confirm installed version and dependency compatibility first.
- **VS Code:** Python extension, debugger, terminal and source control.
- **Hugging Face / Sentence Transformers:** Pretrained text embedding models.
- **PyTorch:** Used by the model runtime; learn tensors and inference fundamentals as part of the project.
- **scikit-learn:** TF-IDF baseline, similarity helpers, clustering and evaluation.
- **pandas:** Read and validate sample CSV datasets.
- **pytest:** Automated tests.

### Add only when needed

- **FastAPI + Uvicorn:** Expose analysis endpoints when core retrieval has been evaluated.
- **PostgreSQL + pgvector:** Optional persistence and scalable vector search; not necessary for 20–50 example articles.
- **React:** Optional separate frontend after the Python pipeline works.
- **Docker + GitHub Actions + AWS:** Later deployment and MLOps learning.

**Starter model:** [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). It produces 384-dimensional embeddings and is a practical *English-language* beginner baseline. Read its model card and check its licence before reuse. Its default text input is truncated above 256 word pieces, so long articles require a deliberately tested chunking method. Do not assume the model works equally well for Arabic or for entire unchunked blog posts.

Using a pretrained model is **inference**, not evidence that I have trained a model. We will compare models only after creating a labelled evaluation set.

---

## 4. Set up a new project in VS Code (Windows PowerShell)

This project should live in its **own folder and Git repository**, not inside the SocialBuzz source code. The instructions below are for a new empty folder.

### Prerequisites

1. Install Git and a supported Python interpreter (start with Python 3.11 or 3.12 if available).
2. Install VS Code with Microsoft's **Python** extension. The Python Environments extension is also useful.
3. In VS Code choose **File → Open Folder**, create/open `semantic-content-analyser`, and open **Terminal → New Terminal**.
4. Run `py --list` (Windows) or `python --version` to confirm the Python installation.

### Create a virtual environment

The following uses Python 3.12 if installed; replace `-3.12` with a version actually available on your PC:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install sentence-transformers scikit-learn pandas pytest
```

This intentionally invokes the environment's Python directly, so **PowerShell activation is not required**. If `py` is not available, use the corresponding installed Python executable to create the environment.

In VS Code, open the Command Palette (`Ctrl+Shift+P`) → **Python: Select Interpreter** → choose `.venv`.

On first use the model must be downloaded from Hugging Face and packages installed, so internet access is required during setup. Normal small-data inference can then run locally once dependencies/model files are cached. Do not commit model caches.

### First runnable exercise: embeddings and similarity

Create `experiments/first_embeddings.py` with this code:

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

sentences = [
    "How to choose a display fridge for a cafe",
    "Selecting refrigeration displays for a retail shop",
    "How to clean a commercial chest freezer",
]

embeddings = model.encode(sentences)
print("Embedding matrix shape:", embeddings.shape)

scores = model.similarity(embeddings, embeddings)
print("Similarity matrix:\n", scores)
```

Run it from the project root:

```powershell
.\.venv\Scripts\python.exe experiments\first_embeddings.py
```

**Expected behaviour:** The shape should show 3 rows and 384 columns for this model. A 3 × 3 similarity matrix should print. Exact similarity values depend on the model and library version; do not hard-code expected values or assume every result represents true SEO relevance.

**Before moving on, answer:** What is an embedding? Why do we have 384 numbers? Why is a similarity matrix symmetric here? Why is a high score not proof that pages should be merged?

### Reproducibility

After the initial environment works, record actual installed versions:

```powershell
.\.venv\Scripts\python.exe -m pip freeze > requirements-lock.txt
```

Keep a small reviewed `requirements.txt` or `pyproject.toml` later; do not blindly upgrade a working dependency stack. A lock snapshot is environment-specific and should be documented alongside the Python version.

---

## 5. Suggested project layout

This is a **target structure**. Do not create empty modules just to fill every folder. Add them milestone by milestone.

```text
semantic-content-analyser/
├── README.md
├── .gitignore
├── requirements.txt                 # after dependency review
├── requirements-lock.txt            # after first working install
├── data/
│   └── synthetic_articles.csv       # made-up article content only
├── labels/
│   └── synthetic_relevance.csv      # manually reviewed query-to-article labels
├── experiments/
│   └── first_embeddings.py
├── src/
│   └── semantic_analyser/
│       ├── __init__.py
│       ├── data_loading.py
│       ├── baseline_tfidf.py
│       ├── embeddings.py
│       ├── retrieval.py
│       ├── evaluation.py
│       └── api.py                    # future FastAPI stage
├── tests/
│   └── test_retrieval.py
├── docs/
│   ├── learning-journal.md
│   ├── model-evaluation.md
│   └── integration-boundaries.md
└── .github/
    └── workflows/                  # future test CI
```

### Minimal `.gitignore` (review before first commit)

```gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.env
.env.*
!.env.example
*.sqlite3
.cache/
models/
checkpoints/
artifacts/private/
data/client_*/
data/raw_private/
*.log
```

Keep demonstration CSVs small and synthetic. Never commit real client copy, tokens, credentials, production exports, downloaded models or private traces. The ignore file is a starting point, not a substitute for reviewing `git status` and staged changes.

---

## 6. Development roadmap and acceptance criteria

### Milestone 0 — Learn Git and build a safe baseline

**Do:** Create the private repository, review `.gitignore`, make a first commit, push only after reviewing every staged file. Learn status, add, commit, log, branch, push, pull and pull requests.

**I should understand:** The difference between a working tree, staging area, commit, branch, remote and a GitHub repository.

**Done when:** I can recover a previous *code version* safely and know that Git is not a database backup.

### Milestone 1 — Embeddings and semantic similarity

**Do:** Run the three-sentence example. Use 20–50 *synthetic* SEO-themed articles with ID, title, short body and topic label. Calculate pairwise similarity and show the top-5 related titles for a selected article.

**Learn:** Pretrained inference, tokenisation, tensors, embedding shape, cosine similarity, caching and text-length limits.

**Done when:** Results are reproducible and I can explain at least two incorrect matches.

### Milestone 2 — Keyword baseline and meaningful evaluation

**Do:** Build a `TfidfVectorizer` + cosine similarity baseline. Create a small manually labelled set of queries and relevant documents. Evaluate both TF-IDF and embeddings on the *same* queries, same documents, same top-K, and report Precision@K / Recall@K where the labelled relevance set permits it.

**Learn:** Baselines, relevance judgement, evaluation metrics, leakage, error analysis, model comparison.

**Done when:** `docs/model-evaluation.md` explains which system works better on which examples and where both fail. A model isn't considered better just because it feels more advanced.

### Milestone 3 — Internal-link opportunity discovery

**Do:** For an explicitly selected source article, rank relevant destination articles. Exclude self-links, known existing links and disallowed targets. Surface a candidate source passage and target URL for review. Distinguish *related subject* from *a useful link at a specific paragraph*.

**Learn:** Retrieval, passage/chunk embeddings, ranking, rule constraints, explainability, evaluation with editorial labels.

**Done when:** Human-reviewed examples demonstrate useful suggestions and false positives are documented. **Do not write to WordPress.**

### Milestone 4 — Topic overlap and content review

**Do:** Group articles that are similar, inspect different search intents, and flag possible overlaps. Incorporate optional *manually imported* performance columns (clicks, impressions, date range) strictly as evidence, not as proof of deletion eligibility.

**Learn:** Clustering, thresholds, ranking, uncertainty and SEO decision-making.

**Done when:** The tool explains why it flagged two articles, and clearly says **review**, not **delete**. A zero-click page is not automatically low value.

### Milestone 5 — API and tests

**Do:** Implement a small FastAPI endpoint for analysing a bounded set of locally supplied articles; validate schema and limits. Add unit/integration tests with a mock or cached model where appropriate. Avoid downloading a large model on every CI test run.

**Learn:** HTTP, request validation, exceptions, type hints, dependency injection, API docs, pytest.

**Done when:** A separate client can call the API and tests pass in a fresh checkout.

### Milestone 6 — Database and deployment (later)

**Do:** Consider PostgreSQL + pgvector only if persistence or scale justifies it. Add Docker and GitHub Actions; deploy an authorised demo with synthetic content. Capture latency, memory, model version and costs.

**Learn:** Vector indexing, persistence, CI/CD, secrets, model provenance, monitoring and deployment.

**Done when:** The demo can be reproduced and supported without relying on undocumented local state.

### Milestone 7 — Possible SocialBuzz integration (separate decision)

Integration is **not** authorised by this README. First design a narrow read-only boundary: SocialBuzz explicitly exports or sends selected, approved article content to the separate analyser and receives **recommendations with evidence**. No hidden crawling, scope expansion, background access to live page bodies, automatic publishing or deletion. Changes to WordPress still require SocialBuzz's existing compatibility, approval, verification and restore controls.

---

## 7. What will the SEO analyser actually recommend?

| Candidate outcome | Appropriate evidence | What it should *not* infer |
|---|---|---|
| Suggest an internal link | Semantic relevance + useful source passage + known eligible destination | That similarity alone proves the link improves rankings |
| Review content overlap | Similarity + matching intent/questions + optionally query overlap | That two semantically similar pages are automatically cannibalising |
| Improve article | Weak or outdated information, user intent mismatch, performance history | That low clicks alone prove bad quality |
| Consolidate articles | Substantial duplicated value, matching intent, coverage and link preservation plan | That one page should be merged solely from an embedding score |
| Investigate removal | Manual editorial review of business value, performance, backlinks, traffic and redirect impact | That the tool may delete or 404 a page autonomously |

Decisions about merging/removal must include URL mapping, inbound links, internal links and appropriate redirects or retention plans. An article with little traffic may still support customers, conversions or other pages.

**Privacy and permission boundary:** Real client data stays out of the public portfolio repository. Only process content the client explicitly authorises, use local/exported data where possible, document model-provider transfers, and avoid bypassing robots, WordPress permissions or the SocialBuzz allowlist.

---

## 8. My learning checkpoints (do not let the agent skip these)

After each milestone, I should be able to **demonstrate** the skill rather than merely say I used the library.

- [ ] Explain Python interpreter vs. `pip` vs. `venv` and select the right interpreter in VS Code.
- [ ] Explain Git `commit` vs. `push` vs. `pull`; create and review a feature branch.
- [ ] Explain embeddings without saying the model “understands SEO perfectly.”
- [ ] Show one cosine-similarity calculation and explain the result.
- [ ] Explain why short text and long articles are processed differently.
- [ ] Compare TF-IDF and embeddings on the same labelled examples.
- [ ] Explain false positives, Precision@K and Recall@K.
- [ ] Explain how to choose an internal-link candidate and why it might be unsuitable.
- [ ] Explain why high similarity does not automatically mean keyword cannibalisation.
- [ ] Explain why zero-click articles may still have business value.
- [ ] Implement and test one FastAPI endpoint.
- [ ] Explain when a vector database is useful and when it adds unnecessary complexity.
- [ ] Package a reproducible application and describe deployment and monitoring considerations.
- [ ] Show Git history, test evidence and a credible portfolio demonstration.

### Interview-style questions to practise

1. What is an embedding and how is it different from TF-IDF?
2. How does cosine similarity work, and what are its limitations?
3. Why might two articles with high semantic similarity need to remain separate?
4. How would you evaluate internal-link recommendations?
5. How would you handle articles longer than the model's input limit?
6. Why might a model with higher embedding quality be worse for a CPU-based product?
7. How do you prevent client data from leaking into logs, models or GitHub?
8. How would your Python service communicate safely with SocialBuzz?
9. How do you reproduce the same result on another laptop?
10. What would you monitor if this application became a paid service?

---

## 9. Rules for using Codex / another coding agent

The agent is a **teacher and engineering assistant**, not an autopilot that should generate an entire commercial product before I understand it.

- Start with **Milestone 0 and the first small Milestone 1 exercise only**.
- Ask me to perform selected terminal/Git operations, explain each command and how to inspect the result.
- For ML concepts, give a small explanation, one focused coding exercise and two or three questions to check understanding.
- Prefer a tested, simple implementation over a large framework.
- Show the file changes, explain their purpose and run relevant tests.
- Keep the first project CPU-friendly and use synthetic or explicitly licensed public data.
- Never ask me to paste secrets or private client data into the agent chat.
- Do not install paid services, publish a public repository or contact a client's site without explicit approval.
- Never merge code into SocialBuzz or relax its access controls automatically.
- Record limitations, model versions, evaluation results and failure cases honestly.
- Stop at an agreed milestone and present evidence before progressing.

A ready-to-send Codex instruction is provided in `CODEX_START_PROMPT.md` (included alongside this README in the downloadable starter pack).

---

## 10. Learning resources (official)

- [Hugging Face model card: all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [Sentence Transformers installation](https://sbert.net/docs/installation.html)
- [Sentence Transformers quickstart](https://sbert.net/docs/quickstart.html)
- [Hugging Face LLM course](https://huggingface.co/learn/llm-course/chapter1/1)
- [scikit-learn cosine similarity documentation](https://scikit-learn.org/stable/modules/metrics.html#cosine-similarity)
- [VS Code Python environments](https://code.visualstudio.com/docs/python/environments)
- [Python virtual environments](https://docs.python.org/3/library/venv.html)
- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [Git book](https://git-scm.com/book/en/v2)
- [GitHub Skills](https://skills.github.com/)

---

## 11. First session checklist

- [ ] Create a **new** `semantic-content-analyser` folder in VS Code (not inside SocialBuzz).
- [ ] Check Python installation and learn what an interpreter is.
- [ ] Create `.venv` and select it.
- [ ] Review `.gitignore` and create a private Git repository with guidance.
- [ ] Install the minimum Python packages.
- [ ] Run `experiments/first_embeddings.py` with three synthetic sentences.
- [ ] Record Python/package/model versions and observations.
- [ ] Explain the 3 × 384 embedding shape and the 3 × 3 similarity matrix in my own words.
- [ ] Commit only reviewed source and synthetic data.

**Next session:** Create a small synthetic article dataset and work toward top-5 retrieval. Do not jump directly to WordPress integration, clustering, AWS or article deletion.
