"""Score judge v2 vs human labels; print v1/v2 side-by-side per LABELING_PROTOCOL."""
import json
from collections import Counter
from pathlib import Path

GATE = Path("/Users/bjkim/.openclaw/workspace/projects/probe-graph-public/gate")
res = json.load(open(GATE / "scripts/phase1_judge_pr_result.json"))  # human+v1
v2 = {}
for line in (GATE / "scripts/phase1_judge_v2_judgments.jsonl").read_text().splitlines():
    row = json.loads(line)
    v2[row["id"]] = row["v2_label"]

M = {"SUPPORTED": "S", "CONTRADICTED": "C", "INSUFFICIENT": "I", "UNRESOLVED": "U"}


def prf(pairs, positive):
    tp = sum(1 for h, j in pairs if h == positive and j == positive)
    fp = sum(1 for h, j in pairs if h != positive and j == positive)
    fn = sum(1 for h, j in pairs if h == positive and j != positive)
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    return p, r, tp, fp, fn


def report(name, pairs):
    agree = sum(1 for h, j in pairs if h == j)
    print(f"\n== {name} (n={len(pairs)}, agreement {agree}/{len(pairs)} = {agree/len(pairs):.1%}) ==")
    ok = True
    for cls in ("S", "C", "I"):
        p, r, tp, fp, fn = prf(pairs, cls)
        f = lambda v: "n/a" if v is None else f"{v:.1%}"
        flag = " ⚠️<90%" if any(v is not None and v < 0.9 for v in (p, r)) else ""
        if flag:
            ok = False
        print(f"  {cls}: P={f(p)} R={f(r)} (tp{tp}/fp{fp}/fn{fn}){flag}")
    gp = [("POS" if h in "CI" else "NEG", "POS" if j in "CI" else "NEG") for h, j in pairs]
    p, r, *_ = prf(gp, "POS")
    f = lambda v: "n/a" if v is None else f"{v:.1%}"
    print(f"  [게이트 양성=C∪I] P={f(p)} R={f(r)}")
    return ok


scored = [r for r in res["records"] if "명제없음" not in r["memo"]]
v1_pairs = [(r["human"], r["judge"]) for r in scored]
v2_pairs = [(r["human"], M.get(v2.get(r["id"]), "U")) for r in scored]

print("v2 라벨 분포:", dict(Counter(j for _, j in v2_pairs)))
u = [r["id"] for r in scored if M.get(v2.get(r["id"])) == "U" or r["id"] not in v2]
if u:
    print("⚠️ UNRESOLVED/누락:", u)

ok1 = report("v1 (claim 고립)", v1_pairs)
ok2 = report("v2 (전체답변+형제+불완전성지침)", v2_pairs)
print(f"\n판정: v1 {'PASS' if ok1 else 'FAIL'} / v2 {'PASS' if ok2 else 'FAIL'} (목표 전 클래스 P·R≥90%)")

print("\nv2 잔여 불일치:")
for r in scored:
    j2 = M.get(v2.get(r["id"]), "U")
    if j2 != r["human"]:
        print(f"  {r['id']}: 사람={r['human']} v1={r['judge']} v2={j2}  memo={r['memo'][:50]}")

out = {
    "v1": {"agreement": sum(1 for h, j in v1_pairs if h == j) / len(v1_pairs)},
    "v2": {"agreement": sum(1 for h, j in v2_pairs if h == j) / len(v2_pairs)},
}
for name, pairs in (("v1", v1_pairs), ("v2", v2_pairs)):
    for cls in ("S", "C", "I"):
        p, r, tp, fp, fn = prf(pairs, cls)
        out[name][cls] = {"precision": p, "recall": r, "tp": tp, "fp": fp, "fn": fn}
(GATE / "scripts/phase1_v1_v2_comparison.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2))
print("\nsaved:", GATE / "scripts/phase1_v1_v2_comparison.json")
