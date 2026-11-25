"""부속서8 E5 판정 규칙(§3)·짝 부트스트랩·SF-K 생성기 검사. 0콜."""
import subprocess
import sys
from pathlib import Path

S = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(S))
import mh_objectives as M  # noqa: E402
import sfk_e5 as E  # noqa: E402
from sfk_build_label_set import SRC  # noqa: E402
import pytest  # noqa: E402

P = "CONTRADICTED"


def _units(n, flag_problem, flag_ok):
    us = {}
    for k in range(n):
        us[f"K1000p{k}-S"] = M.Unit(f"K1000p{k}-S", "S", P if flag_ok(k) else "SUPPORTED")
        us[f"K1000p{k}-C"] = M.Unit(f"K1000p{k}-C", "C", P if flag_problem(k) else "SUPPORTED")
    return us


def test_classify():
    r = lambda *ax: {f"a{i}": (0, lo, hi, lo, hi) for i, (lo, hi) in enumerate(ax)}
    assert E.classify(r((.01, .05), (.02, .04)), 1, 2) == "지배"
    assert E.classify(r((-.05, -.01), (-.04, -.02)), 1, 2) == "열위"
    assert E.classify(r((.01, .05), (-.04, -.02)), 1, 2) == "맞바꿈"
    assert E.classify(r((-.01, .05), (.02, .04)), 1, 2) == "판정 불가"


def test_paired_identical_is_zero_and_better_is_positive():
    base = _units(200, lambda k: k % 2 == 0, lambda k: k % 10 == 0)
    same, n = E.paired("x", base, base)
    assert n == 200 and all(v[0] == 0 and v[1] == 0 == v[2] for v in same.values())
    better = _units(200, lambda k: k % 2 == 0 or k % 3 == 0, lambda k: k % 10 == 0)
    r, _ = E.paired("x", base, better)
    assert r["recall"][1] > 0 and r["specificity"][0] == 0           # recall 만 확정 개선
    assert E.classify(r, 1, 2) == "판정 불가"                          # 한 축만 개선 → 지배 아님


@pytest.mark.skipif(not any(SRC.glob("*.md")), reason="K-IFRS 원문 코퍼스(공개 레포 밖, 로컬 전용)가 없어 재생성 검사 불가")
def test_sfk_generator_reproducible():
    r = subprocess.run([sys.executable, str(S / "sfk_build_label_set.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_sfk_v2_filters():
    """추기 1: 검수에서 나온 비문 유형이 문제집에 다시 들어오지 않는다."""
    import json
    import re
    for split in ("pilot", "main"):
        for u in json.loads((S / f"sfk_{split}.json").read_text(encoding="utf-8")):
            assert not re.match(r"^(따라서|그러나|이러한|또한|이 경우)", u["claim_text"]), u["id"]
            assert not (u["kind"] == "C" and re.search(r"(때문|것)이 아니다\.$", u["claim_text"])), u["id"]
            assert not re.match(r"^(예를 들어|예컨대|이 개정)", u["claim_text"]), u["id"]          # 추기 2
            assert not re.search(r"때문이(다|\s*아니다)\.$", u["claim_text"]), u["id"]
            if u["kind"] == "C":
                assert not re.search(r"(하고|하며|거나|도록),? ", u["source"]["sentence"]), u["id"]
