# probe-graph — Reflection Probe Verification Subgraph for Citation-Grounded QA

인용 기반 QA 파이프라인(RAG 봇)에 꽂는 **검증 서브그래프** 스킬과,
그 효과를 판정한 **A/B 실측 하네스** 전체를 담은 레포입니다.

핵심이 되는 결과부터 밝힙니다: **본 레포의 메인 프로브(P1)는 자체 실측 게이트에서
폐기 판정을 받았습니다.** 이 레포의 가치는 "만능 검증 프롬프트"가 아니라,
①문헌 근거로 설계한 프로브 3종과 ②그것을 **채택하기 전에 걸러낸 판정 절차**
(사전 등록 → 블라인드 채점 → McNemar)의 재현 가능한 전 과정입니다.

![A/B 실측 판정 차트](docs/ab_verdict_chart.png)

## 왜 만들었나 (동기)

출발점은 Anthropic 인터프리터빌리티 팀의 논문이었습니다:

> **"Verbalizable Representations Form a Global Workspace in Language Models"**
> (Anthropic, 2026, transformer-circuits.pub/2026/workspace)

이 논문은 LLM 내부에 "말로 꺼낼 수 있는 표현들의 특권 집합"이 있고, **counterfactual
reflection** — "중간에 끊고 '지금 무슨 생각해?'라고 물으면 원칙을 말하도록" 학습시키면
안 끊긴 상황의 실제 행동까지 개선된다는 것을 보였습니다. 또한 모델이 내부적으로는
이의를 인지하면서 출력에 반영하지 않는 **BUT-갭**(88%)을 보고했습니다.

논문의 본체 기법(J-lens)은 residual stream 접근이 필요해 API 사용자는 쓸 수 없습니다.
그래서 "**물어보면 말할 내용이 곧 조용히 추론하는 내용**"이라는 인과 발견만을
프롬프트 레벨로 번역한 것이 이 스킬입니다: 답변 생성 후 "이 답에서 근거 못 대는
부분을 말해봐"라고 묻는 **리플렉션 프로브**를 파이프라인 노드로 꽂는 설계.

## 순진하게 만들면 해롭다 (설계 과정)

구현 전에 자기검증(self-correction) 문헌 8편을 검토했고, **순진한 프로브는
오히려 성능을 깎는다**는 반대 증거가 일관되게 나왔습니다:

| 논문 | 이 설계에 준 것 |
|---|---|
| Huang et al., *Large Language Models Cannot Self-Correct Reasoning Yet* (arXiv:2310.01798) | "오답 가정" 프롬프트가 최대 −9.5pp (CSQA). 정답→오답 전환이 오답→정답보다 항상 많음 → 앵커 A1("이미 정확할 가능성이 높다고 전제") · A5("문제 찾기가 아니라 일치 확인") |
| Dhuliawala et al., *Chain-of-Verification (CoVe)* (arXiv:2309.11495) | factored 검증(초안 산문을 검증자에게 주지 않음)으로 FACTSCORE 55.9→71.4. yes/no 검증질문은 동조 편향 → P1은 주장 리스트만 입력 + A6(원문 발췌 강제) |
| FBC/EIR 계열 (verify-first ablation) | "수정 전 독립 재확인 + 구체적 오류만 수정" 앵커로 EIR(정답→오답) 2%→0%, McNemar p<10⁻⁴. 같은 예산에서 3-iter refine(86.6) < Self-Consistency(93.4) → **revise 루프 캡=1** · A2·A3 |
| Madaan et al., *Self-Refine* (arXiv:2303.17651) | 실패 분석: 61%가 "부적절 수정" → A4("근거 없으면 표시만, 다른 내용으로 바꾸지 마라") |
| Shinn et al., *Reflexion* (arXiv:2303.11366) | 외부 신호 기반 반성의 한계 조건 |
| Manakul et al., *SelfCheckGPT* (arXiv:2303.08896) | 샘플링 기반 자기점검의 위상 — 본 설계에서는 미채택 근거 |
| Tian et al. (arXiv:2305.14975) · Xiong et al. (arXiv:2306.13063) | 단일 숫자 확신도는 과확신 집중(80~100%), top-2 verbalized가 캘리브레이션 우수 → A7(상/중/하 + 대안 후보 2개) |
| Obfuscation Atlas (FAR.AI, ICML 2026) | 프로브 지적 건수를 KPI로 삼으면 정직해지는 게 아니라 프로브를 피하는 방향으로 최적화됨 → "지적 건수 최적화 금지" 규칙 |
| Morris et al., *How Much Do Language Models Memorize?* (ICML 2026) | 파라미터당 ~3.6비트 기억 한계 → 조문 번호를 기억에서 꺼내면 틀림 → 파라메트릭 인용 금지, 인용은 RAG 원문 발췌 경유 |

이 근거들이 프로브 프롬프트의 **앵커 A1~A7**로 박제되어 있습니다
(`skill/references/probe-prompts.md` — 앵커별 출처 수치 표 포함).

### 프로브 3종

| 프로브 | 수정 권한 | 과교정 위험 | 용도 |
|---|---|---|---|
| P1 인용대조 | 간접 (revise 트리거, 캡=1) | 낮음(앵커로 억제) | 배치 답변 검증 |
| P2 verify-first | 자기 자신 | 실증 0 (FBC) | 실시간 경로 시스템 프롬프트 |
| P3 위험열거 | **없음** | **구조적 0** | 야간 감사, 사람 라우팅 |

## 실측 ① — 합성 스트레스테스트 (프로브 자체 QA)

프로브가 "심은 오류를 잡고, 정상답에 억지 지적을 안 하는지"부터 검증했습니다
(`harness/`). 정상답 5 + 오류 심은 답 5 (조문 오기·수치 변조·근거 밖 주장).

- run1: 9.5/10 — **needs_revision 논리 불일치 1건 발견**: 모델이 verdict='근거없음'을
  정확히 잡고도 needs_revision=false로 출력. → 교훈: **판정 필드는 모델을 믿지 말고
  코드에서 `any(verdict != "일치")`로 유도**할 것 (스킬에 반영됨)
- run2 (수정 후): 오류 특정 5/5, 억지 지적 0, quote 원문 실존 0실패, JSON 10/10 — 통과

## 실측 ② — A/B 게이트: 그리고 P1은 떨어졌다

**사전 등록** (`ab/ab_questions_FROZEN.json`, 고정 후 수정 금지):
K-IFRS 공개 기준서 12종 기반 119문항 = normal 84 + no_answer 17(환각 유도)
+ distractor 18(유사 문단 함정). 채점 규칙도 실험 전 고정.

**실행**: 같은 모델·같은 날, arm A(프로브 없음) vs arm B(P1+revise).
채점은 ①인용오류 기계 대조(채점기 자체를 네거티브 컨트롤 6종으로 검증) +
②arm 라벨을 숨긴 **블라인드 LLM 저지** (제시 순서도 셔플).

**결과** (전문: [`ab/AB_VERDICT.md`](ab/AB_VERDICT.md)):

| 게이트 | arm A | arm B | 판정 |
|---|---|---|---|
| 주지표: 인용오류율 | 0/119 (0%) | 0/119 (0%) | p=1.0 — 개선 여지 없음 ❌ |
| 가드레일1: 답변정확도 | 99.2% | 99.2% | 비열화 ✅ |
| 가드레일2: 과교정율 | — | **0.84% > 임계 0.5%** | ❌ |

**판정: P1 폐기.** 유일한 열화 사례(Q092)는 문헌의 EIR 메커니즘이 그대로 재현된
실물입니다 — 프로브는 규칙대로 "evidence 밖 추론"을 근거없음 판정했고, revise는
규칙대로 그 항목만 hedging으로 바꿨는데, 결과는 첫 문장과 모순되는 답이 됐습니다.
**구성 요소가 각자 옳아도 조합이 정답을 훼손할 수 있다**는 Self-Refine 실패 분석
(부적절 수정 61%)의 사례입니다.

### 교훈

1. **강한 생성 모델 + 근거 동봉 구조에서는 인용오류가 애초에 안 난다.**
   distractor 함정에서도 오인용 0건. 검증 레이어가 잡을 것이 없으면
   상방은 0이고 하방(과교정)만 남습니다 — 보험이 아니라 순비용.
2. P1 도입이 정당화되는 조건: 생성 모델이 인용오류를 실제로 내는 환경
   (더 약한 모델, 근거 미동봉, 파라메트릭 인용 의존). **먼저 baseline 오류율을
   재고, 0%면 P1을 붙이지 마세요.**
3. P3(수정 권한 없음)·P2(verify-first 앵커)는 이 판정의 영향을 받지 않습니다 —
   과교정이 구조적으로 0이거나 실증 0이기 때문.
4. 판정 게이트가 없었다면 "검증 붙였으니 더 안전하겠지"라며 순비용 레이어를
   프로덕션에 얹었을 것입니다. **이 레포에서 가장 재사용 가치가 높은 부분은
   프로브가 아니라 게이트입니다.**

## 파레토 관점 — 하네스를 꽉 잡는 것이 최적이 아니다

이 실험을 한 문장으로 옮기면 경제학의 파레토 개념이 됩니다:
**검증 강도는 공짜 다이얼이 아니라, 상충하는 두 지표(오류 적발 ↔ 과교정) 사이의
이동이다.**

- arm A는 이미 (인용오류 0%, 정확도 99.2%) — 개선할 여지가 있는 축이 없는,
  프런티어의 모서리점에 있었습니다.
- 거기에 검증 레이어를 얹은 arm B는 **파레토 열등 이동**이었습니다: 어떤 지표도
  오르지 않았고(상방 0), 한 지표만 내려갔습니다(과교정 −0.84%).
- Q092는 초과 규제의 사중손실(deadweight loss)의 실물입니다 — 규제(프로브)도
  집행(revise)도 각자 규칙을 지켰는데, 조합의 결과는 후생 순감소였습니다.
- 이 관점에서 McNemar 게이트의 정체는 명확합니다: **파레토 열등 이동을
  채택하기 전에 탐지하는 장치.** "검증을 더하면 더 안전하다"는 직관은
  프런티어 안쪽에서만 참이고, 프런티어 위에서는 거짓입니다.

주장 범위의 한계도 명시합니다: 본 실측은 검증 강도 다이얼의 두 점(무검증 vs
P1+revise) 비교이지 프런티어 전체 지도가 아닙니다. "최적점을 찾았다"가 아니라
"**열등 이동을 실측으로 판별했다**"까지가 이 데이터가 지지하는 주장입니다.
프런티어 자체를 그리려면 검증 강도를 여러 수준(예: P2만 / P1 앵커 강도 조절 /
revise 임계 변경)으로 두고 각 점을 같은 게이트로 재야 합니다.

## 레포 구조

```
skill/                  # 스킬 본문 (에이전트 프레임워크용 SKILL.md 포맷)
  SKILL.md              #   그래프 구조·대원칙·실측 판정 기록
  references/
    probe-prompts.md    #   프로브 프롬프트 전문 3종 + 앵커별 논문 출처 수치
    evals.md            #   이진 품질 게이트 (①자체 QA ②A/B 게이트)
harness/                # 실측 ① 합성 스트레스테스트
  run_stress.py         #   러너 (채점과 분리)
  cases.json            #   정상 5 + 오류 주입 5 (합성 근거 문서 기반)
  evidence.md           #   합성 근거 문서 (실제 기준서 아님)
  stress_results_run{1,2}.json
ab/                     # 실측 ② A/B 게이트
  ab_questions_FROZEN.json  # 사전 등록 문항 119 (K-IFRS 공개 기준서 기반)
  ab_runner.py          #   두 arm 러너 (증분 저장·재개 가능)
  grade_ab.py           #   기계 채점 + 블라인드 저지 + McNemar 리포트
  merge_verify.py       #   문항 생성 시 독립 재검증기
  make_chart.py         #   판정 차트 생성
  ab_grades.json        #   채점 원자료
  AB_VERDICT.md         #   판정 전문
docs/
  ab_verdict_chart.png
```

## 재현

```bash
# 전제: claude CLI (또는 run_llm()을 원하는 LLM 호출로 교체)
cd ab
python3 ab_runner.py            # 두 arm 실행 (문항별 증분 저장, 중단 후 재개 가능)
python3 grade_ab.py mech        # 기계 인용 채점
python3 grade_ab.py judge       # 블라인드 저지 (~250콜)
python3 grade_ab.py report      # McNemar 판정표
python3 make_chart.py           # 차트 (matplotlib 필요)
```

## 참고문헌

- Anthropic (2026). *Verbalizable Representations Form a Global Workspace in Language Models.* transformer-circuits.pub/2026/workspace
- Huang, J. et al. (2023). *Large Language Models Cannot Self-Correct Reasoning Yet.* arXiv:2310.01798
- Dhuliawala, S. et al. (2023). *Chain-of-Verification Reduces Hallucination in Large Language Models.* arXiv:2309.11495
- Madaan, A. et al. (2023). *Self-Refine: Iterative Refinement with Self-Feedback.* arXiv:2303.17651
- Shinn, N. et al. (2023). *Reflexion: Language Agents with Verbal Reinforcement Learning.* arXiv:2303.11366
- Manakul, P. et al. (2023). *SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection.* arXiv:2303.08896
- Tian, K. et al. (2023). *Just Ask for Calibration.* arXiv:2305.14975
- Xiong, M. et al. (2023). *Can LLMs Express Their Uncertainty?* arXiv:2306.13063
- FAR.AI (2026). *Obfuscation Atlas.* ICML 2026 — 프로브 게이밍/정책 난독화
- Morris, J. et al. (2026). *How Much Do Language Models Memorize?* ICML 2026

## 라이선스

MIT. 문항 세트는 한국채택국제회계기준(K-IFRS) **공개 기준서 문단**만을 근거로
생성했으며, 어떤 사적/내부 데이터도 포함하지 않습니다.
