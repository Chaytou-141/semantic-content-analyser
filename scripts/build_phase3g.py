"""Build a new offline packet stripped of model metadata and past decisions."""
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path

from scripts.build_phase3e import build as frozen_build, digest, script_json
from scripts.phase3f_evaluation import validate_frozen
from scripts.phase3g_review import ROOT, VERSION, validate_registry


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def build(root=ROOT):
    frozen, old = frozen_build(root)
    recorded = json.loads((root/'evaluations/phase3e/packet-registry.json').read_text())
    if frozen != recorded:
        raise ValueError('Frozen Phase 3E registry changed.')
    manifest = json.loads((root/'evaluations/phase3d/editorial-review-set.json').read_text())
    evidence = json.loads((root/'evaluations/phase3d/results.json').read_text())
    validate_frozen(frozen, manifest, evidence)
    phase3f = root/'evaluations/phase3f/results.json'
    consolidation = json.loads(phase3f.read_text())
    if consolidation['packet_id'] != frozen['packet_id']:
        raise ValueError('Phase 3F evidence refers to a different packet.')
    candidates = [i for i in old['items'] if i['item_type'] == 'candidate']
    article_ids = sorted({i[k] for i in candidates for k in ['source_id', 'target_id'] if i[k]})
    aliases = {aid: f'A{n:03}' for n, aid in enumerate(article_ids, 1)}
    # Stable hash ordering never uses score, method or previous relevance labels.
    candidates.sort(key=lambda item: fingerprint(['phase3g-order', item['item_id']]))
    mapping, items = [], []
    for n, original in enumerate(candidates, 1):
        meta = {'item_id': f'G{n:03}', 'case_id': original['case_id'],
                'source_id': aliases[original['source_id']] if original['source_id'] else '',
                'target_id': aliases[original['target_id']]}
        mapping.append({**meta, 'original_item_id': original['item_id']})
        pairs = {(e['source_passage'], e['target_passage']) for e in original['evidence']}
        passages = [{'source_passage': a, 'target_passage': b} for a, b in sorted(pairs, key=lambda p: fingerprint(p))]
        items.append({**meta, 'kind': original['kind'], 'question': original['question'],
                      'criterion': original['criterion'], 'existing_link': original['existing_link'], 'passages': passages})
    lookup = {i['original_item_id']: i['item_id'] for i in mapping}
    registry = {'schema_version': VERSION, 'frozen_packet_id': frozen['packet_id'],
                'frozen_registry_sha256': digest(root/'evaluations/phase3e/packet-registry.json'),
                'phase3f_results_sha256': digest(phase3f), 'article_aliases': aliases, 'items': mapping,
                'cases': [{'id': c['id'], 'kind': c['kind'], 'rankings': {
                    m: [lookup[f'C-{c["id"]}-{aid}'] for aid in ids[:5]] for m, ids in c['rankings'].items()}}
                    for c in frozen['cases']]}
    payload = {'schema_version': VERSION, 'items': items, 'articles': {
        aliases[aid]: {k: old['articles'][aid][k] for k in ['title', 'url', 'body']} for aid in article_ids}}
    registry['review_content_sha256'] = fingerprint(payload)
    registry['packet_id'] = fingerprint(registry)
    payload['packet_id'] = registry['packet_id']
    validate_registry(registry, frozen)
    if len(items) != 44 or {c['id'] for c in registry['cases']} != {'R01','R02','R03','R04','L01','L02','L03'}:
        raise ValueError('Expected all 44 recommendation judgements across seven tasks.')
    return registry, payload


def render(root, payload):
    assets = root/'evaluations/phase3g'
    js = (assets/'reviewer.js').read_text(encoding='utf-8')
    template = (assets/'reviewer.html').read_text(encoding='utf-8')
    css = (root/'evaluations/phase3e/reviewer.css').read_text(encoding='utf-8')
    signature = base64.b64encode(hashlib.sha256(js.encode()).digest()).decode()
    # The coordinator registry is deliberately never embedded in the reviewer file.
    substitutions = {'STYLE': css, 'SCRIPT_HASH': signature, 'DATA': script_json(payload), 'SCRIPT': js}
    return re.sub(r'@@(STYLE|SCRIPT_HASH|DATA|SCRIPT)@@', lambda match: substitutions[match[1]], template)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'runtime/phase3g/blind-review.html')
    args = parser.parse_args()
    try:
        registry, payload = build()
        target = ROOT/'evaluations/phase3g/coordinator-registry.json'
        if target.exists() and json.loads(target.read_text()) != registry:
            raise ValueError('Coordinator registry differs; version the round instead of overwriting.')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as file:
            file.write(render(ROOT, payload))
        if not target.exists():
            target.write_text(json.dumps(registry, indent=2)+'\n', encoding='utf-8')
        print(f'Built 44 unreviewed recommendation cases (no overlap cases): {args.output}')
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, str(error)+'\n')


if __name__ == '__main__':
    main()
