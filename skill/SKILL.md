---
name: probe-graph
description: "'프로브 그래프'·'리플렉션 프로브'·답변 자기검증 요청 시 — QA봇 검증 서브그래프 배선."
usage_hint: "적용 전 references/probe-prompts.md의 앵커 확인. 라이브 봇 이식은 라이브 반영 절차 + 섀도우 배포 절차 절차 준용. 실측 통과 전 '효과 있다' 단정 금지."
tags: [reflection-probe, verification, rag, citation, graph-engineering, quality-gate]
related_skills: [섀도우 배포 절차, skill-design-standard, pareto-optimization-gate]
---

# Probe-Graph — 리플렉션 프로브 검증 서브그래프

인용 기반 QA 파이프라인(근거 문서를 인용하는 RAG 봇)에 꽂는 **검증 서브그래프**.
답변 생성 후 프로브 노드가 근거 대조를 수행하고, 조건부 엣지로 수정/통과/사람-라우팅을 분기한다.

**혈통**: Anthropic "Verbalizable Representations Form a Global Workspace" (2026)의
counterfactual reflection을 프롬프트 레벨로 번역 + 검증문헌 8편(CoVe, Huang, FBC/EIR,
Self-Refine, SelfCheckGPT, 캘리브레이션 2편, Reflexion)의 실측 수치로 앵커 설계.
근거 전문 = workspace의 `reflection_probe_문헌정리.md` / `reflection_probe_구현설계.md` /
`counterfactual_reflection_정리.md`.

## 0. 대원칙 (어기면 실증적으로 해로움)

1. **순진한 프로브 금지.** "틀린 곳 찾아라"·"오답일 수 있다고 가정하라"는 모든 문헌에서
   정답→오답 전환이 오답→정답보다 많았다 (Huang: 최대 −9.5pp). 프로브는 반드시
   §2 앵커를 경유해 설계한다.
2. **개념은 그래프, 구현은 기존 파이프라인.** LangGraph 등 프레임워크 신규 도입 금지 —
   기존 봇 코드(answer.py 등)에 노드 함수로 얹는다.
3. **프로브 통과율을 성공 지표로 쓰지 않는다** (Goodhart/프로브 게이밍 방지,
   Obfuscation Atlas ICML 2026). 성공 판정은 항상 외부 ground truth
   (원문 대조 인용오류율)로만. 프로브 지적 건수를 줄이는 방향의 프롬프트 튜닝 금지.
4. **실측 전 효과 단정 금지.** Claude 계열은 이미 자기교정 비열화 그룹(EIR≈0.2%)이라
   P2 앵커는 "이득"이 아니라 "보험"일 수 있다. §4 게이트 통과 후에만 "효과 있다"고 말한다.

## 1. 그래프 구조

### 메인 그래프 (조건부 3단계 — 기본형)

```
                    ┌─────────────────────────────────────┐
                    │  needs_revision=false (대부분 경로)  │
                    ▼                                     │
[question]──→(answer)──→(probe P1)──┤
  +RAG docs    초안+주장리스트  인용대조     │
                                    │ needs_revision=true
                                    ▼
                              (revise)──→(probe 재검증)──→[출력]
                               지적항목만        │
                               수정, 캡=1        │ 여전히 불일치
                                                ▼
                                          [사람 라우팅]
```

- **(answer)**: RAG 근거 + 질문 → 초안 + 원자적 주장/인용 리스트
- **(probe P1)**: 초안 산문은 **넣지 않는다** — 주장 리스트 + 근거 원문만 (CoVe factored:
  자기 환각 재확인 경로 차단, FACTSCORE 55.9→71.4의 핵심)
- **조건부 엣지**: probe JSON의 `needs_revision`. false면 2콜로 종료 (비용 절감)
- **(revise)**: probe가 지적한 항목**만** 수정. 나머지 문장 원문 유지 (정답 바꾸는 변경 차단)

### 루프 불변식 — 캡=1

```
(revise)──→(probe 재검증)──→ PASS → 출력
    ▲              │
    └──── ✕ ───────┘  재수정 루프 금지 (캡=1)
                   │
                   └─ FAIL → 사람 라우팅 (P3 출력 동봉)
```

**루프를 돌리지 않는 근거**: 동일 3콜 예산에서 Self-Consistency 93.4% > 3-iter refine 86.6%
(FBC Table IV). 반복 refine은 손해. 재검증 1회 실패 = 모델이 못 고치는 문제 → 사람에게.

### 경량 그래프 (지연시간 제약 경로 — P2 단일 호출)

```
[question]──→(answer + P2 verify-first 앵커 내장)──→[출력]
```

시스템 프롬프트에 P2 앵커 삽입. 다운사이드 실증적 0 (FBC: 해로운 모델에서 +6.4pp
McNemar p<10⁻⁴, 이미 안전한 모델에선 p=1.0 무변화) → **실시간 경로엔 무조건 넣는다.**

### 사람 라우팅 그래프 (P3 — EIR 구조적 0)

```
[기존 답변]──→(probe P3: 수정권한 없음)──→ risks=[] → 통과
                        │
                        └─ risks 1건+ → [아침 보고/사람 검토 큐]
```

P3는 답을 절대 안 고치므로 과교정 위험이 구조적으로 0. **harness-audit-loop 야간 cron에
바로 꽂아도 안전한 유일한 프로브.** Anthropic 논문의 BUT-갭(내부 이의는 있는데 행동 미반영
88%)을 출력으로 꺼내는 노드가 이것.

## 2. 앵커 7종 (프로브 프롬프트 필수 부품)

전문과 근거 수치는 `references/probe-prompts.md`. 요약:

| # | 앵커 | 한 줄 근거 |
|---|---|---|
| A1 | "이미 정확할 가능성이 높다고 전제하라" | "오답 가정" 문구가 최악 −3.5 (Huang T5) |
| A2 | "수정 전 먼저 근거를 독립적으로 재확인" | FBC verify-first 부품 ①② |
| A3 | "구체적·특정 가능한 오류만 수정, 그 외 '수정 불필요'" | EIR 2%→0%를 만든 핵심 부품 ③ |
| A4 | "근거 없으면 '근거 없음' 표시, 다른 내용으로 바꾸지 마라" | Self-Refine 실패 61%가 부적절 수정 |
| A5 | "'문제 찾기'가 아니라 '근거 일치 확인'이 과제" | "find the problems" −9.5 폭발 (CSQA) |
| A6 | "예/아니오 판정 금지, 원문 발췌 강제" | yes/no 검증질문은 동조 편향 (CoVe T4) |
| A7 | "확신도는 상/중/하 + 후보 2개까지" | top-2가 단일 숫자보다 캘리브레이션 우수 |

**회계/세무 도메인 경고**: 유사 조문·유사 세율 distractor가 널려 있어 CSQA형 위험
프로파일(−9.5 쪽). A5 생략 금지.

## 3. 프로브 3종 선택 기준

| 프로브 | 노드 위치 | 수정권한 | EIR 위험 | 쓰는 곳 |
|---|---|---|---|---|
| P1 인용대조 | 메인 그래프 probe | 간접(revise 트리거) | 낮음(앵커로 억제) | 배치/비실시간 답변 |
| P2 verify-first | answer 내장 | 자기 자신 | 실증 0 | 실시간 채팅 경로 |
| P3 위험열거 | 사후 감사 | **없음** | **구조적 0** | 야간 감사 루프, 사람 라우팅 |

프롬프트 전문 = `references/probe-prompts.md`. 도입 순서 권장: **P3(무위험) → P2(보험) →
P1(실측 통과 후)**.

## 4. A/B 실측 게이트 (합격 전 "효과 있다" 선언 금지)

이진 게이트 전문 = `references/evals.md`. 골자:

- **표본**: 80~100문항 (N=30은 검정력 0.19로 실험 무의미. N=80 → 0.797, N=100 → 0.896)
- **검정**: 쌍대 McNemar (같은 문항, 프로브 유/무)
- **지표 3종**: 인용오류율(주지표) / 답변정확도(가드레일: 비열화) / 과교정율(정답→오답 전환,
  가드레일: ≤0.5% — EIR 임계)
- **판정은 기계적**: 주지표 유의 개선 + 가드레일 2종 통과 = 채택. 하나라도 실패 = 해당
  프로브 폐기(P3 제외 — P3는 라우팅 정밀도로 별도 평가)
- 평가 문항·채점기는 실험 중 수정 금지 (skill-design-standard 실험 불변식)

## 5. 이식 절차 (운영 QA 봇 기준)

1. 섀도우 환경 준비 — 섀도우 배포 절차 절차 준용 (라이브 무접촉)
2. P3부터: 기존 답변 로그 표본에 P3 실행 → 위험 열거 품질을 눈으로 검수 (프로브 자체 QA)
3. A/B 80문항: 공시/공개 기준서 기반 문항만 (회사 내부숫자 금지 — 데이터경계)
4. 게이트 통과 프로브만 라이브 반영 절차로 라이브 반영 (저자 승인 필수)
5. 기존 citation_audit과 역할 분담 명시: audit=인용 실존(사후), P1=인용 의미 일치(생성시)

## 실측 판정 기록 (2026-07-28 — K-IFRS 119문항 A/B 완료)

**P1 폐기 확정.** evals.md ② 게이트 실측 (FROZEN 119문항: normal 84/no_answer 17/
distractor 18, claude CLI 양 arm 동일 모델·동일 날, 블라인드 저지):
- 주지표 인용오류율: **양 arm 모두 0%** (McNemar p=1.0) — Claude+근거 동봉 구조에선
  P1이 잡을 오류가 애초에 없음 (대원칙 4의 실측 확인. distractor 함정 오인용도 0건)
- 가드레일2 과교정: **1/119 (0.84%) > 임계 0.5%** — Q092에서 EIR 실측 재현:
  P1이 "evidence 밖 실무 추론" claim을 근거없음 판정 → revise가 규칙대로 hedging →
  첫 문장과 모순되는 답으로 열화 (draft ✓ → final ✗). 프로브·revise 각자 규칙을
  지켰는데 조합이 열화시킨 사례.
- 교훈: **오류율 0% 시스템에 검증 레이어 = 상방 0, 하방만 존재 (순비용).**
  P1 재도입 검토는 "생성 모델이 인용오류를 실제로 내는" 환경(비-Claude, 근거 미동봉,
  파라메트릭 인용 허용)에서만. P3(무수정)·P2(앵커)는 이 판정과 무관하게 유효.
- 판정 전문: workspace `probe_graph_test/AB_VERDICT.md`
- 공개 레포: 이 저장소 (MIT, README 한/영/중)

## P3 야간 감사 배선 (2026-07-28 — 판정 후속 반영, 라이브)

- **cron**: job_id `af40b95442f2`, "P3 야간 감사 (운영 QA 봇 답변 리플렉션 프로브)",
  `30 21 * * *`(매일 21:30), no_agent(스크립트 stdout 그대로 배달, risks 0건=무음), deliver=origin.
- **wrapper**: `<agent-home>/scripts/probe_p3_audit.sh` → 정본
  `workspace/scripts/probe_p3_audit.py` (harness-audit-loop wrapper 패턴, 복사본 없음).
- **동작**: 운영 QA 봇의 발송 로그 `data/<bot>/sent/*.json` 최근 26h에서 미검사분
  최대 6건 → draft_answer+citations(상위 6청크·1200자 캡)를 P3 프롬프트(references/
  probe-prompts.md 정본, 앵커 불변)에 넣어 claude CLI 실행 → risks만 메신저 보고.
- **상태**: `data/harness_audit/p3_audit_state.json`(done_files 최대 500). 상세 JSON은
  무음이어도 `data/harness_audit/p3_reports/p3_날짜.json`에 항상 남김. 실패 파일은
  done 미기록 → 다음 밤 재시도.
- 첫 실측(07-28): sent 1건 검사 → risks 3건 검출(부가세법 §8 사업장별 등록 원칙 관련
  근거없음 지적 — P3가 실제 위험을 잡는 것 확인). cron run 게이트 통과(last_status ok).
- 🔴 대원칙 3 그대로 적용: 이 리포트의 지적 건수로 봇 프롬프트 튜닝 금지(Goodhart).
  P3 출력은 관찰·사람 검토 전용, 자동수정 배선 금지.
- 제2 QA 봇은 sent 저장 구조가 없어(state.json만) 미배선 — 편입하려면 발송 로그 저장부터.

## 함정/교훈

- **프로브 게이밍(Goodhart)**: "프로브 지적 0건"을 목표로 시스템 프롬프트를 튜닝하면
  답이 정직해지는 게 아니라 프로브를 피하는 방향으로 최적화된다 (Obfuscation Atlas의
  정책 난독화와 동형). 지적 건수는 관찰 지표일 뿐, 최적화 대상 금지.
- **파라메트릭 인용 금지의 근거**: LLM 기억용량은 파라미터당 ~3.6비트로 유한
  (Morris et al., ICML 2026) — 조문 번호를 기억에서 꺼내면 틀린다. 인용은 반드시
  RAG 원문 발췌 경유 (A6).
- **프롬프트는 다이얼, 데이터는 레버**: 프로브 문구 튜닝으로 안 뚫리면 근거 검색
  커버리지(RAG) 문제일 가능성 — pareto-optimization-gate 참조.
- 문헌 수치는 영어·수학/상식 QA 기준. 한국어 회계/세무 도메인 전이는 미검증 —
  그래서 §4 게이트가 필수다.
- **판정 필드는 코드로 유도하라 (2026-07-28 스트레스테스트 실측)**: P1의
  `needs_revision`을 모델이 채우게 하면 verdict="근거없음"을 정확히 잡고도
  needs_revision=false로 내는 케이스가 나온다 (프롬프트 주석 누락 시 10케이스 중 1회
  재현). 구현 시 분기 판정은 모델 필드를 믿지 말고 파이프라인 코드에서
  `needs_revision = any(verdict != "일치")`로 유도할 것. 모델 출력 JSON의
  needs_revision은 참고값으로 강등.
