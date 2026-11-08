"""Phase 3A regression checks using only local network fixtures/offline models.

The Phase 2B real-model verifier is copied with explicit output/root-path overrides
so its original evidence and disposable databases are not opened or overwritten.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runtime/phase3a"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    guard = OUT / "preservation-before.json"
    if not guard.exists():
        paths = [p for base in ["data", "labels", "benchmarks", "web", "infra", "deploy"]
                 for p in (ROOT / base).rglob("*") if p.is_file() and ".terraform" not in p.parts]
        paths += [p for p in (ROOT / "runtime").rglob("*.sqlite3*") if p.is_file() and "phase3a" not in p.parts]
        paths += [ROOT / name for name in ["docs/phase2a-verification.json", "docs/phase2b-verification.json"]]
        guard.write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in paths}, indent=2), encoding="utf-8")
    environment = {**os.environ, "DATABASE_PATH": str(OUT / "bootstrap.sqlite3"), "WORKSPACE_MODE": "local",
                   "APP_ENV": "development", "APP_PASSWORD": "", "PRELOAD_MODEL": "false",
                   "ENABLE_WEBSITE_FETCH": "false", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                   "PYTHONDONTWRITEBYTECODE": "1"}
    tests = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                            "--basetemp", str(OUT / "verification-tests"), "--junitxml", str(OUT / "tests.xml")],
                           cwd=ROOT, env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (OUT / "tests.log").write_text(tests.stdout + tests.stderr, encoding="utf-8")
    print(tests.stdout, flush=True)
    if tests.returncode:
        raise RuntimeError("Automated tests failed; see runtime/phase3a/tests.log")
    summary = re.search(r"(\d+) passed(?:, (\d+) skipped)? in ([0-9.]+)s", tests.stdout)
    if not summary:
        raise RuntimeError("Could not parse test summary")
    source_path = ROOT / "scripts/verify_phase2b.py"
    source = source_path.read_text(encoding="utf-8")
    overrides = {
        'ROOT = Path(__file__).resolve().parents[1]': f'ROOT = Path({str(ROOT)!r})',
        'OUT = ROOT / "runtime/phase2b/real"': 'OUT = ROOT / "runtime/phase3a/real"',
        'ROOT / "runtime/phase2b/preservation-before.json"': 'ROOT / "runtime/phase3a/preservation-before.json"',
    }
    for before, after in overrides.items():
        if before not in source:
            raise RuntimeError("Historical verifier changed; review isolation overrides before execution")
        source = source.replace(before, after)
    isolated = OUT / "isolated_real_regression.py"
    isolated.write_text(source, encoding="utf-8")
    real = subprocess.run([sys.executable, "-B", str(isolated)], cwd=ROOT, env=environment,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    (OUT / "real.log").write_text(real.stdout + real.stderr, encoding="utf-8")
    if real.returncode:
        raise RuntimeError("Real-model/browser regression failed; see runtime/phase3a/real.log")
    syntax = subprocess.run(["node", "--check", "web/app.js"], cwd=ROOT, capture_output=True, text=True)
    assert syntax.returncode == 0
    protected = json.loads(guard.read_text(encoding="utf-8"))
    changed = [name for name, digest in protected.items() if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    assert not changed, changed
    result = {
        "baseline_commit": "6df9b1c", "phase": "3A", "verification_date": "2026-10-28 Australia/Sydney",
        "automated_suite": {"passed": int(summary[1]), "skipped": int(summary[2] or 0), "seconds": float(summary[3])},
        "network_scope": "Controlled loopback HTTP/TLS fixtures, mocked public DNS/transport; no public websites fetched",
        "dns_worker": "Numeric loopback lookup and a deliberately stalled isolated subprocess; no external DNS required",
        "real_regression_source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "real_regression_output": json.loads((OUT / "real/results.json").read_text(encoding="utf-8")),
        "preserved_files": len(protected), "changed_protected_files": changed,
        "javascript_syntax": "passed", "public_deployment": False, "production_readiness_claimed": False,
    }
    (OUT / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"suite": result["automated_suite"], "preserved_files": len(protected), "real_regression": "passed"}, indent=2))


if __name__ == "__main__":
    main()
