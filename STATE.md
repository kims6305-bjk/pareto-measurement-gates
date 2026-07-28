# STATE — reflection-probe-gate

세션 시작 시 이 파일을 먼저 읽는다. 상한 100줄, 아카이브 아닌 다이제스트.
상세는 각 정본 문서 참조(복붙 금지).

## 현재 위치

- **Phase 1 종결 (판정: 프로브 효과 = 판정 불가).** 정본 `gate/PHASE1_VERDICT.md`
- **Phase 2 = 라벨 확장. 내부 파일럿 사전 선언 커밋 완료, bjkim 파일럿 라벨 대기.**
  정본 `gate/PHASE2_LABELING_PROTOCOL.md` + `gate/PHASE2_INTERNAL_PILOT.md`
- 마지막 활동 2026-07-28. HEAD = 파일럿 커밋, git clean, origin push 완료.
- 대기 중인 사람 작업 **1건**: 파일럿 30건 라벨(아래 §세션 연속성).

## 결정 누적

1. **프로브 3표 합의 채택** — 1표 대비 회수 손실 0, 검토율 38.9%→35.2%. `phase1_final_gate_probe3.py`
2. **선택규칙 필터 기각(과적합)** — 근거 문단이 코퍼스 전체에서 1개(1019.103). Q068 제외 시 양성 0건. `phase1_selection_overfit_check.py`
3. **답변문맥 프로브 기각** — 사전 기준 (b)(c) 미달. 오탐 12→2로 줄었으나 진짜 히트 2건 다 놓치고 회수율 90%→70%. `gate/ANSWER_CONTEXT_PROBE.md`
4. **실질 산출물 = per-claim 채점 결함** — 오탐 12건이 100% 분해 아티팩트. 형제 문맥 제공 시 형제 있는 9건이 9/9 뒤집힘(진단 지지). 처방은 미확정.
5. **no_answer 층 제외(실측 정정)** — 17문항 전건 올바른 기권(`claims: []`)이라 라벨 대상 없음. 기권률 17/17은 답변자 지표로 별도 보고.
6. **Phase 1 라벨 55건은 불변** — 재라벨·삭제 금지. Phase 2와 별도 집합으로 유지 후 3단 병기.
7. **내부 파일럿 채택(3→2 경로)** — 정본 순서 201건(seed 20260728, CAP=3)을 고정하고
   파일럿 = 그 앞 30건, 본 표본 = 앞 N건으로 **중첩** 정의. 파일럿에서 **기저율만**
   열람하고 N=clamp(ceil(55/p̂), 90, 201)로 기계 확정. `gate/PHASE2_INTERNAL_PILOT.md`

## 세션 연속성

**멈춘 지점**: 내부 파일럿 사전 선언 + 파일럿 시트(30건) 생성 완료. **bjkim 라벨 대기.**

**바로 집어들 다음 액션**:
1. bjkim이 `gate/scripts/phase2_pilot_label_sheet.xlsx` 30건 라벨 (S/C/I + 메모)
2. `.venv/bin/python scripts/phase2_determine_n.py` → p̂와 N 기계 산출, 원자료 커밋
   (미라벨/비정상 라벨이면 스크립트가 거부한다 — fail-closed 실측 완료)
3. `PHASE2_CLAIM_CAP=3 PHASE2_N=<확정N> .venv/bin/python scripts/phase2_build_label_sheet.py`
   → 본 시트 생성. 파일럿 30건은 앞부분에 그대로 이월(재라벨 금지)
4. 본 라벨 완료 후에야 프로토콜 §4 QC → 효과 지표 집계

**절대 하지 말 것**: 파일럿 단계에서 프로브·저지 출력을 여는 것. 열람 화이트리스트는
`PHASE2_INTERNAL_PILOT.md` §1.1에 있고 결과를 본 뒤 확대하지 않는다.

## 막힘/우려

- **표본 군집화가 근본 병목**(Phase 1에서 확인). 문제 10건이 답변 8개에 분포,
  프로브가 잡은 2건은 답변 1개(Q068-A)에서 나옴. 주장 수를 늘려도 같은 답변이면 무의미.
  → 필요량 실측: 문제 사례 55건, McNemar 불일치쌍 6건. `phase2_power_analysis.py`
- **내 설계 실수 기록**: 답변문맥 실험이 단일 변인이 아니었음(형제 문맥 + 완화 지시 동시 변경).
  형제 없는 오탐 1건도 뒤집혀 원인 귀속 불가. 다음 실험은 변인 1개만.
- 라벨러 1인·inter-rater 미측정 → Phase 2 §4 QC(재현성 12문항, 2차 라벨러, gold 대조)로 보강 예정, 미실행.

## 검증 게이트 (완료 주장 전 필수)

```bash
cd gate
.venv/bin/python scripts/phase1_score_answerctx.py      # 시도 3 판정 재현
.venv/bin/python scripts/phase1_probe_control.py        # 기저율 통제비교
.venv/bin/python scripts/phase2_power_analysis.py       # 표본 소요량
```

- 단일 실행 수치를 성능으로 보고하지 않는다(저지는 3회 실측에서 재현성 없었음).
- 사전 선언 문서는 실행 **전** 커밋한다. 결과 보고 기준·N 변경 금지.
- 프로브 지적 건수를 KPI로 삼지 않는다(Goodhart — 스킬 `probe-graph` 대원칙 3).
