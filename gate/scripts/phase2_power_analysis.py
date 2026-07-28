"""How many labels do we actually need? Measured, not guessed.

Two questions the current n=54 could not answer:
  Q1. Recall difference (70% vs 90%) — what n is needed to call it?
  Q2. Probe precision (14.3%) vs base rate (6.8%) — what n to call the lift?
Also reports the clustering problem: effective sample size is answers, not claims.
"""
import random
from math import sqrt

random.seed(20260728)

# --- current state ------------------------------------------------------
N_CLAIMS, N_PROBLEMS, N_ANSWER_CLUSTERS = 54, 10, 8
print("=== 현재 상태 ===")
print(f"주장 {N_CLAIMS}건 / 문제 {N_PROBLEMS}건 / 문제가 걸친 독립 답변 {N_ANSWER_CLUSTERS}개")
print(f"회수율 1건 = {1/N_PROBLEMS:.0%}p  <- 이게 90% vs 70%의 정체")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


print("\n=== Q1. 회수율 90% vs 70%의 신뢰구간 (Wilson 95%) ===")
for label, k in (("per-claim 90%", 9), ("answer-ctx 70%", 7)):
    lo, hi = wilson(k, N_PROBLEMS)
    print(f"  {label}: {k}/{N_PROBLEMS} -> [{lo:.1%}, {hi:.1%}]")
lo9, hi9 = wilson(9, N_PROBLEMS)
lo7, hi7 = wilson(7, N_PROBLEMS)
print(f"  구간 겹침: {'예 -> 구별 불가' if lo9 < hi7 else '아니오'}")

# n needed so that 90% vs 70% no longer overlap
need = None
for n in range(10, 400):
    if wilson(round(0.90 * n), n)[0] > wilson(round(0.70 * n), n)[1]:
        need = n
        break
print(f"  -> 두 회수율을 구간 비겹침으로 구별하려면 문제 사례 약 {need}건 필요")

# McNemar-style paired power for the recall gap (discordant pairs)
print("\n=== Q1b. 쌍대 McNemar 검정력 (같은 문제 사례, 두 설정) ===")
print("  관측된 불일치쌍: 2건 (per-claim만 잡은 Q068-A-c1, c2)")
print("  McNemar 정확검정 p = 2^-2 * 1 = 0.5 -> 유의 불가")
for d in (2, 5, 6, 8, 10):
    p = 0.5 ** d * 2  # one-sided all-discordant-same-direction, x2 for two-sided
    print(f"    불일치쌍 {d:>2}건이 전부 한 방향이면 양측 p={min(1,p):.4f}"
          f" {'✅ 유의' if p < 0.05 else ''}")

print("\n=== Q2. 프로브 정밀도 14.3% vs 기저율 6.8% ===")
lo, hi = wilson(2, 14)
print(f"  현재: 2/14 = 14.3% -> [{lo:.1%}, {hi:.1%}] (기저율 6.8% 포함 -> 리프트 미확정)")
need2 = None
for n in range(10, 600):
    if wilson(round(0.143 * n), n)[0] > 0.068:
        need2 = n
        break
print(f"  -> 리프트를 확정하려면 프로브 YES가 약 {need2}건 필요 "
      f"(YES율 {14/44:.0%} 가정 시 라벨 주장 약 {round(need2/(14/44))}건)")

print("\n=== Q3. 진짜 병목: 군집화 (독립 단위는 주장이 아니라 답변) ===")
print(f"  문제 10건이 답변 8개에 분포. 프로브가 잡은 2건은 답변 1개(Q068-A)에서 나옴.")
print("  -> 주장 수를 늘려도 같은 답변에서 늘면 독립 정보가 안 늘어난다.")
print("  -> 확장 설계의 1순위는 '주장 수'가 아니라 '문제를 가진 서로 다른 답변 수'.")

print("\n=== 권고 표본 (위 계산 종합) ===")
print(f"  문제 사례 목표: {need}건 이상 (현재 10건)")
print(f"  그 문제가 걸친 서로 다른 답변: 25개 이상 (현재 8개)")
print("  기저율 18.5% 유지 가정 시 총 라벨 주장 수 ≈ 250~300건 (현재 54건)")
print("  스킬 probe-graph evals.md 기준(N=80→검정력 0.797)과도 정합: 문항 단위 80+")
