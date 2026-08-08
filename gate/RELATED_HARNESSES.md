# 관련 하네스 — 자기개선 루프에 채택 게이트가 있는가

이 레포의 주장은 "자기개선 하네스에는 **채택 게이트**(개선 후보를 받아들일지 판정하는
장치)가 필요하다"이다. 그렇다면 먼저 물어야 한다 — **기존 하네스에는 정말 없는가?**

여기서는 공개된 참조 구현 1종을 파일:라인 단위로 해부해 그 부재를 실측한다.
"없다"는 주장은 인상이 아니라 grep 0건과 코드 경로 부재로 증명한다.

## 대상

| 항목 | 값 |
|---|---|
| 저장소 | `PrimeIntellect-ai/prime-agent` |
| 커밋 | `a18809e00ea30638584d87b3afea7285a9d7296c` (2026-08-07) |
| 구조 | TypeScript(`packages/coding-agent/src`) + Python(`prime-agent-runtime/src/rlm`) 하이브리드 |
| 대상 기능 | auto-refine — 실행 궤적을 보고 하네스(프롬프트·메모리·스킬)를 자동 수정 |
| 검증 실행 | `PYTHONPATH=src python3 -m pytest test/test_harness.py -q` → 35 passed |

인용한 줄번호는 위 커밋 기준이며, 본 문서 작성 시 전건 재실측했다.
(TypeScript 테스트는 `node_modules` 미설치로 실행하지 않았다 — 소스 판독만.)

## 판정 요약

**형식은 코드가 강제한다. 개선 여부 판정은 LLM에 위임돼 있다.**

이 구분이 핵심이다. 스키마 위반은 확실히 거부되지만, "이 수정이 실제로 개선인가"를
묻는 코드 경로는 존재하지 않는다.

### 코드가 강제하는 것 (거부 경로 실재)

| 규칙 | 근거 |
|---|---|
| base system prompt은 편집 불가 | `refinement/refinement.ts:671-673` — id 직접·파생 양쪽 차단 |
| skill은 python reference 필수 | `refinement/refinement.ts:683-703` + `harness.py:128-138` (TS/Py 이중 미러) |
| 계획 중 변경된 엔트리는 적용 거부 | `refinement/refinement.ts:727-740` → `"entry changed during refinement planning"` |
| 자식 에이전트는 refine 불가 | `agent-session.ts:7192-7194` (`_rlmDepth === 0`) |

### LLM에 위임된 것 (검증 코드 없음)

| 주장 | 실제 |
|---|---|
| "refine할 가치가 있는 궤적만" | 파싱은 `refinement/refinement.ts:943` `record.shouldRefine === true` **한 줄**. 근거 검증 0 |
| `expectedOutcome`이 달성됐는지 | `refinement/refinement.ts:788`에서 `outcome` 필드로 **저장만** |
| 압축에서 무엇을 하네스로 승격할지 | `grep -rn "harnessState" src/core/compaction/` → **0건.** 두 서브시스템이 결합돼 있지 않다 |

## 핵심 발견 — expectedOutcome은 기록되지만 검증되지 않는다

제안된 각 수정은 `expectedOutcome`(이 변경이 무엇을 개선할 것인가)을 함께 저장한다
(`refinement/refinement.ts:788`). 자연스러운 다음 물음은 "그래서 달성됐는가"이고,
그것을 재는 코드가 있는지 전수 확인했다.

```
$ grep -rn "\.outcome" --include=*.ts --include=*.py packages prime-agent-runtime \
    | grep -v node_modules | grep -v test
```

반환된 소비처 전부가 다른 의미의 `outcome`(cron job 상태, compaction 결과 표시,
telemetry)이었고, refinement의 `expectedOutcome`을 읽는 유일한 지점은:

```ts
// refinement/refinement.ts:511
const outcome = event.outcome ? `; outcome: ${compactText(event.outcome, maxContentLength)}` : "";
```

**다음 refine 호출의 프롬프트에 텍스트로 다시 넣는 것뿐이다.** 즉 기대 효과는
사람이 읽을 문자열로 순환할 뿐, 어떤 조건문도 그 값을 판정에 쓰지 않는다.

결과적으로 자기개선은 **누적되되 측정되지 않는다.** 수정 N개가 쌓였을 때 하네스가
나아졌는지 나빠졌는지 판정하는 장치가 코드에 없고, 되돌림 판단의 근거도 없다.
(엔트리 단위 되돌리기 자체는 `refinement/refinement.ts:804` 이하에 구현돼 있으나,
이는 "적용 실패 시 원복"이지 "개선이 아니었을 때 원복"이 아니다.)

이것이 이 레포가 다루는 빈자리다.

## 부재증명의 함정 — 우리가 한 번 틀렸다

초판 조사에서 "skill의 python import 실존을 확인하는 코드가 없다"고 적으며 근거로
`grep -rn "importlib\|import_module"` → 0건을 들었다. **이 실측이 틀렸다.**
본 문서 작성 중 재실행했을 때 9건이 나왔고, 그중 하나는 테스트가 아니었다:

```python
# tools/ipython.ts:132 이 생성하는 커널 부트스트랩 코드
globals()[_prime_agent_skill_name] = _prime_agent_wrap_skill_module(
    _prime_agent_importlib.import_module(_prime_agent_skill_name)
)
```

다만 성격을 보면 결론은 유지된다. 이 코드는 **런타임 로더**이고, import 실패는
예외를 삼켜 `_PrimeAgentUnavailableSkill` 스텁으로 대체된다
(`tools/ipython.ts:134-139`). 즉 **스킬을 등록하는 시점의 검증이 아니라, 호출될 때
비로소 실패하는 지연 실패**다. `refinement/refinement.ts:683-703`의 계약 검사는
문자열 필드 존재만 보므로, import 불가능한 스킬도 하네스에 등록된다.

정확히 하면: 부재한 것은 "import 코드"가 아니라 **"등록 시점의 import 실존 검증"**이다.

두 가지 교훈을 기록해 둔다.

1. **grep 0건은 검색어가 맞을 때만 증거다.** 초판은 잘못된 파일 경로
   (`core/refinement.ts` — 실제는 `core/refinement/refinement.ts`)로 검색했고,
   경로가 없으면 도구가 0건이 아니라 오류를 반환하는데 그것을 0건으로 읽었다.
   **부재증명은 반드시 재실행해 재현할 것.**
2. **부재증명이 깨져도 결론이 살아남는지는 따로 판정한다.** 여기서는 코드의
   *성격*(등록 시 검증 vs 호출 시 실패)이 결론을 지탱했다. 지탱하지 못했다면
   주장을 철회해야 했다.

## 이 레포와의 관계

| 이 레포 | 참조 구현 |
|---|---|
| 후보를 축 위에서 측정하고 파레토 전선으로 채택 판정 | 채택 판정 없음 — LLM `shouldRefine` 부울 |
| 본 실행 전 계기 검침(IC-0/1/2)으로 자격 없는 탐색 차단 | 검침 개념 없음 |
| 기대 효과를 결과변수로 사전 등록 | 기대 효과를 문자열로 저장, 미검증 |

반대로 참조 구현이 앞서는 부분도 명시해 둔다 — **동시성 안전장치**는 이 레포에
없는 수준으로 구현돼 있다: 세대번호 무효화(`agent-session.ts:1263`, `:7218-7221`),
적용 직전 상태 재읽기 + baseline 대조(`agent-session.ts:7825`,
`refinement/refinement.ts:727-740`), tmp write + rename 원자적 저장
(`refinement/refinement.ts:345-359`), 외부 쓰기 mtime 감지(`harness.py:186-196`).

즉 두 구현은 **다른 축**을 지키고 있다. 참조 구현은 "동시에 써도 깨지지 않는가",
이 레포는 "쓴 것이 개선인가". 채택 게이트의 부재는 설계 실수라기보다
**아직 아무도 그 축을 재지 않았다**는 상태에 가깝다.

## 재현

```bash
git clone https://github.com/PrimeIntellect-ai/prime-agent /tmp/prime-agent
cd /tmp/prime-agent && git checkout a18809e

# 부재증명 (0건이어야 함)
grep -rn "harnessState" packages/coding-agent/src/core/compaction/ | wc -l

# expectedOutcome 소비처 — 프롬프트 렌더링 1곳 외 없음
grep -rn "\.outcome" --include=*.ts --include=*.py packages prime-agent-runtime \
  | grep -v node_modules | grep -v test

# 파이썬 테스트
cd prime-agent-runtime && PYTHONPATH=src python3 -m pytest test/test_harness.py -q
```
