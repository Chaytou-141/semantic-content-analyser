"""Consolidate supplied editorial reviews without inference, fetching, or relabelling."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

from scripts.phase3e_review import DECISIONS, FIELDS

ROOT = Path(__file__).resolve().parents[1]
USER = 'user_decision_after_ai_screening'
AI = 'chatgpt_ai_assisted'
IDENTITY_FIELDS = ['item_type', 'case_id', 'source_id', 'target_id']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_frozen(registry, manifest, evidence):
    """Cross-check portable Phase 3D evidence, not just CSV-supplied identifiers."""
    articles = {a['id'] for a in manifest['articles']}
    cases = {c['id']: c for c in manifest['cases']}
    recorded = {c['id']: c for c in evidence['cases']}
    if len(cases) != len(manifest['cases']) or set(cases) != set(recorded):
        raise ValueError('Frozen case sets differ.')
    if len(registry['cases']) != len(cases) or {c['id'] for c in registry['cases']} != set(cases):
        raise ValueError('Registry case set differs.')
    expected = {}
    for case in registry['cases']:
        cid = case['id']
        original = cases[cid]
        if case['kind'] != original['kind'] or set(case['rankings']) != {'embeddings', 'tfidf'}:
            raise ValueError('Frozen task kind/method mismatch.')
        source = original['source_id'] or ''
        if source and source not in articles:
            raise ValueError('Unknown source article.')
        for method, ids in case['rankings'].items():
            if ids != [r['id'] for r in recorded[cid]['results'][method]['ranking']]:
                raise ValueError('Frozen ranking order differs.')
            if len(ids) != len(set(ids)) or not set(ids) <= articles:
                raise ValueError('Unknown/duplicate ranked article.')
            for aid in ids:
                iid = f'C-{cid}-{aid}'
                expected[iid] = dict(item_id=iid, item_type='candidate', case_id=cid,
                                     source_id=source, target_id=aid)
    pairs = {}
    if set(evidence['overlap_rankings']) != {'embeddings', 'tfidf'} or set(registry['overlap_rankings']) != {'embeddings', 'tfidf'}:
        raise ValueError('Overlap methods differ.')
    for method, rows in evidence['overlap_rankings'].items():
        ids = registry['overlap_rankings'][method]
        if len(ids) != len(rows) or len(ids) != len(set(ids)):
            raise ValueError('Overlap ranking length/duplicates differ.')
        for iid, row in zip(ids, rows):
            pair = tuple(sorted([row['left'], row['right']]))
            if not set(pair) <= articles or pair[0] == pair[1]:
                raise ValueError('Invalid overlap article pair.')
            if iid in pairs and pairs[iid] != pair:
                raise ValueError('Overlap ID maps to different pairs.')
            pairs[iid] = pair
    for iid, (left, right) in pairs.items():
        expected[iid] = dict(item_id=iid, item_type='overlap', case_id='OVERLAP',
                             source_id=left, target_id=right)
    if len(set(pairs.values())) != len(pairs):
        raise ValueError('One overlap pair has multiple item IDs.')
    actual = {i['item_id']: i for i in registry['items']}
    if len(actual) != len(registry['items']) or actual != expected:
        raise ValueError('Registry item identities differ from original rankings.')


def load_csv(path, registry, mixed=False):
    data = Path(path).read_bytes()
    if len(data) > 1024 * 1024:
        raise ValueError('Review CSV exceeds 1 MiB.')
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''), strict=True)
    fields = FIELDS + (['review_origin'] if mixed else [])
    if reader.fieldnames != fields:
        raise ValueError(f'{Path(path).name}: incompatible columns; expected {fields}.')
    expected = {i['item_id']: i for i in registry['items']}
    result = {}
    for line, row in enumerate(reader, 2):
        prefix = f'{Path(path).name}: record {line}: '
        if None in row or any(v is None for v in row.values()):
            raise ValueError(prefix + 'missing/extra fields.')
        iid = row['item_id']
        if iid not in expected or iid in result:
            raise ValueError(prefix + 'unknown/duplicate item ID.')
        if row['schema_version'] != '1' or row['packet_id'] != registry['packet_id']:
            raise ValueError(prefix + 'packet/version mismatch.')
        if any(row[k] != expected[iid].get(k, '') for k in IDENTITY_FIELDS):
            raise ValueError(prefix + 'case/source/target does not match frozen rankings.')
        if row['decision'] not in DECISIONS:
            raise ValueError(prefix + 'unsupported decision.')
        if any(row[k] not in {'true', 'false'} for k in ['independence_attested', 'provisional_revealed']):
            raise ValueError(prefix + 'invalid boolean.')
        if not row['reviewer'].strip() or len(row['reviewer']) > 101 or len(row['reason']) > 2001:
            raise ValueError(prefix + 'invalid reviewer/reason.')
        if mixed and row['review_origin'] not in {USER, AI}:
            raise ValueError(prefix + 'unknown review provenance.')
        if mixed and row['review_origin'] == AI and row['independence_attested'] != 'false':
            raise ValueError(prefix + 'AI assessment cannot attest human independence.')
        result[iid] = row
    if not result:
        raise ValueError('Empty review file.')
    return result


def reconcile(users, mixed, registry):
    expected = {i['item_id'] for i in registry['items']}
    if set(mixed) != expected:
        raise ValueError('Mixed review must cover the original packet exactly; missing items: ' +
                         ', '.join(sorted(expected - set(mixed))))
    declared = {iid for iid, row in mixed.items() if row['review_origin'] == USER}
    if set(users) != declared:
        raise ValueError('User provenance does not match supplied user-decision file.')
    for iid, row in users.items():
        if any(row[k] != mixed[iid][k] for k in FIELDS):
            raise ValueError(f'{iid}: user decision/provenance was changed during reconciliation.')


def cutoff(ids, labels, k, eligible):
    rows = [labels.get(iid) for iid in ids[:k]]
    accepted = [bool(row and eligible(row) and row['decision'] in {'useful', 'not_useful'}) for row in rows]
    unresolved = [iid for iid, ok in zip(ids[:k], accepted) if not ok]
    complete = len(ids) >= k and not unresolved
    return {'value': sum(row['decision'] == 'useful' for row in rows) / k if complete else None,
            'resolved_eligible': sum(accepted), 'required': k, 'unresolved_item_ids': unresolved,
            'missing_result_slots': max(0, k-len(ids))}


def consolidate(registry, users, mixed):
    reconcile(users, mixed, registry)
    human = lambda r: r['review_origin'] == USER
    independent = lambda r: human(r) and r['independence_attested'] == 'true'
    metrics = []
    disagreements = []
    for case in registry['cases']:
        methods = {}
        for method, aids in case['rankings'].items():
            ids = [f'C-{case["id"]}-{aid}' for aid in aids]
            methods[method] = {scope: {f'precision@{k}': cutoff(ids, mixed, k, eligible) for k in [3, 5]}
                               for scope, eligible in [('human_screened_only', human), ('independence_attested_only', independent)]}
        metrics.append({'case_id': case['id'], 'kind': case['kind'], 'methods': methods})
        for k in [3, 5]:
            a, b = (case['rankings'][m][:k] for m in ['embeddings', 'tfidf'])
            disagreements.append({'case_id': case['id'], 'cutoff': k, 'shared_count': len(set(a)&set(b)),
                                  'same_order': a == b, 'minilm_only': [i for i in a if i not in b],
                                  'tfidf_only': [i for i in b if i not in a]})
    coverage = {}
    for kind in ['candidate', 'overlap']:
        items = [i for i in registry['items'] if i['item_type'] == kind]
        coverage[kind] = {'total': len(items), 'user_provided': sum(i['item_id'] in users for i in items),
                          'ai_assisted': sum(mixed[i['item_id']]['review_origin'] == AI for i in items)}
    available = {scope: sum(c['methods'][m][scope][f'precision@{k}']['value'] is not None
                            for c in metrics for m in ['embeddings', 'tfidf'] for k in [3, 5])
                 for scope in ['human_screened_only', 'independence_attested_only']}
    return {'packet_id': registry['packet_id'], 'ground_truth_status': 'Mixed screened-user and AI-assisted review; not independently validated',
            'provenance_counts': dict(Counter(r['review_origin'] for r in mixed.values())),
            'user_decision_counts': dict(Counter(r['decision'] for r in users.values())),
            'mixed_decision_counts_descriptive_only': dict(Counter(r['decision'] for r in mixed.values())),
            'coverage': coverage, 'independence_attested_user_decisions': sum(independent(r) for r in mixed.values()),
            'provisional_revealed_flags': sum(r['provisional_revealed'] == 'true' for r in mixed.values()),
            'protocol_note': 'false disclosure flags do not establish blindness; user origin explicitly says after AI screening. Identity and attestation are not externally verified.',
            'candidate_metrics': metrics, 'available_candidate_cutoffs_of_28': available,
            'overlap_usefulness_not_duplicate_accuracy': {
                m: {f'precision@{k}': cutoff(ids, mixed, k, human) for k in [3, 5]}
                for m, ids in registry['overlap_rankings'].items()},
            'ranking_disagreements': disagreements,
            'negative_candidates': [dict(item_id=iid, review_origin=r['review_origin'], reason=r['reason'])
                                    for iid, r in mixed.items() if r['item_type'] == 'candidate' and r['decision'] == 'not_useful'],
            'mixed_precision_computed': False, 'model_runs': 0, 'network_requests': 0}


def run(root, users_path, mixed_path):
    paths = {'registry': root/'evaluations/phase3e/packet-registry.json',
             'manifest': root/'evaluations/phase3d/editorial-review-set.json',
             'rankings': root/'evaluations/phase3d/results.json'}
    registry, manifest, evidence = [json.loads(paths[k].read_text(encoding='utf-8')) for k in paths]
    if (sha(paths['manifest']) != registry['provisional_manifest_sha256']
            or evidence['input_sha256'] != registry['input_sha256']
            or manifest['source_sha256'] != registry['input_sha256']):
        raise ValueError('Original manifest/corpus fingerprints differ.')
    if evidence['review_set_sha256'] != registry['provisional_manifest_sha256']:
        raise ValueError('Portable ranking evidence belongs to another manifest.')
    validate_frozen(registry, manifest, evidence)
    users = load_csv(users_path, registry)
    mixed = load_csv(mixed_path, registry, mixed=True)
    result = consolidate(registry, users, mixed)
    result['compatibility_findings'] = [
        'User CSV uses the original Phase 3E columns but all current decisions lack independent-human attestation.',
        'Mixed CSV adds review_origin and contains different reviewers; deliberately incompatible with the single independent-reviewer Phase 3E scorer.',
        'Phase 3F explicitly accepts the mixed schema for provenance/diagnostics only; AI rows never fill human metric gaps.']
    by_case = {c['id']: c for c in evidence['cases']}
    for item in result['negative_candidates']:
        meta = next(i for i in registry['items'] if i['item_id'] == item['item_id'])
        item['ranking_evidence'] = [dict(method=m, rank=rank, **row)
                                    for m, data in by_case[meta['case_id']]['results'].items()
                                    for rank, row in enumerate(data['ranking'], 1) if row['id'] == meta['target_id']]
    # Optional private-cache cross-check: never fetch or construct a model if absent.
    raw = root/'runtime/phase3d/analysis-results.json'
    result['private_ranking_cache_checked'] = raw.exists()
    if raw.exists() and sha(raw) != registry['ranking_evidence_sha256']:
        raise ValueError('Private ranking evidence fingerprint differs.')
    result['input_sha256'] = {**{k: sha(p) for k, p in paths.items()},
                              'user_csv': sha(users_path), 'mixed_csv': sha(mixed_path)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    base = ROOT/'evaluations/phase3f/inputs'
    parser.add_argument('--users', type=Path, default=base/'phase3e_user_decisions_14.csv')
    parser.add_argument('--mixed', type=Path, default=base/'phase3e_reconciled_mixed_review.csv')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = run(ROOT, args.users, args.mixed)
        if args.output:
            with args.output.open('x', encoding='utf-8') as file:
                file.write(json.dumps(result, indent=2)+'\n')
            print(json.dumps({'saved': str(args.output), 'coverage': result['coverage'],
                              'available_cutoffs': result['available_candidate_cutoffs_of_28']}))
        else:
            print(json.dumps(result, indent=2))
    except (ValueError, OSError, csv.Error, KeyError, TypeError) as error:
        parser.exit(2, str(error)+'\n')


if __name__ == '__main__':
    main()
