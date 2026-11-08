"""Targeted offline verification; all simulated decisions are synthetic, not evidence."""
import csv
import hashlib
import json
import subprocess
import sys
import time

from scripts.build_phase3g import ROOT, build, render
from scripts.phase3g_review import load_reviews, score


def main():
    out=ROOT/'runtime/phase3g';out.mkdir(parents=True,exist_ok=True)
    suite=subprocess.run([sys.executable,'-B','-m','pytest','-q','tests/test_phase3g_review.py',
                          'tests/test_phase3e_review.py','tests/test_phase3f_evaluation.py'],cwd=ROOT,
                         capture_output=True,text=True)
    (out/'targeted-tests.log').write_text(suite.stdout+suite.stderr,encoding='utf-8')
    print(suite.stdout,flush=True)
    assert suite.returncode==0,suite.stderr
    registry,payload=build()
    packet=out/f'synthetic-test-packet-{time.time_ns()}.html'
    packet.write_text(render(ROOT,payload),encoding='utf-8')
    subprocess.run(['node','--check','evaluations/phase3g/reviewer.js'],cwd=ROOT,check=True)
    from playwright.sync_api import sync_playwright,expect
    errors,requests=[],[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chromium',args=['--disable-gpu'])
        context=browser.new_context(viewport={'width':1440,'height':1000})
        # Simulate old stored decisions. The new round must not read them.
        context.add_init_script('localStorage.setItem('+json.dumps('semantic-review-3e:'+registry['frozen_packet_id'])+
                                ', JSON.stringify({reviewer:"OLD SCREENED FIXTURE",attest:true,rows:{}}));')
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append(r.url));page.goto(packet.as_uri())
        expect(page.locator('.card')).to_have_count(44)
        assert page.locator('input[type=radio]:checked').count()==0
        assert page.locator('#reviewer').input_value()==''
        assert page.locator('#exposure').input_value()=='unreported'
        assert page.locator('.retrieval,.ai-note').count()==0
        assert page.locator('#task option[value=OVERLAP]').count()==0
        page.locator('#reviewer').fill('AUTOMATED FIXTURE - NOT A HUMAN REVIEW')
        page.locator('#attest').check();page.locator('#exposure').select_option('none')
        first=page.locator('.card').first
        first.get_by_role('radio',name='Useful',exact=True).check()
        first.locator('textarea').fill('=1+1,"quoted"\n<script>window.injected=true</script>')
        page.locator('.card').nth(1).get_by_role('radio',name='Unsure',exact=True).check()
        page.locator('.card').nth(2).get_by_role('radio',name='Not useful',exact=True).check()
        expect(page.locator('#progress')).to_have_text('2 of 44 decided · 1 unsure · 41 unreviewed')
        assert not page.evaluate('Boolean(window.injected)')
        with page.expect_download() as download:page.locator('#export').click()
        export=out/'synthetic-browser-review.csv';download.value.save_as(export)
        with export.open(encoding='utf-8-sig',newline='') as file:rows=list(csv.DictReader(file))
        assert len(rows)==44 and rows[0]['reason'].startswith("'=1+1")
        result=score(registry,load_reviews(export,registry))
        assert result['eligible_resolved_decisions']==2
        assert all(v['value'] is None for c in result['case_metrics'] for m in c['methods'].values() for v in m.values())
        page.reload();expect(page.locator('#progress')).to_have_text('2 of 44 decided · 1 unsure · 41 unreviewed')
        page.screenshot(path=str(out/'review-desktop.png'))
        other=browser.new_context(viewport={'width':390,'height':844})
        resumed=other.new_page();resumed.on('pageerror',lambda e:errors.append(str(e)))
        resumed.on('request',lambda r:requests.append(r.url));resumed.goto(packet.as_uri())
        assert resumed.locator('input[type=radio]:checked').count()==0
        resumed.locator('#import').set_input_files(export)
        expect(resumed.locator('#progress')).to_have_text('2 of 44 decided · 1 unsure · 41 unreviewed')
        assert resumed.locator('.card').first.locator('textarea').input_value()==rows[0]['reason']
        bad=out/'synthetic-wrong-target.csv'
        with bad.open('w',encoding='utf-8',newline='') as file:
            writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader()
            writer.writerows([{**r,'target_id':'wrong'} if n==5 else r for n,r in enumerate(rows)])
        resumed.locator('#import').set_input_files(bad)
        expect(resumed.locator('#message')).to_contain_text('mismatch')
        expect(resumed.locator('#progress')).to_have_text('2 of 44 decided · 1 unsure · 41 unreviewed')
        resumed.locator('#import').set_input_files(ROOT/'evaluations/phase3f/inputs/phase3e_reconciled_mixed_review.csv')
        expect(resumed.locator('#message')).to_contain_text('earlier review files are incompatible')
        expect(resumed.locator('#progress')).to_have_text('2 of 44 decided · 1 unsure · 41 unreviewed')
        resumed.locator('#status').select_option('unsure');expect(resumed.locator('.card:visible')).to_have_count(1)
        assert resumed.evaluate('document.documentElement.scrollWidth <= innerWidth')
        resumed.screenshot(path=str(out/'review-mobile.png'),full_page=True)
        assert not errors and not [r for r in requests if r.startswith(('http://','https://'))]
        browser.close()
    protected=json.loads((out/'preservation-before.json').read_text())
    changed=[p for p,h in protected.items() if not (ROOT/p).is_file() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    assert not changed,changed
    assert subprocess.check_output(['git','diff','cad5b4a','--','semantic_analyser','web','data','labels','benchmarks','evaluations/phase3d','evaluations/phase3e','evaluations/phase3f'],cwd=ROOT)==b''
    evidence={'phase':'3G','baseline_commit':'cad5b4a','targeted_tests':suite.stdout.strip(),
              'recommendation_judgements':44,'tasks':7,'overlap_cases_included':0,'overlap_cases_preserved_separately':15,
              'blind_payload_whitelist_and_exact_top5_union':'passed','unselected_initial_decisions':'passed',
              'no_old_draft_or_review_import':'passed','csv_export_resume_and_invalid_import_rollback':'passed',
              'draft_reload_and_mobile_layout':'passed','eligible_cutoff_and_provenance_validation':'passed',
              'browser_errors':errors,'external_http_requests':0,'model_inference_runs':0,
              'actual_new_human_judgements':0,'synthetic_test_decisions_only':True,'full_suite_run':False,
              'protected_files_checked':len(protected),'changed_protected_files':changed,
              'packet_id':registry['packet_id'],'packet_sha256':hashlib.sha256(packet.read_bytes()).hexdigest(),
              'limitations':['Self-reported identity and prior exposure; no formal blindness certification.',
                             'Saved passage selection is model-derived; corpus/tasks are a single-site development sample.',
                             'Private article cache needed to rebuild, but not to score exported CSVs.']}
    (out/'verification.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print('PASS: offline 44-item new round, metadata exclusion, CSV/provenance checks and preservation. Synthetic choices only.')


if __name__=='__main__':main()
