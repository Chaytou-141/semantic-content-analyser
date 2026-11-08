"""No real model/public networking: policy, quotas and fake-encoder API checks."""
from dataclasses import replace
import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from semantic_analyser.api import create_app
from semantic_analyser.demo_limits import DemoLimits
from semantic_analyser.fetch_policy import FetchError, FetchLimits
from semantic_analyser.safe_fetch import SafeFetcher
from test_safe_fetch import FakeDNS, FakeTransport
from test_visitor_workspaces import visitor_settings, headers, start


def request(peer, headers=()):
    return Request({'type':'http','client':(peer,123),'headers':[(k.lower().encode(),v.encode()) for k,v in headers]})


def enabled(settings, **changes):
    return replace(settings,demo_limits_enabled=True,**changes)


def test_forwarded_headers_never_override_untrusted_peer(visitor_settings):
    demo=DemoLimits(enabled(visitor_settings,trusted_proxy_cidrs=('172.30.42.3/32',)))
    assert demo.identity(request('8.8.8.8',[('X-Demo-Client','1.1.1.1'),('X-Forwarded-For','9.9.9.9')]))=='8.8.8.8'
    assert demo.identity(request('172.30.42.3',[('X-Demo-Client','1.1.1.1'),('X-Forwarded-For','9.9.9.9')]))=='1.1.1.1'
    secure=request('172.30.42.3',[('X-Demo-Client','1.1.1.1'),('X-Demo-Scheme','https')])
    assert demo.identity(secure)=='1.1.1.1' and secure.scope['scheme']=='https'
    for values in [[],[('X-Demo-Client','1.1.1.1, 8.8.8.8')],[('X-Demo-Client','fe80::1%eth0')],
                   [('X-Demo-Client','1.1.1.1'),('X-Demo-Scheme','invalid')],
                   [('X-Demo-Client','1.1.1.1'),('X-Demo-Client','8.8.8.8')]]:
        with pytest.raises(HTTPException):demo.identity(request('172.30.42.3',values))


def test_health_checks_model_and_cleanup_readiness(visitor_settings,engine):
    app=create_app(enabled(visitor_settings,preload_model=True),engine)
    with TestClient(app) as c:
        assert c.get('/health').status_code==200
        loaded=engine.model;engine.model=None
        assert c.get('/health').status_code==503
        engine.model=loaded
        manager=app.state.workspaces;manager.stop_event.set();manager.thread.join(timeout=2)
        assert c.get('/health').status_code==503


def test_rolling_budgets_expire_without_evicting_live_state(visitor_settings):
    now=[100.];demo=DemoLimits(enabled(visitor_settings,demo_rate_keys=3),clock=lambda:now[0])
    demo.charge('test','alice',2,3,60);demo.charge('test','alice',2,3,60)
    with pytest.raises(HTTPException) as error:demo.charge('test','alice',2,3,60)
    assert error.value.status_code==429 and error.value.headers['Retry-After']
    demo.charge('test','bob',2,3,60)
    with pytest.raises(HTTPException) as error:demo.charge('test','charlie',2,3,60)
    assert error.value.status_code==503
    now[0]+=60
    demo.charge('test','charlie',2,3,60)
    assert len(demo.buckets)==2


def test_api_limits_cannot_be_reset_with_forwarded_headers(visitor_settings,engine):
    app=create_app(enabled(visitor_settings,demo_requests_per_minute=2),engine)
    with TestClient(app) as c:
        assert c.get('/api/schema',headers={'X-Forwarded-For':'1.1.1.1'}).status_code==200
        assert c.get('/api/schema',headers={'X-Forwarded-For':'2.2.2.2'}).status_code==200
        r=c.get('/api/schema',headers={'X-Forwarded-For':'3.3.3.3','X-Demo-Client':'3.3.3.3'})
        assert r.status_code==429 and r.headers['retry-after']
        assert c.get('/health').status_code==200
        assert app.state.demo_limits.active==0


def test_concurrency_rejects_before_body_and_releases_slots(visitor_settings,engine):
    app=create_app(enabled(visitor_settings,demo_http_concurrency=1),engine)
    with TestClient(app) as c:
        app.state.demo_limits.enter('held')
        try:assert c.post('/api/login',content='invalid').status_code==503
        finally:app.state.demo_limits.leave()
        assert c.post('/api/login',content='invalid').status_code==403
        assert app.state.demo_limits.active==0


def test_session_creation_budget_shared_across_cookie_resets(visitor_settings,engine):
    app=create_app(enabled(visitor_settings,demo_sessions_per_hour=2),engine)
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as c:
        a,_=start(c);b,_=start(c)
        assert a!=b
        c.cookies.clear();r=c.get('/api/session')
        assert r.status_code==429 and len(app.state.workspaces.entries)==2


def test_storage_full_blocks_new_writes_but_allows_read_export_delete(visitor_settings,engine):
    settings=enabled(visitor_settings)
    app=create_app(settings,engine)
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as c:
        token,rev=start(c)
        before=c.get('/api/articles',headers=headers(token)).json()
        settings.visitor_storage_bytes=1
        r=c.post('/api/articles/reset',headers=headers(token,rev),json={})
        assert r.status_code==507
        assert c.get('/api/articles',headers=headers(token)).json()==before
        assert c.get('/api/articles/export',headers=headers(token)).status_code==200
        assert c.delete('/api/workspace',headers=headers(token,rev)).status_code==200
        assert not app.state.workspaces.entries


def test_free_disk_admission_and_expired_lease_cleanup(visitor_settings,engine,monkeypatch):
    app=create_app(enabled(visitor_settings),engine)
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as c:
        token,rev=start(c);manager=app.state.workspaces;entry=next(iter(manager.entries.values()))
        monkeypatch.setattr('semantic_analyser.workspaces.shutil.disk_usage',lambda p:SimpleNamespace(free=0))
        c.cookies.clear();assert c.get('/api/session').status_code==507
        manager.pin(entry);manager.clock=lambda:entry.created+visitor_settings.workspace_lifetime_seconds+1
        manager.cleanup();assert entry.store.path.exists()
        manager.release(entry);manager.cleanup();assert not entry.store.path.exists()


def test_sqlite_page_cap_rolls_back_on_full(visitor_settings,engine):
    app=create_app(enabled(visitor_settings),engine)
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as c:
        token,rev=start(c);entry=next(iter(app.state.workspaces.entries.values()))
        before=entry.store.export()
        with entry.store.connect() as db:pages=db.execute('PRAGMA page_count').fetchone()[0];size=db.execute('PRAGMA page_size').fetchone()[0]
        entry.store.max_bytes=pages*size
        with pytest.raises(sqlite3.DatabaseError) as error:
            with entry.store.connect() as db:db.execute("INSERT INTO metadata VALUES ('oversized',?)",('x'*100000,))
        assert error.value.sqlite_errorcode==sqlite3.SQLITE_FULL
        assert entry.store.export()==before and entry.store.revision()==rev


def test_api_sqlite_full_rejects_atomically_with_safe_error(visitor_settings,engine):
    app=create_app(enabled(visitor_settings),engine)
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as c:
        token,rev=start(c)
        assert c.post('/api/reviews',headers=headers(token,rev),json={'source_id':'A01','target_id':'A02','decision':'useful'}).status_code==200
        entry=next(iter(app.state.workspaces.entries.values()))
        before=c.get('/api/articles',headers=headers(token)).json()
        with entry.store.connect() as db:
            entry.store.max_bytes=db.execute('PRAGMA page_count').fetchone()[0]*db.execute('PRAGMA page_size').fetchone()[0]
        csv_text='id,title,body\n'+'\n'.join(f'C{i},Equipment guide,{"Useful equipment guidance. "*500}' for i in range(8))
        r=c.post('/api/articles/import',headers=headers(token,rev),json={'csv_text':csv_text})
        assert r.status_code==507,r.text
        assert c.get('/api/articles',headers=headers(token)).json()==before
        assert len(c.get('/api/reviews',headers=headers(token)).json()['reviews'])==1


def test_failed_new_database_creation_does_not_leak_workspace(visitor_settings,engine,monkeypatch):
    app=create_app(enabled(visitor_settings),engine)
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as c:
        manager=app.state.workspaces
        def full(path):
            path.write_text('new partial file')
            error=sqlite3.OperationalError('full');error.sqlite_errorcode=sqlite3.SQLITE_FULL;raise error
        monkeypatch.setattr(manager,'_store',full)
        assert c.get('/api/session').status_code==507
        assert list(p.name for p in manager.root.iterdir())==['.owner.lock'] and not manager.entries


def test_restart_preserves_owned_data_but_process_budgets_reset(visitor_settings,engine):
    settings=enabled(visitor_settings,demo_sessions_per_hour=1)
    app=create_app(settings,engine)
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as c:token,rev=start(c)
    restarted=create_app(settings,engine)
    with TestClient(restarted,headers=headers(token)) as c:
        assert c.get('/api/articles').json()['collection_revision']==rev
        assert not restarted.state.demo_limits.buckets.get(('sessions','testclient'))


def test_outbound_wire_budget_counts_robots_failures_and_new_runs(visitor_settings):
    settings=enabled(visitor_settings,demo_outbound_per_hour=2)
    guard=DemoLimits(settings);dns=FakeDNS();transport=FakeTransport({'/robots.txt':(404,b'',{})})
    fetcher=SafeFetcher(FetchLimits(delay_seconds=0),dns,transport,request_guard=guard.outbound)
    session=fetcher.new_session('owner')
    with pytest.raises(FetchError):fetcher.fetch(session,'https://public.example/missing','owner')
    assert len(transport.calls)==2
    with pytest.raises(HTTPException) as error:
        fetcher.fetch(fetcher.new_session('owner'),'https://public.example/new','owner')
    assert error.value.status_code==429 and len(transport.calls)==2


def test_allowed_host_is_not_ssrf_permission_and_offsite_is_never_resolved():
    dns=FakeDNS();wire=FakeTransport()
    fetcher=SafeFetcher(FetchLimits(delay_seconds=0),dns,wire,allowed_hosts=('public.example',))
    with pytest.raises(FetchError):fetcher.fetch(fetcher.new_session('a'),'https://other.example/','a')
    assert not dns.calls and not wire.calls
    unsafe=SafeFetcher(FetchLimits(delay_seconds=0),FakeDNS([['127.0.0.1']]),wire,allowed_hosts=('public.example',))
    with pytest.raises(FetchError) as error:unsafe.fetch(unsafe.new_session('a'),'https://public.example/','a')
    assert error.value.code=='blocked_destination' and not wire.calls


def test_allowed_public_host_and_global_outbound_budget(visitor_settings):
    guard=DemoLimits(enabled(visitor_settings,demo_global_outbound_per_hour=2))
    wire=FakeTransport({'/robots.txt':(404,b'',{}),'/':(200,b'public text',{})})
    fetcher=SafeFetcher(FetchLimits(delay_seconds=0),FakeDNS(),wire,allowed_hosts=('public.example',),request_guard=guard.outbound)
    assert fetcher.fetch(fetcher.new_session('a'),'https://public.example/','a').body==b'public text'
    with pytest.raises(HTTPException) as error:fetcher.fetch(fetcher.new_session('b'),'https://public.example/','b')
    assert error.value.status_code==429 and len(wire.calls)==2


@pytest.mark.parametrize('changes',[{'trusted_proxy_cidrs':('0.0.0.0/0',)}, {'trusted_proxy_cidrs':('::/0',)},
    {'trusted_proxy_cidrs':('172.30.42.0/24',)},
    {'demo_requests_per_minute':0}, {'workspace_idle_seconds':float('nan')}, {'workspace_storage_bytes':1},
    {'fetch_allowed_hosts':('public.example/path',)}])
def test_invalid_demo_configuration_rejected(visitor_settings,changes):
    with pytest.raises(ValueError):enabled(visitor_settings,**changes).validate()
