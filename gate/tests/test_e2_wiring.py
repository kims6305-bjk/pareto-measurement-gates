"""E2(부속서5) 배선 검사 — MH_EXP=E2 하위 프로세스로 돌려 E1 기본값을 건드리지 않는다."""
import os
import subprocess
import sys
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "MH_EXP": "E2"}

PROBE = r"""
import sys; sys.path.insert(0, 'scripts')
import instrument_check_run as icr, phase3_build_prompts as p3, mh_front as mf, mh_objectives as mo
import mh_propose as mp, mh_search as ms, mh_guard as mg
u = icr.load_units()
assert len(u) == 300 and all(x['human'] is None and x['siblings'] == [] for x in u)
pr = p3.build(u[0], with_siblings=True)
assert u[0]['claim_citation'] not in pr and '(인용:' not in pr, 'E2 프롬프트에 인용 번호'
assert p3.CLAUDE_MODEL == mf.MODEL_FIXED == mp.PROPOSER_MODEL == 'claude-opus-5-5'
assert mf.AXES == mo.AXES == ('recall', 'specificity')
assert (mf.CALL_BUDGET, ms.CALLS_PER_CANDIDATE) == (9000, 900)
assert mg.MANIFEST.name == 'mh_e2_manifest.json' and mg.LABEL_JSON.name == 'sf300_label_set.json'
print('E2 wiring OK')
"""


def _run(*args):
    return subprocess.run([sys.executable, *args], cwd=GATE, env=ENV, capture_output=True, text=True)


def test_e2_wiring():
    r = _run("-c", PROBE)
    assert r.returncode == 0, r.stderr


def test_e2_selftests():
    for script in ("scripts/mh_objectives.py", "scripts/sf_ic1.py"):
        r = _run(script, "--selftest")
        assert r.returncode == 0, (script, r.stdout[-500:], r.stderr[-500:])
