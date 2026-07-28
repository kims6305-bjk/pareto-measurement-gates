"""Control comparison: is the probe actually better than sending the same
number of claims to review at random? (base-rate control)

Pre-declared control: on the auto-PASS pool the consensus gate hands over,
a random router that flags k claims recovers k * base_rate problems in
expectation. If the probe's yield is not above that, the probe adds nothing
but review cost.
"""
import json
from pathlib import Path

G = Path("<repo>/gate/scripts")
res = json.load(open(G / "phase1_judge_pr_result.json"))
cons = json.load(open(G / "phase1_consensus_gate.json"))
p3 = json.load(open(G / "phase1_final_gate_probe3.json"))

scored = [r for r in res["records"] if "명제없음" not in r["memo"]]
human = {r["id"]: r["human"] for r in scored}
review_ids = {x["id"] for x in cons["human_review"]}

probe_runs = {}
for name in ("phase1_probe_unsupported.jsonl", "phase1_probe_unsupported_run2.jsonl",
             "phase1_probe_unsupported_run3.jsonl"):
    for line in (G / name).read_text().splitlines():
        row = json.loads(line)
        probe_runs.setdefault(row["id"], []).append(row["unsupported"])

M = {"SUPPORTED": "S", "CONTRADICTED": "C", "INSUFFICIENT": "I"}
v3 = {}
for name in ("phase1_judge_v3_judgments.jsonl", "phase1_judge_v3_run2.jsonl",
             "phase1_judge_v3_run3.jsonl"):
    for line in (G / name).read_text().splitlines():
        row = json.loads(line)
        v3.setdefault(row["id"], []).append(M[row["v3_label"]])

# --- pool the probe actually operates on -------------------------------
pool = [r["id"] for r in scored
        if r["id"] not in review_ids and not all(x in "CI" for x in v3[r["id"]])]
pool = [i for i in pool if i in probe_runs]
pool_problems = [i for i in pool if human[i] in "CI"]
base = len(pool_problems) / len(pool)
print(f"프로브 작동 풀: {len(pool)}건, 그중 실제 문제 {len(pool_problems)}건 "
      f"= 기저율 {base:.1%}")

yes3 = [i for i in pool if all(v == "YES" for v in probe_runs[i])]
hit3 = [i for i in yes3 if human[i] in "CI"]
print(f"\n프로브 3판YES {len(yes3)}건 -> 실제 문제 {len(hit3)}건 = 정밀도 {len(hit3)/len(yes3):.1%}")
print(f"같은 수({len(yes3)}건)를 무작위로 검토 보냈을 때 기대 회수 = "
      f"{len(yes3)*base:.2f}건")
lift = (len(hit3) / len(yes3)) / base
print(f"-> 리프트 {lift:.2f}x  ({'무작위보다 나음' if lift > 1 else '무작위보다 못함 = 신호 없음'})")

# --- what if we drop the probe entirely? -------------------------------
def gate(use_probe):
    final = {}
    for r in scored:
        i = r["id"]
        if i in review_ids:
            final[i] = "REVIEW"
        elif all(x in "CI" for x in v3[i]):
            final[i] = "FLAGGED"
        elif use_probe and i in yes3:
            final[i] = "REVIEW"
        else:
            final[i] = "PASS"
    rev = [i for i in final if final[i] == "REVIEW"]
    tp = sum(1 for i in final if final[i] == "FLAGGED" and human[i] in "CI")
    caught = tp + sum(1 for i in rev if human[i] in "CI")
    problems = sum(1 for i in human if human[i] in "CI")
    fn = [i for i in final if final[i] == "PASS" and human[i] in "CI"]
    return len(rev), caught / problems, fn

for use in (False, True):
    n, rc, fn = gate(use)
    print(f"\n프로브 {'ON ' if use else 'OFF'}: 검토 {n}건 ({n/len(scored):.1%}), "
          f"회수율 {rc:.1%}, 자동통과 잔존문제 {fn}")

print("\n[프로브의 순효과] 검토 +", gate(True)[0] - gate(False)[0],
      "건 늘려서 회수 +", round((gate(True)[1] - gate(False)[1]) * 10), "건")
