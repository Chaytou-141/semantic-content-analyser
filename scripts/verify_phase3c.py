"""Final Phase 3C suite/UI checks; real-site observations are separate and explicit."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runtime/phase3c'


def capture_preservation():
    guard = OUT / 'preservation-before.json'
    if guard.exists():
        return
    paths = [p for folder in ['data', 'labels', 'benchmarks', 'infra', 'deploy']
             for p in (ROOT / folder).rglob('*') if p.is_file() and '.terraform' not in p.parts]
    paths += [p for p in (ROOT / 'runtime').rglob('*.sqlite3*') if p.is_file() and 'phase3c' not in p.parts]
    paths += list((ROOT / 'docs').glob('*verification.json'))
    guard.write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in paths}, indent=2), encoding='utf-8')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    capture_preservation()
    environment = {**os.environ, 'DATABASE_PATH': str(OUT / 'bootstrap.sqlite3'), 'WORKSPACE_MODE': 'local',
                   'APP_ENV': 'development', 'APP_PASSWORD': '', 'ENABLE_WEBSITE_FETCH': 'false',
                   'PRELOAD_MODEL': 'false', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                   'PYTHONDONTWRITEBYTECODE': '1'}
    suite = subprocess.run([sys.executable, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                            '--basetemp', str(OUT / 'final-tests')], cwd=ROOT, env=environment,
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
    (OUT / 'tests.log').write_text(suite.stdout + suite.stderr, encoding='utf-8')
    print(suite.stdout, flush=True)
    assert suite.returncode == 0, 'See runtime/phase3c/tests.log'
    summary = re.search(r'(\d+) passed(?:, (\d+) skipped)? in ([0-9.]+)s', suite.stdout)
    assert summary
    # Reuse existing focused UI assertions without opening/rewriting Phase 3B evidence/DBs.
    source = (ROOT / 'scripts/verify_phase3b.py').read_text(encoding='utf-8')
    overrides = {'ROOT = Path(__file__).resolve().parents[1]': f'ROOT = Path({str(ROOT)!r})',
                 "OUT = ROOT / 'runtime/phase3b'": "OUT = ROOT / 'runtime/phase3c/browser'"}
    for old, new in overrides.items():
        assert old in source, 'Historical verifier changed; review isolation overrides.'
        source = source.replace(old, new)
    helper = OUT / 'isolated_ui_verifier.py'
    helper.write_text(source, encoding='utf-8')
    ui = subprocess.run([sys.executable, '-B', str(helper), '--ui-only'], cwd=ROOT, env=environment,
                        capture_output=True, text=True, encoding='utf-8', errors='replace')
    (OUT / 'browser.log').write_text(ui.stdout + ui.stderr, encoding='utf-8')
    assert ui.returncode == 0, 'See runtime/phase3c/browser.log'
    subprocess.run(['node', '--check', 'web/app.js'], cwd=ROOT, check=True)
    protected = json.loads((OUT / 'preservation-before.json').read_text())
    changed = [p for p, digest in protected.items() if hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != digest]
    assert not changed, changed
    result = {'baseline_commit': '278049d', 'phase': '3C',
              'suite': {'passed': int(summary[1]), 'skipped': int(summary[2] or 0), 'seconds': float(summary[3])},
              'focused_ui': json.loads((OUT / 'browser/ui-verification.json').read_text()),
              'javascript_syntax': 'passed', 'protected_files_checked': len(protected),
              'changed_protected_files': changed, 'minilm_weights_loaded': False,
              'historical_benchmark_rerun': False, 'production_readiness_claimed': False}
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'suite': result['suite'], 'focused_ui': 'passed', 'protected_files_checked': len(protected)}))


if __name__ == '__main__':
    main()
