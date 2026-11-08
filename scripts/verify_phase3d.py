"""One milestone suite plus preservation checks; never repeats model evaluation."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/phase3d'


def capture():
    OUT.mkdir(parents=True,exist_ok=True)
    guard=OUT/'preservation-before.json'
    if not guard.exists():
        paths=[p for folder in ['data','labels','benchmarks','infra','deploy'] for p in (ROOT/folder).rglob('*') if p.is_file() and '.terraform' not in p.parts]
        paths += [p for p in (ROOT/'runtime').rglob('*') if p.is_file() and 'phase3d' not in p.parts and ('.sqlite3' in p.name or 'phase3c' in p.parts)]
        paths += list((ROOT/'docs').glob('*verification.json'))
        guard.write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2),encoding='utf-8')
    return json.loads(guard.read_text())


def main():
    protected=capture()
    env={**os.environ,'DATABASE_PATH':str(OUT/'bootstrap.sqlite3'),'WORKSPACE_MODE':'local',
         'APP_ENV':'development','APP_PASSWORD':'','PRELOAD_MODEL':'false','ENABLE_WEBSITE_FETCH':'false',
         'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','PYTHONDONTWRITEBYTECODE':'1'}
    suite=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider','--basetemp',str(OUT/'final-tests')],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (OUT/'tests.log').write_text(suite.stdout+suite.stderr,encoding='utf-8')
    print(suite.stdout,flush=True)
    assert suite.returncode==0,'See runtime/phase3d/tests.log'
    match=re.search(r'(\d+) passed(?:, (\d+) skipped)? in ([0-9.]+)s',suite.stdout);assert match
    changed=[p for p,h in protected.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    assert not changed,changed
    assert subprocess.check_output(['git','diff','34b613d','--','semantic_analyser','web'],cwd=ROOT)==b''
    analysis=json.loads((OUT/'analysis-results.json').read_text())
    assert analysis['model_constructions']==1 and analysis['network_attempts']==0
    result={'baseline_commit':'34b613d','phase':'3D','suite':{'passed':int(match[1]),'skipped':int(match[2]or 0),'seconds':float(match[3])},
            'protected_files_checked':len(protected),'changed_protected_files':changed,
            'application_source_changed':False,'saved_source_pages_refetched':False,'model_constructions':1,
            'model_evaluation_repeated_by_verifier':False,'exact_evidence_checks':analysis['exact_evidence_checks'],
            'independently_reviewed_judgements':0,'production_readiness_claimed':False}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
