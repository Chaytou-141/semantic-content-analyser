"""New, metadata-blind editorial round. Standard library; no inference/network."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = '3g-1'
FIELDS = ['schema_version', 'packet_id', 'item_id', 'case_id', 'source_id', 'target_id',
          'reviewer', 'human_attested', 'prior_exposure', 'decision', 'reason']
DECISIONS = {'useful', 'not_useful', 'unsure', 'unreviewed'}
EXPOSURES = {'unreported', 'none', 'screened', 'unsure'}


def validate_registry(registry, frozen):
    """Reconstruct the exact top-five union and ranking-item mapping from Phase 3E."""
    if registry['schema_version'] != VERSION or registry['frozen_packet_id'] != frozen['packet_id']:
        raise ValueError('Wrong registry version/frozen packet.')
    unsigned = {k: v for k, v in registry.items() if k != 'packet_id'}
    if registry['packet_id'] != hashlib.sha256(json.dumps(unsigned, sort_keys=True, ensure_ascii=False).encode()).hexdigest():
        raise ValueError('Coordinator registry fingerprint differs.')
    originals = {i['item_id']: i for i in frozen['items'] if i['item_type'] == 'candidate'}
    mapped = {i['original_item_id']: i for i in registry['items']}
    ids = [i['item_id'] for i in registry['items']]
    if set(mapped) != set(originals) or len(mapped) != len(registry['items']) or len(set(ids)) != len(ids):
        raise ValueError('New packet must cover each frozen recommendation exactly once.')
    aliases = registry['article_aliases']
    article_ids = {i[k] for i in originals.values() for k in ['source_id', 'target_id'] if i[k]}
    if set(aliases) != article_ids or len(set(aliases.values())) != len(aliases):
        raise ValueError('Article aliases must be unique.')
    for oid, item in mapped.items():
        original = originals[oid]
        if (item['case_id'] != original['case_id'] or item['target_id'] != aliases[original['target_id']]
                or item['source_id'] != (aliases[original['source_id']] if original['source_id'] else '')):
            raise ValueError('Source/target/task mapping differs from frozen packet.')
    expected = []
    for case in frozen['cases']:
        expected.append({'id': case['id'], 'kind': case['kind'], 'rankings': {
            method: [mapped[f'C-{case["id"]}-{aid}']['item_id'] for aid in aids[:5]]
            for method, aids in case['rankings'].items()}})
    if registry['cases'] != expected:
        raise ValueError('Frozen top-five ranking mapping differs.')


def load_reviews(path, registry):
    raw = Path(path).read_bytes()
    if len(raw) > 1024*1024:
        raise ValueError('Review CSV exceeds 1 MiB.')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    if reader.fieldnames != FIELDS:
        raise ValueError('Use the new Phase 3G CSV; prior/mixed review schemas are incompatible.')
    expected = {i['item_id']: i for i in registry['items']}
    reviews, provenance = {}, set()
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError('Malformed CSV row: missing/extra fields.')
        iid = row['item_id']
        if iid not in expected or iid in reviews:
            raise ValueError('Unknown/duplicate review item.')
        if row['schema_version'] != VERSION or row['packet_id'] != registry['packet_id']:
            raise ValueError('Review belongs to a different packet/version.')
        if any(row[k] != expected[iid][k] for k in ['case_id', 'source_id', 'target_id']):
            raise ValueError('Source, target or task differs from frozen packet.')
        if row['decision'] not in DECISIONS or row['human_attested'] not in {'true', 'false'} or row['prior_exposure'] not in EXPOSURES:
            raise ValueError('Unsupported decision/provenance value.')
        name = row['reviewer'].strip()
        if len(row['reviewer']) > 101 or len(row['reason']) > 2001:
            raise ValueError('Reviewer/reason too long.')
        if row['decision'] != 'unreviewed' and not name:
            raise ValueError('Decisions require a reviewer ID. Anonymous drafts can be resumed in the packet.')
        provenance.add((name, row['human_attested'], row['prior_exposure']))
        reviews[iid] = row
    if not reviews or len(provenance) != 1:
        raise ValueError('Use one reviewer and consistent attestation/exposure per CSV.')
    return reviews


def eligible(row):
    return bool(row and row.get('reviewer', '').strip() and row.get('human_attested') == 'true'
                and row.get('prior_exposure') == 'none')


def score(registry, reviews):
    cases = []
    for case in registry['cases']:
        methods = {}
        for method, ids in case['rankings'].items():
            methods[method] = {}
            for k in [3, 5]:
                selected = ids[:k]
                unresolved = []
                useful = 0
                for iid in selected:
                    row = reviews.get(iid)
                    if not row or row['decision'] in {'unsure', 'unreviewed'}:
                        unresolved.append({'item_id': iid, 'reason': 'missing_or_unresolved_decision'})
                    elif not eligible(row):
                        unresolved.append({'item_id': iid, 'reason': 'ineligible_reviewer_provenance'})
                    elif row['decision'] == 'useful':
                        useful += 1
                methods[method][f'precision@{k}'] = {
                    'value': useful/k if len(selected) == k and not unresolved else None,
                    'eligible_useful': useful, 'required': k, 'unresolved': unresolved,
                    'missing_result_slots': max(0, k-len(selected))}
        cases.append({'case_id': case['id'], 'kind': case['kind'], 'methods': methods})
    aggregates = {}
    for kind in ['related', 'internal_link']:
        group = [c for c in cases if c['kind'] == kind]
        aggregates[kind] = {}
        for k in [3, 5]:
            paired = [c for c in group if all(c['methods'][m][f'precision@{k}']['value'] is not None
                                             for m in ['embeddings', 'tfidf'])]
            aggregates[kind][f'precision@{k}'] = {
                'paired_complete_cases': [c['case_id'] for c in paired], 'total_cases': len(group),
                'methods': {m: {
                    'all_case_mean': sum(c['methods'][m][f'precision@{k}']['value'] for c in paired)/len(group)
                                     if group and len(paired) == len(group) else None,
                    'paired_complete_case_mean': sum(c['methods'][m][f'precision@{k}']['value'] for c in paired)/len(paired)
                                                 if paired else None}
                    for m in ['embeddings', 'tfidf']}}
    counts = Counter(reviews.get(i['item_id'], {}).get('decision', 'unreviewed') for i in registry['items'])
    return {'packet_id': registry['packet_id'], 'label_scope': 'New human round; identity/exposure self-reported, not formally authenticated',
            'protocol': 'No retrieval metadata or previous judgements embedded in reviewer HTML. Corpus/task selection and passage selection remain model-derived.',
            'reviewer_ids': sorted({r['reviewer'].strip() for r in reviews.values()}),
            'prior_exposure': sorted({r['prior_exposure'] for r in reviews.values()}),
            'decision_counts': dict(counts), 'eligible_resolved_decisions': sum(eligible(r) and r['decision'] in {'useful', 'not_useful'} for r in reviews.values()),
            'case_metrics': cases, 'aggregates': aggregates, 'overlap_included': False,
            'ai_assisted_labels_used': False, 'formally_blinded_independence_claimed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviews', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        registry = json.loads((ROOT/'evaluations/phase3g/coordinator-registry.json').read_text())
        frozen = json.loads((ROOT/'evaluations/phase3e/packet-registry.json').read_text())
        validate_registry(registry, frozen)
        result = score(registry, load_reviews(args.reviews, registry))
        if args.output:
            with args.output.open('x', encoding='utf-8') as file:
                file.write(json.dumps(result, indent=2)+'\n')
            print(f'Saved metrics: {args.output}')
        else:
            print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError, csv.Error, TypeError) as error:
        parser.exit(2, str(error)+'\n')


if __name__ == '__main__':
    main()
