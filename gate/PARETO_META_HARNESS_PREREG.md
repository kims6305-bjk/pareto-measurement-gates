# 파레토 메타하네스 사전 선언 (Pareto Meta-Harness) — 첫 콜 이전 커밋

**이 문서를 커밋한 뒤에 러너를 작성하고 후보를 측정한다.** 결과를 보고 축·판정식·조건·
임계를 바꾸지 않는다. 논증은 정본(`PARETO_META_HARNESS_DESIGN.md`)에 있고, 이 문서는
**서명용 계약서**다 — 절 번호로만 참조하고 근거를 반복하지 않는다.

## 0. 머리말 — 무엇이고, 언제 쓰였고, 무엇을 금지하는가

정본 §10.1 의 D6("`PARETO_META_HARNESS_PREREG.md` 커밋 — 첫 콜 이전")에 해당하는 문서다.
정본 §15.2 실행 순서표의 **1단계**이며, 2~19단계는 아직 실행되지 않았다.

**작성 시점의 실물 상태 (git 조회 결과)**

| 대상 | 커밋 | 시각 | 상태 |
|---|---|---|---|
| `gate/PARETO_META_HARNESS_DESIGN.md` | `7d7d28b` (`7d7d28b6deaf33afcce25fc40d56e12cda3a8328`) | 2026-07-30 23:41:22 +0900 | 정본. 이 문서는 정본을 **수정하지 않는다** |
| `gate/scripts/mh_objectives.py` · `gate/scripts/mh_front.py` · `gate/tests/test_mh_judge.py` | `5df830a` (`5df830a38c0dda2d3faa181ec5ffb64de3fb16ee`) "Add Pareto judges before any search run (INV-5)" | 2026-07-31 00:00:05 +0900 | **판정기 커밋 완료** |
| `gate/scripts/phase3_build_prompts.py` (F8 빌더) | `19e0081` | 2026-07-28 20:19:18 +0900 | 기존 파일 |
| 러너 `mh_run_candidate.py` · `mh_guard.py` · `mh_ic1_negative_control.py` · `mh_pair_diagnose.py` · `mh_filter_candidates.py` · `mh_propose.md` · `mh_manifest.json` | — | — | **전부 미구현** (`gate/scripts/` 실측: `mh_front.py`, `mh_objectives.py` 2개만 존재) |

**즉 판정기는 있고 러너는 없다.** 이 시점에 조건과 임계를 박는 이유가 이 문서의 존재
이유다 — 검색 결과를 본 뒤 조건·축·판정식을 바꾸는 것(**다목적판 optional stopping**,
정본 §10)을 원천 차단한다. 금지 목록은 정본 §10.2(9항목)와 §15.3(10항목)이며, 후자를
§7 에 고정 위치와 함께 옮긴다.

**작성 시점에 이미 통과한 것**: IC-2(정본 §8.2, 0콜) — `mh_objectives.py --selftest`
7항목 PASS(전건 정탐 CI=[1.0,1.0], 전건 미탐 CI=[0.0,0.0], `n_flagged=0` → precision
`None`(0.0 아님), 같은 seed 2회 동일, qid CI 폭 ≥ claim CI 폭). LLM 호출 0.

---

## 1. 가설과 주장

정본 §14.1 의 주장을 그대로 옮긴다.

> **C**: 노이즈를 명시적으로 처리하는 dominance 판정으로 harness 후보의 파레토 front 를
> 유지하고 **그 front 의 끝점에서 부모를 고르는 규칙**(§6)을 두면, 같은 후보 예산 아래에서
> front 를 탐색에 쓰지 않는 두 조건(C0: front 없음 / C1: front 있으나 부모 무작위)보다
> **더 나은 front 를 얻는다.**

반증 가능한 형태: **`F_C2` 가 `F_C0` 를 지배하고 `F_C1` 도 지배한다**. 집합 비교 정의는
정본 §14.1 그대로 — `D-dom`(커버: 모든 `y ∈ F_Y` 에 대해 `x ≻ y` 또는 전 축 CI 겹침 동률인
`x ∈ F_X` 존재), `D-str`(커버 + 지배하는 쌍이 1개 이상). **hypervolume·가중합·F1 을
판정 입력으로 쓰지 않는다**(정본 §14.1, §10.2 금지 3).

### 판정표 V1~V7 (정본 §14.2. 실행 전 고정)

| # | 관측 | 결론 |
|---|---|---|
| V1 | `F_C2` 가 `F_C0`·`F_C1` 을 **둘 다 지배** | 주장 C **지지** (§14.5 범위 제한 병기) |
| V2 | 하나만 지배 | **부분 지지.** C0 만 지배 = front 유지가 기여·부모 규칙 미분해 / C1 만 지배 = 부모 규칙이 기여·front 유지 미분해 |
| 🔴 **V3** | 세 front 가 서로 **커버만 하고 지배 없음** | 🔴 **주장 C 기각 — "우리 기여가 없다".** 이 표본·이 예산에서 §6 규칙은 front 를 개선하지 않았다 |
| 🔴 **V4** | `F_C0` 또는 `F_C1` 이 `F_C2` 를 지배 | 🔴 **주장 C 반증 — front 를 탐색에 쓴 것이 해로웠다.** 그대로 보고한다 |
| V5 | 어느 조건이든 T4 정지 | **판정 불가.** 축을 늘리거나 claim CI 로 갈아타지 않는다 |
| V6 | IC-1 FAIL | **탐색 시작 전 중단.** "축 설계 실패" 를 495콜 이내에서 보고 |
| V7 | 모든 조건에서 front 크기 1 유지 | **이 탐색 공간에 baseline 을 지배하는 변이가 없다** — 그 자체로 보고 |

🔴 **V3·V4 가 나오면 다음을 하지 않는다**(정본 §14.2): 축 추가, C2 만 예산 증액,
유리한 ablation 만 본문 게재, front 집합 비교를 point-wise 최댓값 비교로 교체.

---

## 2. 조건 — 정의와 구현 매핑

정의는 정본 §12.1. 각 조건은 **후보 10개 = 1,650콜**을 동일하게 받는다.

| 조건 | front 유지 | dominance(§4) | 부모 선택 | 구현 |
|---|---|---|---|---|
| **C0** | ❌ 활성 harness 1개 | ❌ Self-Harness 수락규칙을 진입 게이트로 | 항상 현재 활성 harness `hₜ` | **(러너 미구현)** — 수락규칙 구현체 없음. `mh_front.py` 에 C0 플래그 없음 |
| **C1** | ✅ | ✅ (CI 겹침 동률 포함) | **무작위** front 균등 추출, `PARENT_SEED = 20260731` | front 계산은 `mh_front.py front --ci qid`. 부모 추출기 **(러너 미구현)**, `PARENT_SEED` 는 코드에 없음 |
| **C2** | ✅ | ✅ | §6.1 S1/S2/S3 + §6.5 filter_strip 전부 | front·판정은 `mh_front.py`. `mh_pair_diagnose.py`(S3)·`mh_filter_candidates.py`(filter_strip) **(러너 미구현)** |
| **A-S3** | ✅ | ✅ | S3 슬롯 비움 (S1·S2·filter_strip 유지) | **(러너 미구현)** |
| **A-FS** | ✅ | ✅ | filter_strip 생략 (S1/S2/S3 만) | **(러너 미구현)** |
| **A-CI** | ✅ | **점 추정만** | C2 계보 재분석 | **구현됨** — `mh_front.py front --ci none` (`CI_KEYS` L44, `DEFAULT_CI` L45, 테스트 `test_front_ci_none_mode_changes_membership`) |

**C0 수락규칙**(정본 §12.1·§13 D13, 변경 금지): `Δ_recall ≥ 0 ∧ Δ_precision ≥ 0 ∧
max(Δ_recall, Δ_precision) > 0`. `Δ_recall` = `n_detected` 차, `Δ_precision` = 비율 차
(분모가 후보마다 변하므로 개수 차를 쓸 수 없다 — 원문과 다른 유일한 지점). **CI 미사용.**
3판 다수결 라벨 하나로 집계. merge 미실시. 거부 후보는 원장에 append(행 삭제 금지).

**세 조건이 글자 단위로 공유하는 것**(정본 §12.1): 원장 스키마·물리 삭제 금지·R1~R5·
유효성 검증 3단계·INV-1~6·라벨 시트 55건과 해시 불변·모델 `claude-sonnet-4-6`·3판·
fail-closed·검침 495콜(조건별 반복 없음)·후보 1개 = 165콜·T2·T3. **baseline `c000` 은
세 조건이 공유하며 한 번만 측정한다**(`prompt_sha256` 중복 차단, `validity_check`).
C0 에서는 T1 을 "활성 harness 3라운드 불변" 으로 대체하고 T4 는 적용하지 않는다.

**ablation 이 검증하는 주장과 반증 형태**(정본 §12.2, D14): A-S3 = "끝점 2개 동시 참조가
기여한다" / A-S3 front 가 C2 를 지배·동률이면 S3 는 기여 아님. A-FS = "붙이기보다 제거
먼저"(현재 n=1) / A-FS 가 C2 와 동률 이상이면 제거 단계 불필요. A-CI = "노이즈 처리가
필요한가" / 점 추정 front 와 CI front 의 멤버십이 같으면 CI 는 계산 비용만 쓴 것.

---

## 3. 측정

**축 = (recall ↑, precision ↑) 2개. 3개를 넘기지 않는다**(정본 §3.3·§3.6, `AXES`
= `mh_objectives.py` L154 / `mh_front.py` L38). 정의는 `instrument_check_score.py` 와
같다: `PROBLEM = {"CONTRADICTED","INSUFFICIENT"}`, 3판 2표 이상 다수결(그 외 `SPLIT`),
`recall = n_detected / n_problem`, `precision = n_detected / n_flagged`.

| 항목 | 실물 |
|---|---|
| 다수결 | `majority()` (`mh_objectives.py`) |
| 카운트 | `counts()` — `n_units`/`n_problem`/`n_flagged`/`n_detected`/`n_split`/`n_unresolved` |
| 축 | `recall_of()` · `precision_of()` (분모 0 → `None`, **0.0 아님**) |
| 부트스트랩 | `bootstrap(units, mode)` — `mode ∈ {"claim","qid"}`, `percentile()`, `_Rng`(LCG 고정) |
| 표본 요건 | `sample_gate()` |
| 출력 조립 | `build_result()` → `measurement` / `objectives` / `reference_fields` / `sample_gate` / `bootstrap` / `diagnostics` |
| 입력 로딩 | `load_labels()` (`.xlsx` 시트 `라벨링` G열 = S/C/I, 또는 `.json`) · `load_runs()` · `build_units()` |
| CLI | `mh_objectives.py --candidate-id … --runs … --labels … --out …` / `--selftest` / `--seed` / `--bootstrap-b` / `--search-cost-calls`. 종료코드 `EXIT_OK=0` · `EXIT_INPUT=2` · `EXIT_SAMPLE_GATE=3` |

**데이터 출처** (정본 §3.2·§7.1, 루프 밖·읽기 전용):
`gate/scripts/phase1_human_label_sheet.xlsx` / `.json` (사람 라벨 55건, 문제 11건),
후보 원자료 `gate/scripts/mh_c<NNN>_run{1,2,3}.jsonl`, `c000` 은
`gate/scripts/instrument_check_run{1,2,3}.jsonl` 재사용(정본 §12.3).
작성 시점 실측 해시(F7 증거): `.xlsx` = `f3349ede…c456fa5`, `.json` = `7463e45d…f56c240`.

**최소 표본 요건 R1~R5** (정본 §4.4. 위반 시 `UNJUDGED` — 지배도 피지배도 하지 않는다):

| 코드 | 임계 | 상수 (`mh_objectives.py`) |
|---|---|---|
| R1 사람 라벨 문제건 | **≥ 8** | `R1_MIN_PROBLEM = 8` (L50) |
| R2 판정기 문제판정 | **≥ 5** | `R2_MIN_FLAGGED = 5` (L51) |
| R3 판수 | **정확히 3** | `R3_N_RUNS = 3` (L52) |
| R4 UNRESOLVED 비율 | **< 10%** | `R4_MAX_UNRESOLVED = 0.10` (L53) |
| R5 SPLIT 비율 | **< 20%** | `R5_MAX_SPLIT = 0.20` (L54) |

**부트스트랩 고정값 F1~F5**: `SEED = 20260730`(L38) · `B = 2000`(L39) ·
`CI_LO_PCT, CI_HI_PCT = 2.5, 97.5`(L40) · `CI_USED_FOR_JUDGMENT = "ci_qid"`(L41,
claim·qid 둘 다 계산하고 **판정은 qid 클러스터 = 보수적인 쪽**) · `PARENT_SEED = 20260731`
(C1 전용, 코드 미구현).

---

## 4. 판정 규칙 — 구현 위치

| 규칙 | 정본 | 구현 (`mh_front.py`) |
|---|---|---|
| 축별 비교 + **CI 겹침 = 동률**(N2) | §4.3 | `cmp_axis()` |
| 강한 지배 `r≥ ∧ p≥ ∧ (하나 초과)` | §4.1 | `dominates()` · `relation()` |
| 비지배 집합 + G1(baseline 에게 지배당한 후보 부모 영구 제외) | §4.1·§5.2 | `compute_front()` → `front` / `dominated` / `g1_excluded` |
| 판정 대상 여부 (UNJUDGED·INVALID·PRUNED 제외) | §4.4·§5.2 | `judgeable()` |
| 끝점 (동률이면 반대 축 큰 쪽 → generation 이른 쪽 → id) | §5.4-1·§6.1 | `endpoints()` |
| front 상한 **8** + 3단 사전식 솎아내기 (**crowding distance 미사용**) | §5.4 | `prune_front()`, `FRONT_CAP = 8`(L40) |
| filter_strip 과반 시 솎아내지 않고 정지 | §5.4 예외 | `prune_front()` → `"T4_filter_strip_majority"` |
| 종료조건 T1~T4 | §6.4 | `termination()`, `STALL_LIMIT = 3`(L41), `CALL_BUDGET = 1650`(L42) |
| 진입 유효성 (모델 alias 금지·`prompt_sha256` 중복 금지·빌더 import) | §5.2-1 | `validity_check()`, `MODEL_FIXED`(L43) |
| 상태 전이 append (물리 삭제 금지) | §5.3 | `_transition()` · `append_archive()`, `TERMINAL = {PRUNED, INVALID}`(L50) |
| A-CI 점추정 판정 | §12.2 | `--ci none` (`CI_KEYS` L44) |

CLI: `mh_front.py front|add|dominance`, 공통 `--archive` · `--ci {claim,none,qid}` ·
`--computed-at`; `front` 는 `--out` · `--cap` · `--dry-run` · `--no-status-write`.
산출 `mh_front.json`: `front` / `endpoints` / `dominated` / `pruned` / `unjudged` /
`front_size` / `front_changed` / `stall_rounds` / `g1_excluded` / `invalid` / `termination`.

**집합 dominance(D-dom / D-str) 계산기는 미지정** → §10 미정 항목 U9.

---

## 5. 실행 순서와 예산

순서를 바꾸지 않는다(정본 §8.3·§15.2).

```
IC-2 (0콜, CI 계산기 자기검증)  → 통과 (작성 시점 PASS)
  ↓
IC-0 (165콜, recall ≥ 30% and CONTRADICTED ≥ 1)   ← PASS 아니면 시작하지 않는다
  ↓
IC-1 (330콜, c_neg_loose / c_neg_strict — precision 축 판별력)  ← FAIL 이면 V6 종결
  ↓
baseline c000 확정 (IC-0 원자료 재사용, 추가 측정 없음)
  ↓
C2 완주 → C0 완주 → C1 완주 → A-CI(재분석, 0콜) → A-S3 · A-FS
  ↓
결정론 검증 D-1·D-4 → 집합 dominance 판정 → V1~V7 자동 선택 → RESULT 작성
```

C2 를 먼저 돌리는 이유: C2 가 T3/T4 로 조기 정지하면 V5(판정 불가)가 확정되어 C0·C1 에
3,300콜을 쓸 이유가 없어진다(정본 §15.2). 대가 = 저자가 C0·C1 실행 시 C2 결과를 이미
알고 있다는 점이며, 완화 수단은 (a) 변이 표면 목록을 조건 간 동일하게 `mh_propose.md`
에 **C2 실행 전** 커밋, (b) C0·C1 후보의 `origin_reason` 을 **측정 전** 커밋. 완전히
봉쇄되지 않는다는 사실을 결과 문서에 남긴다.

| 순위 | 항목 | 콜 | 없으면 주장 못 하는 것 |
|---|---|---|---|
| P0 | IC-2 → IC-0 → IC-1 | **495** (0 + 165 + 330) | 아무것도 |
| P1 | **C2** | 1,650 | 제안 자체 |
| P2 | **C0** | 1,650 | baseline 대조군 |
| P3 | A-CI(재분석) | **0** | 노이즈 규칙의 필요성 |
| P4 | **C1** | 1,650 | 효과의 귀속 (기여 주장의 핵심) |
| P5 | A-S3 | ≤1,650 | §6.2 의 분해 |
| P6 | A-FS | ≤1,650 | 사용자 지론이 n=1 로 남음 |
| P7 | A-CI(실행) | 1,650 | (P3 로 부분 대체) |

**컷라인 = P4, 합 5,445콜.** 못 채우면 **실행하지 않는다.** 컷은 **아래에서 위로만**
(P7 → P5). 재배열 금지. 조건은 **완주 아니면 미실행** — 절반 실행 금지.
정본이 적은 전체 상한은 **8,745콜**이다(= 495 + 1,650×5, 즉 P7 제외 기준). 행 합계와의
불일치는 §10 U10.

---

## 6. 중단 규칙

Phase 3 는 **1,650콜을 태우고 검정 불가**로 끝났다(`PHASE3_VERDICT.md`) — 원인은 처치가
아니라 표본/도구였다. 그래서 아래 중단 규칙은 전부 **싼 쪽을 먼저 재는** 순서다.

| 조건 | 처리 |
|---|---|
| **IC-2 실패** (CI 계산기 자기검증) | **0콜 지점에서 중단.** 계산기를 고치고 재검침 |
| **IC-0 이 PASS 아님** | 파레토 탐색을 **시작하지 않는다.** 이미 PASS 한 실행이 있으므로 환경 변화를 의미 → 원인 규명. 임계·스크립트를 한 글자도 바꾸지 않는다 |
| **IC-1 FAIL** (`c_neg_strict` 의 precision 이 `c000` 보다 CI 비겹침으로 낮지 않음) | **V6 — 495콜 이내 종결.** precision 축 폐기 후 새 사전 선언을 커밋해야 다음 실행 가능 |
| **INV-2 위반** (라벨 시트 sha256 변동) | 그 시점 이후 축 값이 비교 불가 → **즉시 중단** |
| **R1~R5 위반** | 그 후보만 `UNJUDGED`(종료코드 3). 실험은 계속 |
| **T1~T4 충족** | 즉시 정지. 정지는 실패가 아니다. T4 는 **표본 부족 → 판정 불가**로 종결(V5) |
| **예산 소진** | 남은 조건은 **미실행**. 절반 실행으로 비교하지 않는다 |
| **라벨이 틀렸다고 판단됨** | 시트를 고치지 않는다. 실험을 중단하고 재라벨 프로토콜을 사전 선언한 뒤 **처음부터** 다시 |

---

## 7. 🔴 동결(freeze) 선언

정본 §15.3 의 10항목. **결과 열람 후 변경하면 실험 무효다.** 오른쪽이 고정 위치다.

| # | 동결 항목 | 어디에 고정돼 있는가 |
|---|---|---|
| 1 | 조건 정의 C0/C1/C2 와 부모 선택 방식, C1 의 `PARENT_SEED` | 정본 §12.1 / 이 문서 §2 / `PARENT_SEED = 20260731` (F5, 코드 미구현) |
| 2 | C0 의 수락규칙 (부등호·CI 미사용) | 정본 §12.1 D13 / 이 문서 §2 |
| 3 | 조건별 후보 예산 10개(1,650콜) | 정본 §12.3 / `CALL_BUDGET = 1650` (`mh_front.py` L42) |
| 4 | ablation 3종 정의 + 각각의 반증 형태 | 정본 §12.2 / 이 문서 §2 |
| 5 | 우선순위 P0~P7, 컷라인 P4, 컷은 아래에서 위로만 | 정본 §12.2 / 이 문서 §5 |
| 6 | 집합 dominance 정의 D-dom / D-str, **CI 겹침 동률을 커버로 세는 규약** | 정본 §14.1 / 이 문서 §1 |
| 7 | 판정표 V1~V7 매핑 (V3·V4 를 그대로 쓴다) | 정본 §14.2 / 이 문서 §1 |
| 8 | 고정값 F1~F12 — `B=2000`, `seed=20260730`, 판정 CI = `ci_qid`, 모델, 라벨 해시 | `mh_objectives.py` L38~L41 (`SEED`·`B`·`CI_LO_PCT/CI_HI_PCT`·`CI_USED_FOR_JUDGMENT`), `mh_front.py` L43 `MODEL_FIXED`, L45 `DEFAULT_CI`; F7 해시 = 이 문서 §3; F8 빌더 커밋 `19e0081` |
| 9 | §14.5 한계 4개를 Abstract·결론에 병기 | 정본 §14.5 |
| 10 | 실행 순서표 1~10 단계 — 특히 판정기 커밋(3) < 러너(5), 검침(6~9) < C2(11) | 정본 §15.2 / 판정기 커밋 `5df830a` 가 러너 부재 시점에 존재함이 git 이력으로 검증 가능 |

추가로 동결되는 임계(정본 §10.2 금지 2): front 상한 8(`FRONT_CAP` L40), T1 = 3라운드
(`STALL_LIMIT` L41), T2 = 1,650콜(L42), R1~R5(`mh_objectives.py` L50~L54),
IC recall ≥ 0.30(`instrument_check_score.py` 의 `RECALL_THRESHOLD`, 변경 금지).

### 변경 허용 항목 (정본 §15.3 후단)

- **버그 수정**: 판정기·러너의 명백한 오류. 커밋 이력에 남기고 사유를 결과 문서에 적고,
  영향받는 후보를 **전부 재계산**한다(재측정 아님 — L4~L5 층은 결정론).
- 서술·표 배치·차트 스타일.
- 참고 필드(`n_split`·`elapsed_median`·`prompt_chars_median`·`search_cost_calls`)의
  **보고 여부**. 축으로 **승격은 금지**.
- 다음 실행을 위한 새 사전 선언 작성. **이번 판정에 소급 적용하지 않는다.**
- L2(LLM 판정) 재실행: 허용하되 `gate/scripts/mh_replication/` 에만 기록하고
  `mh_archive.jsonl` 을 덮어쓰지 않는다. 판정은 원 아카이브 값으로만 한다.

---

## 8. 루프 경계 (정본 §7)

> **INV-1**: 루프 안은 루프 밖을 읽을 수 있으나 **쓸 수 없다.**
> **INV-2**: `phase1_human_label_sheet.xlsx` / `.json` 의 sha256 은 전 라운드 동일.
> 다르면 비교 불가이므로 실행 중단.
> **INV-3**: `CLAUDE_MODEL = claude-sonnet-4-6` 고정. 모델·max-turns·타임아웃을 바꾸는
> 변이는 `INVALID`.
> **INV-4**: 판정 임계(R1~R5, IC recall ≥ 30%, front 상한 8, T1~T4)는 본 실행 중 변경 불가.
> **INV-5**: 채점기·CI 계산기·front 계산기는 **결과 열람 전 커밋** — `5df830a` 로 이행됨.
> **INV-6**: proposer 는 자기 후보의 축 점수를 계산하지 않는다.

**루프 밖**: 사람 라벨 55건, 축 정의·측정 함수, `mh_objectives.py`, `mh_front.py`,
R1~R5, 계기 검침 게이트, 결정론 채점기(`gate/src/reflection_gate/`), 모델 ID, 3판·
fail-closed 규약, bjkim 의 최종 운영점 선택.
**루프 안**: proposer, 저지 지시문(`phase3_build_prompts.JUDGE` 등), 빌더 조립 순서,
`mh_archive.jsonl`(append 만).

**`mh_guard.py` (미구현) 가 검증할 항목** — 위반 시 `SystemExit`:

1. INV-2 — 라벨 시트 2개 파일의 sha256 이 매니페스트 값과 일치.
2. INV-3 — 후보 `harness.model == "claude-sonnet-4-6"` (alias 불허).
3. `mh_manifest.json` ↔ 후보 필드 일치 (F1·F2·F5·F6·F7·F8·F11).
4. `--init --condition <C0|C1|C2>` 로 매니페스트 생성 및 조건 고정.
5. F12 실행 환경 기록(python 버전·패키지·OS).
6. 원장 append-only 위반(행 삭제·덮어쓰기) 검출.

전례: `phase3_build_prompts.assert_single_variable()` 이 변인 오염 시 예외를 던지고
`phase3_run_judge.py` 가 매 건 호출한다 — 검증을 문서가 아니라 코드에 둔다.

---

## 9. 결정론 경계 (정본 §13.3)

L1 프롬프트 생성 ✅ / **L2 LLM 판정 ❌ 비결정론** / L3 다수결 ✅ / L4 축·CI ✅ /
L5 dominance·front·솎아내기·T1~T4 ✅ / L6 부모 선택 C0·C2 ✅, C1 = seed 고정 재현.
검증은 **L3~L6 만** 대상(D-1 원자료 고정 재계산 바이트 동일, D-2 CI 재현(IC-2 포함),
D-3 C1 부모 dry-run 2회 동일, D-4 아카이브 → front 복원).
보장하는 것은 **"같은 원자료에서 같은 판정"**, 보장하지 않는 것은 **"같은 프롬프트에서
같은 원자료"** 다.

---

## 10. 미정 항목 — 설계에 없어서 채우지 못한 빈칸

**임의로 정하지 않았다.** 아래는 실행 전에 확정돼야 하며, 확정은 정본 수정 또는 별도
사전 선언 추가로만 한다.

| # | 빈칸 / 상충 | 누가 · 언제까지 |
|---|---|---|
| U1 | 정본 §4.3 **문장 상충** — "리샘플 단위는 **claim** 으로 한다" 직후 "판정에는 보수적인 **문항 클러스터 CI**(`ci_qid`)를 쓴다". 코드는 후자를 채택(`CI_USED_FOR_JUDGMENT = "ci_qid"`). 판정값은 이미 고정이므로 결과에 영향 없으나 문면이 충돌 | bjkim · 결과 열람 전 (문면 정정) |
| U2 | 정본 §5.1 `mh_front.json` 예시의 `pruned.rule` = "크기상한 초과 — **crowding** 최소" 가 §5.4 의 crowding 기각과 상충(예시 잔재). 코드는 `"§5.4-2 …"` / `"§5.4-3 …"` 문자열 사용 | bjkim · 결과 열람 전 |
| U3 | `status = "REJECTED_C0"`(정본 §12.1)이 §5.1 status enum 5종과 `mh_front.py` 상태 상수(L48~L49)에 **없다** | C0 러너 작성 전 |
| U4 | 정본 §13.2 가 적은 CLI `mh_front.py --condition C2` 가 실물과 불일치 — 실물은 서브커맨드 + `--ci` 뿐이고 `--condition` 플래그가 없다. 조건별 원장 분리 방식(단일 `ARCHIVE` 경로 L35)도 미정 | 러너 작성 전 |
| U5 | **R4 UNRESOLVED 비율의 분모 미규정.** 코드가 단위 기준·원자료(건×판) 기준 중 **큰 쪽**으로 fail-closed 판정하는 임시 규약을 씀(`sample_gate()` 주석에 "설계 미규정" 명기) | 첫 후보 측정 전 |
| U6 | **부트스트랩 리샘플에서 분모가 0 이 되는 표본의 처리 미규정.** 코드는 그 축에서만 제외(`bootstrap()` 주석에 "설계 미규정" 명기) | 첫 후보 측정 전 |
| U7 | IC-1 의 **`c_neg_loose` 판정 기준 미기재.** §8.2 는 `c_neg_strict` 기준만 고정했다 — loose 가 기대(과소검출)와 다를 때의 처리 없음 | IC-1 실행 전 |
| U8 | **IC-0 재실행 경로 미정.** `instrument_check_run.py` 는 기존 `instrument_check_run{1,2,3}.jsonl` 을 읽어 완료분을 건너뛰는 resume 구조다 — 파일이 이미 완성돼 있으므로 재실행은 **0콜**이 되고, 예산표의 165콜과 맞지 않는다. 기존 원자료 보존(§5.3 물리 삭제 금지)과 재실행을 어떻게 양립시킬지 미정 | 6단계 실행 전 |
| U9 | **집합 dominance(D-dom / D-str) 계산 구현체 미지정.** §13.2 매니페스트에 해당 스크립트가 없는데 §15.2 17단계는 "V1~V7 중 하나 **자동** 선택" 을 요구 | 조건 완주 전 |
| U10 | **예산 총계 불일치.** §12.3 "전체 상한 8,745" = 495 + 1,650×5 (P7 제외 기준)인데 같은 표에 A-CI(실행) 1,650 행이 있어 행 합계는 10,395 가 된다. 컷라인 5,445 는 일관됨 | bjkim · 결과 열람 전 |
| U11 | **`mh_propose.md` 의 "수정 가능 표면 목록" 미작성.** §15.2 완화 수단 1이 조건 간 동일 고정을 요구 | C2 실행 전 커밋 |
| U12 | **C0 의 T1 대체 규칙("활성 harness 3라운드 불변") 구현 위치 미정.** `STALL_LIMIT`(L41)은 front 기준 | C0 러너 작성 전 |
| U13 | **`mh_manifest.json` 미생성** — F7(라벨 해시)·F12(실행 환경) 기록 위치가 없다. `mh_guard.py` 미구현 | 5단계(러너·매니페스트) |
| U14 | A-S3·A-FS 의 **실사용 후보 수**(상한 미달 예상) — 정본이 "실행 전 예측하지 않는다" 로 남긴 항목. 예측하지 않고 비워 둔다 | 해당 없음 (규칙상 공란 유지) |

---

## 11. 서명란

| 항목 | 내용 |
|---|---|
| 작성일 | 2026-07-31 (KST) |
| 작성 주체 | 이 레포의 작업 세션 (정본 §15.2 1단계 산출물) |
| 작성 시점 상태 | 판정기 커밋 `5df830a` 완료 · 러너 전부 미구현 · 후보 측정 0건 · 검색 결과 열람 0건 |
| 확정 시점 | **이 문서를 커밋한 시각.** 이후 §7 동결 항목은 결과 열람 후 변경 불가 |
| 정본 커밋 | `7d7d28b` (이 문서 작성 중 정본을 수정하지 않았음 — `git diff` 로 확인) |
| 미정 항목 | 14건 (§10 U1~U14). U8·U9·U11·U13 은 실행 전 해소 필수 |

**bjkim 승인**

- [ ] §1 주장 C 와 V1~V7 판정표 (특히 V3·V4 를 그대로 쓴다는 것)
- [ ] §2 조건 정의와 조건별 예산 동일(10후보)
- [ ] §3~§4 축 2개·R1~R5·판정식·front 상한 8
- [ ] §5 실행 순서와 컷라인 P4(5,445콜)
- [ ] §7 동결 10항목 + 변경 허용 항목
- [ ] §10 미정 항목 처리 방침 (U8·U9·U11·U13 선해소)

승인 서명: ____________________  일자: ____________
