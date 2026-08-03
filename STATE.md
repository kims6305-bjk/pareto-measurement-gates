# STATE — reflection-probe-gate

세션 시작 시 이 파일을 먼저 읽는다. 상한 100줄, 아카이브 아닌 다이제스트.
상세는 각 정본 문서 참조(복붙 금지).

## 현재 위치

- **Phase 1·2·3 전부 종결.** 판정은 각 정본에 — `gate/PHASE{1,2,3}_VERDICT.md`
  요약: P1 판정불가 / P2 표본부족 종결(171건 라벨 안 함) / P3 1,650콜 완주했으나
  🔴 조건 A 문제판정 0건이라 H1을 검정하지 못함.
- **계기 검침 PASS** — 저지는 정상이었다(recall 81.8%, SPLIT 0). `gate/INSTRUMENT_CHECK_RESULT.md`
- **옆방 검증 2/2 PASS** — SciFact·KLUE-NLI recall 100%. `gate/SIDECHECK_RESULT.md`
- **🆕 파레토 메타하네스 — 🔴 V6 종결 (IC-1 FAIL, 운영자 결정).** 판정 정본
  `gate/PARETO_MH_VERDICT.md`. IC-0 PASS(165콜) → IC-1 FAIL(330콜) — precision 축
  방향은 정확(loose 0.643>c000 0.583>strict 0.500)하나 ci_qid 전부 겹침 = n=55 검정력
  부족. 탐색 1,650콜 미사용, 총 495콜 종결. **330콜 검침이 1,650콜 손실을 차단** = 논문 소재.
  커밋: `7d7d28b` 설계 → `5df830a` 판정기 → `bfef1cd` 사전등록 → `e325770` 문헌 6소스
  → `beacac4` **부속서1**(U3·U4·U8·U12·U13 해소) → `125fdd8` **러너+가드+c000 등록**.
  정본 `gate/PARETO_META_HARNESS_DESIGN.md` · `PREREG.md` · `PREREG_ADDENDUM1.md`
  신규 실물: `mh_guard.py`(INV-2/3 매니페스트, PASS 실측) · `mh_run_candidate.py`
  (sha 대조·resume·fail-closed 실측) · `mh_archive_C2.jsonl`(c000, prompt_sha ce0239b9…)
  · `mh_front.py`에 REJECTED_C0 추가(테스트 32/32 유지).
- **Phase 4 = 다목적 채택 게이트.** `gate/PHASE4_PREREGISTRATION.md` DRAFT.
  §3의 3축은 파레토 설계 §3에서 **2축(recall, precision)으로 개정**됨.
- 마지막 활동 2026-08-03. git clean. 🔴 **push 금지 상태** — 익명화(설계 문서
  절대경로·식별자, 부속서1·본 항목 포함). 처리 절차는 설계 §13.4.

## 결정 누적

Phase 1·2 결정(1~10)은 각 정본에 전문 보관. 여기엔 이후에도 영향 주는 것만.

- **Phase 1 라벨 55건은 불변** — 재라벨·삭제 금지. 재생성 불가한 정답지.
- **확증/탐색 분리** — 가설 생성 표본을 확증 집합에서 제외(순환 논증 차단). 13번의 원인.

11. **🔴 검정력은 표본 크기가 아니라 결과변수 기저율에 대해 계산한다 (P3 실패)** —
   분모는 세고 분자를 안 쟀다. → 이후 모든 실험은 **본 실행 전 계기 검침**이 요건.

12. **계기 검침이 내 진단을 기각했다** — "저지 고장" 가설은 틀렸고 저지는 정상이었다.
   검침 없이 고쳤다면 멀쩡한 도구를 고치고 개선이라 보고할 뻔했다. 비용 165콜/15분.

13. **🔴 진짜 원인 = 순환 논증 차단이 신호를 전량 제거** — Phase 1 문제 문항 28개가
   전부 탐색(제외) 집합에 갔다. 설계 부주의가 아니라 **두 규율의 충돌**.
   → 해법은 제외 포기가 아니라 **제외 후 기저율 확인**.

14. **축 분리: 회수율은 언어에 둔감, 정밀도는 민감** — 오탐률 SciFact 36.4% vs KLUE 3.0%.
   문제를 **놓치는** 실패는 두 언어 0. 어느 쪽이 옳은지는 미해결.

15. **🔴 문헌 대조 — front를 부모 선택에 쓰는 규칙은 harness 자기개선 계층에 없다**
   (2026-07-31 4소스 → 2026-08-03 **6소스로 갱신·문구 좁힘**, 정독본 `<workspace>/tmp/meta_src{1..6}.md`)
   - Self-Harness: 판정식 있음, front 없음. Meta-Harness: front 있음, 판정식·부모규칙 없음.
   - **src5 MOT-SR**(수식발견): front-as-parent **실제 구현** (SyntaxDiv→softmax 부모샘플링).
     단 그 규칙 자체 ablation 없음, 사전등록·통계검정·시드반복 전무 →
     타 도메인 독립 지지 증거이자, **우리 C1 vs C2 대조가 문헌에 없는 측정**임을 보존.
   - **src6 TRACE-Router**(라우팅): front는 사후 문법 전용(스칼라화·α별 정책 격리).
     이식 2건 — 귀속 처방("결정 입자를 감독 단위까지 굵게"), front 점유 주장에는
     무작위 혼합 대조군 필요("random mixture also traces the line segment").
   - 배경 소스(설계문서 미편입): Anthropic harness 블로그, Graph Engineering(Kasana,
     경험재사용하되 선택규칙 부재), BM25-at-scale 2607.26497(스케일 교차·단순함이 front 점유),
     quantization 2607.29397(계측 축 오류), Safety-Gated 2607.27849(조건사다리·regime map),
     SPDP 2607.21985. DP 단계론(프롬프트→하네스→루프→그래프) = 메모이제이션 유추.

16. **🔴 precision을 축으로 올린 것이 이 설계의 핵심 판단** — 단일축(recall)이면
   "전부 CONTRADICTED 찍는 가짜 후보"가 1등을 먹는다. 코드로 실증됨:
   `test_negative_control_all_contradicted_cannot_monopolize_front` (32/32 통과).
   elapsed는 **A/B 모두 4.60s 동률 실측**으로 축에서 기각(P4 §3의 비용축 가정이 틀렸음).

## 세션 연속성

**멈춘 지점** (2026-08-03 오후): **c000 측정·채점·front 완료.**
- 3판×55=165콜 완료 → 원자료 커밋(`a6d84e8`, INV-5 열람 전 커밋) → `mh_objectives.py` 채점
  → 원장 갱신+front(`dab23c4`).
- **c000 = recall 0.6364 [ci_qid 0.3844,1.0] / precision 0.5833 [0.25,0.9168]** —
  🔴 **IC-0 검침 기준(recall ≥ 30%) PASS** (사전등록). sample_gate passed, front={c000}, 누적콜 165.
- 원장 = `mh_archive_C2.jsonl`(2행: 등록→측정), front 캐시 = `mh_front_C2.json`.
- ⚠️ 정답지는 `phase1_human_label_sheet.xlsx` 「라벨링」 시트 G열 (phase2 json은 human_label 빈 파일 — 헷갈리지 말 것).
- **IC-1 실행·판정 완료 → V6 종결** (러너 `mh_ic1_negative_control.py` 실행 전 커밋
  `f433eba` → 원자료 `27b0ea2`). 단일 변인 검증(JUDGE만 차이) 통과. 재개 조건
  (라벨 표본 확대 → IC-1 재실행부터)은 VERDICT §후속 라운드 조건.

**바로 집어들 액션 1개**: **논문/사례글 집필** — 실행 결과가 나왔으므로 해금.
서사 축 = "검침 3종(IC-0/1/2)이 자격 없는 탐색을 막았다" + 결정 15(문헌 빈자리) +
V6 실측. push 전 익명화 13건 처리 필수(§13.4). 탐색 재개는 라벨 확대가 선행.

**병행 트랙 (이번 세션 완료분)**:
- 문헌 6소스 체제 — 결정 15 문구 좁힘(§2 표에 MOT-SR·TRACE-Router 행). 추가 배경 소스는
  결정 15 참조. **front 점유 주장의 함정**(무작위 혼합 대조군)을 결과 보고에 이식할 것.
- 파레토 지식스택 적용 — `pareto-optimization-gate` 스킬에 §적용 지도 병합(재판정 금지).
  local-kb-retrieval-eval 2축 재판정 적용 완료. 도메인 QA봇 A(회귀 러너 --baseline + pareto_gate.py)·도메인 QA봇 B(골드20 검색평가 초안, baseline 0.80/0.50)
  **구현 완료(2026-08-03)** — 상세는 각 봇 스킬. 골드 20문항은 운영자 검수 대기.

**사례글은 실행 결과 후**로 미룸 — 지금 쓰면 "설계했다"로 끝난다. 3주차 소재 정본은
직전 gpters 발행본의 「앞으로의 계획」에서 확인할 것(PLAN.md 추측 착수 금지).

## 막힘/우려

- **표본 군집화가 근본 병목** — 문제 10건이 답변 8개에 분포. 주장 수를 늘려도 같은 답변이면 무의미.
- **라벨러 1인·inter-rater 미측정** — 파레토 실험의 ground truth도 이 55건에 의존.
  설계 §14.5·부록B-3이 한계로 명시. **미해결.**
- **C1 조건이 이 실험의 약한 고리** — `"no parent-selection rule"`은 에이전트 재량이지
  균등 무작위가 아니다. C2>C1이 나와도 "우리 규칙 > 에이전트 재량"은 주장 불가(부록 B-5).
- **kiro 자기보고 "파일 안 건드렸다"는 검증 수단 없으면 못 믿는다** — 1라운드에서 실제로
  해시 불일치 발생. → **kiro 호출 전 대상 파일을 커밋하거나 스냅샷을 뜬다.**

## 검증 게이트 (완료 주장 전 필수)

```bash
cd gate
.venv/bin/python -m pytest tests/test_mh_judge.py -q    # 파레토 판정기 32건
.venv/bin/python scripts/phase1_probe_control.py        # 기저율 통제비교
.venv/bin/python scripts/phase2_power_analysis.py       # 표본 소요량
cd .. && python3 gate/scripts/anonymize_check.py        # push 전 필수(현재 13건 = push 불가)
```

- 단일 실행 수치를 성능으로 보고하지 않는다(저지는 3회 실측에서 재현성 없었음).
- 사전 선언 문서는 실행 **전** 커밋한다. 결과 보고 기준·N 변경 금지.
- 프로브 지적 건수를 KPI로 삼지 않는다(Goodhart).
