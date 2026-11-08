"""Offline browser regression for link evidence, keyboard navigation and mock reviews.

No model, live website, real API or saved-data writes. --baseline serves 0d10d70 assets.
"""
from copy import deepcopy
import hashlib
import json
import mimetypes
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from link_ui_fixtures import fixture, REVISION


def main():
    from playwright.sync_api import sync_playwright,expect
    baseline='--baseline' in sys.argv
    out=ROOT/'runtime/link-opportunities-ui';out.mkdir(parents=True,exist_ok=True)
    articles,groups,initial_reviews=fixture()
    frozen={path:subprocess.check_output(['git','show','0d10d70:web/'+path],cwd=ROOT)
            for path in ['app.js','styles.css']} if baseline else {}
    cases=[];errors=[];blocked=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chromium')
        for width,height in ([(1440,1000)] if baseline else [(1440,1000),(1024,768),(768,1024),(390,844),(320,800)]):
            reviews=deepcopy(initial_reviews);posts=[];pending=[];control={'hold':False,'fail':False}
            ctx=browser.new_context(viewport={'width':width,'height':height})
            page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            def respond(route):
                req=route.request;path=urlsplit(req.url).path
                if req.method=='POST' and path=='/api/links':
                    data=req.post_data_json;assert data['source_id']=='S01' and data['top_k']==5
                    methods=['embeddings','tfidf'] if data['method']=='compare' else [data['method']]
                    payload={'results':{m:groups[m] for m in methods},'reviews':reviews,'review_required':True,'collection_revision':REVISION}
                elif req.method=='POST' and path=='/api/reviews':
                    data=req.post_data_json;assert req.headers['if-match']==REVISION
                    assert data['source_id']=='S01' and data['target_id'] in {r['id'] for r in groups['embeddings']['results']}
                    posts.append(deepcopy(data))
                    if control['fail']:
                        control['fail']=False;route.fulfill(status=500,content_type='application/json',body=json.dumps({'detail':'Controlled offline save failure'}));return
                    reviews[:]=[r for r in reviews if r['target_id']!=data['target_id']]+[deepcopy(data)]
                    if control['hold']:pending.append(route);return
                    payload={'saved':True,'collection_revision':REVISION}
                elif req.method!='GET':blocked.append((req.method,path));route.abort();return
                elif path=='/api/session':payload={'authenticated':True,'password_required':False}
                elif path=='/api/articles':payload={'articles':articles,'collection_revision':REVISION}
                elif path=='/api/meta':payload={'website_fetch_enabled':True,'workspace_mode':'local','idle_seconds':3600}
                else:
                    asset=ROOT/'web'/('index.html' if path=='/' else path.removeprefix('/static/'))
                    if (path!='/' and not path.startswith('/static/')) or not asset.resolve().is_relative_to((ROOT/'web').resolve()) or not asset.is_file():
                        blocked.append(req.url);route.abort();return
                    route.fulfill(body=frozen.get(asset.name,asset.read_bytes()),content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream');return
                route.fulfill(content_type='application/json',body=json.dumps(payload))
            page.route('**/*',respond)
            def load(method='embeddings'):
                if page.url.startswith('http://offline.test/'):
                    page.reload()
                    page.evaluate('navigate("links")')
                else:page.goto('http://offline.test/#links')
                expect(page.locator('#links-source')).to_have_value('S01')
                page.locator('#links-method').select_option(method)
                page.locator('#links-form button[type=submit]').click()
                page.wait_for_function('state.lastLinks && !state.busy')
            load()
            if baseline:
                expect(page.locator('#links-results .result-card')).to_have_count(5)
                page.screenshot(path=str(out/'before-1440.png'),full_page=True)
                offset=page.locator('.result-card .review-actions').first.bounding_box()['y']-page.locator('.result-card').first.bounding_box()['y']
                cases.append({'width':width,'before_result_cards':5,'review_action_offset_px':round(offset,2)})
                ctx.close();continue
            tabs=page.locator('#link-list-embeddings [role=tab]');panel=page.locator('#link-panel-embeddings')
            expect(tabs).to_have_count(5)
            assert tabs.evaluate_all('(a)=>a.map(t=>t.id)')==[f'link-tab-embeddings-D0{i}' for i in range(1,6)]
            expect(tabs.nth(0)).to_have_attribute('aria-selected','true')
            expect(tabs.nth(1)).to_have_attribute('data-review','not_useful')
            expect(tabs.nth(2)).to_have_attribute('data-review','useful')
            expect(page.locator('.link-review-count')).to_have_text('2 of 5 reviewed')
            # Every candidate retains exact identities, raw full evidence and offsets.
            for index,result in enumerate(groups['embeddings']['results']):
                tabs.nth(index).click()
                expect(panel.locator('.link-route-source')).to_contain_text(articles[0]['title'])
                expect(panel.locator('.link-route-target')).to_contain_text(result['title'])
                expect(panel.locator('.link-similarity strong')).to_have_text(f"{result['score']:.3f}")
                full=panel.locator('.full-evidence pre').all_text_contents()
                assert full==[result['source_passage'],result['passage']]
                excerpts=panel.locator('.link-excerpt').all_text_contents()
                assert all(raw.startswith(short) and len(short)<=220 for raw,short in zip(full,excerpts))
                assert panel.locator('.link-passage a').evaluate_all('(a)=>a.map(x=>x.href)')==[articles[0]['url'],result['url']]
                for label,start,end in [('Source',result['source_start'],result['source_end']),('Destination',result['passage_start'],result['passage_end'])]:
                    assert f'Original character offsets: {start}–{end}' in panel.text_content()
                assert not page.evaluate('window.linkFixtureExecuted || false')
            # Standard vertical tab keyboard pattern; focus survives selection changes.
            tabs.nth(4).focus();page.keyboard.press('Home')
            expect(tabs.nth(0)).to_be_focused();expect(tabs.nth(0)).to_have_attribute('aria-selected','true')
            page.keyboard.press('ArrowDown');expect(tabs.nth(1)).to_be_focused()
            page.keyboard.press('End');expect(tabs.nth(4)).to_be_focused()
            page.keyboard.press('ArrowDown');expect(tabs.nth(0)).to_be_focused()
            page.keyboard.press('ArrowUp');expect(tabs.nth(4)).to_be_focused()
            assert page.locator('#link-list-embeddings [tabindex="0"]').count()==1
            page.keyboard.press('Tab');expect(page.locator('.link-inspect')).to_be_focused()
            page.keyboard.press('Enter');expect(panel).to_be_focused()
            # Untrusted source text stays text, and original passages are keyboard-expandable.
            panel.locator('.full-evidence summary').nth(1).focus();page.keyboard.press('Enter')
            expect(panel.locator('.full-evidence pre').nth(1)).to_be_visible()
            assert '<img src=x' in panel.locator('.full-evidence pre').nth(1).text_content()
            assert panel.locator('img').count()==0
            # Source and destination buttons still open the original article body.
            panel.locator('.link-route-source .result-title').click()
            expect(page.locator('#article-dialog')).to_be_visible()
            expect(page.locator('#article-dialog textarea[name=body]')).to_have_value(articles[0]['body'])
            page.locator('#article-dialog .close-dialog').click()
            # A note draft survives moving among candidates, and decision save retains selection.
            tabs.nth(3).click();panel.locator('.link-note-editor summary').click()
            note=panel.locator('.link-note-editor input');note.fill('Adds practical bakery layout context.')
            tabs.nth(0).click();tabs.nth(3).click();expect(note).to_have_value('Adds practical bakery layout context.')
            panel.get_by_role('button',name='Useful candidate',exact=True).click()
            expect(panel.locator('.link-review-state')).to_have_text('Useful')
            expect(tabs.nth(3)).to_have_attribute('aria-selected','true')
            expect(panel.get_by_role('button',name='Useful candidate',exact=True)).to_be_focused()
            assert posts[-1]=={'source_id':'S01','target_id':'D04','decision':'useful','note':'Adds practical bakery layout context.'}
            panel.get_by_role('button',name='Not useful',exact=True).click()
            expect(panel.locator('.link-review-state')).to_have_text('Not useful')
            panel.get_by_role('button',name='Clear decision',exact=True).click()
            expect(panel.locator('.link-review-state')).to_have_text('Unreviewed')
            assert posts[-1]['decision']=='pending' and posts[-1]['note']=='Adds practical bakery layout context.'
            # A failed save never paints a success state or drops a draft.
            control['fail']=True;note.fill('Unsaved note after a controlled failure.')
            panel.get_by_role('button',name='Not useful',exact=True).click()
            expect(page.locator('#app-error')).to_contain_text('Controlled offline save failure')
            expect(panel.locator('.link-review-state')).to_have_text('Unreviewed')
            expect(note).to_have_value('Unsaved note after a controlled failure.')
            # Navigating while save is pending must not move selection back on response.
            control['hold']=True
            panel.get_by_role('button',name='Useful candidate',exact=True).click()
            page.wait_for_function('state.busy');assert len(pending)==1
            tabs.nth(0).click()
            pending.pop().fulfill(content_type='application/json',body=json.dumps({'saved':True,'collection_revision':REVISION}))
            control['hold']=False
            page.wait_for_function('!state.busy')
            expect(tabs.nth(0)).to_have_attribute('aria-selected','true')
            expect(tabs.nth(3)).to_have_attribute('data-review','useful')
            # A browser reload obtains the saved mock decision from the existing API contract.
            load('compare')
            expect(page.locator('[role=tablist]')).to_have_count(2)
            expect(page.locator('#link-tab-embeddings-D04')).to_have_attribute('data-review','useful')
            expect(page.locator('#link-tab-tfidf-D04')).to_have_attribute('data-review','useful')
            expected_orders={m:[r['id'] for r in g['results']] for m,g in groups.items()}
            actual_orders=page.evaluate('Object.fromEntries(Object.entries(state.lastLinks.results).map(([m,g])=>[m,g.results.map(r=>r.id)]))')
            assert actual_orders==expected_orders
            assert page.evaluate('state.lastLinks.results')==groups
            page.locator('#link-tab-embeddings-D04').click();page.locator('#link-tab-tfidf-D04').click()
            first=page.locator('#link-panel-embeddings .link-note-editor input')
            second=page.locator('#link-panel-tfidf .link-note-editor input')
            first.fill('Shared pair note across both methods.');expect(second).to_have_value('Shared pair note across both methods.')
            page.locator('#link-tab-embeddings-D01').click()
            page.locator('#link-panel-embeddings .link-score-help summary').click()
            expect(page.locator('#link-panel-embeddings .link-score-help')).to_contain_text('not accuracy')
            if width<=760:
                page.locator('#link-panel-embeddings .link-back').click()
                expect(page.locator('#link-tab-embeddings-D01')).to_be_focused()
            # Boundary states keep method identity, and singleton keyboard loops work.
            small={'results':{'embeddings':{**deepcopy(groups['embeddings']),'results':[]}},'reviews':deepcopy(reviews),'collection_revision':REVISION}
            page.evaluate('p=>renderLinks(p)',small)
            expect(page.locator('#links-results')).to_contain_text('MiniLM candidates')
            expect(page.locator('#links-results')).to_contain_text('No eligible candidates found.')
            expect(page.locator('[role=tablist]')).to_have_count(0)
            small['results']['embeddings']['results']=deepcopy(groups['embeddings']['results'][:1])
            page.evaluate('p=>renderLinks(p)',small)
            page.locator('[role=tab]').focus();page.keyboard.press('ArrowDown');page.keyboard.press('End')
            expect(page.locator('[role=tab]')).to_be_focused()
            expect(page.locator('.link-detail-topline')).to_contain_text('Recommendation 1 of 1')
            page.evaluate('invalidateResults()');assert page.evaluate('state.linkView') is None
            assert page.evaluate('state.articles')==articles
            # Screenshot a clean initial recommendation, with all five overview rows.
            load()
            page.locator('.link-method h2').evaluate("e=>e.scrollIntoView({block:'start'})")
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(out/f'after-{width}.png'),full_page=True)
            page.locator('.link-workbench').screenshot(path=str(out/f'workbench-{width}.png'))
            (out/f'accessibility-{width}.txt').write_text(page.locator('#links-results').aria_snapshot(),encoding='utf-8')
            offset=page.locator('.link-editorial .review-actions').first.bounding_box()['y']-panel.bounding_box()['y']
            page.locator('#link-tab-embeddings-D02').click()
            page.locator('.link-workbench').screenshot(path=str(out/f'not-useful-{width}.png'))
            cases.append({'viewport':[width,height],'five_candidate_navigation':True,'exact_raw_evidence_and_offsets':True,'review_posts':len(posts),'keyboard':True,'compare_pair_state':True,'overflow':False,'review_action_offset_px':round(offset,2)})
            ctx.close()
        browser.close()
    assert not errors and not blocked,(errors,blocked)
    protected=json.loads((out/'preservation-before.json').read_text())
    changed=[p for p,h in protected.items() if not (ROOT/p).is_file() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    assert not changed,changed
    report={'baseline':baseline,'cases':cases,'browser_errors':errors,'blocked_requests':blocked,'protected_files':len(protected),'unexpected_changes':changed,'live_requests':0,'real_model_runs':0,'actual_review_writes':0,'fixture_scores':'Synthetic display values, not model-quality measurements'}
    (out/('baseline-verification.json' if baseline else 'browser-verification.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'baseline':baseline,'viewports_passed':len(cases),'protected_files_unchanged':len(protected),'browser_errors':errors,'live_requests':0,'actual_review_writes':0}))


if __name__=='__main__':main()
