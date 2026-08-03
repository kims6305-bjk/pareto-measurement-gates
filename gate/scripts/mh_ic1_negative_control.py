#!/usr/bin/env python3
"""IC-1 — precision 축 판별력 네거티브 컨트롤 (330콜).

정본: `gate/PARETO_META_HARNESS_DESIGN.md` §8.2 게이트 IC-1.
  - c_neg_loose : JUDGE 지시문에서 INSUFFICIENT **정의 1줄 삭제** → 과소검출 기대
  - c_neg_strict: "의심되면 INSUFFICIENT" **1문장 추가** → 과검출 기대
  - 판정(사전 고정): c_neg_strict 의 precision 이 c000 보다 **ci_qid 비겹침으로
    낮아야** PASS (§4.3 N2 — CI 가 겹치면 그 축은 동률).
  - FAIL 시: precision 축 폐기 → §3.6 축 재선정 + 새 사전 선언 커밋.
    파레토 탐색은 시작하지 않는다 (V6).

🔴 변인 통제: 두 후보는 JUDGE 문자열 외에 c000 과 어떤 차이도 없다
   (같은 빌더 build(), 같은 with_siblings=True, 같은 모델, 같은 55 units).
   원문 앵커 문자열이 phase3_build_prompts.JUDGE 에서 사라지면 즉시 중단
   (드리프트 가드 — 조용히 다른 실험이 되는 것을 막는다).
🔴 측정 원자료는 mh_ic1_<cid>_run{1,2,3}.jsonl — resume 가능·fail-closed
   (mh_run_candidate.py 와 같은 규약). 채점은 mh_objectives.py CLI 재사용.

usage:
    python mh_ic1_negative_control.py --measure           # 330콜 측정(재개 가능)
    python mh_ic1_negative_control.py --score             # 채점 + IC-1 판정 (0콜)
    python mh_ic1_negative_control.py --measure --score   # 연속 실행
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE / "scripts"))

import phase3_build_prompts as p3  # noqa: E402
from instrument_check_run import call, load_units  # noqa: E402

RUNS = ("run1", "run2", "run3")
LABELS = GATE / "scripts/phase1_human_label_sheet.xlsx"
C000_OBJ = GATE / "scripts/mh_c000_objectives.json"

# --- JUDGE 변형 (앵커 문자열 실측 후 수술) ---------------------------------
_INSUFF_DEF = ("- INSUFFICIENT: 근거만으로는 확인할 수 없다. 회계적으로 옳은 주장이라도 "
               "제공된 근거 범위 밖이면 INSUFFICIENT다.\n")
_TAIL_ANCHOR = "오직 제공된 근거가 주장을 지지하는지만 본다."
_STRICT_ADD = " 조금이라도 의심되면 INSUFFICIENT를 선택하라."


def judge_variant(cid: str) -> str:
    base = p3.JUDGE
    if cid == "c_neg_loose":
        if _INSUFF_DEF not in base:
            raise SystemExit("드리프트: INSUFFICIENT 정의 앵커가 JUDGE 에 없다")
        return base.replace(_INSUFF_DEF, "", 1)
    if cid == "c_neg_strict":
        if _TAIL_ANCHOR not in base:
            raise SystemExit("드리프트: JUDGE 말미 앵커가 없다")
        return base.replace(_TAIL_ANCHOR, _TAIL_ANCHOR + _STRICT_ADD, 1)
    raise SystemExit(f"unknown cid: {cid}")


def build_prompt(cid: str, unit: dict) -> str:
    """p3.build 재사용 — JUDGE 만 임시 교체(단일 변인)."""
    orig = p3.JUDGE
    p3.JUDGE = judge_variant(cid)
    try:
        return p3.build(unit, with_siblings=True)
    finally:
        p3.JUDGE = orig


def measure(cid: str) -> None:
    units = load_units()
    psha = hashlib.sha256(build_prompt(cid, units[0]).encode()).hexdigest()
    print(f"[{cid}] prompt_sha={psha[:12]}… units={len(units)}")
    for run in RUNS:
        out = GATE / f"scripts/mh_ic1_{cid}_{run}.jsonl"
        done = set()
        if out.exists():
            for line in out.read_text(encoding="utf-8").splitlines():
                try:
                    done.add(json.loads(line)["id"])
                except (json.JSONDecodeError, KeyError):
                    pass
        todo = [u for u in units if u["id"] not in done]
        print(f"{cid}/{run}: 대상 {len(units)}, 완료 {len(done)}, 남은 {len(todo)}")
        n = 0
        with open(out, "a", encoding="utf-8") as f:
            for u in todo:
                label, rationale = call(build_prompt(cid, u))
                n += 1
                f.write(json.dumps({
                    "id": u["id"], "run": run, "label": label,
                    "rationale": rationale, "human": u["human"],
                    "candidate": cid, "prompt_sha256": psha,
                }, ensure_ascii=False) + "\n")
                f.flush()
                if n % 10 == 0 or n == len(todo):
                    print(f"[{n}/{len(todo)}] {u['id']} human={u['human']} -> {label}",
                          flush=True)
                time.sleep(0.2)
        print(f"DONE {cid}/{run} -> {out.name}")


def score() -> int:
    objs = {}
    for cid in ("c_neg_loose", "c_neg_strict"):
        out = GATE / f"scripts/mh_ic1_{cid}_objectives.json"
        r = subprocess.run(
            [sys.executable, str(GATE / "scripts/mh_objectives.py"),
             "--candidate-id", cid,
             "--runs", str(GATE / f"scripts/mh_ic1_{cid}_run*.jsonl"),
             "--labels", str(LABELS), "--out", str(out)],
            capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
        if r.returncode != 0:
            print(f"채점 실패: {cid}", file=sys.stderr)
            return 2
        objs[cid] = json.loads(out.read_text(encoding="utf-8"))

    c000 = json.loads(C000_OBJ.read_text(encoding="utf-8"))
    p000 = c000["objectives"]["precision"]
    p_str = objs["c_neg_strict"]["objectives"]["precision"]
    p_loo = objs["c_neg_loose"]["objectives"]["precision"]

    # 판정: c_neg_strict precision ci_qid 상한 < c000 precision ci_qid 하한
    strict_hi = p_str["ci_qid"][1] if p_str["ci_qid"] else None
    c000_lo = p000["ci_qid"][0] if p000["ci_qid"] else None
    ok = (strict_hi is not None and c000_lo is not None and strict_hi < c000_lo)

    verdict = {
        "gate": "IC-1",
        "criterion": "c_neg_strict.precision ci_qid 비겹침으로 c000 보다 낮음 (§8.2 사전 고정)",
        "c000_precision": p000,
        "c_neg_strict_precision": p_str,
        "c_neg_loose_precision": p_loo,
        "c_neg_strict_recall": objs["c_neg_strict"]["objectives"]["recall"],
        "c_neg_loose_recall": objs["c_neg_loose"]["objectives"]["recall"],
        "strict_ci_hi": strict_hi, "c000_ci_lo": c000_lo,
        "verdict": "PASS" if ok else "FAIL",
    }
    out = GATE / "scripts/mh_ic1_verdict.json"
    out.write_text(json.dumps(verdict, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(verdict, ensure_ascii=False, indent=1))
    print(f"\nIC-1 {verdict['verdict']} — saved: {out.name}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--score", action="store_true")
    a = ap.parse_args()
    if not (a.measure or a.score):
        ap.error("--measure 그리고/또는 --score")

    # 가드 (INV-2·INV-3)
    r = subprocess.run([sys.executable, str(GATE / "scripts/mh_guard.py")],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip(), file=sys.stderr)
        return r.returncode

    if a.measure:
        for cid in ("c_neg_loose", "c_neg_strict"):
            measure(cid)
    if a.score:
        return score()
    return 0


if __name__ == "__main__":
    sys.exit(main())
