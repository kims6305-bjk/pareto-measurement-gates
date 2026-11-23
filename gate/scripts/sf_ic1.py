"""IC-1′ — c000 판정 결과의 결정론 열화 음성대조 (부속서5 §5). 추가 LLM 0콜.

  선택: id 마다 h = sha256(f"{IC1_SEED}|{id}"), int(h,16)/2**256 < r 인 id. 정답을 보지 않는다.
  n_over  : 고른 id 의 3판 판정 → INSUFFICIENT  (과검출)
  n_under : 고른 id 의 3판 판정 → SUPPORTED     (과소검출)
  n_both  : 고른 id 중 int(h[:8],16) 짝수 → INSUFFICIENT, 홀수 → SUPPORTED
  PASS ⇔ ① cmp_axis(c000, n_over, specificity)=+1 ② cmp_axis(c000, n_under, recall)=+1  (ci_qid)
  ③ dominates(c000, n_both) 는 참고값만 (부속서5 §9 추기3: 라벨 무관 혼합 열화는 구조적으로 지배 불가)

usage:
    MH_EXP=E2 python sf_ic1.py --power            # 측정 전 r 검정력 모의 (0콜)
    MH_EXP=E2 python sf_ic1.py --r 0.30           # c000 원자료 → mh_e2_ic1_verdict.json
    MH_EXP=E2 python sf_ic1.py --selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from multiprocessing import Pool
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE / "scripts"))

import mh_exp  # noqa: E402

if not mh_exp.E2:
    raise SystemExit("sf_ic1.py 는 E2 전용 — MH_EXP=E2 로 실행")

import mh_front as mf  # noqa: E402
import mh_objectives as mo  # noqa: E402

IC1_SEED = 20261124
LABELS = GATE / "scripts/sf300_label_set.json"
R_GRID = (0.15, 0.20, 0.25, 0.30, 0.35)   # 0.35 = 부속서5 §9 추기3
R_ADOPTED = 0.35
CELLS = [(rc, sp) for rc in (0.6, 0.75, 0.9) for sp in (0.75, 0.85, 0.95)]
N_SIM = 40
MIN_RATE = 0.90


def _h(uid: str) -> str:
    return hashlib.sha256(f"{IC1_SEED}|{uid}".encode()).hexdigest()


def picked(uid: str, r: float) -> bool:
    return int(_h(uid), 16) / 2 ** 256 < r


def degrade(maj: dict[str, str], mode: str, r: float) -> dict[str, str]:
    """maj: id → 판정(3판이 같은 값으로 바뀌므로 다수결 = 그 값)."""
    out = {}
    for uid, lab in maj.items():
        if not picked(uid, r):
            out[uid] = lab
        elif mode == "over":
            out[uid] = "INSUFFICIENT"
        elif mode == "under":
            out[uid] = "SUPPORTED"
        else:
            out[uid] = "INSUFFICIENT" if int(_h(uid)[:8], 16) % 2 == 0 else "SUPPORTED"
    return out


def record(cid: str, units: list) -> dict:
    ci = mo.bootstrap(units, "qid")
    return {"candidate_id": cid, "objectives": {
        a: {"value": mo._AXIS_FN[a](units), "ci_qid": ci[a]["ci"]} for a in mf.AXES}}


def verdict(labels: dict[str, str], maj: dict[str, str], r: float) -> dict:
    mk = lambda m: [mo.Unit(u, labels[u], m[u]) for u in sorted(m)]   # noqa: E731
    base = record("c000", mk(maj))
    over, under, both = (record(f"n_{k}", mk(degrade(maj, k, r))) for k in ("over", "under", "both"))
    c1 = mf.cmp_axis(base, over, "specificity", "ci_qid") == 1
    c2 = mf.cmp_axis(base, under, "recall", "ci_qid") == 1
    c3 = mf.dominates(base, both, "ci_qid")
    return {"r": r, "c1_over_specificity": c1, "c2_under_recall": c2, "c3_both_dominated": c3,
            "verdict": "PASS" if (c1 and c2) else "FAIL",   # ③ 참고값(추기3)
            "records": {x["candidate_id"]: x["objectives"] for x in (base, over, under, both)}}


def _synth(labels: dict[str, str], rc: float, sp: float, rng: random.Random) -> dict[str, str]:
    out = {}
    for u, h in sorted(labels.items()):
        if h == "S":
            out[u] = "INSUFFICIENT" if rng.random() > sp else "SUPPORTED"
        else:
            out[u] = ("CONTRADICTED" if h == "C" else "INSUFFICIENT") if rng.random() < rc else "SUPPORTED"
    return out


def _cell(args) -> dict:
    labels, rc, sp = args
    hits = {r: {"c12": 0, "c3": 0, "all": 0} for r in R_GRID}
    for k in range(N_SIM):
        maj = _synth(labels, rc, sp, random.Random(f"{IC1_SEED}|{rc}|{sp}|{k}"))
        for r in R_GRID:
            v = verdict(labels, maj, r)
            hits[r]["c12"] += v["c1_over_specificity"] and v["c2_under_recall"]
            hits[r]["c3"] += v["c3_both_dominated"]
            hits[r]["all"] += v["c1_over_specificity"] and v["c2_under_recall"] and v["c3_both_dominated"]
    return {"recall": rc, "specificity": sp,
            "rate": {str(r): {k: n / N_SIM for k, n in d.items()} for r, d in hits.items()}}


def power(labels: dict[str, str]) -> dict:
    with Pool() as pool:
        cells = pool.map(_cell, [(labels, rc, sp) for rc, sp in CELLS])
    worst = {str(r): {k: min(c["rate"][str(r)][k] for c in cells) for k in ("c12", "c3", "all")}
             for r in R_GRID}
    return {"seed": IC1_SEED, "n_sim": N_SIM, "cells": cells, "worst": worst,
            "smallest_r_c12": next((r for r in R_GRID if worst[str(r)]["c12"] >= MIN_RATE), None),
            "smallest_r_all": next((r for r in R_GRID if worst[str(r)]["all"] >= MIN_RATE), None)}


def selftest() -> bool:
    labels = {f"Q{i // 4:03d}-sf-x{i}": "S" if i % 2 else "C" for i in range(200)}
    perfect = {u: ("SUPPORTED" if h == "S" else "CONTRADICTED") for u, h in labels.items()}
    v = verdict(labels, perfect, 0.30)
    ok = v["verdict"] == "PASS"
    ok &= verdict(labels, perfect, 0.0)["verdict"] == "FAIL"           # 열화 0 → 구별 불가
    ok &= degrade(perfect, "over", 0.3) == degrade(perfect, "over", 0.3)   # 결정론
    sel = sum(picked(u, 0.3) for u in labels)
    ok &= 40 <= sel <= 80                                                # ≈ 0.3 × 200
    print(f"sf_ic1 selftest {'PASS' if ok else 'FAIL'} (selected {sel}/200 at r=0.3)")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--power", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--r", type=float, default=R_ADOPTED)
    a = ap.parse_args()
    if a.selftest:
        return 0 if selftest() else 1
    labels = mo.load_labels(LABELS)
    if a.power:
        res = power(labels)
        Path(GATE / "scripts/sf_ic1_power.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"worst": res["worst"], "smallest_r_c12": res["smallest_r_c12"],
                          "smallest_r_all": res["smallest_r_all"]}, indent=1))
        return 0
    if a.r != R_ADOPTED:
        raise SystemExit(f"r={a.r} — 부속서5 §9 추기3 커밋값 {R_ADOPTED} 만 허용")
    per, files = mo.load_runs([str(GATE / "scripts/mh_e2_c000_run*.jsonl")])
    mo.validate_run_ledger(per, labels, "c000")
    maj = {u.id: u.maj for u in mo.build_units(per, labels)}
    v = verdict(labels, maj, a.r) | {"raw_files": files, "ic1_seed": IC1_SEED}
    Path(GATE / "scripts/mh_e2_ic1_verdict.json").write_text(
        json.dumps(v, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(v["verdict"], {k: v[k] for k in ("c1_over_specificity", "c2_under_recall", "c3_both_dominated")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
