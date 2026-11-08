"""Stream image layers without extracting them or storing a multi-GB archive.

Checks known canaries in every layer, including files later deleted/whiteouted.
This is evidence for named probes, not a universal secret-detection guarantee.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tarfile

CANARY = b'PHASE4E_SYNTHETIC_BUILD_SECRET_CANARY'


def scan_layer(layer, token=CANARY):
    found=[];sensitive=[];files=0
    for member in layer:
        if not member.isfile():continue
        files+=1
        name=member.name.removeprefix('./').lstrip('/')
        known_root_secret=name in {'.env','release.env','root/.aws/credentials','root/.docker/config.json','root/.netrc'}
        if not Path(name).name.startswith('.wh.') and (known_root_secret or (name.startswith(('app/','context/','opt/huggingface/')) and (
                name.endswith(('.env','.key','.sqlite3','/token')) or '/.git/' in name or name.endswith('/release.env')))):
            sensitive.append(name)
        handle=layer.extractfile(member);tail=b''
        while True:
            chunk=handle.read(1024*1024)
            if not chunk:break
            if token in tail+chunk:found.append(name)
            tail=chunk[-(len(token)-1):]
    return {'files':files,'canary_files':sorted(set(found)),'sensitive_first_party_paths':sensitive}


def scan_archive(stream):
    layers=[]
    with tarfile.open(fileobj=stream,mode='r|') as outer:
        for entry in outer:
            if not entry.isfile():continue
            try:
                # Even a tiny gzip blob can contain a secret-bearing filesystem
                # layer. Do not infer filesystem type from compressed byte size.
                with tarfile.open(fileobj=outer.extractfile(entry),mode='r|*') as layer:
                    result=scan_layer(layer);result['archive_entry']=entry.name;layers.append(result)
            except tarfile.ReadError:
                pass  # OCI config/manifest blobs, not filesystem layers.
    return layers


def audit(image):
    config=json.loads(subprocess.check_output(['docker','image','inspect',image],encoding='utf-8'))[0]
    # Image config defaults contain no deployment credentials; runtime environment
    # and mounted workspaces are separate and remain visible to Docker operators.
    forbidden=['APP_PASSWORD=','SECRET_KEY=','AWS_SECRET_ACCESS_KEY=','HF_TOKEN=']
    assert not any(v.startswith(k) and v[len(k):] for v in config['Config'].get('Env',[]) for k in forbidden)
    process=subprocess.Popen(['docker','image','save',image],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        layers=scan_archive(process.stdout)
        assert process.wait(timeout=10)==0
    finally:
        if process.poll() is None:process.kill();process.wait()
    assert len(layers)==len(config['RootFS']['Layers']),'Incomplete or unexpected filesystem layer coverage'
    return {'image':image,'id':config['Id'],'layer_count':len(layers),'files':sum(v['files'] for v in layers),
            'canary_files':[p for v in layers for p in v['canary_files']],
            'sensitive_first_party_paths':[p for v in layers for p in v['sensitive_first_party_paths']],
            'nonempty_secret_defaults':0,'rootfs_diff_ids':config['RootFS']['Layers'],
            'limitations':'Named canary/path/default-environment checks; does not prove arbitrary unknown strings are not credentials. Backend source and model remain readable to image holders.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('image');parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();result=audit(args.image);args.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'rootfs_diff_ids'}}))
    raise SystemExit(bool(result['canary_files'] or result['sensitive_first_party_paths']))
