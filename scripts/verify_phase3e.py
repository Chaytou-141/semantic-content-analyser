"""Targeted review-tool checks only. Synthetic UI decisions are not human evidence."""
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/phase3e'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    env={**os.environ,'DATABASE_PATH':str(OUT/'bootstrap.sqlite3'),'WORKSPACE_MODE':'local',
         'APP_ENV':'development','APP_PASSWORD':'','PRELOAD_MODEL':'false',
         'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','PYTHONDONTWRITEBYTECODE':'1'}
    suite=subprocess.run([sys.executable,'-B','-m','pytest','tests/test_phase3e_review.py','-q','-p','no:cacheprovider',
                          '--basetemp',str(OUT/'targeted-final')],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (OUT/'tests.log').write_text(suite.stdout+suite.stderr,encoding='utf-8')
    print(suite.stdout,flush=True);assert suite.returncode==0
    packet=OUT/('test-packet-'+str(time.time_ns())+'.html')
    subprocess.run([sys.executable,'-B','scripts/build_phase3e.py','--output',str(packet)],cwd=ROOT,env=env,check=True)
    subprocess.run(['node','--check','evaluations/phase3e/reviewer.js'],cwd=ROOT,check=True)
    from playwright.sync_api import sync_playwright,expect
    errors,requests=[],[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(channel='chromium',args=['--disable-gpu'])
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:requests.append(request.url))
        page.goto(packet.as_uri())
        expect(page.locator('.card')).to_have_count(59)
        assert page.locator('input[type=radio]:checked').count()==0
        first=page.locator('.card').first
        first.locator('.ai-note > summary').click()
        assert page.locator('input[type=radio]:checked').count()==0
        page.locator('#reviewer').fill('AUTOMATED FIXTURE - NOT A HUMAN REVIEW')
        page.locator('#attest').check()
        first.get_by_role('radio',name='Useful',exact=True).check()
        first.locator('textarea').fill('=1+1,"quoted"\n<script>window.injected=true</script>')
        page.locator('.card').nth(1).get_by_role('radio',name='Unsure',exact=True).check()
        page.locator('#task').select_option('OVERLAP')
        expect(page.locator('.card:visible')).to_have_count(15)
        page.locator('.card:visible').first.get_by_role('radio',name='Not useful',exact=True).check()
        expect(page.locator('#progress')).to_have_text('2 of 59 decided · 1 unsure · 56 unreviewed')
        assert not page.evaluate('Boolean(window.injected)')
        with page.expect_download() as download:
            page.locator('#export').click()
        export=OUT/'synthetic-browser-review.csv';download.value.save_as(export)
        rows=list(csv.DictReader(export.open(encoding='utf-8-sig',newline='')))
        assert len(rows)==59 and rows[0]['reason'].startswith("'=1+1")
        assert rows[0]['provisional_revealed']=='true' and rows[0]['decision']=='useful'
        assert 'relevant' not in rows[0] and 'ai_label' not in rows[0]
        page.reload();expect(page.locator('#progress')).to_have_text('2 of 59 decided · 1 unsure · 56 unreviewed')
        other=browser.new_context(viewport={'width':390,'height':844});resumed=other.new_page()
        resumed.on('pageerror',lambda error:errors.append(str(error)))
        resumed.goto(packet.as_uri());assert resumed.locator('input[type=radio]:checked').count()==0
        resumed.locator('#import').set_input_files(export)
        expect(resumed.locator('#progress')).to_have_text('2 of 59 decided · 1 unsure · 56 unreviewed')
        assert resumed.locator('.card').first.get_by_role('radio',name='Useful',exact=True).is_checked()
        assert resumed.locator('.card').first.locator('textarea').input_value()==rows[0]['reason']
        bad=OUT/'synthetic-wrong-packet.csv'
        with bad.open('w',encoding='utf-8',newline='') as file:
            writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows([{**r,'packet_id':'wrong'}for r in rows])
        resumed.locator('#import').set_input_files(bad)
        expect(resumed.locator('#message')).to_contain_text('different packet')
        expect(resumed.locator('#progress')).to_have_text('2 of 59 decided · 1 unsure · 56 unreviewed')
        resumed.locator('#status').select_option('unsure');expect(resumed.locator('.card:visible')).to_have_count(1)
        assert resumed.evaluate('document.documentElement.scrollWidth <= innerWidth')
        resumed.screenshot(path=str(OUT/'review-mobile.png'),full_page=True)
        page.locator('#task').select_option('R01');page.screenshot(path=str(OUT/'review-desktop.png'))
        assert not errors and not [url for url in requests if url.startswith(('http://','https://'))]
        browser.close()
    scored=OUT/('synthetic-metrics-'+str(time.time_ns())+'.json')
    cli=subprocess.run([sys.executable,'-B','scripts/score_phase3e.py','--reviews',str(export),'--output',str(scored)],cwd=ROOT,env=env,capture_output=True,text=True)
    assert cli.returncode==0,cli.stderr
    result=json.loads(scored.read_text())
    assert result['decision_counts']=={'useful':1,'not_useful':1,'unsure':1,'unreviewed':56}
    assert all(x['value'] is None for c in result['case_metrics'] for method in c['methods'].values() for x in method.values())
    assert result['provisional_exposure_count']==1 and not result['ai_labels_used']
    protected=json.loads((OUT/'preservation-before.json').read_text())
    changed=[p for p,h in protected.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h];assert not changed,changed
    assert subprocess.check_output(['git','diff','036f173','--','semantic_analyser','web','evaluations/phase3d'],cwd=ROOT)==b''
    evidence={'phase':'3E','baseline_evidence_commit':'771c4cb','preserved_application_commit':'036f173',
              'targeted_suite':suite.stdout.strip(),'browser_items':59,'candidate_items':44,'overlap_pairs':15,
              'csv_export_resume_and_failed_import_atomicity':'passed','draft_reload':'passed','ai_label_separation':'passed',
              'synthetic_decisions_only':True,'actual_human_reviews_received':0,'incomplete_precision_unavailable':'passed',
              'external_http_requests':0,'browser_errors':errors,'model_inference_runs':0,'full_suite_run':False,
              'protected_files_checked':len(protected),'changed_protected_files':changed}
    (OUT/'verification.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print('PASS: 59-item offline packet, independent choices, draft/CSV roundtrip, unresolved metrics and preservation. All test decisions synthetic.')


if __name__=='__main__':main()
