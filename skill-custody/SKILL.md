---
name: chain-of-custody
description: "계보·위변조 검증이 필요한 artifact 원장을 만들 때 사용한다."
version: 0.1.0
author: project maintainers, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [provenance, integrity, ledger, verification, pareto]
    related_skills: [pareto-optimization-gate]
---

# Chain of Custody

기존 artifact를 새 포맷으로 복제하지 않고 SHA-256 digest와 portable locator로 색인한다. 모델·벤더와 무관한 공통 event chain을 append-only JSONL로 남기고 검증한다. 외부 패키지는 사용하지 않는다.

## 언제 쓰나

- 원천 → 판정 → 결정 → 적용 → 검증의 계보와 위변조 탐지가 필요할 때
- Claude/Claude Code, Codex/OpenAI, Hermes, Open Claw, Jev, 규칙엔진, 사람 검토를 같은 원장에 기록할 때
- baseline과 candidate가 같은 Pareto cohort인지 비교 전에 fail-closed로 확인할 때
- 쓰지 않는 경우: artifact 본문을 보관·변환하는 저장소, 전자서명·공증, 접근제어 시스템이 필요할 때

## 입력 계약

- artifact는 `artifact_id`, `digest.algorithm=sha256`, `digest.value`, `locator`만 기록한다.
- locator는 `{"scheme":"repo","path":"relative/posix/path"}` 형식이다. 절대경로, `..`, 역슬래시는 거부한다.
- actor 공통 필드는 `adapter`, `provider`, `principal_type`, `model`, `runtime`이다. `adapter`는 실행기·오케스트레이터이고 `provider`는 실제 모델/판정 제공자라 서로 다를 수 있다.
- adapter는 `anthropic`, `openai`, `hermes`, `open-claw`, `jev`, `rules-engine`, `human` 입력을 정본 ID로 정규화한다. unknown adapter는 기록과 검증 모두 실패한다.
- event type은 `source`, `judgment`, `decision`, `application`, `verification`이다.
- `api_key`, token, password, authorization, cookie, session 및 메시징 식별자는 저장 전에 `[REDACTED]`로 바꾼다.

## 실행

Hermes `terminal`에서 이 스킬 디렉터리를 `workdir`로 지정해 실행한다.

1. 기존 artifact를 색인한다.

   `python3 scripts/chain_of_custody.py artifact --root . --path fixtures/result.json --id result-v1`

2. 출력된 reference를 event JSON의 `artifacts` 배열에 넣는다. artifact 원문은 옮기거나 복제하지 않는다.

3. event를 append한다. 기존 ledger가 있으면 현재 receipt, chain, artifact를 먼저 전수검증한다.

   `python3 scripts/chain_of_custody.py append --ledger custody/events.jsonl --receipt custody/receipt.json --root . --event event.json`

4. 소비 직전에 다시 검증한다.

   `python3 scripts/chain_of_custody.py verify --ledger custody/events.jsonl --receipt custody/receipt.json --root .`

5. Pareto 입력은 custody PASS 뒤에 비교 계약도 확인한다.

   `python3 scripts/chain_of_custody.py compare --baseline baseline-contract.json --candidate candidate-contract.json`

## 비교 계약

baseline과 candidate의 다음 값이 모두 같아야 `COMPARABLE`이다.

- `cohort_id`, `cohort_sha256`, `n_units`
- `metric.name`, `metric.direction`, `metric.unit`
- `code_revision`
- `adapter`, `provider`, `model`, `runtime`

하나라도 누락·형식오류·불일치이면 `INCOMPARABLE`로 중단한다. 점수가 같다는 이유로 우회하지 않는다.

## 검증 기준

- receipt의 event count, head hash, ledger SHA-256가 실제 파일과 일치한다.
- 모든 event의 index가 0부터 연속이고 `previous_event_hash`가 직전 event hash와 일치한다.
- event hash를 `event_hash` 필드 제외 canonical JSON에서 재계산한다.
- 모든 artifact locator를 지정 root 아래에서 해석하고 실제 SHA-256를 다시 계산한다.
- adapter와 comparison contract를 다시 검증한다.
- `references/evals.md`의 합성 fixture 게이트를 실제 실행한다. 실행 0건은 PASS가 아니다.

## 함정과 한계

- hash chain은 위변조를 드러내지만 서명은 아니다. 공격자가 ledger와 receipt를 함께 다시 만들 수 있는 환경에서는 receipt를 별도 서명·WORM 저장소에 둔다.
- receipt 갱신은 원장 append 뒤 원자적으로 교체한다. 두 파일을 여러 writer가 동시에 쓰는 분산 lock은 제공하지 않는다.
- metadata redaction은 방어선이지 비밀 저장 허가가 아니다. 필요한 최소 allowlist metadata만 event에 넣는다.
- artifact가 이동하면 locator를 고치지 말고 새 digest/locator를 새 event로 append한다.
