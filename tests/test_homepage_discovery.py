"""Homepage-first discovery, with mixed sitemap shapes from the saved diagnostic.

All content is synthetic; no public requests or model inference.
"""
import pytest

from semantic_analyser.fetch_policy import FetchError, FetchLimits
from semantic_analyser.safe_fetch import SafeFetcher
from semantic_analyser.websites import WebsiteService, article_sitemap_hint
from test_safe_fetch import FakeDNS, FakeTransport
from test_websites import discover
from website_fixtures import BASE, routes

NS='http://www.sitemaps.org/schemas/sitemap/0.9'


def mixed_routes():
    data=routes('sitemap',14)
    data['/robots.txt']=(200,f'User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml'.encode(),
                         {'content-type':'text/plain','cache-control':'public,max-age=0,must-revalidate'})
    names=['store-products','store-categories','event-pages','blog-posts','blog-categories','pages']
    data['/sitemap.xml']=(200,('<sitemapindex xmlns="'+NS+'">'+''.join(
        f'<sitemap><loc>{BASE}/{name}-sitemap.xml</loc></sitemap>' for name in names)+'</sitemapindex>').encode(),{'content-type':'text/xml'})
    data['/blog-posts-sitemap.xml']=data.pop('/blog-map.xml')
    data['/store-products-sitemap.xml']=(403,b'blocked',{})
    data['/store-categories-sitemap.xml']=(400,b'rejected',{})
    return data


def make_service(data):
    transport=FakeTransport(data)
    return WebsiteService(SafeFetcher(FetchLimits(delay_seconds=0),FakeDNS(),transport)),transport


def test_homepage_auto_finds_blog_without_guessing_wordpress_or_scanning_store():
    svc,wire=make_service(mixed_routes())
    run=discover(svc)
    assert run.phase=='selecting' and len(run.candidates)==14
    assert run.session.requests==6  # no-cache robots + homepage, index, blog map
    assert [u for u,_,_ in wire.calls if not u.endswith('/robots.txt')]==[
        BASE+'/',BASE+'/sitemap.xml',BASE+'/blog-posts-sitemap.xml']
    assert any('not the complete website' in w and 'All sitemap pages' in w for w in run.warnings)


def test_all_sitemap_pages_remains_explicit_and_does_not_bypass_denial():
    svc,wire=make_service(mixed_routes())
    with pytest.raises(FetchError) as caught: discover(svc,BASE,'sitemap')
    assert caught.value.upstream_status==403
    assert wire.calls[-1][0]==BASE+'/store-products-sitemap.xml'
    assert not any('blog-posts' in u for u,_,_ in wire.calls)


@pytest.mark.parametrize('status',[400,401,403,429,503])
def test_selected_blog_map_failure_never_retries_or_moves_to_other_branches(status):
    data=mixed_routes();data['/blog-posts-sitemap.xml']=(status,b'',{})
    svc,wire=make_service(data)
    with pytest.raises(FetchError) as caught:discover(svc)
    assert caught.value.upstream_status==status
    assert wire.calls[-1][0]==BASE+'/blog-posts-sitemap.xml'
    assert not any('store-' in u or 'wp-json' in u for u,_,_ in wire.calls)


def test_blog_robots_denial_is_not_bypassed():
    data=mixed_routes()
    data['/robots.txt']=(200,f'User-agent: *\nDisallow: /blog-posts-sitemap.xml\nSitemap: {BASE}/sitemap.xml'.encode(),{'content-type':'text/plain'})
    svc,wire=make_service(data)
    with pytest.raises(FetchError) as caught:discover(svc)
    assert caught.value.code=='robots'
    assert not any('blog-posts' in u or 'store-' in u for u,_,_ in wire.calls)


def test_advertised_wordpress_remains_preferred_and_denial_is_fatal():
    data=mixed_routes()
    data['/']=(200,b'<link rel="https://api.w.org/" href="/wp-json/">',{'content-type':'text/html'})
    wp='/wp-json/wp/v2/posts?per_page=20&page=1&_fields=id,link,title,content.protected'
    data[wp]=(403,b'',{})
    svc,wire=make_service(data)
    with pytest.raises(FetchError) as caught:discover(svc)
    assert caught.value.upstream_status==403
    assert not any(u.endswith('/sitemap.xml') for u,_,_ in wire.calls)


def test_generic_map_names_remain_discoverable_without_filtering():
    data=routes('sitemap',3)
    data['/robots.txt']=(200,f'User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml'.encode(),{'content-type':'text/plain'})
    data['/sitemap.xml']=(200,f'<sitemapindex><sitemap><loc>{BASE}/content-1.xml</loc></sitemap></sitemapindex>'.encode(),{'content-type':'text/xml'})
    data['/content-1.xml']=data.pop('/blog-map.xml')
    svc,wire=make_service(data)
    run=discover(svc)
    assert len(run.candidates)==3 and not any('focused' in w for w in run.warnings)


def test_multiple_post_maps_are_all_processed():
    data=mixed_routes()
    data['/sitemap.xml']=(200,f'<sitemapindex><sitemap><loc>{BASE}/post-sitemap1.xml</loc></sitemap><sitemap><loc>{BASE}/article-sitemap.xml</loc></sitemap><sitemap><loc>{BASE}/store-products-sitemap.xml</loc></sitemap></sitemapindex>'.encode(),{'content-type':'text/xml'})
    data['/post-sitemap1.xml']=(200,f'<urlset><url><loc>{BASE}/posts/1</loc></url></urlset>'.encode(),{'content-type':'text/xml'})
    data['/article-sitemap.xml']=(200,f'<urlset><url><loc>{BASE}/posts/2</loc></url></urlset>'.encode(),{'content-type':'text/xml'})
    svc,wire=make_service(data)
    assert len(discover(svc).candidates)==2


def test_unsafe_article_hints_cannot_displace_safe_generic_maps():
    data=mixed_routes()
    data['/sitemap.xml']=(200,f'<sitemapindex><sitemap><loc>https://127.0.0.1/posts.xml</loc></sitemap><sitemap><loc>https://other.example/posts.xml</loc></sitemap><sitemap><loc>{BASE}/content.xml</loc></sitemap></sitemapindex>'.encode(),{'content-type':'text/xml'})
    data['/content.xml']=data['/blog-posts-sitemap.xml']
    svc,wire=make_service(data)
    assert len(discover(svc).candidates)==14
    assert all(u.startswith(BASE) for u,_,_ in wire.calls)


@pytest.mark.parametrize('path,expected',[
    ('/blog-posts-sitemap.xml',True),('/post-sitemap1.xml',True),('/wp-sitemap-posts-post-1.xml',True),
    ('/blog-categories-sitemap.xml',False),('/store-products-sitemap.xml',False),
    ('/maps/posts/categories.xml',False),('/content.xml?type=posts',False)])
def test_filename_hints_are_conservative_and_ignore_queries(path,expected):
    assert article_sitemap_hint(BASE+path)==expected
