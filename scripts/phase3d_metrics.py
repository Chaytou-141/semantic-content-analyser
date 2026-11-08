"""Offline editorial evaluation helpers. No network, model or application changes."""


def precision_at(ranked_ids, judgements, k, review_status=None):
    """Never convert unreviewed items/missing result slots into positive evidence."""
    if k < 1 or len(set(ranked_ids)) != len(ranked_ids):
        raise ValueError('Use a positive cutoff and unique ranked article IDs.')
    labels = {}
    for row in judgements:
        if row['article_id'] in labels or type(row['relevant']) is not bool:
            raise ValueError('Judgements need distinct IDs and explicit boolean relevance.')
        labels[row['article_id']] = row
    if len(ranked_ids) < k:
        return {'value': None, 'reason': 'fewer_than_k_results'}
    top = [labels.get(aid) for aid in ranked_ids[:k]]
    if any(row is None for row in top):
        return {'value': None, 'reason': 'missing_judgements'}
    if review_status and any(row['review_status'] != review_status for row in top):
        return {'value': None, 'reason': 'insufficient_review_provenance'}
    relevant = sum(row['relevant'] for row in top)
    return {'value': relevant / k, 'relevant': relevant, 'returned': k}


def summarize_case(ranked_ids, judgements):
    return {'provisional': {f'precision@{k}': precision_at(ranked_ids, judgements, k, 'assistant_provisional') for k in [3, 5]},
            'independent': {f'precision@{k}': precision_at(ranked_ids, judgements, k, 'independent_human') for k in [3, 5]}}
