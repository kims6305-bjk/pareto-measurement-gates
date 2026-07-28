# 의미 레이어 재채점 — 238건 전수 (2026-07-28)

기존 기계 채점기(문단번호 집합 위주)가 의미 불일치를 못 잡는다는 외부 리뷰 지적에 대응해,
238건(119문항 × A/B) 전수를 claim 단위 LLM 저지로 재채점했다.

- 스크립트: `scripts/semantic_regrade.py` (재개 가능, fail-closed)
- 저지: `claude-sonnet-4-6` (정확한 모델 ID 고정, alias 미사용) — `scripts/semantic_regrade_manifest.json`
- 저지 원문·사유 전문: `scripts/semantic_regrade_judgments.jsonl` (238행, claim별 rationale + raw 출력)
- 요약: `scripts/semantic_regrade_summary.json`

## 집계

| 판정 | armA | armB |
|---|---|---|
| VERIFIED | 93 | 93 |
| ABSTAIN_OK | 17 | 17 |
| FLAGGED | 9 | 9 |

## FLAGGED 18건 전수 원문 대조 (사람 검토)

저지 rationale + ab_results.json 원답변 + FROZEN 근거 문단을 3자 대조한 결과:

**진짜 의미오류(답변이 기준서와 상충): 0건.**

| 분류 | 건수 | 사례 | 원인 |
|---|---|---|---|
| 저지 오탐 — claim 고립 채점 | 14 | Q014·Q033·Q042·Q043·Q047·Q049·Q068·Q069·Q071·Q081 | 답변은 "A와 B를 모두 차감/충족"으로 완전한데, claim 추출이 접속 규칙을 c1="A", c2="B"로 분해. 저지가 각 claim을 **답변 컨텍스트 없이 고립 채점**하여 "누락→CONTRADICTED" |
| claim 추출 불량 | 1 | Q082B c3 | claim 텍스트 자체가 "제공된 자료에서 확인되지 않음"(명제 부재)이라 저지가 모순으로 오독 |
| 근거범위 초과 (저지 판정 타당) | 3 | Q087A·Q107A·Q118A | 회계적으로는 옳은 서술이나 **제공된 근거 문단이 지지하지 않는 주장** (예: 정의는 문단 15에 있는데 근거는 문단 32만 동봉). 인용 게이트가 잡아야 할 바로 그 유형 |

## 결론

1. **A/B 판정 불변** — FLAGGED가 A 9 / B 9 완전 대칭(같은 문항 쌍이 양 arm에서 걸림).
   P1 무익 결론은 의미 레이어에서도 유지된다.
2. 주지표 표현 교체: "인용오류 0%" → **"구조·주소·인용 오류 0 + 의미상 상충 0 +
   근거범위 초과 3/238(1.3%)"**. 의미상 상충 0/238의 95% CI 상한(~1.3%, rule of three)을
   명시하고 점 추정 과신을 제거.
3. 저지 자체의 한계 실측: 오탐 15/18의 단일 원인은 **claim 고립 채점**.
   후속 실험에서는 저지 프롬프트에 전체 답변 + 형제 claim을 컨텍스트로 동봉해야 한다.
   (이 오탐률 데이터가 Phase 1 저지 P/R 측정의 실증 근거)

재현: `.venv/bin/python scripts/semantic_regrade.py` (완료분 자동 스킵)
