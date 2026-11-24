"""부속서10 — 구조가 다른 후보 c401(조건 분해 대조표) 1개를 c000 과 비교.
  MH_EXP=E6P python sfk_e10.py register   # E6P 원장에 c401 등록(0콜)
  MH_EXP=E6  python sfk_e10.py register   # E6  원장에 c401 등록(0콜)
  MH_EXP=E6P python sfk_e10.py pilot      # §3 안전 게이트: c401 파일럿 3판 두 축 ≥ 0.70
  MH_EXP=E6  python sfk_e10.py verdict    # §4 c401 − c000, 95% 주판정 + 97.5% 민감도
c000 본측정 3판(부속서9 추기4)은 재사용한다 — 다시 돌리지 않는다.
"""
import json
import sys
from pathlib import Path

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
from mh_exp import EXP  # noqa: E402

CID = "c401"
# 부속서10 §2 — JUDGE 표면 5개 전면 교체(preamble 가드 유지). 문구는 이 커밋에서 동결.
PARTS = {
    "task": "검증할 주장을 먼저 독립된 조건(주체·대상·요건·예외·결과)으로 쪼개고, "
            "조건마다 근거에서 그 내용을 직접 말하는 문장을 찾아 대조하라.\n",
    "def_supported": "- SUPPORTED: 모든 조건이 근거 문장에 명시돼 있거나 그 문장에서 직접 도출된다.\n",
    "def_contradicted": "- CONTRADICTED: 어느 한 조건이라도 근거 문장이 반대로 진술한다"
                        "(긍정↔부정, 허용↔금지, 포함↔제외, 이상↔미만 등).\n",
    "def_insufficient": "- INSUFFICIENT: 반대 진술은 없지만 한 조건이라도 근거에서 찾을 수 없다. "
                        "회계적으로 옳은 주장이라도 제공된 근거 범위 밖이면 INSUFFICIENT다.\n\n",
    "closing": "회계 지식이나 기준서 기억으로 판정하지 마라. 근거의 서술이 네가 아는 내용과 달라도 근거를 따른다. "
               "출력 JSON 맨 앞에 \"checks\" 키를 두고 '조건1=근거 요지|없음|반대; 조건2=...' 형식으로 "
               "대조 결과를 적은 뒤 label 을 정하라. checks 안에는 중괄호를 쓰지 마라.",
}


def harness() -> dict:
    import mh_propose as P
    h = P.harness_from_surfaces({f"JUDGE.{k}": v for k, v in {**P.DEFAULT_PARTS, **PARTS}.items()},
                                diff="조건 분해→문장 대조→라벨 (판정 절차 구조 변경)",
                                edited=[f"JUDGE.{k}" for k in PARTS])
    h["model"] = "claude-haiku-5-5"
    return h


def register() -> None:
    from instrument_check_run import load_units
    from mh_run_candidate import archive_path, prompt_sha256, resolve_builder
    assert EXP in ("E6P", "E6")
    out = archive_path("C2")
    if any(json.loads(l)["candidate_id"] == CID for l in out.open(encoding="utf-8")):
        raise SystemExit(f"{out.name} 에 {CID} 이미 있음")
    h = harness()
    fn, kw, _ = resolve_builder(h)
    units = load_units()
    h["prompt_sha256"] = prompt_sha256(fn, kw, units)
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"candidate_id": CID, "origin": "부속서10 §2 신규", "harness": h,
                            "status": "registered"}, ensure_ascii=False) + "\n")
    print(out.name, CID, "등록, 단위", len(units), h["prompt_sha256"][:12])


def pilot() -> None:
    import mh_objectives as M
    from sfk_e5 import _units
    assert EXP == "E6P"
    us = list(_units(CID).values())
    r, s = M.recall_of(us), M.specificity_of(us)
    ok = r >= 0.70 and s >= 0.70
    print(f"{CID} 파일럿: recall {r:.3f} specificity {s:.3f} UNRESOLVED {M.counts(us)['n_unresolved']} → "
          + ("PASS(본측정 진행)" if ok else "FAIL(본측정 중단·기록)"))
    sys.exit(0 if ok else 1)


def verdict() -> None:
    from sfk_e5 import _units, classify, paired
    assert EXP == "E6"
    r, n = paired(CID, _units("c000"), _units(CID))
    print(f"{CID} − c000 (군집 {n}): " + "; ".join(
        f"{ax} Δ {d*100:+.1f}%p 95%[{lo*100:+.1f}, {hi*100:+.1f}] 97.5%[{l2*100:+.1f}, {h2*100:+.1f}]"
        for ax, (d, lo, hi, l2, h2) in r.items()))
    print(f"주판정(95%): {classify(r, 1, 2)}  ·  민감도(97.5%): {classify(r, 3, 4)}")


if __name__ == "__main__":
    {"register": register, "pilot": pilot, "verdict": verdict}[sys.argv[1]]()
