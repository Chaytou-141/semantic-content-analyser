"""Offline feature export availability and download wiring."""
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit
import pytest
from playwright.sync_api import sync_playwright, expect
from semantic_analyser.storage import demo_articles
from semantic_analyser.pdf_report import build_report
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('width',[1280,390])
def test_feature_export_controls_and_downloads(width):
    articles=demo_articles();calls=[];errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page(viewport={'width':width,'height':900},accept_downloads=True)
        page.on('pageerror',lambda e:errors.append(str(e)))
        def route(r):
            path=urlsplit(r.request.url).path
            if path.startswith('/api/reports/'):
                assert r.request.method=='POST'
                section=path.split('/')[3];calls.append(section)
                r.fulfill(body=b'%PDF-1.4\n%offline download fixture',content_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="{section}-analysis.pdf"'});return
            assert r.request.method=='GET'
            if path=='/api/session':payload={'authenticated':True,'password_required':False}
            elif path=='/api/articles':payload={'articles':[a.model_dump() for a in articles],'collection_revision':'fixture'}
            elif path=='/api/meta':payload={'website_fetch_enabled':True,'workspace_mode':'local'}
            else:
                asset=ROOT/'web'/('index.html' if path=='/' else path.removeprefix('/static/'))
                assert asset.is_file() and asset.resolve().is_relative_to((ROOT/'web').resolve())
                r.fulfill(body=asset.read_bytes(),content_type=mimetypes.guess_type(asset)[0] or 'application/octet-stream');return
            r.fulfill(json=payload)
        page.route('**/*',route);page.goto('http://offline.test/#search')
        expect(page.locator('#workspace')).to_be_visible()
        assert page.locator('#analysis-nav [data-export-pdf]').count()==0
        for section in ['search','links','overlaps']:
            expect(page.locator(f'[data-export-pdf="{section}"]')).to_be_disabled()
        page.evaluate("()=>{renderSearch({results:{tfidf:[]},elapsed_ms:0});}")
        expect(page.locator('[data-export-pdf="search"]')).to_be_enabled()
        expect(page.locator('[data-export-pdf="links"]')).to_be_disabled()
        page.evaluate("()=>{state.sourceId='A01';renderLinks({results:{tfidf:{results:[],excluded:{self:'A01',existing:[],disallowed:[]}}},reviews:[]});renderOverlaps({pairs:[]});}")
        for section,view in [('search','search'),('links','links'),('overlaps','overlap')]:
            page.evaluate('view=>navigate(view)',view)
            button=page.locator(f'[data-export-pdf="{section}"]');expect(button).to_be_visible()
            bounds=button.bounding_box();assert bounds['x']>=0 and bounds['x']+bounds['width']<=width
            with page.expect_download() as downloaded:button.click()
            assert downloaded.value.suggested_filename==f'{section}-analysis.pdf'
            page.wait_for_function('!state.busy')
        assert calls==['search','links','overlaps']
        page.evaluate('invalidateResults()')
        for section in ['search','links','overlaps']:expect(page.locator(f'[data-export-pdf="{section}"]')).to_be_disabled()
        assert not errors
        browser.close()
