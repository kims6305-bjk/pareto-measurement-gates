# reflection_gate

K-IFRS 인용 QA 봇용 **fail-closed 4단계 검증 게이트** (Phase 0 골격).

기존 채점기(`ab/grade_ab.py`)는 문단번호 집합 대조 위주라
"문단번호는 맞고 기준서가 틀린" 인용이나 "실제 인용 + 거짓 주장"을 잡지 못하고,
파싱 실패 경로가 조용히 통과로 흐를 여지가 있었다. 이 패키지는 그 지적에 대한 교체본이다.

## 레이어

| # | 레이어 | 모듈 | 성격 |
|---|--------|------|------|
| 1 | 스키마 검사 | `deterministic.check_schema` | 결정론 |
| 2 | 인용 주소·원문 검사 | `deterministic.check_citations` | 결정론 |
| 3 | 의미 검사 | `semantic` (주입형 판정기) | LLM |
| 4 | 정책 판정 | `policy.decide` | 결정론 |

판정은 3상태: `VERIFIED` / `FLAGGED` / `INDETERMINATE`.
**강제 INDETERMINATE가 FLAGGED보다 우선**하며, 어떤 예외도 통과로 흐르지 않는다
(`policy.fail_closed`).

## 사용

```python
from reflection_gate import evaluate, parse_evidence_paragraphs

bundle = parse_evidence_paragraphs(question["evidence_paragraphs"])
result = evaluate(raw_answer_json, bundle, judge=my_llm_judge)
result.verdict   # GateVerdict
result.findings  # [Finding(reason=..., detail=..., claim_id=...)]
```

`judge`를 주입하지 않으면 의미 레이어는 `UNRESOLVED` → 결과는 `INDETERMINATE`다.
구조 검사만 돌리려면 `require_semantic=False`.

## 테스트

```bash
cd gate
uv run pytest -v      # 또는: python3 -m pytest -v
```

네거티브 컨트롤 10종(①틀린 기준서 ②없는 하위항 ③거짓 주장 ④숫자 뒤집기
⑤절반만 근거 ⑥claims=[] ⑦인용 남발 ⑧prompt injection ⑨malformed JSON
⑩timeout/빈 응답) + 포지티브 컨트롤 2종이 상시 게이트로 돈다.
구조적 변조(①②⑥⑦⑨⑩)는 의미 레이어가 전부 SUPPORTED를 돌려주는
mock judge 하에서도 결정론 레이어만으로 차단되는지 확인한다.

모든 파일 I/O는 `encoding='utf-8'` 명시 (Windows 기본 인코딩 의존 제거).
