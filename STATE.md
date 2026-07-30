# STATE — reflection-probe-gate

세션 시작 시 이 파일을 먼저 읽는다. 상한 100줄, 아카이브 아닌 다이제스트.
상세는 각 정본 문서 참조(복붙 금지).

## 현재 위치

- **Phase 1·2·3 전부 종결.** 판정은 각 정본에 — `gate/PHASE{1,2,3}_VERDICT.md`
  요약: P1 판정불가 / P2 표본부족 종결(171건 라벨 안 함) / P3 1,650콜 완주했으나
  🔴 조건 A 문제판정 0건이라 H1을 검정하지 못함.
- **계기 검침 PASS** — 저지는 정상이었다(recall 81.8%, SPLIT 0). `gate/INSTRUMENT_CHECK_RESULT.md`
- **옆방 검증 2/2 PASS** — SciFact·KLUE-NLI recall 100%. `gate/SIDECHECK_RESULT.md`
- **🆕 파레토 메타하네스 — 설계·판정기·사전등록 완료, 실행 전.** (2026-07-31)
  커밋 `7d7d28b` 설계 1,978행 → `5df830a` 판정기+테스트32 → `bfef1cd` 사전등록 340행.
  정본 `gate/PARETO_META_HARNESS_DESIGN.md` · `gate/PARETO_META_HARNESS_PREREG.md`
  🔴 **러너(mh_run_candidate.py) 미구현. 이것이 INV-5를 만족시키는 상태다** —
  판정기와 임계를 결과 열람 전에 커밋했으므로 사후 조정이 불가능하다.
- **Phase 4 = 다목적 채택 게이트.** `gate/PHASE4_PREREGISTRATION.md` DRAFT.
  §3의 3축은 파레토 설계 §3에서 **2축(recall, precision)으로 개정**됨.
- 마지막 활동 2026-07-31. git clean. 🔴 **push 금지 상태** — 익명화 13건(설계 문서
  절대경로·식별자). 처리 절차는 설계 §13.4.

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

15. **🔴 문헌 대조 결과 — front를 탐색 엔진으로 쓰는 주체가 없다** (2026-07-31, 4소스 정독)
   정독본 `<workspace>/tmp/meta_src{1,2,3,4}.md` (Self-Harness 2606.09498 /
   Awesome-Harness-Self-Improvement MIT / Lilian Weng / Meta-Harness 2603.28052)
   - Self-Harness: Pareto 용어 **0회**지만 비지배 판정을 **진입 게이트에 구현**.
     스칼라 합산 명시 거부. 그러나 front 미보관 — 활성 harness 항상 1개.
   - Meta-Harness: Pareto **11회** 언급 + front 반환. 그러나 dominance 판정식이 원문에 없고
     `"imposes no parent-selection rule"` — 탐색이 front를 쓰지 않는다. 최종 선택도 수동.
   - 두 논문 다 안 하는 것 = **front를 부모 선택에 쓰는 규칙.** 이것이 우리 기여 지점.
   - 레포 §5와 Lilian이 독립적으로 같은 처방: evaluator·권한제어는 진화 루프 **밖**에.

16. **🔴 precision을 축으로 올린 것이 이 설계의 핵심 판단** — 단일축(recall)이면
   "전부 CONTRADICTED 찍는 가짜 후보"가 1등을 먹는다. 코드로 실증됨:
   `test_negative_control_all_contradicted_cannot_monopolize_front` (32/32 통과).
   elapsed는 **A/B 모두 4.60s 동률 실측**으로 축에서 기각(P4 §3의 비용축 가정이 틀렸음).

## 세션 연속성

**멈춘 지점**: 파레토 메타하네스 = 실행 전 준비 완료. 러너만 남았다.

**바로 집어들 액션 1개**: 사전등록 §10 **미정 14건 중 U8·U9·U10 해소** (실행 차단 3건)
- **U8** IC-0 재실행이 실제로는 0콜 — `instrument_check_run.py`가 기존 jsonl을 resume하고,
  원자료 물리 삭제는 설계 §5.3이 금지. 예산표는 165콜로 잡혀 있어 **검침이 헛돈다.**
- **U9** 집합 dominance(D-dom/D-str) 계산 구현체 미지정 → V1~V7 자동 판정 불가.
- **U10** 예산 총계 불일치: 495+1650×5=8,745인데 표에 1650 행이 6개(10,395). 컷라인 5,445는 일관.
- 나머지 11건은 러너 만들며 자연 해소 가능. 그 뒤 `mh_guard.py` → 러너 순서(설계 §9.3).

**사례글은 실행 결과 후**로 미룸 — 지금 쓰면 "설계했다"로 끝난다. 설계 부록A가
"front를 쓰면 더 좋다는 것은 아직 측정하지 않았다"를 명시. 3주차 소재 정본은
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
