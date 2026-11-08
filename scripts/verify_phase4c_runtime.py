"""Exercise an already-started disposable Phase 4C Compose project, then clean it up.

No builds, public requests, inference or host database mounts. See phase4c report.
"""
import argparse
import hashlib
import http.cookiejar
import http.client
import json
from pathlib import Path
import re
import secrets
import socket
import ssl
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'scripts')]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,default=ROOT/'runtime/phase4c/rehearsal-state.json')
    parser.add_argument('--start',action='store_true',help='Prepare a fresh uniquely owned project and start it.')
    parser.add_argument('--prepare-only',action='store_true',help='Create/validate fresh state without starting services.')
    parser.add_argument('--image',default='semantic-demo:phase4c-verified')
    args=parser.parse_args();out=args.state.parent
    if args.start or args.prepare_only:
        if args.state.exists():parser.error('Use a new --state path to preserve previous rehearsal evidence.')
        out.mkdir(parents=True,exist_ok=True)
        values={'IMAGE':args.image,'DOMAIN':'localhost:8443','APP_PASSWORD':secrets.token_hex(16),'SECRET_KEY':secrets.token_hex(32)}
        env_path=(out/'rehearsal.env').resolve()
        if env_path.exists():parser.error('Refusing to overwrite an existing rehearsal environment file.')
        env_path.write_text(''.join(k+'='+v+'\n' for k,v in values.items()),encoding='utf-8')
        args.state.write_text(json.dumps({'project':'semantic-phase4c-'+secrets.token_hex(4),'image':args.image,'env_file':str(env_path)},indent=2)+'\n',encoding='utf-8')
    state=json.loads(args.state.read_text())
    project=state['project'];image=state['image'];owned=[];clients=[]
    assert re.fullmatch(r'semantic-phase4c-[a-f0-9]{8}',project),'Not a rehearsal-owned project'
    env_values=dict(line.split('=',1) for line in Path(state['env_file']).read_text().splitlines() if line)
    base=['docker','compose','--env-file',state['env_file'],'-p',project,'-f',str(ROOT/'deploy/aws/compose.production.yaml'),'-f',str(ROOT/'deploy/local/compose.rehearsal.yaml')]
    report={'project':project,'checks':{},'errors':{},'real_model_inference_runs':0,'public_test_requests':0,'host_database_mounts':0}
    def cmd(parts,timeout=30):
        p=subprocess.run(parts,capture_output=True,text=True,timeout=timeout)
        if p.returncode:raise RuntimeError('Command failed: '+parts[0]+' '+parts[1]+'; '+p.stderr[-800:])
        return p.stdout.strip()
    def check(name,function):
        try:report['checks'][name]=function();print(json.dumps({'check':name,'status':'passed'}),flush=True)
        except Exception as e:
            report['errors'][name]={'message':str(e),'traceback':traceback.format_exc()}
            print(json.dumps({'check':name,'status':'failed','error':str(e)}),flush=True)
        (out/'runtime-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    cmd(base+['config','--quiet'])
    if args.prepare_only:
        print(json.dumps({'state':str(args.state),'project':project,'compose_config_valid':True,'containers_started':0}));return 0
    if args.start:
        try:cmd(base+['up','-d','--wait','--wait-timeout','180'],timeout=210)
        except BaseException:
            cmd(base+['down','--volumes','--remove-orphans'],timeout=45)
            raise
    app=cmd(base+['ps','-q','app']);proxy=cmd(base+['ps','-q','proxy'])
    for cid in [app,proxy]:
        inspected=json.loads(cmd(['docker','inspect',cid]))[0]
        assert inspected['Config']['Labels']['com.docker.compose.project']==project
    def execute(code,cid=app):return json.loads(cmd(['docker','exec',cid,'python','-c',code]))
    def create(suffix,options,code):
        cid=cmd(['docker','create','--name',project+'-'+suffix,'--label','semantic.phase4c.owner='+project,
                 '--read-only','--tmpfs','/tmp:size=64m,mode=1777','--cap-drop','ALL','--security-opt','no-new-privileges:true',
                 *options,image,'python','-c',code])
        owned.append(cid);cmd(['docker','start',cid]);return cid
    def finish(cid,timeout=20):
        rc=int(cmd(['docker','wait',cid],timeout));logs=cmd(['docker','logs',cid])
        return rc,logs,json.loads(cmd(['docker','inspect',cid]))[0]
    try:
        def configuration():
            values={}
            for name,cid in [('app',app),('proxy',proxy)]:
                i=json.loads(cmd(['docker','inspect',cid]))[0];h=i['HostConfig']
                values[name]={'image_id':i['Image'],'user':i['Config']['User'],'memory_bytes':h['Memory'],
                    'memory_swap_bytes':h['MemorySwap'],'nano_cpus':h['NanoCpus'],'pids_limit':h['PidsLimit'],
                    'read_only':h['ReadonlyRootfs'],'cap_drop':h.get('CapDrop'),'security_opt':h['SecurityOpt'],
                    'ports':i['NetworkSettings']['Ports'],'health':i['State']['Health']['Status'],
                    'restart_policy':h['RestartPolicy']['Name']}
                assert values[name]['health']=='healthy'
            assert values['app']['memory_bytes']==4*1024**3 and values['app']['nano_cpus']==2*10**9
            assert values['app']['pids_limit']==128 and values['app']['read_only'] and values['app']['user']=='appuser'
            assert values['proxy']['memory_bytes']==256*1024**2 and values['proxy']['nano_cpus']==500000000
            assert all(not bindings for bindings in values['app']['ports'].values())
            bindings=[b for v in values['proxy']['ports'].values() for b in v]
            assert {b['HostPort'] for b in bindings}=={'8080','8443'} and all(b['HostIp']=='127.0.0.1' for b in bindings)
            assert '--no-proxy-headers' in json.loads(cmd(['docker','inspect',app]))[0]['Config']['Cmd']
            values['cgroups']=execute("import pathlib,json\np=pathlib.Path('/sys/fs/cgroup');v2=(p/'cgroup.controllers').exists()\ndef read(*paths):\n for x in paths:\n  if (p/x).exists():return (p/x).read_text().strip()\n return None\nr={'version':2 if v2 else 1,'cpu_quota':read('cpu.max') if v2 else read('cpu/cpu.cfs_quota_us'),'cpu_period':None if v2 else read('cpu/cpu.cfs_period_us'),'memory_limit':read('memory.max','memory/memory.limit_in_bytes'),'swap_or_memsw_limit':read('memory.swap.max','memory/memory.memsw.limit_in_bytes'),'memory_current':read('memory.current','memory/memory.usage_in_bytes'),'memory_peak':read('memory.peak','memory/memory.max_usage_in_bytes'),'pids_max':read('pids.max','pids/pids.max')};print(json.dumps(r))")
            assert int(values['cgroups']['memory_limit'])==4*1024**3 and int(values['cgroups']['pids_max'])==128
            # Every application and UI file copied by Docker must match this checkout.
            hashes=execute("import pathlib,hashlib,json; print(json.dumps({str(p.relative_to('/app')):hashlib.sha256(p.read_bytes()).hexdigest() for d in ['semantic_analyser','web'] for p in (pathlib.Path('/app')/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts}))")
            assert hashes=={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in hashes}
            values['matching_source_files']=len(hashes)
            values['filesystem']=execute("import os,json,pathlib; r={};\ntry:pathlib.Path('/app/should-not-write').write_text('x')\nexcept OSError as e:r['root_write_errno']=e.errno\np=pathlib.Path('/tmp/phase4c-write');p.write_text('ok');r['tmp_writable']=p.read_text()=='ok';p.unlink();r['uid']=os.getuid();r['hardening']=[l for l in pathlib.Path('/proc/self/status').read_text().splitlines() if l.startswith(('CapEff:','NoNewPrivs:'))];print(json.dumps(r))")
            assert values['filesystem']['root_write_errno']==30 and values['filesystem']['uid']==10001
            return values
        check('configuration_sources_cgroups',configuration)
        cert=out/'caddy-local-root.crt'
        cmd(['docker','cp',proxy+':/data/caddy/pki/authorities/local/root.crt',str(cert)])
        context=ssl.create_default_context(cafile=str(cert))
        def browser():
            jar=http.cookiejar.CookieJar()
            return urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(jar),urllib.request.HTTPSHandler(context=context)),jar
        def call(client,path,data=None,revision=None,extra=None,method=None):
            headers={'X-Workspace-Request':'true','Content-Type':'application/json',**(extra or {})}
            if revision:headers['If-Match']=revision
            req=urllib.request.Request('https://localhost:8443'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
            try:
                with client.open(req,timeout=10) as response:
                    raw=response.read();return response.status,json.loads(raw) if raw else None,dict(response.headers)
            except urllib.error.HTTPError as error:return error.code,json.loads(error.read()),dict(error.headers)
        def tls_auth_isolation():
            nonlocal clients
            a,aj=browser();b,bj=browser();clients=[a,b]
            assert call(a,'/api/articles')[0]==401
            for client in clients:
                assert call(client,'/api/login',{'password':env_values['APP_PASSWORD']})[0]==200
                assert call(client,'/api/session')[0]==200
            ar=call(a,'/api/articles')[1];br=call(b,'/api/articles')[1]
            assert len(ar['articles'])==len(br['articles'])==21 and ar['collection_revision']!=br['collection_revision']
            # Mechanical disposable isolation sentinel, not a new editorial judgement.
            sentinel={'source_id':'A01','target_id':'A02','decision':'useful','note':'Disposable isolation sentinel; not editorial evaluation.'}
            assert call(a,'/api/reviews',sentinel,ar['collection_revision'])[0]==200
            assert len(call(a,'/api/reviews')[1]['reviews'])==1 and not call(b,'/api/reviews')[1]['reviews']
            assert call(b,'/api/reviews',sentinel,ar['collection_revision'])[0]==409
            assert call(a,'/api/does-not-exist')[0]==404
            assert call(a,'/api/website/start',{'url':'file:///etc/passwd'},ar['collection_revision'])[0] in {400,422},'Invalid scheme not rejected with current revision'
            status,health,_=call(a,'/health');assert status==200 and health['model_loaded']
            with a.open('http://localhost:8080/health',timeout=10) as response:assert response.geturl()=='https://localhost:8443/health'
            cookies=[{'name':c.name,'secure':c.secure,'http_only':'HttpOnly' in c._rest,'same_site':c._rest.get('SameSite')} for c in aj]
            assert all(c['secure'] for c in cookies) and any(c['name']=='__Host-semantic_visitor' for c in cookies)
            with context.wrap_socket(socket.create_connection(('localhost',8443),timeout=5),server_hostname='localhost') as sock:
                tls={'version':sock.version(),'subject_alt_names':sock.getpeercert().get('subjectAltName'),'issuer':sock.getpeercert().get('issuer')}
            return {'health':health,'visitors':2,'isolation_sentinel_rows':1,'cross_revision_status':409,'cookies':cookies,'tls':tls,'http_redirect':'https://localhost:8443/health','public_certificate':False}
        check('tls_auth_isolation_errors',tls_auth_isolation)
        def offline_ui():
            from playwright.sync_api import sync_playwright,expect
            from verify_discovery_progress import snapshots
            from link_ui_fixtures import fixture
            views=snapshots();articles,groups,reviews=fixture();cases=[];blocked=[]
            with sync_playwright() as pw:
                browser_instance=pw.chromium.launch(channel='chromium')
                for width,height in [(1440,1000),(390,844)]:
                    ctx=browser_instance.new_context(ignore_https_errors=True,viewport={'width':width,'height':height})
                    page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    def guard(route):
                        request=route.request
                        if not request.url.startswith('https://localhost:8443/') or (request.method!='GET' and not request.url.startswith('https://localhost:8443/api/login')):
                            blocked.append(request.url);route.abort()
                        else:route.continue_()
                    page.route('**/*',guard);page.goto('https://localhost:8443/')
                    page.locator('#login-form input').fill(env_values['APP_PASSWORD']);page.locator('#login-form button').click()
                    expect(page.locator('#workspace')).to_be_visible()
                    page.evaluate('r=>{renderWebsite(r);$("#website-dialog").showModal();}',views['one'])
                    meter=page.locator('#extraction-meter');expect(meter).to_be_visible()
                    box=meter.bounding_box();assert box['height']>=18 and box['width']>100
                    assert meter.evaluate('p=>[p.value,p.max]')==[1,36]
                    page.screenshot(path=str(out/f'extraction-1-of-36-{width}.png'))
                    page.evaluate('r=>renderWebsite(r)',views['two']);assert meter.evaluate('p=>p.value')==2
                    page.evaluate('async()=>{await task("Offline controlled error",async()=>{throw Error("Controlled fixture error");});}')
                    expect(page.locator('#extraction-count')).to_contain_text('Stopped. Last confirmed: 2 of 36')
                    page.evaluate('$("#website-dialog").close()')
                    page.evaluate('p=>{state.articles=p.articles;state.sourceId="S01";navigate("links");renderLinks({results:p.groups,reviews:p.reviews,collection_revision:state.revision});}',{'articles':articles,'groups':{'embeddings':groups['embeddings']},'reviews':reviews})
                    expect(page.locator('[role=tab]')).to_have_count(5)
                    page.locator('[role=tab]').nth(4).click()
                    expect(page.locator('.link-route-target')).to_contain_text(groups['embeddings']['results'][4]['title'])
                    assert page.locator('.full-evidence pre').all_text_contents()==[groups['embeddings']['results'][4]['source_passage'],groups['embeddings']['results'][4]['passage']]
                    page.locator('[role=tab]').nth(0).focus();page.keyboard.press('End')
                    expect(page.locator('[role=tab]').nth(4)).to_be_focused()
                    assert not errors and not page.evaluate('window.linkFixtureExecuted || false')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    page.screenshot(path=str(out/f'link-opportunities-{width}.png'),full_page=True)
                    cases.append({'viewport':[width,height],'visible_progress':box,'counts':[1,2],'candidates':5,'browser_errors':errors})
                    ctx.close()
                browser_instance.close()
            assert not blocked,blocked
            return {'cases':cases,'browser_tls':'Local CA warning bypassed in browser only; Python client independently verified trusted localhost TLS.','fixture_analysis_endpoints_called':0,'real_backend_sessions':True,'unexpected_requests':blocked}
        check('container_https_ui_offline_fixtures',offline_ui)
        def network():
            name=project+'_demo';net=json.loads(cmd(['docker','network','inspect',name]))[0];assert net['Internal']
            fixture_code="from http.server import BaseHTTPRequestHandler,HTTPServer\nclass H(BaseHTTPRequestHandler):\n def do_GET(self):\n  self.send_response(200);self.end_headers();self.wfile.write(b'Controlled internal fixture')\nHTTPServer(('0.0.0.0',18081),H).serve_forever()"
            create('private-fixture',['--network',name,'--ip','172.30.42.4','--memory','128m','--cpus','0.5','--pids-limit','32'],fixture_code)
            code="import json,time,urllib.request,pathlib;from semantic_analyser.safe_fetch import SafeFetcher;from semantic_analyser.fetch_policy import FetchError\nr={}\nfor i in range(20):\n try:\n  r['private_nonstandard_port_status']=urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://172.30.42.4:18081',timeout=1).status;break\n except OSError:time.sleep(.1)\nf=SafeFetcher()\ntry:f.fetch(f.new_session('probe'),'http://172.30.42.4/','probe')\nexcept FetchError as e:r['safe_fetch_private_code']=e.code\nr['ipv4_routes']=pathlib.Path('/proc/net/route').read_text();r['ipv6_routes']=pathlib.Path('/proc/net/ipv6_route').read_text();print(json.dumps(r))"
            values=execute(code)
            assert values['private_nonstandard_port_status']==200 and values['safe_fetch_private_code']=='blocked_destination'
            routes=[line.split() for line in values['ipv4_routes'].splitlines()[1:]]
            assert not any(row[1]=='00000000' for row in routes)
            return {'app_internal_network':True,'app_no_ipv4_default_route':True,'controlled_private_port_access':values['private_nonstandard_port_status'],
                'safe_fetch_private_code':values['safe_fetch_private_code'],'raw_routes':values,
                'production_bridge_firewall_verified':False,'public_dns_or_external_destinations_tested':False,
                'limitation':'Private peers and nonstandard ports are reachable by raw sockets. Only the app is offline-isolated; Caddy has a separate localhost ingress bridge. This is not a public-import-compatible firewall.'}
        check('actual_network_boundaries',network)
        def cpu_probe():
            code="import pathlib,time,json,os\nbase=pathlib.Path('/sys/fs/cgroup');v2=(base/'cpu.stat').exists();p=base/('cpu.stat' if v2 else 'cpu/cpu.stat');read=lambda:dict(x.split() for x in p.read_text().splitlines());a=read();start=time.monotonic();cpu=time.process_time()\nwhile time.monotonic()-start<2:pass\nb=read();quota=(base/'cpu.max').read_text().strip() if v2 else (base/'cpu/cpu.cfs_quota_us').read_text().strip()+' '+(base/'cpu/cpu.cfs_period_us').read_text().strip();print(json.dumps({'cpu_max':quota,'cgroup_version':2 if v2 else 1,'throttled_periods':int(b['nr_throttled'])-int(a['nr_throttled']),'cpu_seconds':round(time.process_time()-cpu,3),'wall_seconds':round(time.monotonic()-start,3)}))"
            cid=create('cpu-probe',['--network','none','--memory','64m','--memory-swap','64m','--cpus','0.25','--pids-limit','32'],code)
            rc,logs,_=finish(cid);r=json.loads(logs);assert rc==0 and r['throttled_periods']>0;return r
        check('cpu_quota_reduced_probe',cpu_probe)
        def memory_probe():
            cid=create('oom-probe',['--network','none','--memory','32m','--memory-swap','32m','--cpus','0.5','--pids-limit','16'],"x=bytearray(128*1024**2);print(len(x),flush=True)")
            rc,logs,i=finish(cid);assert rc==137 and i['State']['OOMKilled']
            return {'probe_limit_bytes':32*1024**2,'allocation_attempt_bytes':128*1024**2,'exit_code':rc,'oom_killed':True,'production_app_4g_exhaustion':False}
        check('memory_hard_limit_reduced_probe',memory_probe)
        def pid_probe():
            code="import os,time,json\nchildren=[];error=None\nfor i in range(40):\n try:\n  pid=os.fork()\n  if pid==0:time.sleep(2);os._exit(0)\n  children.append(pid)\n except OSError as e:error=e.errno;break\nfor pid in children:os.waitpid(pid,0)\nprint(json.dumps({'children':len(children),'fork_errno':error}))"
            cid=create('pid-probe',['--network','none','--memory','128m','--cpus','0.5','--pids-limit','16'],code)
            rc,logs,_=finish(cid);r=json.loads(logs);assert rc==0 and r['fork_errno']==11 and r['children']<=15;return r
        check('pid_hard_limit_reduced_probe',pid_probe)
        def retention():
            options=['--network','none','--memory','1g','--cpus','1','--pids-limit','128',
                     '--tmpfs','/app/runtime:size=64m,uid=10001,gid=10001,mode=0700']
            for key,value in {'APP_ENV':'development','WORKSPACE_MODE':'visitor','SECRET_KEY':'disposable-local-retention-key-at-least32','PRELOAD_MODEL':'false',
                              'WORKSPACE_IDLE_SECONDS':'3','WORKSPACE_LIFETIME_SECONDS':'20','WORKSPACE_CLEANUP_SECONDS':'0.2'}.items():options+=['-e',key+'='+value]
            cid=create('retention',options,"import uvicorn;uvicorn.run('semantic_analyser.api:app',host='127.0.0.1',port=8000,proxy_headers=False)")
            code="import urllib.request,urllib.error,http.cookiejar,time,pathlib,json\nc=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))\nfor i in range(80):\n try:c.open('http://127.0.0.1:8000/health',timeout=1);break\n except OSError:time.sleep(.1)\ndef get(path):return c.open(urllib.request.Request('http://127.0.0.1:8000'+path,headers={'X-Workspace-Request':'true'}),timeout=2)\nget('/api/session').read();root=pathlib.Path('/app/runtime/visitors');before=len([p for p in root.iterdir() if p.is_dir()]);time.sleep(4)\nfor i in range(30):\n after=len([p for p in root.iterdir() if p.is_dir()])\n if after==0:break\n time.sleep(.1)\ntry:get('/api/articles');status=200\nexcept urllib.error.HTTPError as e:status=e.code\nprint(json.dumps({'created_directories':before,'remaining_directories':after,'expired_cookie_status':status,'idle_seconds':3,'cleanup_seconds':.2}))"
            r=execute(code,cid);assert r['created_directories']==1 and r['remaining_directories']==0 and r['expired_cookie_status']==410;return r
        check('actual_idle_expiry_cleanup',retention)
        def request_budget():
            a=clients[0];statuses=[];limit=None
            jar=next(h.cookiejar for h in a.handlers if isinstance(h,urllib.request.HTTPCookieProcessor))
            cookie='; '.join(c.name+'='+c.value for c in jar)
            # A persistent local connection makes this a bounded burst, rather
            # than timing out one-minute windows on Windows IPv6 fallback.
            connection=http.client.HTTPSConnection('localhost',8443,context=context,timeout=5)
            def get(path,extra=None):
                connection.request('GET',path,headers={'Cookie':cookie,'X-Workspace-Request':'true',**(extra or {})})
                response=connection.getresponse();status=response.status;pause=response.getheader('Retry-After');response.read();return status,pause
            try:
                for i in range(245):
                    status,pause=get('/api/meta',{'X-Forwarded-For':f'198.51.100.{i%250+1}','X-Demo-Client':f'203.0.113.{i%250+1}','X-Demo-Scheme':'http','Forwarded':'for=192.0.2.1;proto=http'})
                    statuses.append(status)
                    if status==429:limit={'attempt':i+1,'retry_after':pause};break
                assert limit and limit['retry_after']
                assert get('/api/meta',{'X-Demo-Client':'192.0.2.200','X-Forwarded-For':'192.0.2.200'})[0]==429
                assert get('/health')[0]==200
            finally:connection.close()
            return {'first_limit':limit,'attempted':len(statuses),'spoofed_headers_did_not_reset_budget':True,'health_after_overload':200,'process_restart_budget_reset':'Known boundary; separately covered in Linux regression and Phase4B restart smoke.'}
        check('https_proxy_request_budget_spoofing',request_budget)
        report['docker_stats']=cmd(['docker','stats','--no-stream','--format','{{.Name}}|{{.MemUsage}}|{{.CPUPerc}}',app,proxy])
        for name,cid in [('app',app),('proxy',proxy)]:
            (out/(name+'-logs.txt')).write_text(cmd(['docker','logs',cid]),encoding='utf-8')
    finally:
        cleanup=[]
        for cid in reversed(owned):
            i=json.loads(cmd(['docker','inspect',cid]))[0]
            assert i['Config']['Labels'].get('semantic.phase4c.owner')==project
            cmd(['docker','rm','-f',cid]);cleanup.append(cid[:12])
        cmd(base+['down','--volumes','--remove-orphans'],timeout=45)
        report['cleanup']={'owned_helper_containers_removed':cleanup,'compose_project_removed_with_volumes':True}
        report['status']='passed' if not report['errors'] else 'failed'
        (out/'runtime-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'status':report['status'],'checks':len(report['checks']),'failures':report['errors'],'cleanup':report['cleanup']}),flush=True)
    return 0 if not report['errors'] else 1


if __name__=='__main__':raise SystemExit(main())
