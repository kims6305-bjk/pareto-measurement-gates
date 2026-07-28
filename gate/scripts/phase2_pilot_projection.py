"""파일럿 기저율의 불확실성과 그 함의를 계산한다.

열람 화이트리스트(PHASE2_INTERNAL_PILOT.md §1.1) 내 항목만 사용한다.
프로브·저지 출력은 참조하지 않는다.
"""
import json
import math
from pathlib import Path

GATE = Path("<repo>/gate/scripts")
br = json.load(open(GATE / "phase2_pilot_baserate.json", encoding="utf-8"))

k, n = br["n_problems"], br["denominator"]
p = k / n
POOL = br["n_max_pool"]
TARGET = br["target_problems"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


lo, hi = wilson(k, n)
print("=== 파일럿 기저율 (n=30) ===")
print(f"문제 사례 {k}/{n} -> p̂ = {p:.3f}  (Wilson 95% CI [{lo:.3f}, {hi:.3f}])")
print(f"Phase 1 기저율 18.5%와 비교: Phase 1은 '저지가 시비 건 건 전수 + VERIFIED 표본'")
print(f"  이라는 편향 추출이었고, 이번은 무작위 추출 -> 기저율이 낮게 나오는 것이 정상.")
print()

print("=== 후보 풀 전량(201건)을 다 라벨하면 문제 사례 몇 건인가 ===")
for label, pp in (("점추정 p̂", p), ("CI 하한", lo), ("CI 상한", hi)):
    exp = pp * POOL
    print(f"  {label:8s} p={pp:.3f} -> 기대 문제 {exp:5.1f}건  "
          f"(목표 {TARGET}건 대비 {exp/TARGET:.0%})")
print()

print("=== 목표 55건을 채우려면 몇 건을 라벨해야 하는가 ===")
for label, pp in (("점추정", p), ("CI 상한(가장 낙관)", hi)):
    need = math.ceil(TARGET / pp) if pp > 0 else float("inf")
    print(f"  {label:18s} -> {need:,}건 필요 (후보 풀 {POOL}건의 {need/POOL:.1f}배)")
print()

print("=== 판정 ===")
exp_pool = p * POOL
print(f"후보 풀을 전량 소진해도 기대 문제 사례는 {exp_pool:.1f}건으로 목표 {TARGET}건에")
print(f"크게 미달한다. 즉 **Phase 2를 원안대로 끝까지 밀어도 회수율 90% vs 70%를")
print(f"구간 비겹침으로 구별할 수 없다**. 이것은 파일럿이 실패한 것이 아니라,")
print(f"파일럿이 정확히 잡아내라고 설계된 신호다(라벨 171건을 태우기 전에 드러났다).")

out = GATE / "phase2_pilot_projection.json"
out.write_text(json.dumps({
    "base_rate": round(p, 4),
    "wilson95": [round(lo, 4), round(hi, 4)],
    "pool": POOL,
    "target_problems": TARGET,
    "expected_problems_at_pool": round(exp_pool, 1),
    "expected_problems_at_pool_ci": [round(lo * POOL, 1), round(hi * POOL, 1)],
    "labels_needed_point": math.ceil(TARGET / p) if p > 0 else None,
    "labels_needed_optimistic": math.ceil(TARGET / hi) if hi > 0 else None,
    "verdict": "후보 풀 전량으로도 목표 미달 — 원안 완주는 파레토상 열등",
    "note": "효과 지표(프로브/저지 출력) 미참조. 화이트리스트 §1.1 준수.",
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nsaved: {out.name}")
