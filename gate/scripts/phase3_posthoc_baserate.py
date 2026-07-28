"""Phase 3 사후 분석 — 왜 개선 뒤집힘이 0건이었는가.

🔴 이것은 **사후(post-hoc) 분석**이다. 사전 선언한 판정 기준(phase3_score.py)은
   수정하지 않았고, 그 판정은 이미 phase3_result.json으로 확정됐다.
   이 스크립트는 확정된 판정을 **설명**할 뿐이며, 어떤 가설도 채택하지 않는다.

목적: 조건 A(대조)의 문제 판정 기저율을 측정한다.
      개선 뒤집힘(A:문제 -> B:SUPPORTED)의 상한은 A의 문제 판정 건수다.
      그 값이 0이면 H1은 검정된 것이 아니라 **검정 불가능한 설계**였던 것이다.
"""
import collections
import glob
import json
from pathlib import Path

GATE = Path(__file__).resolve().parent


def majority(cond):
    per = collections.defaultdict(list)
    for f in sorted(glob.glob(str(GATE / f"phase3_judge_{cond}_run*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            per[d["id"]].append(d)
    out = {}
    for i, rows in per.items():
        cnt = collections.Counter(r["label"] for r in rows).most_common()
        out[i] = (cnt[0][0] if cnt[0][1] >= 2 else "SPLIT", rows[0])
    return out


A, B = majority("A"), majority("B")
ids = sorted(set(A) & set(B))
PROBLEM = {"CONTRADICTED", "INSUFFICIENT"}

rows = []
for s in ("confirmatory", "exploratory"):
    sub = [i for i in ids if A[i][1]["set"] == s]
    if not sub:
        continue
    a_prob = [i for i in sub if A[i][0] in PROBLEM]
    a_split = [i for i in sub if A[i][0] == "SPLIT"]
    rows.append({
        "set": s,
        "n": len(sub),
        "A_problem": len(a_prob),
        "A_problem_rate": round(len(a_prob) / len(sub), 4),
        "A_split": len(a_split),
        "improvement_ceiling": len(a_prob),
    })

deg = []
for i in ids:
    if A[i][0] != B[i][0]:
        r = A[i][1]
        deg.append({"id": i, "set": r["set"], "rule_type": r["rule_type"],
                    "n_siblings": r["n_siblings"], "A": A[i][0], "B": B[i][0]})

qcnt = collections.Counter(d["id"].split("-")[0] for d in deg)

out = {
    "note": "POST-HOC. 사전 판정(phase3_result.json)을 설명할 뿐 변경하지 않는다.",
    "by_set": rows,
    "disagreements": deg,
    "disagreement_by_question": dict(qcnt),
}
(GATE / "phase3_posthoc_baserate.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

for r in rows:
    print(f"[{r['set']}] n={r['n']}  조건A 문제판정 {r['A_problem']}건 "
          f"({r['A_problem_rate']:.1%})  SPLIT {r['A_split']}건")
    print(f"    -> 개선 뒤집힘의 구조적 상한 = {r['improvement_ceiling']}건")
print(f"\n불일치 {len(deg)}건, 문항 분포: {dict(qcnt)}")
print("saved: phase3_posthoc_baserate.json")
