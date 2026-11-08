"""Shared-word highlighting is a safe display aid, never model attribution."""
from pathlib import Path
import json
import re
import subprocess
from urllib.parse import urlsplit
import pytest
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('width',[1366,390])
def test_overlap_highlights_preserve_exact_text(client,width):
    left='A tennis court with synthetic turf creates an outdoor recreation space. Café visitors enjoy this court.\n\n'+('Original supporting context. '*20)
    right='Synthetic turf surrounds the outdoor tennis court. The café offers a different recreation experience.\n\n'+('More original context. '*20)
    row=lambda aid,text:{'id':aid,'title':'Article '+aid,'topic':'','url':'https://example.com/'+aid,'score':0.842,'passage':text,'passage_start':20,'passage_end':20+len(text)}
    payload={'pairs':[{'left':row('A',left),'right':row('B',right),'score':0.842}]}
    with sync_playwright() as pw:
        browser=pw.chromium.launch();page=browser.new_page(viewport={'width':width,'height':900},reduced_motion='reduce')
        def route(r):
            assert r.request.method=='GET'
            response=client.get(urlsplit(r.request.url).path)
            r.fulfill(status=response.status_code,body=response.content,headers={'Content-Type':response.headers.get('content-type','text/plain')})
        page.route('**/*',route);page.goto('http://offline.test/#overlap')
        expect(page.locator('#workspace')).to_be_visible()
        page.evaluate('p=>renderOverlaps(p)',payload)
        marks=page.locator('.evidence-preview mark')
        expect(page.locator('.overlap-wording strong')).to_contain_text('Common terms:')
        assert marks.count()>0
        assert 'tennis' in [x.lower() for x in marks.all_text_contents()]
        expect(page.locator('.overlap-wording')).to_contain_text('Highlighted terms appear in both passages. They do not determine the semantic similarity score.')
        assert page.evaluate("sharedEvidenceWords('the this have with same','this same with have')")==[]
        assert page.evaluate("sharedEvidenceWords('courts tennis','court tennis')")==['tennis']
        assert page.evaluate("sharedEvidenceWords('Forest ecology','Bakery pastries')")==[]
        for i,text in enumerate([left,right]):
            block=page.locator('.evidence-block').nth(i)
            expected=page.evaluate("s=>{const clean=displayText(s);return clean.length>320?clean.slice(0,320).replace(/\\s+\\S*$/u,'')+'\\u2026':clean}",text)
            assert block.locator('.evidence-preview').text_content()==expected
            block.locator('summary').focus();page.keyboard.press('Enter')
            expect(block.locator('pre')).to_be_visible()
            assert block.locator('pre').text_content()==text
            assert block.locator('pre mark').count()>0
            assert f'20\u2013{20+len(text)}' in block.locator('.context-note').text_content()
            block.locator('summary').press('Enter')
            expect(block.locator('pre')).not_to_be_visible()
            assert block.locator('.evidence-preview mark').count()>0
            block.locator('summary').press('Enter')
        out=ROOT/'runtime/overlap-highlights';out.mkdir(exist_ok=True,parents=True)
        page.locator('#overlap-results').screenshot(path=str(out/f'overlap-{width}.png'))
        malicious='<img src=x onerror="window.injected=true"> Shared tennis court'
        page.evaluate('s=>{const box=evidence(s,"overlap passage",0,s.length,["shared","tennis","court"]);document.body.append(box);window.testEvidence=box}',malicious)
        assert page.evaluate('testEvidence.querySelector("pre").textContent')==malicious
        assert page.evaluate('testEvidence.querySelectorAll("img").length')==0
        assert not page.evaluate('window.injected || false')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        empty={'pairs':[{'left':row('A','The 2026 court.'),'right':row('B','The 2026 courts.'),'score':0.842}]}
        page.evaluate('p=>renderOverlaps(p)',empty)
        expect(page.locator('.overlap-wording')).to_contain_text('No common terms highlighted')
        assert page.locator('#overlap-results mark').count()==0
        expect(page.locator('.pair-heading')).to_contain_text('0.842')
        browser.close()


@pytest.mark.parametrize('left,right,expected',[
    ('Court, TENNIS! synthetic-turf.', '(COURT); tennis / turf?', ['court','tennis','turf']),
    ('court courts tennis', 'COURTS Tennis', ['courts','tennis']),
    ('court', 'courts', []),
    ('The this with 2026 1234', 'WITH this the 2026 1234', []),
    ('', '', []),
    ('Caf\u00e9, SYNTHETIC!', 'CAF\u00c9 synthetic', ['caf\u00e9','synthetic']),
    ('tennis tennis tennis', 'Tennis', ['tennis']),
    ('Forest ecology', 'Bakery pastries', []),
])
def test_exact_common_term_rules(left,right,expected):
    source=(ROOT/'web/app.js').read_text(encoding='utf-8')
    display=re.search(r'^function displayText\(text\) \{.*$',source,re.M).group()
    helper=re.search(r'function sharedEvidenceWords\(left, right\) \{.*?^\}',source,re.S|re.M).group()
    result=subprocess.run(['node','-e',display+'\n'+helper+'\nconsole.log(JSON.stringify(sharedEvidenceWords('+json.dumps(left)+','+json.dumps(right)+')));'],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)==expected
