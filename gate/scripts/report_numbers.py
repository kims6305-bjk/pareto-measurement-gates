"""보고서 수치 정본 — 원자료에서 직접 계산(0콜). usage: python report_numbers.py → report_numbers.json"""
import json
import os
import subprocess
import sys
from pathlib import Path

S = Path(__file__).resolve().parent
if len(sys.argv) > 1:   # 자식: MH_EXP 별 계산
    import mh_objectives as M
    from sfk_e5 import _units, paired
    exp, cands = sys.argv[1], sys.argv[2:]
    base = _units("c000")
    out = {}
    for c in cands:
        us = _units(c) if c != "c000" else base
        d = {"recall": M.recall_of(us.values()), "specificity": M.specificity_of(us.values()), "n_units": len(us)}
        if c != "c000":
            r, n = paired(c, base, us)
            d["delta"] = {ax: [round(x * 100, 1) for x in v] for ax, v in r.items()}   # Δ, 95lo, 95hi, 97.5lo, 97.5hi
            d["clusters"] = n
        out[c] = d
    print(json.dumps(out))
    sys.exit()

py = str(S.parent.parent / ".venv/bin/python")
res = {}
for exp, cands in {"E5": ["c000", "c301", "c302"], "E6P": ["c000", "c301", "c302", "c401"],
                   "E6": ["c000", "c301", "c302", "c401"]}.items():
    p = subprocess.run([py, __file__, exp, *cands], env={**os.environ, "MH_EXP": exp},
                       capture_output=True, text=True, cwd=S)
    if p.returncode:
        raise SystemExit(p.stderr[-800:])
    res[exp] = json.loads(p.stdout.strip().splitlines()[-1])
# 유형별 정답률(E6 본측정, 3판 평탄)
gold = {u["id"]: (u["human_label"], u["kind"]) for u in json.loads((S / "sfk4_main.json").read_text())}
lab = {"S": "SUPPORTED", "C": "CONTRADICTED", "I": "INSUFFICIENT"}
kinds = {}
for c in ("c000", "c401"):
    acc = {}
    for r in (1, 2, 3):
        for l in (S / f"mh_e6_{c}_run{r}.jsonl").open():
            x = json.loads(l)
            g, k = gold[x["id"]]
            a = acc.setdefault(k, [0, 0])
            a[0] += x["label"] == lab[g]
            a[1] += 1
    kinds[c] = {k: round(a / n, 3) for k, (a, n) in sorted(acc.items())}
res["E6_kind_acc"] = kinds
import statistics  # noqa: E402
rows = {c: [json.loads(l) for r in (1, 2, 3) for l in (S / f"mh_e6_{c}_run{r}.jsonl").open()] for c in ("c000", "c401")}
res["E6_pred"] = {c: sum(x["label"] == "CONTRADICTED" for x in v) for c, v in rows.items()}
res["E6_pred"]["gold_C"] = 3 * sum(g == "C" for g, _ in gold.values())
res["E6_elapsed"] = {c: round(statistics.median(x["elapsed"] for x in v), 1) for c, v in rows.items()}
# 강한 모델 팔(E6P 파일럿, 1판): 단위 1개 판정이라 직접 계산
pil = {u["id"]: u["human_label"] for u in json.loads((S / "sfk4_pilot.json").read_text())}
strong = {}
for f in sorted(S.glob("mh_e6p_arm_*_c000_run1.jsonl")):
    xs = [json.loads(l) for l in f.open()]
    pos = [x for x in xs if pil[x["id"]] != "S"]
    neg = [x for x in xs if pil[x["id"]] == "S"]
    strong[xs[0]["model"]] = [round(sum(x["label"] != "SUPPORTED" for x in pos) / len(pos), 3),
                              round(sum(x["label"] == "SUPPORTED" for x in neg) / len(neg), 3)]
res["E6P_strong"] = strong
res["calls"] = {e: sum(sum(1 for _ in f.open()) for f in S.glob(f"mh_{e}_*run*.jsonl")) for e in ("e5", "e6p", "e6")}
(S / "report_numbers.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
print(json.dumps(res, ensure_ascii=False, indent=1))
