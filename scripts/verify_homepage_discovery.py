"""Offline homepage-form -> real WebsiteService -> article selection browser check."""
import hashlib
import json
import mimetypes
import sqlite3
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'scripts')]
from semantic_analyser.execution import Deadline
from test_homepage_discovery import mixed_routes, make_service
from website_fixtures import BASE


def main():
    from playwright.sync_api import sync_playwright,expect
    out=ROOT/'runtime/homepage-discovery';out.mkdir(parents=True,exist_ok=True)
    original=json.loads((ROOT/'runtime/discovery-progress-fixes/preservation-before.json').read_text())
    # Start a new baseline: a user may legitimately have imported a new collection
    # since the earlier milestone. Never restore data to satisfy an old fixture.
    protected={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in original if (ROOT/p).is_file()}
    (out/'preservation-before.json').write_text(json.dumps(protected,indent=2)+'\n',encoding='utf-8')
    connection=sqlite3.connect('file:'+str(ROOT/'runtime/workspace.sqlite3')+'?mode=ro',uri=True)
    try:articles=[json.loads(r[0]) for r in connection.execute('SELECT payload FROM articles ORDER BY id')]
    finally:connection.close()
    cases=[];errors=[];blocked=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chromium')
        for width,height in [(1440,900),(1024,600),(390,844)]:
            svc,wire=make_service(mixed_routes());runs=[];posts=[]
            ctx=browser.new_context(viewport={'width':width,'height':height})
            page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            def respond(route):
                req=route.request;path=urlsplit(req.url).path
                if req.method=='POST':
                    data=req.post_data_json;posts.append(path)
                    if path=='/api/website/start':
                        assert data['url']==BASE and data['method']=='auto'
                        run=svc.start('offline-owner','fixture-revision',data['url'],data['method']);runs.append(run)
                        payload=run.view()
                    elif path=='/api/website/step':
                        assert data['run_id']==runs[-1].identifier
                        payload=svc.step(runs[-1],Deadline(10))
                    else:blocked.append((req.method,path));route.abort();return
                elif req.method!='GET':blocked.append((req.method,path));route.abort();return
                elif path=='/api/session':payload={'authenticated':True,'password_required':False}
                elif path=='/api/articles':payload={'articles':articles,'collection_revision':'fixture-revision'}
                elif path=='/api/meta':payload={'website_fetch_enabled':True,'workspace_mode':'local','idle_seconds':3600}
                else:
                    asset=ROOT/'web'/('index.html' if path=='/' else path.removeprefix('/static/'))
                    if (path!='/' and not path.startswith('/static/')) or not asset.resolve().is_relative_to((ROOT/'web').resolve()) or not asset.is_file():
                        blocked.append(req.url);route.abort();return
                    route.fulfill(body=asset.read_bytes(),content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream');return
                route.fulfill(content_type='application/json',body=json.dumps(payload))
            page.route('**/*',respond);page.goto('http://offline.test/')
            page.locator('#home-website-url').fill(BASE)
            page.locator('#home-website-form button[type=submit]').click()
            expect(page.locator('.website-candidate')).to_have_count(14)
            expect(page.locator('#website-progress')).to_contain_text('Choose your articles')
            expect(page.locator('#website-results')).to_contain_text('not the complete website')
            expect(page.locator('#website-method')).to_have_value('auto')
            expect(page.locator('#website-source-settings')).not_to_have_attribute('open','')
            expect(page.locator('.dialog-error')).to_have_count(0)
            page.get_by_role('button',name='Select first 40 shown').click()
            expect(page.locator('#website-extract')).to_have_text('Extract 14 selected articles')
            box=page.locator('#website-extract').bounding_box()
            assert box and box['y']>=0 and box['y']+box['height']<=height
            assert page.evaluate('state.articles')==articles
            assert len(runs)==1 and runs[0].session.requests==6 and len(posts)==4
            assert not any('store-' in u or 'wp-json' in u for u,_,_ in wire.calls)
            page.screenshot(path=str(out/f'articles-found-{width}.png'))
            cases.append({'viewport':[width,height],'candidates':14,'mock_wire_requests':6,'api_posts':posts,'collection_unchanged':True})
            ctx.close()
        browser.close()
    assert not errors and not blocked,(errors,blocked)
    changed=[p for p,h in protected.items() if not (ROOT/p).is_file() or hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    assert not changed,changed
    report={'cases':cases,'browser_errors':errors,'blocked_requests':blocked,'protected_files':len(protected),'unexpected_changes':changed,'saved_articles':len(articles),'saved_characters':sum(len(a['title'])+len(a['body']) for a in articles),'live_requests':0,'real_model_runs':0,'saved_database_writes':0}
    (out/'browser-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'browser_viewports_passed':len(cases),'protected_files_unchanged':len(protected),'live_requests':0,'real_model_runs':0}))


if __name__=='__main__':main()
