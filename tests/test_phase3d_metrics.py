import pytest

from scripts.phase3d_metrics import precision_at, summarize_case


def labels(status='assistant_provisional'):
    return [{'article_id': str(i), 'relevant': i % 2 == 0, 'review_status': status} for i in range(5)]


def test_precision_denominator_and_independent_provenance():
    scores = summarize_case(['0', '1', '2', '3', '4'], labels())
    assert scores['provisional']['precision@3']['value'] == 2 / 3
    assert scores['provisional']['precision@5']['value'] == 3 / 5
    assert scores['independent']['precision@3']['value'] is None
    assert precision_at(['0', '1', '2'], labels('independent_human'), 3, 'independent_human')['value'] == 2 / 3


def test_missing_or_incomplete_judgements_do_not_become_negative_labels():
    assert precision_at(['0', 'missing', '2'], labels(), 3)['reason'] == 'missing_judgements'
    assert precision_at(['0'], labels(), 3)['reason'] == 'fewer_than_k_results'


@pytest.mark.parametrize('ids,rows,k', [(['0','0'], labels(), 1), (['0'], labels()+labels(), 1), (['0'], [{'article_id':'0','relevant':'yes'}], 1), (['0'], labels(), 0)])
def test_invalid_evaluation_inputs_are_rejected(ids, rows, k):
    with pytest.raises(ValueError):
        precision_at(ids, rows, k)


def test_independent_source_audit_distinguishes_text_and_mapping_differences():
    from scripts.phase3d_extraction_audit import audit_article
    body=b'<html><head><link rel="canonical" href="/a"></head><h1>Source title</h1><div class="entry-content"><h2>Section</h2><p>Body words <a href="/b">Destination</a></p></div></html>'
    article={'id':'a','url':'https://example.com/a','title':'Source title','body':'Section Body words Destination','existing_links':['b']}
    audit=audit_article(article,body,['Section'],{'https://example.com/a':'a','https://example.com/b':'b'})
    assert audit['missing_word_occurrences']==audit['extra_word_occurrences']==0
    assert not audit['missing_selected_link_ids'] and audit['title_matches_source_h1'] and audit['canonical_matches_source']
    article['body']='Body words';article['existing_links']=[]
    audit=audit_article(article,body,[],{'https://example.com/b':'b'})
    assert audit['missing_word_occurrences']==2 and audit['missing_body_headings']==['Section']
    assert audit['missing_selected_link_ids']==['b']
