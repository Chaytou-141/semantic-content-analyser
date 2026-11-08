"""Synthetic fixtures test arithmetic; supplied reviews test real provenance/coverage."""
import copy
import csv
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.phase3e_review import FIELDS, load_reviews
from scripts.phase3f_evaluation import (AI, USER, ROOT, consolidate, cutoff, load_csv,
                                        reconcile, run, validate_frozen)


@pytest.fixture
def supplied():
    registry = json.loads((ROOT/'evaluations/phase3e/packet-registry.json').read_text())
    base = ROOT/'evaluations/phase3f/inputs'
    users = load_csv(base/'phase3e_user_decisions_14.csv', registry)
    mixed = load_csv(base/'phase3e_reconciled_mixed_review.csv', registry, mixed=True)
    return registry, users, mixed


def test_actual_inputs_keep_all_provenance_and_no_complete_human_cutoffs(supplied):
    registry, users, mixed = supplied
    result = consolidate(registry, users, mixed)
    assert result['provenance_counts'] == {AI: 45, USER: 14}
    assert result['coverage'] == {'candidate': {'total': 44, 'user_provided': 8, 'ai_assisted': 36},
                                  'overlap': {'total': 15, 'user_provided': 6, 'ai_assisted': 9}}
    assert result['available_candidate_cutoffs_of_28'] == {'human_screened_only': 0, 'independence_attested_only': 0}
    assert result['independence_attested_user_decisions'] == 0
    assert not result['mixed_precision_computed']
    assert all(m['value'] is None for methods in result['overlap_usefulness_not_duplicate_accuracy'].values() for m in methods.values())


def test_full_human_cutoff_arithmetic_and_unresolved():
    rows = {'a': {'decision': 'useful'}, 'b': {'decision': 'not_useful'}, 'c': {'decision': 'useful'}}
    assert cutoff(list('abc'), rows, 3, lambda r: True)['value'] == 2/3
    assert cutoff(list('abc'), rows, 5, lambda r: True)['value'] is None
    rows['c']['decision'] = 'unsure'
    assert cutoff(list('abc'), rows, 3, lambda r: True)['unresolved_item_ids'] == ['c']
    del rows['c']
    assert cutoff(list('abc'), rows, 3, lambda r: True)['value'] is None


def test_ai_rows_and_unattested_humans_cannot_fill_independent_gaps():
    rows = {i: {'decision': 'useful', 'review_origin': USER, 'independence_attested': 'true'} for i in 'abcde'}
    eligible = lambda r: r['review_origin'] == USER and r['independence_attested'] == 'true'
    assert cutoff(list('abcde'), rows, 5, eligible)['value'] == 1
    rows['b']['review_origin'] = AI
    assert cutoff(list('abcde'), rows, 3, eligible)['value'] is None
    rows['b']['review_origin'] = USER
    rows['c']['independence_attested'] = 'false'
    assert cutoff(list('abcde'), rows, 3, eligible)['value'] is None


def write(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


@pytest.mark.parametrize('mutation', [
    {'packet_id': 'wrong'}, {'case_id': 'R99'}, {'target_id': 'unknown'},
    {'source_id': 'wrong'}, {'item_id': 'O99'}, {'item_type': 'other'},
    {'schema_version': '2'}, {'decision': 'Relevant'}, {'reviewer': ''},
    {'provisional_revealed': 'maybe'}, {'review_origin': 'human'},
    {'review_origin': AI, 'independence_attested': 'true'}])
def test_incompatible_or_tampered_rows_rejected(tmp_path, supplied, mutation):
    registry, _, mixed = supplied
    row = dict(next(iter(mixed.values())))
    row.update(mutation)
    path = tmp_path/'bad.csv'; write(path, [row], FIELDS+['review_origin'])
    with pytest.raises(ValueError):
        load_csv(path, registry, mixed=True)


def test_missing_extra_columns_and_duplicate_rows_rejected(tmp_path, supplied):
    registry, users, _ = supplied
    row = next(iter(users.values()))
    path = tmp_path/'bad.csv'
    for fields, rows in [(FIELDS[:-1], [{k:v for k,v in row.items() if k in FIELDS[:-1]}]),
                         (FIELDS+['extra'], [{**row, 'extra': 'x'}]), (FIELDS, [row, row])]:
        write(path, rows, fields)
        with pytest.raises(ValueError): load_csv(path, registry)
    path.write_text(','.join(FIELDS)+'\n"unterminated', encoding='utf-8')
    with pytest.raises(csv.Error): load_csv(path, registry)


@pytest.mark.parametrize('change', ['decision', 'reason', 'reviewer', 'independence_attested', 'review_origin', 'missing'])
def test_reconciliation_must_preserve_every_user_field(supplied, change):
    registry, users, mixed = supplied
    mixed = copy.deepcopy(mixed)
    iid = next(iter(users))
    if change == 'missing': del mixed[iid]
    elif change == 'review_origin': mixed[iid][change] = AI
    else: mixed[iid][change] = 'changed'
    with pytest.raises(ValueError): reconcile(users, mixed, registry)


def test_original_scorer_stays_strict(supplied):
    registry, _, _ = supplied
    base = ROOT/'evaluations/phase3f/inputs'
    for name in ['phase3e_user_decisions_14.csv', 'phase3e_reconciled_mixed_review.csv']:
        with pytest.raises(ValueError): load_reviews(base/name, registry)


@pytest.mark.parametrize('change', ['rank', 'source', 'unknown_article', 'overlap', 'missing_item', 'duplicate_case'])
def test_portable_evidence_cross_checks(supplied, change):
    registry, _, _ = supplied
    registry = copy.deepcopy(registry)
    manifest = json.loads((ROOT/'evaluations/phase3d/editorial-review-set.json').read_text())
    evidence = json.loads((ROOT/'evaluations/phase3d/results.json').read_text())
    if change == 'rank': registry['cases'][0]['rankings']['embeddings'].reverse()
    if change == 'source': registry['items'][0]['source_id'] = 'wrong'
    if change == 'unknown_article': registry['cases'][0]['rankings']['embeddings'][0] = 'wrong'
    if change == 'overlap': registry['overlap_rankings']['tfidf'].reverse()
    if change == 'missing_item': registry['items'].pop()
    if change == 'duplicate_case': registry['cases'].append(registry['cases'][0])
    with pytest.raises(ValueError): validate_frozen(registry, manifest, evidence)


def test_actual_report_reproducible_and_cli_refuses_overwrite(tmp_path):
    base = ROOT/'evaluations/phase3f'
    result = run(ROOT, base/'inputs/phase3e_user_decisions_14.csv', base/'inputs/phase3e_reconciled_mixed_review.csv')
    saved = json.loads((base/'results.json').read_text())
    # Presence of an ignored authorised cache varies between checkouts, not metrics.
    result.pop('private_ranking_cache_checked'); saved.pop('private_ranking_cache_checked')
    assert result == saved
    out = tmp_path/'keep.json'; out.write_text('preserve')
    process = subprocess.run([sys.executable, '-B', '-m', 'scripts.phase3f_evaluation', '--output', str(out)],
                             cwd=ROOT, capture_output=True)
    assert process.returncode == 2 and out.read_text() == 'preserve' and b'Traceback' not in process.stderr


def test_error_annotations_reference_supplied_negative_labels_and_frozen_passages(supplied):
    registry, _, mixed = supplied
    annotations = json.loads((ROOT/'evaluations/phase3f/error-analysis.json').read_text(encoding='utf-8'))
    evidence = json.loads((ROOT/'evaluations/phase3d/results.json').read_text())
    cases = {c['id']: c for c in evidence['cases']}
    items = {i['item_id']: i for i in registry['items']}
    assert len(annotations['examples']) == 12
    for item in annotations['examples']:
        original = mixed[item['item_id']]
        assert item['decision'] == original['decision'] == 'not_useful'
        assert item['review_origin'] == original['review_origin']
        assert all(item[k] == items[item['item_id']][k] for k in ['source_id', 'target_id', 'case_id'])
        for ref in item['frozen_evidence']:
            if item['case_id'] != 'OVERLAP':
                row = cases[item['case_id']]['results'][ref['method']]['ranking'][ref['rank']-1]
                assert row['id'] == item['target_id']
                assert row['passage_sha256'] == ref['target_passage_sha256']
            else:
                row = evidence['overlap_rankings'][ref['method']][ref['rank']-1]
                pair = {row['left']: row['left_passage_sha256'], row['right']: row['right_passage_sha256']}
                assert pair[item['source_id']] == ref['source_passage_sha256']
                assert pair[item['target_id']] == ref['target_passage_sha256']
            assert ref['score'] == row['score']
