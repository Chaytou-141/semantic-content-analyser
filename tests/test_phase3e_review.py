import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.build_phase3e import build, script_json
from scripts.phase3e_review import FIELDS, load_reviews, score_reviews


@pytest.fixture
def registry():
    return {'packet_id':'f'*64,'items':[{'item_id':'C-R1-'+aid,'item_type':'candidate','case_id':'R1','source_id':'','target_id':aid} for aid in 'abcde']+
            [{'item_id':'O01','item_type':'overlap','case_id':'OVERLAP','source_id':'a','target_id':'b'}],
            'cases':[{'id':'R1','kind':'related','rankings':{'embeddings':list('abcde'),'tfidf':list('edcba')}}]}


def write_csv(path, registry, decisions, overrides=None):
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
        for item in registry['items']:
            row={'schema_version':'1','packet_id':registry['packet_id'],**item,'reviewer':'Synthetic test fixture, not a human',
                 'independence_attested':'true','decision':decisions.get(item['item_id'],'unreviewed'),
                 'reason':'Quoted "reason", with comma\nand newline','provisional_revealed':'false'}
            row.update(overrides or {});writer.writerow(row)


def test_complete_human_metrics_do_not_read_ai_labels(tmp_path, registry):
    decisions={'C-R1-'+a:('useful' if a in 'ace' else 'not_useful') for a in 'abcde'}
    p=tmp_path/'review.csv';write_csv(p,registry,decisions)
    result=score_reviews(registry,load_reviews(p,registry))
    metric=result['case_metrics'][0]['methods']['embeddings']
    assert metric['precision@3']['value']==2/3 and metric['precision@5']['value']==3/5
    registry['provisional_ai_labels']={'a':False,'c':False,'e':False}
    assert score_reviews(registry,load_reviews(p,registry))==result
    assert result['duplicate_detection_accuracy_computed'] is False and result['ai_labels_used'] is False


def test_unsure_and_missing_rows_keep_precision_unavailable(tmp_path, registry):
    p=tmp_path/'partial.csv';write_csv(p,registry,{'C-R1-a':'useful','C-R1-b':'not_useful','C-R1-c':'unsure'})
    result=score_reviews(registry,load_reviews(p,registry));metric=result['case_metrics'][0]['methods']['embeddings']['precision@3']
    assert metric['value'] is None and metric['decided']==2 and metric['unresolved_ids']==['c']
    assert result['aggregates']['related']['embeddings']['precision@3']['all_case_mean'] is None
    assert result['decision_counts']['unsure']==1 and result['decision_counts']['unreviewed']==3


def test_partial_top_three_is_scoreable_but_top_five_is_not(tmp_path, registry):
    p=tmp_path/'partial.csv';write_csv(p,registry,{'C-R1-'+a:'useful' for a in 'abc'})
    result=score_reviews(registry,load_reviews(p,registry));metric=result['case_metrics'][0]['methods']['embeddings']
    assert metric['precision@3']['value']==1 and metric['precision@5']['value'] is None


@pytest.mark.parametrize('override',[{'packet_id':'wrong'},{'target_id':'other'},{'reviewer':''},{'independence_attested':'false'},{'decision':'Relevant'},{'provisional_revealed':'yes'}])
def test_tampered_or_unattested_reviews_rejected(tmp_path, registry, override):
    p=tmp_path/'bad.csv';write_csv(p,registry,{'C-R1-a':'useful'},override)
    with pytest.raises(ValueError):load_reviews(p,registry)


def test_duplicate_and_mixed_reviewers_rejected(tmp_path, registry):
    p=tmp_path/'review.csv';write_csv(p,registry,{})
    rows=list(csv.DictReader(io.StringIO(p.read_text(encoding='utf-8-sig'))))
    for invalid in [rows+[rows[0]],[{**r,'reviewer':'other'} if i==1 else r for i,r in enumerate(rows)]]:
        with p.open('w',newline='',encoding='utf-8')as f:
            writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(invalid)
        with pytest.raises(ValueError):load_reviews(p,registry)


def test_cli_refuses_to_overwrite_existing_metrics(tmp_path, registry):
    p=tmp_path/'review.csv';write_csv(p,registry,{})
    reg=tmp_path/'registry.json';reg.write_text(json.dumps(registry));out=tmp_path/'keep.json';out.write_text('preserve')
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([sys.executable,'-B',str(root/'scripts/score_phase3e.py'),'--reviews',str(p),'--registry',str(reg),'--output',str(out)],capture_output=True)
    assert result.returncode==2 and out.read_text()=='preserve'
    p.write_text(','.join(FIELDS)+'\n"unterminated',encoding='utf-8')
    malformed=subprocess.run([sys.executable,'-B',str(root/'scripts/score_phase3e.py'),'--reviews',str(p),'--registry',str(reg)],capture_output=True)
    assert malformed.returncode==2 and b'Traceback' not in malformed.stderr


def test_json_embedding_cannot_close_data_script():
    encoded=script_json({'value':'</script><img src=x onerror=alert(1)> & \u2028'})
    assert '</script>' not in encoded and '<img' not in encoded
    assert json.loads(encoded)['value'].startswith('</script>')


def test_saved_registry_and_supporting_passages_are_reproducible():
    root=Path(__file__).resolve().parents[1]
    if not (root/'runtime/phase3d/analysis-results.json').exists():
        pytest.skip('Authorised private Phase 3D cache is not distributed in Git.')
    registry,data=build(root)
    assert len(registry['items'])==59 and sum(i['item_type']=='candidate' for i in registry['items'])==44
    assert all(item['existing_link'] is False for item in data['items'] if item['kind']=='internal_link')
    assert any(item['source_id']=='' for item in data['items'])
    assert all('decision' not in item for item in data['items'])


def test_overlap_usefulness_metrics_are_separate_from_article_relevance(tmp_path):
    root=Path(__file__).resolve().parents[1]
    registry=json.loads((root/'evaluations/phase3e/packet-registry.json').read_text())
    p=tmp_path/'synthetic.csv'
    write_csv(p,registry,{i['item_id']:'useful' for i in registry['items'] if i['item_type']=='overlap'})
    result=score_reviews(registry,load_reviews(p,registry))
    assert result['overlap_review_precision']['embeddings']['precision@3']['value']==1
    assert result['overlap_review_precision']['tfidf']['precision@5']['value']==1
    assert result['case_metrics'][0]['methods']['embeddings']['precision@3']['value'] is None
    assert not result['duplicate_detection_accuracy_computed']
