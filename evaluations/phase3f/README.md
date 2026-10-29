# Phase 3F: screened mixed-review consolidation

`inputs/` preserves the supplied CSV bytes. They contain **14 reported user decisions
after AI screening**, not independent validation, plus **45 AI-assisted assessments**.
All independent attestations remain false. `results.json` contains validated coverage,
unresolved per-cutoff gaps and frozen ranking disagreements. No available human P@3/P@5
is manufactured from AI labels. `error-analysis.json` contains assistant interpretations
of 12 negative examples with original provenance and saved evidence hashes.

From the project root:

```powershell
.\.venv\Scripts\python.exe -B -m scripts.phase3f_evaluation
.\.venv\Scripts\python.exe -B -m pytest -q tests/test_phase3f_evaluation.py tests/test_phase3e_review.py
```

Use `--output <new-path.json>` to save instead of print; parent directory must exist and
existing files are protected. No downloads, inference, SQLite writes or packages needed.
Original Phase 3E schema/independent scorer remains strict; do not change false
attestations or discard the mixed file's provenance column to force compatibility.

See `docs/phase3f-evaluation.md` for scope, interpretation, measured coverage, error
patterns and proposed next experiment. Earlier provisional labels/results are unchanged.
