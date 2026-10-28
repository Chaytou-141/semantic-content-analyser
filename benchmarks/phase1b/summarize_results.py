"""Render the portable results without running inference or changing application data."""

import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent


def render():
    bundle = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    verification = json.loads((HERE / "verification.json").read_text(encoding="utf-8"))
    lines = ["# Phase 1B measured results", "", f"Application commit: `{bundle['base_commit']}`.", "",
             "All times are local Windows measurements with a cached, offline real model. "
             "See README.md for methodology and limitations. No production defaults changed.", "",
             "## Capacity", "", "| Scenario | Characters | Passages | Import accepted? |",
             "| --- | ---: | ---: | --- |"]
    for row in verification["capacity"]["scenarios"]:
        name = f"{row['articles']} articles" + (f", length ×{row['length_multiplier']}" if "length_multiplier" in row else "")
        lines.append(f"| {name} | {row['characters']:,} | {row['passages']} | {'yes' if row['accepted'] else 'no: character limit'} |")
    lines += ["", "The 40-article scenario uses four duplicated length fixtures with new IDs. "
              "Length multipliers duplicate prose for capacity only; neither is quality data.", "",
              "All 269 original passages retain exact body offsets and final article tokens. "
              f"Maximum encoded title/body input: {verification['capacity']['max_combined_tokens']} tokens (limit 256).", "",
              "## Cold stages", "", "Wall/CPU seconds; one fresh subprocess per profile. "
              "Collection tokenization diagnostic is timed separately and excluded from the reconstructed first-use total.", "",
              "| Articles | Method | Imports wall/CPU | Model load wall/CPU | Prepare wall/CPU | Encode wall/CPU | First use total wall/CPU |",
              "| ---: | --- | ---: | ---: | ---: | ---: | ---: |"]
    for run in bundle["runs"]:
        ops = {r["operation"]: r for r in run["measurements"]}
        names = ["imports_and_thread_configuration", "load_model_from_local_disk_cache", "prepare_passages_and_tfidf", "encode_collection_first_time", "first_search_after_index"]
        values = [ops[n] for n in names if n in ops]
        cells = [f"{ops[n]['wall_s']:.3f}/{ops[n]['cpu_s']:.3f}" if n in ops else "not needed" for n in names[:4]]
        total = f"{sum(r['wall_s'] for r in values):.3f}/{sum(r['cpu_s'] for r in values):.3f}"
        lines.append(f"| {run['count']} | {run['method']} | " + " | ".join(cells) + f" | {total} |")
    lines += ["", "The total is a sum of measured stages, not an independently timed HTTP request. "
              "Model load includes lazy Sentence Transformers imports. A first HTTP comparison on the "
              f"36-article collection, with model already loaded by UI checks but index cold, reported {verification['real_model_http_36_articles']['search']['elapsed_ms']:,} ms.", "",
              "## Warm operations", "", "Median wall/CPU milliseconds. Search n=5; links/overlap n=3. "
              "Zero CPU measurements reflect timer granularity, not free computation.", "",
              "| Articles | Method | Search wall/CPU | Links wall/CPU | Overlap wall/CPU |",
              "| ---: | --- | ---: | ---: | ---: |"]
    for run in bundle["runs"]:
        cells = []
        for prefix in ["warm_search_", "links_warm_", "overlaps_warm_"]:
            rows = [r for r in run["measurements"] if r["operation"].startswith(prefix)]
            cells.append(f"{statistics.median(r['wall_s'] for r in rows)*1000:.3f}/{statistics.median(r['cpu_s'] for r in rows)*1000:.3f}")
        lines.append(f"| {run['count']} | {run['method']} | " + " | ".join(cells) + " |")
    lines += ["", "Raw JSON retains all individual samples; small n does not support p95/p99 claims.", "",
              "## Process memory", "", "MiB (1,048,576 bytes). Baseline includes measured cold/warm "
              "operations and matrix diagnostics, before the additional planted-paragraph probes.", "",
              "| Articles | Method | OS peak working set | Current working set | Current private bytes | OS peak commit |",
              "| ---: | --- | ---: | ---: | ---: | ---: |"]
    for run in bundle["runs"]:
        mem = run["baseline_process_memory_before_probes"]
        vals = [f"{mem[k]/1048576:.1f}" for k in ["peak_rss_bytes", "rss_bytes", "private_bytes", "peak_commit_bytes"]]
        lines.append(f"| {run['count']} | {run['method']} | " + " | ".join(vals) + " |")
    overall_peak = max(run["final_process_memory"]["peak_rss_bytes"] for run in bundle["runs"]) / 1048576
    lines += ["", f"Including the additional probes, the largest OS process peak was {overall_peak:.1f} MiB. "
              "These are per-process readings, not total system RAM or multi-visitor deployment sizing. "
              "TF-IDF still loads the model because the current passage splitter uses its tokenizer.", "",
              "## Same-score matrix diagnostic", "", "No production optimization was applied.", "",
              "| Articles | Method | Full entries/bytes | Source-only entries/bytes | Full ms | Source-only ms | Equivalent? |",
              "| ---: | --- | ---: | ---: | ---: | ---: | --- |"]
    for run in bundle["runs"]:
        m = run["matrix_diagnostic"]
        ops = {r["operation"]: r for r in run["measurements"]}
        lines.append(f"| {run['count']} | {run['method']} | {m['full_shape'][0]*m['full_shape'][1]:,}/{m['full_bytes']:,} | "
                     f"{m['source_shape'][0]*m['source_shape'][1]:,}/{m['source_bytes']:,} | "
                     f"{ops['diagnostic_full_similarity_matrix']['wall_s']*1000:.3f} | "
                     f"{ops['diagnostic_source_only_matrix']['wall_s']*1000:.3f} | {m['same_source_scores']} |")
    lines += ["", "Matrix timings are single micro-measurements and sensitive to scheduling/cache effects. "
              "They establish numerical equivalence and smaller allocation, not a reliable production speedup factor.", "",
              "## Constructed intent-mismatch probes (36-article profiles)", "",
              "The same cycling article is evaluated at three prefix lengths, with/without one "
              "39-word espresso paragraph. The original cycling article B24 is replaced, keeping count constant. "
              "The query asks about two baristas' espresso layout. No independent human labels are used.", "",
              "| Method | Words | Planted paragraph? | Passages | Max score | Mean score | Passage fraction ≥0.5 | Rank in top20 |",
              "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |"]
    for run in bundle["runs"]:
        if run["count"] != 36:
            continue
        for p in run["synthetic_false_positive_probes"]:
            lines.append(f"| {run['method']} | {p['body_words']} | {p['planted_cafe_paragraph']} | {p['passages']} | "
                         f"{p['max_similarity']:.4f} | {p['mean_similarity']:.4f} | {p['fraction_passages_ge_0_5']:.2f} | {p['rank_in_top20'] or 'outside 20'} |")
    lines += ["", "Length alone increased the semantic maximum from 0.1820 to 0.2905 in this case, "
              "without producing a high-scoring match. Planting one related paragraph moved both methods "
              "into the top two despite different whole-article intent. The longest planted case has "
              "MiniLM max 0.6598 versus mean 0.2309; TF-IDF max 0.5445 versus mean 0.0934. "
              "Scores are not monotonic with length because passage boundaries change and TF-IDF refits. "
              "This shows a risk for whole-article/link intent decisions, not a corpus-wide false-positive "
              "rate. A relevant passage can be a legitimate result for passage search. Do not replace "
              "max scoring with the mean or choose a threshold from this constructed case alone.", "",
              "## Verification", "",
              "- Existing pytest suite: " + verification["pytest"]["output"].strip().splitlines()[-1] + ".",
              "- Existing JavaScript syntax check passed.",
              "- Latest UI browser smoke passed: comparison, links/exclusions/review save, overlap, "
              "live filters, shortcut, editor/unsaved guard, evaluation and mobile/import dialog.",
              "- Real MiniLM HTTP search/links/overlap passed against the isolated 36-article collection.",
              "- Real tokenizer: all 269 offsets/tails checked, no combined input above 256 tokens.",
              "- Token-dense collection: import accepted (200), analysis rejected (422, >800 passages). "
              "This confirms the current delayed-admission defect in the disposable database only.",
              f"- Preservation: {verification['preservation']['checked_files']} original source/data/database files hashed; "
              f"{len(verification['preservation']['changed'])} changed.",
              "- Temporary server stopped; no existing server/database reset; no infrastructure or deployment executed.", "",
              "The corpus and probes are synthetic. Historical development metrics remain untouched, "
              "and this phase does not add an accuracy, recall or production recommendation-quality claim.", ""]
    (HERE / "results-summary.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    render()
