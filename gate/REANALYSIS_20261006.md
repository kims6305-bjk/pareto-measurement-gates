# 0콜 재분석 (2026-10-06) — 군집 부트스트랩 · 판정기 일치도

**LLM 호출 0건.** 이미 레포에 있는 원자료만 다시 읽어 새 측정을 냈다.
코드 `scripts/zero_call_reanalysis.py`, 산출 `reanalysis_20261006/results.json`, 그림 `reanalysis_20261006/figures/F1~F4`.
모든 수치는 results.json에서 왔다. 그림은 matplotlib artist에서 읽은 값을 JSON과 대조한다.

정의는 새로 만들지 않았다. 다수결·문제 판정 집합·recall/precision·LCG 리샘플러·percentile은 `mh_objectives.py`에서,
Phase 3 다수결·Wilson은 `phase3_score.py`에서 import해 그대로 쓴다.
c000 원자료는 `archive_sonnet46_20261006/mh_c000_run*.jsonl`(유효본)이다. 같은 폴더의 `mh_ic1_*`(무효)는 읽지 않는다.
사람 라벨은 `phase1_human_label_sheet.xlsx`이고 sha256은 보관 objectives와 같다.

재현: `python3 scripts/zero_call_reanalysis.py --selftest`(시스템 python3 사용 — uv venv에는 matplotlib이 없다).

## 1. 군집 부트스트랩 — 논문 §7.2 (i.i.d. 가정 위배)

**재현 검사:** 보관된 `mh_c000_objectives.json`의 CI를 `mh_objectives.bootstrap`(seed 20260730, B=2000)으로 다시 계산했다.
claim CI와 qid CI 모두 **4자리까지 일치**했고, 표본을 보관하는 내 리샘플러로 계산한 값도 같았다.
같은 리샘플러를 B=10,000으로 돌렸다.

**클러스터 구조**(qid = `id.split('-')[0]`, arm A/B는 같은 문항으로 묶음)
- 단위 55개, 클러스터 28개
- 클러스터 크기 분포: 1개짜리 13 · 2개짜리 8 · 3개짜리 4 · 4개짜리 2 · 6개짜리 1
- 사람 라벨 문제 11건이 **7개 클러스터**에 몰려 있다. 클러스터별 문제 수는 1건 4개, 2건 2개, 3건 1개다.

| 대상 (sonnet-4-6) | 축 | 값 | iid CI (B=10k) | qid CI (B=10k) | 설계효과 var_qid/var_iid |
|---|---|---|---|---|---|
| c000 archive | recall | 0.6364 (7/11) | [0.3333, 0.9091] | [0.3750, 1.0000] | **0.96** |
| c000 archive | precision | 0.5833 (7/12) | [0.2857, 0.8750] | [0.2500, 0.9091] | **1.35** |
| 계기 검침 (instrument_check) | recall | 0.8182 (9/11) | [0.5556, 1.0000] | [0.5556, 1.0000] | 1.41 |
| 계기 검침 | precision | 0.6923 (9/13) | [0.4167, 0.9286] | [0.3636, 1.0000] | 1.46 |

c000 혼동행렬(사람 × 판정기 다수결)은 S→{SUPPORTED 39, CONTRADICTED 3, INSUFFICIENT 2}, C→{CONTRADICTED 4, SUPPORTED 3, SPLIT 1}, I→{INSUFFICIENT 2, CONTRADICTED 1}이다.
문제 검출 2×2로는 TP 7, FP 5, FN 4, TN 39다.

**읽는 법**
- precision과 계기 검침 두 축에서는 군집이 분산을 **35~46% 부풀린다**. i.i.d. CI는 과신이다.
- c000 recall의 설계효과는 1 미만(0.96)인데 qid CI는 위로 밀려 상한 1.0에 닿았다. 분산은 거의 같지만 분포 모양이 다르다는 뜻이다.
  recall의 실질 표본은 문제가 있는 **클러스터 7개**다. qid 리샘플 9,996/10,000만 분모가 0이 아니었다.
- 💡 `mh_objectives`가 판정에 qid CI를 쓰는 선택(§4.3 F3)은 precision 쪽에서 실측으로 정당화된다. recall 쪽 근거는 분산 증가가 아니라 분포 비대칭이다.

## 2. 판정기 일치도 — 논문 §7.3 (단일 모델)

3판 간 일치도(같은 모델 `claude-sonnet-4-6`, 같은 프롬프트로 3회 반복)

| 집합 | n | 3판 만장일치 | Fleiss κ (4범주) | Fleiss κ (문제/비문제) |
|---|---|---|---|---|
| Phase 3 조건 A | 275 | 98.9% (272) | 0.197 | −0.004 |
| Phase 3 조건 B | 275 | 98.9% (272) | 0.796 | 0.796 |
| c000 archive | 55 | 92.7% (51) | 0.864 | 0.870 |
| 계기 검침 | 55 | 89.1% (49) | 0.818 | 0.866 |
| 옆방1 SciFact | 55 | 98.2% (54) | 0.981 | 0.974 |
| 옆방2 KLUE | 55 | 96.4% (53) | 0.959 | 1.000 |

**조건 A vs B 다수결 라벨**(양쪽 모두 다수결인 273건, `phase3_result.json` n_usable과 일치)
- 일치는 269/273(98.5%)다. Cohen κ는 4범주와 이진 모두 **0.00**이다.
- 불일치 4건은 모두 SUPPORTED→INSUFFICIENT다.

**문제 판정률**(F1)
| 조건 | 다수결 단위 | 원자료 행(판×단위) |
|---|---|---|
| A | 0/273 = 0.0% · Wilson [0.0%, 1.39%] | 3/825 = 0.36% · [0.12%, 1.06%] |
| B | 6/275 = 2.18% · Wilson [1.00%, 4.68%] | 15/825 = 1.82% · [1.10%, 2.98%] |

**읽는 법**
- 조건 A의 κ가 0.2와 0에 가까운 것은 **불안정해서가 아니라 κ 역설 때문이다.** A는 거의 모든 라벨이 SUPPORTED(820/825)라서 우연 일치가 1에 가깝다.
  같은 이유로 A vs B Cohen κ=0은 "일치 없음"이 아니라 **미정보**다. A 다수결이 상수라서 κ가 정의상 0이 된다.
  이런 집합에서는 만장일치율과 원 교차표를 함께 보고해야 한다.
- 원자료 행 기준으로 A와 B의 Wilson 구간은 겹치지 않는다(A 상한 1.06% < B 하한 1.10%). 하지만 이 825행은 독립이 아니다.
  같은 단위를 3판 반복한 것이고, 불일치 6건은 5문항에 몰려 있다(PHASE3_VERDICT §3). 그러므로 **사전등록 판정(McNemar p=0.125, H1 기각)을 뒤집지 않는다.** 방향 기록일 뿐이다.

## 3. 그림

| 파일 | 내용 | 값 출처 |
|---|---|---|
| `figures/F1_phase3_problem_rates.png` | Phase 3 A/B 문제 판정률과 Wilson CI | `phase3.problem_rates` |
| `figures/F2_c000_iid_vs_cluster_ci.png` | c000 recall/precision의 iid CI vs qid CI, 설계효과 | `c000_archive_sonnet46.bootstrap_B10000` |
| `figures/F3_axis_flip_case1.png` | 계측 실패 사례 1 — 같은 dedup이 축에 따라 −4.5% / −0.6% / +9.5% | `axis_flip_case1` (MEASUREMENT_FAILURES.md 표 파싱) |
| `figures/F4_judge_run_agreement.png` | 6개 집합의 3판 만장일치율과 Fleiss κ | `phase3.agreement_*`, `*.agreement_3run`, `other_3run_agreement` |

## 4. 한계 (정직하게)

- **§7.3을 해소하지 않는다.** 3판은 모두 같은 모델·같은 프롬프트다. 높은 일치도는 **안정성(재현성)**을 보여 줄 뿐 **이식성**을 보여 주지 않는다.
  다른 모델이 같은 판정을 내는지는 여전히 미검증이다. 판정기 대 사람 일치(혼동행렬)도 라벨러가 1명(저자)이다.
- **§7.2를 정량화했을 뿐 해소하지 않는다.** 클러스터는 28개이고 문제가 있는 클러스터는 7개다. 이렇게 클러스터가 적으면 클러스터 부트스트랩 percentile CI 자체가 과소 포함(under-coverage)할 수 있다.
  설계효과 1.35~1.46은 하한에 가까운 추정으로 읽어야 한다.
- 논문 §7.2 본문은 "문제 10건이 답변 8개"라고 적고 있다. 여기 수치(11건/문항 7개)와는 단위가 다르다. 본문은 답변(arm) 단위, 여기는 arm을 합친 qid 단위다.
  어느 표본을 가리키는지 저자 확인이 필요하다.
- F3 수치의 원자료는 이 레포에 없다. 익명화된 문서 표에서 파싱한 값이고, 문서가 바뀌면 스크립트가 assert로 멈춘다.
- c000과 계기 검침은 같은 55단위·같은 라벨을 쓴다. 두 행을 독립된 반복 실험으로 읽지 않는다.
