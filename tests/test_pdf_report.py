from io import BytesIO
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from semantic_analyser.api import create_app
from semantic_analyser.config import Settings
from semantic_analyser.pdf_report import build_report
from semantic_analyser.schemas import Article


def text_of(data):
    return '\n'.join(p.extract_text() for p in PdfReader(BytesIO(data)).pages)


def export(client,section,headers=None):
    response=client.post(f'/api/reports/{section}/pdf',json={},headers=headers)
    assert response.status_code==200,response.text if response.status_code!=200 else ''
    assert response.headers['content-type']=='application/pdf'
    assert response.headers['content-disposition']==f'attachment; filename="{section}-analysis.pdf"'
    assert response.headers['cache-control']=='no-store'
    return response


@pytest.mark.parametrize('section',['search','links','overlaps'])
def test_unavailable_and_old_route(client,section):
    assert client.post(f'/api/reports/{section}/pdf',json={}).status_code==409
    assert client.post('/api/reports/pdf',json={}).status_code==404


def test_separate_reports_correct_scores_links_reviews(client,monkeypatch):
    search=client.post('/api/search',json={'query':'Private coffee station query','method':'tfidf','top_k':3}).json()
    links=client.post('/api/links',json={'source_id':'A08','method':'tfidf','top_k':3}).json()
    overlap=client.post('/api/overlaps',json={'method':'tfidf','threshold':0.1,'limit':3}).json()
    target=links['results']['tfidf']['results'][0]
    client.post('/api/reviews',json={'source_id':'A08','target_id':target['id'],'decision':'not_useful','note':'Editorial judgement only'})
    monkeypatch.setattr(client.app.state.engine,'load',lambda:pytest.fail('No PDF inference'))
    for section in ['search','links','overlaps']:
        response=export(client,section); text=text_of(response.content)
        assert '21 articles in collection' in text
        assert 'passage_start' not in text and 'offsets' not in text and 'source_id=' not in text
        assert 'Requested' in text and 'Page 1' in text
        assert bool('Private coffee station query' in text)==(section=='search')
        assert bool('Editorial judgement only' in text)==(section=='links')
        assert bool('Article A' in text)==(section=='overlaps')
        if section=='search': score=search['results']['tfidf'][0]['score']
        elif section=='links':
            score=target['score'];assert 'Not useful' in text
        else:
            score=overlap['pairs'][0]['score'];assert 'does not prove duplication' in text
        assert f'{score:.5f}' in text
        assert any(p.get('/Annots') for p in PdfReader(BytesIO(response.content)).pages)


def test_stale_results_rejected(client):
    client.post('/api/search',json={'query':'oldquery','method':'tfidf'})
    a=client.get('/api/articles').json()['articles'][0];a['title']='Changed'
    client.put('/api/articles/'+a['id'],json=a)
    assert client.post('/api/reports/search/pdf',json={}).status_code==409


def test_latest_successful_settings(client):
    client.post('/api/search',json={'query':'firstquery','method':'tfidf'})
    client.post('/api/search',json={'query':'lastquery','method':'tfidf','top_k':2})
    assert client.post('/api/search',json={'query':'x'}).status_code==422
    text=text_of(export(client,'search').content)
    assert 'lastquery' in text and 'firstquery' not in text and 'per method: 2' in text


def test_isolation_revision_and_auth(tmp_path,engine):
    app=create_app(Settings(database_path=tmp_path/'local.sqlite3',workspace_mode='visitor',visitor_root=tmp_path/'visitors',secret='test-secret'*8,password=''),engine)
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as a,TestClient(app,headers={'X-Workspace-Request':'true'}) as b:
        a.get('/api/session');b.get('/api/session')
        ar=a.get('/api/articles').json()['collection_revision'];br=b.get('/api/articles').json()['collection_revision']
        a.post('/api/search',headers={'If-Match':ar},json={'query':'Only Alice','method':'tfidf'})
        assert 'Only Alice' in text_of(export(a,'search',{'If-Match':ar}).content)
        assert b.post('/api/reports/search/pdf',headers={'If-Match':br},json={}).status_code==409
        assert a.post('/api/reports/search/pdf',json={}).status_code==428
        assert a.post('/api/reports/search/pdf',headers={'If-Match':br},json={}).status_code==409
        b.cookies.clear();assert b.post('/api/reports/search/pdf',headers={'If-Match':ar},json={}).status_code==401
    assert not (tmp_path/'local.sqlite3').exists()


def test_password_and_workspace_header(tmp_path,engine,client):
    app=create_app(Settings(database_path=tmp_path/'private.sqlite3',password='private',secret='test-secret'*8),engine)
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as c:
        assert c.post('/api/reports/links/pdf',json={}).status_code==401
    assert client.post('/api/reports/search/pdf',json={},headers={'X-Workspace-Request':''}).status_code==403


def sample():
    a=Article(id='private_internal_id',title='Café crème –  '+('Long title '*15),body='Original supporting text. '*100,url='https://example.com/'+('long-url-'*180))
    row={'id':a.id,'title':a.title,'url':a.url,'score':0.54321,'passage':a.body}
    return a,row


def test_limits_unicode_url_annotations_and_no_split_cards():
    a,row=sample()
    snapshot={'parameters':{'query':'<b>literal query</b>','method':'tfidf','top_k':20},'payload':{'results':{'tfidf':[row]*20}}}
    data=build_report([a],'search',snapshot,[])
    reader=PdfReader(BytesIO(data));text=text_of(data)
    assert 'Café crème' in text and '<b>literal query</b>' in text
    assert a.id not in text and 'shortened' in text
    assert 'Showing 10 of 20' in text and 'Report truncated' in text
    assert text.count('Cosine similarity: 0.54321')==10
    for page in reader.pages:
        txt=page.extract_text()
        if 'Matching article' in txt: assert 'Cosine similarity:' in txt
    urls=[annot.get_object().get('/A',{}).get('/URI') for page in reader.pages for annot in page.get('/Annots',[])]
    assert a.url in urls and len(data)<2_000_000


def test_completed_empty_report():
    snapshot={'parameters':{'query':'empty','method':'tfidf'},'payload':{'results':{'tfidf':[]}}}
    text=text_of(build_report([],'search',snapshot,[]))
    assert 'No results returned' in text and '0 articles in collection' in text


def test_cancellation_and_output_size(monkeypatch):
    snap={'parameters':{'query':'empty','method':'tfidf'},'payload':{'results':{'tfidf':[]}}}
    with pytest.raises(RuntimeError,match='cancelled'):
        build_report([],'search',snap,[],lambda:(_ for _ in ()).throw(RuntimeError('cancelled')))
    monkeypatch.setattr('semantic_analyser.pdf_report.MAX_BYTES',10)
    with pytest.raises(ValueError,match='2 MB'):build_report([],'search',snap,[])

def test_long_link_cards_keep_evidence_and_editorial_status_together():
    source,row=sample()
    target=source.model_copy(update={'id':'destination'})
    result={**row,'id':target.id,'source_passage':source.body}
    snap={'parameters':{'source_id':source.id,'method':'tfidf','top_k':5},'payload':{'results':{'tfidf':{'results':[result]*5}}}}
    data=build_report([source,target],'links',snap,[{'source_id':source.id,'target_id':target.id,'decision':'useful','note':'Original editorial note '*40}])
    reader=PdfReader(BytesIO(data))
    for page in reader.pages:
        text=page.extract_text()
        scores=text.count('Cosine similarity:')
        if scores:
            assert text.count('Editorial status: Useful')==scores
            assert text.count('Suggested destination')>=scores
    assert 'shortened' in text_of(data)
