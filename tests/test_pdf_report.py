from io import BytesIO
from dataclasses import replace
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader
from semantic_analyser.api import create_app
from semantic_analyser.config import Settings
from semantic_analyser.pdf_report import build_report
from semantic_analyser.schemas import Article


def pdf_text(response):
    assert response.status_code == 200, response.text[:200] if response.status_code != 200 else ''
    assert response.headers['content-type'] == 'application/pdf'
    assert 'attachment;' in response.headers['content-disposition']
    assert response.headers['cache-control'] == 'no-store'
    return '\n'.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)


def test_empty_report_without_inference(client, monkeypatch):
    monkeypatch.setattr(client.app.state.engine, 'load', lambda: pytest.fail('PDF must not load a model'))
    text = pdf_text(client.post('/api/reports/pdf', json={}))
    assert 'Articles in this collection: 21' in text
    assert text.count('Unavailable: analysis not run') == 3
    assert 'accuracy' in text and 'Page 1' in text


def test_completed_report_exact_scores_and_current_reviews(client):
    search = client.post('/api/search', json={'query':'coffee station', 'method':'tfidf'}).json()
    links = client.post('/api/links', json={'source_id':'A08','method':'tfidf'}).json()
    client.post('/api/overlaps', json={'method':'tfidf','threshold':0.1,'limit':3})
    target = links['results']['tfidf']['results'][0]['id']
    client.post('/api/reviews',json={'source_id':'A08','target_id':target,'decision':'useful','note':'Reviewed by editor'})
    text = pdf_text(client.post('/api/reports/pdf',json={}))
    assert 'coffee station' in text and 'Query-dependent' in text
    assert f"{search['results']['tfidf'][0]['score']:.5f}" in text
    assert 'Reviewed by editor' in text and 'Saved editorial status: useful' in text
    assert 'Potential overlap only' in text
    reader = PdfReader(BytesIO(client.post('/api/reports/pdf',json={}).content))
    assert any(p.get('/Annots') for p in reader.pages)


def test_changed_collection_excludes_stale_analysis(client):
    client.post('/api/search',json={'query':'secretquery','method':'tfidf'})
    article = client.get('/api/articles').json()['articles'][0]
    article['title']='Updated title'
    assert client.put('/api/articles/'+article['id'],json=article).status_code == 200
    text = pdf_text(client.post('/api/reports/pdf',json={}))
    assert 'secretquery' not in text and text.count('Unavailable: analysis not run') == 3


def test_visitor_isolation_revision_and_headers(tmp_path,engine):
    app=create_app(Settings(database_path=tmp_path/'local.sqlite3',workspace_mode='visitor',visitor_root=tmp_path/'visitors',secret='test-secret'*8,password='',production=False),engine)
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as a, TestClient(app,headers={'X-Workspace-Request':'true'}) as b:
        a.get('/api/session'); b.get('/api/session')
        ar=a.get('/api/articles').json()['collection_revision']; br=b.get('/api/articles').json()['collection_revision']
        assert a.post('/api/search',headers={'If-Match':ar},json={'query':'Alice private query','method':'tfidf'}).status_code == 200
        assert 'Alice private query' in pdf_text(a.post('/api/reports/pdf',headers={'If-Match':ar},json={}))
        assert 'Alice private query' not in pdf_text(b.post('/api/reports/pdf',headers={'If-Match':br},json={}))
        assert a.post('/api/reports/pdf',json={}).status_code == 428
        assert a.post('/api/reports/pdf',headers={'If-Match':br},json={}).status_code == 409
        b.cookies.clear()
        assert b.post('/api/reports/pdf',headers={'If-Match':ar},json={}).status_code == 401
    assert not (tmp_path/'local.sqlite3').exists()


def test_authentication_required(tmp_path,engine):
    app=create_app(Settings(database_path=tmp_path/'test.sqlite3',password='private',secret='test-only'*8),engine)
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as c:
        assert c.post('/api/reports/pdf',json={}).status_code == 401


def test_long_wrapped_text_and_limits(tmp_path):
    article=Article(id='long',title='Long cafe title ' * 12,body='Original evidence '*500,url='https://example.com/'+('long-path-'*180))
    row={'id':article.id,'title':article.title,'url':article.url,'score':0.54321,'passage':article.body,'passage_start':0,'passage_end':len(article.body)}
    snapshot={'search':{'parameters':{'query':'<b>untrusted</b>','method':'tfidf'},'payload':{'results':{'tfidf':[row]*20}}}}
    data=build_report([article],snapshot,[])
    text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(data)).pages)
    assert 'showing 10 of 20' in text and 'Report truncated' in text
    assert text.count('Cosine similarity: 0.54321') == 10
    assert 'Excerpt shortened' in text and '<b>untrusted</b>' in text
    assert len(data)<2_000_000
    (tmp_path/'long-report.pdf').write_bytes(data)


def test_empty_completed_results():
    data=build_report([],{'search':{'parameters':{'query':'empty','method':'tfidf'},'payload':{'results':{'tfidf':[]}}}},[])
    text=''.join(p.extract_text() for p in PdfReader(BytesIO(data)).pages)
    assert 'No results returned' in text and 'Articles in this collection: 0' in text


def test_render_cancellation():
    with pytest.raises(RuntimeError,match='cancelled'):
        build_report([],{},[],lambda: (_ for _ in ()).throw(RuntimeError('cancelled')))


def test_output_limit(monkeypatch):
    monkeypatch.setattr('semantic_analyser.pdf_report.MAX_BYTES',10)
    with pytest.raises(ValueError,match='2 MB'):
        build_report([],{},[])

def test_latest_successful_run_and_no_export_inference(client, monkeypatch):
    client.post('/api/search', json={'query':'firstquery','method':'tfidf'})
    client.post('/api/search', json={'query':'latestquery','method':'tfidf'})
    assert client.post('/api/search', json={'query':'x','method':'tfidf'}).status_code == 422
    monkeypatch.setattr(client.app.state.engine, 'load', lambda: pytest.fail('Export triggered inference'))
    text=pdf_text(client.post('/api/reports/pdf',json={}))
    assert 'latestquery' in text and 'firstquery' not in text
    assert client.post('/api/reports/pdf',json={},headers={'X-Workspace-Request':''}).status_code == 403
