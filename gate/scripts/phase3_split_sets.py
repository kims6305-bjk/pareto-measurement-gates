"""Phase 3 확증/탐색 집합 분리 — 순환 논증 차단.

PHASE3_PREREGISTRATION.md §0: Phase 2 파일럿 30건이 속한 문항은 이 가설을 **생성**한
표본이므로 탐색(exploratory) 집합으로 격리하고, 검정은 확증(confirmatory) 집합에서만
수행한다.

이 스크립트는 저지를 실행하지 않는다. 집합을 나누고 각 집합의 검정력 가용량만 센다.
"""
import json
from collections import Counter
from pathlib import Path

P = Path("/Users/bjkim/.openclaw/workspace/projects/probe-graph-public")
GATE = P / "gate/scripts"

results = json.load(open(P / "ab/ab_results.json", encoding="utf-8"))
frozen = {q["qid"]: q for q in
          json.load(open(P / "ab/ab_questions_FROZEN.json", encoding="utf-8"))["questions"]}

# 가설을 생성한 표본: Phase 2 파일럿 30건 + Phase 1 라벨 55건.
# 둘 다 사람이 눈으로 본 데이터이므로 확증 집합에서 제외한다.
pilot = json.load(open(GATE / "phase2_pilot_label_sheet.json", encoding="utf-8"))
phase1 = json.load(open(GATE / "phase1_human_label_sheet.json", encoding="utf-8"))
seen_qids = ({r["qid"] for r in pilot}
             | {r["id"].split("-")[0] for r in phase1})

SELECTION = ("중 이른", "중 늦은", "중 빠른", "둘 중", "중 하나", "중 작은", "중 큰",
             "중 낮은", "중 높은")
CONJUNCTIVE = ("모두 충족", "모두 해당", "요소로 구성", "항목으로 구성", "모두 확인",
               "다음을 모두")
ARMS = ("armA", "armB_final")   # 'armB'는 존재하지 않는 키다 — phase3_sample_availability 참조


def rule_type(q):
    ev = q.get("evidence_paragraphs", "")
    if any(k in ev for k in SELECTION):
        return "SELECTION"
    if any(k in ev for k in CONJUNCTIVE):
        return "CONJUNCTIVE"
    return "OTHER"


units = []          # 채점 단위 = (qid, arm, claim_id)
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
        for c in claims:
            units.append({
                "qid": qid, "arm": arm, "claim_id": c.get("claim_id"),
                "rule_type": rt, "layer": q.get("layer"),
                "n_siblings": len(claims) - 1,
                "set": "exploratory" if qid in seen_qids else "confirmatory",
            })

conf = [u for u in units if u["set"] == "confirmatory"]
expl = [u for u in units if u["set"] == "exploratory"]

print(f"가설 생성에 쓰인 문항(제외 대상): {len(seen_qids)}개 "
      f"(Phase 2 파일럿 {len({r['qid'] for r in pilot})} + Phase 1 {len({r['id'].split('-')[0] for r in phase1})})")
print()

for name, group in (("확증(confirmatory)", conf), ("탐색(exploratory)", expl)):
    sib = [u for u in group if u["n_siblings"] >= 1]
    solo = [u for u in group if u["n_siblings"] == 0]
    by = Counter(u["rule_type"] for u in sib)
    print(f"=== {name} ===")
    print(f"  전체 채점단위 {len(group)}건 / 문항 {len({u['qid'] for u in group})}개")
    print(f"  형제 보유(주검정 대상) {len(sib)}건 — "
          f"CONJUNCTIVE {by['CONJUNCTIVE']} / SELECTION {by['SELECTION']} / OTHER {by['OTHER']}")
    print(f"  단독 주장(음성 대조군) {len(solo)}건")
    print()

# H2 병목 점검: 확증 집합의 SELECTION이 검정 가능한 규모인가
conf_sel = [u for u in conf if u["n_siblings"] >= 1 and u["rule_type"] == "SELECTION"]
conf_conj = [u for u in conf if u["n_siblings"] >= 1 and u["rule_type"] == "CONJUNCTIVE"]
print("=== H2(구분선 가설) 검정 가능성 ===")
print(f"  확증 SELECTION {len(conf_sel)}건 / 문항 {len({u['qid'] for u in conf_sel})}개 "
      f"/ 기준서 {len({frozen[u['qid']].get('standard') for u in conf_sel})}종")
print(f"  확증 CONJUNCTIVE {len(conf_conj)}건 / 문항 {len({u['qid'] for u in conf_conj})}개 "
      f"/ 기준서 {len({frozen[u['qid']].get('standard') for u in conf_conj})}종")
print(f"  -> Phase 1은 선택규칙 근거가 코퍼스 전체에서 문단 1개(1019.103)라 검정 불가였음.")
print(f"     기준서 2종 이상이면 '암기가 아닌 규칙'을 처음으로 시험할 수 있다.")

cost = len([u for u in conf if u["n_siblings"] >= 1]) * 2 * 3
print(f"\n=== 비용 (확증 집합 주검정만) ===")
print(f"  {len([u for u in conf if u['n_siblings']>=1])}건 × 2조건 × 3판 = {cost:,}콜")

out = GATE / "phase3_split.json"
out.write_text(json.dumps({
    "generating_qids": sorted(seen_qids),
    "n_units_total": len(units),
    "confirmatory": {
        "n": len(conf),
        "siblings": len([u for u in conf if u["n_siblings"] >= 1]),
        "solo": len([u for u in conf if u["n_siblings"] == 0]),
        "by_rule": dict(Counter(u["rule_type"] for u in conf if u["n_siblings"] >= 1)),
    },
    "exploratory": {
        "n": len(expl),
        "siblings": len([u for u in expl if u["n_siblings"] >= 1]),
        "solo": len([u for u in expl if u["n_siblings"] == 0]),
    },
    "units": units,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nsaved: {out.name}")
