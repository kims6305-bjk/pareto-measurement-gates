"""Final Phase 1 comparison: v1/v2/v3 vs human labels, with 애매(borderline) split."""
import json
from collections import Counter
from pathlib import Path

GATE = Path("<repo>/gate")
res = json.load(open(GATE / "scripts/phase1_judge_pr_result.json"))

def load_jsonl(name, key):
    out = {}
    p = GATE / f"scripts/{name}"
    for line in p.read_text().splitlines():
        row = json.loads(line)
        out[row["id"]] = row[key]
    return out

v2 = load_jsonl("phase1_judge_v2_judgments.jsonl", "v2_label")
v3 = load_jsonl("phase1_judge_v3_judgments.jsonl", "v3_label")
M = {"SUPPORTED": "S", "CONTRADICTED": "C", "INSUFFICIENT": "I", "UNRESOLVED": "U"}

scored = [r for r in res["records"] if "명제없음" not in r["memo"]]
for r in scored:
    r["v2"] = M.get(v2.get(r["id"]), "U")
    r["v3"] = M.get(v3.get(r["id"]), "U")
    r["borderline"] = "애매" in r["memo"]

def prf(pairs, positive):
    tp = sum(1 for h, j in pairs if h == positive and j == positive)
    fp = sum(1 for h, j in pairs if h != positive and j == positive)
    fn = sum(1 for h, j in pairs if h == positive and j != positive)
    return (tp / (tp + fp) if tp + fp else None,
            tp / (tp + fn) if tp + fn else None, tp, fp, fn)

def report(name, key):
    pairs = [(r["human"], r[key]) for r in scored]
    agree = sum(1 for h, j in pairs if h == j)
    print(f"\n== {name} (n={len(pairs)}, agreement {agree}/{len(pairs)} = {agree/len(pairs):.1%}) ==")
    f = lambda v: "n/a" if v is None else f"{v:.1%}"
    ok = True
    for cls in ("S", "C", "I"):
        p, r_, tp, fp, fn = prf(pairs, cls)
        flag = " ⚠️<90%" if any(v is not None and v < 0.9 for v in (p, r_)) else ""
        if flag:
            ok = False
        print(f"  {cls}: P={f(p)} R={f(r_)} (tp{tp}/fp{fp}/fn{fn}){flag}")
    gp = [("POS" if h in "CI" else "NEG", "POS" if j in "CI" else "NEG") for h, j in pairs]
    p, r_, *_ = prf(gp, "POS")
    print(f"  [게이트 양성=C∪I] P={f(p)} R={f(r_)}")
    dis = [r for r in scored if r[key] != r["human"]]
    solid = [r for r in dis if not r["borderline"]]
    print(f"  불일치 {len(dis)} = 확실 {len(solid)} + 애매표시 {len(dis)-len(solid)}")
    for r in dis:
        tag = "애매" if r["borderline"] else "확실"
        print(f"    [{tag}] {r['id']}: 사람={r['human']} {key}={r[key]}")
    return ok, agree / len(pairs)

r1 = report("v1 (claim 고립)", "judge")
r2 = report("v2 (맥락+불완전성지침)", "v2")
r3 = report("v3 (v2+규칙왜곡 이분)", "v3")

# solid-only (애매 제외) agreement for v3
solid_pairs = [(r["human"], r["v3"]) for r in scored if not r["borderline"]]
sa = sum(1 for h, j in solid_pairs if h == j)
print(f"\nv3 확실 건만(애매 {len(scored)-len(solid_pairs)}건 제외): {sa}/{len(solid_pairs)} = {sa/len(solid_pairs):.1%}")

out = GATE / "scripts/phase1_final_comparison.json"
out.write_text(json.dumps({
    "n_scored": len(scored),
    "agreement": {"v1": r1[1], "v2": r2[1], "v3": r3[1]},
    "records": [{k: r[k] for k in ("id", "human", "judge", "v2", "v3", "memo", "borderline")}
                for r in scored],
}, ensure_ascii=False, indent=2))
print("saved:", out)
