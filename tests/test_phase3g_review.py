"""Only synthetic choices; frozen metadata/text checks never load a model."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

from scripts.build_phase3g import build, render
from scripts.phase3g_review import FIELDS, ROOT, VERSION, load_reviews, score, validate_registry


@pytest.fixture
def registry():
    return json.loads((ROOT/'evaluations/phase3g/coordinator-registry.json').read_text())


def rows_for(registry):
    return [{'schema_version': VERSION, 'packet_id': registry['packet_id'],
             **{k: item[k] for k in ['item_id', 'case_id', 'source_id', 'target_id']},
             'reviewer': 'SYNTHETIC FIXTURE - NOT A HUMAN REVIEW', 'human_attested': 'true',
             'prior_exposure': 'none', 'decision': 'useful', 'reason': 'Quoted "reason",\nwith comma'}
            for item in registry['items']]


def write(path, rows, fields=FIELDS):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def test_complete_packet_supports_all_cutoffs(tmp_path, registry):
    p=tmp_path/'synthetic.csv'; write(p, rows_for(registry))
    result=score(registry, load_reviews(p, registry))
    assert result['eligible_resolved_decisions'] == 44
    assert all(v['value']==1 for c in result['case_metrics'] for m in c['methods'].values() for v in m.values())
    assert not result['overlap_included'] and not result['ai_assisted_labels_used']
    assert not result['formally_blinded_independence_claimed']
    assert all(v['methods']['embeddings']['all_case_mean']==1 for group in result['aggregates'].values() for v in group.values())


def test_denominator_unsure_missing_and_paired_comparisons(tmp_path, registry):
    rows=rows_for(registry); by_id={r['item_id']:r for r in rows}
    case=registry['cases'][0]; first=case['rankings']['embeddings'][0]
    by_id[first]['decision']='not_useful'
    p=tmp_path/'synthetic.csv';write(p,rows)
    result=score(registry,load_reviews(p,registry))
    assert result['case_metrics'][0]['methods']['embeddings']['precision@3']['value']==2/3
    assert result['case_metrics'][0]['methods']['embeddings']['precision@5']['value']==4/5
    for value in ['unsure','unreviewed',None]:
        changed=[{**r,'decision':value} if r['item_id']==first else r for r in rows] if value else [r for r in rows if r['item_id']!=first]
        write(p,changed); result=score(registry,load_reviews(p,registry))
        assert result['case_metrics'][0]['methods']['embeddings']['precision@3']['value'] is None
        pair=result['aggregates'][case['kind']]['precision@3']
        assert case['id'] not in pair['paired_complete_cases']
        assert pair['methods']['tfidf']['all_case_mean'] is None


@pytest.mark.parametrize('field,value', [('human_attested','false'), ('prior_exposure','screened'),
                                        ('prior_exposure','unsure'), ('prior_exposure','unreported')])
def test_provenance_ineligible_but_preserved(tmp_path, registry, field, value):
    rows=[{**r,field:value} for r in rows_for(registry)]
    p=tmp_path/'screened.csv';write(p,rows)
    reviewed=load_reviews(p,registry);result=score(registry,reviewed)
    assert reviewed[rows[0]['item_id']][field]==value
    assert result['eligible_resolved_decisions']==0
    assert all(v['value'] is None for c in result['case_metrics'] for m in c['methods'].values() for v in m.values())


@pytest.mark.parametrize('field,value', [('packet_id','old'),('schema_version','1'),('item_id','O01'),
    ('case_id','R99'),('source_id','wrong'),('target_id','wrong'),('decision','yes'),
    ('human_attested','maybe'),('prior_exposure','true'),('reviewer',''),('reason','x'*2002)])
def test_tampered_fields_fail(tmp_path,registry,field,value):
    rows=rows_for(registry);rows[0][field]=value;p=tmp_path/'bad.csv';write(p,rows)
    with pytest.raises(ValueError):load_reviews(p,registry)


def test_duplicate_schema_malformed_mixed_identity_and_provenance_fail(tmp_path,registry):
    rows=rows_for(registry);p=tmp_path/'bad.csv'
    for invalid in [rows+[rows[0]], [{**r,'reviewer':'other'} if n==1 else r for n,r in enumerate(rows)],
                    [{**r,'prior_exposure':'screened'} if n==1 else r for n,r in enumerate(rows)]]:
        write(p,invalid)
        with pytest.raises(ValueError):load_reviews(p,registry)
    write(p,[{**rows[0],'extra':'AI label'}],FIELDS+['extra'])
    with pytest.raises(ValueError):load_reviews(p,registry)
    p.write_text(','.join(FIELDS)+'\n"unclosed',encoding='utf-8')
    with pytest.raises(csv.Error):load_reviews(p,registry)
    for old in (ROOT/'evaluations/phase3f/inputs').glob('*.csv'):
        with pytest.raises(ValueError):load_reviews(old,registry)


def test_registry_covers_exact_frozen_union_and_detects_tampering(registry):
    frozen=json.loads((ROOT/'evaluations/phase3e/packet-registry.json').read_text())
    validate_registry(registry,frozen)
    assert len(registry['items'])==44 and len(registry['cases'])==7
    for kind in ['missing','rank','source']:
        bad=copy.deepcopy(registry)
        if kind=='missing':bad['items'].pop()
        if kind=='rank':bad['cases'][0]['rankings']['embeddings'].reverse()
        if kind=='source':bad['items'][0]['source_id']='bad'
        with pytest.raises(ValueError):validate_registry(bad,frozen)


def test_builder_whitelists_review_data_no_previous_judgements_or_methods(registry):
    if not (ROOT/'runtime/phase3d/analysis-results.json').exists():
        pytest.skip('Authorised private article cache unavailable; no refetch fallback.')
    actual,payload=build();assert actual==registry
    assert set(payload)=={'schema_version','packet_id','items','articles'}
    assert len(payload['items'])==44
    assert payload['packet_id']!=registry['frozen_packet_id']
    for item in payload['items']:
        assert set(item)=={'item_id','case_id','source_id','target_id','kind','question','criterion','existing_link','passages'}
        for evidence in item['passages']:
            assert set(evidence)=={'source_passage','target_passage'}
    html=render(ROOT,payload)
    for forbidden in ['MiniLM','TF-IDF','embeddings','tfidf','ai_notes','original_item_id','coordinator-registry','provisional_revealed']:
        assert forbidden not in html
    original=json.loads((ROOT/'evaluations/phase3e/packet-registry.json').read_text())
    assert all(i['item_id'] not in html for i in original['items'])
    embedded=json.loads(re.search(r'<script type="application/json" id="review-data">(.*?)</script>',html,re.S)[1])
    assert embedded==payload


def test_untrusted_text_cannot_break_json_script_or_replace_template_tokens():
    payload={'test':'</script><script>window.bad=1</script>@@SCRIPT@@ & \u2028'}
    html=render(ROOT,payload)
    embedded=re.search(r'<script type="application/json" id="review-data">(.*?)</script>',html,re.S)[1]
    assert json.loads(embedded)==payload
    assert '<script>window.bad' not in html


def test_cli_scores_without_corpus_and_refuses_overwrite(tmp_path,registry):
    p=tmp_path/'synthetic.csv';write(p,rows_for(registry));out=tmp_path/'result.json'
    cmd=[sys.executable,'-B','-m','scripts.phase3g_review','--reviews',str(p),'--output',str(out)]
    result=subprocess.run(cmd,cwd=ROOT,capture_output=True)
    assert result.returncode==0,result.stderr
    before=out.read_bytes();result=subprocess.run(cmd,cwd=ROOT,capture_output=True)
    assert result.returncode==2 and out.read_bytes()==before
    p.write_text(','.join(FIELDS)+'\n"unclosed',encoding='utf-8')
    result=subprocess.run(cmd[:-2],cwd=ROOT,capture_output=True)
    assert result.returncode==2 and b'Traceback' not in result.stderr


def test_build_cli_refuses_overwrite(tmp_path):
    if not (ROOT/'runtime/phase3d/analysis-results.json').exists():
        pytest.skip('Private corpus unavailable.')
    out=tmp_path/'keep.html';out.write_text('preserve')
    result=subprocess.run([sys.executable,'-B','-m','scripts.build_phase3g','--output',str(out)],cwd=ROOT,capture_output=True)
    assert result.returncode==2 and out.read_text()=='preserve'
