"""Phase 3 가용 표본 실측 — 분해 아티팩트 연구가 검정력을 가질 수 있는가.

Phase 2가 막힌 이유는 결과변수(사람 라벨 기준 '문제 사례')의 기저율이 3.3%로
희소했기 때문이다. Phase 3 후보 결과변수는 **채점 단위에 따른 판정 뒤집힘**이며,
이것은 사람 라벨이 아니라 저지 재실행으로 관측된다. 그 모집단이 실제로 얼마나
있는지를 세는 것이 이 스크립트의 목적이다.

여기서는 '형제 주장을 가진 주장'의 수만 센다. 저지·프로브 출력은 열지 않는다
(Phase 2 화이트리스트는 종료됐으나, Phase 3 사전 선언 전이므로 동일 규율 유지).
"""
import json
from collections import Counter
from pathlib import Path

P = Path("/Users/bjkim/.openclaw/workspace/projects/probe-graph-public")
results = json.load(open(P / "ab/ab_results.json", encoding="utf-8"))
frozen = {q["qid"]: q for q in
          json.load(open(P / "ab/ab_questions_FROZEN.json", encoding="utf-8"))["questions"]}

SELECTION = ("중 이른", "중 늦은", "중 빠른", "둘 중", "중 하나", "중 작은", "중 큰",
             "중 낮은", "중 높은")
CONJUNCTIVE = ("모두 충족", "모두 해당", "요소로 구성", "항목으로 구성", "모두 확인",
               "다음을 모두")


def rule_type(q):
    ev = q.get("evidence_paragraphs", "")
    if any(k in ev for k in SELECTION):
        return "SELECTION"
    if any(k in ev for k in CONJUNCTIVE):
        return "CONJUNCTIVE"
    return "OTHER"


total_answers = 0
total_claims = 0
sib_claims = 0          # 형제를 가진 주장 (분해 아티팩트가 발생할 수 있는 단위)
sib_answers = 0         # 주장이 2개 이상인 답변
by_rule = Counter()
by_rule_answers = Counter()
abstain = 0

# ⚠️ 함정: 결과 JSON의 arm 키는 'armA' / 'armB_final' 이다. 'armB'는 존재하지 않고
#    None을 반환하므로, 그대로 세면 B arm 119개가 통째로 누락된다(실제로 겪음).
ARMS = ("armA", "armB_final")

for qid, res in results.items():
    q = frozen.get(qid)
    if not q:
        continue
    rt = rule_type(q)
    for arm in ARMS:
        a = res.get(arm)
        if not isinstance(a, dict):
            continue
        claims = a.get("claims") or []
        total_answers += 1
        if not claims:
            abstain += 1
            continue
        total_claims += len(claims)
        if len(claims) >= 2:
            sib_answers += 1
            sib_claims += len(claims)
            by_rule[rt] += len(claims)
            by_rule_answers[rt] += 1

print("=== 전체 코퍼스 (armA + armB_final, 119문항 × 2) ===")
print(f"답변 {total_answers}개 / 기권 {abstain}개 / 주장 {total_claims}건")
print()
print("=== 분해 아티팩트가 발생 가능한 모집단 (형제 주장 보유) ===")
print(f"주장 2개 이상인 답변: {sib_answers}개 "
      f"({sib_answers/max(1,total_answers-abstain):.0%} of 답변)")
print(f"형제를 가진 주장:     {sib_claims}건 "
      f"({sib_claims/max(1,total_claims):.0%} of 주장)")
print()
print("=== 규칙유형별 (형제 보유 답변 기준) ===")
for rt in ("CONJUNCTIVE", "SELECTION", "OTHER"):
    print(f"  {rt:12s} 답변 {by_rule_answers[rt]:3d}개 / 주장 {by_rule[rt]:3d}건")
print()
print("=== Phase 2와의 대비 ===")
print(f"Phase 2 결과변수(사람 라벨 문제 사례) 기저율: 3.3% -> 201건 라벨 시 약 6.7건")
print(f"Phase 3 후보 모집단(형제 보유 주장): {sib_claims}건 — 사람 라벨 없이 저지 재실행으로 관측")
print(f"  -> 결과변수를 바꾸면 표본 문제가 해소되는지가 Phase 3 설계의 핵심 질문")

out = P / "gate/scripts/phase3_sample_availability.json"
out.write_text(json.dumps({
    "total_answers": total_answers,
    "abstentions": abstain,
    "total_claims": total_claims,
    "answers_with_siblings": sib_answers,
    "claims_with_siblings": sib_claims,
    "by_rule_claims": dict(by_rule),
    "by_rule_answers": dict(by_rule_answers),
    "note": "저지/프로브 출력 미참조. 형제 보유 여부는 claims 개수만으로 결정.",
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nsaved: {out.name}")
