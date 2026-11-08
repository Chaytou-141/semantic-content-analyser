"""Human-only review CSV validation and scoring. Standard library; no model/network."""
import csv
import io
import json
from pathlib import Path

FIELDS = ['schema_version','packet_id','item_id','item_type','case_id','source_id','target_id',
          'reviewer','independence_attested','decision','reason','provisional_revealed']
DECISIONS = {'useful','not_useful','unsure','unreviewed'}


def load_reviews(path, registry):
    raw = Path(path).read_bytes()
    if len(raw) > 1024 * 1024:
        raise ValueError('Review CSV exceeds 1 MiB.')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    if reader.fieldnames != FIELDS:
        raise ValueError('Use the CSV exported by this Phase 3E packet; column order/schema differs.')
    expected = {item['item_id']:item for item in registry['items']}
    reviews, identities = {}, set()
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError('Malformed review CSV row.')
        item_id = row['item_id']
        if item_id not in expected or item_id in reviews:
            raise ValueError('Unknown or duplicate review item.')
        if row['schema_version'] != '1' or row['packet_id'] != registry['packet_id']:
            raise ValueError('The review belongs to a different packet/version.')
        item = expected[item_id]
        if any(row[k] != item.get(k,'') for k in ['item_type','case_id','source_id','target_id']):
            raise ValueError('Review source/target/task does not match the frozen packet.')
        if row['decision'] not in DECISIONS or row['independence_attested'] not in {'true','false'} or row['provisional_revealed'] not in {'true','false'}:
            raise ValueError('Unsupported decision or attestation value.')
        if len(row['reason']) > 2001 or len(row['reviewer']) > 101:
            raise ValueError('Reviewer/reason exceeds supported lengths.')
        identity = row['reviewer'].strip()
        if row['decision'] != 'unreviewed' and (not identity or row['independence_attested'] != 'true'):
            raise ValueError('Scoring decisions requires a reviewer name and independent-human attestation. Draft exports can be resumed in the packet.')
        if identity:
            identities.add(identity)
        reviews[item_id] = row
    if len(identities) > 1:
        raise ValueError('Use one reviewer per file; multiple-reviewer adjudication is a separate step.')
    if not reviews:
        raise ValueError('No review rows supplied.')
    return reviews


def score_reviews(registry, reviews):
    """AI labels are neither accepted nor consulted by this calculation."""
    if any(r.get('decision') != 'unreviewed' and (not r.get('reviewer','').strip() or r.get('independence_attested') != 'true') for r in reviews.values()):
        raise ValueError('Decisions need a reviewer and independent-human attestation.')
    counts = {decision:0 for decision in DECISIONS}
    for item in registry['items']:
        counts[reviews.get(item['item_id'],{}).get('decision','unreviewed')] += 1
    results = []
    for case in registry['cases']:
        methods = {}
        for method, ids in case['rankings'].items():
            cutoffs = {}
            for k in [3,5]:
                decisions = [reviews.get(f'C-{case["id"]}-{aid}',{}).get('decision','unreviewed') for aid in ids[:k]]
                useful = decisions.count('useful')
                unresolved = [aid for aid,decision in zip(ids[:k],decisions) if decision in {'unsure','unreviewed'}]
                complete = len(ids) >= k and not unresolved
                cutoffs[f'precision@{k}'] = {'value':useful/k if complete else None,'useful':useful,
                    'decided':sum(d in {'useful','not_useful'} for d in decisions),'required':k,
                    'unresolved_ids':unresolved,'missing_result_slots':max(0,k-len(ids)),
                    'reason':None if complete else 'unresolved_judgements_or_missing_results'}
            methods[method] = cutoffs
        results.append({'case_id':case['id'],'kind':case['kind'],'methods':methods})
    aggregates = {}
    for kind in ['related','internal_link']:
        group = [case for case in results if case['kind']==kind]
        aggregates[kind] = {}
        for method in ['embeddings','tfidf']:
            aggregates[kind][method] = {}
            for k in [3,5]:
                values = [case['methods'][method][f'precision@{k}']['value'] for case in group]
                available = [v for v in values if v is not None]
                aggregates[kind][method][f'precision@{k}'] = {
                    'all_case_mean':sum(available)/len(group) if group and len(available)==len(group) else None,
                    'completed_cases':len(available),'total_cases':len(group),
                    'completed_case_mean':sum(available)/len(available) if available else None}
    overlap_metrics={}
    for method,ids in registry.get('overlap_rankings',{}).items():
        overlap_metrics[method]={}
        for k in [3,5]:
            decisions=[reviews.get(item_id,{}).get('decision','unreviewed') for item_id in ids[:k]]
            unresolved=[item_id for item_id,decision in zip(ids[:k],decisions) if decision in {'unsure','unreviewed'}]
            overlap_metrics[method][f'precision@{k}']={'value':decisions.count('useful')/k if len(ids)>=k and not unresolved else None,
                'useful':decisions.count('useful'),'required':k,'unresolved_ids':unresolved,'missing_result_slots':max(0,k-len(ids))}
    return {'packet_id':registry['packet_id'],'label_source':'Self-attested human CSV; identity/independence not externally verified',
            'reviewer_ids':sorted({r.get('reviewer','').strip() for r in reviews.values()}-{''}),
            'ai_labels_used':False,'decision_counts':counts,
            'provisional_exposure_count':sum(r['provisional_revealed']=='true' for r in reviews.values()),
            'case_metrics':results,'aggregates':aggregates,
            'overlap_review':[{'item_id':i['item_id'],'source_id':i['source_id'],'target_id':i['target_id'],
                              'decision':reviews.get(i['item_id'],{}).get('decision','unreviewed')}
                             for i in registry['items'] if i['item_type']=='overlap'],
            'overlap_review_precision':overlap_metrics,
            'overlap_metric_definition':'Precision of useful investigation flags, not duplicate or merge accuracy.',
            'duplicate_detection_accuracy_computed':False}
