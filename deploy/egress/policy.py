"""Network-namespace firewall owner. Never runs in the host network namespace.

The unprivileged app shares this namespace but cannot modify rules/state. No proxying,
DNS re-resolution, TLS termination or website content processing occurs here.
"""
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

STATE = Path('/run/egress/status.json')
V4_DENY = ('0.0.0.0/8','10.0.0.0/8','100.64.0.0/10','127.0.0.0/8','169.254.0.0/16',
           '172.16.0.0/12','192.0.0.0/24','192.0.2.0/24','192.168.0.0/16','192.88.99.0/24',
           '198.18.0.0/15','198.51.100.0/24','203.0.113.0/24','224.0.0.0/4','240.0.0.0/4',
           '168.63.129.16/32')
V6_DENY = ('::/96','::ffff:0:0/96','64:ff9b::/96','64:ff9b:1::/48','100::/64',
           '2001::/23','2001:db8::/32','2002::/16','3ffe::/16','3fff::/20','fc00::/7','fe80::/10','fec0::/10','ff00::/8')
HEALTH_CODE = """import http.client,json
c=http.client.HTTPConnection('127.0.0.1',8000,timeout=1)
try:
 c.request('GET','/health');r=c.getresponse();n=r.getheader('Content-Length','')
 if r.status!=200 or not n.isdecimal() or int(n)>1024:raise ValueError()
 d=json.loads(r.read(int(n)))
 print(json.dumps({'healthy':d.get('status')=='ok','model_loaded':d.get('model_loaded') is True}))
finally:c.close()
"""


def command(args, data=None):
    result = subprocess.run(args, input=data, text=True, capture_output=True, timeout=3)
    if result.returncode:
        raise RuntimeError('firewall_command_failed')
    return result.stdout


def rules(version, tls_port='443', extra=()):
    if str(tls_port) not in {'443','8443'}:
        raise ValueError('unsupported_frontend_tls_port')
    deny = list(V4_DENY if version == 4 else V6_DENY)
    for value in extra:
        network = ipaddress.ip_network(value, strict=False)
        if network.version == version:deny.append(str(network))
    lines = ['*filter', ':INPUT DROP [0:0]', ':FORWARD DROP [0:0]', ':OUTPUT DROP [0:0]',
             '-A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
             '-A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT']
    if version == 4:
        # Root-only own backend and TLS health exceptions. Caddy and the monitor
        # share this namespace; the app is UID 10001, without capabilities.
        lines += ['-A OUTPUT -o lo -d 127.0.0.1/32 -p tcp --dport 8000 -m owner --uid-owner 0 -j ACCEPT',
                  '-A INPUT -i lo -s 127.0.0.1/32 -d 127.0.0.1/32 -p tcp --dport 8000 -j ACCEPT',
                  f'-A OUTPUT -o lo -d 127.0.0.1/32 -p tcp --dport {tls_port} -m owner --uid-owner 0 -j ACCEPT']
        # Docker DNATs 127.0.0.11:53 to its resolver's local ephemeral port BEFORE
        # filter/OUTPUT. Match the conntrack ORIGINAL destination, never all lo.
        for protocol in ['udp','tcp']:
            lines.append(f'-A OUTPUT -o lo -d 127.0.0.11/32 -p {protocol} -m conntrack --ctorigdst 127.0.0.11 --ctorigdstport 53 -j ACCEPT')
            lines.append(f'-A INPUT -i lo -d 127.0.0.11/32 -p {protocol} -m conntrack --ctorigdst 127.0.0.11 --ctorigdstport 53 -j ACCEPT')
    else:
        lines.append(f'-A OUTPUT -o lo -d ::1/128 -p tcp --dport {tls_port} -m owner --uid-owner 0 -j ACCEPT')
        # IPv6 requires link-local neighbour discovery even for public TCP peers.
        # Only ND with the mandatory hop limit 255; no general ICMP/IPv6 bypass.
        for direction in ['INPUT','OUTPUT']:
            for kind in ['neighbor-solicitation','neighbor-advertisement']:
                lines.append(f'-A {direction} -p ipv6-icmp --icmpv6-type {kind} -m hl --hl-eq 255 -j ACCEPT')
    lines.append(f'-A INPUT -p tcp -m multiport --dports 80,{tls_port} -m conntrack --ctstate NEW -j ACCEPT')
    for network in deny:lines.append(f'-A OUTPUT -d {network} -j REJECT')
    if version == 4:
        lines.append('-A OUTPUT -p tcp -m multiport --dports 80,443 -m conntrack --ctstate NEW -j ACCEPT')
    else:
        lines.append('-A OUTPUT -d 2000::/3 -p tcp -m multiport --dports 80,443 -m conntrack --ctstate NEW -j ACCEPT')
    lines += ['COMMIT','']
    return '\n'.join(lines)


def sealed():
    return '*filter\n:INPUT DROP [0:0]\n:FORWARD DROP [0:0]\n:OUTPUT DROP [0:0]\nCOMMIT\n'


def snapshot(version):
    text = command(['iptables-save' if version == 4 else 'ip6tables-save','-t','filter'])
    return '\n'.join(re.sub(r'\[\d+:\d+\]','[0:0]',line) for line in text.splitlines() if line and not line.startswith('#'))


def write_status(policy_ready, app_healthy=False, model_loaded=False):
    data = {'version':1,'monotonic':time.monotonic(),'policy_ready':policy_ready,
            'app_healthy':app_healthy,'model_loaded':model_loaded,
            'netns':os.readlink('/proc/self/ns/net')}
    temporary=STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(data),encoding='utf-8');temporary.chmod(0o644)
    temporary.replace(STATE)


def event(code):
    print(json.dumps({'component':'egress','event':code}),flush=True)


def namespace_prerequisites():
    # Do not even attempt filter changes on a host-network/misconfigured launch.
    # The verified Compose owner has this exact local address and Docker DNS.
    expected=ipaddress.ip_address(os.environ['APP_PEER'])
    if expected.version!=4 or not expected.is_private or expected.is_loopback:
        raise ValueError('unexpected_namespace_address')
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as probe:
        probe.bind((str(expected),0))
    resolvers=[line.split()[1] for line in Path('/etc/resolv.conf').read_text().splitlines()
               if line.startswith('nameserver ') or line.startswith('nameserver\t')]
    if resolvers!=['127.0.0.11']:raise ValueError('docker_embedded_dns_required')


def monitor():
    expected = {}
    STATE.parent.mkdir(parents=True,exist_ok=True)
    write_status(False)
    try:namespace_prerequisites()
    except Exception:
        event('namespace_prerequisites_failed')
        raise SystemExit(1)
    try:
        # Establish DROP before opening a single exception. Compose does not
        # start the app until successful installation and a fresh health state.
        for version in [4,6]:command(['iptables-restore' if version == 4 else 'ip6tables-restore','-w','2'],sealed())
        extra=tuple(v.strip() for v in os.getenv('EGRESS_DENY_CIDRS','').split(',') if v.strip())
        for version in [4,6]:
            command(['iptables-restore' if version == 4 else 'ip6tables-restore','-w','2'],rules(version,os.getenv('INGRESS_TLS_PORT','443'),extra))
            expected[version]=snapshot(version)
        write_status(True)
        event('policy_enforced')
        previous=None
        while True:
            if any(snapshot(v)!=expected[v] for v in [4,6]):raise RuntimeError('policy_drift')
            healthy=False;loaded=False
            try:
                probe=subprocess.run([sys.executable,'-I','-S','-c',HEALTH_CODE],capture_output=True,text=True,timeout=2)
                if probe.returncode==0 and len(probe.stdout)<=128:
                    data=json.loads(probe.stdout);healthy=data['healthy'] is True;loaded=data['model_loaded'] is True
            except (OSError,ValueError,KeyError,subprocess.TimeoutExpired):pass
            write_status(True,healthy,loaded)
            if healthy!=previous:event('app_healthy' if healthy else 'app_not_ready');previous=healthy
            time.sleep(1)
    except BaseException:
        # Quarantine stays up/unhealthy; no automatic retry that could hide drift.
        for version in [4,6]:
            try:command(['iptables-restore' if version == 4 else 'ip6tables-restore','-w','2'],sealed())
            except Exception:pass
        write_status(False)
        event('policy_unavailable_quarantined')
        while True:time.sleep(60)


def health():
    try:
        data=json.loads(STATE.read_text())
        return 0 if (data.get('policy_ready') is True and data.get('netns')==os.readlink('/proc/self/ns/net')
                     and 0 <= time.monotonic()-data['monotonic'] <= 5) else 1
    except (OSError,ValueError,KeyError,TypeError):return 1


if __name__=='__main__':
    if sys.argv[1:] == ['health']:raise SystemExit(health())
    if sys.argv[1:] != ['run']:raise SystemExit('Use run or health')
    monitor()
