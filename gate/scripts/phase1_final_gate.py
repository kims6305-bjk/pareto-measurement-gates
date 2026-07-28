"""Evaluate the specialist probe as an INDETERMINATE router on top of the consensus gate.

Pre-declared routing: probe YES on an auto-PASS claim -> route to human review.
Cannot increase auto false positives by construction; cost = review volume.
Reports the final gate configuration end-to-end.
"""
import json
from pathlib import Path

GATE = Path("<repo>/gate")
res = json.load(open(GATE / "scripts/phase1_judge_pr_result.json"))
cons = json.load(open(GATE / "scripts/phase1_consensus_gate.json"))
probe = {}
for line in (GATE / "scripts/phase1_probe_unsupported.jsonl").read_text().splitlines():
    row = json.loads(line)
    probe[row["id"]] = row["unsupported"]

M = {"SUPPORTED": "S", "CONTRADICTED": "C", "INSUFFICIENT": "I", "UNRESOLVED": "U"}
v3 = {}
for name in ("phase1_judge_v3_judgments.jsonl", "phase1_judge_v3_run2.jsonl",
             "phase1_judge_v3_run3.jsonl"):
    for line in (GATE / f"scripts/{name}").read_text().splitlines():
        row = json.loads(line)
        v3.setdefault(row["id"], []).append(M[row["v3_label"]])

scored = [r for r in res["records"] if "명제없음" not in r["memo"]]
review_ids = {x["id"] for x in cons["human_review"]}

# --- probe standalone quality on the auto-PASS pool -----------------------
pool = [r for r in scored if r["id"] in probe]
hit_prob = [r for r in pool if probe[r["id"]] == "YES" and r["human"] in "CI"]
hit_ok = [r for r in pool if probe[r["id"]] == "YES" and r["human"] == "S"]
miss = [r for r in pool if probe[r["id"]] == "NO" and r["human"] in "CI"]
print(f"프로브 단독 (auto-PASS {len(pool)}건):")
print(f"  YES {sum(1 for r in pool if probe[r['id']]=='YES')}건 중 실제 문제 {len(hit_prob)}건 "
      f"-> 정밀도 {len(hit_prob)/max(1,len(hit_prob)+len(hit_ok)):.1%}")
print(f"  회수: {[r['id'] for r in hit_prob] or '없음'}")
print(f"  놓침: {[r['id'] for r in miss] or '없음'}")

# --- final gate -----------------------------------------------------------
final = {}
for r in scored:
    i = r["id"]
    if i in review_ids:
        final[i] = "REVIEW"
    elif all(x in "CI" for x in v3[i]):
        final[i] = "FLAGGED"
    elif probe.get(i) == "YES":
        final[i] = "REVIEW"
    else:
        final[i] = "PASS"

auto = [r for r in scored if final[r["id"]] != "REVIEW"]
rev = [r for r in scored if final[r["id"]] == "REVIEW"]
tp = sum(1 for r in auto if final[r["id"]] == "FLAGGED" and r["human"] in "CI")
fp = sum(1 for r in auto if final[r["id"]] == "FLAGGED" and r["human"] == "S")
fn = [r for r in auto if final[r["id"]] == "PASS" and r["human"] in "CI"]
tn = sum(1 for r in auto if final[r["id"]] == "PASS" and r["human"] == "S")
problems = sum(1 for r in scored if r["human"] in "CI")
caught = tp + sum(1 for r in rev if r["human"] in "CI")

print("\n=== 최종 게이트 (3표 합의 + 미지지단정 프로브 라우팅) ===")
print(f"자동 {len(auto)}/{len(scored)} ({len(auto)/len(scored):.1%}), "
      f"사람검토 {len(rev)} ({len(rev)/len(scored):.1%})")
print(f"자동 오탐 {fp}건 ({fp/len(auto):.1%}), 자동 미탐 "
      f"{[(r['id'], '애매' if '애매' in r['memo'] else '확실') for r in fn] or '없음'}")
print(f"[최종 회수율 (검토 포함)] {caught}/{problems} = {caught/problems:.1%}")
print(f"[자동 통과 중 문제 잔존] {len(fn)}/{len(scored)} = {len(fn)/len(scored):.1%}")

out = {
    "probe_standalone": {
        "pool": len(pool), "yes": sum(1 for r in pool if probe[r["id"]] == "YES"),
        "recovered": [r["id"] for r in hit_prob], "false_alarm": [r["id"] for r in hit_ok],
        "missed": [r["id"] for r in miss]},
    "final_gate": {
        "auto_n": len(auto), "review_n": len(rev),
        "auto_fp": fp, "auto_fn": [r["id"] for r in fn],
        "final_recall_with_review": caught / problems,
        "review_rate": len(rev) / len(scored),
        "decisions": {r["id"]: final[r["id"]] for r in scored}},
}
(GATE / "scripts/phase1_final_gate.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2))
print("\nsaved: scripts/phase1_final_gate.json")
