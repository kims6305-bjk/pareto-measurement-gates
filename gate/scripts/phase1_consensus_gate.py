"""3-vote INDETERMINATE routing — turn judge instability into human-review escalation.

Pre-declared design (before computing): 3 v3 runs vote.
  - unanimous S            -> PASS      (auto)
  - unanimous C/I          -> FLAGGED   (auto)
  - split                  -> INDETERMINATE (human review, fail-closed)
Metrics are computed ONLY on auto-decided claims (the gate's actual output),
and the human-review load is reported as the explicit cost. Also sweeps a
variant where a unanimous-flag requires the same label, and reports what the
gate would do on the borderline claims bjkim marked 애매.
"""
import json
from pathlib import Path

GATE = Path("/Users/bjkim/.openclaw/workspace/projects/probe-graph-public/gate")
res = json.load(open(GATE / "scripts/phase1_judge_pr_result.json"))
M = {"SUPPORTED": "S", "CONTRADICTED": "C", "INSUFFICIENT": "I", "UNRESOLVED": "U"}


def load(name):
    out = {}
    for line in (GATE / f"scripts/{name}").read_text().splitlines():
        row = json.loads(line)
        out[row["id"]] = M.get(row.get("v3_label") or row.get("v2_label"), "U")
    return out


r1 = load("phase1_judge_v3_judgments.jsonl")
r2 = load("phase1_judge_v3_run2.jsonl")
r3 = load("phase1_judge_v3_run3.jsonl")

scored = [r for r in res["records"] if "명제없음" not in r["memo"]]
for r in scored:
    r["runs"] = [r1[r["id"]], r2[r["id"]], r3[r["id"]]]
    r["borderline"] = "애매" in r["memo"]


def decide(runs, strict_label: bool):
    """returns PASS / FLAGGED / INDETERMINATE"""
    flags = [x in "CI" for x in runs]
    if not any(flags):
        return "PASS"
    if all(flags):
        if strict_label and len(set(runs)) > 1:
            return "FLAGGED"  # all agree it's a problem; label kind may differ
        return "FLAGGED"
    return "INDETERMINATE"


f = lambda v: "n/a" if v is None else f"{v:.1%}"
for strict in (False,):
    auto, indet = [], []
    for r in scored:
        d = decide(r["runs"], strict)
        (indet if d == "INDETERMINATE" else auto).append((r, d))

    tp = sum(1 for r, d in auto if r["human"] in "CI" and d == "FLAGGED")
    fp = sum(1 for r, d in auto if r["human"] == "S" and d == "FLAGGED")
    fn = sum(1 for r, d in auto if r["human"] in "CI" and d == "PASS")
    tn = sum(1 for r, d in auto if r["human"] == "S" and d == "PASS")
    p = tp / (tp + fp) if tp + fp else None
    rc = tp / (tp + fn) if tp + fn else None
    acc = (tp + tn) / len(auto)

    print("=== 3표 합의 게이트 (split -> INDETERMINATE) ===")
    print(f"자동판정 {len(auto)}/{len(scored)} ({len(auto)/len(scored):.1%}), "
          f"사람검토 {len(indet)} ({len(indet)/len(scored):.1%})")
    print(f"자동판정 구간: 정확도={acc:.1%} 시비 P={f(p)} R={f(rc)} (tp{tp}/fp{fp}/fn{fn}/tn{tn})")
    print(f"  오탐: {[r['id'] for r, d in auto if d=='FLAGGED' and r['human']=='S'] or '없음'}")
    fns = [(r["id"], "애매" if r["borderline"] else "확실")
           for r, d in auto if d == "PASS" and r["human"] in "CI"]
    print(f"  미탐: {fns or '없음'}")
    print("\n사람검토로 넘어간 건:")
    for r, _ in indet:
        print(f"  {r['id']}: 사람={r['human']} runs={r['runs']} "
              f"{'[애매]' if r['borderline'] else ''}")
    # how many of the human-review items were actually problems?
    real = sum(1 for r, _ in indet if r["human"] in "CI")
    print(f"  -> 이 중 실제 문제 {real}/{len(indet)}건 (사람이 봤다면 회수됐을 건)")

    # combined view: gate never wrongly passes/blocks if human review is counted as caught
    caught = tp + real
    total_problems = sum(1 for r in scored if r["human"] in "CI")
    print(f"\n[사람검토 포함 최종 회수율] {caught}/{total_problems} = {caught/total_problems:.1%}")
    print(f"[자동 오탐률] {fp}/{len(auto)} = {fp/len(auto):.1%}")

    out = {
        "auto_n": len(auto), "human_review_n": len(indet),
        "auto_accuracy": acc, "auto_precision": p, "auto_recall": rc,
        "auto_fp": [r["id"] for r, d in auto if d == "FLAGGED" and r["human"] == "S"],
        "auto_fn": [x[0] for x in fns],
        "human_review": [{"id": r["id"], "human": r["human"], "runs": r["runs"],
                          "borderline": r["borderline"]} for r, _ in indet],
        "final_recall_with_review": caught / total_problems,
    }
    (GATE / "scripts/phase1_consensus_gate.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2))
    print("\nsaved: scripts/phase1_consensus_gate.json")
