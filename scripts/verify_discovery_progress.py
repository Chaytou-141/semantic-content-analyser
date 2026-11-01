"""Offline Chromium verification using real extraction snapshots and intercepted assets.

No application server, model, public requests, imports or database writes.
Run: .venv/Scripts/python.exe -B scripts/verify_discovery_progress.py
"""
import hashlib
import base64
import json
import mimetypes
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tests'), str(ROOT/'scripts')]
from semantic_analyser.execution import Deadline
from semantic_analyser.fetch_policy import FetchLimits
from semantic_analyser.safe_fetch import SafeFetcher
from semantic_analyser.websites import WebsiteService
from test_safe_fetch import FakeDNS, FakeTransport
from test_websites import discover
from website_fixtures import routes
from verify_homepage_fixes import fixtures

OUT = ROOT/'runtime/discovery-progress-fixes'


def snapshots():
    data = routes('sitemap', 110)
    data['/posts/36'] = (200, b'<article>Too short</article>', {'content-type':'text/html'})
    service = WebsiteService(SafeFetcher(FetchLimits(delay_seconds=0), FakeDNS(), FakeTransport(data)))
    run = discover(service, method='sitemap')
    copy = lambda: json.loads(json.dumps(run.view()))
    views = {'selecting': copy()}
    service.select(run, list(run.candidates)[:36])
    service.step(run, Deadline(10)); views['one'] = copy()
    service.step(run, Deadline(10)); views['two'] = copy()
    while run.phase == 'extracting':
        service.step(run, Deadline(10))
    views['ready'] = copy()
    assert views['one']['processed'] == 1 and views['two']['processed'] == 2
    assert views['ready']['processed'] == 36 and len(run.articles) == 35 and len(run.failures) == 1
    # API cancellation clears extracted/accepted previews, hence reports zero.
    # UI must label its previous backend count as last confirmed, not new progress.
    views['cancelled'] = {**views['one'], 'phase':'cancelled', 'processed':0, 'articles':[]}
    return views


def main():
    from playwright.sync_api import sync_playwright, expect
    OUT.mkdir(parents=True, exist_ok=True)
    views = snapshots()
    (OUT/'extraction-snapshots.json').write_text(json.dumps(views, indent=2)+'\n', encoding='utf-8')
    articles = fixtures()['imported']
    cases, errors, blocked = [], [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chromium', args=['--disable-gpu'])
        for width, height in [(1440,900), (1366,768), (1024,600), (390,844)]:
            ctx = browser.new_context(viewport={'width':width,'height':height})
            page = ctx.new_page(); page.on('pageerror', lambda e: errors.append(str(e)))
            def respond(route):
                req = route.request; path = urlsplit(req.url).path
                if req.method != 'GET':
                    blocked.append((req.method,path)); route.abort(); return
                if path == '/api/session': payload = {'authenticated':True,'password_required':False}
                elif path == '/api/articles': payload = {'articles':articles,'collection_revision':'fixture-revision'}
                elif path == '/api/meta': payload = {'website_fetch_enabled':True,'workspace_mode':'local','idle_seconds':3600}
                else:
                    asset = ROOT/'web'/('index.html' if path=='/' else path.removeprefix('/static/'))
                    if (path!='/' and not path.startswith('/static/')) or not asset.resolve().is_relative_to((ROOT/'web').resolve()) or not asset.is_file():
                        blocked.append(req.url); route.abort(); return
                    route.fulfill(body=asset.read_bytes(), content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream'); return
                route.fulfill(content_type='application/json',body=json.dumps(payload))
            page.route('**/*', respond); page.goto('http://offline.test/')
            expect(page.locator('#workspace')).to_be_visible()
            def render(view):
                page.evaluate('r=>{renderWebsite(r); if(!$("#website-dialog").open) $("#website-dialog").showModal(); $(".website-workspace").scrollTop=0;}', view)
            def visible_actions():
                for selector in ['#website-stop', '#website-commit', '#website-extract']:
                    button=page.locator(selector)
                    if button.is_visible():
                        box=button.bounding_box()
                        assert box and box['y']>=0 and box['y']+box['height']<=height, (selector,box)
            render(views['one'])
            meter=page.locator('#extraction-meter'); expect(meter).to_be_visible()
            box=meter.bounding_box(); assert box['height']>=18 and box['width']>100
            assert box['y']>=0 and box['y']+box['height']<=height
            assert meter.evaluate('p=>[p.value,p.max]')==[1,36]
            assert page.locator('#website-progress').bounding_box()['y'] < box['y']
            # Check painted pixels, not just presence in the DOM.
            accent=page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--accent").trim()')
            rgb=tuple(int(accent.lstrip('#')[i:i+2],16) for i in (0,2,4))
            fill=page.evaluate('''async ({png,rgb})=>{const i=new Image();i.src='data:image/png;base64,'+png;await i.decode();const c=document.createElement('canvas');c.width=i.width;c.height=i.height;const x=c.getContext('2d');x.drawImage(i,0,0);const d=x.getImageData(0,0,c.width,c.height).data;let n=0;for(let j=0;j<d.length;j+=4)if(d[j]===rgb[0]&&d[j+1]===rgb[1]&&d[j+2]===rgb[2])n++;return n;}''', {'png':base64.b64encode(meter.screenshot()).decode(), 'rgb':rgb})
            assert fill>10 and fill<box['width']*box['height']/10, (fill,box,accent)
            visible_actions()
            page.screenshot(path=str(OUT/f'extraction-1-of-36-{width}.png'))
            render(views['two']); assert meter.evaluate('p=>p.value')==2
            render(views['one']); render(views['cancelled'])
            expect(page.locator('#extraction-count')).to_contain_text('Cancelled. Preview discarded. Last confirmed: 1 of 36')
            assert meter.evaluate('p=>p.value')==1
            render(views['cancelled']); assert meter.evaluate('p=>p.value')==1
            render(views['one'])
            page.evaluate('async()=>{await task("Controlled offline failure",async()=>{throw Error("Controlled request failure");});}')
            expect(page.locator('#extraction-count')).to_contain_text('Stopped. Last confirmed: 1 of 36')
            assert meter.evaluate('p=>p.value')==1
            for name in ['selecting','ready']:
                render(views[name])
                if name=='ready':
                    assert meter.evaluate('p=>[p.value,p.max]')==[36,36]
                    expect(page.locator('.website-preview-summary').first).to_contain_text('35 articles ready')
                    page.locator('.website-preview').first.locator('summary').first.click()
                    # Confirmation remains guarded for partial results; do not click it.
                    expect(page.locator('#website-partial')).not_to_be_checked()
                visible_actions()
                scroll=page.evaluate('''()=>{const w=$('.website-workspace');w.scrollTop=w.scrollHeight;return ['.website-workspace','.website-source-panel','.website-content-panel','.website-preview pre'].map(s=>{const e=$(s);return e?{selector:s,overflow:getComputedStyle(e).overflowY,height:e.clientHeight,scroll:e.scrollHeight}:null;});}''')
                assert scroll[0]['overflow']=='auto' and scroll[0]['scroll']>scroll[0]['height'], scroll
                assert all(x is None or x['overflow'] not in ['auto','scroll'] for x in scroll[1:]), scroll
                visible_actions()
                page.screenshot(path=str(OUT/f'{name}-{width}.png'))
            assert page.evaluate('state.articles')==articles
            cases.append({'viewport':[width,height], 'bar_bounds':box,'painted_fill_pixels':fill,'checks':['1/36','2/36','cancelled','failed request','36/36 with one failed','long selection/review single scroll','fixed actions','saved collection unchanged']})
            ctx.close()
        browser.close()
    assert not errors and not blocked, (errors,blocked)
    protected=json.loads((OUT/'preservation-before.json').read_text())
    changed=[s for s,h in protected.items() if not (ROOT/s).is_file() or hashlib.sha256((ROOT/s).read_bytes()).hexdigest()!=h]
    assert not changed, changed
    report={'cases':cases,'browser_errors':errors,'blocked_requests':blocked,'protected_files':len(protected),'unexpected_changes':changed,'live_requests':0,'model_runs':0,'database_writes':0}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'viewports_passed':len(cases),'protected_files':len(protected),'browser_errors':errors,'live_requests':0,'model_runs':0}))


if __name__=='__main__': main()
