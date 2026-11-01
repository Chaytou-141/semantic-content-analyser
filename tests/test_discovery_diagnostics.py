"""Controlled upstream failures; never fetch the reported real website."""
import re
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from semantic_analyser.api import create_app
from semantic_analyser.fetch_policy import FetchError,FetchLimits
from semantic_analyser.safe_fetch import SafeFetcher
from semantic_analyser.websites import WebsiteService
from test_safe_fetch import FakeDNS,FakeTransport
from test_visitor_workspaces import visitor_settings,headers,start
from test_websites import discover
from website_fixtures import BASE,routes

WP='/wp-json/wp/v2/posts?per_page=20&page=1&_fields=id,link,title,content.protected'


@pytest.mark.parametrize('status,phrase',[(401,'authentication'),(403,'denied'),(404,'not found'),
    (410,'no longer'),(429,'pause'),(500,'does not by itself'),(503,'temporarily unavailable')])
def test_http_status_messages_do_not_guess_authentication(status,phrase):
    wire=FakeTransport({'/robots.txt':(404,b'',{}),'/endpoint':(status,b'private upstream body',{})})
    fetch=SafeFetcher(FetchLimits(delay_seconds=0),FakeDNS(),wire)
    with pytest.raises(FetchError) as error:fetch.fetch(fetch.new_session('owner'),BASE+'/endpoint','owner')
    assert error.value.upstream_status==status and error.value.fetch_resource=='content'
    assert phrase in error.value.message and str(status) in error.value.message
    assert error.value.code==('backoff' if status==429 else 'inaccessible')


def wix_like_routes():
    data=routes('sitemap',3)
    data['/robots.txt']=(200,f'User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml'.encode(),{'content-type':'text/plain'})
    data['/sitemap.xml']=(200,f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>{BASE}/blog-posts-sitemap.xml</loc></sitemap></sitemapindex>'.encode(),{'content-type':'application/xml'})
    data['/blog-posts-sitemap.xml']=data.pop('/blog-map.xml')
    return data


def test_wix_shaped_standard_index_and_blog_map_work_without_wordpress():
    wire=FakeTransport(wix_like_routes());svc=WebsiteService(SafeFetcher(FetchLimits(delay_seconds=0),FakeDNS(),wire))
    assert len(discover(svc,BASE,'sitemap').candidates)==3
    assert not any('wp-json' in url for url,_,_ in wire.calls)


def test_same_auto_configuration_can_succeed_then_fail_if_upstream_changes(caplog):
    wire=FakeTransport(wix_like_routes());svc=WebsiteService(SafeFetcher(FetchLimits(delay_seconds=0),FakeDNS(),wire))
    first=discover(svc);assert len(first.candidates)==3  # REST 404 permits existing fallback.
    wire.routes[WP]=(403,b'Do not expose: 10.0.0.1 token=secret',{})
    before=len(wire.calls)
    with pytest.raises(FetchError) as error:discover(svc)
    assert error.value.discovery_stage=='WordPress discovery' and error.value.upstream_status==403
    assert len(wire.calls)-before==3  # Fresh robots policy, homepage, then REST probe.


def test_api_diagnostics_are_safe_and_auth_failures_do_not_fallback(visitor_settings,engine,caplog):
    data=wix_like_routes();data[WP]=(403,b'secret internal upstream response',{})
    wire=FakeTransport(data);fetch=SafeFetcher(FetchLimits(delay_seconds=0),FakeDNS(),wire)
    app=create_app(replace(visitor_settings,website_fetch_enabled=True),engine,fetch)
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as client:
        token,rev=start(client)
        run=client.post('/api/website/start',headers=headers(token,rev),json={'url':BASE}).json()
        client.post('/api/website/step',headers=headers(token,rev),json={'run_id':run['run_id']})
        response=client.post('/api/website/step',headers=headers(token,rev),json={'run_id':run['run_id']})
        assert response.status_code==502
        body=response.json();assert body['source_http_status']==403 and body['discovery_stage']=='WordPress discovery'
        assert body['fetch_resource']=='content' and re.fullmatch('[a-f0-9]{12}',body['diagnostic_reference'])
        assert body['diagnostic_reference'] in caplog.text
        assert all(secret not in response.text+caplog.text for secret in ['8.8.8.8','secret internal',WP,BASE])
        assert not any('sitemap' in url for url,_,_ in wire.calls)


def test_robots_timeout_network_and_run_budget_remain_distinct():
    cases=[({'/robots.txt':(200,b'User-agent: *\nDisallow: /',{})},'robots'),
           ({'/robots.txt':(503,b'',{})},'robots_unavailable')]
    for data,code in cases:
        f=SafeFetcher(FetchLimits(delay_seconds=0),FakeDNS(),FakeTransport(data))
        with pytest.raises(FetchError) as error:f.fetch(f.new_session('a'),BASE,'a')
        assert error.value.code==code and error.value.fetch_resource=='robots'
    for code in ['timeout','network']:
        class Broken(FakeTransport):
            def get(self,*args):raise FetchError(code)
        f=SafeFetcher(FetchLimits(delay_seconds=0),FakeDNS(),Broken())
        with pytest.raises(FetchError) as error:f.fetch(f.new_session('a'),BASE,'a')
        assert error.value.code==code and not hasattr(error.value,'upstream_status')
    f=SafeFetcher(FetchLimits(delay_seconds=0),FakeDNS(),FakeTransport());s=f.new_session('a');s.requests=60
    with pytest.raises(FetchError) as error:f.fetch(s,BASE,'a')
    assert error.value.code=='limit' and not hasattr(error.value,'upstream_status')
