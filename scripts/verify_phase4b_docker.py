"""Local-only Linux container smoke. No builds/pulls, public fetches or inference."""
import argparse
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',default='semantic-demo:local')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'runtime/phase4b',
                        help='Evidence directory; use a new directory to preserve earlier results.')
    args=parser.parse_args()
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    result={'linux_container_verified':False,'model_inference_runs':0,'public_fetches':0}
    def command(parts, **kwargs):
        return subprocess.run(parts,capture_output=True,text=True,timeout=kwargs.pop('timeout',20),**kwargs)
    if not shutil.which('docker'):
        result.update(status='skipped',reason='Docker CLI not found; no Linux container ran.')
    else:
        try:
            info=command(['docker','info','--format','{{.OSType}}'])
            if info.returncode or info.stdout.strip()!='linux':
                raise RuntimeError('No accessible Linux Docker daemon.')
            if command(['docker','image','inspect',args.image]).returncode:
                raise RuntimeError('Requested local image absent. No build or pull attempted.')
            env={**os.environ,'LOCAL_IMAGE':args.image}
            # A unique project owns only this verifier's new disposable volume.
            project=f'semantic-verify-4b-{os.getpid()}'
            base=['docker','compose','--project-name',project,'-f',str(ROOT/'deploy/local/compose.verify.yaml')]
            if command([*base,'config','--quiet'],env=env).returncode:
                raise RuntimeError('Compose validation failed.')
            try:
                started=command([*base,'up','-d','--wait','--wait-timeout','90'],env=env,timeout=110)
                if started.returncode:raise RuntimeError('Disposable container failed health/startup checks.')
                cid=command([*base,'ps','-q','app'],env=env).stdout.strip()
                watched=['api.py','config.py','demo_limits.py','workspaces.py','storage.py','safe_fetch.py']
                code='import pathlib,hashlib,json; print(json.dumps({n:hashlib.sha256((pathlib.Path("/app/semantic_analyser")/n).read_bytes()).hexdigest() for n in '+repr(watched)+'}))'
                checked=command(['docker','exec',cid,'python','-c',code])
                expected={n:hashlib.sha256((ROOT/'semantic_analyser'/n).read_bytes()).hexdigest() for n in watched}
                if checked.returncode or json.loads(checked.stdout)!=expected:
                    raise RuntimeError('Local image application sources differ from this checkout; no verification claim.')
                def browser():
                    return urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
                a,b=browser(),browser();origin='http://127.0.0.1:8020'
                def call(client,path,data=None,revision=None):
                    headers={'X-Workspace-Request':'true','Content-Type':'application/json'}
                    if revision:headers['If-Match']=revision
                    r=urllib.request.Request(origin+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
                    with client.open(r,timeout=10) as response:return json.load(response)
                for client in [a,b]:call(client,'/api/session')
                ar=call(a,'/api/articles');br=call(b,'/api/articles')
                call(a,'/api/reviews',{'source_id':'A01','target_id':'A02','decision':'useful'},ar['collection_revision'])
                assert len(call(a,'/api/reviews')['reviews'])==1 and not call(b,'/api/reviews')['reviews']
                restarted=command([*base,'restart','app'],env=env,timeout=30)
                if restarted.returncode:raise RuntimeError('Container restart failed.')
                for _ in range(30):
                    try:
                        call(a,'/health');break
                    except OSError:time.sleep(.5)
                assert len(call(a,'/api/reviews')['reviews'])==1
                assert not call(b,'/api/reviews')['reviews']
                cid=command([*base,'ps','-q','app'],env=env).stdout.strip()
                for _ in range(40):
                    inspected=json.loads(command(['docker','inspect',cid]).stdout)[0]
                    if inspected['State']['Health']['Status']=='healthy':break
                    time.sleep(1)
                host=inspected['HostConfig']
                assert '--no-proxy-headers' in inspected['Config']['Cmd']
                assert host['Memory']==4*1024**3 and host['NanoCpus']==2*10**9 and host['PidsLimit']==128
                assert inspected['State']['Health']['Status']=='healthy'
                result.update(status='passed',linux_container_verified=True,
                              checks=['current application source hashes','cookie visitor separation','review write/restart persistence','configured cgroup limits','app health'],
                              not_exercised=['actual cgroup exhaustion','HTTPS/Caddy path','outbound kernel firewall','real model startup'])
            finally:
                stopped=command([*base,'down','--volumes','--remove-orphans'],env=env,timeout=40)
                if stopped.returncode:raise RuntimeError('Disposable project cleanup failed; inspect its named project.')
        except (RuntimeError,subprocess.TimeoutExpired,AssertionError,OSError,ValueError) as error:
            result.update(status='blocked_or_failed',reason=str(error))
    (out/'docker-verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
    return 0 if result['status'] in {'passed','skipped'} else 1


if __name__=='__main__':raise SystemExit(main())
