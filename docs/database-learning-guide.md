# Semantic Content Analyser Database Learning Guide

## Purpose and recommendation

This guide explains our actual storage architecture, teaches the database concepts behind it, and provides a staged plan for a future PostgreSQL and pgvector implementation. It is written for the project owner learning AI engineering with an assistant.

**Current implementation:** SQLite saves articles and editorial decisions. Python memory holds passage chunks, embeddings and TF-IDF vectors. CSV and Markdown files hold learning data and evaluation evidence. PostgreSQL, pgvector, persistent vector storage, background jobs and client isolation are not implemented.

**Recommendation:** retain SQLite for the current single-workspace learning application. Design and adopt PostgreSQL before operating a shared multi-client SocialBuzz integration. Add persistent passage vectors when useful; introduce an approximate vector index only after measuring the need.

Reviewed on 27 October 2026. Source snapshot: branch `feature/deployable-aws-app`, commit `34e4a076ef31e28ecf6f9500a9f172d8c95a8968`. Line numbers below refer to that snapshot and may move in later versions. The review inspected code and confirmed that the database file exists; it did not query private database records or inspect SocialBuzz's separate codebase.

This is documentation, not authorisation to change code, install packages, migrate data, provision AWS resources or integrate with SocialBuzz. All proposed schemas and implementation stages are future work.

## 1 How to learn with your assistant

Work through one lesson at a time. Ask your assistant to explain a concept, point to our actual code, demonstrate a tiny example, let you try, and check your explanation. Do not ask it to silently implement the entire migration while teaching the first lesson.

For every lesson, answer five questions:

1. What does this concept mean?
2. Why does an application use it?
3. Which file or function demonstrates it here?
4. What currently happens when the function runs?
5. How would I verify that behaviour safely?

Suggested sequence: current storage, tables and SQL, transactions, in-memory embeddings, PostgreSQL, JSONB, pgvector, ownership and isolation, then implementation planning. Complete the read-only exercises before authorising a disposable implementation exercise.

Use these status labels when discussing changes:

| Label | Meaning |
| --- | --- |
| Implemented | Present in the reviewed application code |
| Proposed | A design recommendation that has not been built |
| Exercise | A learning activity; not an instruction already executed |
| Requires authorisation | Changes data, application behaviour, infrastructure or external integration |

## 2 Current storage architecture

The application has several storage layers with different jobs. A database is not the same thing as every file the application uses.

| Layer | Actual contents | Survives process restart |
| --- | --- | --- |
| SQLite | Articles, link rules inside article payloads, editorial reviews and initialisation metadata | Yes, if its disk or volume survives |
| Python process memory | Tokenised passages, character offsets, normalised embeddings, TF-IDF vectors and cache fingerprint | No |
| CSV and Markdown files | Synthetic articles, questions, relevance labels, experiment rankings and reports | Yes |
| Model files on disk | Pretrained model weights, tokenizer and configuration | Yes, if retained in cache or image |
| Session cookie and environment | Signed workspace session in the browser; password and signing-secret configuration | Separate from article storage |

**Model weights are not article embeddings.** Weights are the parameters of the pretrained model. Embeddings are the numerical representations produced when it processes our article passages.

The default local database is `runtime/workspace.sqlite3`. It is an ignored runtime file, not a file committed to Git. SQLite's WAL mode can also create companion `-wal` and `-shm` files.

In a container the database path is `/app/runtime/workspace.sqlite3`. Compose mounts a named `workspace` volume at `/app/runtime`, preserving records across container replacement. That is persistence, not an off-machine backup. Terminating the AWS instance can still destroy its disk and Docker volumes.

### Code map

| File and function | What to inspect |
| --- | --- |
| `semantic_analyser/config.py:10` — `Settings` | `DATABASE_PATH` and its SQLite default |
| `semantic_analyser/storage.py:61` — `Store` | Table creation and raw SQL operations |
| `semantic_analyser/schemas.py:10` — `Article` | Validated article fields |
| `semantic_analyser/api.py:26` — `create_app` | Constructs the store and retrieval engine |
| `semantic_analyser/engine.py:53` — `prepare` | Builds or reuses the passage index |
| `semantic_analyser/engine.py:73` — `semantic_vectors` | Calculates and caches article-passage embeddings |
| `compose.yaml:9` | Local named database volume |
| `deploy/aws/compose.production.yaml:9` | Production database path and volume |
| `semantic_analyser/api.py:208` — `evaluation` | Reads historical CSV evidence rather than a results table |

The implementation uses Python's built-in `sqlite3` library and explicit SQL. There is no SQLAlchemy ORM, PostgreSQL connection pool or pgvector configuration in the reviewed code.

**Exercise 1:** open `config.py` and identify the environment variable controlling the database location. Explain what would happen if two deployments used two different database files. Do not change either path.

## 3 What is implemented and what is planned

| Capability | Actual status |
| --- | --- |
| Persistent article collection | Implemented in SQLite |
| Saved useful and not-useful link decisions | Implemented in SQLite |
| CSV import and export | Implemented |
| Article edits and link eligibility | Implemented |
| Persistent passage records | Not implemented |
| Persistent embedding records | Not implemented |
| Search or overlap history | Not implemented as application records |
| Historical evaluation evidence | Saved in CSV and Markdown files |
| Background queue and job status | Not implemented |
| Client, website and user membership tables | Not implemented |
| PostgreSQL and pgvector | Not implemented |
| SocialBuzz API integration | Not implemented |
| AWS database service | Not provisioned by the current infrastructure template |

The app currently limits a collection to 100 articles, 250,000 total title/body characters and 800 passages. Article bodies have a 20,000-character field limit. These are application limits, not SQLite's maximum capacity.

A small learning dataset does not require a vector database merely because it contains embeddings. The reasons to introduce a database server include ownership, concurrency, shared persistence and operational needs as well as data size.

## 4 Tables rows columns and keys

A **table** holds records of one kind. A **row** is one record. A **column** is one named property of each row. We use these structures to give saved data predictable organisation and constraints.

Our actual schema is created in `Store.__init__`:

| Table | Actual columns | Primary key |
| --- | --- | --- |
| `articles` | `id TEXT`, `payload TEXT` | `id` |
| `reviews` | `source_id`, `target_id`, `decision`, `note`, `updated_at` | The pair `source_id, target_id` |
| `metadata` | `key`, `value` | `key` |

Our articles table has only two SQL columns. Title, body, topic, URL, eligibility and existing-link IDs live inside the JSON string in `payload`; they are not separate SQL columns today.

An abbreviated example of the structure is:

```text
articles row
  id       A01
  payload  {"id":"A01","title":"Choosing a display fridge for a cafe", ...}
```

The actual `Article` model defines `id`, `title`, `body`, `topic`, `url`, `eligible` and `existing_links`. `model_dump_json()` serialises a validated object into JSON text. `Article.model_validate_json()` reconstructs and validates an object after reading it back.

A **primary key** uniquely identifies a row. The article key prevents a second row with the same ID. The review key is a **composite key**: it combines two columns. A01 to A02 and A02 to A01 are distinct directed relationships.

A **relationship** connects records. Our review's source and destination IDs refer to articles. A **foreign key** would make the database enforce that those referenced records exist. The reviewed schema does not declare foreign keys: `Store.review()` checks article existence in Python. A future design should add database-enforced relationships too.

**Exercise 2:** explain why A01 to A02 and A01 to A03 can both be saved, while a second decision about A01 to A02 updates an existing review. Find `PRIMARY KEY` and `ON CONFLICT` in `storage.py`.

## 5 SQL and safe database queries

**SQL** is the language used to ask a relational database to retrieve or change records. Both SQLite and PostgreSQL use SQL, although their connection APIs, types and some syntax differ.

`Store.articles()` executes this existing read query:

```sql
SELECT payload FROM articles ORDER BY id;
```

It asks for article payloads sorted by ID. `Store.reviews()` reads review rows sorted by their update timestamp. An illustrative read-only query is:

```sql
SELECT source_id, target_id, decision
FROM reviews
WHERE source_id = 'A01'
ORDER BY updated_at DESC;
```

`SELECT` chooses the columns; `FROM` chooses the table; `WHERE` filters records; `ORDER BY` sorts them. Without explicit ordering, do not assume a database returns rows in the order you want.

Our update code passes values separately from the query:

```python
connection.execute(
    "UPDATE articles SET payload=? WHERE id=?",
    (article.model_dump_json(), article.id),
)
```

The question marks are parameter placeholders. This existing example changes data; it is shown for explanation, not execution. Parameterisation avoids treating supplied article text as SQL instructions. A PostgreSQL driver may use different placeholder syntax, so migrating is more than changing the database filename.

**Exercise 3:** describe what the read-only review query above returns. Then read the existing update function and identify the value that selects which article changes.

### Optional read-only database inspection exercise

Only if you want to inspect your own existing local database, run the following from the repository root. It refuses to create a missing database and queries schema definitions only. It does not import the application module.

```python
from contextlib import closing
from pathlib import Path
import sqlite3

path = Path("runtime/workspace.sqlite3").resolve()
uri = path.as_uri() + "?mode=ro"

with closing(sqlite3.connect(uri, uri=True)) as connection:
    connection.execute("PRAGMA query_only = ON")
    rows = connection.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type = 'table' ORDER BY name"
    ).fetchall()
    for name, definition in rows:
        print(name)
        print(definition)
```

The guide's creation did not execute this exercise. Avoid using application startup or tests as a supposedly read-only inspection method: `create_app()` constructs a store, and store initialisation can create tables or seed demo data.

## 6 Transactions updates and review invalidation

A **transaction** groups database changes so they can be committed together or rolled back if an operation fails. We use transactions to avoid leaving only half a collection imported.

`Store.replace()` validates the collection, then deletes old articles, inserts replacement rows and clears old reviews inside a database transaction. `parse_csv()` validates the input before replacement. See `storage.py:28` and `storage.py:88`.

`Store.save_article()` validates an edit, updates its JSON payload and clears reviews where that article is the source or destination. A changed article can make earlier editorial judgements stale. This policy intentionally discards current decisions; it is not an audit-history system.

`Store.review()` uses an upsert. That means insert a new decision if none exists, otherwise update the existing decision for the same source/destination pair. The timestamp records the latest update, not a complete event history or reviewer identity.

The API also serialises mutations with a process lock. A process lock coordinates threads inside this one running service; it does not coordinate all future servers or replace database constraints.

**Exercise 4:** read `test_invalid_import_is_atomic` and `test_review_persists_and_edit_invalidates_it` in `tests/test_application.py`. Explain what each test protects. Do not run tests during a read-only review.

## 7 Embeddings and the memory cache

An **embedding** is a vector representing text. Our model produces 384 numbers per input passage. A **cache** keeps a computed result around so the app does not repeat expensive work unnecessarily.

The current request flow is:

```text
Browser question
  -> FastAPI search route
  -> SQLite article payloads
  -> Article objects
  -> Passage chunks and vectors in Python memory
  -> Similarity calculation and article ranking
  -> JSON results and source evidence
```

`passages()` divides bodies into windows of 192 tokens with 32-token overlap, adds up to 40 title tokens and retains character offsets. A token is a model input piece, not necessarily a whole word. One article can produce several passages and therefore several embeddings.

`prepare()` fingerprints all article data. A **fingerprint**, here a SHA-256 hash, is a content-derived identifier. When the collection fingerprint changes, the engine rebuilds passage and TF-IDF data and clears cached semantic vectors. URL and link-metadata changes are included, so invalidation is broader than body-text changes alone.

`semantic_vectors()` calculates normalised embeddings and assigns them to `self.embeddings`, a NumPy array in RAM. TF-IDF has its own vector representation in `self.word_vectors`. Even keyword-only operation currently loads the model to use its tokenizer for passage construction; TF-IDF itself does not need neural embedding inference.

The engine normalises semantic vectors. For these vectors, the dot product used in `scores()` corresponds to cosine similarity. Search keeps each article's best matching passage; link and overlap review use the strongest matching passage pair.

On restart, saved articles and reviews remain in SQLite, while the memory cache disappears. The model files may remain on disk, but article vectors still have to be recomputed. With several future workers, each would otherwise have a separate memory cache.

**Exercise 5:** find `self.embeddings = None` and `self.cache_key` in `engine.py`. Explain what would go wrong if we edited article text but kept returning rankings from old vectors.

## 8 Why SQLite fits the current application

SQLite is an embedded database: Python opens a database file directly through a library. There is no separate database server to install, configure or authenticate to. This suits our one-workspace, one-process, bounded learning demo.

SQLite supports concurrent readers but only one writer at a time. That does not mean only one person can use it. WAL mode helps readers coexist with a writer; it does not create a multi-writer server. See the official SQLite guidance in the reference list.

| Consideration | Current SQLite design | PostgreSQL design |
| --- | --- | --- |
| Setup | Embedded library and file | Separate database server or managed service |
| Local learning | Small operational burden | More backend concepts to configure |
| Concurrent writes | One writer at a time | Designed for concurrent transactions |
| Several application servers | Local file design needs reconsideration | Multiple services can connect to one server |
| Durable vector sharing | Not implemented here | Can store shared passage vectors |
| Access controls | File access plus application logic | Roles, privileges and optional row policies |
| Operations | Correct file backup and disk retention | Connection management, server backup and recovery |

SQLite can store much more than 100 articles. Our limits come from application design and model workload. Database choice should follow real ownership, concurrency and operational requirements, not an arbitrary article-count threshold.

**Exercise 6:** imagine two EC2 servers with separate local SQLite files. Explain why importing into server A does not automatically update server B. Then explain how connecting both to one PostgreSQL server changes that situation.

## 9 PostgreSQL and JSONB

**PostgreSQL** is a relational database server. FastAPI would connect through a driver using database credentials and network configuration. The server manages stored records and transactions; the application still performs validation, authorisation and model inference.

Our application does not currently make that connection. A migration would replace the SQLite storage implementation with PostgreSQL queries and connection management. A managed AWS service such as RDS is a possible later hosting choice, not an existing resource in this project. Verify supported extensions, versions, pricing and account constraints when making that choice.

**JSON** is a structured text format. Our article payload is JSON saved in a SQLite text column. **JSONB** is PostgreSQL's processed JSON representation, supporting JSON-specific queries and indexes. It is useful for flexible metadata, but it should not hide important ownership and relationship fields.

For a future article schema, use regular columns for required fields such as tenant, website, article identity, title, body and URL. Consider JSONB for optional metadata whose shape varies. Use a vector type for searchable embeddings rather than treating JSONB as a vector-search engine.

**Exercise 7:** classify these proposed values as a required relational column, flexible JSONB metadata or an embedding: `tenant_id`, optional editorial tags, `body`, and 384 model numbers. Explain why client ownership should not be an optional metadata convention.

## 10 PostgreSQL and pgvector

**pgvector** is an extension that adds vector storage and similarity operations to PostgreSQL. A `vector(384)` value can hold one embedding from our current model. The extension does not generate vectors or train a model: Python still runs the encoder.

In pgvector, `<=>` is cosine distance and `1 - distance` gives cosine similarity. Exact nearest-neighbour search is available without an approximate index. Optional HNSW or IVFFlat indexes trade some neighbour-retrieval recall for speed. Finding exact mathematical neighbours is not the same as finding editor-approved relevant articles.

A proposed future flow is:

```text
Authorised article text
  -> Python passage chunking
  -> Pretrained encoder
  -> Passage records and 384-number vectors in PostgreSQL

Later query
  -> Compatible query embedding
  -> Tenant and website scoped vector search
  -> Passage matches
  -> Distinct article aggregation and review evidence
```

Store passage ownership, text, character offsets, article version/content hash, model identity/revision and chunking version with the vector. These are design recommendations derived from our cache and passage behaviour. Dimensions alone do not make vectors from different models compatible.

This illustrative SELECT refers to a proposed table; it cannot run against our current schema:

```sql
SELECT article_id, passage_text,
       1 - (embedding <=> $1::vector) AS similarity
FROM article_passages
WHERE tenant_id = $2
  AND site_id = $3
  AND model_revision = $4
ORDER BY embedding <=> $1::vector
LIMIT 5;
```

The parameters represent the query vector, authorised tenant, website and model revision. The driver would bind values safely. Filtering by compatible chunking/content versions is another requirement of the final design. Five passages may belong to fewer than five articles, so this query alone does not reproduce the application's distinct-article ranking.

**Exercise 8:** suppose article A has four passages and article B has two. Why does a passage table need more than one row per article? Why must an article edit invalidate old passage vectors?

### Do we need pgvector now

No. At the current 100-article and 800-passage application bounds, direct in-memory comparison is a reasonable baseline. Persistent vectors can still be valuable for restart time and sharing across workers, even when search is small. PostgreSQL can be adopted for ownership and persistence before an approximate vector index is justified.

Measure passage counts, memory, cold-start time, query latency and retrieval quality. Do not choose a universal threshold such as a particular number of articles: article lengths and concurrency matter. Introducing pgvector also does not remove the need to preserve and evaluate TF-IDF as a separate method.

## 11 A proposed relational schema

The following is a teaching design, not a migration or final production schema.

| Proposed table | Purpose | Important fields |
| --- | --- | --- |
| `tenants` | Client organisations | Internal ID and organisation details |
| `sites` | Websites owned by clients | ID, tenant ID and approved website identity |
| `articles` | Authorised content snapshots | Internal ID, tenant/site IDs, external article ID, text and content version |
| `article_passages` | Traceable model inputs and vectors | Passage ID, article ownership, offsets, text, model/chunk versions and embedding |
| `article_links` | Known existing article links | Tenant/site ownership plus source and target identities |
| `link_reviews` | Editorial decisions | Scoped source/target identities, decision, note, reviewer and content versions |
| Optional `analysis_jobs` | Asynchronous work if needed | Ownership, status, retry/idempotency data and timestamps |

One tenant can own multiple sites. One site can have many articles. One article can have many passages. A link review joins a source article to a target article and records a decision.

Use internal unique IDs or scoped composite keys so two clients can both have an external article ID such as A01. Enforce uniqueness of an external article ID within its intended tenant/site scope. Use foreign keys that cannot silently cross ownership boundaries; independent valid source and target IDs are not enough if they can belong to different clients.

A separate embedding table may be preferable if multiple model versions must coexist. That would reference a passage plus an embedding configuration, avoiding duplication of passage text for every model. Decide this from actual versioning requirements rather than introducing every possible table at once.

**Exercise 9:** draw the relationships in words: tenant to sites, site to articles, article to passages. Mark each as one-to-many. Then explain which records must be removed or superseded when an article version changes.

## 12 SocialBuzz integration through an API

SocialBuzz already uses PostgreSQL according to the project owner. Its schema and implementation were not inspected here. Our applications can communicate through an API regardless of whether they use the same database technology.

For a future integration, prefer separate application databases and credentials. They may initially share one PostgreSQL server to reduce operational overhead, but should not share unrestricted ownership of each other's tables. Separate databases do not automatically require separate database servers.

SocialBuzz should remain responsible for its users, client permissions, authoritative content identity and publishing controls. The analyser should own its authorised processing snapshots, compatible vectors and analysis evidence. Send only selected, approved content; do not add hidden crawling or direct production access.

```text
User in SocialBuzz
  -> SocialBuzz checks user and website permissions
  -> SocialBuzz reads approved content from its own database
  -> Authenticated analyser API receives scoped content
  -> FastAPI validates ownership and input
  -> Python creates compatible passages and embeddings
  -> Analyser PostgreSQL stores authorised snapshots and vectors
  -> API returns scoped recommendations and evidence
  -> SocialBuzz shows them for human review
```

Stable external IDs and content versions make updates traceable. An **idempotent** import means repeating the same request does not create accidental duplicates. A later asynchronous workflow would need durable job records and a real worker/queue; moving data into PostgreSQL alone does not create that system.

The current global CSV replacement endpoint is not an integration endpoint suitable for multiple clients. It replaces the workspace's entire collection and clears reviews. A future API needs scoped imports/updates, authorisation, conflict handling and version checks.

**Exercise 10:** explain why SocialBuzz should ask the analyser API for recommendations rather than directly writing into the analyser's article and embedding tables.

## 13 Preventing client data from mixing

A **tenant** is a customer organisation whose records must remain isolated from other customers. **Authentication** establishes the caller's identity. **Authorisation** determines which records and actions that identity may access. They are different checks.

The reviewed app has one shared workspace, one database path and one optional workspace password. It has no tenant/site columns or client membership model. Its password is not multi-client isolation. Do not connect several real clients to this unchanged shared collection.

| Layer | Required future behaviour |
| --- | --- |
| API identity | Authenticate the service/user making the request |
| Permissions | Verify membership or service authority for the requested tenant/site |
| Database records | Give content and related records explicit ownership |
| SQL | Scope reads and writes to authorised ownership |
| Relationships | Reject links, passages or reviews crossing prohibited client/site boundaries |
| Vector retrieval | Apply ownership restrictions to the authorised search scope |
| Cache | Include tenant, site and relevant version/configuration in cache identity |
| Jobs and exports | Preserve ownership on background work and downloads |
| Tests | Attempt cross-client access using the wrong credentials and IDs |

Do not trust a client merely because it submits `tenant_id=client-B`. The API must verify that the authenticated caller is allowed to access client B. Do not retrieve neighbours across every client and rely only on filtering the displayed answer afterward.

PostgreSQL **row-level security** can restrict which rows a database role can read or change. It supplements API checks. Table owners, superusers and roles with bypass privileges require care; a policy is ineffective if the application's connection bypasses it. Use an appropriately restricted application role and test real connection-pool/transaction behaviour.

If tenant context is set on a database connection, set and clear it safely within transactions; do not let pooled connections retain another request's tenant context. Exports, administrative routes and background workers need equivalent checks.

**Exercise 11:** client A requests an article ID belonging to client B. Describe the expected API outcome. Repeat the exercise for search, export, editing, link review and a background job. Merely hiding an item in the interface is not an acceptable answer.

## 14 A staged implementation plan for later

This section is a future work plan. Before carrying it out, obtain explicit authorisation for the particular implementation stage. Work on a feature branch and disposable data before touching real records.

### Stage 1 Agree requirements and ownership

Define what a tenant, website, article and content version mean. Decide who owns source text, which service can send it, and what data the analyser may retain. Decide whether one shared workspace remains sufficient. Write examples of permitted and forbidden cross-client actions.

Acceptance evidence: a reviewed ownership model and API contract. No database migration is needed merely to produce that design.

### Stage 2 Establish the current baseline

Inventory articles, reviews, metadata, application limits and runtime paths. Plan a consistent SQLite backup that includes review decisions, not just CSV content. Record representative searches, link exclusions and edit/import behaviour. Use independent relevance review where possible.

Acceptance evidence: a verified backup/recovery plan and expected functional behaviours. Current embeddings are not persistent, so there is no vector table to export.

### Stage 3 Design PostgreSQL schema and migration history

Choose relational columns, JSONB fields, scoped identifiers, foreign keys, uniqueness rules and vector/configuration versioning. Decide whether to retain one review decision or add immutable review events. Use a migration tool, such as Alembic, only after selecting the database-access approach. Neither Alembic nor SQLAlchemy is currently configured.

Acceptance evidence: schema review, rollback approach and decisions about ownership of existing unscoped SQLite records. Do not guess which client owns legacy data.

### Stage 4 Implement a storage adapter in a disposable environment

Add a PostgreSQL driver and connection pool, configuration and transaction handling. Implement equivalents of `articles`, `replace`, `save_article`, `reviews` and `review`, reconsidering global replacement for a scoped API. Preserve parameterised queries and explicit error handling.

Acceptance evidence: storage contract tests against a real disposable PostgreSQL database. Mock-only tests do not prove SQL, constraints or row policies work.

### Stage 5 Persist versioned passages and embeddings

Reuse the current token-bounded passage construction as a baseline. Store passage text and offsets with content/model/chunk configuration versions. Generate embeddings in Python and save them. Make unchanged-content processing idempotent, and replace or supersede stale vectors after an edit.

Acceptance evidence: repeated processing creates no accidental duplicates; restarts can retrieve saved vectors; edited content never returns evidence from an obsolete passage version.

### Stage 6 Implement and evaluate database retrieval

Begin with exact vector search. Scope every request and database operation to authorised ownership. Aggregate passage results into distinct articles, preserve self/existing/disallowed-link exclusions, and maintain a fair TF-IDF baseline. Only introduce an approximate index after benchmarking its speed, neighbour recall and filtering behaviour.

Acceptance evidence: representative retrieval results, relevance metrics, evidence-offset checks and cross-client isolation tests. The historical whole-article evaluation is not automatically a benchmark of the new passage scorer.

### Stage 7 Transfer approved data and rehearse cutover

Unpack the SQLite JSON payloads into the chosen schema. Assign explicit ownership, preserve intended article identity and review meaning, validate row counts and constraints, and regenerate embeddings. Test a consistent migration snapshot and prevent conflicting writes during cutover. Keep the previous system and backup available according to the rollback plan.

Acceptance evidence: reviewed counts/content checks, usable reviews, compatible vectors, documented rollback and a rehearsal on copies. Only then schedule an authorised real migration.

### Stage 8 Prepare AWS operations

Choose self-managed PostgreSQL or a managed service deliberately. For managed hosting, check extension availability and costs at implementation time. Configure private networking, least-privilege credentials, TLS, secrets, backup retention, recovery testing, monitoring and connection limits. The current EC2 template does not provision PostgreSQL.

Acceptance evidence: a reviewed infrastructure plan, cost estimate, successful backup restore and operational runbook. No AWS resources are authorised merely by reading this guide.

## 15 How to verify the future implementation

| Test area | Example acceptance check |
| --- | --- |
| Article transfer | Text, IDs, URLs and eligibility match the approved source snapshot |
| Transactions | A failed import leaves the previous collection consistent |
| Relationships | A review cannot reference a missing or differently owned article |
| Idempotency | Repeating one content-version import does not duplicate articles or vectors |
| Edit invalidation | Old content vectors and review state follow the documented invalidation policy |
| Vector compatibility | Queries do not mix different model spaces or unsupported chunk versions |
| Evidence | Stored character offsets reproduce the returned passage exactly |
| Ranking | Multiple matching passages do not consume all distinct-article result slots |
| Client isolation | Client A cannot read, search, edit, export or infer client B's records |
| Pooling | Tenant context cannot leak through reused connections |
| Restart and recovery | Saved articles, vectors and decisions remain usable after restart/restore |
| Retrieval quality | Precision and recall use a complete reviewed candidate set for each question |
| Performance | Latency, memory, index size and concurrency meet measured requirements |

Existing tests in `tests/test_application.py` cover several current behaviours, including import rollback, review invalidation and link exclusions. They do not constitute PostgreSQL or multi-tenant tests because those capabilities do not exist yet.

## 16 Working with data and backups safely

Git saves source history; it is not the backup system for runtime client records. The SQLite database and future production data should remain outside ordinary source commits. A CSV article export is not a full database backup because it omits editorial decisions and other state.

For SQLite, use its backup API or an appropriately controlled stopped-database procedure. WAL mode means copying only the main file during active writes can miss committed data. Follow `docs/aws-deployment.md` for the application's documented backup procedure and verify restoration with disposable data.

For a future PostgreSQL service, choose a backup/recovery strategy appropriate to its hosting model. Keep credentials, database dumps and personally identifying data out of chat and Git. Backups must retain ownership boundaries and access controls too.

A database change is not the same as a model-quality improvement. Re-evaluate retrieval after changes to model revision, chunking, distance metric, aggregation, filtering or approximate indexing.

## 17 Answer checks for the exercises

1. `DATABASE_PATH` controls the file location. Different paths normally mean separate SQLite databases with no automatic synchronisation.
2. Reviews use the directed pair of source and target as their key. Different pairs coexist; the same pair is updated through the upsert.
3. The SELECT returns saved decisions whose source is A01, most recently updated first. In the update query, the supplied article ID chooses the row.
4. The tests protect against partial/invalid replacement and stale decisions after article edits. Their names do not imply PostgreSQL is installed.
5. Old vectors describe old text. Clearing the cache forces representations to match current content on the next analysis.
6. Separate local files are independent. A PostgreSQL server can be shared by multiple app instances, although cache invalidation and tenant scoping still need design.
7. Tenant identity and body belong in deliberate relational columns; optional tags may fit JSONB; the 384 numbers fit a vector representation.
8. Each passage is a different model input and needs its own identity/offsets. Edits can change text, chunk boundaries and evidence locations.
9. The relationships are one-to-many. An article-version change must trigger an explicit policy for passages, vectors and dependent reviews.
10. An API preserves application ownership and validation boundaries. Direct table writes tightly couple services and can bypass business rules.
11. The caller should receive an authorised denial or a consistent not-found response without disclosure of another client's data. Enforce this in the API, queries, relationships and any background/retrieval paths.

## 18 Prompt to give your learning assistant

Copy this prompt together with the guide when starting a new learning session:

```text
I am learning backend development and AI engineering through the Semantic
Content Analyser project. Read this database learning guide and inspect the
current code before teaching me. The guide describes a specific source
snapshot, so verify file contents and report any differences.

Teach one concept at a time using this sequence:
1. Explain it simply.
2. Show the relevant file and function in our application.
3. Demonstrate a tiny concrete example.
4. Give me one small exercise and let me answer or run it.
5. Check my understanding before advancing.

Clearly distinguish current implementation from proposed future architecture.
Current storage is SQLite plus JSON article payloads and in-memory vectors.
Do not claim PostgreSQL, pgvector, jobs or tenant isolation already exist.
Do not treat assistant-proposed relevance labels as independent human labels.

Start in read-only teaching mode. Do not modify code, install packages,
run migrations, alter database records, provision AWS resources or access
SocialBuzz or client websites without my explicit instruction for that step.
Do not execute application startup or tests as a read-only inspection shortcut.

When I explicitly authorise implementation, work in a feature branch using
disposable data first. Explain each change, show the diff and the verification
evidence, preserve tenant boundaries and prepare a rollback plan. Do not infer
permission to modify production or another application's database.

Begin with Lesson 1: show where DATABASE_PATH is configured and explain the
difference between SQLite records, cached embeddings and model weights.
```

## 19 References and next reading

Project references:

- `semantic_analyser/config.py` — database and model settings.
- `semantic_analyser/storage.py` — actual SQLite schema and query methods.
- `semantic_analyser/schemas.py` — field validation and review request rules.
- `semantic_analyser/engine.py` — passages, cache, vectors and ranking.
- `semantic_analyser/api.py` — endpoints, session checks and mutation coordination.
- `tests/test_application.py` — current functional expectations.
- `docs/architecture.md` — application architecture and quality limits.
- `docs/aws-deployment.md` — persistence, backup and deployment instructions.
- `Semantic_Content_Analyser_Starter_Docs/README.md` — original roadmap and integration boundaries.

Official technical references:

- SQLite storage choices: https://www.sqlite.org/whentouse.html
- PostgreSQL relational concepts: https://www.postgresql.org/docs/current/tutorial-concepts.html
- PostgreSQL JSON and JSONB: https://www.postgresql.org/docs/current/datatype-json.html
- PostgreSQL row-level security: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- pgvector operations and indexing: https://github.com/pgvector/pgvector

Read the sources when implementing, because software versions, hosting support and operational requirements can change. The next learning action is to explain the actual three SQLite tables, not to install a new database immediately.
