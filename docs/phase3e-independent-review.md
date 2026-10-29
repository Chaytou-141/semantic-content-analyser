# Phase 3E preparation: independent editorial review

29 October 2026, Australia/Sydney. Evidence baseline: `771c4cb`; later website-first
application commit `036f173` is retained unchanged. Local commit subject:
`Prepare independent SEO review packet and human-label scoring`.

The new standalone packet is `runtime/phase3e/independent-review.html`. Open in a browser,
enter reviewer identity/attestation, mark Useful/Not useful/Unsure and optionally explain.
Export CSV and submit the file to the coordinator or score it locally. It does not send
messages, upload reviews, modify an application collection or call a model/website.

Complete instructions and reproducible commands: [Phase 3E guide](../evaluations/phase3e/README.md).
The old `runtime/phase3d/editorial-review.html` and Phase 3D data are not rewritten.

## Design decisions

- One decision per task/target (44 candidates), shared across retrieval methods, plus
  15 overlap pairs. Evidence alternatives retain both methods' recorded passages.
  Sorting is by task/identifier, not best score. Retrieval information and provisional
  AI notes are optional disclosures; human answers start empty and are stored separately.
- Related-content tasks have a source question, not a source article. Link tasks show
  both source and target; overlap shows both articles and link status in both directions.
  All statuses refer to the frozen selected collection, not a new live check.
- Full saved text is expandable, with supporting passages visible. All fetched text is
  inserted with textContent; JSON embedding escapes script delimiters. The standalone
  packet has a hashed inline script/CSP and no external fonts/resources/network calls.
- Local drafts are keyed by the frozen packet fingerprint; CSV backup/resume handles
  browser transfer. Import validates the entire file before replacing a draft. Reasons
  support commas, quotes and newlines. Spreadsheet-sensitive free text is escaped.
- Human exports contain no AI relevance labels. A disclosure flag records viewing AI
  notes. Attestation/identity are self-reported; software cannot certify independence.
- Precision uses only resolved human Useful/Not useful choices. Unsure/unreviewed remain
  listed and make affected cutoffs unavailable. Group summaries show coverage. Overlap
  usefulness precision is separate from relevance and does not measure duplicate accuracy.
- Scoring uses saved rankings/registry, not inference. Existing metrics outputs are
  protected against overwrite. Multiple reviewers require separate exports/adjudication;
  no automatic consensus or relabelling of Phase 3D was added.

## Files

- `scripts/build_phase3e.py`: verifies frozen input/label/evidence hashes and exact
  passage substrings, creates the offline HTML and metadata-only registry.
- `evaluations/phase3e/reviewer.{html,css,js}`: packet assets, manual choices/drafts/CSV.
- `evaluations/phase3e/packet-registry.json`: 59 identities and original method rankings;
  no human decisions and no original article bodies.
- `scripts/phase3e_review.py`, `scripts/score_phase3e.py`: validation and human-only metrics.
- `tests/test_phase3e_review.py`, `scripts/verify_phase3e.py`: targeted synthetic checks.

## Verification and limitations

Fourteen targeted tests passed. Browser checks passed all 59 empty initial choices,
AI/human separation, source evidence display, decision/optional reason entry, draft
reload, CSV download, fresh-context resume, invalid-import atomicity, filtering and
390px layout. Quote/newline/formula-sensitive text round-tripped safely. Partial reviews
left precision unavailable. Follow-up strict CSV checks rejected malformed quoted input
cleanly. No page errors/external HTTP requests were observed.

All **1,254 protected files** remain unchanged, including application/UI source, saved
development databases, Phase 3C/3D raw samples and evaluation/benchmark history. No full
suite, MiniLM/tokenizer, historical benchmark, installation, infrastructure, push or
deployment was run. Browser/test review files are explicitly **synthetic**, not human
judgements. Actual completed independent reviews received: **0**.

The corpus remains one authorised WordPress site. Preparing a reviewer does not validate
XML/non-WordPress compatibility, recommendation accuracy or release readiness. Full
article text remains local and must not be publicly redistributed without permission.
Offline drafts/evaluation artifacts are not covered by application workspace expiration.
Next: receive an independently completed CSV, inspect its provenance/coverage/Unsure
items, adjudicate disagreements, then compare human-labelled results without changing
the frozen ranks or rerunning the model.
