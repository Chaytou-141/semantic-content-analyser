"""Offline source/destination evidence, accessibility and source-integrity regression."""
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit
import pytest
from playwright.sync_api import sync_playwright,expect
from link_ui_fixtures import fixture,REVISION
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('width,height',[(1440,1000),(390,844)])
def test_direction_and_original_evidence(width,height):
    articles,groups,reviews=fixture();errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page(viewport={'width':width,'height':height},reduced_motion='reduce')
        page.on('pageerror',lambda e:errors.append(str(e)))
        def respond(route):
            path=urlsplit(route.request.url).path
            assert route.request.method=='GET'
            if path=='/api/session':payload={'authenticated':True,'password_required':False}
            elif path=='/api/articles':payload={'articles':articles,'collection_revision':REVISION}
            elif path=='/api/meta':payload={'website_fetch_enabled':True,'workspace_mode':'local'}
            else:
                asset=ROOT/'web'/('index.html' if path=='/' else path.removeprefix('/static/'))
                assert asset.is_file() and asset.resolve().is_relative_to((ROOT/'web').resolve())
                route.fulfill(body=asset.read_bytes(),content_type=mimetypes.guess_type(asset)[0] or 'application/octet-stream');return
            route.fulfill(json=payload)
        page.route('**/*',respond);page.goto('http://offline.test/#links')
        expect(page.locator('#workspace')).to_be_visible()
        page.evaluate('p=>{state.sourceId="S01";renderLinks(p)}',{'results':{'embeddings':groups['embeddings']},'reviews':reviews,'collection_revision':REVISION})
        panel=page.locator('.link-detail')
        for i,result in enumerate(groups['embeddings']['results']):
            page.locator('[role=tab]').nth(i).click()
            src=panel.locator('.link-passage--source');dst=panel.locator('.link-passage--destination')
            expect(src.locator('h4')).to_have_text('Source \u00b7 link from')
            expect(dst.locator('h4')).to_have_text('Destination \u00b7 link to')
            expect(src.locator('h5')).to_have_text(articles[0]['title'])
            expect(dst.locator('h5')).to_have_text(result['title'])
            expect(panel.locator('.link-evidence-direction')).to_contain_text('Suggested link')
            assert src.locator('a').get_attribute('href')==articles[0]['url']
            assert dst.locator('a').get_attribute('href')==result['url']
            for node,original,start,end,summary in [(src,result['source_passage'],result['source_start'],result['source_end'],'Read full source passage'),(dst,result['passage'],result['passage_start'],result['passage_end'],'Read full destination passage')]:
                assert node.locator('pre').text_content()==original
                assert original.startswith(node.locator('blockquote').text_content())
                assert f'{start}\u2013{end}' in node.locator('.link-offsets').text_content()
                node.get_by_text(summary,exact=True).focus();page.keyboard.press('Enter')
                expect(node.locator('pre')).to_be_visible()
                assert node.locator('h5').evaluate('e=>getComputedStyle(e).fontFamily').startswith('"Instrument Sans"')
                assert 'Georgia' in node.locator('blockquote').evaluate('e=>getComputedStyle(e).fontFamily')
                node.get_by_text(summary,exact=True).press('Enter')
            assert src.evaluate('e=>getComputedStyle(e).borderLeftColor')!=dst.evaluate('e=>getComputedStyle(e).borderLeftColor')
            assert src.bounding_box()['y']<panel.locator('.link-evidence-direction').bounding_box()['y']<dst.bounding_box()['y']
        page.locator('[role=tab]').first.focus();page.keyboard.press('ArrowDown')
        expect(page.locator('[role=tab]').nth(1)).to_be_focused()
        page.locator('[role=tab]').first.click()
        out=ROOT/'runtime/evidence-direction';out.mkdir(exist_ok=True,parents=True)
        panel.locator('.link-evidence-flow').screenshot(path=str(out/f'evidence-{width}.png'))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert page.evaluate('state.articles')==articles
        assert page.evaluate('state.lastLinks.results.embeddings')==groups['embeddings']
        assert not errors
        browser.close()
