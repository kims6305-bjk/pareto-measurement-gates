"""Final gate with a 3-vote probe (pre-declared rule, fixed before this run).

Pre-declared routing (unchanged from the handoff note):
  - consensus judge (3x v3): unanimous S -> PASS, unanimous C/I -> FLAGGED,
    split -> REVIEW.
  - probe on auto-PASS claims: route to REVIEW only if ALL 3 probe runs say
    YES. Any split reverts to PASS (i.e. the unstable probe hits are dropped).
Reports the 1-run vs 3-run probe as pareto points; no rule is changed after
seeing the numbers.
"""
import json
from pathlib import Path

GATE = Path("<repo>/gate")
res = json.load(open(GATE / "scripts/phase1_judge_pr_result.json"))
cons = json.load(open(GATE / "scripts/phase1_consensus_gate.json"))

M = {"SUPPORTED": "S", "CONTRADICTED": "C", "INSUFFICIENT": "I"}
v3 = {}
for name in ("phase1_judge_v3_judgments.jsonl", "phase1_judge_v3_run2.jsonl",
             "phase1_judge_v3_run3.jsonl"):
    for line in (GATE / f"scripts/{name}").read_text().splitlines():
        row = json.loads(line)
        v3.setdefault(row["id"], []).append(M[row["v3_label"]])

probe_runs = {}
for name in ("phase1_probe_unsupported.jsonl", "phase1_probe_unsupported_run2.jsonl",
             "phase1_probe_unsupported_run3.jsonl"):
    for line in (GATE / f"scripts/{name}").read_text().splitlines():
        row = json.loads(line)
        probe_runs.setdefault(row["id"], []).append(row["unsupported"])

scored = [r for r in res["records"] if "명제없음" not in r["memo"]]
review_ids = {x["id"] for x in cons["human_review"]}


def run_gate(votes_needed):
    final = {}
    for r in scored:
        i = r["id"]
        if i in review_ids:
            final[i] = "REVIEW"
        elif all(x in "CI" for x in v3[i]):
            final[i] = "FLAGGED"
        elif probe_runs.get(i) and sum(1 for v in probe_runs[i] if v == "YES") >= votes_needed:
            final[i] = "REVIEW"
        else:
            final[i] = "PASS"
    auto = [r for r in scored if final[r["id"]] != "REVIEW"]
    rev = [r for r in scored if final[r["id"]] == "REVIEW"]
    tp = sum(1 for r in auto if final[r["id"]] == "FLAGGED" and r["human"] in "CI")
    fp = [r["id"] for r in auto if final[r["id"]] == "FLAGGED" and r["human"] == "S"]
    fn = [r["id"] for r in auto if final[r["id"]] == "PASS" and r["human"] in "CI"]
    problems = sum(1 for r in scored if r["human"] in "CI")
    caught = tp + sum(1 for r in rev if r["human"] in "CI")
    useful_rev = sum(1 for r in rev if r["human"] in "CI")
    return {
        "votes_needed": votes_needed, "auto_n": len(auto), "review_n": len(rev),
        "review_rate": len(rev) / len(scored), "auto_fp": fp, "auto_fn": fn,
        "recall_with_review": caught / problems,
        "review_yield": useful_rev / len(rev) if rev else None,
        "decisions": final,
    }


probe_ids = [i for i, v in probe_runs.items() if len(v) == 3]
stable_yes = [i for i in probe_ids if all(v == "YES" for v in probe_runs[i])]
stable_no = [i for i in probe_ids if all(v == "NO" for v in probe_runs[i])]
split = [i for i in probe_ids if i not in stable_yes and i not in stable_no]
print(f"프로브 3판 안정성: 3판 YES {len(stable_yes)} / 3판 NO {len(stable_no)} / 흔들림 {len(split)} (총 {len(probe_ids)})")
print(f"  흔들린 건: {split or '없음'}")

human = {r["id"]: r["human"] for r in scored}
print(f"  3판 YES 중 실제 문제: {[i for i in stable_yes if human.get(i) in 'CI'] or '없음'}")
print(f"  흔들림 중 실제 문제: {[i for i in split if human.get(i) in 'CI'] or '없음'}")

out = {}
for k in (1, 3):
    g = run_gate(k)
    out[f"probe_{k}vote"] = g
    print(f"\n=== 최종 게이트 (프로브 {k}표 이상 YES 시 라우팅) ===")
    print(f"자동 {g['auto_n']}/{len(scored)}, 사람검토 {g['review_n']} ({g['review_rate']:.1%})")
    print(f"자동 오탐 {len(g['auto_fp'])}건 {g['auto_fp']}, 자동 미탐 {g['auto_fn'] or '없음'}")
    print(f"[검토 포함 회수율] {g['recall_with_review']:.1%}  [검토 적중률] {g['review_yield']:.1%}")

(GATE / "scripts/phase1_final_gate_probe3.json").write_text(
    json.dumps({"probe_stability": {"stable_yes": stable_yes, "split": split},
                **out}, ensure_ascii=False, indent=2))
print("\nsaved: scripts/phase1_final_gate_probe3.json")
