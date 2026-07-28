"""Ensemble rules over v3 x3 (+v2) vs human labels — rules declared BEFORE this run.

Rules (pre-declared in chat before run2/run3 launched):
  R1 any-flag (v3 x3): 1표라도 C/I -> FLAGGED
  R2 any-flag (v3 x3 + v2)
  R3 majority (v3 x3): 2표 이상 C/I -> FLAGGED
Adoption criterion (pre-declared): 시비 정밀도 100% 유지가 전제, 그 안에서 재현율 최대.
Also reports single-run v3 (run1) as the baseline, and run-to-run instability.
"""
import json
from collections import Counter
from pathlib import Path

GATE = Path("<repo>/gate")
res = json.load(open(GATE / "scripts/phase1_judge_pr_result.json"))
M = {"SUPPORTED": "S", "CONTRADICTED": "C", "INSUFFICIENT": "I", "UNRESOLVED": "U"}


def load(name, key):
    out = {}
    for line in (GATE / f"scripts/{name}").read_text().splitlines():
        row = json.loads(line)
        out[row["id"]] = M.get(row[key], "U")
    return out


r1 = load("phase1_judge_v3_judgments.jsonl", "v3_label")
r2 = load("phase1_judge_v3_run2.jsonl", "v3_label")
r3 = load("phase1_judge_v3_run3.jsonl", "v3_label")
v2 = load("phase1_judge_v2_judgments.jsonl", "v2_label")

scored = [r for r in res["records"] if "명제없음" not in r["memo"]]
for r in scored:
    i = r["id"]
    r["runs"] = [r1[i], r2[i], r3[i]]
    r["v2"] = v2[i]
    r["borderline"] = "애매" in r["memo"]

# run-to-run instability
unstable = [r for r in scored if len(set(r["runs"])) > 1]
print(f"판정 흔들린 claim: {len(unstable)}/{len(scored)}")
for r in unstable:
    print(f"  {r['id']}: 사람={r['human']} runs={r['runs']} v2={r['v2']}")


def binary(pred_pos, human):
    return ("POS" if human in "CI" else "NEG", "POS" if pred_pos else "NEG")


def prf(pairs):
    tp = sum(1 for h, j in pairs if h == "POS" and j == "POS")
    fp = sum(1 for h, j in pairs if h == "NEG" and j == "POS")
    fn = sum(1 for h, j in pairs if h == "POS" and j == "NEG")
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    return p, r, tp, fp, fn


RULES = {
    "single v3 (run1, 기준선)": lambda r: r["runs"][0] in "CI",
    "R1 any-flag (v3 x3)": lambda r: any(x in "CI" for x in r["runs"]),
    "R2 any-flag (v3 x3 + v2)": lambda r: any(x in "CI" for x in r["runs"] + [r["v2"]]),
    "R3 majority (v3 x3, 2표+)": lambda r: sum(1 for x in r["runs"] if x in "CI") >= 2,
}

out = {}
f = lambda v: "n/a" if v is None else f"{v:.1%}"
for name, rule in RULES.items():
    pairs = [binary(rule(r), r["human"]) for r in scored]
    p, rc, tp, fp, fn = prf(pairs)
    fps = [r["id"] for r in scored if rule(r) and r["human"] == "S"]
    fns = [(r["id"], "애매" if r["borderline"] else "확실")
           for r in scored if not rule(r) and r["human"] in "CI"]
    print(f"\n== {name} ==")
    print(f"  시비 P={f(p)} R={f(rc)} (tp{tp}/fp{fp}/fn{fn})")
    print(f"  오탐: {fps or '없음'}")
    print(f"  미탐: {fns or '없음'}")
    out[name] = {"precision": p, "recall": rc, "tp": tp, "fp": fp, "fn": fn,
                 "false_positives": fps, "false_negatives": [x[0] for x in fns]}

# adoption per pre-declared criterion
elig = {k: v for k, v in out.items() if v["precision"] == 1.0}
print("\n=== 채택 판정 (사전선언: 정밀도 100% 전제, 그 안에서 재현율 최대) ===")
if elig:
    best = max(elig.items(), key=lambda kv: kv[1]["recall"] or 0)
    print(f"  적격: {list(elig)}")
    print(f"  채택 후보: {best[0]} (R={best[1]['recall']:.1%})")
else:
    print("  적격 없음 — 정밀도 100%를 지키는 규칙이 없음")

(GATE / "scripts/phase1_ensemble_comparison.json").write_text(
    json.dumps({"rules": out,
                "unstable_claims": [{"id": r["id"], "human": r["human"], "runs": r["runs"]}
                                    for r in unstable]},
               ensure_ascii=False, indent=2))
print("\nsaved: scripts/phase1_ensemble_comparison.json")
