"""Original synthetic standard-sitemap fixtures; only controlled DNS/transport."""
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from semantic_analyser.api import create_app
from semantic_analyser.execution import Deadline
from semantic_analyser.extraction import homepage_metadata, sitemap
from semantic_analyser.fetch_policy import FetchError
from test_websites import BASE, discover, prepare, service, post
from test_visitor_workspaces import headers, start, visitor_settings

NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'


@pytest.mark.parametrize('path', ['/maps/articles', '/map.php?type=posts', '/?sitemap=posts'])
def test_explicit_sitemap_endpoint_is_preserved_without_xml_suffix(path):
    svc, transport = service('sitemap', 3)
    transport.routes[path] = transport.routes['/blog-map.xml']
    run = discover(svc, BASE+path, 'sitemap')
    assert len(run.candidates) == 3
    assert [url for url, _, _ in transport.calls] == [BASE+'/robots.txt', BASE+path]


def test_sitemap_mode_root_uses_robots_index_without_wordpress_probe():
    svc, transport = service('sitemap', 40)
    transport.routes['/robots.txt'] = (200, f'User-agent: *\nAllow: /\nSitemap: {BASE}/maps/index'.encode(), {'content-type':'text/plain'})
    transport.routes['/maps/index'] = transport.routes.pop('/sitemap.xml')
    run = prepare(svc, discover(svc, BASE, 'sitemap'))
    assert len(run.articles) == 40 and run.phase == 'ready'
    assert run.session.requests == 44  # robots, home, index, URL set, 40 articles
    assert not any('wp-json' in url or '/sitemap.xml' in url for url, _, _ in transport.calls)


def test_sitemap_mode_honours_homepage_metadata_without_rest():
    svc, transport = service('sitemap', 3)
    transport.routes['/'] = (200, b'<link rel="sitemap" href="/blog-map.xml">', {'content-type':'text/html'})
    assert len(discover(svc, BASE, 'sitemap').candidates) == 3
    assert [url for url, _, _ in transport.calls] == [BASE+'/robots.txt', BASE+'/', BASE+'/blog-map.xml']


def test_standard_namespace_extensions_are_not_article_locations():
    body = f'''<?xml version="1.0"?><sm:urlset xmlns:sm="{NS}"
      xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"
      xmlns:xhtml="http://www.w3.org/1999/xhtml">
      <sm:url><sm:loc>{BASE}/posts/1?a=1&amp;b=2</sm:loc>
      <image:loc>{BASE}/image.jpg</image:loc>
      <xhtml:link rel="alternate" href="https://elsewhere.example/post"/></sm:url></sm:urlset>'''.encode()
    assert sitemap(body) == ('urlset', [BASE+'/posts/1?a=1&b=2'])


@pytest.mark.parametrize('encoding', ['utf-8', 'utf-16'])
def test_standard_xml_encoding_stylesheet_and_foreign_entries(encoding):
    body = (f'<?xml version="1.0" encoding="{encoding}"?>'
            f'<?xml-stylesheet type="text/xsl" href="http://127.0.0.1/private.xsl"?>'
            f'<urlset xmlns="{NS}" xmlns:other="urn:other">'
            f'<other:url><loc>{BASE}/not-a-page</loc></other:url>'
            f'<url><other:loc>{BASE}/also-not-a-page</other:loc><loc>{BASE}/posts/1</loc></url></urlset>').encode(encoding)
    assert sitemap(body) == ('urlset', [BASE+'/posts/1'])


def test_empty_locations_and_foreign_loc_limits_do_not_create_homepage_candidate():
    body = (f'<urlset xmlns="{NS}" xmlns:image="urn:image"><url><loc> </loc></url>'
            f'<url><loc>{BASE}/posts/1</loc><image:loc>'+ 'x'*2100 + '</image:loc></url></urlset>').encode()
    assert sitemap(body) == ('urlset', [BASE+'/posts/1'])
    svc, transport = service('sitemap', 1)
    transport.routes['/sitemap.xml'] = (200, b'<urlset><url><loc/></url></urlset>', {'content-type':'application/xml'})
    assert not discover(svc, BASE+'/sitemap.xml', 'sitemap').candidates


@pytest.mark.parametrize('body', [b'<urlset xmlns="urn:unrelated"/>',
    b'<urlset><url><loc>https://public.example/<b>post</b></loc></url></urlset>'])
def test_wrong_namespace_or_markup_inside_primary_loc_is_rejected(body):
    with pytest.raises(ValueError): sitemap(body)


def test_missing_metadata_href_does_not_advertise_the_homepage():
    assert homepage_metadata(b'<link rel="sitemap"><link rel="https://api.w.org/">', BASE) == (None, [])


def test_depth_truncation_is_visible_and_bounded():
    svc, transport = service('sitemap', 1)
    for i in range(5):
        path = '/sitemap.xml' if i==0 else f'/map-{i}.xml'
        transport.routes[path] = (200, f'<sitemapindex><sitemap><loc>{BASE}/map-{i+1}.xml</loc></sitemap></sitemapindex>'.encode(), {'content-type':'application/xml'})
    run = discover(svc, BASE+'/sitemap.xml', 'sitemap')
    assert run.discovery_count == 4 and run.session.requests == 5
    assert any('bounded' in warning for warning in run.warnings)


def test_candidate_cap_warns_even_without_pending_documents():
    svc, transport = service('sitemap', 1)
    body = ('<urlset>' + ''.join(f'<url><loc>{BASE}/posts/{i}</loc></url>' for i in range(201)) + '</urlset>').encode()
    transport.routes['/sitemap.xml'] = (200,body,{'content-type':'application/xml'})
    run = discover(svc,BASE+'/sitemap.xml','sitemap')
    assert len(run.candidates)==200 and any('200-location' in w for w in run.warnings)


@pytest.mark.parametrize('status', [401,403,429,503])
def test_sitemap_root_access_denial_does_not_trigger_other_endpoints(status):
    svc, transport = service('sitemap',1)
    transport.routes['/'] = (status,b'',{})
    with pytest.raises(FetchError):discover(svc,BASE,'sitemap')
    assert [url for url,_,_ in transport.calls]==[BASE+'/robots.txt',BASE+'/']


def test_xml_sitemap_api_import_is_atomic_and_owned(visitor_settings, engine):
    svc, transport = service('sitemap', 4)
    app = create_app(replace(visitor_settings, website_fetch_enabled=True), engine, svc.fetcher)
    with TestClient(app, headers={'X-Workspace-Request':'true'}) as client:
        a, ar = start(client); b, br = start(client)
        result = post(client, a, ar, 'start', {'url':BASE, 'method':'sitemap'})
        action = {'run_id':result['run_id']}
        while result['phase']=='discovering': result=post(client, a, ar, 'step', action)
        post(client, b, br, 'select', {**action,'ids':[result['candidates'][0]['id']]},404)
        post(client,a,ar,'select',{**action,'ids':[c['id'] for c in result['candidates']]})
        for _ in range(4): result=post(client,a,ar,'step',action)
        before=client.get('/api/articles',headers=headers(a)).json()
        entry=next(e for e in app.state.workspaces.entries.values() if e.website_run)
        preflight=entry.engine.preflight
        entry.engine.preflight=lambda articles: (_ for _ in ()).throw(ValueError('Too many passages.'))
        post(client,a,ar,'import',action,422)
        assert client.get('/api/articles',headers=headers(a)).json()==before
        entry.engine.preflight=preflight
        imported=post(client,a,ar,'import',action)
        assert imported['count']==4 and imported['collection_revision']!=ar
        assert len(client.get('/api/articles',headers=headers(b)).json()['articles'])==21


def test_sitemap_mode_does_not_bypass_robots_or_denial():
    svc, transport = service('sitemap', 2)
    transport.routes['/robots.txt']=(200,b'User-agent: *\nDisallow: /blog-map.xml',{'content-type':'text/plain'})
    with pytest.raises(FetchError) as error: discover(svc,BASE+'/sitemap.xml','sitemap')
    assert error.value.code=='robots'
    assert not any('/blog-map.xml' in url for url,_,_ in transport.calls)
