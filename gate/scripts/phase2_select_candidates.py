"""Phase 2 candidate selection — maximize INDEPENDENT problem cases per label.

Design target (from phase2_power_analysis.py, run before this):
  - problem cases >= 55 (currently 10)
  - distinct answers carrying a problem >= 25 (currently 8)
  - the binding constraint is CLUSTERING, not claim count: 2 of the 10 problems
    came from a single answer (Q068-A), so extra claims on the same answer buy
    almost no independent information.

Selection rules (declared here, applied mechanically below):
  R1. One answer per question. Never label two answers of the same qid — that
      re-introduces the clustering that broke phase 1.
  R2. Prioritize the trap layers (no_answer / distractor): they carry the highest
      prior probability of producing a genuine problem case, so they raise the
      problem count per unit of bjkim's labeling time.
  R3. Cover distinct standards (기준서). Phase 1's only true hits all sat on one
      paragraph (1019.103); standard diversity is what makes a filter testable
      instead of memorized.
  R4. Deliberately include SELECTION-rule paragraphs ("중 이른 날" 등) from
      standards other than 1019 — this is the specific hypothesis phase 1 could
      not test (overfit to a single paragraph).
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

P = Path("/Users/bjkim/.openclaw/workspace/projects/probe-graph-public")
d = json.load(open(P / "ab/ab_questions_FROZEN.json", encoding="utf-8"))
qs = d["questions"]
sheet = json.load(open(P / "gate/scripts/phase1_human_label_sheet.json", encoding="utf-8"))
used_q = {i["id"].split("-")[0] for i in sheet}

unused = [q for q in qs if q["qid"] not in used_q]
print(f"미사용 문항 {len(unused)}건 / 전체 {len(qs)}건 (기존 라벨 사용 {len(used_q)}건)")
print("미사용 층 분포:", dict(Counter(q["layer"] for q in unused)))

SELECTION = ("중 이른", "중 늦은", "중 빠른", "둘 중", "중 하나", "중 작은", "중 큰",
             "중 낮은", "중 높은")
CONJUNCTIVE = ("모두 충족", "모두 해당", "요소로 구성", "항목으로 구성", "모두 확인",
               "다음을 모두")


def rule_type(q):
    ev = q["evidence_paragraphs"]
    if any(k in ev for k in SELECTION):
        return "SELECTION"
    if any(k in ev for k in CONJUNCTIVE):
        return "CONJUNCTIVE"
    return "OTHER"


def std_of(q):
    m = re.match(r"(\d{4})", q.get("standard", ""))
    return m.group(1) if m else q.get("standard", "?")


for q in unused:
    q["_rule"] = rule_type(q)
    q["_std"] = std_of(q)

print("\n미사용 풀의 규칙유형 분포:", dict(Counter(q["_rule"] for q in unused)))
print("선택규칙 문항이 걸친 기준서:",
      dict(Counter(q["_std"] for q in unused if q["_rule"] == "SELECTION")))

# --- R4 check: does the pool let us escape the 1019.103 overfit? ---------
sel = [q for q in unused if q["_rule"] == "SELECTION"]
sel_std = {q["_std"] for q in sel}
print(f"\n[R4] 선택규칙 미사용 문항 {len(sel)}건, 서로 다른 기준서 {len(sel_std)}개 -> "
      f"{'1019 밖에서 검증 가능 ✅' if sel_std - {'1019'} else '여전히 1019뿐 ❌'}")
for q in sel:
    print(f"   {q['qid']} [{q['layer']}] {q['standard']}")

# --- selection: R1 (1 answer/question) + R2 (trap first) + R3 (std spread) ---
LAYER_PRIORITY = {"distractor": 0, "normal": 1, "no_answer": 2}

# R2 CORRECTION (see phase2_build_label_sheet.py): every no_answer question in
# this corpus produced `claims: []` — the answerer correctly abstained on all 17.
# Abstentions have no claim to label, so the layer cannot yield problem cases.
# Excluded here and reported separately as a correct-abstention rate.
noans = [q for q in unused if q["layer"] == "no_answer"]
unused = [q for q in unused if q["layer"] != "no_answer"]
print(f"\n[R2 정정] no_answer {len(noans)}건 제외 — 전건 올바른 기권(claims 0)이라 "
      f"라벨 대상 주장이 없음. 기권률은 별도 지표로 보고.")

# R4 is a HARD requirement, not a preference: every SELECTION-rule question in
# the pool is force-included first. Phase 1's untestable hypothesis (선택규칙 필터)
# is exactly what these 9 questions across 7 standards can finally test, and a
# round-robin that only happened to pick 5 of them would leave it untestable.
picked = sorted([q for q in unused if q["_rule"] == "SELECTION"],
                key=lambda x: (LAYER_PRIORITY[x["layer"]], x["qid"]))
forced = {q["qid"] for q in picked}
print(f"\n[R4 강제 포함] 선택규칙 {len(picked)}문항 우선 편입")

by_std = defaultdict(list)
for q in sorted(unused, key=lambda x: (LAYER_PRIORITY[x["layer"]], x["qid"])):
    if q["qid"] not in forced:
        by_std[q["_std"]].append(q)

# round-robin across standards so no single 기준서 dominates
guard = 0
while len(picked) < 80 and guard < 50:
    added = False
    for std in sorted(by_std):
        # cap per standard to keep the spread wide
        if sum(1 for p in picked if p["_std"] == std) >= 8:
            continue
        if by_std[std]:
            picked.append(by_std[std].pop(0))
            added = True
            if len(picked) >= 80:
                break
    guard += 1
    if not added:
        break

print(f"\n=== 선정 {len(picked)}문항 (R1~R4 적용) ===")
print("  층 분포:", dict(Counter(q["layer"] for q in picked)))
print("  규칙유형:", dict(Counter(q["_rule"] for q in picked)))
print(f"  기준서 {len({q['_std'] for q in picked})}종, 최대 편중 "
      f"{Counter(q['_std'] for q in picked).most_common(1)[0]}")
trap = sum(1 for q in picked if q["layer"] != "normal")
print(f"  함정층 비율 {trap}/{len(picked)} = {trap/len(picked):.0%} "
      f"(evals.md 기준 각 ≥15%: "
      f"no_answer {sum(1 for q in picked if q['layer']=='no_answer')/len(picked):.0%}, "
      f"distractor {sum(1 for q in picked if q['layer']=='distractor')/len(picked):.0%})")

out = P / "gate/scripts/phase2_candidate_questions.json"
out.write_text(json.dumps({
    "meta": {"selected_from": "ab_questions_FROZEN.json",
             "excluded_already_labeled": sorted(used_q),
             "rules": ["R1 one answer per question", "R2 trap layers first",
                       "R3 standard diversity (cap 6/standard)",
                       "R4 include SELECTION-rule paragraphs outside 1019"],
             "n": len(picked)},
    "questions": [{k: v for k, v in q.items() if not k.startswith("_")}
                  | {"rule_type": q["_rule"], "standard_code": q["_std"]}
                  for q in picked],
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nsaved: {out.relative_to(P)}")
