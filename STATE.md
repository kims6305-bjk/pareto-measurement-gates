# STATE — pareto-measurement-gates

(구 `reflection-probe-gate` — 2026-08-08 개명. 옛 URL은 GitHub 301 리다이렉트로
살아 있으나, 새 인용은 반드시 새 이름으로.)

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
  설계·사전등록·부속서1 = `gate/PARETO_META_HARNESS_{DESIGN,PREREG,PREREG_ADDENDUM1}.md`.
  실물: `mh_guard.py`(INV-2/3 매니페스트) · `mh_run_candidate.py`(sha 대조·resume·
  fail-closed) · `mh_archive_C2.jsonl` · `mh_front.py`(REJECTED_C0, 테스트 32/32).
- **Phase 4 = 다목적 채택 게이트.** `gate/PHASE4_PREREGISTRATION.md` DRAFT.
  §3의 3축은 파레토 설계 §3에서 **2축(recall, precision)으로 개정**됨.
- 마지막 활동 2026-08-08. **논문 트랙 진입** — 범위 확정(파레토/측정 게이트 1편 먼저,
  온톨로지는 2편으로 분리) + 논문용 정본 3건 레포 추가. 다음은 목차 초안.
- 익명화 0건 유지, push 가능 상태. 처리 절차는 설계 §13.4.

## 결정 누적

Phase 1·2 결정(1~10)은 각 정본에 전문 보관. 여기엔 이후에도 영향 주는 것만.

- **Phase 1 라벨 55건은 불변** — 재라벨·삭제 금지. 재생성 불가한 정답지.
- **확증/탐색 분리** — 가설 생성 표본을 확증 집합에서 제외(순환 논증 차단). 13번의 원인.

11. **🔴 검정력은 표본 크기가 아니라 결과변수 기저율에 대해 계산한다 (P3 실패)** —
   분모는 세고 분자를 안 쟀다. → 이후 모든 실험은 **본 실행 전 계기 검침**이 요건.

12. **계기 검침이 내 진단을 기각했다** — "저지 고장" 가설은 틀렸고 저지는 정상이었다.
   검침 없이 고쳤다면 멀쩡한 도구를 고치고 개선이라 보고할 뻔했다. 비용 165콜/15분.

13. **🔴 순환 논증 차단이 신호를 전량 제거** — Phase 1 문제 문항 28개가 전부 탐색
   (제외) 집합으로. 두 규율의 충돌. → 해법은 제외 포기가 아니라 **제외 후 기저율 확인**.

14. **축 분리: 회수율은 언어에 둔감, 정밀도는 민감** — 오탐률 SciFact 36.4% vs KLUE 3.0%,
   놓치는 실패는 두 언어 0. 어느 쪽이 옳은지는 미해결.

15. **🔴 문헌 대조 — front를 부모 선택에 쓰는 규칙은 harness 자기개선 계층에 없다**
   (6소스 체제, 정독본 `<workspace>/tmp/meta_src{1..6}.md`, 표는 설계문서 §2)
   - Self-Harness: 판정식 있음·front 없음 / Meta-Harness: front 있음·부모규칙 없음.
   - src5 MOT-SR이 front-as-parent를 **실제 구현**했으나 그 규칙 자체의 ablation·
     사전등록·통계검정 전무 → 타 도메인 독립 지지이자, **우리 C1 vs C2 대조가
     문헌에 없는 측정**임을 보존.
   - src6 TRACE-Router에서 이식 2건: 귀속 처방(결정 입자를 감독 단위까지 굵게),
     🔴 **front 점유 주장에는 무작위 혼합 대조군 필요**("random mixture also traces
     the line segment") — 결과 보고에 반드시 반영할 것.
   - 배경 소스 목록(설계문서 미편입)은 설계문서 §2 각주 참조.

16. **🔴 precision을 축으로 올린 것이 이 설계의 핵심 판단** — 단일축(recall)이면
   "전부 CONTRADICTED 찍는 가짜 후보"가 1등을 먹는다. 코드로 실증됨:
   `test_negative_control_all_contradicted_cannot_monopolize_front` (32/32 통과).
   elapsed는 **A/B 모두 4.60s 동률 실측**으로 축에서 기각(P4 §3의 비용축 가정이 틀렸음).

17. **🔴 부재증명은 재실행해 재현한 것만 인용한다** (2026-08-08, 실패 1건에서) —
   경로 오타로 도구 오류를 "grep 0건"으로 읽었고 재실행하니 9건. 공개 문서·논문의
   부재증명은 예외 없이 재현 필수. **깨졌을 때 결론이 살아남는지 따로 판정**한다
   (이번엔 "없다"를 "등록 시점에 없다"로 좁혀 살렸다). 교정 과정은
   `RELATED_HARNESSES.md`에 그대로 남겼다 — 숨기면 검증 강도가 안 보인다.

18. **논문 범위 = 분리, 파레토/측정 게이트 1편 먼저** (2026-08-08, 운영자 결정) —
   측정 게이트는 문제→오판→수정→결론이 커밋으로 재현되나, 온톨로지는 실측이
   클러스터 재사용 42% 하나뿐. 묶으면 약한 쪽이 전체를 끌어내린다. 레포는 동거.

19. **레포명 개명 완료** (2026-08-08, 운영자 결정 A) —
   `reflection-probe-gate` → `pareto-measurement-gates`. 내용물이 이름을 앞질렀고
   (프로브 실험은 종결된 한 챕터), 논문에 URL이 박히기 전이 마지막 무료 타이밍이었다.
   옛 URL 301 리다이렉트 실측 확인. README 3판 제목도 `probe-graph`로 어긋나 있던 걸
   함께 정합. 레포 밖 스킬 문서 7곳(9건)도 갱신 — `reflection_gate` 패키지명은 보존.

## 세션 연속성

**멈춘 지점**: 2026-08-08 논문 트랙 착수 — 범위 확정(결정 18) + 논문용 정본 3건 추가.
커밋 `ac20c3c` 외. 상세는 각 문서에, 여기는 무엇이 어디에 쓰이는지만.

| 신규 정본 | 논문 배치 | 핵심 |
|---|---|---|
| `gate/RELATED_HARNESSES.md` | §관련연구 | 참조 구현(prime-agent `a18809e`) 해부 — 채택 게이트 부재를 파일:라인 실측. 최강 근거 = `expectedOutcome` 저장은 되나 소비처가 프롬프트 렌더링 1곳(선언↔소비 괴리). 우리 부재증명 오류 1건도 교정째 수록 |
| `gate/MEASUREMENT_FAILURES.md` | §도입 문제제기 | 계측 실패 3건(계수단위·전처리순환·판정순환). 사설 커밋 `6335bcd0`/`7edf8ba3`/`94b0cbd3`+`d4259f06` 익명화 요약, 원자료 미동봉 |
| `gate/THEORY_MAPPING.md` | §배경 | RLS 이득 K↔채택 게이트, AR 노출편향↔스킬 재입력, 사전 가지치기↔계기 검침. 3등급 분리 + 성립 안 하는 전제 별도 절 |

스킬 `primary-source-repo-research`에 §8.2.1(부재증명 재실행)·§8.7(대조 판정) 신설.

**바로 집어들 액션 1개**: **논문 목차 초안.** 사설 워크스페이스
`outputs/ontology_paper_sources.md`의 13소스를 읽고 목차를 잡는다.
서사 축 = "검침 3종이 자격 없는 탐색을 막았다" + 결정 15(문헌 빈자리) + V6 실측 +
front 점유 함정(무작위 혼합 대조군). 위 표대로 3건을 배치.
🔴 새 실험 금지. 레포명 변경(`pareto-measurement-gates`)은 목차 확정 후 — 지금 바꾸면
기존 링크만 깨진다.

**이전 라운드 요약 (2026-08-03, 상세는 커밋·정본에)**: c000 측정 3판×55=165콜 →
IC-0 PASS(recall 0.6364 [0.3844,1.0] / precision 0.5833 [0.25,0.9168]),
front={c000}. IC-1 실행 후 V6 종결(총 495콜, 탐색 1,650콜 미사용).
원장 `mh_archive_C2.jsonl` · front 캐시 `mh_front_C2.json` · 판정 `PARETO_MH_VERDICT.md`.
익명화 28건→0 + push 완료, 스킬 `skill-pareto/` 동기화, 사례글 작가봇 인계 완료.
⚠️ 정답지는 `phase1_human_label_sheet.xlsx` 「라벨링」 시트 G열
(phase2 json은 human_label 빈 파일 — 헷갈리지 말 것).

**병행 트랙 (이전 세션 완료분)**:
- 문헌 6소스 체제 — 결정 15 문구 좁힘(§2 표에 MOT-SR·TRACE-Router 행). 추가 배경 소스는
  결정 15 참조. **front 점유 주장의 함정**(무작위 혼합 대조군)을 결과 보고에 이식할 것.
- 파레토 지식스택 적용 — `pareto-optimization-gate` 스킬에 §적용 지도 병합(재판정 금지).
  local-kb-retrieval-eval 2축 재판정 적용 완료. 도메인 QA봇 A(회귀 러너 --baseline + pareto_gate.py)·도메인 QA봇 B(골드20 검색평가 초안, baseline 0.80/0.50)
  **구현 완료(2026-08-03)** — 상세는 각 봇 스킬. 골드 20문항은 운영자 검수 대기.

(구 유예 조항 해소 — 실행 결과가 나와 사례글 작성·인계 완료됨.)

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
