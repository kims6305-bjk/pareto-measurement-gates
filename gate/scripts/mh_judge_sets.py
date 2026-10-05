"""Set-dominance auto-judge (U9) — V1..V7 + ADDENDUM3 C13. Pure, 0 LLM calls.

Definitions (design §14.1, prereg §1; frozen):
  covers(FX, FY)    ⇔ ∀y∈FY ∃x∈FX: x ≻ y  or  x, y tied on every axis (CI overlap)
  dominates(FX, FY) ⇔ covers(FX, FY) and ∃x∈FX, y∈FY: x ≻ y
Point dominance and CI ties are `mh_front.dominates` / `mh_front.cmp_axis` (judgment
CI = ci_qid). Nothing here re-implements them.

Precedence (IMPL_NOTES D9): V6 > V5 > V4 > V1 > V2 > V7 > V3.
Outcomes the §14.2 table does not name (e.g. C2 neither covers nor is covered) are
reported as V3 with `table_gap=True` — the claim is not supported (conservative).

usage:
    python mh_judge_sets.py --cond C0 ARCHIVE FRONT_JSON --cond C1 ... --cond C2 ... \
        [--ic1-verdict mh_ic1_verdict.json] [--ci qid]
    python mh_judge_sets.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE / "scripts"))

import mh_front as mf  # noqa: E402


def _tied(x: dict, y: dict, ci_key: Optional[str]) -> bool:
    return all(mf.cmp_axis(x, y, a, ci_key) == 0 for a in mf.AXES)


def covers(fx: list[dict], fy: list[dict], ci_key: Optional[str]) -> bool:
    return all(any(mf.dominates(x, y, ci_key) or _tied(x, y, ci_key) for x in fx) for y in fy)


def set_dominates(fx: list[dict], fy: list[dict], ci_key: Optional[str]) -> bool:
    return covers(fx, fy, ci_key) and any(mf.dominates(x, y, ci_key) for x in fx for y in fy)


def judge(fronts: dict[str, list[dict]], stops: dict[str, list[str]],
          ci_key: Optional[str] = "ci_qid", ic1: Optional[str] = None) -> dict:
    """fronts: {"C0","C1","C2"} → final front records. stops: cond → triggered T-codes."""
    pool = {f"{c}:{i}": r for c, fr in fronts.items() for i, r in enumerate(fr)}
    for r in pool.values():
        mf.validate_axes(r, ci_key)
    mf.validate_comparability(pool)          # positional keys: same c000 in every front

    D = {(x, y): set_dominates(fronts[x], fronts[y], ci_key)
         for x in fronts for y in fronts if x != y}
    C = {(x, y): covers(fronts[x], fronts[y], ci_key)
         for x in fronts for y in fronts if x != y}
    ids = {c: sorted(r["candidate_id"] for r in fr) for c, fr in fronts.items()}
    gap = False
    if ic1 == "FAIL":
        v = "V6"
    elif any("T4" in stops.get(c, []) for c in ("C1", "C2")):   # C0 has no T4 (§12.1)
        v = "V5"
    elif D[("C0", "C2")] or D[("C1", "C2")]:
        v = "V4"
    elif D[("C2", "C0")] and D[("C2", "C1")]:
        v = "V1"
    elif D[("C2", "C0")] or D[("C2", "C1")]:
        v = "V2"
    elif all(ids[c] == [mf.BASELINE_ID] for c in fronts):
        v = "V7"
    else:
        v = "V3"
        gap = not (all(C.values()) and not any(D.values()))

    # ADDENDUM3 §2 — C13 primary test = C2 vs C1 only
    if ic1 == "FAIL":
        c13 = "not run (IC-1 FAIL)"
    elif any(t in stops.get(c, []) for c in ("C1", "C2") for t in ("T3", "T4")):
        c13 = "undecidable (T3/T4 early stop)"
    elif D[("C2", "C1")] and not D[("C1", "C2")]:
        c13 = "supported"
    elif D[("C1", "C2")]:
        c13 = "opposite direction"
    else:
        c13 = "rejected"
    return {"verdict": v, "table_gap": gap, "c13": c13,
            "set_dominates": {f"{x}>{y}": b for (x, y), b in sorted(D.items())},
            "covers": {f"{x}>{y}": b for (x, y), b in sorted(C.items())},
            "fronts": ids, "stops": stops, "ci": ci_key}


# ── selftest: hand-built fronts covering every V ─────────────────────────────────
def _rec(cid: str, r: float, p: float, w: float = 0.02) -> dict:
    return {"candidate_id": cid, "harness": {"model": "m"},
            "measurement": {"label_sheet_sha256": "a" * 64, "n_units": 55, "n_runs": 3},
            "objectives": {"recall": {"value": r, "ci_qid": [max(0, r - w), min(1, r + w)]},
                           "precision": {"value": p, "ci_qid": [max(0, p - w), min(1, p + w)]}}}


def selftest(verbose: bool = True) -> bool:
    base = _rec("c000", 0.5, 0.5)
    hi = _rec("c101", 0.8, 0.8)          # dominates base
    lo = _rec("c201", 0.2, 0.2)          # dominated by base
    tr = _rec("c301", 0.9, 0.1)          # trade-off vs base
    cases = {
        "V1": ({"C0": [base], "C1": [base], "C2": [hi]}, {}, None),
        "V2": ({"C0": [base], "C1": [hi], "C2": [hi, _rec("c302", 0.95, 0.05)]}, {}, None),
        "V3": ({"C0": [base], "C1": [_rec("c201", 0.51, 0.5)], "C2": [_rec("c301", .5, .51)]},
               {}, None),
        "V4": ({"C0": [hi], "C1": [base], "C2": [base]}, {}, None),
        "V5": ({"C0": [base], "C1": [base], "C2": [hi]}, {"C2": ["T4"]}, None),
        "V6": ({"C0": [base], "C1": [base], "C2": [hi]}, {}, "FAIL"),
        "V7": ({"C0": [base], "C1": [base], "C2": [base]}, {}, None),
    }
    ok = True
    for want, (fr, st, ic1) in cases.items():
        got = judge(fr, st, ic1=ic1)
        good = got["verdict"] == want and not got["table_gap"]
        ok &= good
        if verbose:
            print(f"  [{'PASS' if good else 'FAIL'}] {want}: got {got['verdict']} c13={got['c13']}")
    # V2 split: C2 dominates C1 only → C13 supported; table gap → V3*
    g = judge({"C0": [hi], "C1": [base], "C2": [hi]}, {})
    ok &= g["verdict"] == "V2" and g["c13"] == "supported"
    g = judge({"C0": [tr], "C1": [base], "C2": [lo]}, {})
    ok &= g["verdict"] == "V4" and g["c13"] == "opposite direction"
    g = judge({"C0": [tr], "C1": [tr], "C2": [_rec("c303", 0.1, 0.9)]}, {})
    ok &= g["verdict"] == "V3" and g["table_gap"] and g["c13"] == "rejected"
    if verbose:
        print(f"set-dominance judge selftest {'PASS' if ok else 'FAIL'}")
    return ok


def load_front(archive: Path, front_json: Path) -> tuple[list[dict], list[str]]:
    _, latest = mf.load_archive(archive)
    doc = json.loads(front_json.read_text(encoding="utf-8"))
    return [latest[i] for i in doc["front"]], doc.get("termination", {}).get("triggered", [])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cond", nargs=3, action="append", metavar=("COND", "ARCHIVE", "FRONT"))
    ap.add_argument("--ic1-verdict", default=None)
    ap.add_argument("--ci", choices=sorted(mf.CI_KEYS), default=mf.DEFAULT_CI)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return 0 if selftest() else 1
    conds = {c: (Path(ar), Path(fj)) for c, ar, fj in (a.cond or [])}
    if set(conds) != {"C0", "C1", "C2"}:
        ap.error("need --cond for exactly C0, C1, C2")
    fronts, stops = {}, {}
    for c, (ar, fj) in sorted(conds.items()):
        fronts[c], stops[c] = load_front(ar, fj)
    ic1 = (json.loads(Path(a.ic1_verdict).read_text(encoding="utf-8"))["verdict"]
           if a.ic1_verdict else None)
    print(json.dumps(judge(fronts, stops, mf.CI_KEYS[a.ci], ic1), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
