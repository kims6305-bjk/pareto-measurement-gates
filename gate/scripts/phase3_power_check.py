"""Phase 3 검정력 사전 점검 — 확증 집합이 H1/H2를 실제로 검정할 수 있는가.

사전 선언(PHASE3_PREREGISTRATION.md) 커밋 전에 돌린다. Phase 2의 교훈은
"필요 표본을 실행 전에 계산하지 않으면 라벨/콜을 태우고 나서 판정 불가를 안다"였다.
"""
import json
import math
from collections import Counter
from pathlib import Path

GATE = Path("/Users/bjkim/.openclaw/workspace/projects/probe-graph-public/gate/scripts")
split = json.load(open(GATE / "phase3_split.json", encoding="utf-8"))
conf = [u for u in split["units"] if u["set"] == "confirmatory" and u["n_siblings"] >= 1]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


print("=== H1 (주가설): McNemar 쌍대 검정 ===")
print(f"확증 집합 형제 보유 주장 {len(conf)}건 (쌍대이므로 각 건이 A/B 쌍)")
for m in (5, 6, 8, 10, 15):
    p = 2 ** (-m)
    print(f"  불일치쌍 {m:2d}건이 전부 한 방향 -> 양측 p = {p:.4f} "
          f"{'✅ 유의' if p < 0.05 else ''}")
print("  Phase 1 실측: 형제 있는 오탐 9건이 문맥 제공 시 9/9 뒤집힘")
print("  -> 그 정도 효과가 재현되면 불일치쌍은 충분. H1은 검정력 문제 없음.")
print()

sel = [u for u in conf if u["rule_type"] == "SELECTION"]
conj = [u for u in conf if u["rule_type"] == "CONJUNCTIVE"]
n_sel, n_conj = len(sel), len(conj)
q_sel = len({u["qid"] for u in sel})
q_conj = len({u["qid"] for u in conj})

print("=== H2 (구분선 가설): 두 비율의 Wilson 구간 비겹침 ===")
print(f"확증 CONJUNCTIVE {n_conj}건 (문항 {q_conj}개) vs SELECTION {n_sel}건 (문항 {q_sel}개)")
print()
print("가정: CONJUNCTIVE 뒤집힘률이 높고 SELECTION은 낮다. 어느 조합에서 구간이 갈리나?")
sep = []
for pc in (0.9, 0.8, 0.7, 0.6):
    for ps in (0.0, 0.1, 0.2, 0.3):
        lo_c, _ = wilson(round(pc * n_conj), n_conj)
        _, hi_s = wilson(round(ps * n_sel), n_sel)
        ok = lo_c > hi_s
        if ok:
            sep.append((pc, ps))
        print(f"  CONJ {pc:.0%} (하한 {lo_c:.2f}) vs SEL {ps:.0%} (상한 {hi_s:.2f}) "
              f"-> {'✅ 비겹침' if ok else '겹침'}")
print()
if sep:
    worst = min(sep, key=lambda x: x[0] - x[1])
    print(f"  -> 구간이 갈리는 최소 격차: CONJ {worst[0]:.0%} vs SEL {worst[1]:.0%} "
          f"(격차 {worst[0]-worst[1]:.0%}p)")
    print(f"     즉 H2를 채택하려면 두 규칙유형의 뒤집힘률이 최소 이만큼 벌어져야 한다.")
else:
    print("  -> 어떤 조합에서도 구간이 갈리지 않는다. H2는 이 표본으로 검정 불가.")
print()

print("🔴 === 군집화 경고 (Phase 1이 무너진 바로 그 원인) ===")
print(f"  확증 CONJUNCTIVE {n_conj}건이 문항 {q_conj}개에만 분포 "
      f"(문항당 {n_conj/max(1,q_conj):.1f}건)")
qc = Counter(u["qid"] for u in conj)
print(f"  문항별: {dict(qc)}")
print(f"  확증 SELECTION {n_sel}건 / 문항 {q_sel}개: {dict(Counter(u['qid'] for u in sel))}")
print()
print("  독립 단위는 주장이 아니라 문항이다. 문항 3개에서 나온 24건을 독립 표본처럼")
print("  다루면 Phase 1의 과적합(선택규칙 근거가 문단 1개)을 반복하는 것이다.")
print("  -> H2는 주장 단위 비율이 아니라 **문항 단위**로도 병기 보고해야 하며,")
print("     문항 수가 이토록 적으면 '판정 불가'가 정직한 결론일 수 있다.")

solo = split["confirmatory"]["solo"]
print(f"\n🔴 === 음성 대조군 경고 ===")
print(f"  확증 집합 단독 주장 {solo}건 — 노이즈 하한 추정에 너무 적다.")
print(f"  탐색 집합 단독 {split['exploratory']['solo']}건을 합쳐도 "
      f"{solo + split['exploratory']['solo']}건.")
print(f"  -> 음성 대조군은 확증/탐색 구분 없이 전량 사용하고, 그 사실을 명시한다.")
print(f"     (대조군은 가설 검정이 아니라 노이즈 측정이므로 순환 논증 위험이 없다.)")

out = GATE / "phase3_power_check.json"
out.write_text(json.dumps({
    "confirmatory_siblings": len(conf),
    "conjunctive": {"claims": n_conj, "questions": q_conj,
                    "per_question": dict(qc)},
    "selection": {"claims": n_sel, "questions": q_sel,
                  "per_question": dict(Counter(u["qid"] for u in sel))},
    "h2_min_gap": ({"conj": sep and min(sep, key=lambda x: x[0]-x[1])[0],
                    "sel": sep and min(sep, key=lambda x: x[0]-x[1])[1]}
                   if sep else None),
    "negative_control_solo_confirmatory": solo,
    "negative_control_solo_all": solo + split["exploratory"]["solo"],
    "warning": "H2의 독립 단위는 문항이며 확증 CONJUNCTIVE는 문항 3개뿐 — 군집화 위험",
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nsaved: {out.name}")
