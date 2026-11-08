"""Offline capacity/real-tokenizer checks; imports no API or database store."""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from semantic_analyser.engine import AnalysisEngine
from semantic_analyser.schemas import Article
from semantic_analyser.storage import validate_collection


def main():
    rows = list(csv.DictReader((Path(__file__).parent / "articles.csv").open(encoding="utf-8")))
    articles = [Article(**{**row, "eligible": True, "existing_links": []}) for row in rows]
    engine = AnalysisEngine()
    chunks = [p for article in articles for p in engine.passages(article)]
    by_id = {a.id: a for a in articles}
    for chunk in chunks:
        assert chunk["text"] == by_id[chunk["article_id"]].body[chunk["start"]:chunk["end"]]
    max_tokens = max(len(engine.model.tokenizer.encode(p["model_text"], add_special_tokens=True)) for p in chunks)
    assert max_tokens <= 256
    for article in articles:
        last = [p for p in chunks if p["article_id"] == article.id][-1]
        assert last["end"] == len(article.body)
    scenarios = []
    for count in [30, 36, 40]:
        selection = list(articles[:count])
        if count == 40:
            selection += [a.model_copy(update={"id": f"EXTRA{i}"}) for i, a in enumerate(articles[-4:])]
        try:
            validate_collection(selection)
            accepted, reason = True, None
        except ValueError as error:
            accepted, reason = False, str(error)
        scenarios.append({"articles": count, "characters": sum(len(a.title) + len(a.body) for a in selection),
                          "accepted": accepted, "reason": reason,
                          "passages": sum(len(engine.passages(a)) for a in selection),
                          "note": "36 originals plus four duplicated length fixtures with new IDs" if count == 40 else "original ordered prefix"})
    # Probe growing original articles without changing the saved corpus. Repeated
    # prose here is solely a capacity fixture, never a quality evaluation input.
    for multiplier in [1.25, 1.5, 2.0]:
        expanded = []
        for article in articles:
            size = int(len(article.body) * multiplier)
            body = (article.body + "\n\n" + article.body)[:size]
            expanded.append(article.model_copy(update={"body": body}))
        try:
            validate_collection(expanded)
            accepted = True
        except ValueError:
            accepted = False
        scenarios.append({"articles": 36, "length_multiplier": multiplier, "characters": sum(len(a.title) + len(a.body) for a in expanded),
                          "accepted": accepted, "passages": sum(len(engine.passages(a)) for a in expanded),
                          "note": "repeated-prose engineering capacity fixture"})
    print(json.dumps({"real_tokenizer_passages_checked": len(chunks), "max_combined_tokens": max_tokens,
                      "all_offsets_and_tails_preserved": True, "scenarios": scenarios}))


if __name__ == "__main__":
    main()
