"""Disposable browser/API journeys with fake encoder and controlled network only."""
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/ux-refinement';OUT.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
os.environ.update(DATABASE_PATH=str(OUT/'bootstrap.sqlite3'),APP_ENV='development',WORKSPACE_MODE='local',
                  APP_PASSWORD='',PRELOAD_MODEL='false',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')


def main():
    import uvicorn
    from playwright.sync_api import sync_playwright,expect
    from conftest import FakeModel
    from semantic_analyser.api import create_app
    from semantic_analyser.config import Settings
    from semantic_analyser.engine import AnalysisEngine
    from semantic_analyser.fetch_policy import FetchLimits
    from semantic_analyser.safe_fetch import SafeFetcher
    from test_safe_fetch import FakeDNS,FakeTransport
    from website_fixtures import article,routes

    fixture={'wp.example':routes('wordpress',110),'map.example':routes('sitemap',3)}
    for i in range(1,111):
        prose=(f'Guide {i}. '+('Useful equipment planning protects ventilation clearance and stock rotation. '*120))[:7700]
        if i==1:prose=':contentReference[oaicite:2]{index=2} '+prose
        fixture['wp.example'][f'/posts/{i}']=(200,article(i,prose),{'content-type':'text/html'})
    for host,mapping in fixture.items():
        for key,(status,body,headers) in list(mapping.items()):
            mapping[key]=(status,body.replace(b'https://public.example',('https://'+host).encode()),headers)
    class Transport(FakeTransport):
        def get(self,target,*args):
            assert target.host in fixture
            self.routes=fixture[target.host]
            time.sleep(.01)  # Let loading/progress states paint; not a latency benchmark.
            return super().get(target,*args)
    wire=Transport();engine=AnalysisEngine(model_factory=FakeModel)
    settings=Settings(database_path=OUT/'unused.sqlite3',workspace_mode='visitor',visitor_root=OUT/f'visitors-{time.time_ns()}',
                      secret=os.urandom(32).hex(),password='',production=False,preload_model=False,website_fetch_enabled=True)
    app=create_app(settings,engine,SafeFetcher(FetchLimits(delay_seconds=0),FakeDNS(),wire))
    sock=socket.socket();sock.bind(('127.0.0.1',0));base=f'http://127.0.0.1:{sock.getsockname()[1]}'
    server=uvicorn.Server(uvicorn.Config(app,log_level='error',proxy_headers=False))
    thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
    errors=[];external=[];checks=[]
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.05)
        assert server.started
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='chromium',args=['--disable-gpu'])
            context=browser.new_context(viewport={'width':1440,'height':1000})
            def page_in(ctx):
                p=ctx.new_page();p.on('pageerror',lambda e:errors.append(str(e)))
                def route(r):
                    if r.request.url.startswith(base+'/'):r.continue_()
                    else:external.append(r.request.url);r.abort()
                p.route('**/*',route);p.goto(base);expect(p.locator('#workspace')).to_be_visible();return p
            p=page_in(context)
            p.screenshot(path=str(OUT/'home-desktop.png'),full_page=True)
            expect(p.locator('#home-explore')).to_have_text('Explore sample analysis')
            p.locator('#home-explore').click();expect(p.locator('#view-search')).to_be_visible()
            p.get_by_role('link',name='Articles 21',exact=True).click();expect(p.locator('#article-table tr')).to_have_count(21)
            p.go_back();expect(p.locator('#view-search')).to_be_visible()
            p.locator('#search-query').fill('Choosing a display fridge for a cafe')
            p.locator('.search-settings summary').click();p.locator('#search-method').select_option('compare')
            with p.expect_response(lambda r:r.url.endswith('/api/search')) as response:
                p.locator('#search-form button[type=submit]').click()
            payload=response.value.json();expect(p.locator('#search-results .comparison')).to_be_visible()
            first=p.locator('#search-results .result-card').first
            assert len(first.locator('.evidence-preview').inner_text())<=321
            first.locator('.full-evidence summary').click()
            assert first.locator('.full-evidence pre').inner_text()==payload['results']['embeddings'][0]['passage']
            p.screenshot(path=str(OUT/'search-desktop.png'),full_page=True)
            p.get_by_role('link',name='Link opportunities',exact=True).click()
            p.locator('#links-source').select_option('A01');p.locator('#links-form button[type=submit]').click()
            expect(p.locator('#links-results .result-card').first).to_be_visible()
            card=p.locator('#links-results .result-card').first
            card.locator('.review-note input').fill('Useful follow-on reading for this source.')
            card.get_by_role('button',name='Useful candidate',exact=True).click()
            expect(p.locator('#links-results .review-label').first).to_have_text('Review saved: Useful')
            p.locator('#links-form button[type=submit]').click()
            expect(p.locator('#links-results .review-note input').first).to_have_value('Useful follow-on reading for this source.')
            p.get_by_role('link',name='Content overlap',exact=True).click()
            p.locator('#overlap-threshold').fill('0');p.locator('#overlap-form button[type=submit]').click()
            expect(p.locator('#overlap-results .result-card').first).to_be_visible()
            p.locator('#overlap-results .full-evidence summary').first.click()
            expect(p.locator('#overlap-results .full-evidence pre').first).to_be_visible()
            p.locator('.utility-menu summary').click();p.get_by_role('link',name='Development evaluation',exact=True).click()
            expect(p.locator('#evaluation-content')).to_contain_text('21 original demo articles')
            expect(p.locator('#view-evaluation')).to_contain_text('do not update when you import')
            checks.append('sample search/compare, exact full evidence, review persistence and overlaps')
            p.get_by_role('link',name='Semantic Content Analyser home',exact=True).click()
            p.locator('#home-website-url').fill('https://wp.example')
            p.locator('#home-website-submit').click()
            expect(p.locator('.website-candidate')).to_have_count(110,timeout=20000)
            p.locator('#website-filter').fill('Equipment guide 10')
            p.get_by_role('button',name='Select first 40 shown',exact=True).click()
            assert p.locator('.website-candidates input:checked').count()==11
            p.locator('#website-filter').fill('');p.get_by_role('button',name='Select first 40 shown',exact=True).click()
            assert p.locator('.website-candidates input:checked').count()==40
            p.locator('#website-extract').click();expect(p.locator('#extraction-progress')).to_be_visible()
            expect(p.locator('#website-commit')).to_be_visible(timeout=30000)
            assert p.locator('#extraction-meter').get_attribute('value')=='40'
            expect(p.locator('.website-preview-summary strong').first).to_contain_text('32 articles ready · 8 excluded · 0 failed')
            expect(p.locator('.import-exclusions summary')).to_contain_text('Excluded by application capacity: 8')
            assert int(p.locator('#capacity-meter').get_attribute('value'))<=250000
            preview=p.locator('.website-preview').first;preview.locator('summary').first.click()
            assert 'contentReference' not in preview.locator(':scope > pre').inner_text()
            preview.get_by_text('Show original extracted text, including source citation markers',exact=True).click()
            assert 'contentReference' in preview.locator('details pre').inner_text()
            p.locator('#website-partial').check();p.once('dialog',lambda d:d.accept());p.locator('#website-commit').click()
            expect(p.locator('#import-success-title')).to_have_text('32 articles imported',timeout=20000)
            expect(p.locator('#view-search')).to_be_visible()
            p.locator('#import-success').get_by_role('link',name='Manage articles',exact=True).click()
            expect(p.locator('#article-table tr')).to_have_count(32)
            assert not p.locator('#collection-imports').get_attribute('open')
            p.screenshot(path=str(OUT/'collection-success.png'),full_page=True)
            p.get_by_role('link',name='Semantic Content Analyser home',exact=True).click()
            p.locator('#home-explore').click();expect(p.locator('#sample-dialog')).to_be_visible()
            p.locator('#sample-keep').click();expect(p.locator('#view-search')).to_be_visible()
            assert len(context.request.get(base+'/api/articles').json()['articles'])==32
            p.locator('.examples button').first.click();expect(p.locator('#search-results .result-card').first).to_be_visible()
            p.get_by_role('link',name='Articles 32',exact=True).click()
            p.locator('#article-table button').filter(has_text='Edit').first.click()
            p.locator('#article-dialog input[name=title]').fill('Edited disposable equipment guide')
            p.get_by_role('button',name='Save article',exact=True).click();expect(p.locator('#article-dialog')).to_be_hidden()
            with p.expect_download() as download:p.locator('#view-collection').get_by_role('link',name='Export CSV',exact=True).click()
            download.value.save_as(OUT/'disposable-export.csv')
            p.get_by_role('button',name='Import',exact=True).click()
            p.locator('#import-collection').click();p.locator('#csv-text').fill('id,title,body\nX,Bad,')
            p.once('dialog',lambda d:d.accept());p.locator('#import-form button[type=submit]').click()
            expect(p.locator('#import-dialog .dialog-error')).to_be_visible()
            assert len(context.request.get(base+'/api/articles').json()['articles'])==32
            p.once('dialog',lambda d:d.accept());p.get_by_role('button',name='Close import',exact=True).click()
            p.locator('#import-collection').click();p.locator('#csv-text').fill('id,title,body\nX,Kitchen guide,Useful coffee preparation equipment planning\nY,Coffee guide,Arrange equipment for a safe coffee station')
            p.once('dialog',lambda d:d.accept());p.locator('#import-form button[type=submit]').click()
            expect(p.locator('#import-success-title')).to_have_text('2 articles imported')
            checks.append('110 discovered, filtered selection, 40 extracted, 32 accepted/8 capacity excluded, success actions, sample protection and failed CSV rollback')
            other=browser.new_context(viewport={'width':390,'height':844});mobile=page_in(other)
            mobile.get_by_role('button',name='Import',exact=True).click();mobile.locator('#website-open').click()
            mobile.locator('#website-url').fill('https://map.example');mobile.locator('#website-method').select_option('sitemap')
            mobile.locator('#website-form button[type=submit]').click();expect(mobile.locator('.website-candidate')).to_have_count(3,timeout=20000)
            mobile.get_by_role('button',name='Select first 40 shown',exact=True).click();mobile.locator('#website-extract').click()
            expect(mobile.locator('#website-commit')).to_be_visible(timeout=20000)
            mobile.once('dialog',lambda d:d.accept());mobile.locator('#website-commit').click()
            expect(mobile.locator('#import-success-title')).to_have_text('3 articles imported')
            assert len(context.request.get(base+'/api/articles').json()['articles'])==2
            mobile.screenshot(path=str(OUT/'mobile-success.png'),full_page=True)
            assert mobile.evaluate('document.documentElement.scrollWidth <= innerWidth')
            mobile.keyboard.press('/');expect(mobile.locator('#search-query')).to_be_focused()
            mobile.locator('#search-query').fill('zzzz_no_vocabulary_match_zzzz')
            mobile.locator('.search-settings summary').click();mobile.locator('#search-method').select_option('tfidf')
            mobile.locator('#search-form button[type=submit]').click()
            expect(mobile.locator('#search-results')).to_contain_text('No matches above this score.')
            mobile.get_by_role('link',name='Semantic Content Analyser home',exact=True).click()
            mobile.screenshot(path=str(OUT/'home-mobile.png'),full_page=True)
            checks.append('non-WordPress XML import, visitor separation, mobile and keyboard, empty search')
            # Valid-shaped empty results and status failures exercise presentation only.
            mobile.get_by_role('link',name='Analysis',exact=True).click()
            for status in [429,410]:
                def error_route(route,_request,code=status):route.fulfill(status=code,content_type='application/json',body=json.dumps({'detail':'Controlled request budget or session failure.'}))
                mobile.route('**/api/search',error_route)
                mobile.locator('#search-query').fill('equipment');mobile.locator('#search-form button[type=submit]').click()
                expect(mobile.locator('#app-error')).to_contain_text('Wait before retrying' if status==429 else 'Reload to start')
                mobile.unroute('**/api/search',error_route)
            rev=other.request.get(base+'/api/articles').json()['collection_revision']
            mobile.get_by_role('link',name='Link opportunities',exact=True).click()
            mobile.route('**/api/links',lambda r:r.fulfill(content_type='application/json',body=json.dumps({'collection_revision':rev,'results':{'embeddings':{'results':[],'excluded':{'self':'source','existing':[],'disallowed':[]}}},'reviews':[]})))
            mobile.locator('#links-form button[type=submit]').click();expect(mobile.locator('#links-results')).to_contain_text('No eligible candidates')
            mobile.get_by_role('link',name='Content overlap',exact=True).click()
            mobile.route('**/api/overlaps',lambda r:r.fulfill(content_type='application/json',body=json.dumps({'collection_revision':rev,'pairs':[]})))
            mobile.locator('#overlap-form button[type=submit]').click();expect(mobile.locator('#overlap-results')).to_contain_text('No pairs above this threshold')
            checks.append('editor save/CSV export and replacement, development provenance, empty link/overlap and simulated budget/expiry errors')
            assert not errors and not external,(errors,external)
            browser.close()
    finally:
        server.should_exit=True;thread.join(timeout=10)
    protected=json.loads((OUT/'preservation-before.json').read_text())
    transient={'runtime/workspace.sqlite3-shm','runtime/workspace.sqlite3-wal'}
    changed=[s for s,h in protected.items() if s not in transient and (not (ROOT/s).is_file() or hashlib.sha256((ROOT/s).read_bytes()).hexdigest()!=h)]
    assert not changed,changed
    result={'checks':checks,'browser_errors':errors,'external_browser_requests':external,'public_site_fetches':0,
            'model':'deterministic test encoder only; not MiniLM quality evidence','preserved_files':len(protected)-len(set(protected)&transient),
            'transient_sqlite_sidecars_excluded':sorted(set(protected)&transient),
            'changed_protected_files':changed,'real_saved_collection_modified':False,'fixture_discovery':110,
            'fixture_selected':40,'fixture_accepted':32,'fixture_capacity_excluded':8,'network':'mock DNS/transport, local app only'}
    (OUT/'browser-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
