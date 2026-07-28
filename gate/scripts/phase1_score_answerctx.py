"""Score the answer-context probe against the PRE-DECLARED criteria in
gate/ANSWER_CONTEXT_PROBE.md (committed before the run).

Criteria (verbatim, not re-derived here):
  (a) >=8 of the 12 per-claim false alarms flip to NO
  (b) the 2 true hits (Q068-A-c1, Q068-A-c2) stay YES
  (c) final gate recall does not drop below 90.0%
Routing rule: 3/3 YES -> review (same as the per-claim experiment).
Reports per-claim and answer-context side by side; neither replaces the other.
"""
import json
from collections import defaultdict
from pathlib import Path

G = Path("<repo>/gate/scripts")
res = json.load(open(G / "phase1_judge_pr_result.json", encoding="utf-8"))
cons = json.load(open(G / "phase1_consensus_gate.json", encoding="utf-8"))
scored = {r["id"]: r for r in res["records"] if "명제없음" not in r["memo"]}
human = {i: scored[i]["human"] for i in scored}
review_ids = {x["id"] for x in cons["human_review"]}

M = {"SUPPORTED": "S", "CONTRADICTED": "C", "INSUFFICIENT": "I"}
v3 = defaultdict(list)
for name in ("phase1_judge_v3_judgments.jsonl", "phase1_judge_v3_run2.jsonl",
             "phase1_judge_v3_run3.jsonl"):
    for line in (G / name).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        v3[row["id"]].append(M[row["v3_label"]])


def load(names, key="unsupported"):
    d = defaultdict(list)
    for n in names:
        p = G / n
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            d[r["id"]].append((r[key], r.get("rationale", "")))
    return d


old = load(["phase1_probe_unsupported.jsonl", "phase1_probe_unsupported_run2.jsonl",
            "phase1_probe_unsupported_run3.jsonl"])
new = load(["phase1_probe_answerctx_run1.jsonl", "phase1_probe_answerctx_run2.jsonl",
            "phase1_probe_answerctx_run3.jsonl"])

incomplete = [i for i in new if len(new[i]) < 3]
if len(new) < len(old) or incomplete:
    print(f"⚠ 아직 미완: 신규 {len(new)}건 (3판 미달 {len(incomplete)}건) / 기존 {len(old)}건")


def yes3(d):
    return {i for i in d if len(d[i]) == 3 and all(v == "YES" for v, _ in d[i])}


def stability(d):
    full = [i for i in d if len(d[i]) == 3]
    sy = [i for i in full if all(v == "YES" for v, _ in d[i])]
    sn = [i for i in full if all(v == "NO" for v, _ in d[i])]
    return len(full), len(sy), len(sn), len(full) - len(sy) - len(sn)


def gate(hits):
    final = {}
    for i in scored:
        if i in review_ids:
            final[i] = "REVIEW"
        elif all(x in "CI" for x in v3[i]):
            final[i] = "FLAGGED"
        elif i in hits:
            final[i] = "REVIEW"
        else:
            final[i] = "PASS"
    rev = [i for i in final if final[i] == "REVIEW"]
    tp = sum(1 for i in final if final[i] == "FLAGGED" and human[i] in "CI")
    caught = tp + sum(1 for i in rev if human[i] in "CI")
    problems = sum(1 for i in human if human[i] in "CI")
    fn = [i for i in final if final[i] == "PASS" and human[i] in "CI"]
    return {"review_n": len(rev), "review_rate": len(rev) / len(scored),
            "recall": caught / problems, "auto_fn": fn,
            "auto_fp": [i for i in final if final[i] == "FLAGGED" and human[i] == "S"]}


oy, ny = yes3(old), yes3(new)
old_fa = sorted(i for i in oy if human[i] == "S")
old_tp = sorted(i for i in oy if human[i] in "CI")

print("=== 프로브 안정성 (3판) ===")
for tag, d in (("per-claim ", old), ("answer-ctx", new)):
    n, sy, sn, sp = stability(d)
    print(f"  {tag}: 완료 {n}건 | 3판YES {sy} | 3판NO {sn} | 흔들림 {sp}")

print(f"\n=== (a) 기존 오탐 {len(old_fa)}건이 뒤집혔나 ===")
flipped = []
for i in old_fa:
    if i not in new or len(new[i]) < 3:
        print(f"  {i}: (미완)")
        continue
    votes = [v for v, _ in new[i]]
    ok = i not in ny
    flipped.append(ok)
    print(f"  {i}: {votes} -> {'뒤집힘 ✅' if ok else '여전히 YES ❌'}")
n_flip = sum(flipped)
ans_flip = len({i.rsplit('-', 1)[0] for i, f in zip(old_fa, flipped) if f}) if flipped else 0
print(f"  => {n_flip}/{len(old_fa)}건 뒤집힘 (독립 답변 {ans_flip}개). 기준 8건: "
      f"{'충족 ✅' if n_flip >= 8 else '미달 ❌'}")

print(f"\n=== (b) 진짜 히트 {len(old_tp)}건이 YES를 유지했나 ===")
kept = []
for i in old_tp:
    if i not in new or len(new[i]) < 3:
        print(f"  {i}: (미완)")
        continue
    votes = [v for v, _ in new[i]]
    ok = i in ny
    kept.append(ok)
    print(f"  {i}: {votes} -> {'유지 ✅' if ok else '놓침 ❌'}")
    if not ok:
        print(f"      사유: {new[i][0][1][:160]}")
b_ok = kept and all(kept)
print(f"  => 기준(2건 모두 유지): {'충족 ✅' if b_ok else '미달 ❌'}")

print("\n=== (c) 게이트 최종 비교 ===")
go, gn = gate(oy), gate(ny)
print(f"{'':<12}{'검토':<10}{'검토율':<10}{'회수율':<10}{'자동오탐':<10}{'자동미탐'}")
for tag, g in (("per-claim", go), ("answer-ctx", gn)):
    print(f"{tag:<12}{g['review_n']:<10}{g['review_rate']:<10.1%}{g['recall']:<10.1%}"
          f"{len(g['auto_fp']):<10}{g['auto_fn']}")
c_ok = gn["recall"] >= 0.90 - 1e-9
print(f"  => 기준(회수율 90.0% 유지): {'충족 ✅' if c_ok else '미달 ❌'}")

# probe-level precision
def prec(hits):
    t = [i for i in hits if human[i] in "CI"]
    return len(t), len(hits), (len(t) / len(hits) if hits else None)


for tag, h in (("per-claim", oy), ("answer-ctx", ny)):
    t, n, p = prec(h)
    print(f"\n{tag} 프로브 3판YES: {n}건 중 진짜 {t}건 = 정밀도 "
          f"{'n/a' if p is None else f'{p:.1%}'}")

# --- CONFOUND CONTROL (added mid-run, before scoring) --------------------
# The change bundled TWO things: (i) sibling context, (ii) a softening
# instruction ("형제 문장이 담당하는 조건을 누락으로 보지 마라").
# If claims with NO siblings also flipped, the flip cannot be attributed to
# context — the instruction alone blunted the probe.
sib_n = {}
for name in ("phase1_probe_answerctx_run1.jsonl",):
    p = G / name
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            sib_n[r["id"]] = r.get("n_siblings", 0)

solo_fa = [i for i in old_fa if sib_n.get(i, 0) <= 1]
solo_flip = [i for i in solo_fa if i not in ny and i in new and len(new[i]) == 3]
multi_fa = [i for i in old_fa if sib_n.get(i, 0) > 1]
multi_flip = [i for i in multi_fa if i not in ny and i in new and len(new[i]) == 3]
print("\n=== 교란변수 통제: 형제가 없는 주장도 뒤집혔나 ===")
print(f"  형제 없음(단독) 오탐 {len(solo_fa)}건 중 뒤집힘 {len(solo_flip)}건 {solo_flip}")
print(f"  형제 있음 오탐     {len(multi_fa)}건 중 뒤집힘 {len(multi_flip)}건")
if solo_flip:
    print("  ⚠ 형제가 없는데도 뒤집힌 건이 있음 -> 문맥이 아니라 '완화 지시' 효과가 섞여 있다.")
    print("     즉 이 실험은 단일 변인이 아니며, 정밀도 개선을 문맥 덕분이라고 말할 수 없다.")
else:
    print("  형제 있는 건만 뒤집힘 -> 문맥 효과로 해석 가능.")

verdict = ("처방 통함 (a,b,c 모두 충족)" if (n_flip >= 8 and b_ok and c_ok)
           else "채택 불가 — 사전 선언 기준 미충족")
print(f"\n[사전 선언 기준에 따른 판정] {verdict}")
if solo_flip:
    print("[추가 경고] 교란변수 미통제 — 위 판정이 충족이어도 원인 귀속은 불가.")

(G / "phase1_answerctx_result.json").write_text(json.dumps({
    "criteria": {"a_flipped": n_flip, "a_required": 8, "a_pass": n_flip >= 8,
                 "a_independent_answers": ans_flip,
                 "b_true_hits_kept": bool(b_ok), "c_recall": gn["recall"], "c_pass": bool(c_ok)},
    "stability": {"per_claim": stability(old), "answer_ctx": stability(new)},
    "gate": {"per_claim": go, "answer_ctx": gn},
    "probe_yes3": {"per_claim": sorted(oy), "answer_ctx": sorted(ny)},
    "verdict": verdict,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print("saved: scripts/phase1_answerctx_result.json")
