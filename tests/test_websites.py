import json
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from semantic_analyser.api import create_app
from semantic_analyser.execution import Deadline
from semantic_analyser.extraction import Document, extract, site_url, sitemap
from semantic_analyser.fetch_policy import FetchError, FetchLimits
from semantic_analyser.safe_fetch import SafeFetcher
from semantic_analyser.websites import WebsiteService
from test_safe_fetch import FakeDNS, FakeTransport
from test_visitor_workspaces import headers, start, visitor_settings
from website_fixtures import BASE, article, routes


def service(method='wordpress', count=40):
    transport = FakeTransport(routes(method, count))
    fetcher = SafeFetcher(FetchLimits(delay_seconds=0), FakeDNS(), transport)
    return WebsiteService(fetcher), transport


def discover(service, url=BASE, method='auto'):
    run = service.start('owner', 'revision', url, method)
    while run.phase == 'discovering':
        service.step(run, Deadline(10))
    return run


def prepare(service, run, count=40):
    service.select(run, list(run.candidates)[:count])
    while run.phase == 'extracting':
        service.step(run, Deadline(10))
    return run


@pytest.mark.parametrize('method', ['wordpress', 'sitemap'])
def test_forty_article_workflow_and_links(method):
    svc, transport = service(method)
    run = prepare(svc, discover(svc))
    assert run.phase == 'ready' and len(run.articles) == 40
    assert run.session.requests <= 60 and run.view()['processed'] == 40
    assert all('POISON' not in a.body and 'window.evil' not in a.body for a in run.articles)
    assert all(a.existing_links for a in run.articles)
    assert all('https://public.example' in url for url, _, _ in transport.calls)


def test_extraction_title_headings_canonical_and_inert_markup():
    with pytest.raises(ValueError, match='HTML'):
        Document(b'<![bogus[malformed]]>')
    data = extract(article(1), BASE + '/posts/1')
    assert data['title'] == 'Equipment guide 1' and data['headings'][1] == 'Planning equipment 1'
    assert data['url'] == BASE + '/posts/1' and BASE + '/posts/2' in data['links']
    assert BASE + '/posts/3' not in data['links']
    hostile = article(1).replace(b'href="/posts/1"', b'href="http://169.254.169.254/"')
    assert extract(hostile, BASE + '/posts/1')['url'] == BASE + '/posts/1'
    assert site_url('/posts/1?utm_source=x#part', BASE) == BASE + '/posts/1'


@pytest.mark.parametrize('payload', [b'<html><p>Not a main region</p></html>', b'<article><p>short</p></article>', b'<article>' + b'a' * 20001 + b'</article>', b'<main>' * 99, b'<main>\xff</main>', b'<meta itemprop="isAccessibleForFree" content="false"><article>text</article>'])
def test_unsupported_or_restricted_html_rejected(payload):
    with pytest.raises(ValueError):
        extract(payload, BASE)


@pytest.mark.parametrize('payload', [b'<!DOCTYPE urlset [<!ENTITY x "boom">]><urlset>&x;</urlset>',
    '<!DOCTYPE urlset SYSTEM "file:///secret"><urlset/>'.encode('utf-16'), b'<urlset><url>', b'<rss/>',
    ('<urlset>' + '<x>' * 40 + '</x>' * 40 + '</urlset>').encode()])
def test_sitemap_dtd_entities_malformed_and_depth_rejected(payload):
    with pytest.raises(ValueError):
        sitemap(payload)


def test_nested_sitemap_duplicates_cycles_and_offsite_links():
    svc, transport = service('sitemap', 3)
    transport.routes['/blog-map.xml'] = (200, f'<sitemapindex><sitemap><loc>{BASE}/sitemap.xml</loc></sitemap><sitemap><loc>{BASE}/last.xml</loc></sitemap><sitemap><loc>http://127.0.0.1/private.xml</loc></sitemap></sitemapindex>'.encode(), {'content-type': 'application/xml'})
    transport.routes['/last.xml'] = (200, f'<urlset><url><loc>{BASE}/posts/1</loc></url><url><loc>{BASE}/posts/1?utm_source=x</loc></url><url><loc>https://evil.example/private</loc></url></urlset>'.encode(), {'content-type': 'application/xml'})
    run = discover(svc)
    assert len(run.candidates) == 1 and run.discovery_count <= 8
    assert not any('evil.example' in u or '127.0.0.1' in u for u, _, _ in transport.calls)


def test_wp_repeated_pages_and_protected_posts_are_bounded():
    svc, transport = service('wordpress', 40)
    first = '/wp-json/wp/v2/posts?per_page=20&page=1&_fields=id,link,title,content.protected'
    second = first.replace('page=1&', 'page=2&')
    rows = json.loads(transport.routes[first][1])
    rows[0]['content']['protected'] = True
    transport.routes[first] = (200, json.dumps(rows).encode(), {'content-type': 'application/json', 'x-wp-totalpages': '999'})
    transport.routes[second] = transport.routes[first]
    run = discover(svc)
    assert len(run.candidates) == 19 and run.discovery_count == 3


def test_discovery_and_selection_caps_and_run_lifetime():
    svc, transport = service('sitemap', 1)
    transport.routes['/sitemap.xml'] = (200, ('<urlset>' + ''.join(f'<url><loc>{BASE}/posts/{i}</loc></url>' for i in range(500)) + '</urlset>').encode(), {'content-type': 'application/xml'})
    run = discover(svc)
    assert len(run.candidates) == 200
    for ids in [[], list(run.candidates)[:41], [next(iter(run.candidates))] * 2, ['unknown']]:
        with pytest.raises(ValueError):
            svc.select(run, ids)
    svc.select(run, list(run.candidates)[:1])
    run.session.started -= 181
    with pytest.raises(FetchError):
        svc.step(run, Deadline(10))


@pytest.mark.parametrize('status', [401, 403, 429, 503])
def test_discovery_never_falls_back_around_access_denial(status):
    svc, transport = service('sitemap', 1)
    transport.routes['/wp-json/wp/v2/posts?per_page=20&page=1&_fields=id,link,title,content.protected'] = (status, b'', {})
    with pytest.raises(FetchError):
        discover(svc)
    assert not any('/sitemap.xml' in u for u, _, _ in transport.calls)


@pytest.fixture
def website_api(visitor_settings, engine):
    svc, transport = service()
    app = create_app(replace(visitor_settings, website_fetch_enabled=True), engine, svc.fetcher)
    with TestClient(app, headers={'X-Workspace-Request': 'true'}) as client:
        yield app, client, transport


def post(client, token, rev, path, data, status=200):
    response = client.post('/api/website/' + path, headers=headers(token, rev), json=data)
    assert response.status_code == status, response.text
    return response.json()


def api_ready(client, token, rev, count=3):
    result = post(client, token, rev, 'start', {'url': BASE})
    action = {'run_id': result['run_id']}
    while result['phase'] == 'discovering':
        result = post(client, token, rev, 'step', action)
    post(client, token, rev, 'select', {**action, 'ids': [c['id'] for c in result['candidates'][:count]]})
    for _ in range(count):
        result = post(client, token, rev, 'step', action)
    return action, result


def test_api_owned_runs_cross_session_and_stale_revision(website_api):
    app, client, transport = website_api
    a, ar = start(client)
    b, br = start(client)
    action, result = api_ready(client, a, ar)
    for endpoint in ['step', 'cancel', 'import']:
        post(client, b, br, endpoint, action, 404)
    post(client, b, br, 'select', {**action, 'ids': [result['candidates'][0]['id']]}, 404)
    assert len(client.get('/api/articles', headers=headers(b)).json()['articles']) == 21
    reset = client.post('/api/articles/reset', headers=headers(a, ar), json={}).json()
    post(client, a, reset['collection_revision'], 'import', action, 409)


def test_atomic_website_import_and_model_admission_failure(website_api):
    app, client, transport = website_api
    token, rev = start(client)
    client.post('/api/reviews', headers=headers(token, rev), json={'source_id': 'A01', 'target_id': 'A02', 'decision': 'useful'})
    before = client.get('/api/articles', headers=headers(token)).json()
    action, result = api_ready(client, token, rev)
    entry = next(iter(app.state.workspaces.entries.values()))
    original = entry.engine.preflight
    entry.engine.preflight = lambda articles: (_ for _ in ()).throw(ValueError('The collection exceeds 800 passages.'))
    post(client, token, rev, 'import', action, 422)
    assert client.get('/api/articles', headers=headers(token)).json() == before
    assert len(client.get('/api/reviews', headers=headers(token)).json()['reviews']) == 1
    entry.engine.preflight = original
    imported = post(client, token, rev, 'import', action)
    assert imported['count'] == 3 and imported['collection_revision'] != rev
    assert client.get('/api/reviews', headers=headers(token)).json()['reviews'] == []
    search = client.post('/api/search', headers=headers(token, imported['collection_revision']), json={'query': 'counter equipment', 'method': 'compare'})
    assert search.status_code == 200 and set(search.json()['results']) == {'embeddings', 'tfidf'}


def test_extraction_failure_requires_explicit_partial_acceptance(website_api):
    app, client, transport = website_api
    token, rev = start(client)
    transport.routes['/posts/1'] = (200, b'<article><h1>Short</h1><p>too short</p></article>', {'content-type': 'text/html'})
    action, result = api_ready(client, token, rev)
    assert result['phase'] == 'ready' and len(result['failures']) == 1 and len(result['articles']) == 2
    post(client, token, rev, 'import', action, 422)
    assert post(client, token, rev, 'import', {**action, 'accept_partial': True})['count'] == 2


def test_expired_cancelled_and_replaced_runs_cannot_commit(website_api):
    app, client, transport = website_api
    token, rev = start(client)
    action, result = api_ready(client, token, rev)
    post(client, token, rev, 'cancel', action)
    post(client, token, rev, 'import', action, 409)
    entry = next(iter(app.state.workspaces.entries.values()))
    entry.website_run.session.started -= 181
    post(client, token, rev, 'import', action, 410)


def test_canonical_deduplication_and_repeated_template_removal():
    svc, transport = service('sitemap', 4)
    for i in range(1, 5):
        body = article(i).replace(b'</article>', b'<p>Repeated newsletter subscription template text.</p></article>')
        if i == 4:
            body = body.replace(b'href="/posts/4"', b'href="/posts/3"')
        transport.routes[f'/posts/{i}'] = (200, body, {'content-type': 'text/html'})
    run = prepare(svc, discover(svc), 4)
    assert len(run.articles) == 3
    assert all('newsletter subscription' not in a.body for a in run.articles)
    assert any('collapsed' in message for message in run.warnings)


def test_robots_advertised_sitemap_and_subdirectory_wp_api():
    svc, transport = service('sitemap', 2)
    transport.routes['/robots.txt'] = (200, f'User-agent: *\nAllow: /\nSitemap: {BASE}/blog-map.xml'.encode(), {'content-type': 'text/plain'})
    assert len(discover(svc).candidates) == 2
    svc, transport = service('wordpress', 2)
    transport.routes['/'] = (200, b'<link rel="https://api.w.org/" href="/blog/wp-json/">', {'content-type': 'text/html'})
    key = '/wp-json/wp/v2/posts?per_page=20&page=1&_fields=id,link,title,content.protected'
    transport.routes['/blog' + key] = transport.routes.pop(key)
    assert len(discover(svc).candidates) == 2


def test_xml_index_depth_and_discovery_request_cap():
    # Entity-fragmented character callbacks remain bounded and counted linearly.
    assert len(sitemap(b'<urlset><url><loc>https://public.example/' + b'&amp;' * 2000 + b'</loc></url></urlset>')[1]) == 1
    with pytest.raises(ValueError, match='2,048'):
        sitemap(b'<urlset><url><loc>https://public.example/' + b'&amp;' * 2048 + b'</loc></url></urlset>')
    svc, transport = service('sitemap', 1)
    for i in range(15):
        name = '/sitemap.xml' if i == 0 else f'/map-{i}.xml'
        transport.routes[name] = (200, f'<sitemapindex><sitemap><loc>{BASE}/map-{i + 1}.xml</loc></sitemap></sitemapindex>'.encode(), {'content-type': 'application/xml'})
    run = discover(svc, BASE + '/sitemap.xml')
    assert not run.candidates and run.discovery_count == 4
    svc, transport = service('sitemap', 1)
    transport.routes['/sitemap.xml'] = (200, ('<sitemapindex>' + ''.join(f'<sitemap><loc>{BASE}/map-{i}.xml</loc></sitemap>' for i in range(30)) + '</sitemapindex>').encode(), {'content-type': 'application/xml'})
    run = discover(svc, BASE + '/sitemap.xml')
    assert run.discovery_count <= 12 and run.session.requests <= 13


def test_character_limits_and_no_silent_article_truncation():
    svc, transport = service('sitemap', 15)
    for i in range(1, 16):
        transport.routes[f'/posts/{i}'] = (200, article(i, ('Substantial paragraph about planning safe useful equipment for staff. ' * 260)), {'content-type': 'text/html'})
    run = prepare(svc, discover(svc), 15)
    assert run.failures and sum(len(a.title) + len(a.body) for a in run.articles) <= 250000


def test_cancelled_control_and_failed_commit_preserve_data(website_api):
    app, client, transport = website_api
    token, rev = start(client)
    action, result = api_ready(client, token, rev)
    entry = next(iter(app.state.workspaces.entries.values()))
    before = entry.store.export()
    control = Deadline(10)
    control.cancelled.set()
    with pytest.raises(Exception) as error:
        entry.collections.replace(entry.website_run.articles, control.check)
    assert getattr(error.value, 'status_code', None) == 504
    assert entry.store.export() == before and entry.store.revision() == rev


def test_new_run_replaces_only_own_transient_state(website_api):
    app, client, transport = website_api
    a, ar = start(client)
    b, br = start(client)
    action, result = api_ready(client, a, ar)
    post(client, a, ar, 'start', {'url': BASE}, 429)
    entry = next(e for e in app.state.workspaces.entries.values() if e.website_run)
    entry.website_run.session.started -= 6
    replacement = post(client, a, ar, 'start', {'url': BASE})
    assert replacement['run_id'] != action['run_id']
    post(client, a, ar, 'import', action, 404)
    assert client.get('/api/articles', headers=headers(b)).json()['collection_revision'] == br


def test_run_expiry_during_model_admission_rolls_back(website_api):
    app, client, transport = website_api
    token, rev = start(client)
    action, _ = api_ready(client, token, rev)
    entry = next(iter(app.state.workspaces.entries.values()))
    original = entry.engine.preflight
    def expire(articles):
        summary = original(articles)
        entry.website_run.session.started -= 181
        return summary
    entry.engine.preflight = expire
    before = entry.store.export()
    post(client, token, rev, 'import', action, 410)
    assert entry.store.export() == before and entry.store.revision() == rev


@pytest.mark.parametrize('marker', [b'<script type="application/ld+json">{"isAccessibleForFree":false}</script>', b'<div class="paywall">Subscribers only</div>'])
def test_explicit_paywall_signals_rejected(marker):
    with pytest.raises(ValueError, match='restriction'):
        extract(article(1).replace(b'</body>', marker + b'</body>'), BASE)
