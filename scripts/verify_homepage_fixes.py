"""Homepage-only browser tests. Mock API, local assets, no model or network service."""
import csv
import hashlib
import json
import mimetypes
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/homepage-fixes'


def fixtures():
    connection=sqlite3.connect('file:'+str(ROOT/'runtime/workspace.sqlite3')+'?mode=ro',uri=True)
    try:current=[json.loads(r[0]) for r in connection.execute('SELECT payload FROM articles ORDER BY id')]
    finally:connection.close()
    assert len(current)==32 and sum(len(a['title'])+len(a['body']) for a in current)==249162
    with (ROOT/'data/synthetic_articles.csv').open(encoding='utf-8') as f:sample=list(csv.DictReader(f))
    for a in sample:
        a['eligible']=a.get('eligible','true').lower() not in {'false','0','no'}
        a['existing_links']=[x for x in a.get('existing_links','').split(';') if x]
        a['url']='https://example.com/articles/'+a['id'].lower()
        a.setdefault('topic','')
    return {'imported':current,'sample':sample}


def main():
    from playwright.sync_api import sync_playwright,expect
    OUT.mkdir(parents=True,exist_ok=True)
    cases=[];errors=[];mutations=[];unhandled=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='chromium',args=['--disable-gpu'])
        for kind,articles in fixtures().items():
            for width in [1440,390,320]:
                ctx=browser.new_context(viewport={'width':width,'height':900})
                page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                def respond(route):
                    req=route.request;path=urlsplit(req.url).path
                    if req.method!='GET':mutations.append((req.method,path));route.abort();return
                    if path=='/api/session':payload={'authenticated':True,'password_required':False}
                    elif path=='/api/articles':payload={'articles':articles,'collection_revision':'fixture-revision'}
                    elif path=='/api/meta':payload={'website_fetch_enabled':True,'workspace_mode':'local','idle_seconds':3600}
                    else:
                        asset=ROOT/'web'/('index.html' if path=='/' else path.removeprefix('/static/'))
                        if path!='/' and not path.startswith('/static/') or not asset.resolve().is_relative_to((ROOT/'web').resolve()) or not asset.is_file():
                            unhandled.append(req.url);route.abort();return
                        route.fulfill(body=asset.read_bytes(),content_type=mimetypes.guess_type(str(asset))[0] or 'application/octet-stream');return
                    route.fulfill(content_type='application/json',body=json.dumps(payload))
                page.route('**/*',respond);page.goto('http://homepage.test/')
                expect(page.locator('#workspace')).to_be_visible()
                expect(page.locator('#home-sample-note')).not_to_be_empty()
                if kind=='imported':
                    expect(page.locator('#home-current-collection')).to_be_visible()
                    expect(page.locator('#home-continue')).to_have_text('Continue with your 32 articles')
                    expect(page.locator('#home-explore')).to_have_text('View sample options')
                    assert page.locator('.sample-entry #home-continue').count()==0
                    page.locator('#home-explore').click();expect(page.locator('#sample-dialog')).to_be_visible()
                    page.once('dialog',lambda d:d.dismiss());page.locator('#sample-restore').click()
                    expect(page.locator('#sample-dialog')).to_be_visible()
                    assert page.evaluate('state.articles')==articles and not mutations
                    page.locator('#sample-keep').click();expect(page.locator('#view-search')).to_be_visible()
                    page.locator('.brand').click()
                    page.locator('#home-continue').click();expect(page.locator('#view-search')).to_be_visible()
                    page.locator('.brand').click()
                else:
                    expect(page.locator('#home-current-collection')).to_be_hidden()
                    page.locator('#home-explore').click();expect(page.locator('#view-search')).to_be_visible()
                    page.locator('.brand').click()
                cards=page.get_by_role('navigation',name='Analysis tools').get_by_role('link')
                expect(cards).to_have_count(3)
                gaps=cards.evaluate_all('''cards => cards.map(c=>({gap:c.querySelector('p').getBoundingClientRect().top-c.querySelector('h2').getBoundingClientRect().bottom,width:c.getBoundingClientRect().width}))''')
                assert all(c['gap']>=12 and c['width']>0 for c in gaps),gaps
                for index,view in enumerate(['search','links','overlap']):
                    cards.nth(index).focus();page.keyboard.press('Enter')
                    expect(page.locator('#view-'+view)).to_be_visible();page.go_back();expect(page.locator('#view-home')).to_be_visible()
                page.screenshot(path=str(OUT/f'after-{kind}-{width}.png'),full_page=True)
                about=page.locator('#about-demo');summary=about.locator('summary')
                for enlarged in [False,True]:
                    if enlarged:summary.evaluate("s=>s.style.fontSize='30px'")
                    summary.focus();summary.evaluate("s=>s.scrollIntoView({block:'center'})")
                    bounds=summary.evaluate('''s=>{const r=s.getBoundingClientRect(),t=s.querySelector('span').getBoundingClientRect(),i=s.querySelector('svg').getBoundingClientRect();return {left:r.left,right:r.right,bottom:r.bottom,top:r.top,textLeft:t.left,textRight:t.right,iconLeft:i.left,viewport:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth}}''')
                    assert 0<=bounds['left']<=bounds['textLeft']<bounds['textRight']<=bounds['right']<=width
                    assert bounds['iconLeft']>=bounds['left'] and bounds['top']>=0 and bounds['bottom']<=bounds['height'] and not bounds['overflow'],bounds
                    page.keyboard.press('Enter');assert about.get_attribute('open') is not None
                    page.keyboard.press('Space');assert about.get_attribute('open') is None
                about.screenshot(path=str(OUT/f'about-enlarged-{kind}-{width}.png'))
                assert page.evaluate('state.articles')==articles
                cases.append({'collection':kind,'width':width,'feature_gaps':gaps,'enlarged_summary_bounds':bounds,'sample_overwrite_requests':0})
                ctx.close()
        browser.close()
    assert not errors and not mutations and not unhandled,(errors,mutations,unhandled)
    protected=json.loads((OUT/'preservation-before.json').read_text())
    changed=[s for s,h in protected.items() if not (ROOT/s).is_file() or hashlib.sha256((ROOT/s).read_bytes()).hexdigest()!=h]
    assert not changed,changed
    report={'cases':cases,'passed_cases':len(cases),'browser_errors':errors,'mutating_requests':mutations,'unhandled_external_requests':unhandled,
            'model_inference_runs':0,'live_website_requests':0,'backend_services_started':0,'protected_files':len(protected),'unexpected_changes':changed,
            'footer_before':'No clipping/overflow reproduced in fresh Chromium at 1440/390/320. Native summary marker layout replaced by contained flex icon/text, not a claim of reproduced fixed-position bug.'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed_cases':len(cases),'browser_errors':errors,'mutating_requests':mutations,'protected_files':len(protected)}))


if __name__=='__main__':main()
