# 파레토 메타하네스 설계 — front 를 탐색 엔진으로 쓰는 게이트

**작성일**: 2026-07-30
**상태**: 설계 문서. 코드는 아직 없다. §9가 구현 계획이고 §10이 확정 순서다.
**표기 규칙**: **[사실]** = 정독본·레포 파일에 명시된 것(출처 표기 필수) /
**[설계]** = 우리 결정 / **[미확인]** = 원문에서 확인 불가

**근거 자료 (전부 read 로 통독함)**

| 약칭 | 파일 |
|---|---|
| `src1` | `(로컬 정독본) meta_src1_arxiv.md` (Self-Harness, arXiv 2606.09498) |
| `src2` | `(로컬 정독본) meta_src2_repo.md` (Awesome-Harness-Self-Improvement, MIT) |
| `src3` | `(로컬 정독본) meta_src3_lilian.md` (Lilian Weng, Harness Engineering, 2026-07-04) |
| `src4` | `(로컬 정독본) meta_src4_metaharness.md` (Meta-Harness, arXiv 2603.28052) |
| `src5` | `(로컬 정독본) meta_src5_motsr.md` (MOT-SR, arXiv 2607.29561 — 2026-08-03 추가) |
| `src6` | `(로컬 정독본) meta_src6_tracerouter.md` (TRACE-Router, arXiv 2607.22465 — 2026-08-03 추가) |
| `skill` | `(로컬 스킬) pareto-optimization-gate/SKILL.md` |
| `P4` | `gate/PHASE4_PREREGISTRATION.md` |
| `IC` | `gate/INSTRUMENT_CHECK_PREREG.md` · `gate/INSTRUMENT_CHECK_RESULT.md` |

**전제 (재논증하지 않음, 지시에 따라 확정 판정으로 사용)**

1. Self-Harness 는 Pareto 용어 0회지만 수락규칙 `Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in,Δ_ho) > 0`
   으로 비지배 판정을 **진입 게이트**에 구현했다. 스칼라 합산을 명시적으로 거부한다.
   그러나 front 를 아카이브하지 않는다 — 활성 harness 는 항상 1개.
2. Meta-Harness 는 Pareto 11회 언급 + front 를 **반환**하지만, dominance 판정식이 원문에
   없고, 아카이브는 append-only, `"imposes no parent-selection rule"` 이라 탐색이 front 를
   활용하지 않으며, 최종 선택도 자동 규칙 없이 사실상 정확도 최대 끝점이다.
3. **front 를 탐색 엔진으로 쓰는 주체가 두 논문 모두에 없다.** 이 빈자리가 우리 기여 지점이다.
4. evaluator 와 permission control 은 harness 를 진화시키는 루프 **밖**에 있어야 한다
   (`src2` §5 도입부, `src3` Future Challenges — 독립적으로 같은 처방).

---

## 1. 문제 정의 — 단일 지표 최적화는 harness 개선에서 왜 실패하는가

### 1.1 문헌이 말하는 실패 구조

**[사실]** harness 는 성능의 공동 결정 요인이며 최적 harness 는 모델별로 다르다
(`src1` §2). 그리고 harness 설계가 실행 가능한 탐색 공간이 되는 순간 코딩 에이전트가
그 공간을 탐색할 수 있다 (`src3` 주장 4):

> "Still, the important lesson is clear: once harness design becomes an executable search space, a strong coding agent can exploit the same design space human engineers use." (`src3` §9 인용 9)

**[사실]** 그런데 그 탐색을 **하나의 스칼라**로 판정하면 문헌이 열거한 실패 모드가
그대로 열린다.

- **reward hacking / 신호 원천별 착취.** `src3` Future Challenges 5번:
  "If the reward comes from unit tests, the agent may overfit to tests; if it comes from a judge model, it may learn reward hacking tricks specific to this judge; if it comes from benchmark scores, it may exploit benchmark artifacts." (`src3` §7)
- **노이즈를 성과로 선언.** `src3` 이 인용한 Bubeck et al. (2025) 의 "p-hacking and
  eureka-ing" — 모델이 "numerical duct tape" 를 붙이고 승리를 선언한다 (`src3` §7).
- **accuracy 과집중.** `src2` §4(a) 가 정리한 *AI Agents That Matter* (arXiv:2407.01502):
  에이전트 벤치마크가 **accuracy vs cost** 를 무시하고 정확도에 과집중하며 holdout 이 약하다.
- **다양성 붕괴.** `src3` Future Challenges 4번: 진화·RL 루프가 알려진 고보상 패턴만
  착취하며, "the best path may initially look worse under the current evaluator" (`src3` §6).

**[사실]** 두 논문 모두 스칼라화를 **명시적으로 거부**한다. Self-Harness:
> "Proposals that only trade off one split against the other are rejected, even if their total pass count increases." (`src1` §3.4, 인용 8)

Meta-Harness:
> "we can express a joint preference for both accuracy and context cost rather than committing to a single scalar objective in advance" (`src4` §4.1, 인용 5)

즉 **"단일 지표로 판정하면 안 된다"는 것은 우리 주장이 아니라 두 논문의 공통 입장이다.**
빈 곳은 그 다음이다 — 어떻게 판정하고, 판정 결과를 탐색에 어떻게 되먹이는가.

### 1.2 우리 쪽 실패 3건 — 같은 병이 세 층에서 각각 다르게 났다

**[사실]** probe-graph 는 Phase 1~3 에서 세 번 연속 판정 불가를 냈고, 세 번의 원인이
모두 달랐다. 출처는 각 판정 문서다.

**실패 ① Phase 1 — 측정의 재현성을 안 봤다.**
`PHASE1_VERDICT.md` §8: "저지 판정은 3회 실측에서 재현성이 없었고(합의 게이트를 도입한
이유), 프로브는 44건 중 42건 재현되었다." 단일 실행 수치를 성능으로 보고하면 허위보고다.
같은 문서 §4: 회수율 90% vs 70% 의 Wilson 구간이 [59.6%, 98.2%] vs [39.7%, 89.2%] 로
**겹친다** — 즉 "90%" 라는 점 추정은 판정 근거가 되지 못했다.

**실패 ② Phase 2 — 사람 라벨의 기저율을 안 봤다.**
`PHASE2_VERDICT.md` §2: 파일럿 기저율 **1/30 = 3.3%** (Wilson [0.6%, 16.7%]). 후보 풀
201건을 전량 라벨해도 기대 문제 사례 6.7건으로 목표 55건에 미달. 그래서 171건을 라벨하지
않고 종결했다 — "원안 완주를 하지 않는다" 는 판단의 근거가 **파레토 열등**이었다(같은 §3).

**실패 ③ Phase 3 — 결과변수(저지 판정)의 기저율을 안 봤다.**
`PHASE3_VERDICT.md` §2: 확증 집합 **271건 중 조건 A 의 문제 판정이 0건(0.0%)**.
H1 은 "A 에서 문제 판정된 것이 B 에서 뒤집히는가" 이므로, **뒤집힐 대상 자체가 없었다.**
1,650콜을 태우고 검정 불가. 같은 문서 §2.1 이 원인을 확정한다: 순환 논증 차단 규칙이
Phase 1 에서 문제를 발견한 28문항을 확증 집합에서 **전량 제거**했다(확증 0개 / 탐색 28개).

**[사실]** 그리고 이 세 실패의 공통 구조를 `IC` §0 이 이미 표로 정리해 두었다:

| Phase | 안 잰 것 | 결과 |
|---|---|---|
| 1 | 프로브 판정의 재현성 | 3회 실측에서 흔들림 발견(사후) |
| 2 | 사람 라벨 기저율 | 파일럿에서 3.3% 확인 → 목표 미달 |
| 3 | 저지 판정 기저율 | 0% → 검정 불가 |

> "세 번 다 '표본 크기는 셌지만 **측정 도구가 신호를 잡는지**는 안 쟀다'." (`IC` §0)

### 1.3 진단 — 세 실패는 "지표가 하나였다"의 세 가지 얼굴이다

**[설계]** 세 실패를 하나의 명제로 접으면 다음이 된다.

> **P1**: 성능 지표 하나만 보는 판정은, 그 지표가 **측정 가능한 상태인지**를 판정에
> 포함하지 않는다. 재현성(Phase 1), 사람 라벨 기저율(Phase 2), 결과변수 기저율(Phase 3)은
> 전부 "성능축 바깥의 축"이며, 축이 하나뿐인 설계에서는 이것들이 **판정 대상이 아니라
> 사후 변명거리**로 밀려난다.

`PHASE3_VERDICT.md` §6 이 같은 말을 다르게 한다: "264건이라는 숫자는 분모였고, 필요한
것은 분자의 기저율이었다."

**[설계]** 그리고 성능축 하나로는 아예 판정이 뒤집히는 사례가 우리 데이터에 있다.
`skill` §"모서리점에서는 레이어 추가가 곧 열등 이동": P1 A/B 에서 baseline 이
(인용오류 0%, 정확도 99.2%) 인 모서리점이었고, 검증 레이어를 얹으니 상방 0 + 과교정
−0.84% = 순수 파레토 열등 이동이었다. **성능축만 보면 "동률"이므로 채택도 기각도
정당화되지 않는다. 축을 하나 더 놓아야 "열등"이라고 말할 수 있다.**

**[설계]** 따라서 이 설계의 문제 정의는 다음 한 줄이다.

> **harness 후보를 판정할 때, 성능축과 함께 "그 성능 수치가 신뢰 가능한가"를 축으로
> 올린다. 그리고 그 다목적 판정 결과(front)를 버리지 않고 다음 후보 생성의 입력으로
> 되먹인다.** 앞부분은 `skill` 이 이미 갖고 있고, 뒷부분이 두 논문에 없는 빈자리다(전제 3).

---

## 2. 선행연구 위치

**[사실]** 4열 대조. 근거는 각 칸에 표기.

| | Pareto 언급 | dominance 판정식 구현 | front 유지(아카이브) | front 를 탐색에 활용 |
|---|---|---|---|---|
| **Self-Harness** (`src1`) | **0회** (`src1` §6: Pareto/multi-objective/dominance/trade-off 전문 검색 0건) | **있음** — `Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in,Δ_ho) > 0` (`src1` §3.4). 확률적 평가 시 반복 후 누적 통과 수에 같은 규칙 적용 | **없음** — 활성 harness 단일 계보 `h₀,h₁,...`, 거부 후보는 로그만 (`src1` §3.4) | **해당 없음** (front 가 없음) |
| **Meta-Harness** (`src4`) | **11회** (`src4` §11-2 관찰) | **없음** — "we evaluate candidates under Pareto dominance" 문장뿐, 부등호·동률·노이즈 규칙 전부 미기재 (`src4` §5-4, **[미확인]**) | **append-only** — `D ← D ∪ {(H,E_H)}` 가 유일한 갱신 연산. 제거·pruning·크기제한 서술 없음 (`src4` §5-3·5-5) | **없음** — `"imposes no parent-selection rule"` (`src4` §7, 인용 2). front CLI 는 "optional, but helpful" (`src4` 인용 8) |
| **GEPA** (`src2`) | 있음 — "Genetic-**Pareto** reflective optimizer" (`src2` §4(a)) | **[미확인]** — 우리는 GEPA 원문을 읽지 않았다. `src2` 는 목록 항목 1줄이고 `src4` Appendix E 의 GEPA 대조는 피드백 풍부함 축만 다룬다 | **[미확인]** (같은 이유) | **있는 것으로 보고됨** — `src4` §7 이 "GEPA 의 Pareto 기반 부모 샘플링" 을 자기와 대비되는 것으로 지목. 단 `src4` Appendix E 는 그 차이를 **언급조차 하지 않는다**(`src4` §7 관찰) |
| **MOT-SR** (`src5`, 2607.29561, 수식발견 도메인) | 있음 — "dynamic Pareto front" (abstract) | **있음** — 3축(NMSE_ID/NMSE_OOD/AST 복잡도). 단 OOD 가 훈련셋 내부 백분위 분할이라 진짜 홀드아웃 아님 (`src5`) | **있음** — 단 pruning 규칙 `PopulationManagement` 정의가 논문에 없음 (`src5`) | **있음** — front 위 식들만 `SyntaxDiv` 다양성 점수 → softmax 샘플링으로 부모집합 구성 (§3.3), Meta Strategy Generator 는 front 전체를 입력 (Alg.1). 🔴 단 **front-부모선택 규칙 자체의 ablation 은 없음** — 다목적 vs 단일목적, 구조모듈 유무만. 사전등록·통계검정·시드반복 전무(전 표가 단일 실행값), 탐색예산 비대칭("traditional baselines are allowed more iterations") |
| **TRACE-Router** (`src6`, 2607.22465, LLM 라우팅 도메인) | 있음 — "non-dominated Pareto frontier points" (abstract) | 스칼라화 — r^(α)=(1−α)·a−α·ℓ̃ 가중합 (Eq.11). 비지배 판정은 학습 신호에 미사용 | **없음** — α별 정책 상태 완전 격리: "observations are never shared across scalarizations" (§3.4) | **없음** — front 는 사후 평가 문법 전용(Fig.3 "rings mark the non-dominated set"). 대신 이식 가치: ① 귀속 처방 = "결정 입자를 감독 단위까지 굵게"("the finest-grained choice such a signal can credit unambiguously"), ② front 점유 주장의 함정 — "a random mixture of two endpoint models also traces the line segment between them in expectation" → latency-matched 대조군 요구 (§4.2) |

**[설계] 빈칸이 우리 자리다 — 단, 2026-08-03 갱신으로 문구를 좁힌다.** Self-Harness 는
판정식을 갖고 front 를 안 갖는다. Meta-Harness 는 front 를 갖고 판정식을 안 갖는다.
GEPA(프롬프트 계층)와 MOT-SR(수식발견 도메인)은 front-as-parent 를 실제로 쓴다 —
그러므로 "front 를 탐색 엔진으로 쓰는 주체가 없다" 는 **전 도메인 주장으로는 성립하지
않으며**, 정직한 주장은 "**harness 자기개선 계층에는 없다**" 다. 이 좁힘은 손해가 아니다:
타 계층·타 도메인의 front-as-parent 실증(MOT-SR 의 국소수렴 탈출, GEPA 의 부모 샘플링)은
우리 C2 규칙의 **독립 지지 증거**가 되고, 동시에 MOT-SR 이 front-부모선택 규칙 자체를
ablation 하지 않았다는 사실은 **우리 C1(무작위 부모) vs C2(front 부모) 대조가 문헌에 없는
측정**임을 보존한다. TRACE-Router 는 반대편 경계를 세운다 — front 를 사후 문법으로만 쓰는
스칼라화 계열이 주류이며, front 점유 주장에는 무작위 혼합 대조군이 필요하다는 §4.2 논리는
우리 결과 보고에 그대로 이식한다. 우리가 새로 발명할 것은 다목적 최적화 이론이 아니라 —
그건 오래된 수학이다 — **harness 후보 아카이브 위에서 이 조각들의 접합부와, 그 접합부에
우리 실패 3건에서 나온 노이즈 규율을 박아 넣는 것**이다.

---

## 3. 🔴 목적 축 정의 — 무엇을 동시에 최적화하는가

### 3.1 축 선정 원칙

**[사실]** `skill` §0: "지표쌍·목표함수 먼저 확정 (측정 전)". 그리고 §함정:
"사후 목표 선택 = Goodhart."

**[사실]** `P4` §3 은 이미 3축을 선언했고, **비용축을 사후에 정하지 않았다는 증거**를
코드로 제시한다: `phase3_run_judge.py` 가 Phase 3 실행 전부터 `elapsed` 를 기록하고
있었다. 실측 확인: `gate/scripts/phase3_run_judge.py` 의 기록 dict 에
`"elapsed": round(time.time() - t0, 1)` 이 있고, `instrument_check_run.py` 도 동일 필드를
기록한다. **[사실]**

**[설계]** `P4` §3 을 폐기하지 않고 **개정**한다. 개정 이유는 결과를 봐서가 아니라,
`P4` 자체가 DRAFT 이고(문서 상단 "상태: 초안(DRAFT)"), P4 §3 이 정한 3축이 §1.3 의 진단
(재현성·기저율이 축이어야 한다)을 반영하지 못하기 때문이다. 개정 시점은 **어떤 변이도
생성하지 않은 지금**이며, 이 문서가 그 개정의 사전 선언이다.

### 3.2 후보 축 전수 판정

| # | 후보 축 | 측정 함수 | 데이터 출처(실측 확인된 경로) | 판정 |
|---|---|---|---|---|
| A1 | **검출 회수율 (recall)** | 사람 라벨 문제건 중 판정기가 CONTRADICTED/INSUFFICIENT 로 잡은 비율. 3판 다수결. | `gate/scripts/phase1_human_label_sheet.xlsx` (라벨링 시트 G열 = 사람 라벨 S/C/I) + `phase1_human_label_sheet.json` (본문). `instrument_check_score.py` 가 이미 이 계산을 함 | **채택 (축 1)** |
| A2 | **정밀도 (precision)** | 판정기 문제판정 중 사람도 문제로 본 비율 | 같음. `instrument_check_score.py` 가 이미 `precision_reported_only` 로 계산·기록 | **채택 (축 2)** |
| A3 | 3판 판정 일치율 (안정성) | 3 run 중 3표 일치 건수 / 전체. SPLIT 은 불일치 | `instrument_check_run{1,2,3}.jsonl` (id·run·label 필드 실측 확인) | **기각 → 노이즈 처리로 흡수** (§3.4) |
| A4 | `elapsed` 중앙값 (지연) | 건별 `elapsed` 의 median | `phase3_judge_*.jsonl`, `instrument_check_run*.jsonl` 의 `elapsed` 필드 | **기각** (§3.4) |
| A5 | 프롬프트 문자수 (컨텍스트 비용) | `phase3_build_prompts.build(unit, with_siblings=...)` 의 반환 문자열 길이 | 빌더가 결정론적이므로 사후에도 편향 없이 복원 가능 (`P4` §3) | **기각** (§3.4) |
| A6 | 토큰 수 / 콜 수 | — | **기록되지 않음.** `P4` §3 이 이미 영구 제외 선언 | **기각 (측정 불가)** |
| A7 | 탐색 비용 (eval_budget) | 탐색에 쓴 콜 수 | 러너가 세면 가능 | **기각 (목적 축 아님)** — 기록은 한다 (§3.5) |

### 3.3 채택 — 2축 확정

**[설계] 목적 벡터 = (recall ↑, precision ↑). 2축. 이것으로 확정한다.**

축 정의를 실행 가능한 수준으로 못 박는다. 아래는 `instrument_check_score.py` 에 이미
구현된 정의와 **글자 단위로 동일**하다 — 새 정의를 만들지 않는다는 것이 요점이다. **[사실]**

```
PROBLEM = {"CONTRADICTED", "INSUFFICIENT"}                  # instrument_check_score.py L15
maj[i]  = 3판 중 2표 이상 일치 라벨, 아니면 "SPLIT"          # 같은 파일 main()
prob_ids = [i for i in units if human(i) in ("C","I")]
detected = [i for i in prob_ids if maj[i] in PROBLEM]
flagged  = [i for i in units    if maj[i] in PROBLEM]

recall    = len(detected) / len(prob_ids)
precision = len(detected) / len(flagged)
```

**왜 이 두 축인가 — 사용자가 말한 "조화"의 정확한 소재지.**

**[사실]** recall 과 precision 이 상충한다는 것은 우리 데이터에서 이미 실측됐다.
`SIDECHECK_RESULT.md` 기준 수치(README 표 재확인): SciFact(en) 은 recall 100% 인데
오탐 36.4% / 정밀도 64.7%, KLUE-NLI(ko) 은 recall 100% 인데 오탐 3.0% / 정밀도 95.7%.
**회수율은 언어에 둔감하고 정밀도는 민감했다.** 즉 축 하나로는 두 방을 구별조차 못 한다 —
둘 다 recall 100% 로 동률이다.

**[사실]** 그리고 `IC` §4 는 recall 만 게이트에 쓰고 precision 은 "보고만" 하도록 사전
선언했다. 근거: "Phase 3에서 확인된 실패 모드는 과검출이 아니라 **무검출**이다."
이는 **계기 검침 게이트**로서는 옳다(§8). 그러나 **후보 채택 게이트**로 쓰면 곧바로
Goodhart 다 — recall 만 보면 "전부 CONTRADICTED 라고 답하는 판정기" 가 recall 100% 로
1위가 된다. `skill` §"레버는 상호작용한다" 3번이 같은 구조를 경고한다: "후보를 넓히는
레버는 랭킹을 악화시키는 방향으로 결합된다(회수↑ ⇒ 경쟁↑ ⇒ 정밀도↓)."

**[설계]** 그래서 축을 (recall, precision) 으로 둔다. 이 두 축은:
- 둘 다 **최대화**이고 방향이 명확하다 (부등호 혼동 여지 없음).
- 둘 다 **동일한 사람 라벨 55건**에서 나오므로 데이터 출처가 하나다.
- 둘 다 이미 구현된 함수가 계산한다 — 새 계측기를 만들 필요가 없다. **계측기를 새로
  만들면 그 계측기부터 검침해야 한다**(§8).
- 그리고 **서로 밀당한다** — 이것이 front 가 자명하지 않기 위한 필요조건이다.

### 3.4 기각 사유 — 실행 가능한 결정으로 명시

**A3 (3판 일치율) 기각.** **[설계]** 축이 아니라 **노이즈 파라미터**다. 축으로 올리면
"항상 SUPPORTED 를 내는 판정기"가 일치율 100% 로 front 에 들어온다 — 안정성은 성능과
독립적으로 최대화하면 병리가 되는 지표다. 대신 §4.3 의 부트스트랩 CI 와 SPLIT 처리
규칙으로 흡수한다. `instrument_check_score.py` 는 이미 SPLIT 을 "문제 판정으로 세지
않음" 으로 처리한다 **[사실]** — 이 규약을 그대로 승계하되, SPLIT 건수는 §5 스키마의
`n_split` 필드에 **기록하고 게이트에는 쓰지 않는다.**

**A4 (`elapsed`) 기각.** **[사실]** `PHASE3_VERDICT.md` §7 실측: 조건 A/B 의 `elapsed`
중앙값이 **4.60s / 4.60s 로 동일**하다. `P4` §7 이 사전 선언한 동률 임계 ±20% 이내이므로
이 축은 **판정에 기여하지 않는다.** 기여하지 않는 축을 front 에 올리면 §3.6 의 차원의
저주만 악화시킨다. **[설계]** 게이트에서 제외하고 §5 스키마에 참고 필드로만 남긴다.

**A5 (프롬프트 문자수) 기각.** **[설계]** 이 축은 우리 탐색 공간에서 **성능축과 거의
완전 상관**일 위험이 크다. 근거: Phase 3 의 유일한 변인이 형제 블록 삽입이었고, 그것이
곧 문자수 증가였다(`phase3_build_prompts._sibling_block`). 즉 "문자수" 는 독립된 비용이
아니라 **변이 그 자체의 대리변수**가 된다. 상관된 축을 두 개 세면 front 가 인공적으로
넓어진다. 참고 필드로만 기록한다.

**A6 (토큰) 기각.** **[사실]** `P4` §3: "토큰 카운트는 기록되지 않으므로 **토큰을 비용축으로
쓰지 않는다** — 없는 데이터를 사후에 만들어 붙이지 않는다." 이 결정을 승계한다.

**A7 (탐색 비용) 목적 축이 아님.** **[사실]** `P4` §5.4: "`eval_budget`(탐색에 쓴 콜 수)은
**산출 하네스의 운영 비용이 아니다.**" 그리고 `src4` §4-2 관찰이 같은 혼동을 지적한다 —
Meta-Harness 가 최적화하는 cost 는 산출 harness 의 추론 시점 Ctx 이고, iteration 당
10.0 MTok 이라는 **탐색 자체의 비용은 목적이 아니다.** **[설계]** 탐색 비용은 §5 스키마의
`search_cost_calls` 에 기록하고 §6.4 의 종료 조건에만 쓴다.

### 3.5 참고 필드 (기록하되 판정에 쓰지 않음)

**[설계]** 다음은 축이 아니지만 후보마다 기록한다. 이유: 나중에 축으로 승격하려면
**데이터가 이미 있어야** 한다(A6 이 승격 불가능한 이유가 바로 데이터 부재). 기록은
싸고, 사후 생성은 불가능하다.

`n_split`, `elapsed_median`, `prompt_chars_median`, `search_cost_calls`.

**승격 금지 규칙**: 이 필드들을 **본 실행 중에 축으로 승격하지 않는다.** 승격은 별도
사전 선언 문서를 새로 커밋한 뒤 다음 실행에서만 가능하다 (§10).

### 3.6 🔴 축 개수의 위험 — 많으면 front 가 전부 비지배가 된다

**[설계]** 축을 `d` 개 두면, 무작위 두 후보가 서로 비지배일 확률이 `d` 와 함께 급격히
올라간다. 극단적으로 모든 후보가 서로 비지배면 front = 전체 아카이브이고, 그때
"front 에서 부모를 고른다"(§6)는 "아무 데서나 고른다"와 같아진다. **front 가 정보를
0으로 잃는다.**

정량 근거를 우리 데이터에서 든다. **[사실]** `src4` Table 9 (`src4` §5-4 재수록):
2축에서 40개 후보 중 front 가 8개였다. **[설계]** 2축이라 8개로 좁혀진 것이고, 여기에
지연·문자수·일치율을 얹어 5축으로 만들면 40개 대부분이 서로 비지배가 될 것으로
예상한다 — 이 예상은 검증하지 않으며, 검증하지 않기 위해 **애초에 2축으로 고정한다.**

**[설계] 확정: 축은 2개. 3개를 넘기지 않는다.** 3축으로 늘릴 수 있는 유일한 조건은
"기존 2축이 동률인 후보 쌍이 front 의 절반을 넘을 때" 이며, 그 경우에도 §10 의 순서를
따라 새 사전 선언을 커밋한 뒤 **다음 실행**에서만 늘린다.

---

## 4. 🔴 dominance 판정식

**[사실]** Meta-Harness 는 이것을 쓰지 않았다: "we evaluate candidates under Pareto
dominance" 라는 문장뿐이고 부등호 방향·weak/strong·타이 브레이크·노이즈 처리가 전부
미기재다(`src4` §5-4). 우리는 쓴다.

### 4.1 기본 정의

**[설계]** 후보 `x` 의 목적 벡터를 `f(x) = (r(x), p(x))` 로 둔다. `r` = recall,
`p` = precision, 둘 다 최대화.

**강한 지배 (strict dominance)** — `x ≻ y` 는 다음을 만족할 때:

```
r(x) ≥ r(y)  ∧  p(x) ≥ p(y)  ∧  ( r(x) > r(y)  ∨  p(x) > p(y) )
```

이는 `skill` §개념3 의 정의와 동일하다 **[사실]**: "후보 B가 baseline A를 지배한다 =
B가 두 지표 다 A 이상이고 최소 하나는 초과."

**비지배 (non-dominated)**: 아카이브 `D` 안에서 `x` 를 지배하는 후보가 하나도 없을 때.
**front(D) = { x ∈ D : ¬∃ y ∈ D, y ≻ x }`.**

**[설계]** Self-Harness 의 수락규칙과의 관계를 명시한다. 그쪽은 `(P_in, P_ho)` 두 축을
**현재 활성 harness 대비** 비교하는 진입 게이트이고(`src1` §3.4), 우리 식은 **아카이브
전체에 대한** 비지배 집합이다. `src4` §11-2 의 표현을 빌리면 Self-Harness 는 비지배를
써서 가능한 변화를 좁히고 Meta-Harness 는 가능한 결과를 넓힌다 — **우리는 둘 다 한다**:
§5.2 의 추가 규칙이 진입 게이트 역할을, front 자체가 결과 노출 역할을 한다.

### 4.2 동률 처리

**[설계]** 세 경우로 나누고 각각 결정한다.

1. **완전 동률** `r(x) = r(y) ∧ p(x) = p(y)`: 서로 지배하지 않는다(위 식의 셋째 절이
   거짓). **둘 다 front 에 남는다.** 단 §5.4 의 크기 상한 처리에서 **표본이 큰 쪽,
   같으면 부모 세대가 이른 쪽(먼저 발견된 쪽)을 남긴다.** 사유: 늦게 온 동률 후보는
   새 정보가 없으므로 아카이브만 부풀린다.
2. **한 축 동률 + 한 축 우세**: 위 식에 의해 **지배한다.** 예: `r` 동률, `p(x) > p(y)`
   → `x ≻ y`. 이는 `PHASE1_VERDICT.md` §2 시도1의 판정과 정확히 같은 형태다 **[사실]**
   — 프로브 3표가 1표를 회수율 90.0% 동률 + 검토율 38.9%→35.2% 개선으로 지배했다.
3. **한 축 우세 + 다른 축 열세**: 지배 아님. **front 에 병존하고 `트레이드오프` 로
   라벨한다.** `P4` §4 의 게이트 P 정의와 같다 **[사실]**: "지배하지 못하면 `트레이드오프`로
   라벨해 보류."

**[설계] 스칼라화 금지.** F1·가중합·hypervolume·chebyshev 로 동률을 깨지 않는다.
근거는 세 겹이다: `skill` §함정("사후 목표 선택 = Goodhart"), `P4` §3("가중치를 정하는
순간 그것이 사후 선택의 통로가 된다"), 그리고 두 논문의 명시적 거부(§1.1 인용 2개).
**F1 은 보고 표에 병기해도 되지만 판정 입력이 아니다.**

### 4.3 🔴 노이즈 처리 — 이 절이 가장 중요하다

**[사실]** 문제는 실재한다. `PHASE1_VERDICT.md` §4: "회수율 1건의 무게 = 문제 10건 →
1건 = 10%p." 55건 표본에서 문제건이 11건이면(`IC` 실측: 11건) **recall 의 최소 눈금이
1/11 = 9.1%p** 다. 그보다 작은 차이는 존재할 수 없고, 1건 차이는 라벨 1건의 흔들림으로
발생할 수 있다.

**[사실]** 그리고 판정기 자체가 비결정적이다. `PHASE1_VERDICT.md` §8: 저지 v3 는 3판에서
5건이 흔들렸다. `IC` 결과는 SPLIT 0건이었지만, **0이 항상 0이라는 보장은 없다** —
`skill` §1단계: "LLM 판정이 끼면 비결정적 → 케이스당 N회(3회+) 다수결로 재는 자를 정밀화.
단일 실행 ±몇%p는 노이즈."

**[설계] 규칙 N1 — 부트스트랩 95% CI 를 축마다 계산한다.**

절차를 실행 가능한 수준으로 고정한다.

```
입력: units = 3판 다수결이 확정된 라벨 단위 리스트 (id, human, maj_label)
B = 2000                      # 부트스트랩 반복
seed = 20260730               # 고정. 실행마다 바꾸지 않는다
for b in 1..B:
    S_b = units 에서 복원추출 n=len(units)   # 단위(=claim) 수준 리샘플
    r_b = recall(S_b);  p_b = precision(S_b)
CI_r = (percentile(r_*, 2.5), percentile(r_*, 97.5))
CI_p = (percentile(p_*, 2.5), percentile(p_*, 97.5))
```

**[설계]** 리샘플 단위는 **claim** 으로 한다. 문항(qid) 단위 클러스터 부트스트랩이
통계적으로 더 옳다 — `PHASE1_VERDICT.md` §4 와 `phase3_power_check.py` 가 둘 다
군집화를 경고하고, 후자는 "독립 단위는 주장이 아니라 문항이다" 라고 명시한다 **[사실]**.
그런데 55건이 몇 문항에 분포하는지에 따라 문항 단위 부트스트랩은 CI 를 크게 넓혀
**모든 후보를 비지배로 만들** 위험이 있다. **결정: 두 CI 를 모두 계산해 스키마에 기록하고,
지배 판정에는 보수적인 쪽(넓은 쪽) = 문항 클러스터 CI 를 쓴다.** 보수적인 쪽을 쓰면
"우연한 개선을 채택" 하는 오류를 막고, 대신 "실제 개선을 놓치는" 오류가 늘어난다.
후자가 싸다 — 놓친 개선은 다음 라운드에 다시 제안될 수 있지만, 잘못 채택한 열등 이동은
아카이브를 오염시킨다.

**[설계] 규칙 N2 — CI 가 겹치면 그 축은 동률로 본다.**

축 `k` 에서 두 후보의 95% CI 가 겹치면 `f_k(x) = f_k(y)` 로 **간주**한다. 즉:

```
def cmp_axis(x, y, k):          # 반환: +1 (x 우세) / 0 (동률) / -1 (y 우세)
    lo_x, hi_x = CI_k(x);  lo_y, hi_y = CI_k(y)
    if lo_x > hi_y: return +1
    if lo_y > hi_x: return -1
    return 0                     # 겹침 -> 동률

def dominates(x, y):
    c = [cmp_axis(x, y, k) for k in AXES]
    return all(v >= 0 for v in c) and any(v > 0 for v in c)
```

**[사실]** 이 "구간 비겹침" 판정은 우리 프로젝트가 이미 쓰는 방식이다.
`PHASE1_VERDICT.md` §4 가 Wilson 구간 겹침으로 90% vs 70% 를 구별 불가로 판정했고,
`PHASE3_VERDICT.md` §1 의 조건 ③④ 도 Wilson 비겹침 기준이며, `P4` §4.1 조건 4 도
"Wilson 95% 구간이 비겹침" 이다. **새 기준을 도입하는 게 아니라 기존 기준을 dominance
연산자 안으로 옮기는 것이다.**

**[설계]** Wilson 이 아니라 부트스트랩을 쓰는 이유: Wilson 은 단일 비율의 CI 이고,
precision 의 분모(`flagged`)는 **후보에 따라 변한다.** 즉 recall 과 precision 이 같은
리샘플에서 함께 움직이는 구조를 Wilson 으로는 표현할 수 없다. 부트스트랩은 두 축을
같은 리샘플에서 동시에 계산하므로 이 상관을 자연히 반영한다. 사용자가 지적한
`pareto-optimization-gate` 및 week2 MT5 작업의 부트스트랩 95% CI 전례를 이 설계의
방법론적 근거로 승계한다 — **[미확인]**: 그 두 전례의 구현 파일 경로는 이 세션에서
직접 확인하지 못했으므로 경로를 인용하지 않는다.

**[설계] 규칙 N3 — 겹침 동률이 만드는 부작용을 명시한다.**

N2 를 넣으면 "모든 축이 동률" 인 후보 쌍이 늘어난다. 그 결과 §3.6 의 차원 저주가
2축에서도 재현될 수 있다. **대응**: front 크기 상한(§5.4)과 종료 조건(§6.4)이 이 부작용을
흡수한다. 그리고 front 의 절반 이상이 "전 축 겹침 동률" 이면 그것은 **표본이 작다는
신호**이므로, 축을 늘리지 말고 **라벨을 늘릴지 판단**한다 — 늘릴 수 없으면
`PHASE2_VERDICT.md` 처럼 판정 불가로 종결한다.

### 4.4 최소 표본 요건 — 이 아래면 판정 자체를 거부한다

**[설계]** 판정 거부 조건. 하나라도 위반하면 그 후보는 front 진입 판정을 받지 못하고
`UNJUDGED` 로 아카이브에 들어간다(§5.2).

| 요건 | 임계 | 근거 |
|---|---|---|
| R1. 사람 라벨 문제건 수 `len(prob_ids)` | **≥ 8** | 11건이 현재 실측값(`IC`). 8 미만이면 recall 눈금이 12.5%p 를 넘어 CI 가 사실상 [0,1] 이 된다 |
| R2. 판정기 문제판정 수 `len(flagged)` | **≥ 5** | precision 분모. 0 이면 precision 이 정의되지 않는다. `instrument_check_score.py` 는 이 경우 0.0 을 반환하는데, 그 0.0 을 "정밀도 0%" 로 읽으면 오판이다 **[사실]** |
| R3. 판정 실행 판수 | **정확히 3판** | `P4` §5.3 "모든 채점 3판 다수결". 2판이면 다수결이 정의되지 않고, 4판 이상은 다른 후보와 비교 불가 |
| R4. UNRESOLVED 비율 | **< 10%** | fail-closed 규약(`P4` §5.3). UNRESOLVED 가 많으면 recall/precision 이 "판정기가 답을 못 한 것" 과 "문제 없다고 답한 것" 을 뒤섞는다 |
| R5. SPLIT 비율 | **< 20%** | SPLIT 은 문제 판정으로 세지 않으므로(§3.4), 많으면 recall 이 구조적으로 깎인다. 20% 이상이면 후보가 아니라 **측정이 고장난 것**으로 취급하고 §8 로 되돌린다 |

**[설계]** R1~R5 는 **결과를 보기 전에 이 문서에 박혀 있다.** 임계를 결과에 맞춰
조정하는 것을 §10 이 금지한다.

**[설계]** 그리고 전체 실행 자체를 거부하는 조건이 하나 더 있다 — `IC` §4 의 recall ≥ 30%
게이트다. 이것은 후보별 요건이 아니라 **실행 전 요건**이므로 §8 에서 다룬다.

---

## 5. 🔴 front 아카이브 설계

**[사실]** Meta-Harness 의 아카이브는 파일시스템 `D` 이고 갱신 연산은 합집합
`D ← D ∪ {(H, E_H)}` 하나뿐이며 **append-only** 다. 제거·pruning·eviction·크기제한
서술이 원문에 없다(`src4` §5-2·5-3·5-5). front 를 담는 별도 자료구조도 없고, front 는
종료 시점에 `D` 위의 질의로 산출된다(`src4` Algorithm 1 line 13). **우리는 front 를
상태로 유지하고 제거 규칙을 둔다.**

### 5.1 자료구조 — JSON 스키마

**[설계]** 파일 2개로 나눈다. 근거: `src3` 주장 5 **[사실]** — "A harness should not
carry the entire workflow and all logs in context; instead, it should keep durable state
in files." 그리고 우리 레포의 기존 관행과 일치한다(`*_run{1,2,3}.jsonl` 원자료 +
`*_result.json` 판정).

**파일 A — `gate/scripts/mh_archive.jsonl`** (append-only 원장. 한 줄 = 후보 1개)

```json
{
  "candidate_id": "c007",
  "created_at": "2026-07-31T09:12:04+09:00",
  "parent_ids": ["c003", "c005"],
  "generation": 3,
  "origin": "front_pair",
  "origin_reason": "c003(고recall 끝점)과 c005(고precision 끝점)가 공통으로 Q068 계열에서 갈림 — 두 끝점이 동시에 실패하는 축을 지목",
  "harness": {
    "builder_module": "phase3_build_prompts",
    "builder_fn": "build",
    "builder_kwargs": {"with_siblings": true},
    "prompt_sha256": "3f9a…",
    "model": "claude-sonnet-4-6",
    "diff_from_parent": "JUDGE 지시문에 '규칙의 왜곡 → CONTRADICTED' 1문장 추가",
    "edited_surface": ["JUDGE"]
  },
  "measurement": {
    "label_sheet_sha256": "a1b2…",
    "n_units": 55,
    "n_runs": 3,
    "n_problem": 11,
    "n_flagged": 13,
    "n_detected": 9,
    "n_split": 0,
    "n_unresolved": 0,
    "raw_files": ["mh_c007_run1.jsonl", "mh_c007_run2.jsonl", "mh_c007_run3.jsonl"]
  },
  "objectives": {
    "recall":    {"value": 0.8182, "ci_claim": [0.5455, 1.0], "ci_qid": [0.4545, 1.0]},
    "precision": {"value": 0.6923, "ci_claim": [0.4615, 0.9231], "ci_qid": [0.3846, 0.9231]}
  },
  "reference_fields": {
    "elapsed_median": 4.6,
    "prompt_chars_median": 3184,
    "search_cost_calls": 165
  },
  "sample_gate": {"passed": true, "violations": []},
  "status": "ON_FRONT",
  "status_history": [
    {"at": "2026-07-31T09:40:11+09:00", "status": "ON_FRONT", "by": "c007 진입"}
  ]
}
```

**필드 타입 명세** **[설계]**

| 필드 | 타입 | 설명 |
|---|---|---|
| `candidate_id` | `str` | `c%03d`. 불변. baseline 은 `c000` |
| `created_at` | `str` (ISO8601 + offset) | 생성 시각 |
| `parent_ids` | `list[str]` | 부모 후보 id. **길이 0 = baseline, 1 = 단일 부모, 2 = front 쌍 참조(§6.2)** |
| `generation` | `int` | 라운드 번호. baseline = 0 |
| `origin` | `str` enum | `baseline` / `front_endpoint` / `front_pair` / `filter_strip`(§6.5) |
| `origin_reason` | `str` | 자연어 1~3문장. **왜 이 부모에서 출발했는가.** 비워두면 안 된다 |
| `harness.builder_module` / `builder_fn` | `str` | 실제 import 경로. 추측 금지 |
| `harness.builder_kwargs` | `dict` | 빌더 인자 |
| `harness.prompt_sha256` | `str` | 고정 unit 하나에 빌더를 적용한 프롬프트의 해시. **동일 harness 재측정 방지** |
| `harness.model` | `str` | alias 금지 (`P4` §5.3) |
| `harness.diff_from_parent` | `str` | 부모 대비 변경 1건 서술 |
| `harness.edited_surface` | `list[str]` | 수정한 상수/함수 이름 |
| `measurement.label_sheet_sha256` | `str` | **라벨 시트 불변성 증거.** 값이 바뀌면 전 후보 비교 무효 |
| `measurement.n_*` | `int` | §3.3 정의의 카운트 |
| `measurement.raw_files` | `list[str]` | jsonl 원자료 파일명 |
| `objectives.<axis>.value` | `float` | 점 추정 |
| `objectives.<axis>.ci_claim` / `ci_qid` | `[float, float]` | §4.3 두 CI. 판정은 `ci_qid` 사용 |
| `reference_fields` | `dict` | §3.5. 판정 미사용 |
| `sample_gate.passed` | `bool` | §4.4 R1~R5 전부 통과 여부 |
| `sample_gate.violations` | `list[str]` | 위반 요건 코드 (`["R2","R5"]` 등) |
| `status` | `str` enum | `ON_FRONT` / `DOMINATED` / `PRUNED` / `UNJUDGED` / `INVALID` |
| `status_history` | `list[dict]` | 상태 전이 이력. **덮어쓰지 않고 append** |

**파일 B — `gate/scripts/mh_front.json`** (파생 상태. 매 라운드 재계산)

```json
{
  "computed_at": "2026-07-31T09:40:11+09:00",
  "archive_sha256": "9c1d…",
  "axes": ["recall", "precision"],
  "ci_used": "ci_qid",
  "front": ["c000", "c003", "c005", "c007"],
  "endpoints": {"recall": "c003", "precision": "c005"},
  "dominated": [{"id": "c001", "dominated_by": ["c003"]}],
  "pruned": [{"id": "c004", "rule": "크기상한 초과 — crowding 최소", "at": "…"}],
  "unjudged": [{"id": "c006", "violations": ["R2"]}],
  "front_size": 4,
  "front_changed": true,
  "stall_rounds": 0
}
```

**[설계]** `mh_front.json` 은 **언제든 `mh_archive.jsonl` 에서 재생성 가능**해야 한다.
`archive_sha256` 이 그 검증 수단이다. 즉 front 는 권위 있는 상태가 아니라 **캐시된
파생값**이다 — 이 점은 `src4` §5-1 의 해석("front 는 유지·갱신되는 상태가 아니라 종료
시점에 `D` 에서 계산되는 파생값에 가깝다")과 같다 **[사실]**. 우리가 다른 것은 그 파생값을
**매 라운드 계산해 탐색 입력으로 쓴다**는 점이다(§6).

### 5.2 후보 추가 규칙

**[사실]** Meta-Harness 의 유일한 관문은 인터페이스 검증이다(`src4` Algorithm 1 line 11).
성능 기반 수락 게이트가 없다. 회귀한 후보도 그대로 `D` 에 들어가고, 실제로 그것이
자산으로 쓰인다(`src4` §5-2, Appendix A.2).

**[설계]** 우리도 **아카이브 진입은 막지 않는다.** 근거: `src3` Future Challenges 3번
**[사실]** — "A research harness should make failed attempts easy to preserve, as learning
from failure is the best way to trim down the task search space." 그리고 `src4` Table 3
ablation 이 raw trace 접근이 핵심 재료임을 실증했다(`src4` §8-1).

추가 규칙 3단계 **[설계]**:

1. **유효성 검증 (INVALID 차단)** — Meta-Harness 의 인터페이스 검증에 대응.
   - 빌더가 import 되고 `build()` 가 문자열을 반환하는가
   - `prompt_sha256` 가 아카이브의 기존 후보와 **중복되지 않는가** (중복이면 측정하지
     않고 기존 후보를 참조. 같은 harness 를 두 번 재는 것은 표본 낭비다)
   - `harness.model` 이 `claude-sonnet-4-6` 인가 (alias 금지)
   - 실패 → `status = "INVALID"`, 측정 안 함, 콜 0
2. **측정 (3판 실행)** — 통과분만 165콜(55×3) 을 태운다.
3. **표본 요건 검증 (§4.4 R1~R5)** — 실패 → `status = "UNJUDGED"`.
   **아카이브에 남고, front 판정에서만 제외된다.** 지배도 피지배도 하지 않는다.

**[설계] 진입 게이트를 하나 둔다 — Self-Harness 규칙의 이식.**
`src1` §3.4 의 수락규칙은 **활성 harness 대비 비악화**를 요구한다 **[사실]**. 우리는
활성 harness 가 없고 front 가 있으므로 다음으로 번역한다:

> **G1 (열등 이동 차단)**: 후보 `x` 가 **baseline `c000` 에게 지배당하면**(`c000 ≻ x`),
> `status = "DOMINATED"` 로 기록하되 **§6 의 부모 후보에서 영구 제외**한다.

사유는 `skill` §"모서리점에서는 레이어 추가가 곧 열등 이동" 이다 **[사실]** — baseline 을
지배당하는 지점에서 다시 출발하면 열등 방향 탐색이 누적된다. 단 **아카이브에는 남는다**
— §6.2 가 실패 쌍 비교에 쓴다.

### 5.3 🔴 후보 제거 규칙 — Meta-Harness 에 없던 것

**[설계]** 제거를 두 종류로 구분한다. 이 구분이 없으면 "제거" 가 곧 증거 인멸이 된다.

**제거 A — 논리적 제거 (`status` 전이).** 원장에서 **행을 지우지 않는다.**
`status` 를 `DOMINATED` / `PRUNED` 로 바꾸고 `status_history` 에 append 한다.
front 계산에서만 빠진다. **원자료 jsonl 은 절대 삭제하지 않는다.**

**제거 B — 물리적 제거.** **금지한다.** 예외 없음. 근거: `src3` Future Challenges 3번
(실패 보존)과 우리 레포의 감사 가능성 원칙. 디스크가 문제라면 압축하되 지우지 않는다.

**전이 규칙** **[설계]**

| 전이 | 조건 | 되돌릴 수 있나 |
|---|---|---|
| `→ ON_FRONT` | 아카이브 내 어떤 후보에게도 지배당하지 않고 `sample_gate.passed = true` | 예 — 새 후보가 지배하면 `DOMINATED` 로 |
| `→ DOMINATED` | 어떤 후보에게 지배당함 | 예 — 지배자가 나중에 `INVALID` 판정되면 재계산으로 복귀 가능 |
| `→ PRUNED` | front 크기 상한 초과 시 §5.4 규칙으로 솎아짐 | **아니오** — 한 번 PRUNED 면 부모 후보에서 영구 제외 |
| `→ UNJUDGED` | §4.4 요건 위반 | 예 — 표본을 늘려 재측정하면 |
| `→ INVALID` | §5.2 1단계 실패 | 아니오 |

**[설계] `DOMINATED` 후보를 부모로 쓸 수 있는가?** 원칙적으로 쓸 수 있다 — 단 §6.1 의
우선순위에서 **front 후보보다 뒤**이고, `origin_reason` 에 왜 지배당한 후보에서
출발하는지를 적어야 한다. 예외: G1 에 걸린 후보(baseline 에게 지배당한 것)는 영구 제외.

### 5.4 front 크기 상한과 솎아내기 기준

**[사실]** Meta-Harness 는 크기 제한 서술이 없고, §4.1 런에서 40 후보 → front 8개가
나왔다. 그것이 상한의 결과인지 자연 발생인지는 **[미확인]** (`src4` §5-5).

**[설계] 상한 = 8.** 근거 두 가지:
- `src4` §4.1 이 2축 40후보에서 8개를 냈다 **[사실]** — 같은 축 개수에서의 유일한 실측 참조점.
- §6.2 의 부모 선택 규칙이 **front 의 서로 다른 끝점 2개**를 참조한다. front 가 8개를
  넘으면 "끝점" 의 의미가 흐려지고, 사람(운영자)이 한눈에 검토할 수 없다.

**[설계] crowding distance 를 쓸지 — 판정: 쓰지 않는다.**

NSGA-II 계열의 crowding distance 는 목적 공간에서 이웃 간 거리를 재서 밀집 구간을
솎아낸다. 우리 맥락에서 기각하는 이유:

1. **눈금이 굵어서 거리가 의미를 잃는다.** §4.3 에서 확인했듯 recall 의 최소 눈금은
   1/11 = 9.1%p 다. 8개 이하의 front 점들이 이 굵은 격자 위에 놓이므로 "밀집" 이라는
   개념 자체가 성립하지 않는다.
2. **CI 동률 규칙(N2)과 이중 계산이 된다.** N2 가 이미 "가까운 점을 동률로 묶는" 역할을
   한다. 거기에 거리 기반 솎아내기를 얹으면 같은 근접성을 두 번 벌하게 된다.

**[설계] 대신 쓸 규칙 — 3단 사전식(lexicographic) 솎아내기.**
front 크기가 8을 넘으면 다음 순서로 `PRUNED` 를 정한다. 각 단계는 결정론적이고
tie 가 남으면 다음 단계로 내려간다.

```
1) 끝점 보호: endpoints(recall 최대, precision 최대) 는 절대 PRUNED 되지 않는다.
   최대가 여럿이면 반대 축이 큰 쪽을 끝점으로 삼는다.
2) 두 축 CI 가 모두 다른 front 후보와 겹치는 후보를 먼저 후보군에 넣는다
   (= 구별되지 않는 점). 그 안에서 표본 요건 여유가 적은 순(n_flagged 작은 순)으로 PRUNED.
3) 그래도 8을 넘으면 generation 이 큰 쪽(늦게 온 쪽)을 PRUNED.
```

**[설계]** 2)의 사유: 구별되지 않는 점은 **정보를 더하지 않으면서 부모 선택 확률만
분산시킨다.** 3)의 사유: §4.2 동률 규칙과 방향을 맞춘다(늦게 온 동률은 새 정보 없음).

**[설계] 상한을 넘겨도 `PRUNED` 하지 않는 예외 1개**: front 전체가 8을 넘고 **그중
`origin = "filter_strip"`(§6.5) 후보가 절반 이상**이면, PRUNED 하지 말고 **탐색을
정지하고 §4.3 N3 로 간다** — 그것은 후보가 많다는 신호가 아니라 표본이 작다는 신호다.

### 5.5 각 후보에 무엇을 저장하는가 (요구사항 대조)

**[설계]** 지시된 6개 항목이 §5.1 스키마의 어디에 있는지 못 박는다.

| 요구 항목 | 스키마 필드 |
|---|---|
| harness 구성 | `harness` 전체 (`builder_module`/`builder_fn`/`builder_kwargs`/`prompt_sha256`/`model`/`edited_surface`) |
| 축별 점수 | `objectives.<axis>.value` |
| CI | `objectives.<axis>.ci_claim`, `.ci_qid` |
| 표본 크기 | `measurement.n_units`, `n_problem`, `n_flagged`, `n_runs` (+ `sample_gate`) |
| 부모 ID | `parent_ids` (+ `generation`) |
| 생성 이유 | `origin`, `origin_reason`, `harness.diff_from_parent` |

**[설계]** 추가로 저장하는 것 2개와 그 이유:
- `measurement.label_sheet_sha256` — **라벨 시트가 실험 중 바뀌지 않았다는 증거.**
  `IC` §3 이 "라벨 55건은 정답지이며 이 검침으로 재라벨·수정하지 않는다" 고 선언했고,
  이 해시가 그 선언의 기계 검증이다 **[사실]**.
- `harness.prompt_sha256` — 같은 harness 를 두 번 측정하는 낭비 차단(§5.2).

---

## 6. 🔴 front 를 탐색에 쓰는 규칙 — 우리 기여의 핵심

**[사실]** Meta-Harness 는 부모 선택 규칙이 없다:

> "Meta-Harness maintains a population H and a Pareto frontier over evaluated harnesses, but **imposes no parent-selection rule**: the proposer is free to inspect any prior harness and its execution trace when proposing new ones. … This simplicity is deliberate: by leaving diagnosis and edit decisions to the proposer rather than hard-coding search heuristics, Meta-Harness can improve automatically as coding agents become more capable." (`src4` §3, 인용 2)

**[사실]** 그리고 좋은 조상에서 출발하는 것은 **창발**이라고 명시한다:
> "In practice, it often starts from a strong prior harness, but this is an emergent strategy rather than a hard-coded rule." (`src4` §3, 인용 10)

**[설계]** 우리는 규칙을 둔다. 규칙을 두는 이유는 "코딩 에이전트를 못 믿어서" 가 아니라
**사전등록 가능성** 때문이다. 부모 선택이 에이전트 재량이면 그 선택은 결과를 본 뒤에
설명되고, 그것이 곧 사후 선택이다(§10). 규칙이 있으면 부모 선택을 실행 전에 예측할 수
있고, 예측 가능한 절차만 사전등록될 수 있다.

### 6.1 부모 선택 — 어느 지점에서 출발하는가

**[설계]** 매 라운드 **정확히 3개 후보를 생성**한다. 세 개의 출발점이 규칙으로 고정된다.

| 슬롯 | 출발점 | `origin` | 목적 |
|---|---|---|---|
| **S1** | `endpoints["recall"]` — recall 최대 끝점 | `front_endpoint` | 회수율 끝을 유지하며 정밀도를 얻으려는 시도 |
| **S2** | `endpoints["precision"]` — precision 최대 끝점 | `front_endpoint` | 정밀도 끝을 유지하며 회수율을 얻으려는 시도 |
| **S3** | **끝점 2개를 동시에 참조** (§6.2) | `front_pair` | 두 끝점이 **공통으로** 실패하는 축을 지목 |

**[설계] 결정론적 선택.** 확률적 부모 샘플링(GEPA·ShinkaEvolve 계열)을 쓰지 않는다.
사유: 우리 front 는 최대 8개이고 라운드 수도 작다(§6.4). 이 규모에서 확률 샘플링은
재현 불가능성만 추가한다. `skill` §1단계의 "측정 노이즈 제거" 정신과 같다 — **탐색
자체의 분산도 줄인다.**

**[설계] 동률 처리.** 끝점이 여럿이면 §5.4 1) 규칙(반대 축이 큰 쪽)으로 유일하게 정한다.
S1 과 S2 의 끝점이 **같은 후보**이면(즉 한 후보가 두 축 모두 최대) 그 후보는
아카이브 전체를 지배하므로 front 크기가 1이다. 이때는 **S2 를 §6.5 의 filter_strip
슬롯으로 대체**한다 — 붙일 곳이 없으면 걷어낸다.

### 6.2 🔴 front 의 서로 다른 끝점 2개를 동시에 참조하는 절차

**[사실]** 근거는 Meta-Harness Appendix A.2 의 실물 기록이다. TB2 런에서 초반 6
iteration 이 연속 회귀했고, iteration 3 이 **회귀한 후보 1·2 를 동시에 참조해 공통
요인(prompt 개편)을 confound 로 특정**했다(`src4` §11-3 (1)). proposer 의 로그 원문:

> "All 6 prior iterations regressed from the 64.4% baseline because they modified the completion flow, prompt template, or observation processing. evo env bootstrap takes a different approach --- purely additive." (`src4` 인용 19)

**[사실]** 그리고 `src4` §11-3 (1) 이 결정적인 관찰을 덧붙인다: **"단일 활성 harness
체제에서는 이 추론이 원리적으로 불가능하다 — 비교할 실패 쌍이 계보에 남지 않기 때문이다."**
즉 이 추론 능력은 front 아카이브가 있어야 성립한다. 그런데 Meta-Harness 에서 그것은
창발이었다(인용 10). **[설계] 우리는 이것을 규칙으로 승격한다.**

**절차 S3 — 쌍 진단 (pair diagnosis)** **[설계]**

```
입력: A = endpoints["recall"], B = endpoints["precision"]   (A ≠ B)
      A, B 의 원자료 jsonl (각 3판) + 사람 라벨 시트

1) 단위별 판정표를 만든다.
   for each unit u:  (human(u), maj_A(u), maj_B(u))

2) 4분면으로 분류한다.
   - BOTH_OK   : A 와 B 가 모두 사람 라벨과 일치
   - A_ONLY    : A 만 일치        -> A 의 강점, B 의 약점
   - B_ONLY    : B 만 일치        -> B 의 강점, A 의 약점
   - BOTH_FAIL : 둘 다 불일치      🔴 이것이 S3 의 표적

3) BOTH_FAIL 을 문항(qid) 으로 묶고 크기순 정렬한다.
   claim 단위가 아니라 문항 단위로 묶는 이유: phase3_power_check.py 가 명시한
   "독립 단위는 주장이 아니라 문항이다" 를 따른다. [사실]

4) BOTH_FAIL 클러스터가 0개면 -> S3 슬롯을 §6.5 filter_strip 으로 대체하고 종료.
   1개 이상이면 최대 클러스터 1개만 표적으로 삼는다.

5) 그 클러스터에 대해 변이를 1개 만든다. 제약:
   - 수정 표면(edited_surface) 은 1개. A 와 B 의 diff 에 이미 등장한 표면은 금지.
     (두 끝점이 이미 그 축을 탐색했고 둘 다 실패했으므로)
   - origin_reason 에 (a) 클러스터의 문항 id, (b) A·B 가 각각 무엇이라 판정했는지,
     (c) 왜 그 공통 실패가 이 표면 수정으로 해결되리라 보는지를 적는다.
```

**[설계]** 5)의 "A 와 B 의 diff 에 이미 등장한 표면 금지" 가 이 절차의 칼날이다.
`src4` Appendix A.2 의 승리 후보가 정확히 이 형태였다 — 6번 연속 실패한
"completion flow / prompt template / observation processing" 을 **건드리지 않고**
purely additive 로 갔다 **[사실]**. 우리는 그 판단을 에이전트 재량에 맡기지 않고
**금지 목록으로 강제**한다.

**[설계] BOTH_FAIL 이 우리 데이터에 실제로 있는가?** `IC` §5 실측: 미검출 2건이
`Q068-A-c1`, `Q068-A-c2` 로 **둘 다 Q068** 이고, 저자 라벨 메모에 "애매" 로 적혀 있던
건이다 **[사실]**. 즉 문항 단위 공통 실패 클러스터가 최소 1개 존재한다. 다만 `IC` §5 는
같은 문항이 "이 코퍼스의 난이도 상한" 이라고도 적었다 — **[설계]** 따라서 S3 가 이
클러스터를 반복해서 표적으로 삼고 계속 실패하면, 그것은 탐색 실패가 아니라 **천장**이다.
`skill` §4("천장으로 인정하고 멈춘다")에 따라 §6.4 의 종료 조건이 이를 잡는다.

### 6.3 변이 강제 금지

**[사실]** `skill` §"하네스 자동탐색" 이 인용한 참조 구현의 지시:
> "You MUST produce 1 new agent variant every iteration. Do NOT write 'the frontier is optimal' or 'stop iterating', or abort early."

**[사실]** `skill` 은 이것이 자기 §4(천장 인정하고 멈춘다)와 **정면 충돌**한다고 판정하고
"흡수 금지" 로 분류했다. `P4` §5.1 도 같다: "`no-change`(baseline이 지배당하지 않음)는
**정당한 산출**이다."

**[설계] 승계한다.** 어떤 라운드에서든 다음이면 그 슬롯은 **비운다**:
- S1/S2: 끝점에서 만들 변이가 §6.2 5) 제약이나 §5.2 유효성 검증을 통과하지 못할 때
- S3: BOTH_FAIL 클러스터가 0개일 때 (→ §6.5 로 대체)

**세 슬롯이 모두 비면 그 라운드는 후보 0개이고, 그것이 종료 신호다**(§6.4 T3).

### 6.4 탐색 종료 조건

**[설계]** 넷 중 **하나라도** 충족하면 즉시 정지한다. 정지는 실패가 아니다.

| # | 조건 | 사유 |
|---|---|---|
| **T1** | front 가 **3라운드 연속 갱신되지 않음** (`front_changed = false` 3회, `mh_front.json.stall_rounds ≥ 3`) | `skill` §4: 한 레버가 한쪽을 올리며 다른 쪽을 같은 폭으로 떨어뜨리면 사정거리 밖 → 천장 인정 |
| **T2** | 누적 `search_cost_calls` 가 **1,650콜** 초과 | Phase 3 가 태운 액수(`PHASE3_VERDICT.md`)를 상한으로 못 박는다. 후보 1개 = 165콜이므로 **최대 10후보 ≈ 3~4라운드** |
| **T3** | 어느 라운드에서 유효 후보가 **0개** (§6.3) | 만들 변이가 없다 = 탐색 공간 소진 |
| **T4** | front 의 절반 이상이 **전 축 CI 겹침 동률** (§4.3 N3) 또는 `filter_strip` 후보(§5.4 예외) | 후보 문제가 아니라 표본 문제 → 축을 늘리지 말고 판정 불가로 종결 |

**[설계] T2 의 산술을 명시한다.** 후보 1개 = 55 units × 3 runs = **165콜**. 1,650 / 165
= **10 후보**. 라운드당 최대 3후보이므로 **최대 3라운드 + 1후보**. 이 예산이 작다는 것이
결함이 아니라 설계 의도다 — `IC` §3 이 계기 검침을 165콜로 설계한 것과 같은 논리로,
**진단 비용을 본 실행의 10분의 1로 유지**하는 것이 이 프로젝트의 규율이다.

**[설계]** 종료 시 산출물은 **front 전체**다. "최종 1개" 를 자동으로 고르지 않는다.
근거: `src4` §6 **[사실]** — Meta-Harness 는 front 에서 최종 1개를 고르는 자동 규칙이
없고, 실제로 보고된 대표 시스템은 **정확도 최대 끝점**이었다("the highest-accuracy
frontier point used in the main text", `src4` 인용 6). 즉 **다목적을 유지한 것은 front
보고이고, 대표 선정에서는 단일 축 극단으로 되돌아갔다**(`src4` §6). **[설계] 우리는 그
되돌아감을 하지 않는다 — 최종 선택은 §7 의 루프 밖 주체(운영자)가 하고, 그 선택은
설계가 자동화하지 않는다.**

### 6.5 🔴 붙이기보다 제거·필터가 먼저

**[설계]** 사용자 지론을 절차에 못 박는다. **매 라운드, S1/S2/S3 변이를 만들기 전에
`filter_strip` 단계를 먼저 실행한다.** 순서가 규율이다.

**근거 — 우리 데이터에서 파레토 바깥이동은 전부 "걷어내서" 나왔다** **[사실]**:
- `PHASE1_VERDICT.md` §2 시도1: 프로브 1표 → **3표 합의**. 회수율 90.0% 유지(손실 0),
  검토율 38.9% → **35.2%**, 자동 오탐 0 유지. **지표를 더 붙인 게 아니라 불안정분을 걷어냈다.**
- `PHASE2_VERDICT.md` §3: 171건을 **라벨하지 않고** 종결. 원안 완주가 파레토 열등이므로.
- `IC` §2: 저자 진단대로 저지에 지침을 **추가**했다면 "멀쩡한 도구를 고치고 그것을 개선이라고
  보고할 뻔했다." 그리고 부수 소득: **지침이 단순한 쪽이 오히려 3판 재현성이 높았다**
  (Phase 1 v3 는 5건 흔들림, Phase 3 저지는 SPLIT 0건).

세 번 다 같은 방향이다. **[설계]** 그러므로:

**절차 F — filter_strip (라운드 시작 시 필수)**

```
1) front 의 각 후보에 대해 "걷어낼 불안정분" 후보를 열거한다. 우선순위 순:
   a. SPLIT 을 유발하는 지시문 요소 — n_split > 0 인 후보에서, SPLIT 건들의
      rationale 에 공통 등장하는 판정 기준 문장
   b. 오탐(사람 S → 문제 판정)을 유발하는 지시문 요소 — n_flagged - n_detected 건들의
      rationale 공통 요소
   c. 참조 필드에서만 비용을 쓰는 요소 (prompt_chars 를 늘리면서 두 축 어디도 못 올린 diff)

2) 그중 **제거 변이 1개**를 만든다. edited_surface 는 1개, diff 는 "삭제" 만.
   추가·수정 금지. origin = "filter_strip".

3) 제거 변이가 만들어지면 그 라운드의 후보는 filter_strip 1개 + S1/S2/S3 최대 3개 = 최대 4개.
   ⚠️ 단 T2 예산(165콜/후보)을 초과하면 **filter_strip 을 남기고 S3 를 버린다.**
      우선순위: filter_strip > S1 > S2 > S3.

4) 1)에서 걷어낼 것이 없으면(SPLIT 0 + 오탐 0 + 무용 diff 0) filter_strip 을 건너뛴다.
   그리고 이 사실을 mh_front.json 에 기록한다 — 걷어낼 것이 없다는 것은
   T1 정지가 가까워졌다는 신호다.
```

**[설계]** 3)의 우선순위가 이 설계의 성격을 결정한다. 예산이 부족할 때 **버리는 것은
새 기법(S3)이고 남기는 것은 제거(filter_strip)** 다. 이것은 `skill` §개념2 와 긴장
관계에 있다 — 거기서는 "곡선 레버(데이터·알고리즘)" 가 프론티어를 밀고 다이얼은 못
민다고 했다 **[사실]**. **[설계]** 우리 판단: 우리 탐색 공간(프롬프트 지시문)은 대부분
**다이얼 레버**이므로, 다이얼을 더 돌리는 것(S3)보다 **불안정분 제거**(Phase 1 3표 합의가
실증한, 다이얼 공간 안에서 얻은 유일한 바깥이동)가 기대값이 높다. 이 판단은 실측으로
반증 가능하다 — filter_strip 후보가 3라운드 연속 front 에 못 들면 우선순위를 뒤집는다.
**단 그 변경은 §10 순서를 따라 새 사전 선언으로만 한다.**

---

## 7. 🔴 루프 밖 기준 (외부 검증)

**[사실]** 두 출처가 독립적으로 같은 처방을 낸다.

`src2` §5 도입부:
> "The evaluator and permission control should sit **outside** the loop that evolves the harness."

`src3` (인용 12):
> "The evaluator and permission control should likely sit outside the loop that evolves harness, with held-out tests, trace audits, and human review at decision points that matter—how much oversight can be scaled up and automated remains an open research area."

`src3` (인용 11) 이 이유를 밝힌다:
> "Self-harness type of work does raise my concerns that if a program is allowed to edit the OS system, abstraction boundaries are broken. The editable surface needs to be properly designed and the permission control and security layers need to live outside this loop. All the challenges around reward hacking still remain."

**[사실]** 그리고 `src3` 이 인용한 AHE(Lin et al. 2026)의 읽기 전용 경계가 구체적 이식
사례다: "the runs directory, tracer, verifier, and LLM configuration are read-only, which
disables a set of reward hacking (e.g disabling the verifier, swapping the model, or
raising the reasoning budget)" (`src3` §5).

### 7.1 경계 확정표

**[설계]** 실측 확인된 파일 경로만 쓴다.

| 구성요소 | 실제 경로 / 정체 | 루프 | 쓰기 권한 |
|---|---|---|---|
| **사람 라벨 55건** | `gate/scripts/phase1_human_label_sheet.xlsx` (시트 `라벨링`, G열 = S/C/I) + `phase1_human_label_sheet.json` | **밖** | **읽기 전용.** `label_sheet_sha256` 로 매 측정 검증 |
| **목적 축 정의·측정 함수** | §3.3 정의 (현 구현: `instrument_check_score.py` 의 `PROBLEM` / 다수결 / recall / precision) | **밖** | 읽기 전용 |
| **부트스트랩 CI 계산기** | §9 의 `mh_objectives.py` (신규) | **밖** | 읽기 전용 |
| **dominance 판정식 + front 계산** | §9 의 `mh_front.py` (신규) | **밖** | 읽기 전용 |
| **표본 요건 R1~R5** | §4.4, `mh_front.py` 에 상수로 | **밖** | 읽기 전용 |
| **계기 검침 게이트** | `INSTRUMENT_CHECK_PREREG.md` §4 + `instrument_check_score.py` (`RECALL_THRESHOLD = 0.30`) | **밖** | 읽기 전용 |
| **결정론 채점기** | `gate/src/reflection_gate/deterministic.py`, `gate.py`(`evaluate`), `policy.py`, `models.py` + `tests/` (pytest, 네거티브 컨트롤 포함) | **밖** | 읽기 전용 |
| **모델 ID** | `claude-sonnet-4-6` (`phase3_build_prompts.CLAUDE_MODEL`) | **밖** | **읽기 전용 — 모델 교체 금지** |
| **3판 규약 / fail-closed** | `P4` §5.3 | **밖** | 읽기 전용 |
| **운영자의 최종 판정** | 사람 | **밖** | front 를 보고 운영점 선택 |
| | | | |
| **proposer** (변이 생성자) | §9 의 `mh_propose.md` 절차 + 사람/에이전트 | **안** | `harness.*` 필드만 |
| **저지 (판정기)** | `phase3_build_prompts.JUDGE` / `CONTRACT` / `SIBLING_HEADER` 등 지시문 상수 | **안** | proposer 가 수정 가능 |
| **프롬프트 빌더 구조** | `phase3_build_prompts.build()` 의 parts 조립 순서 | **안** | 수정 가능 |
| **후보 계보·아카이브 원장** | `mh_archive.jsonl` | **안** (append 만) | append only |

### 7.2 불변식 — 루프 안이 루프 밖을 수정할 수 없다

**[설계]** 다음을 **불변식(invariant)** 으로 선언한다. 위반은 버그가 아니라 **실험 무효**다.

> **INV-1**: 루프 안 구성요소는 루프 밖 구성요소를 읽을 수 있으나 **쓸 수 없다.**
>
> **INV-2**: `phase1_human_label_sheet.xlsx` / `.json` 의 sha256 은 전 라운드에서 동일해야
> 한다. 다르면 그 시점 이후 모든 후보의 축 값이 **비교 불가**이며 실행을 중단한다.
>
> **INV-3**: `CLAUDE_MODEL` 은 `claude-sonnet-4-6` 고정. proposer 가 모델·max-turns·
> 타임아웃을 바꾸는 변이를 제안하면 `status = "INVALID"`.
>
> **INV-4**: 판정 임계(§4.4 R1~R5, `IC` recall ≥ 30%, front 상한 8, T1~T4)는 **본 실행
> 중 변경 불가.** 변경은 §10 순서를 따라 새 사전 선언 문서를 커밋한 뒤 다음 실행에서만.
>
> **INV-5**: 채점기·CI 계산기·front 계산기는 **결과 열람 전에 커밋**된다. 이는 새 규율이
> 아니라 이미 3회 적용된 것이다 — `instrument_check_score.py`(커밋 `5d13ec3`, `IC` 결과 문서),
> `phase3_score.py`(커밋 `19e0081`, `PHASE3_VERDICT.md`), `sidecheck_score.py`(문서 상단
> "결과를 보기 전에 커밋한다"). **[사실]**
>
> **INV-6**: proposer 는 **자기 후보의 축 점수를 계산하지 않는다.** 측정은 러너가 하고
> 판정은 `mh_front.py` 가 한다. proposer 는 계산된 결과만 읽는다.

**[설계] 기계 검증.** INV-2/INV-3 는 §9 의 `mh_guard.py` 가 매 라운드 실행 시 검사하고
위반 시 `SystemExit` 한다. 이 방식은 우리 레포에 전례가 있다 — `phase3_build_prompts.py`
의 `assert_single_variable()` 이 변인 오염 시 `VariableContamination` 예외를 던지고,
`phase3_run_judge.py` 가 **매 건마다** 그것을 호출한다 **[사실]**. 같은 문서가 이유까지
적어 두었다: "검증을 문서가 아니라 코드에 두는 이유는, 나중에 프롬프트를 손댈 때 사람이
'이 정도는 괜찮겠지' 하고 변인을 오염시키는 것을 막기 위해서다."

**[설계] 왜 저지가 루프 안인가 — 명시적 확인.** 저지(`JUDGE` 지시문)는 최적화 **대상**
이므로 루프 안이다. 그런데 축을 재는 데 쓰이는 것도 저지의 출력이다. 순환이 아닌가?
아니다 — **판정 기준은 사람 라벨(루프 밖)이고 저지는 피험자다.** 저지가 잘 맞히면 recall/
precision 이 오르고, 저지가 라벨을 바꿀 수는 없다. 이 구조는 `IC` §3 과 동일하다:
"라벨 55건은 **정답지**이며 이 검침으로 재라벨·수정하지 않는다" **[사실]**.

---

## 8. 계기 검침 게이트와의 접속

**[설계]** 원칙 한 줄: **고장난 자로 잰 front 는 front 가 아니다.** 축이 2개면 고장 지점도
2개가 되므로, 검침은 오히려 더 필요해진다.

### 8.1 기존 게이트가 무엇을 보장하는가

**[사실]** `IC` §4 의 사전 선언 기준:

| 판정 | 조건 | 처방 |
|---|---|---|
| PASS | recall ≥ 30% (≥4/11) **and** CONTRADICTED ≥ 1건 | 저지 유지, 표본을 바꾼다 |
| DEGRADED | 0 < recall < 30% | 저지 교정 후 재검침 |
| FAIL | recall = 0 | 저지 폐기, v3 계열 재구성 |

**[사실]** 실측 결과(`INSTRUMENT_CHECK_RESULT.md`): recall **81.8%** (9/11),
Wilson 95% [52.3%, 94.9%], CONTRADICTED 7건, SPLIT **0건**, 정밀도 69.2%(게이트 미사용)
→ **PASS**. 혼동행렬: human=S 44건 중 SUPPORTED 40 / CONTRADICTED 3 / INSUFFICIENT 1.

**[사실]** 그리고 이 게이트는 **저자의 진단이 틀렸음을 잡아냈다**(`IC` 결과 §2) — 가설 I
(계기 고장)이 기각됐다. 검침 없이 진단대로 고쳤다면 멀쩡한 도구를 고치고 그것을 개선이라고
보고했을 것이다.

**[사실]** 옆방 2곳에서도 동일 임계로 PASS 했다(`sidecheck_score.py` 의
`RECALL_THRESHOLD = 0.30`, "전 옆방 동일, 변경 금지"): SciFact(en) recall 100%,
KLUE-NLI(ko) recall 100%, 양쪽 SPLIT 0.

### 8.2 🔴 파레토 판정 이전에 통과해야 할 검침 항목

**[설계]** `IC` 의 게이트는 **recall 만** 본다. 사유가 명시돼 있다 — "Phase 3에서 확인된
실패 모드는 과검출이 아니라 **무검출**이다" (`IC` §4) **[사실]**. 그런데 우리 목적 벡터는
precision 도 축으로 쓴다(§3.3). **precision 축을 재는 자가 멀쩡한지는 아직 검침된 적이
없다.** 그래서 검침 항목을 확장한다.

**게이트 IC-0 (기존, 변경 없음)** — 실행 **전** 1회.
```bash
cd gate
for r in run1 run2 run3; do .venv/bin/python scripts/instrument_check_run.py $r; done
.venv/bin/python scripts/instrument_check_score.py
```
**[설계]** `verdict != "PASS"` 면 **파레토 탐색을 시작하지 않는다.** `IC` §4 의 임계와
스크립트를 **한 글자도 바꾸지 않는다.** 이미 통과한 실행이 있으므로(`instrument_check_result.json`
존재, verdict PASS) 재실행은 baseline 확정 목적이며, **재실행 결과가 PASS 가 아니면
환경이 변한 것이므로 중단하고 원인을 규명한다.**

**게이트 IC-1 (신규) — precision 축의 판별력 검침.** **[설계]**

문제: precision 축이 판정에 기여하려면 **후보 간에 precision 이 실제로 달라야** 한다.
recall 이 세 방 모두 100%/81.8% 로 갈렸지만 precision 은 64.7% / 95.7% / 69.2% 로
크게 갈렸다는 것이 이 축의 판별력 근거지만 **[사실]**, 그것은 **도메인 간** 차이이고
**같은 도메인 내 후보 간** 차이는 아직 관측된 바 없다.

- **측정**: baseline `c000`(= 현 Phase 3 저지, `build(u, with_siblings=True)`) 와
  **의도적 저품질 후보 `c_neg`** 2개를 측정한다.
  - `c_neg_loose`: 지시문에서 INSUFFICIENT 정의를 삭제 → 과소검출 기대
  - `c_neg_strict`: "의심되면 INSUFFICIENT" 1문장 추가 → 과검출 기대
- **판정 기준 (사전 고정)**: `c_neg_strict` 의 precision 이 `c000` 의 precision 보다
  **CI 비겹침으로 낮아야** 한다(§4.3 N2 기준). 즉 **과검출을 precision 축이 벌해야 한다.**
- **FAIL 시**: precision 축이 과검출을 구별하지 못한다는 뜻 → **precision 축을 폐기하고
  §3.6 에 따라 다른 축을 선정한 뒤 새 사전 선언을 커밋**한다. 파레토 탐색은 시작하지 않는다.
- **비용**: 2후보 × 165콜 = **330콜.**

**[설계]** 이것은 네거티브 컨트롤이며, 우리 레포에 전례가 있다 — `ab/grade_ab.py` 가
"채점기 자체를 네거티브 컨트롤 6종으로 검증" 했고 `gate/tests/test_negative_controls.py`
가 존재한다 **[사실]**. 새 발명이 아니라 기존 규율의 이식이다.

**게이트 IC-2 (신규) — 부트스트랩 CI 계산기 자체의 검침.** **[설계]**

축을 재는 자가 아니라 **CI 를 재는 자**를 검침한다. `mh_objectives.py` 를 쓰기 전에:
- 합성 입력 3종으로 알려진 답을 확인한다: (a) 전건 정탐 → recall CI = [1.0, 1.0],
  (b) 전건 미탐 → recall CI = [0.0, 0.0], (c) `n_flagged = 0` → precision **미정의**로
  반환(0.0 아님. §4.4 R2 의 함정).
- 같은 seed 로 두 번 돌려 **비트 단위 동일**한 CI 가 나오는지 확인한다(재현성).
- 실패 시 탐색을 시작하지 않는다. **비용 0콜** (LLM 호출 없음).

### 8.3 검침 → 파레토 판정 순서

**[설계]** 이 순서를 바꾸지 않는다.

```
IC-2 (0콜, CI 계산기 자기검증)
  ↓ PASS
IC-0 (165콜, 기존 게이트 — recall ≥ 30% and CONTRADICTED ≥ 1)
  ↓ PASS
IC-1 (330콜, precision 축 판별력 네거티브 컨트롤)
  ↓ PASS
baseline c000 확정 → mh_archive.jsonl 에 첫 줄 기록
  ↓
라운드 1: filter_strip → S1 → S2 → S3  (§6.5 우선순위)
  ↓
mh_front.py 로 front 재계산 → T1~T4 검사
  ↓
(반복 또는 정지)
```

**[설계] 누적 예산 확인.** IC-0(165) + IC-1(330) = **495콜**을 검침에 쓰고, T2 의 탐색
예산 1,650콜은 **별도**다. 총 상한 **2,145콜.** Phase 3 단일 실험(1,650콜)의 1.3배로
"검침 3종 + 파레토 탐색 최대 10후보" 를 전부 커버한다. **[설계]** 이 비율을 근거로
검침을 생략할 유혹을 미리 차단한다 — 검침은 전체의 23%이고, `IC` §0 이 기록한 대로
검침을 건너뛴 대가는 **1,650콜 전액 손실**이었다.

---

## 9. 최소 구현 계획

**[설계]** 파일 단위. 실제 코드는 쓰지 않는다. 재사용은 명시한다.

### 9.1 신규 파일

| 파일 | 역할 (3줄 이내) |
|---|---|
| `gate/scripts/mh_objectives.py` | 3판 jsonl + 라벨 시트를 받아 recall/precision 점 추정과 부트스트랩 CI 2종(claim·qid 클러스터)을 계산한다. seed 20260730 고정, B=2000. IC-2 자기검증 모드(`--selftest`) 포함. |
| `gate/scripts/mh_front.py` | `mh_archive.jsonl` 을 읽어 §4 dominance(CI 겹침 동률 포함)로 front 를 계산하고 `mh_front.json` 을 쓴다. §4.4 R1~R5 와 §5.4 상한·솎아내기, T1~T4 종료 조건 판정을 포함한다. |
| `gate/scripts/mh_guard.py` | INV-2(라벨 시트 sha256 불변) · INV-3(모델 고정) · INV-6(proposer 가 축을 계산하지 않음) 을 검사하고 위반 시 `SystemExit`. 매 라운드 시작 시 호출된다. |
| `gate/scripts/mh_run_candidate.py` | 후보 1개를 3판(55×3=165콜) 측정해 `mh_c<NNN>_run{1,2,3}.jsonl` 을 쓴다. 재개 가능·fail-closed. 후보 정의는 `mh_archive.jsonl` 의 `harness` 필드에서 읽는다. |
| `gate/scripts/mh_pair_diagnose.py` | §6.2 절차 S3 — 두 끝점의 원자료를 4분면(BOTH_OK/A_ONLY/B_ONLY/BOTH_FAIL)으로 분류하고 BOTH_FAIL 을 문항 단위로 묶어 표적 클러스터와 금지 표면 목록을 출력한다. |
| `gate/scripts/mh_filter_candidates.py` | §6.5 절차 F — front 후보들의 SPLIT·오탐 건 rationale 에서 공통 요소를 뽑아 "걷어낼 후보" 목록을 낸다. 제거 변이 제안은 사람/proposer 가 하고 이 스크립트는 근거만 제공한다. |
| `gate/scripts/mh_ic1_negative_control.py` | §8.2 IC-1 — `c_neg_loose` / `c_neg_strict` 2개를 생성·측정하고 precision 축이 과검출을 CI 비겹침으로 벌하는지 판정한다. 330콜. |
| `gate/PARETO_META_HARNESS_PREREG.md` | 이 설계에서 **판정 기준만 추출한 사전 선언**. 축 2개·판정식·임계·종료조건·금지사항. §10 순서상 첫 실행 **전** 커밋. |
| `gate/scripts/mh_propose.md` | proposer 절차서(skill 문서 대응). 부모 선택 규칙(§6.1)·금지 표면·`origin_reason` 필수 항목·수정 가능 표면 목록. 목적을 자연어로 전달하지 않고 **규칙으로** 전달한다. |
| `gate/PARETO_META_HARNESS_RESULT.md` | 결과 문서. 실행 후 작성. front 표 + T1~T4 중 무엇으로 정지했는지 + 판정 불가면 그대로 보고. |

### 9.2 재사용 (수정하지 않고 import)

| 기존 파일 | 재사용 내용 |
|---|---|
| `gate/scripts/phase3_build_prompts.py` | `build()` · `CLAUDE_MODEL` · `SIBLING_HEADER` · `JUDGE` · `CONTRACT`. **baseline `c000` 은 이 빌더의 현 상태 그대로다.** 변이는 이 모듈의 사본에 적용하고 원본은 건드리지 않는다 |
| `gate/scripts/instrument_check_run.py` | `load_units()`(라벨 시트 → unit) · `call()`(fail-closed 규약) · `VALID` 집합. `mh_run_candidate.py` 가 이 함수들을 재사용한다 |
| `gate/scripts/instrument_check_score.py` | `PROBLEM` 집합 · 3판 다수결 로직 · `wilson()`. **recall/precision 정의를 새로 쓰지 않고 이 정의를 그대로 쓴다**(§3.3) |
| `gate/scripts/phase1_human_label_sheet.{xlsx,json}` | 사람 라벨 55건. **읽기 전용**(INV-2) |
| `gate/src/reflection_gate/semantic.py` | `SYSTEM_GUARD` · `EVIDENCE_OPEN/CLOSE` · `sanitize_evidence_text()`. 프롬프트 인젝션 방어는 루프 밖이므로 변이 대상이 아니다 |
| `gate/src/reflection_gate/` 전체 + `gate/tests/` | 결정론 채점 레이어. 루프 밖(§7.1). 이번 작업에서 **수정하지 않는다** |
| `gate/scripts/phase3_power_check.py` | `mcnemar_exact()` · `wilson()`. 필요 시 참조. **양측 p 임계가 불일치쌍 6건**이라는 정정 기록도 함께 승계 |
| `gate/scripts/sidecheck_score.py` | 임계를 방마다 바꾸지 않는 패턴. 다른 도메인으로 이식할 때의 참조 구현 |

### 9.3 구현 순서

**[설계]** 의존 순서대로. 각 단계는 다음 단계의 전제다.

```
1. PARETO_META_HARNESS_PREREG.md          (커밋. 코드 0줄)
2. mh_objectives.py + --selftest 통과      (IC-2)
3. mh_front.py + mh_guard.py               (판정기. 결과 열람 전 커밋 — INV-5)
4. mh_run_candidate.py                     (러너)
5. IC-0 재실행 → IC-1 실행 → baseline c000 기록
6. mh_pair_diagnose.py + mh_filter_candidates.py + mh_propose.md
7. 라운드 실행 (최대 3~4라운드, T2=1,650콜)
8. PARETO_META_HARNESS_RESULT.md
```

**[설계]** 3번이 4번보다 앞인 것이 핵심이다. **판정기를 러너보다 먼저 커밋한다** —
INV-5, 그리고 우리 레포가 3회 지킨 규율(§7.2).

---

## 10. 사전등록 관점의 위험

**[설계]** 결과를 보고 축이나 판정식을 바꾸면 **optional stopping 의 다목적판**이 된다.
단일 지표에서는 "언제 멈출지" 를 결과를 보고 고르는 것이 문제였다. 다목적에서는
**"어느 축을 셀지" 를 결과를 보고 고르는 것**이 추가된다. 후자가 더 위험하다 — 축을 하나
더하거나 빼면 front 멤버십이 통째로 바뀌고, 그 조작은 "다목적이니까 축을 더 봤다" 는
그럴듯한 서술로 은폐된다.

**[사실]** 우리는 이미 이 유혹에 노출된 전례가 있다. `PHASE2_VERDICT.md` §5 가 하지 않은
것을 명시한다: "목표 55건을 낮춰 '달성'으로 만들지 않았다. 회수율 대신 유리한 다른 지표로
갈아타 Phase 2를 성공으로 보고하지 않았다." 그리고 `P4` §6 이 금지 사항 목록을 갖고 있다.

### 10.1 확정 순서 (이 순서를 어기면 실험 무효)

**[설계]**

| 단계 | 무엇을 확정 | 언제 | 확정 후 변경 가능? |
|---|---|---|---|
| **D0** | 목적 축 2개 = (recall, precision), 측정 함수, 데이터 출처 | **지금 — 이 문서** | ❌ |
| **D1** | dominance 판정식, 동률 규칙, 노이즈 규칙(부트스트랩 B/seed/CI 선택), R1~R5 | **지금 — 이 문서 §4** | ❌ |
| **D2** | front 스키마, 상한 8, 솎아내기 규칙, 제거 규칙 | **지금 — 이 문서 §5** | ❌ |
| **D3** | 부모 선택 규칙 S1/S2/S3, filter_strip 우선순위, T1~T4 | **지금 — 이 문서 §6** | ❌ |
| **D4** | 루프 경계표 + INV-1~6 | **지금 — 이 문서 §7** | ❌ |
| **D5** | 검침 게이트 IC-0/IC-1/IC-2 와 각 임계 | **지금 — 이 문서 §8** | ❌ |
| **D6** | `PARETO_META_HARNESS_PREREG.md` 커밋 | **첫 콜 이전** | ❌ |
| **D7** | 판정기 코드(`mh_objectives.py`, `mh_front.py`, `mh_guard.py`) 커밋 | **첫 후보 측정 이전** | ❌ (버그 수정은 커밋 이력에 남기고 사유 기록) |
| **D8** | baseline `c000` 의 축 값 | IC-0/IC-1 통과 직후 | ❌ |
| **D9** | 후보별 축 값 | 각 측정 직후 | ❌ (재측정 금지 — `prompt_sha256` 로 차단) |
| **D10** | 정지 판정 (T1~T4 중 무엇) | 각 라운드 종료 시 자동 | — |
| **D11** | front 에서 운영점 1개 선택 | 정지 후, **사람이** | 사람 판단이므로 사전등록 대상 아님 (§6.4) |

**[설계]** D0~D5 가 이 문서에 **전부 들어 있다는 것이 요점이다.** 결과를 하나도 보지 않은
시점에 축·판정식·임계·종료조건이 다 박혀 있어야 사전등록이 성립한다. D6 는 이 문서에서
판정 기준만 발췌해 별 문서로 커밋하는 형식적 단계다 — 이 문서는 논증을 포함하므로 길고,
사전 선언은 짧고 기계적이어야 검증 가능하다.

### 10.2 금지 사항 (`P4` §6 승계 + 다목적 확장)

**[설계]**

1. 결과를 보고 **축을 추가·제거·교체**하는 것. 특히 §3.5 참고 필드를 본 실행 중에 축으로
   승격하는 것.
2. 결과를 보고 **임계를 조정**하는 것 (`IC` recall 30%, R1~R5, front 상한 8, T1 3라운드,
   T2 1,650콜, 부트스트랩 B·seed).
3. **스칼라 가중합·F1·hypervolume 으로 dominance 를 대체**하는 것. F1 병기 보고는 허용,
   판정 입력은 금지(§4.2).
4. **CI 를 좁히려고 리샘플 단위를 claim 으로 바꾸는 것.** 판정에는 `ci_qid`(보수적)를
   쓴다고 §4.3 에서 확정했다. 결과가 안 나와서 claim CI 로 바꾸면 그것이 조작이다.
5. **후보를 재측정해 유리한 실행을 채택**하는 것. `prompt_sha256` 중복 차단으로 구조적으로
   막지만, 우회 시도 자체를 금지한다.
6. **front 진입 건수·채택 건수를 KPI 로 삼는 것.** `P4` §6 승계. 근거는 Obfuscation Atlas
   계열(probe-graph 대원칙 3) — 지적 건수를 KPI 로 삼으면 프로브를 피하는 방향으로 최적화된다.
7. **변이를 강제하는 것** (§6.3). `no-change` 는 정당한 산출이다.
8. **라벨 시트를 수정하는 것** (INV-2). 라벨이 틀렸다고 판단되면 이 실험을 중단하고
   별도 재라벨 프로토콜을 사전 선언한 뒤 **처음부터** 다시 한다.
9. **판정 불가를 다른 결론으로 갈아타는 것.** T4 로 정지하면 "표본 부족으로 판정 불가" 가
   결론이다. `PHASE2_VERDICT.md` 가 그렇게 했고 그것이 규율이다.

### 10.3 이 설계가 스스로 실패할 수 있는 방식 (미리 선언)

**[설계]** 정직하게 미리 적는다. 아래 중 어느 것이 나와도 **설계 실패가 아니라 결과**다.

- **front 크기가 1로 유지된다.** baseline 이 모든 후보를 지배 → §6.1 의 S1=S2 예외 경로로
  filter_strip 만 돌다가 T1/T3 정지. 결론: "이 탐색 공간에서 baseline 을 지배하는 변이를
  찾지 못했다." 이는 `skill` §"모서리점" 판정의 반복이며, 그 자체로 보고 가치가 있다.
- **모든 후보가 서로 비지배.** T4 정지 → 표본 부족 판정 불가.
- **IC-1 FAIL.** precision 축이 과검출을 구별 못 함 → 탐색 시작 전에 축 재설계.
  495콜 이내에서 알게 된다.
- **BOTH_FAIL 클러스터가 Q068 하나로 고정.** S3 가 매 라운드 같은 표적을 치고 실패 →
  T1 정지. 결론: "Q068 계열이 이 코퍼스의 천장" (`IC` §5 가 이미 시사한 것).

---

## 11. 미확인·한계

### 11.1 정독본에서 미확인으로 남아 이 설계에 영향을 주는 것

**[사실 — 부재 / 미확인]**

| 항목 | 출처 | 이 설계에 주는 영향 |
|---|---|---|
| Meta-Harness 의 **dominance 판정식** (부등호 방향, weak/strong, 타이브레이크) | `src4` §5-4·§12 | **비교 불가.** 우리 §4 식이 그쪽과 같은지 다른지 확인할 수 없다. 따라서 "Meta-Harness 를 개선했다" 고 주장하지 않고 "명세되지 않은 것을 명세했다" 까지만 주장한다 |
| Meta-Harness 의 **노이즈/분산 하 dominance 처리** | `src4` §12 | 우리 §4.3 이 선행연구와 대조 불가. 근거를 우리 실측(Phase 1 재현성, Wilson 관행)에서만 끌어온다 |
| Meta-Harness 의 **front 크기 상한 존재 여부** | `src4` §5-5 | 우리 상한 8의 근거가 "2축 40후보 → front 8" 이라는 **단일 관측점**뿐이다. 상한 8은 원리가 아니라 잠정값이다 |
| Meta-Harness **front 에서 최종 1개를 고르는 자동 규칙** | `src4` §6·§12 | 없다고 추정될 뿐이다. 우리가 §6.4 에서 "자동 선택 안 함" 을 택한 것은 선행연구 부재를 메우는 게 아니라 **동일한 공백을 의도적으로 유지**하는 것이다 |
| **GEPA 의 front 활용 방식** 원문 | `src2` 1줄 항목, `src4` Appendix E 가 이 축을 다루지 않음 | §2 표의 GEPA 행이 2차 출처 기반이다. "GEPA 와 다르다/같다" 는 주장을 하지 않는다 |
| Self-Harness 의 `K`(제안 폭)·`T`(라운드 수) | `src1` §9 | 우리 라운드당 3~4후보·최대 3~4라운드가 선행연구 대비 크거나 작은지 판단 근거가 없다. T2 예산은 우리 콜 회계에서만 정당화된다 |
| Self-Harness 의 held-in/held-out **분할 크기** | `src1` §4·§9 | 우리는 분할을 쓰지 않으므로 직접 영향은 없다. 단 §11.2 의 첫 항목과 연결된다 |
| Self-Harness **merge 후 재검증/롤백 규칙** | `src1` §9 | 우리는 merge 를 하지 않는다(라운드당 후보를 독립 측정). 이 공백을 피하는 방향으로 설계했다 |
| **라운드당 비용(토큰·시간·요금)** — 두 논문 모두 미보고 | `src1` §9, `src4` §9-5 | 우리 T2 예산이 선행연구와 비교 불가. 자체 회계(165콜/후보)만 근거 |
| **통계적 유의성·신뢰구간** — 두 논문 모두 없음 | `src1` §4, `src4` §9-5 | §4.3 의 CI 규칙에 선행 사례가 없다. **우리가 처음 쓰는 것이므로 틀릴 수 있다** |
| Weakness Mining 의 signature 산출 주체가 대상 모델인지 별도 시스템인지 | `src1` §7 | §6.2 의 쌍 진단을 사람/에이전트 중 누가 하는지에 대한 선행 근거가 없다. 우리는 스크립트가 4분면을 계산하고 해석은 proposer 가 하도록 나눴다 — 이 분할에 선행 근거 없음 |
| Lilian Weng 의 Meta-Harness **Pareto 목적 축 설명** | `src3` §10 미확인 항목 | 3차 출처에서도 축 정보를 얻을 수 없다 |
| `src3` 코딩 에이전트 루프 도식 (이미지) | `src3` §10 | harness 루프 구조 참조 불가. 우리는 우리 파일 구조를 쓴다 |

### 11.2 이 설계 자체의 한계

**[설계]** 실행하면 반드시 결론에 병기해야 하는 것들.

1. **held-out 이 없다.** 성능축이 **사람 라벨 55건 전량**에 묶여 있고, 그 55건이 부모
   선택에도 간접적으로 노출된다(§6.2 의 쌍 진단이 라벨과의 일치/불일치를 본다).
   즉 우리 front 는 **선택 신호가 반복 사용된 집합 위의 front** 다. 이 문제는 선행연구에도
   있다 — `src1` 은 held-out 을 15~20 라운드 동안 selection 신호로 반복 사용했고(`src1` §5),
   `src4` §4.3 은 TB2 에서 search/test 를 아예 분리하지 않았다(`src4` §9-2). **[설계]**
   우리가 그들보다 나은 점은 없고, **다른 점은 이 사실을 결과 문서 첫 줄에 쓴다는 것뿐이다.**
   `P4` §7 이 같은 고지를 이미 했다: "성능축이 Phase 1 라벨 55건에 묶여 있다. 이 집합은
   이미 여러 Phase에서 참조됐으므로 완전히 신선하지 않다." **[사실]**
2. **라벨러 1인, inter-rater 신뢰도 미측정.** `PHASE1_VERDICT.md` §8 · `PHASE2_VERDICT.md`
   §8 이 이미 고지한 미해결 사항 **[사실]**. 두 축이 모두 이 라벨에서 나오므로 **라벨 오류는
   두 축에 동시에 전파**된다. 축을 2개로 늘려도 이 의존은 줄지 않는다.
3. **표본 55건이 편향 추출이다.** `IC` §5 · `PHASE2_VERDICT.md` §4: Phase 1 기저율 18.5%
   는 편향 추출의 산물이고 무작위 추출은 3.3% 였다 **[사실]**. 따라서 여기서 나오는
   recall/precision 은 **일반 코퍼스 값이 아니다.** front 의 상대 순서는 유효할 수 있으나
   절대 수치는 운영 성능 예측치가 아니다.
4. **군집화가 CI 를 지배할 수 있다.** `phase3_power_check.py` 가 경고한 대로 독립 단위는
   문항이다 **[사실]**. 55건이 소수 문항에 몰려 있으면 `ci_qid` 가 매우 넓어져 **모든 후보가
   전 축 겹침 동률**이 된다 → T4 정지. **[설계]** 이 경우 판정 불가가 결론이며,
   claim CI 로 갈아타지 않는다(§10.2 금지 4).
5. **최대 10후보는 작다.** `src4` §4.1 은 40후보로 front 8을 얻었다 **[사실]**. 우리는
   10후보 상한이므로 front 가 얇을 수밖에 없다. "프런티어를 그렸다" 고 주장할 수 없고,
   README 의 기존 표현과 같은 범위로만 주장한다 — "열등 이동을 실측으로 판별했다."
6. **단일 모델·단일 도메인.** 판정기는 `claude-sonnet-4-6` 하나이고 도메인은 K-IFRS 하나다.
   옆방 2곳 PASS 는 **계기 검침 절차**의 이식성 증거이며 **파레토 탐색**의 이식성 증거가
   아니다. 모델 간 이식성은 여전히 미검증(README 명시) **[사실]**.
7. **proposer 가 사람인지 에이전트인지 이 설계가 정하지 않았다.** §6 의 규칙은 어느 쪽이든
   따를 수 있게 썼다. 그러나 `src4` §9-2 6번·7번이 경고한 것 — skill 텍스트 반복 수정이
   iteration 수·population 크기보다 결과에 더 큰 영향을 줬다 **[사실]** — 이 우리에게도
   적용된다. **`mh_propose.md` 를 결과를 보고 고치는 것은 §10.2 2번 위반**으로 취급하되,
   이 위험이 완전히 봉쇄되지 않았음을 인정한다.
8. **filter_strip 우선순위에 실증 근거가 얇다.** §6.5 의 근거는 Phase 1 3표 합의 1건
   (그리고 그 개선의 표본은 "흔들린 건이 2건뿐" 이라 `PHASE1_VERDICT.md` §2 가 직접
   "표본이 얇다" 고 적었다) **[사실]** + Phase 2·IC 의 방향성 2건이다. **n=1 의 실증 위에
   우선순위를 세웠다는 것을 인정한다.** 3라운드 연속 front 진입 실패 시 뒤집는다고 §6.5 에
   써 두었지만, 그 판단 자체가 소표본이 될 것이다.
9. **부트스트랩 B=2000·seed 고정의 적절성은 검증하지 않았다.** IC-2 는 계산기의 정확성과
   재현성만 본다. B 가 충분한지는 CI 폭 수렴을 확인해야 하나, 이 설계는 그것을 요구하지
   않는다. **[설계]** 이유: B 를 결과를 보고 늘리면 그것이 optional stopping 이다. 고정값을
   미리 박고 사후에 바꾸지 않는 쪽을 택했다.
10. **이 문서는 실행되지 않았다.** 여기 있는 모든 수치는 **기존 Phase 1~3·계기 검침·옆방
    검증의 실측값**이거나 **사전 선언한 임계**다. 파레토 탐색의 결과 수치는 하나도 없다.
    §9 를 구현해 §8 게이트를 통과한 뒤에야 `PARETO_META_HARNESS_RESULT.md` 가 쓰일 수 있다.

---

## 부록 A — 이 설계가 두 논문에 대해 주장하는 것과 하지 않는 것

**[설계]** 범위를 못 박는다.

**주장한다**
- Meta-Harness 가 명세하지 않은 dominance 판정식·front 갱신·제거 규칙·부모 선택 규칙을
  **우리 도메인에 대해** 명세했다.
- Self-Harness 의 비지배 진입 게이트를 front 아카이브 위로 옮기는 구성이 가능하다.
  이 조합은 `src4` §11-5 4번이 "두 논문 어디에도 없다" 고 지목한 바로 그 지점이다 **[사실]**.
- 노이즈 하의 dominance 처리(CI 겹침 동률)를 우리 실측 관행(Wilson 비겹침 판정 3회 사용)
  에서 유도해 명시했다.

**주장하지 않는다**
- 두 논문의 방법보다 성능이 좋다 — 공통 수치 축이 없고, 우리는 harness 코드가 아니라
  프롬프트 지시문을 탐색한다.
- front 를 탐색에 쓰면 더 좋은 harness 가 나온다 — 이것은 **아직 측정하지 않았다.**
  §10.3 이 실패 경로 4개를 미리 열거한 이유다.
- 이 설계가 도메인 일반적이다 — 절차는 일반적일 수 있으나 실측은 K-IFRS 55건 하나다.

---

## 12. 실험 설계 — 조건과 대조군

**[설계]** §1~11 은 시스템 설계로는 닫혔으나 **논문 요건 3개**가 비어 있다: 재현 패키지,
baseline 대조군, ablation. 특히 **§6(front 를 탐색에 쓰는 규칙)이 우리 기여인데, 그것을
뺀 조건이 없으면 기여로 성립하지 않는다.** 이 절이 그 조건들을 구현 전에 못 박는다.
지금 못 박는 이유는 §10 과 같다 — 조건을 결과를 본 뒤에 추가하면 그것이 사후 선택이다.

### 12.1 조건 정의

**[설계]** 조건은 3개. 각 조건은 **후보 예산 10개(1,650콜)를 동일하게** 받는다.

| 조건 | front 유지 | dominance 판정(§4) | 부모 선택 | 한 줄 차이 |
|---|---|---|---|---|
| **C0** (baseline) | ❌ 없음 (활성 harness 1개) | ❌ — 대신 Self-Harness 수락규칙을 **진입 게이트**로 | 항상 현재 활성 harness `hₜ` | 비지배 규칙을 **필터**로만 쓴다 |
| **C1** (front 대조) | ✅ | ✅ (CI 겹침 동률 포함) | **무작위** — front 후보 중 균등 추출 | front 를 갖되 **탐색에 쓰지 않는다** |
| **C2** (제안) | ✅ | ✅ | §6.1 S1/S2/S3 + §6.5 filter_strip **전부** | front 를 **탐색 입력**으로 쓴다 |

**C0 의 수락규칙 — `src1` 원문 그대로 옮긴다.** **[사실]** `src1` §3.4 의 규칙은
`Δ_in ≥ 0` **∧** `Δ_ho ≥ 0` **∧** `max(Δ_in, Δ_ho) > 0` 이고, `Δ` 는 통과 태스크
**개수** 차이이며, 평가가 확률적일 때는 **후보 평가를 반복하고 반복 전체의 누적 통과
수에 같은 규칙을 적용**한다. 추가 거부 조건 2개도 원문에 있다 — editable surface 를
전혀 수정하지 않은 제안, 유효한 평가 결과 전에 실행 실패하는 제안. 거부된 후보는
**로그만 남기고 활성 harness 를 바꾸지 않는다**.

**[설계]** 우리 환경으로의 번역을 1:1 로 명시한다. 번역이 필요한 유일한 지점은
`(P_in, P_ho)` → `(recall, precision)` 이다.

| `src1` 원문 | C0 구현 |
|---|---|
| `Δ_in`, `Δ_ho` = 두 split 의 통과 **개수** 차 | `Δ_recall` = `n_detected` 차, `Δ_precision` = `n_detected/n_flagged` 차 — **분모가 후보마다 변하는 precision 은 개수 차로 쓸 수 없으므로 비율 차를 쓴다.** 이 한 곳이 원문과 다르다 |
| `max(Δ_in, Δ_ho) > 0` | `max(Δ_recall, Δ_precision) > 0` |
| 확률적 평가 → 반복 후 **누적** 통과 수 | 3판을 각각의 반복으로 보지 않고 **§3.3 의 3판 다수결 라벨** 하나로 집계. 사유: 우리 3판은 독립 시도가 아니라 같은 단위에 대한 재판정이고, 다수결 규약이 이미 §4.4 R3 로 고정돼 있다 |
| 점 추정 비교, CI 없음 | **CI 를 쓰지 않는다.** `src1` §4 는 신뢰구간·유의성 검정을 보고하지 않는다 **[사실]** — C0 는 그 상태를 그대로 재현한다 |
| 거부 후보는 로그만 | `mh_archive.jsonl` 에 `status = "REJECTED_C0"` 로 append. **행을 지우지 않는다**(§5.3 제거 B 금지) |
| 통과 후보 여럿이면 merge | **하지 않는다.** 사유: `src1` §9 가 merge 후 재검증·롤백 규칙을 미기재로 남겼고(**[미확인]**), 우리는 라운드당 후보를 독립 측정하므로 merge 를 정의할 근거가 없다(§11.1 마지막 항목과 동일한 회피). **이것은 C0 가 Self-Harness 의 완전한 재현이 아니라는 뜻이며, 부록 B-4 에서 정면으로 답한다** |

**C1 의 무작위 부모 — 무엇을 재현하는가.** **[사실]** `src4` §3: Meta-Harness 는
front 를 유지하지만 `"imposes no parent-selection rule"` 이고, 좋은 조상에서 출발하는 것은
`"an emergent strategy rather than a hard-coded rule"` (`src4` 인용 10)이다.
**[설계]** "규칙 없음" 을 우리 환경에서 실행 가능한 조건으로 만들려면 무언가를 정해야
하고, 우리는 **front 후보 중 균등 무작위 추출**로 정한다. `PARENT_SEED = 20260731` 고정.

**[설계] 이 번역의 한계를 먼저 인정한다.** Meta-Harness 의 "규칙 없음" 은 **강한 코딩
에이전트의 재량**이고 균등 무작위가 아니다. 즉 C1 은 "규칙 없음" 의 **하한(lower bound)**
이다 — 에이전트 재량이 무작위보다 나쁠 이유가 없으므로, C2 > C1 이 나와도 그것이
"우리 규칙 > 에이전트 재량" 을 증명하지 않는다. 이 제약은 §14.5 와 부록 B-5 에 그대로
싣는다. 재량 조건을 조건으로 세우지 않는 이유는 §6 서두와 같다 — **재량은 사전등록될 수
없기 때문**이다.

### 조건이 공유하는 것 (전부 §5·§7 그대로)

**[설계]** 조건 간 유일한 변인은 위 표의 3열이다. 다음은 **세 조건이 글자 단위로 공유**한다.

| 공유 항목 | 근거 절 | C0 에도 적용되는가 |
|---|---|---|
| `mh_archive.jsonl` 스키마 (append-only, `status_history`) | §5.1 | ✅ — front 를 계산하지 않을 뿐 원장은 같다 |
| 물리적 제거 금지 / 원자료 jsonl 보존 | §5.3 제거 B | ✅ |
| 표본 요건 R1~R5 | §4.4 | ✅ — 위반 시 `UNJUDGED`, 수락 판정 안 함 |
| 유효성 검증 3단계 (`INVALID`, `prompt_sha256` 중복 차단) | §5.2 1단계 | ✅ |
| 루프 경계표 + INV-1~6 | §7 | ✅ — 라벨 시트·모델·채점기는 세 조건 모두 루프 밖 |
| 라벨 시트 55건, `label_sheet_sha256` 불변 | §7.1, INV-2 | ✅ |
| 모델 `claude-sonnet-4-6`, 3판, fail-closed | §7.1, INV-3, R3 | ✅ |
| 검침 게이트 IC-0/IC-1/IC-2 | §8 | ✅ — **조건별로 다시 돌지 않는다**(§12.3) |
| 후보 1개 = 165콜 | §6.4 T2 | ✅ |
| 종료 조건 T2(예산)·T3(유효 후보 0) | §6.4 | ✅ |

**[설계] 조건별로 다른 종료 조건.** T1(front 3라운드 미갱신)과 T4(front 절반이 전 축
동률)는 front 가 있어야 정의된다. **C0 에서는 T1 을 "활성 harness 가 3라운드 연속
불변" 으로 대체하고, T4 는 적용하지 않는다.** 이 대체는 `src1` Algorithm 1 5행
("수락된 것이 없으면 `hₜ₊₁ ← hₜ`") 을 그대로 읽은 것이다 **[사실]**.

**[설계] baseline `c000` 은 세 조건이 공유한다.** 같은 빌더의 현 상태(`build(u,
with_siblings=True)`)이므로 `prompt_sha256` 이 동일하고, §5.2 의 중복 차단 규칙에 의해
**한 번만 측정한다.** 조건마다 baseline 을 다시 재면 축 값이 실행 노이즈만큼 갈라져
조건 간 비교가 무효가 된다.

### 12.2 ablation — 각각 어떤 주장을 검증하는가

**[설계]** ablation 은 전부 C2 에서 한 조각씩 빼는 형태다. C2 가 이기더라도 **어느 조각이
이겼는지**를 분해하지 못하면 §6 전체를 기여로 주장할 수 없다. `src1` 의 최대 구멍이
정확히 이것이다 — **[사실]** `src1` 은 ablation 이 **없고**(§4 Baseline), 3단계 중 어느
것이 이득의 원천인지 분해되지 않았다. 반대로 `src4` Table 3 은 proposer 인터페이스
3조건 ablation 으로 "raw trace 접근이 핵심" 을 실증했다 **[사실]**. 우리는 후자를 따른다.

| ablation | 빼는 것 | **검증하는 주장** | 반증 형태 (이 결과면 그 조각은 기여가 아니다) |
|---|---|---|---|
| **A-S3** | §6.2 쌍 진단 (S3 슬롯 비움. S1·S2·filter_strip 유지) | "front **끝점 2개를 동시에 참조**하는 것이 실제로 기여한다" — `src4` §11-3 (1) 이 "단일 활성 harness 체제에서는 원리적으로 불가능" 이라 지목한 추론을 규칙으로 승격한 것이 우리 §6.2 다 **[사실]** | A-S3 의 최종 front 가 C2 의 front 를 **지배하거나 동률**이면, S3 는 콜만 쓰고 아무것도 더하지 않았다 |
| **A-FS** | §6.5 `filter_strip` (제거 단계 없이 S1/S2/S3 만) | 사용자 지론 **"붙이기보다 제거 먼저"** — §6.5 의 근거는 Phase 1 3표 합의 1건이고 `PHASE1_VERDICT.md` §2 가 직접 "표본이 얇다" 고 적었다 **[사실]**. 즉 이 지론은 현재 **n=1** 위에 서 있다 | A-FS 가 C2 와 동률 이상이면 제거 단계는 불필요하다. 반대로 C2 의 front 끝점 중 하나 이상이 `origin = "filter_strip"` 이면 지론이 지지된다 |
| **A-CI** | §4.3 노이즈 규칙 (점 추정만으로 dominance 판정) | "노이즈 처리가 필요한가" — §11.1 이 인정했듯 **CI 규칙에는 선행 사례가 없다**(두 논문 모두 유의성·CI 미보고). 우리가 처음 쓰는 것이므로 검증 대상이다 | 점 추정 front 와 CI front 의 **멤버십이 같으면** CI 는 계산 비용만 쓴 것이다. 반대로 점 추정 front 가 더 크면 "CI 가 우연한 개선을 걸러냈다" 는 §4.3 의 설계 의도가 지지된다 |

**[설계] A-CI 는 0콜로 돌린다 — 그리고 그 대가를 명시한다.**
A-CI 는 **판정 연산자만** 다르므로, C2 가 남긴 `mh_archive.jsonl` 에 점 추정 dominance 를
다시 적용하면 콜 없이 비교할 수 있다(`mh_front.py --ci none`). 단 **유효 범위는
라운드 1 뿐이다** — 라운드 2 이후로는 부모 선택이 갈려 계보 자체가 달라지므로 재분석이
실제 실행을 대체하지 못한다. 그러므로 A-CI 는 두 층으로 보고한다:

- **A-CI(재분석, 0콜)**: 전 라운드의 front 멤버십 차이를 **관측**으로 보고. "만약 그때
  점 추정을 썼다면 front 가 이렇게 달랐다" 까지만 주장한다.
- **A-CI(실행, 1,650콜)**: 예산이 남으면 별도 계보로 완주. 컷라인 아래다(§12.3).

### 우선순위와 컷라인 (예산 초과 시 버리는 순서)

**[설계]** 전부 돌 예산이 없을 때를 **미리** 정한다. 아래 순서는 결과를 보고 바꾸지 않는다.

| 순위 | 항목 | 콜 | 없으면 무엇을 주장할 수 없나 |
|---|---|---|---|
| **P0** | IC-2 → IC-0 → IC-1 (§8.3) | 495 | 아무것도. 고장난 자로 잰 front 는 front 가 아니다 |
| **P1** | **C2** | 1,650 | 제안 자체가 없다 |
| **P2** | **C0** | 1,650 | **baseline 대조군 부재 = `src1` 이 지적받은 그 구멍.** 이게 없으면 논문 요건 미충족 |
| **P3** | A-CI(재분석) | **0** | 노이즈 규칙의 필요성 |
| **P4** | **C1** | 1,650 | "효과가 front 존재 때문인지 §6 규칙 때문인지" 귀속 불가 — **기여 주장의 핵심** |
| **P5** | A-S3 | 1,650 | §6.2 가 기여인지 분해 불가 |
| **P6** | A-FS | 1,650 | 사용자 지론이 n=1 로 남는다 |
| **P7** | A-CI(실행) | 1,650 | (P3 로 부분 대체됨) |

**[설계] 컷라인 = P4.** P0~P4 (합 **5,445콜**) 를 못 채우면 **실행하지 않는다.**
사유: P4 까지가 "front 를 탐색에 쓰는 것이 기여인가" 라는 질문에 답하는 최소 구성이고,
그 아래로는 §14.1 의 주장이 반증 가능한 형태로 서지 않는다. P5~P7 은 **있으면 분해,
없으면 미분해로 정직하게 보고**한다 — `src1` 이 ablation 없이 발표된 것과 같은 상태이며,
그 상태의 한계를 §14.5 에 쓴다.

**[설계] 컷은 아래에서 위로만 한다.** P6 을 남기고 P5 를 버리는 식의 재배열을 금지한다.
재배열이 허용되면 "돌려 보니 유리한 ablation 만 남긴" 것과 구별되지 않는다.

### 12.3 예산 산정

**[설계]** 단가는 §6.4 T2 의 산술을 그대로 쓴다: 후보 1개 = 55 units × 3 runs = **165콜**.

| 항목 | 후보 수 | 콜 | 비고 |
|---|---|---|---|
| IC-2 (CI 계산기 자기검증) | — | **0** | LLM 호출 없음 (§8.2) |
| IC-0 (기존 게이트 재실행) | 1 | **165** | `instrument_check_run.py` 3판. **이 원자료가 곧 `c000` 측정치다** — 같은 빌더·같은 라벨 시트·같은 3판이므로 `prompt_sha256` 이 일치하고, §5.2 중복 차단 규칙에 의해 c000 을 따로 재지 않는다 |
| IC-1 (precision 축 네거티브 컨트롤) | 2 (`c_neg_loose`, `c_neg_strict`) | **330** | §8.2 |
| **검침 소계** | | **495** | 세 조건이 **공유**. 조건별로 반복하지 않는다 — 검침 대상은 조건이 아니라 계측기다 |
| C2 | 10 | **1,650** | T2 상한 |
| C0 | 10 | **1,650** | 동일 예산 |
| C1 | 10 | **1,650** | 동일 예산 |
| A-CI(재분석) | 0 | **0** | C2 아카이브 재계산 |
| A-S3 | ≤10 | **≤1,650** | S3 슬롯이 비므로 라운드당 후보가 줄어 **실사용은 상한 미달이 기대된다**(미확인 — 실행 전 예측하지 않는다) |
| A-FS | ≤10 | **≤1,650** | 같음 |
| A-CI(실행) | 10 | **1,650** | 컷라인 아래 |
| **전체 상한** | | **8,745** | Phase 3 단일 실험(1,650콜)의 **5.3배** |
| **컷라인(P0~P4) 합** | | **5,445** | Phase 3 의 3.3배 |

**[설계] 조건 간 예산을 같게 두는 것이 공정성 조치다.** **[사실]** `src4` §4.1 이 text
optimizer 4종과 대조할 때 쓴 조치가 정확히 이것이다 — 동일 proposer 설정, search-set
성능만으로 후보 선택, test set 최종까지 보류, **평가 횟수 예산 동일**. **[설계]** 우리는
"라운드 수" 가 아니라 **"후보 수 10개"** 를 맞춘다. 사유: C2 는 라운드당 최대 4후보
(filter_strip + S1 + S2 + S3), C0 는 `src1` 의 `K` 값이 **[미확인]** 이라 라운드를 맞출
근거가 없다. 후보 수를 맞추면 콜 회계가 자동으로 같아진다.

**[설계] 예산 초과 시 버리는 순서는 §12.2 컷라인 표의 역순(P7 → P5)이며, P4 아래로
내려가면 실행 자체를 하지 않는다.** 중간에 예산이 마르면 **그 조건을 절반만 돌지 않는다**
— 5후보만 돌린 C1 은 10후보 C2 와 비교 불가이고, 그 비교를 하는 것이 §10.2 의 조작이다.
조건은 **완주 아니면 미실행**이다.

---

## 13. 재현 패키지

**[설계]** 논문 요건 두 번째. 목표는 "제3자가 같은 판정에 도달할 수 있는가" 이고,
LLM 호출이 끼는 순간 그것이 **부분적으로만 가능**하다는 점을 이 절에서 경계로 못 박는다.

**[사실]** 두 선행연구의 상태를 먼저 적는다 — 우리가 무엇을 더 하는지의 기준선이다.
`src4` 는 산출물 저장소(`stanford-iris-lab/meta-harness-tbench2-artifact`)를 공개하고
프로젝트 페이지를 갖는다. `src1` 은 코드·프롬프트 저장소 링크를 **논문에서 발견하지
못했다**(`src1` §9 미확인 항목). 그리고 **두 논문 모두 seed 반복·분산·신뢰구간을 보고하지
않는다**(`src1` §4, `src4` §9-5).

### 13.1 고정해야 할 것 — 값과 기록 위치

**[설계]** 아래 표의 "기록 위치" 는 전부 파일 경로다. **문서에만 적고 파일에 안 남기는
항목은 두지 않는다** — §7.2 가 밝힌 이유와 같다(검증을 문서가 아니라 코드에 둔다).

| # | 고정 항목 | 값 | 기록 위치 |
|---|---|---|---|
| F1 | 부트스트랩 seed | **`20260730`** | `mh_objectives.py` 상수 + `mh_manifest.json`(신규) + 후보마다 `mh_archive.jsonl` |
| F2 | 부트스트랩 반복 수 | **`B = 2000`** | 같음 |
| F3 | 부트스트랩 리샘플 단위 | claim·qid **둘 다 계산**, 판정은 `ci_qid` | `objectives.<axis>.ci_claim` / `.ci_qid` + `mh_front.json.ci_used` |
| F4 | CI 산출 방식 | percentile 2.5 / 97.5 (§4.3) | `mh_objectives.py` + `mh_manifest.json` |
| F5 | 부모 선택 seed (C1 전용) | **`PARENT_SEED = 20260731`** | `mh_manifest.json` + C1 후보의 `origin_reason` |
| F6 | 모델 ID | **`claude-sonnet-4-6`** (alias 금지, INV-3) | `harness.model` (후보마다) + `mh_manifest.json` |
| F7 | 라벨 파일 해시 | `phase1_human_label_sheet.xlsx` / `.json` 의 sha256 | `measurement.label_sheet_sha256` (후보마다) + `mh_manifest.json`. `mh_guard.py` 가 매 라운드 검사(INV-2) |
| F8 | 프롬프트 빌더 버전 | `phase3_build_prompts.py` 의 git commit sha + 고정 unit 1개에 대한 `prompt_sha256` | `harness.prompt_sha256` (후보마다) + `mh_manifest.json.builder_commit` |
| F9 | 후보별 프롬프트 실체 | 빌더 모듈·함수·kwargs | `harness.builder_module` / `builder_fn` / `builder_kwargs` |
| F10 | 판정 임계 전체 | R1~R5, IC recall ≥ 0.30, front 상한 8, T1=3라운드, T2=1,650콜 | `mh_front.py` 상수 + `PARETO_META_HARNESS_PREREG.md`(신규) |
| F11 | 조건 정의 | C0/C1/C2 와 ablation 조각 (§12) | `mh_manifest.json.condition` + 후보의 `origin` |
| F12 | 실행 환경 | python 버전, 설치 패키지 목록, OS | `mh_manifest.json` (`uv.lock` 이 이미 레포에 있음 **[사실]**) |

**[설계] `mh_manifest.json` (신규) — 실행 1회당 1개.** §5 의 파일 2개(원장·front)에
**세 번째**를 추가한다. 사유: F1~F12 중 일부는 후보 단위가 아니라 **실행 단위 상수**이고,
후보마다 반복 기록하면 불일치가 생길 수 있다. `mh_guard.py` 가 매 라운드 이 파일과
후보 필드의 일치를 검사한다.

**[설계]** 그리고 **git 커밋 순서 자체를 기록물로 쓴다.** 이는 새 규율이 아니다 —
`INSTRUMENT_CHECK_RESULT.md` 는 채점기가 결과 열람 **전** 커밋(`5d13ec3`)됐음을,
`PHASE3_VERDICT.md` 는 `phase3_score.py` 가 `19e0081` 로 커밋됐음을 문서 본문에
적어 두었다 **[사실]**. 같은 방식으로 `PARETO_META_HARNESS_RESULT.md` 는
`mh_front.py`·`mh_objectives.py`·`PARETO_META_HARNESS_PREREG.md` 의 커밋 해시를
본문에 싣는다(§15 의 D 항목과 대응).

### 13.2 산출물 매니페스트

**[설계]** 논문 재현에 필요한 파일과 생성 명령. `(신규)` = 아직 존재하지 않는 계획 파일.
경로 접두사는 레포 루트 기준이며, 실행 위치는 기존 관행과 같이 `gate/` 다 **[사실]**
(README 재현 절이 `cd gate` 후 `.venv/bin/python scripts/...` 를 쓴다).

| 산출물 | 생성 명령 | 논문에서 쓰이는 곳 |
|---|---|---|
| `gate/PARETO_META_HARNESS_PREREG.md` **(신규)** | 사람이 작성 → 커밋 (콜 0) | Method / 사전등록 증거 |
| `gate/scripts/mh_manifest.json` **(신규)** | `mh_guard.py --init --condition C2` | Reproducibility 절 |
| IC-2 통과 로그 | `mh_objectives.py --selftest` | Experiments §검침 |
| `gate/scripts/instrument_check_run{1,2,3}.jsonl`, `instrument_check_result.json` | `instrument_check_run.py run{1,2,3}` → `instrument_check_score.py` **(둘 다 기존 파일, 실측 확인)** | IC-0, 그리고 **`c000` 축 값** |
| `gate/scripts/mh_ic1_*.jsonl` **(신규)** | `mh_ic1_negative_control.py` | IC-1 판정 (330콜) |
| `gate/scripts/mh_archive.jsonl` **(신규)** | `mh_run_candidate.py --candidate cNNN` 누적 | 전 후보 원장 (감사) |
| `gate/scripts/mh_c<NNN>_run{1,2,3}.jsonl` **(신규)** | 같음 | 저지 원자료 (재채점용) |
| `gate/scripts/mh_front.json` **(신규)** | `mh_front.py --condition C2` | front 표 · T1~T4 정지 근거 |
| A-CI 재분석 결과 | `mh_front.py --condition C2 --ci none` | ablation A-CI (0콜) |
| 쌍 진단 4분면 | `mh_pair_diagnose.py --front mh_front.json` | §6.2 가 실제로 표적을 찾았는지 |
| `gate/PARETO_META_HARNESS_RESULT.md` **(신규)** | 사람이 작성 (실행 후) | Experiments 본문 |
| 차트 | `make_pareto_chart.py` **(기존 파일, 실측 확인)** 확장 | Figure |

**[설계] 원자료 용량 규약.** LLM 원시 출력은 커지므로, 공개 시 `*_run{1,2,3}.jsonl` 을
그대로 올릴지는 `public-repo-release` 스킬의 슬림화 규칙(원시 출력은 `.gitignore`,
"재현 스크립트로 생성 가능" 명시)에 따른다 **[사실]**. **단 판정 필드(`label`, `elapsed`,
`id`, `run`)는 반드시 남긴다** — 그것이 없으면 §4 판정이 재계산되지 않는다.

### 13.3 결정론 검증 — 경계를 먼저 그린다

**[설계]** 🔴 **이 실험은 결정론적이지 않다.** 결정론 검증을 "같은 시드로 두 번 돌려
같은 결과" 로 쓰면 거짓이 된다. 층을 나눈다.

| 층 | 결정론? | 근거 |
|---|---|---|
| **L1. 프롬프트 생성** | ✅ 결정론 | 빌더가 결정론적이라는 것은 `P4` §3 이 이미 근거로 쓴 사실이다 **[사실]** |
| **L2. LLM 판정 (저지 호출)** | ❌ **비결정론** | `PHASE1_VERDICT.md` §8: v3 저지 3판에서 5건 흔들림 **[사실]**. `IC` 는 SPLIT 0건이었지만 §4.3 이 "0이 항상 0이라는 보장은 없다" 고 이미 적었다 |
| **L3. 3판 다수결 집계** | ✅ 결정론 (L2 출력 고정 시) | `instrument_check_score.py` 의 다수결 로직 **[사실]** |
| **L4. 축 계산 + 부트스트랩 CI** | ✅ 결정론 (seed 고정) | F1·F2·F4 |
| **L5. dominance·front·솎아내기·T1~T4** | ✅ 결정론 | §4·§5.4·§6.4 가 전부 사전식·규칙 기반. crowding distance 를 기각한 것이 여기서도 이득이다(§5.4) |
| **L6. 부모 선택** | C0·C2 ✅ 결정론 / **C1 ❌ 무작위(seed 고정 시 재현 가능)** | §6.1 "결정론적 선택" / §12.1 `PARENT_SEED` |

**[설계] 검증 절차 — L3~L6 만 대상으로 한다.**

```
D-1) 원자료 고정 재계산:  같은 *_run{1,2,3}.jsonl 을 입력으로
     mh_objectives.py + mh_front.py 를 2회 실행 →
     mh_front.json 과 objectives 블록이 **바이트 단위 동일**해야 한다 (diff 로 확인).
     ⚠️ created_at / computed_at 같은 타임스탬프 필드는 비교에서 제외한다.
D-2) CI 재현:  IC-2 의 자기검증에 이미 포함돼 있다 —
     "같은 seed 로 두 번 돌려 비트 단위 동일한 CI" (§8.2 IC-2).
D-3) C1 부모 선택 재현:  PARENT_SEED 고정 하에 부모 추출 시퀀스가 동일해야 한다.
     러너를 실행하지 않고 선택기만 dry-run 으로 2회 돌려 비교한다 (콜 0).
D-4) 아카이브 → front 복원:  mh_front.json 을 지우고 mh_archive.jsonl 만으로
     재생성해 archive_sha256 이 맞는지 확인한다 (§5.1 이 요구한 성질).
```

**[설계] L2 는 검증 대상이 아니다 — 그리고 그것이 §10.2 금지 5와 충돌하지 않게 정리한다.**
"같은 후보를 다시 3판 재실행해 같은 결과가 나오는지" 를 확인하는 것은 재현성 검증으로는
자연스럽지만, 우리 규칙에서는 **재측정**이고 §10.2 금지 5(유리한 실행 채택)의 통로다.
그래서 다음과 같이 분리한다.

> **재실행 규약**: L2 재실행은 **허용**하되, 그 결과는 `gate/scripts/mh_replication/`
> **(신규 디렉터리)** 에만 기록하고 **`mh_archive.jsonl` 을 덮어쓰지 않는다.** 판정은
> 원 아카이브 값으로만 한다. 재실행 결과는 논문 Limitations 에 **판정 안정성 참고
> 수치**로 병기한다. 이 규약이 있으면 제3자의 독립 재실행도 같은 자리에 놓인다 —
> 제3자 실행은 새 실험이며 우리 판정을 덮어쓰지 않는다.

**[설계]** 즉 우리가 재현 패키지로 보장하는 것은 **"같은 원자료에서 같은 판정"** 이고,
보장하지 않는 것은 **"같은 프롬프트에서 같은 원자료"** 다. 후자를 보장한다고 쓰면
`PHASE1_VERDICT.md` §8 의 실측(5건 흔들림)과 모순된다.

### 13.4 공개 시 제거할 것

**[사실]** 회사 내부 자료·개인 식별정보는 이 프로젝트의 **데이터**에 없다 — 문항 세트는
K-IFRS 공개 기준서 문단 기반이고(README 라이선스 절), 옆방 검증 2곳은 공개 데이터셋
(SciFact CC BY-NC 2.0, KLUE-NLI CC BY-SA 4.0)이며 스크립트가 각 출처에서 직접 받는다.

**[사실]** 그러나 익명화 검사기는 레포에 **이미 존재**하고, 검사 대상이 무엇인지 확인
가능하다: `gate/scripts/anonymize_check.py`. 실측 확인한 구조는 다음과 같다.

| 검사 요소 | 내용 |
|---|---|
| 대상 확장자 | `.md .py .json .sh .yml .yaml .txt .jsonl .toml` (`EXT`) |
| 스캔 범위 | 레포 루트 `rglob("*")` **전수**. `.git` / `.venv` 제외 |
| 단어장 | `BAD` (부분 일치, 대소문자 무시) + `BAD_STRICT` (문맥 한정 정규식) = 총 26개 |
| 단어장의 성격 | 사람 식별자(계정·이름·호칭), **워크스페이스 경로 토큰**, 내부 스킬명, 메신저명, 상장사명 |
| 자기 제외 | `SELF = {anonymize_check.py, readme_parity_check.py, readme_numbers_check.py}` — 검사기 자신이 단어장을 담고 있어 제외하지 않으면 영원히 0건이 안 된다 |
| 게이트 방식 | 누출 1건 이상이면 `exit 1` → push 차단 |
| 네거티브 컨트롤 | 스킬이 요구하는 절차 — 일부러 누출 문자열을 넣어 **실제로 막히는지** 확인. 단어장을 좁힌 직후의 "0건" 은 아무것도 증명하지 않는다 |
| 알려진 함정 | 2글자 한글 회사명이 일반 용어를 오탐한다(실측: 생의학 근거의 해부학 용어가 회사명으로 걸려 push 가 막혔다) → 문맥 한정 패턴으로만 잡는다 |

**[사실] 🔴 그리고 이 설계 문서 자체가 현재 게이트를 통과하지 못한다.**
지금 상태로 검사기를 돌리면 **누출 13건 / exit 1** 이고, 13건 전부 이 파일
(`gate/PARETO_META_HARNESS_DESIGN.md`) 에서 나온다 — 근거 자료 표의 절대 경로와
본문의 사람 식별자다. 다른 파일에서는 0건이다.

**[설계]** 따라서 §12~15 를 포함한 이 문서의 **공개 전 처리 3개**를 못 박는다.

1. **경로 치환**: `src1`~`src4` 정독본과 스킬 파일의 절대 경로를 레포 상대 경로 또는
   `<workspace>/tmp/...` 형태의 플레이스홀더로 바꾼다. 정독본 자체는 레포 밖 자료이므로
   **동봉하지 않고 출처(arXiv ID)로 대체**한다 — 이미 §2 표와 참고문헌이 arXiv ID 를 갖고 있다.
2. **사람 식별자 치환**: §6.1·§6.4·§7.1 의 라벨러/최종 판정자 표기를 역할명("저자",
   "루프 밖 사람 판정자")으로 바꾼다. **치환 규칙 테이블은 레포에 넣지 않는다** —
   그 테이블 자체가 내부 식별자 전체 목록이므로 그것이 곧 누출이다(스킬 함정 2번).
3. **치환 후 재검사 + 실행 검증**: `anonymize_check.py` 로 0건을 확인하고, 경로 치환이
   코드를 깨뜨렸는지 확인한다(스킬 요구: `py_compile` 전수 + 대표 스크립트 1개 실행).

**[설계]** 새로 추가되는 파일(`mh_*.py`, `mh_manifest.json`, `mh_archive.jsonl`)은
**작성 시점부터 내부 경로·식별자를 넣지 않는다.** 특히 `mh_archive.jsonl` 의
`origin_reason` 은 자연어 필드이므로(§5.1) 여기서 새는 것이 가장 쉽다 — 스킬이 실측으로
기록한 대로 **"실험 중 작성한 문서는 내부용 문체 그대로라 익명화를 안 거친다"** 는
패턴이 그대로 재현될 자리다. `origin_reason` 에는 **문항 id·판정 라벨·수정 표면 이름만**
쓰고 사람·환경을 언급하지 않는다.

---

## 14. 논문 골격

**[설계]** 이 절은 "무엇을 쓸 수 있는가" 가 아니라 **"어떤 결과가 나오면 쓸 수 없는가"**
를 먼저 정한다. §14.2 가 그것이고, 그것이 §14.1 을 반증 가능하게 만든다.

### 14.1 주장 (claim) — 1문장, 반증 가능한 형태

> **C**: 노이즈를 명시적으로 처리하는 dominance 판정으로 harness 후보의 파레토 front 를
> 유지하고 **그 front 의 끝점에서 부모를 고르는 규칙**(§6)을 두면, 같은 후보 예산 아래에서
> front 를 탐색에 쓰지 않는 두 조건(C0: front 없음 / C1: front 있으나 부모 무작위)보다
> **더 나은 front 를 얻는다.**

**[설계] "더 나은 front" 를 조작적으로 정의한다** — 정의하지 않으면 반증 불가다.
front 끼리의 비교는 점 하나끼리의 비교가 아니므로, **§4.1 의 dominance 를 집합으로
확장**한다.

```
조건 X 의 최종 front 를 F_X 라 한다 (§6.4 정지 시점의 mh_front.json.front).

정의 D-dom:  F_X 가 F_Y 를 "커버한다"
  ⇔  ∀ y ∈ F_Y,  ∃ x ∈ F_X 로서  x ≻ y  또는  x 와 y 가 전 축 CI 겹침 동률
정의 D-str:  F_X 가 F_Y 를 "지배한다"
  ⇔  F_X 가 F_Y 를 커버하고,  ∃ y ∈ F_Y 를 지배하는 x ∈ F_X 가 하나 이상 존재
```

**[설계]** 즉 주장 C 의 형식은 **`F_C2` 가 `F_C0` 를 지배하고 `F_C1` 도 지배한다** 이다.
CI 겹침 동률을 커버로 세는 것은 §4.3 N2 와 방향을 맞춘 것이다 — 55건 표본에서 눈금이
굵으므로(recall 최소 눈금 9.1%p) 미세 우세를 우세로 세면 노이즈를 성과로 선언하게 된다.

**[설계] hypervolume 을 쓰지 않는다.** front 비교의 표준 지표지만 §10.2 금지 3에 걸린다
(스칼라화). 그리고 hypervolume 은 reference point 선택에 따라 순서가 바뀌는데, 그 선택이
곧 사후 선택의 통로다. **집합 dominance 는 순서 정보를 덜 주지만 임의 파라미터가 없다.**

### 14.2 지지 / 반증 판정 기준 (실행 전 고정)

**[설계]** 표로 못 박는다. 왼쪽 칼럼의 사건이 관측되면 오른쪽 결론을 **그대로 쓴다.**

| # | 관측 | 결론 |
|---|---|---|
| **V1** | `F_C2` 가 `F_C0` 와 `F_C1` 을 **둘 다 지배** | 주장 C **지지**. 단 §14.5 의 범위 제한 병기 |
| **V2** | `F_C2` 가 하나만 지배 | **부분 지지.** 지배하지 못한 쪽이 무엇인지에 따라 서술이 갈린다 — C0 만 지배 = "front 유지가 기여, 부모 규칙은 미분해". C1 만 지배 = "부모 규칙이 기여, front 유지 자체는 미분해" |
| **V3** | 세 front 가 서로 **커버만 하고 지배 없음** (= 전부 비지배 동률) | 🔴 **주장 C 기각 — "우리 기여가 없다".** 이 표본·이 예산에서 §6 규칙은 front 를 개선하지 않았다 |
| **V4** | `F_C0` 또는 `F_C1` 이 `F_C2` 를 지배 | 🔴 **주장 C 반증.** front 를 탐색에 쓰는 것이 **해로웠다.** 이 결과를 그대로 보고한다 — README 가 이미 P1 폐기 판정을 1면에 실은 것과 같은 처리 **[사실]** |
| **V5** | 어느 조건이든 T4 정지 (front 절반 이상이 전 축 CI 겹침 동률, §6.4) | **판정 불가.** 표본 부족이 원인이고, 축을 늘리거나 claim CI 로 갈아타지 않는다(§10.2 금지 4) |
| **V6** | IC-1 FAIL (precision 축이 과검출을 CI 비겹침으로 벌하지 못함) | **탐색 시작 전 중단.** 논문은 "축 설계 실패" 를 보고하고 495콜 이내에서 종결 |
| **V7** | 모든 조건에서 front 크기 1 유지 (baseline 이 전 후보 지배) | **판정: 이 탐색 공간에 baseline 을 지배하는 변이가 없다.** §10.3 이 이미 예고한 경로이며 그 자체로 보고 가치가 있다 |

**[설계] 🔴 "우리 기여가 없다" 로 결론내는 조건은 V3·V4 다.** 이 두 칸이 이 절의 존재
이유다. V3/V4 가 나왔을 때 다음을 **하지 않는다**:

- 축을 하나 더 세어 C2 가 이기는 조합을 찾는 것 (§10.2 금지 1)
- 예산을 늘려 C2 만 더 돌리는 것 (조건 간 예산 대칭 파괴 — §12.3)
- ablation 결과 중 유리한 것만 본문에 올리는 것 (§12.2 컷 재배열 금지)
- front 집합 비교를 point-wise 최댓값 비교로 바꾸는 것 (= 단일 축 argmax 로의 회귀,
  `src4` §6 이 실제로 한 것이고 §6.4 가 하지 않겠다고 선언한 것)

**[설계] 보조 관측 — 판정에는 쓰지 않고 보고한다.** front 진입 후보의 `origin` 분포
(S1/S2/S3/filter_strip 별 front 진입 건수)와 정지 사유(T1~T4). 이것을 **KPI 로 삼는 것은
§10.2 금지 6** 이므로, 서술은 "몇 건이 들어왔다" 까지이고 "많을수록 좋다" 로 쓰지 않는다.

### 14.3 절 구성과 우리 자산 매핑

**[설계]** 왼쪽이 논문 절, 오른쪽이 이 레포의 **이미 존재하는** 자산(실측 확인) 또는
`(신규)` 계획물이다.

| 논문 절 | 우리 자산 |
|---|---|
| **Abstract** | 주장 C(§14.1) + 판정 결과 1문장. **부정 결과여도 그대로 싣는다** |
| **1. Introduction** | §1.1(문헌이 말하는 단일 지표 실패 구조) + §1.2(우리 실패 3건: `PHASE1_VERDICT.md` / `PHASE2_VERDICT.md` / `PHASE3_VERDICT.md`) + §1.3(P1 명제). 도입의 훅은 **"1,650콜을 태우고 검정 불가였다"** 는 실측이다 |
| **2. Related Work** | §2 의 4열 대조표(Pareto 언급 / 판정식 / 아카이브 / 탐색 활용). §14.4 가 이 표를 어떻게 쓰는지 정한다 |
| **3. Method** | §3(축 2개와 전수 기각 사유) · §4(dominance 판정식 + 노이즈 규칙 N1~N3 + R1~R5) · §5(아카이브 스키마·제거·솎아내기) · §6(S1/S2/S3 + filter_strip + T1~T4) · §7(루프 경계 + INV-1~6) |
| **4. Experimental Setup** | §12(C0/C1/C2 + ablation + 예산) · §8(검침 게이트 IC-0/1/2) · §13(재현 패키지) · 라벨 55건과 `LABELING_PROTOCOL.md` **(기존 파일)** |
| **5. Experiments** | `PARETO_META_HARNESS_RESULT.md` **(신규)** — front 표, 집합 dominance 판정(§14.1 D-dom/D-str), ablation 분해, 정지 사유. Figure: `make_pareto_chart.py` **(기존 파일)** 확장 |
| **6. Limitations** | §11.1(정독본 미확인 13항목이 이 설계에 준 영향) + §11.2(설계 자체의 한계 10항목) + §14.5 |
| **Appendix** | 부록 A(두 논문에 대해 주장하는 것/하지 않는 것) · 부록 B(리뷰어 지적과 답변) · §13.2 매니페스트 · `mh_archive.jsonl` 전문 |

**[설계] 이 논문에는 "성능이 올랐다" 절이 없다.** 결과변수가 harness 성능이 아니라
**front 의 질**이기 때문이다. 이 선택의 근거는 `P4` §4 가 이미 적었다 **[사실]**:
"Phase 4의 주장이 '우리 하네스가 더 좋다'라면, 그건 탐색을 많이 돌린 쪽이 이기는 자명한
결과다. 그러므로 결과변수를 게이트로 옮긴다."

### 14.4 관련연구 — 정확히 무엇을 다르게 하는가 (각 1문장)

**[설계]** §2 표를 **재수록하지 않고 참조**한다. 아래는 그 표의 각 행에서 우리가 하는
"다른 한 가지" 만 뽑은 것이다.

- **Self-Harness** (`src1`, §2 표 1행): 같은 비지배 부등식을 쓰지만, 그쪽은 **활성 harness
  1개에 대한 진입 필터**로 쓰고 우리는 **아카이브 전체의 비지배 집합을 상태로 유지**해
  다음 부모의 출처로 쓴다 — 그리고 그쪽에 없는 **CI 기반 동률 처리**(§4.3)를 넣는다.
- **Meta-Harness** (`src4`, §2 표 2행): 같은 front 를 갖지만, 그쪽은 판정식·갱신·제거·부모
  선택을 전부 명세하지 않았고(`"imposes no parent-selection rule"`) 우리는 그 네 자리를
  **명세**한다 — 다만 그쪽 판정식이 미기재이므로 **"개선했다" 가 아니라 "명세되지 않은 것을
  명세했다" 까지만 주장**한다(부록 A 와 동일).
- **GEPA** (`src2`, §2 표 3행): front 를 부모 샘플링에 쓴다고 **2차 출처로 보고**되지만
  우리는 원문을 읽지 않았고, 무엇보다 그쪽은 **프롬프트 계층(L0)** 이고 우리는 **harness/
  판정기 지시문 계층**이다 — 그래서 "GEPA 와 같다/다르다" 는 주장을 하지 않는다(§11.1).

**[설계] Related Work 에 반드시 넣을 한 문장.** **[사실]** `src4` §11-5 3번의 관찰 —
**"front 유지의 순효과는 두 논문 어느 쪽에서도 통제 실험되지 않았다"**(Meta-Harness 에는
front 없는 ablation 이 없고, Self-Harness 에는 front 확장이 없다). **[설계]** §12 의
C0/C1/C2 가 정확히 그 통제 실험이며, 이것이 이 논문의 위치다.

### 14.5 정직하게 밝혀야 할 것

**[설계]** §11.2 와 중복되는 항목은 반복하지 않고, **주장 범위를 어떻게 제한하는지**만
쓴다. 이 4개는 Limitations 가 아니라 **Abstract 와 결론에도 조건절로 들어간다.**

| 한계 | 실측/사실 | 주장 범위에 주는 제한 |
|---|---|---|
| **단일 도메인** (K-IFRS 회계 QA) | 옆방 2곳 PASS 는 **계기 검침 절차**의 이식성 증거이며 파레토 탐색의 이식성 증거가 아니다(§11.2-6) **[사실]** | "이 절차가 도메인 일반적이다" 를 주장하지 않는다. 주장은 **"이 조건에서 front 를 탐색에 쓴 것이 열등/우등 이동이었다"** 로 한정된다 |
| **단일 라벨러 1인** | `PHASE1_VERDICT.md` §8 · `PHASE2_VERDICT.md` §8 이 inter-rater 신뢰도 미측정을 미해결로 이미 고지 **[사실]** | 두 축이 **같은 라벨에서 나오므로 라벨 오류가 두 축에 동시에 전파**된다(§11.2-2). 따라서 front 의 **절대 좌표를 성능 예측치로 쓸 수 없다.** 조건 간 비교는 같은 라벨을 쓰므로 상대 순서는 유효할 수 있다 — 이것이 우리가 방어할 수 있는 최대치다 |
| **표본 55건** | 문제건 11건 → recall 최소 눈금 **1/11 = 9.1%p**(§4.3) **[사실]**. 그리고 55건은 편향 추출이다 — Phase 1 기저율 18.5% vs 무작위 추출 3.3%(§11.2-3) **[사실]** | 미세 개선을 **관측할 수 없다.** 9.1%p 미만의 효과는 존재해도 잡히지 않으므로, V3(동률) 결과를 "효과가 없다" 로 읽으면 안 되고 **"이 해상도에서 구별되지 않는다"** 로 써야 한다 |
| **held-out 부재** | 성능축이 라벨 55건 전량에 묶여 있고, §6.2 쌍 진단이 라벨과의 일치/불일치를 보므로 **선택 신호가 반복 사용된다**(§11.2-1) **[사실]** | front 수치를 **일반화 성능으로 제시할 수 없다.** 다만 이 문제는 선행연구도 갖는다 — `src1` 은 held-out 을 15~20 라운드 동안 selection 신호로 반복 사용했고, `src4` §4.3(TB2)은 search/test 를 아예 분리하지 않았다 **[사실]**. **우리가 그들보다 나은 점은 없고, 다른 점은 이 사실을 결과 문서 첫 줄에 쓴다는 것뿐이다**(§11.2-1 그대로) |

**[설계] 이 4개가 겹치면 주장은 다음 형태로만 성립한다.**

> "K-IFRS 회계 QA 의 라벨 55건(라벨러 1인, held-out 없음, recall 해상도 9.1%p) 위에서,
> 후보 예산 10개를 동일하게 준 조건 비교에서, front 를 탐색에 쓴 조건의 최종 front 가
> 쓰지 않은 두 조건의 front 를 (지배했다 / 지배하지 못했다 / 지배당했다)."

**[설계]** 이보다 넓은 문장을 Abstract 에 쓰면 그것이 과대주장이다. 그리고 이 범위
한정은 README 가 P1 판정에 이미 적용한 것과 같은 형식이다 **[사실]** — "'P1 폐기' 판정의
유효 범위도 이 실측 조건(K-IFRS + 강한 모델 + 근거 동봉)에 한정된다."

---

## 15. 실행 순서와 확정 시점 (사전등록)

**[설계]** §10.1 의 D0~D11 을 §12~14 항목까지 포함하도록 확장한다. 기존 D0~D11 은
**번호와 내용을 바꾸지 않는다** — 이미 확정된 항목의 번호를 흔들면 사전등록 이력이
추적 불가가 된다. 새 항목은 **D12~D18** 로 뒤에 붙이고, §12~14 를 반영한 **실행 순서표**를
따로 둔다.

### 15.1 추가 확정 항목 (D12~D18)

| 단계 | 무엇을 확정 | 언제 | 확정 후 변경 가능? |
|---|---|---|---|
| **D12** | 조건 정의 C0/C1/C2 와 각 조건이 공유하는 것 (§12.1), `PARENT_SEED = 20260731` | **지금 — 이 문서 §12.1** | ❌ |
| **D13** | C0 의 수락규칙 번역 1:1 표 (`Δ_recall ≥ 0 ∧ Δ_precision ≥ 0 ∧ max > 0`, CI 미사용, merge 미실시) | **지금 — 이 문서 §12.1** | ❌ |
| **D14** | ablation 3종(A-S3 / A-FS / A-CI)과 **각각의 반증 형태** | **지금 — 이 문서 §12.2** | ❌ |
| **D15** | 우선순위 P0~P7, **컷라인 = P4**, 컷은 아래에서 위로만 | **지금 — 이 문서 §12.2** | ❌ |
| **D16** | 조건별 예산 = 후보 10개 = 1,650콜, 검침 495콜 공유, 전체 상한 8,745콜 | **지금 — 이 문서 §12.3** | ❌ |
| **D17** | 주장 C 와 집합 dominance 정의(D-dom / D-str), hypervolume 미사용 | **지금 — 이 문서 §14.1** | ❌ |
| **D18** | **판정표 V1~V7** — 특히 "우리 기여가 없다"로 결론내는 V3·V4 | **지금 — 이 문서 §14.2** | ❌ |

**[설계]** D12~D18 이 **이 문서에 전부 들어 있다는 것이 §10.1 과 같은 요점이다.**
조건도 ablation 도 판정표도 결과를 하나도 보지 않은 시점에 박혀 있다.

### 15.2 실행 순서표

**[설계]** 왼쪽에서 오른쪽으로만 진행한다. 각 단계의 산출물이 다음 단계의 입력이다.
`R` = 실행(콜 소모), `F` = 확정(freeze), `W` = 문서 작성.

| # | 종류 | 할 일 | 콜 | 전제 |
|---|---|---|---|---|
| 1 | **F/W** | `PARETO_META_HARNESS_PREREG.md` **(신규)** 커밋 — 이 문서에서 판정 기준만 발췌(축·판정식·R1~R5·T1~T4·조건 정의·V1~V7·예산·컷라인) | 0 | D0~D18 |
| 2 | **W** | `mh_objectives.py` **(신규)** 작성 + `--selftest`(IC-2) 통과 | 0 | 1 |
| 3 | **F** | `mh_front.py` · `mh_guard.py` **(신규)** 커밋 — **러너보다 먼저**(INV-5) | 0 | 2 |
| 4 | **R** | 결정론 검증 D-2·D-3 (합성 입력·dry-run) | 0 | 3 |
| 5 | **W** | `mh_run_candidate.py` **(신규)** + `mh_manifest.json --init` | 0 | 3 |
| 6 | **R** | **IC-0** 재실행 → `verdict == "PASS"` 확인 | 165 | 5 |
| 7 | **F** | `c000` 축 값 확정 — **IC-0 원자료 재사용, 추가 측정 없음**(§12.3) | 0 | 6 |
| 8 | **R** | **IC-1** (`c_neg_loose` / `c_neg_strict`) → precision 축 판별력 판정 | 330 | 7 |
| 9 | **F** | IC-1 FAIL 이면 **V6 로 종결**. PASS 면 아래로 | 0 | 8 |
| 10 | **W** | `mh_pair_diagnose.py` · `mh_filter_candidates.py` · `mh_propose.md` **(신규)** 커밋 | 0 | 9 |
| 11 | **R** | **C2 완주** (라운드당 filter_strip → S1 → S2 → S3, 후보 10개 상한, T1~T4 검사) | ≤1,650 | 10 |
| 12 | **R** | **C0 완주** (Self-Harness 수락규칙, 활성 harness 1개, 후보 10개) | ≤1,650 | 10 |
| 13 | **R** | **C1 완주** (front + 무작위 부모, `PARENT_SEED`, 후보 10개) | ≤1,650 | 10 |
| 14 | **R** | **A-CI(재분석)** — `mh_front.py --ci none` 을 C2 아카이브에 적용 | 0 | 11 |
| 15 | **R** | A-S3 · A-FS (예산 남으면. 컷라인 아래) | ≤3,300 | 11 |
| 16 | **R** | 결정론 검증 D-1·D-4 (원자료 고정 재계산, 아카이브→front 복원) | 0 | 11~15 |
| 17 | **F** | 집합 dominance 판정(D-dom / D-str) → **V1~V7 중 하나 자동 선택** | 0 | 16 |
| 18 | **W** | `PARETO_META_HARNESS_RESULT.md` **(신규)** — 커밋 해시 병기, 한계 4개 병기 | 0 | 17 |
| 19 | **W** | 공개 전 처리: 경로·식별자 치환 → `anonymize_check.py` 0건 → `py_compile` 전수 (§13.4) | 0 | 18 |

**[설계] 11 → 12 → 13 의 순서가 중요하다.** C2 를 먼저 돌린다. 사유: C2 가 T3(유효 후보
0)이나 T4(표본 부족)로 조기 정지하면 **C0·C1 을 돌릴 이유가 없어질 수 있다** — V5 로
판정 불가가 확정되기 때문이다. 반대 순서로 하면 대조군에 3,300콜을 쓴 뒤에 그것을 알게 된다.
이것은 §8.3 이 검침을 먼저 두는 것과 같은 논리다(**가장 싸게 판정 불가를 알아내는 순서**).

**[설계] 그런데 이 순서에는 위험이 있고, 그것을 명시한다.** C2 를 먼저 보면 C0·C1 실행
시점에 저자가 C2 결과를 **이미 알고 있다.** C0·C1 은 부모 선택이 규칙(C0) 또는 고정
seed(C1)로 결정되므로 저자 재량이 개입할 지점은 **변이 내용 생성**뿐이지만, 그 지점이
0이 아니다. 완화 수단 2개:

1. **변이 표면 제약을 조건 간에 동일하게 고정한다** — 수정 가능 표면 목록은
   `mh_propose.md`(단계 10, C2 실행 **전** 커밋)에 있고 조건별로 다르지 않다.
2. **C0·C1 의 각 후보 `origin_reason` 을 측정 전에 커밋한다** — 측정 결과를 보고 사유를
   고쳐 쓰는 것을 차단한다. 이는 §5.1 이 `origin_reason` 을 필수 필드로 둔 이유의 연장이다.

**[설계]** 완화해도 **완전히 봉쇄되지 않는다.** 이것은 §11.2-7(proposer 재량 위험)과 같은
성질의 미해결 사항이며, 부록 B-5 에 **미해결**로 적는다.

### 15.3 🔴 결과를 본 뒤에 바꾸면 안 되는 항목 (단일 목록)

**[설계]** §10.2 금지 9개는 그대로 유효하다. 여기서는 **§12~14 가 추가한 것**만 모아
한 목록으로 만든다. 아래 항목을 결과 열람 후 변경하면 **실험 무효**다.

1. **조건 정의 3개** (C0/C1/C2) 와 각 조건의 부모 선택 방식. 특히 C1 의 `PARENT_SEED`.
2. **C0 의 수락규칙** — `src1` §3.4 원문 그대로. "C0 가 너무 약하다/강하다" 는 이유로
   부등호나 CI 사용 여부를 바꾸지 않는다.
3. **조건별 후보 예산 10개.** 어느 조건도 더 받거나 덜 받지 않는다. 예산이 마르면
   **그 조건은 미실행**이고 절반 실행은 없다(§12.3).
4. **ablation 3종의 정의와 각각의 반증 형태**(§12.2 4열). "A-S3 가 이겼으니 S3 를 다르게
   정의했어야 한다" 는 사후 재정의를 금지한다.
5. **우선순위 P0~P7 과 컷라인 P4.** 컷은 아래에서 위로만. 재배열 금지.
6. **집합 dominance 정의**(D-dom / D-str). 특히 **CI 겹침 동률을 커버로 세는 규약**.
   결과가 애매하다고 점 추정 비교나 hypervolume·평균 front 값으로 갈아타지 않는다.
7. **판정표 V1~V7 의 매핑.** V3·V4 가 나왔을 때 "우리 기여가 없다"/"해로웠다" 를 그대로
   쓴다. 조건을 추가해 재판정하지 않는다.
8. **§13.1 의 고정값 F1~F12** — 특히 `B = 2000`, `seed = 20260730`, 판정 CI = `ci_qid`,
   모델 `claude-sonnet-4-6`, 라벨 시트 해시.
9. **§14.5 의 한계 4개를 Abstract·결론에 병기하는 것.** 결과가 좋게 나왔다는 이유로
   범위 한정을 빼는 것을 금지한다.
10. **실행 순서표의 1~10 단계 순서** — 특히 3(판정기 커밋)이 5(러너)보다, 6~9(검침)이
    11(C2)보다 앞이라는 순서.

**[설계]** 반대로 **결과를 본 뒤에 바꿔도 되는 것**도 명시한다. 목록이 한쪽만 있으면
모든 수정이 위반처럼 보여서 실무가 멈춘다.

- 버그 수정: 판정기·러너의 명백한 오류. **단 커밋 이력에 남기고 사유를 결과 문서에 적고,
  수정 후 영향받는 후보를 전부 재계산**한다(재측정이 아니라 재계산 — L4~L5 층은 결정론).
- 서술·표 배치·차트 스타일.
- §3.5 참고 필드의 **보고 여부**(축 승격은 금지, 표에 싣는 것은 자유).
- 다음 실행을 위한 새 사전 선언 작성. **이번 실행의 판정에는 소급 적용하지 않는다.**

---

## 부록 B — 리뷰어가 찌를 지점과 우리 답변

**[설계]** 7개. 각 항목은 (지적 / 답변 / 근거 파일) 구조다. 답할 수 없는 것은
**미해결**로 적는다 — 방어하지 않는 것이 방어보다 낫다.

### B-1. "P4 사전등록의 3축을 왜 개정했나 — 사후 선택 아닌가"

**지적**: `PHASE4_PREREGISTRATION.md` §3 은 3축(성능 / 프롬프트 문자수 / `elapsed`)을
"측정 전 고정" 으로 선언했다. 이 설계는 2축(recall / precision)으로 바꿨다. 사전등록을
사후에 고친 것이면 나머지 사전등록도 신뢰할 수 없다.

**답변**: 세 갈래로 답한다.

1. **P4 는 DRAFT 이고 baseline 칸이 비어 있다.** 문서 상단이 "상태: 초안(DRAFT)" 이고,
   §3 의 baseline 3칸이 `____` 로 비어 있다 **[사실]** — 즉 P4 §3 은 **한 번도 측정에
   적용된 적이 없는 선언**이다. 적용된 선언을 결과에 맞춰 고친 것이 아니다.
2. **개정 시점이 변이 생성 전이다.** 이 문서 §3.1 이 그것을 명시했고, 파레토 탐색의
   후보는 아직 0개다(§11.2-10). 반면 P4 §6 이 금지한 것은 **"결과를 보고" 목적 벡터를
   바꾸는 것**이다 — 볼 결과가 존재하지 않는다.
3. **바뀐 방향이 사후 선택의 방향과 반대다.** 사후 선택은 통상 **유리한 축을 추가**한다.
   우리는 **축을 3개에서 2개로 줄였고**, 줄인 근거가 실측이다: `elapsed` 중앙값이
   조건 A/B 모두 **4.60s 로 동일**해 P4 §7 의 동률 임계 ±20% 안에 들었고
   (`PHASE3_VERDICT.md` §7) **[사실]**, 프롬프트 문자수는 변인 그 자체의 대리변수여서
   성능축과 상관된다(§3.4 A5). **판정에 기여하지 않는 축을 뺀 것**이며, 축이 줄면
   front 가 좁아져 우리에게 불리하다(§3.6).

**그리고 정직하게 남는 부분**: recall/precision 이라는 **새 축을 넣은 것**은 축 제거가
아니라 축 교체다. 이것을 "감축" 으로만 서술하면 부정확하다. 방어 근거는 새 축이
**이미 구현된 함수의 정의를 글자 단위로 그대로 쓴다**는 점이다(§3.3, `instrument_check_score.py`)
— 새 계측기를 만들어 유리한 정의를 고를 여지가 없다.

**근거 파일**: `gate/PHASE4_PREREGISTRATION.md`(§3 DRAFT·빈 baseline·§6·§7) ·
`gate/PHASE3_VERDICT.md`(§7 elapsed 4.60s/4.60s) ·
`gate/scripts/instrument_check_score.py`(recall/precision 정의) · 이 문서 §3.1·§3.4.

### B-2. "표본 55건으로 다목적 주장이 되나"

**지적**: 문제건 11건이면 recall 의 최소 눈금이 9.1%p 다. 그 해상도로 front 의
형태를 논하는 것은 과잉이다.

**답변**: **눈금이 굵다는 것을 우리가 먼저 계산해 설계에 반영했다.** 세 곳에서 그렇다.

1. **CI 를 판정 연산자 안에 넣었다**(§4.3 N2). 그래서 9.1%p 미만의 차이는 **구조적으로
   동률로 처리**된다 — 미세 차이를 우세로 세지 않는다.
2. **보수적인 CI 를 쓴다.** claim CI 와 qid 클러스터 CI 를 둘 다 계산하고 **넓은 쪽(qid)**
   으로 판정한다(§4.3). 이는 "실제 개선을 놓치는" 오류를 늘리고 "우연을 채택하는" 오류를
   줄이는 방향이다.
3. **crowding distance 를 기각한 사유가 바로 이 눈금이다**(§5.4) — 굵은 격자 위에서
   "밀집" 은 정의되지 않는다.

**그리고 이 지적이 옳은 지점을 인정한다.** 55건으로는 **미세 개선을 관측할 수 없다.**
그래서 §14.2 는 V3(전 조건 동률)을 "효과 없음" 이 아니라 **"이 해상도에서 구별되지 않음"**
으로 쓰도록 미리 못 박았고, V5(T4 정지)를 **판정 불가**로 처리한다. **표본을 늘려
판정하는 경로는 이미 한 번 파레토 열등으로 판정됐다** — Phase 2 는 후보 풀 201건을 전량
라벨해도 기대 문제 사례가 6.7건으로 목표 55건에 미달해 **171건을 라벨하지 않고 종결**했다
(`PHASE2_VERDICT.md`) **[사실]**.

**미해결**: 그러므로 "표본을 늘리면 된다" 는 처방을 우리는 실행할 수 없다. 이 한계는
해소되지 않고 남으며, §14.5 가 이를 주장 범위 조건절로 싣는다.

**근거 파일**: 이 문서 §4.3·§5.4·§14.2·§14.5 · `gate/PHASE2_VERDICT.md` ·
`gate/PHASE1_VERDICT.md`(§4 Wilson 구간 겹침).

### B-3. "라벨러 1인이면 ground truth 가 아니지 않나"

**지적**: 축 2개가 모두 한 사람의 라벨에서 나온다. 그것은 정답지가 아니라 한 사람의 의견이다.

**답변**: **부분적으로 인정한다.** 다만 두 가지를 구분해야 한다.

1. **이 실험이 라벨을 쓰는 방식은 "절대 성능 측정" 이 아니라 "조건 간 비교" 다.**
   세 조건이 **동일한 라벨 시트**를 쓰고(INV-2 가 해시로 강제), 라벨 오류는 세 조건에
   **같은 방향으로** 전파된다. 따라서 라벨 오류가 조건 순서를 뒤집으려면 **조건별로 다르게
   작용해야** 하는데, 조건은 라벨을 바꾸지 않으므로 그 경로가 없다.
2. **외부 라벨러 조건에서 이미 한 번 검증됐다.** 옆방 검증 2곳은 라벨러가 **외부**
   (SciFact 22건, KLUE-NLI 22건)였고 recall 100% / SPLIT 0 으로 **둘 다 PASS** 였다
   (`SIDECHECK_RESULT.md`) **[사실]**. "저자가 라벨하고 저자가 만든 판정기를 검침했으니
   기준이 정렬됐을 것" 이라는 설명은 그 실측에서 지지되지 않았다.

**그러나 위 2는 이 실험을 구제하지 못한다.** 옆방 검증이 검증한 것은 **계기 검침 절차**
이고, 여기서 라벨이 쓰이는 자리는 **목적 축 2개**다. 그리고 inter-rater 신뢰도는
**측정되지 않았다** — `PHASE1_VERDICT.md` §8 과 `PHASE2_VERDICT.md` §8 이 이미 미해결로
고지한 항목이다 **[사실]**.

**미해결**: 2인 이상 라벨과 κ 계수는 이 설계에 없다. 추가하려면 라벨 프로토콜을 새로
사전 선언해야 하고(§10.2 금지 8: 라벨 시트 수정 금지 — 재라벨은 **처음부터 다시**),
그것은 이 실험의 범위가 아니다. **따라서 우리는 "ground truth" 라는 단어를 쓰지 않고
"라벨 55건" 이라고만 쓴다.** `IC` §3 의 표현("정답지")도 검침 문맥의 조작적 정의였음을
결과 문서에 병기한다.

**근거 파일**: `gate/PHASE1_VERDICT.md` §8 · `gate/PHASE2_VERDICT.md` §8 ·
`gate/SIDECHECK_RESULT.md` · `gate/LABELING_PROTOCOL.md` · 이 문서 §7.1(INV-2)·§11.2-2.

### B-4. "C0 가 Self-Harness 의 공정한 재현인가"

**지적**: C0 를 Self-Harness 라고 부르면서 실제로는 약화시킨 것 아닌가. 약한 baseline 을
세워 이기는 것은 기여가 아니다.

**답변**: **완전한 재현이 아니라는 것을 먼저 인정하고, 어긋난 지점을 전수로 공개한다.**
§12.1 의 1:1 번역표가 그것이고, 어긋난 곳은 **4개**다.

| 어긋난 지점 | C0 가 다르게 한 것 | 방향 (C0 에 유리? 불리?) |
|---|---|---|
| 축의 성격 | `src1` 은 **같은 지표(pass count)를 두 split 에서** 재고, C0 는 **서로 다른 두 지표**를 잰다 (`src4` §11-2 표가 이 차이를 지목) **[사실]** | **판정 불가** — 유불리를 말할 근거가 없다. 이것이 가장 큰 어긋남이다 |
| `Δ` 의 단위 | `src1` 은 통과 **개수** 차, C0 의 precision 은 **비율** 차 (분모가 후보마다 변하므로) | 판정 불가 |
| merge | `src1` 은 호환 후보를 merge, C0 는 **하지 않는다** | **C0 에 불리.** merge 는 한 라운드에 여러 개선을 합치는 장치이므로, 없으면 C0 가 덜 빠르게 오른다 |
| held-in/held-out 분할 | `src1` 은 2 split, C0 는 **단일 55건** | **C0 에 유리한 쪽으로 보인다** — 게이트를 두 번 통과할 필요가 없으므로 수락이 쉽다. 단 확정적이지 않다 |

**[설계] merge 를 빼면 C0 가 불리해진다는 것을 인지하고도 뺀 이유**: `src1` §9 가
**merge 후 재검증·롤백 규칙을 미기재로 남겼다** **[사실]**. 명세되지 않은 절차를 우리가
추측해 구현하면, C0 의 성능은 우리 추측의 성능이 되고 그것을 "Self-Harness" 라고 부르는
것이 더 큰 왜곡이다. **없는 것을 지어내지 않는 쪽**을 택했다(§11.1 의 일관된 처리).

**그리고 우리가 C0 에 유리하게 준 것들**: C0 는 **아카이브·원자료 보존·R1~R5·검침
게이트·3판 다수결·fail-closed 를 전부 공유**한다(§12.1 공유표). 즉 C0 는 `src1` 원문보다
**측정 규율이 강한 조건**이다 — `src1` 은 CI·유의성·seed 반복을 보고하지 않았다 **[사실]**.
후보 예산도 동일하게 10개다(`src4` §4.1 의 "평가 횟수 예산 동일" 조치와 같은 형식).

**미해결**: 그럼에도 **"C0 가 Self-Harness 의 성능 상한을 대표하는가" 는 답할 수 없다.**
`src1` 의 `K`(제안 폭)·`T`(라운드 수)가 **[미확인]** 이므로 우리 예산이 그쪽보다 큰지
작은지 판단할 근거조차 없다(§11.1). 따라서 논문에서 C0 를 **"Self-Harness"** 로 부르지
않고 **"Self-Harness 수락규칙을 우리 환경에 이식한 조건"** 으로 표기한다. 이 표기 규약을
§12.1 과 §14.4 에 맞춘다.

**근거 파일**: `src1` §3.4·§4·§9 (정독본) · `src4` §11-2·§4.1 (정독본) · 이 문서 §12.1·§11.1.

### B-5. "C1 이 Meta-Harness 의 공정한 재현인가 — 무작위가 에이전트 재량과 같나"

**지적**: `src4` 의 `"imposes no parent-selection rule"` 은 **강한 코딩 에이전트의 재량**을
뜻한다. 균등 무작위로 대체하면 그것은 Meta-Harness 가 아니라 무작위 탐색이다.

**답변**: **인정한다. C1 은 "규칙 없음" 의 하한이다.** §12.1 이 이미 그렇게 적었다.
그리고 `src4` 자신이 재량의 위력을 실증한다 — Appendix A.2 에서 proposer 는 회귀한
후보 1·2를 동시에 참조해 공통 요인을 confound 로 특정했고, `src4` §11-3 (1)은 그 추론이
front 아카이브 없이는 **원리적으로 불가능**하다고 적었다 **[사실]**. 즉 재량은 무작위보다
나쁠 이유가 없다.

**그래서 우리가 주장을 좁힌다**: C2 > C1 이 나와도 **"우리 규칙이 에이전트 재량보다
낫다" 를 주장하지 않는다.** 주장은 **"front 를 갖는 것만으로는 부족하고, 그것을 부모
선택에 쓰는 절차가 필요하다"** 까지다 — 즉 C1 은 "front 존재" 를 통제하는 항이고
"재량" 을 대표하는 항이 아니다.

**재량 조건을 세우지 않은 이유**는 §6 서두와 같다: **재량은 사전등록될 수 없다.**
부모 선택이 에이전트 재량이면 그 선택은 결과를 본 뒤에 설명되고, 그것이 사후 선택이다.
`src4` §9-2 7번이 같은 위험을 실측으로 보고한다 — **skill 텍스트 반복 수정이 iteration
수·population 크기보다 결과에 더 큰 영향을 줬다** **[사실]**.

**미해결 2개**:
- **C1 은 무작위이므로 단일 실행이 한 번의 추출이다.** 분산을 재려면 seed 를 여러 개
  두고 반복해야 하고, 그것은 예산 밖이다(seed 3개면 +3,300콜). 따라서 **C1 대비 우세는
  운의 기여를 분리하지 못한다.** 이것이 이 실험에서 가장 약한 고리다.
- **§15.2 의 실행 순서(C2 먼저)가 저자에게 C2 결과를 먼저 보여준다.** 변이 내용 생성
  지점에 재량이 0이 아니므로, 완화 수단 2개(표면 제약 사전 고정, `origin_reason` 측정 전
  커밋)에도 봉쇄되지 않는다. §11.2-7 과 같은 성질의 미해결이다.

**근거 파일**: `src4` §3·§11-3·§9-2 (정독본) · 이 문서 §6 서두·§12.1·§15.2·§11.2-7.

### B-6. "front 를 탐색에 쓴다는 기여가 GEPA 에 이미 있는 것 아닌가"

**지적**: GEPA(Genetic-**Pareto**)는 front 기반 부모 샘플링을 한다고 알려져 있다.
그렇다면 §6 은 새롭지 않다.

**답변**: **우리는 이 지적에 실질적으로 답할 수 없고, 그래서 주장을 그 방향으로 하지 않는다.**

- **원문을 읽지 않았다.** §2 표의 GEPA 행은 2차 출처(`src2` 의 목록 1줄) 기반이고,
  `src4` Appendix E 의 GEPA 대조는 **피드백 풍부함 축만** 다루며 **Pareto 부모 샘플링을
  언급조차 하지 않는다** **[사실]**. §11.1 이 이 공백을 이미 미확인으로 기록했다.
- 따라서 논문에서 **"GEPA 와 다르다/같다" 를 주장하지 않는다.** 대신 확인 가능한 차이
  하나만 적는다: **계층이 다르다** — `src2` Optimization Ladder 기준 GEPA = L0
  (instruction prompts), Meta-Harness = L4(optimizer/meta-harness code) **[사실]**.
- 그리고 우리 기여 주장의 형태는 §14.4 대로 **"두 논문 어느 쪽에서도 통제 실험되지
  않은 것(front 유지의 순효과)을 통제 실험했다"** 이다(`src4` §11-5 3번) **[사실]**.
  이 주장은 GEPA 에 front 부모 샘플링이 있든 없든 **영향받지 않는다** — GEPA 는
  harness 계층에서 C0/C1/C2 대조를 하지 않았다.

**미해결**: GEPA 원문을 읽고 §2 표의 3행을 1차 출처로 채우는 것. 이 작업은 **논문 투고
전에 반드시 해야 한다.** 하지 않은 상태로 Related Work 를 쓰면 그것이 가장 먼저
지적받을 자리다.

**근거 파일**: `src2`(정독본, Optimization Ladder) · `src4` Appendix E·§11-5 (정독본) ·
이 문서 §2·§11.1·§14.4.

### B-7. "결과변수가 front 의 질이면, 결국 자기 지표로 자기를 평가하는 것 아닌가"

**지적**: front 를 만드는 규칙(§6)이 좋은지를 front 로 판정한다. 순환이다.

**답변**: **순환이 아니다 — 판정 기준이 루프 밖에 있다.** 구조는 §7.2 가 이미 밝힌 것과
같다: 축을 재는 기준은 **사람 라벨 55건(루프 밖, 읽기 전용, 해시로 불변 강제)** 이고,
front 는 그 라벨에 대한 측정값의 파생물이다. §6 규칙은 **어떤 후보를 만들지**만 정하고
**그 후보의 점수를 정하지 못한다**(INV-6: proposer 는 자기 후보의 축 점수를 계산하지
않는다).

**그리고 조건 비교가 순환을 한 겹 더 끊는다.** C0/C1/C2 는 **같은 라벨·같은 채점기·같은
예산**을 쓰고 §6 규칙의 유무만 다르다. 만약 front 라는 측정 자체가 §6 에 유리하게
편향돼 있다면 그 편향은 C1 에도 동일하게 작용한다(C1 도 front 를 계산한다) — 즉
**C2 vs C1 비교는 "front 라는 측정 도구" 를 상수로 놓는다.**

**남는 취약점 2개는 인정한다.**
- **C0 는 front 를 계산하지 않으므로**, C0 의 최종 산출(활성 harness 1개)을 front 형태로
  비교하려면 우리가 C0 의 후보들에 front 를 **사후 계산**해야 한다. 그 계산은 C0 가
  최적화하지 않은 목표에 대한 평가다 — **불공정할 수 있다.** 완화: C0 의 front 는
  **아카이브 전체(수락·거부 모두)** 에 대해 계산한다. 거부 후보도 원장에 남기므로
  (§12.1 `REJECTED_C0`) C0 가 도달한 목적 공간을 가장 넓게 잡아 주는 방식이며,
  이는 C0 에 **유리한** 방향의 선택이다.
- **held-out 이 없다**(§11.2-1). front 의 질을 재는 라벨이 부모 선택에도 간접 노출되므로,
  front 우세가 **선택 신호 재사용의 산물**일 가능성을 배제하지 못한다. 선행연구도 같은
  문제를 갖지만(`src1` 반복 사용, `src4` §4.3 미분리) **그것이 우리 결과를 정당화하지는
  않는다.** 결과 문서 첫 줄에 이 사실을 쓴다.

**근거 파일**: 이 문서 §7.1·§7.2(INV-1~6)·§11.2-1·§12.1 · `src1` §5·`src4` §4.3 (정독본).
