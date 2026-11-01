"""Policy contracts and operational interlock. Kernel proof is in the Linux lab."""
import importlib.util
import json
from pathlib import Path
import time
import os
import sys
import ipaddress
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from semantic_analyser.api import create_app
from semantic_analyser.config import Settings
from semantic_analyser.egress_status import policy_status, app_ready
from semantic_analyser.fetch_policy import DENIED_NETWORKS
from test_visitor_workspaces import visitor_settings, headers, start
from test_safe_fetch import FakeDNS,FakeTransport
from semantic_analyser.safe_fetch import SafeFetcher

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('namespace_policy',ROOT/'deploy/egress/policy.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
root_state = pytest.mark.skipif(sys.platform!='linux' or os.geteuid()!=0,
                               reason='Creates root-owned readiness fixtures; run in the disposable Linux root test container.')


def state(path,**changes):
    data={'version':1,'monotonic':time.monotonic(),'policy_ready':True,'app_healthy':True,'model_loaded':True,'netns':os.readlink('/proc/self/ns/net'),**changes}
    path.write_text(json.dumps(data));path.chmod(0o644)
    return data


def test_firewall_denies_all_existing_application_explicit_networks():
    for network in DENIED_NETWORKS:
        rules=policy.rules(network.version,'443')
        denied = {ipaddress.ip_network(line.split()[3]) for line in rules.splitlines()
                  if line.startswith('-A OUTPUT -d ') and line.endswith(' -j REJECT')}
        assert network in denied
        assert ':OUTPUT DROP' in rules and ':FORWARD DROP' in rules and ':INPUT DROP' in rules


def test_dns_exception_is_original_docker_dns_only_and_health_is_root_only():
    rules=policy.rules(4,'443')
    assert '--ctorigdst 127.0.0.11 --ctorigdstport 53' in rules
    assert '-A INPUT -i lo -d 127.0.0.11/32' in rules
    assert '--dport 8000 -m owner --uid-owner 0' in rules
    assert '-A OUTPUT -o lo -j ACCEPT' not in rules
    assert '--dports 80,443' in rules
    assert rules.index('-A OUTPUT -d 169.254.0.0/16')<rules.index('-A OUTPUT -p tcp -m multiport --dports 80,443')


def test_ipv6_neighbour_discovery_is_narrow_and_does_not_open_private_tcp():
    rules = policy.rules(6)
    nd = [line for line in rules.splitlines() if 'ipv6-icmp' in line]
    assert len(nd) == 4
    assert all('--hl-eq 255' in line and ('neighbor-solicitation' in line or 'neighbor-advertisement' in line) for line in nd)
    assert '-A OUTPUT -d fc00::/7 -j REJECT' in rules


@pytest.mark.parametrize('peer',['8000','22','0','443\n-A OUTPUT -j ACCEPT',None,'127.0.0.1'])
def test_untrusted_or_injected_tls_configuration_is_rejected(peer):
    with pytest.raises(ValueError):policy.rules(4,peer)


def test_operator_deny_ranges_and_ipv6_are_not_silently_ignored():
    assert '-d 11.22.0.0/16 -j REJECT' in policy.rules(4,'443',['11.22.3.4/16','2001:4860::/32'])
    assert '-d 2001:4860::/32 -j REJECT' in policy.rules(6,'443',['2001:4860::/32'])
    with pytest.raises(ValueError):policy.rules(4,'443',['unsafe'])


@pytest.mark.parametrize('changes',[
    {'version':True},{'policy_ready':False},{'policy_ready':'true'},{'monotonic':float('nan')},
    {'monotonic':float('inf')},{'monotonic':True},{'monotonic':None},
    {'netns':'another-namespace'},
    {'monotonic':time.monotonic()-100},{'monotonic':time.monotonic()+100}])
@root_state
def test_status_rejects_unready_stale_future_and_invalid_records(tmp_path,changes):
    path=tmp_path/'status.json';state(path,**changes)
    assert policy_status(path) is None


@root_state
def test_health_requires_app_and_model_readiness_without_network(tmp_path):
    path=tmp_path/'status.json';state(path)
    assert app_ready(path)
    state(path,model_loaded=False);assert not app_ready(path) and app_ready(path,False)
    state(path,app_healthy=False);assert not app_ready(path,False)
    path.write_bytes(b'{'*4097);assert policy_status(path) is None
    path.unlink();assert policy_status(path) is None


@root_state
def test_writable_and_symlink_status_is_not_trusted(tmp_path):
    path=tmp_path/'status.json';state(path);path.chmod(0o666)
    # Windows chmod does not represent POSIX group/other writability.
    if __import__('os').name=='posix':assert policy_status(path) is None
    path.chmod(0o644)
    link=tmp_path/'link.json'
    try:link.symlink_to(path)
    except OSError:return  # Linux container regression exercises the symlink assertion.
    assert policy_status(link) is None


@root_state
def test_guard_blocks_before_dns_and_transport_and_recovers(visitor_settings,engine,tmp_path):
    path=tmp_path/'status.json';dns=FakeDNS();wire=FakeTransport()
    settings=replace(visitor_settings,website_fetch_enabled=True,egress_policy_required=True,egress_state_path=path)
    app=create_app(settings,engine,SafeFetcher(resolver=dns,transport=wire))
    with TestClient(app,headers={'X-Workspace-Request':'true'}) as client:
        token,revision=start(client)
        assert client.get('/health').status_code==503
        response=client.post('/api/website/check',headers=headers(token,revision),json={'url':'https://public.example/'})
        assert response.status_code==503 and response.json()['code']=='egress_unavailable'
        assert not dns.calls and not wire.calls
        state(path)
        assert client.get('/health').status_code==200


def test_production_import_cannot_opt_out_of_network_guard():
    with pytest.raises(ValueError,match='egress'):
        Settings(production=True,website_fetch_enabled=True,egress_policy_required=False).validate()
