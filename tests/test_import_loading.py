"""Offline import lifecycle UI checks: no server, saved DB or live network."""
import json
import mimetypes
from pathlib import Path
import sys
from urllib.parse import urlsplit
import pytest
from playwright.sync_api import sync_playwright, expect
from semantic_analyser.storage import demo_articles
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_discovery_progress import snapshots

@pytest.mark.parametrize('width,height',[(1366,768),(390,844)])
def test_import_loading_lifecycle(width,height):
    views=snapshots()
    articles=[a.model_dump() for a in demo_articles()]
    errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch()
        page=browser.new_page(viewport={'width':width,'height':height})
        page.on('pageerror',lambda e:errors.append(str(e)))
        def respond(route):
            path=urlsplit(route.request.url).path
            assert route.request.method=='GET','Unexpected real mutation'
            if path=='/api/session': value={'authenticated':True,'password_required':False}
            elif path=='/api/articles': value={'articles':articles,'collection_revision':'fixture'}
            elif path=='/api/meta': value={'website_fetch_enabled':True,'workspace_mode':'local'}
            else:
                asset=ROOT/'web'/('index.html' if path=='/' else path.removeprefix('/static/'))
                assert asset.is_file() and asset.resolve().is_relative_to((ROOT/'web').resolve())
                route.fulfill(body=asset.read_bytes(),content_type=mimetypes.guess_type(asset)[0] or 'application/octet-stream');return
            route.fulfill(json=value)
        page.route('**/*',respond);page.goto('http://offline.test/')
        expect(page.locator('#workspace')).to_be_visible()
        page.evaluate('''v=>{window.views=v;window.calls=[];window.originalApi=api;
          api=async(path,...args)=>{calls.push(path);if(path.endsWith('/start'))return {...views.selecting,phase:'discovering'};
          if(path.endsWith('/step')) return await new Promise(resolve=>window.finishStep=resolve);
          if(path.endsWith('/cancel')) return views.cancelled;throw Error('Unexpected '+path);};
          $('#website-dialog').showModal();$('#website-url').value='https://example.com/';
        }''',views)
        page.locator('#website-form button[type=submit]').click()
        expect(page.locator('.website-loading h3')).to_have_text('Discovering website articles')
        expect(page.locator('.website-loading strong')).to_have_text('110 articles found so far')
        expect(page.locator('#busy')).to_be_hidden()
        expect(page.locator('.website-loading .spinner')).to_be_visible()
        assert page.locator('.website-loading progress').count()==0
        assert page.locator('.website-loading').evaluate('e=>getComputedStyle(e).display')=='flex'
        assert page.locator('.website-loading').evaluate('e=>getComputedStyle(e).alignItems')=='center'
        spinner=page.locator('.website-loading .spinner').bounding_box()
        assert spinner['width']>=28 and spinner['height']>=28
        assert spinner['y']>=0 and spinner['y']+spinner['height']<=height
        out=ROOT/'runtime/import-loading';out.mkdir(exist_ok=True,parents=True)
        page.screenshot(path=str(out/f'discovery-{width}.png'))
        # Duplicate discovery cannot enqueue another start.
        page.evaluate("$('#website-form').dispatchEvent(new Event('submit',{cancelable:true}))")
        assert page.evaluate("calls.filter(x=>x.endsWith('/start')).length")==1
        page.locator('#website-stop').click()
        expect(page.locator('#website-progress')).to_contain_text('Cancellation requested')
        assert 'cancelled' not in page.locator('#website-progress').inner_text().lower()
        page.evaluate('finishStep(views.one)')
        page.wait_for_function('!state.busy')
        expect(page.locator('#website-progress')).to_contain_text('Import cancelled')
        expect(page.locator('.website-loading')).to_have_count(0)
        expect(page.locator('#website-operation')).to_be_hidden()
        # Cancellation failure remains uncertain and allows retry, not success copy.
        page.evaluate("()=>{renderWebsite(views.one);api=async()=>{throw Error('Cancel request failed')};}")
        page.locator('#website-stop').click()
        page.wait_for_function('!state.busy')
        expect(page.locator('#website-progress')).to_contain_text('server work may still be finishing')
        expect(page.locator('#website-stop')).to_be_enabled()
        assert 'Import cancelled' not in page.locator('#website-progress').inner_text()
        # Extraction uses actual counters, then transitions to review (not import).
        page.evaluate('websiteCancelled=false;renderWebsite(views.one)')
        expect(page.locator('#extraction-meter')).to_be_visible()
        assert page.locator('#extraction-meter').evaluate('e=>[e.value,e.max]')==[1,36]
        assert page.locator('#extraction-meter').bounding_box()['height']>=18
        expect(page.locator('#extraction-outcomes')).to_contain_text('0 failed')
        out=ROOT/'runtime/import-loading';out.mkdir(exist_ok=True,parents=True)
        page.screenshot(path=str(out/f'extract-{width}.png'))
        page.evaluate('renderWebsite(views.ready)')
        expect(page.locator('#extraction-outcomes')).to_contain_text('35 ready for review (not imported)')
        expect(page.locator('#extraction-outcomes')).to_contain_text('1 failed')
        expect(page.locator('#website-commit')).to_be_visible()
        assert '/api/website/import' not in page.evaluate('calls')
        # Failed response clears active spinner without claiming the server stopped.
        page.evaluate('''()=>{renderWebsite({...views.selecting,phase:'discovering'});
          window.failedTask=task('Checking...',async()=>{throw Error('Fixture timeout');});}''')
        page.wait_for_function('!state.busy')
        expect(page.locator('.website-loading')).to_have_count(0)
        expect(page.locator('#website-progress')).to_contain_text('server work may still be finishing')
        expect(page.locator('#website-operation')).to_be_hidden()
        # Confirmed import: validation stays in modal, refresh moves to active page.
        page.evaluate('''()=>{renderWebsite(views.ready);window.confirm=()=>true;
          api=async(path)=>{calls.push(path);if(path.endsWith('/import'))return await new Promise(resolve=>window.finishImport=resolve);
           if(path==='/api/articles')return await new Promise(resolve=>window.finishLoad=resolve);
           if(path==='/api/meta')return {website_fetch_enabled:true,workspace_mode:'local'};throw Error(path);};}''')
        page.locator('#website-commit').click()
        expect(page.locator('#website-operation')).to_be_visible()
        expect(page.locator('#website-operation-text')).to_contain_text('validating')
        expect(page.locator('#busy')).to_be_hidden()
        page.evaluate('finishImport({count:35})')
        expect(page.locator('#website-dialog')).not_to_be_visible()
        expect(page.locator('#busy')).to_be_visible()
        expect(page.locator('#busy-message')).to_contain_text('Loading your imported collection')
        page.evaluate('''a=>finishLoad({articles:a,collection_revision:'imported'})''',articles)
        page.wait_for_function('!state.busy')
        expect(page.locator('#busy')).to_be_hidden()
        expect(page.locator('#website-operation')).to_be_hidden()
        assert not any(x in page.evaluate('calls') for x in ['/api/search','/api/links','/api/overlaps'])
        assert page.evaluate('state.articles')==articles
        assert not errors,errors
        browser.close()


def test_import_assets_use_updated_matching_cache_versions():
    import re
    html=(ROOT/'web/index.html').read_text(encoding='utf-8')
    css=re.search(r'/static/styles.css\?v=([^"\s]+)',html).group(1)
    js=re.search(r'/static/app.js\?v=([^"\s]+)',html).group(1)
    assert css==js and css!='link-workbench-20261101'
