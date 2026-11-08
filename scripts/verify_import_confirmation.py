"""Offline native-confirm/repeated-click regression; no actual imports or inference."""
import hashlib
import json
import mimetypes
from pathlib import Path
import sqlite3
import subprocess
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'scripts')]
from verify_discovery_progress import snapshots


def main():
    from playwright.sync_api import sync_playwright,expect
    baseline='--baseline' in sys.argv
    baseline_js=subprocess.check_output(['git','show','c859346:web/app.js'],cwd=ROOT) if baseline else None
    out=ROOT/'runtime/import-confirmation';out.mkdir(parents=True,exist_ok=True)
    db=ROOT/'runtime/workspace.sqlite3';before=hashlib.sha256(db.read_bytes()).hexdigest()
    connection=sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True)
    try:articles=[json.loads(r[0]) for r in connection.execute('SELECT payload FROM articles ORDER BY id')]
    finally:connection.close()
    ready=snapshots()['ready'];cases=[];errors=[];blocked=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chromium')
        for width in ([1440] if baseline else [1440,390]):
            for mode in (['accept'] if baseline else ['accept','cancel','failure']):
                ctx=browser.new_context(viewport={'width':width,'height':900})
                page=ctx.new_page();pending=[];prompts=[];imports=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                def dialog(d):
                    prompts.append(d.message)
                    if mode=='cancel' or (mode=='failure' and len(prompts)>1):d.dismiss()
                    else:d.accept()
                page.on('dialog',dialog)
                def respond(route):
                    req=route.request;path=urlsplit(req.url).path
                    if req.method=='POST' and path=='/api/website/import':
                        imports.append(req.post_data_json);pending.append(route);return
                    if req.method!='GET':blocked.append((req.method,path));route.abort();return
                    if path=='/api/session':payload={'authenticated':True,'password_required':False}
                    elif path=='/api/articles':payload={'articles':articles,'collection_revision':'fixture-revision'}
                    elif path=='/api/meta':payload={'website_fetch_enabled':True,'workspace_mode':'local','idle_seconds':3600}
                    else:
                        asset=ROOT/'web'/('index.html' if path=='/' else path.removeprefix('/static/'))
                        if (path!='/' and not path.startswith('/static/')) or not asset.resolve().is_relative_to((ROOT/'web').resolve()) or not asset.is_file():
                            blocked.append(req.url);route.abort();return
                        content=baseline_js if baseline and path=='/static/app.js' else asset.read_bytes()
                        route.fulfill(body=content,content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream');return
                    route.fulfill(content_type='application/json',body=json.dumps(payload))
                page.route('**/*',respond);page.goto('http://offline.test/')
                expect(page.locator('#workspace')).to_be_visible()
                page.evaluate('r=>{renderWebsite(r);$("#website-dialog").showModal();$("#website-partial").checked=true;}',ready)
                if not baseline:
                    page.evaluate('state.busy=true;$("#website-commit").dispatchEvent(new MouseEvent("click",{bubbles:true}));')
                    assert not prompts and not imports
                    page.evaluate('state.busy=false')
                page.locator('#website-commit').click()
                if mode=='cancel':
                    assert len(prompts)==1 and not imports
                    expect(page.locator('#website-commit')).to_be_enabled()
                    assert page.evaluate('websiteRun.phase')=='ready'
                    assert page.evaluate('state.articles')==articles
                else:
                    page.wait_for_function('state.busy')
                    # A second event during the outstanding request must be ignored,
                    # even if dispatched programmatically past a disabled button.
                    page.evaluate('$("#website-commit").dispatchEvent(new MouseEvent("click",{bubbles:true}))')
                    assert len(prompts)==(2 if baseline else 1),prompts
                    assert len(imports)==1 and imports[0]['accept_partial'] is True
                    if not baseline:expect(page.locator('#website-commit')).to_be_disabled()
                    pending.pop().fulfill(status=422 if mode=='failure' else 200,content_type='application/json',
                        body=json.dumps({'detail':'Controlled admission failure'} if mode=='failure' else {'count':35,'collection_revision':'fixture-revision'}))
                    page.wait_for_function('!state.busy')
                    if mode=='failure':
                        expect(page.locator('#website-commit')).to_be_enabled()
                        assert page.evaluate('websiteRun.phase')=='ready'
                        page.locator('#website-commit').click()  # Deliberate retry may ask again.
                        assert len(prompts)==2 and len(imports)==1
                        assert page.evaluate('state.articles')==articles
                    elif not baseline:
                        expect(page.locator('#website-dialog')).not_to_be_visible()
                        page.evaluate('$("#website-commit").dispatchEvent(new MouseEvent("click",{bubbles:true}))')
                        assert len(prompts)==1 and len(imports)==1
                cases.append({'width':width,'case':mode,'confirmations':len(prompts),'intentional_retry_confirmation':mode=='failure','mock_import_requests':len(imports)})
                ctx.close()
        browser.close()
    assert not errors and not blocked,(errors,blocked)
    assert hashlib.sha256(db.read_bytes()).hexdigest()==before
    report={'baseline':baseline,'cases':cases,'browser_errors':errors,'blocked_requests':blocked,'development_database_unchanged':True,'live_requests':0,'real_model_runs':0}
    (out/('baseline.json' if baseline else 'verification.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':main()
