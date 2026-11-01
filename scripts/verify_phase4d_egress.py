"""Disposable, localhost-only Linux kernel egress proof. No Internet test targets.

Build app/egress images first. Python standard library only; openssl creates a
throwaway CA for the controlled HTTPS fixture. No model inference/loading.
"""
import argparse
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess
import time
import traceback
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def command(args, timeout=30):
    p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if p.returncode:
        raise RuntimeError(f'{args[:2]} failed: {p.stderr[-1200:]} {p.stdout[-600:]}')
    return p.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New evidence directory; never overwrites a previous run.')
    parser.add_argument('--image', default='semantic-phase4d:app')
    parser.add_argument('--egress-image', default='semantic-phase4d:egress')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixture = out / 'fixture'
    fixture.mkdir()
    shutil.copyfile(ROOT/'deploy/local/egress_fixture.py', fixture/'server.py')
    openssl = shutil.which('openssl') or 'C:/Program Files/Git/usr/bin/openssl.exe'
    command([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '2',
             '-subj', '/CN=public.fixture.invalid', '-addext', 'subjectAltName=DNS:public.fixture.invalid',
             '-keyout', str(fixture/'ca.key'), '-out', str(fixture/'ca.crt')])
    project = 'semantic-phase4d-' + secrets.token_hex(4)
    values = {'IMAGE':args.image, 'EGRESS_IMAGE':args.egress_image, 'DOMAIN':'localhost:8443',
              'APP_PASSWORD':secrets.token_hex(16), 'SECRET_KEY':secrets.token_hex(32),
              'FIXTURE_DIR':fixture.as_posix()}
    envfile = out/'lab.env'
    envfile.write_text(''.join(k+'='+v+'\n' for k,v in values.items()), encoding='utf-8')
    base = ['docker','compose','--env-file',str(envfile),'-p',project,'-f',str(ROOT/'deploy/aws/compose.production.yaml'),
            '-f',str(ROOT/'deploy/local/compose.egress-test.yaml')]
    report = {'project':project, 'checks':{}, 'errors':{}, 'model_loads':0, 'public_test_requests':0}
    owned = []

    def save():
        (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n', encoding='utf-8')

    def check(name, function):
        try:
            report['checks'][name] = function()
            print(json.dumps({'check':name,'status':'passed'}),flush=True)
        except Exception as error:
            report['errors'][name] = {'error':str(error),'traceback':traceback.format_exc()}
            print(json.dumps({'check':name,'status':'failed','error':str(error)}),flush=True)
        save()

    def inspect(cid):
        return json.loads(command(['docker','inspect',cid]))[0]

    def execute(cid, code, user=None):
        return json.loads(command(['docker','exec',*(['--user',user] if user else []),cid,'python','-c',code],90))

    def wait_status(cid, status, seconds=30):
        for _ in range(seconds):
            if inspect(cid)['State'].get('Health',{}).get('Status') == status:
                return True
            time.sleep(1)
        raise AssertionError(f'Expected {status} for {cid}')

    try:
        command(base+['config','--quiet'])
        command(base+['up','-d','--wait','--wait-timeout','90'],120)
        gate,app,proxy,target = [command(base+['ps','-q',n]) for n in ['egress','app','proxy','fixture']]
        for cid in [gate,app,proxy,target]:
            assert inspect(cid)['Config']['Labels']['com.docker.compose.project']==project
        # Hard safety prerequisites, not soft report checks: never probe these
        # public-classified addresses unless they belong to our internal fixture.
        for network in ['simulated_public','simulated_metadata','demo']:
            assert json.loads(command(['docker','network','inspect',project+'_'+network]))[0]['Internal']
        target_networks=inspect(target)['NetworkSettings']['Networks']
        assert target_networks[project+'_simulated_public']['IPAddress']=='11.203.24.3'
        assert target_networks[project+'_simulated_public']['GlobalIPv6Address']=='2001:4860:ffff:4d::3'
        assert target_networks[project+'_simulated_metadata']['IPAddress']=='169.254.169.254'
        control = command(['docker','create','--label','semantic.phase4d.owner='+project,'--network',project+'_demo',
                           '--cap-drop','ALL','--read-only','--security-opt','no-new-privileges:true',
                           '--no-healthcheck','--memory','64m','--cpus','0.5','--pids-limit','32',
                           args.egress_image,'python','-c','import time;time.sleep(600)'])
        owned.append(control)
        for network in ['simulated_public','simulated_metadata']:
            command(['docker','network','connect',project+'_'+network,control])
        command(['docker','start',control])

        def configuration():
            result = {}
            for name,cid in [('app',app),('egress',gate),('proxy',proxy)]:
                i=inspect(cid); h=i['HostConfig']
                result[name] = {'image':i['Image'],'memory':h['Memory'],'memory_swap':h['MemorySwap'],
                                'nano_cpus':h['NanoCpus'],'pids':h['PidsLimit'],'cap_add':h.get('CapAdd'),
                                'cap_drop':h.get('CapDrop'),'network_mode':h['NetworkMode'],'read_only':h['ReadonlyRootfs']}
            assert result['app']['network_mode']=='container:'+gate
            assert result['proxy']['network_mode']=='container:'+gate
            assert result['app']['cap_drop']==['ALL'] and result['proxy']['cap_drop']==['ALL']
            assert {c.removeprefix('CAP_') for c in result['egress']['cap_add']}=={'NET_ADMIN'}
            bindings=inspect(gate)['NetworkSettings']['Ports']
            assert all(b['HostIp']=='127.0.0.1' for v in bindings.values() if v for b in v)
            assert inspect(app)['State']['Health']['Status']=='healthy'
            assert not execute(app,"from pathlib import Path;import json;print(json.dumps(Path('/run/egress/status.json').stat().st_mode & 0o022))")
            for network in ['simulated_public','simulated_metadata','demo']:
                assert json.loads(command(['docker','network','inspect',project+'_'+network]))[0]['Internal']
            result['fixture_ips']={k:v['IPAddress'] for k,v in inspect(target)['NetworkSettings']['Networks'].items()}
            result['ports']=bindings
            return result
        check('namespace_configuration',configuration)

        probe = """import json,socket,struct
targets=[('public_http','11.203.24.3',80),('public_https','11.203.24.3',443),
('public_v6_http','2001:4860:ffff:4d::3',80),('public_v6_https','2001:4860:ffff:4d::3',443),
('private_http','172.30.42.4',80),('private_v6_http','fd00:4d::4',80),
('metadata_http','169.254.169.254',80),('public_ssh','11.203.24.3',22),
('public_alternative_port','11.203.24.3',8081),('alternate_dns','11.203.24.3',53)]
r={}
for name,host,port in targets:
 try:
  s=socket.create_connection((host,port),timeout=.5);s.close();r[name]=True
 except OSError:r[name]=False
for host,family in [('127.0.0.1',socket.AF_INET),('::1',socket.AF_INET6)]:
 with socket.socket(family,socket.SOCK_STREAM) as listener:
  listener.bind((host,18082));listener.listen(1)
  try:s=socket.create_connection((host,18082),timeout=.5);s.close();r['loopback_'+host]=True
  except OSError:r['loopback_'+host]=False
r['dns_addresses']=sorted({x[4][0] for x in socket.getaddrinfo('public.fixture.invalid',443,type=socket.SOCK_STREAM)})
q=struct.pack('!HHHHHH',19789,256,1,0,0,0)+b''.join(bytes([len(v)])+v.encode() for v in 'public.fixture.invalid'.split('.'))+bytes([0])+struct.pack('!HH',1,1)
for proto in ['udp','tcp']:
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM if proto=='udp' else socket.SOCK_STREAM) as sock:
  sock.settimeout(1);sock.connect(('127.0.0.11',53))
  if proto=='udp':sock.send(q);answer=sock.recv(2048)
  else:
   sock.sendall(struct.pack('!H',len(q))+q);n=struct.unpack('!H',sock.recv(2))[0];answer=b''
   while len(answer)<n:
    part=sock.recv(n-len(answer))
    if not part:raise OSError('DNS response ended early')
    answer+=part
  r['docker_dns_'+proto]=len(answer)>=12 and struct.unpack('!H',answer[:2])[0]==19789 and answer[3]&15==0
with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
 sock.settimeout(.5)
 try:sock.sendto(b'controlled-echo',('11.203.24.3',53));r['alternate_udp_dns']=sock.recv(512)==b'controlled-echo'
 except OSError:r['alternate_udp_dns']=False
print(json.dumps(r))
"""
        def enforcement():
            baseline = execute(control,probe)
            try:
                protected = execute(app,probe)
            finally:
                (out/'iptables-before-drift.txt').write_text(command(['docker','exec',gate,'iptables-save','-c'])+'\n'+
                                                             command(['docker','exec',gate,'iptables-save','-t','nat']),encoding='utf-8')
            assert all(value is True for key,value in baseline.items() if key!='dns_addresses'),baseline
            allowed={'public_http','public_https','public_v6_http','public_v6_https','docker_dns_tcp','docker_dns_udp'}
            for key,value in protected.items():
                if key!='dns_addresses':assert value == (key in allowed),(key,value)
            assert protected['dns_addresses']==['11.203.24.3','2001:4860:ffff:4d::3']
            # Root proxy/helper is also blocked from private/metadata/alternate ports.
            root = execute(gate,probe)
            assert root==protected,(root,protected)
            (out/'iptables-counters.txt').write_text(command(['docker','exec',gate,'iptables-save','-c'])+'\n'+
                                                    command(['docker','exec',gate,'ip6tables-save','-c']),encoding='utf-8')
            return {'unprotected_control':baseline,'protected_app_uid10001':protected,'protected_root_proxy_namespace':root}
        check('actual_kernel_allow_and_deny',enforcement)

        def capabilities():
            value=execute(app,"import json,pathlib; r={'status': [l for l in pathlib.Path('/proc/self/status').read_text().splitlines() if l.startswith(('Uid:','CapEff:','NoNewPrivs:'))]};\ntry:pathlib.Path('/run/egress/status.json').write_text('forged');r['writable']=True\nexcept OSError:r['writable']=False\nprint(json.dumps(r))")
            assert not value['writable'] and 'CapEff:\t0000000000000000' in value['status']
            assert execute(app,"import json;from semantic_analyser.egress_status import policy_status;print(json.dumps(policy_status('/run/egress/status.json') is not None))")
            return value
        check('unprivileged_app_cannot_forge_status',capabilities)

        command(['docker','cp',proxy+':/data/caddy/pki/authorities/local/root.crt',str(out/'caddy-root.crt')])
        context=ssl.create_default_context(cafile=str(out/'caddy-root.crt'))
        def client():
            return urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),urllib.request.HTTPSHandler(context=context))
        def call(browser,path,data=None,revision=None):
            headers={'Content-Type':'application/json','X-Workspace-Request':'true'}
            if revision:headers['If-Match']=revision
            req=urllib.request.Request('https://localhost:8443'+path,headers=headers,data=json.dumps(data).encode() if data is not None else None)
            try:
                with browser.open(req,timeout=25) as response:return response.status,json.load(response)
            except urllib.error.HTTPError as error:return error.code,json.load(error)
        a,b=client(),client()
        def visitors_and_fetch():
            for browser in [a,b]:
                assert call(browser,'/api/login',{'password':values['APP_PASSWORD']})[0]==200
                assert call(browser,'/api/session')[0]==200
            ar=call(a,'/api/articles')[1];br=call(b,'/api/articles')[1]
            assert ar['collection_revision']!=br['collection_revision']
            status,run=call(a,'/api/website/start',{'url':'https://public.fixture.invalid/sitemap.xml','method':'sitemap'},ar['collection_revision'])
            assert status==200,run
            runid=run['run_id']
            assert call(b,'/api/website/step',{'run_id':runid},br['collection_revision'])[0]==404
            for _ in range(12):
                status,run=call(a,'/api/website/step',{'run_id':runid},ar['collection_revision'])
                assert status==200,run
                if run['phase']!='discovering':break
            assert run['phase']=='selecting' and len(run['candidates'])==2,run
            status,run=call(a,'/api/website/select',{'run_id':runid,'ids':[c['id'] for c in run['candidates']]},ar['collection_revision'])
            assert status==200,run
            progress=[]
            for _ in range(4):
                status,run=call(a,'/api/website/step',{'run_id':runid},ar['collection_revision'])
                assert status==200,run
                progress.append(run['processed'])
                if run['phase']!='extracting':break
            assert run['phase']=='ready' and len(run['articles'])==2 and not run['failures'],run
            assert call(a,'/api/articles')[1]==ar and call(b,'/api/articles')[1]==br
            health=call(a,'/health');assert health[0]==200 and not health[1]['model_loaded']
            return {'separate_sessions':2,'cross_run_status':404,'discovered':2,'extracted':2,'processed':progress,
                    'requests_used':run['requests_used'],'saved_collections_unchanged':True,
                    'verified_fixture_tls':True,'model_loaded':False,'admission_import_not_run':'No model loading requested; atomic admission covered by targeted regressions.'}
        check('tls_pinned_fetch_discovery_extraction_isolation',visitors_and_fetch)

        def app_restart():
            before=[call(browser,'/api/articles')[1] for browser in [a,b]]
            command(base+['restart','app'],30)
            wait_status(app,'healthy',30)
            after=[call(browser,'/api/articles')[1] for browser in [a,b]]
            assert before==after
            assert call(a,'/health')[1]['model_loaded'] is False
            return {'sessions_and_collections_preserved':2,'model_loaded':False,
                    'rate_counter_persistence':'Not durable; process restart resets existing in-memory counters.'}
        check('app_restart_under_existing_policy',app_restart)

        def stale_interlock():
            command(['docker','pause',gate])
            try:
                time.sleep(7)
                assert not execute(app,"from semantic_analyser.egress_status import policy_status;import json;print(json.dumps(policy_status('/run/egress/status.json') is not None))")
                status,body=call(a,'/api/website/check',{'url':'https://public.fixture.invalid/'},call(a,'/api/articles')[1]['collection_revision'])
                assert status==503 and body['code']=='egress_unavailable',(status,body)
                assert not execute(app,probe)['metadata_http']
            finally:command(['docker','unpause',gate])
            for _ in range(30):
                if execute(app,"from semantic_analyser.egress_status import app_ready;import json;print(json.dumps(app_ready('/run/egress/status.json',False)))"):
                    break
                time.sleep(.5)
            else:raise AssertionError('Fresh policy/app status did not recover')
            return {'stale_seconds':7,'fetch_status':503,'kernel_metadata_still_denied':True}
        check('paused_owner_freshness_interlock',stale_interlock)

        def drift():
            command(['docker','exec',gate,'iptables','-I','OUTPUT','1','-d','172.30.42.4/32','-j','ACCEPT'])
            for _ in range(30):
                if not execute(app,"import json;print(json.dumps(json.load(open('/run/egress/status.json'))['policy_ready']))"):
                    break
                time.sleep(.5)
            else:raise AssertionError('Rule drift did not quarantine the namespace')
            value=execute(app,"import socket,json; r={};\nfor h in ['11.203.24.3','172.30.42.4','169.254.169.254']:\n try:s=socket.create_connection((h,80),timeout=.5);s.close();r[h]=True\n except OSError:r[h]=False\nprint(json.dumps(r))")
            assert not any(value.values()),value
            logs=command(['docker','logs',gate]);assert 'policy_unavailable_quarantined' in logs
            return {'operator_injected_drift':'quarantined','all_test_connections_denied':value}
        check('rule_drift_fails_closed',drift)
        def no_capability():
            cid=command(['docker','create','--label','semantic.phase4d.owner='+project,'--network',project+'_demo',
                         '--cap-drop','ALL','--read-only','--tmpfs','/run/egress:size=64k',
                         '-e','APP_PEER=172.30.42.5','--ip','172.30.42.5',args.egress_image])
            owned.append(cid);command(['docker','start',cid]);time.sleep(4)
            i=inspect(cid)
            # Unsupported/missing capability cannot become ready, even with valid namespace identity.
            assert i['State']['Health']['Status']!='healthy'
            text=command(['docker','exec',cid,'cat','/run/egress/status.json'])
            assert json.loads(text)['policy_ready'] is False
            return {'without_net_admin':'not_ready','status_ready':False}
        check('missing_firewall_capability_fails_closed',no_capability)
        for service in ['egress','app','proxy','fixture']:
            (out/(service+'.log')).write_text(command(base+['logs','--no-color',service]),encoding='utf-8')
    except Exception as error:
        report['errors']['setup_or_run']={'error':str(error),'traceback':traceback.format_exc()}
        print(json.dumps({'status':'failed','error':str(error)}),flush=True)
        try:(out/'compose-failure.log').write_text(command(base+['logs','--no-color']),encoding='utf-8')
        except Exception:pass
    finally:
        for cid in owned:
            if inspect(cid)['Config']['Labels'].get('semantic.phase4d.owner')!=project:raise RuntimeError('Cleanup ownership mismatch')
            command(['docker','rm','-f',cid])
        command(base+['down','--volumes','--remove-orphans'],60)
        envfile.unlink(missing_ok=True)
        (fixture/'ca.key').unlink(missing_ok=True)
        report['cleanup']='Owned project and auxiliary containers removed; disposable credentials/key deleted.'
        save()
    print(json.dumps({'passed':len(report['checks']),'failed':len(report['errors']),'report':str(out/'verification.json')}))
    return bool(report['errors'])


if __name__=='__main__':
    raise SystemExit(main())
