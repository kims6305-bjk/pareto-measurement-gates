"""E6P 중간 열람(판정 무관): 완료된 팔만 축·유형별 검출률. usage: MH_EXP=E6P python sfk_e6_peek.py"""
import json
import sys
from pathlib import Path

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
import mh_objectives as M  # noqa: E402

lab = M.load_labels(S / "sfk4_pilot.json")
kind = {u["id"]: u["kind"] for u in json.loads((S / "sfk4_pilot.json").read_text(encoding="utf-8"))}
for f in sorted(S.glob("mh_e6p_*run*.jsonl")):
    got = {json.loads(l)["id"]: json.loads(l)["label"] for l in f.open(encoding="utf-8")}
    us = [M.Unit(i, lab[i], got[i]) for i in sorted(got)]
    by = {}
    for u in us:
        ok = u.is_flagged if u.is_problem else not u.is_flagged
        a = by.setdefault(kind[u.id], [0, 0]); a[0] += ok; a[1] += 1
    r, s = M.recall_of(us), M.specificity_of(us)
    print(f"{f.name[7:-6]:40s} n={len(us):3d} recall {r:.3f} spec {s:.3f}", {k: f"{a}/{b}" for k, (a, b) in sorted(by.items())})
