#!/usr/bin/env python3
"""probe-graph 합성 스트레스테스트 러너 (evals.md ① 게이트)
P1(인용대조)·P3(위험열거)를 claude CLI로 각 케이스에 실행하고 원시 출력 저장.
채점은 별도 단계(사람 또는 별도 채점기)에서 — 러너는 실행만."""
import json, subprocess, sys, time, pathlib, re

BASE = pathlib.Path(__file__).parent
cases = json.loads((BASE / "cases.json").read_text())["cases"]
evidence = (BASE / "evidence.md").read_text()

P1_TMPL = """[역할]
너는 회계·세무 답변의 인용 검증자다. 답변을 다시 쓰지 않는다.
아래 '주장 목록'의 각 항목이 '근거 문서'로 뒷받침되는지만 확인한다.

[중요한 전제]
- 이 주장들은 이미 정확할 가능성이 높다. 오류가 있다고 가정하지 마라.
- 네 과제는 '문제를 찾는 것'이 아니라 '근거와 일치하는지 확인하는 것'이다.
- 지적할 것이 없으면 없다고 답하는 것이 정답이다.

[검증 절차] 각 주장에 대해:
1. 근거 문서에서 그 주장을 뒷받침하는 문장을 원문 그대로 발췌하라.
   (예/아니오로 판정하지 말고, 반드시 원문 문장을 발췌할 것)
2. 발췌할 문장이 없으면 근거란에 "없음"이라고 쓴다.
3. 발췌 문장이 주장과 구체적으로 어긋나는 경우에만(조문 번호 불일치,
   수치 불일치, 적용 요건 불일치 등) 판정을 '불일치'로 하고,
   어느 부분이 어떻게 다른지 한 문장으로 특정하라.
   막연히 "부정확해 보인다"는 사유는 금지한다.

[출력 형식] JSON만 출력. 다른 텍스트 금지.
{{
  "items": [
    {{"claim_id": 1, "verdict": "일치|근거없음|불일치",
     "quote": "근거 문서 원문 발췌 또는 없음",
     "specific_error": "불일치일 때만, 어느 부분이 어떻게 다른지. 그 외 null"}}
  ],
  "needs_revision": true/false   // 불일치 또는 근거없음이 1건 이상일 때만 true
}}

[근거 문서]
{evidence}

[주장 목록]
{claims}"""

P3_TMPL = """[역할]
너는 답변을 수정하지 않는다. 위험 구간만 표시한다.
아래 답변에서 '근거로 뒷받침되지 않거나 불확실한 부분'만 열거하라.

[규칙]
- 답변 문장을 고쳐 쓰지 마라. 대안 답변도 제시하지 마라.
- 근거 문서로 확인되는 부분은 언급하지 마라.
- 각 항목마다 답변 원문을 그대로 인용하고, 왜 불확실한지 아래 유형 중 하나로 분류:
  (a) 근거 문서에 해당 내용 없음
  (b) 근거는 있으나 적용 요건/기간/대상이 질문 상황과 다를 수 있음
  (c) 근거 문서 간 상충
  (d) 수치·날짜가 근거와 불일치
- 확신도는 단일 숫자로 쓰지 말고 상/중/하로 표기하고,
  대안 해석이 있으면 후보를 최대 2개까지 함께 적어라.
- 위험 구간이 없으면 {{"risks": []}} 만 출력하라. 억지로 채우지 마라.

[출력] JSON만 출력. 다른 텍스트 금지.
{{"risks":[{{"quote":"...","type":"a|b|c|d","confidence":"상|중|하",
           "alternatives":["...","..."]}}]}}

[근거 문서]
{evidence}

[답변]
{answer}"""


def run_llm(prompt: str) -> str:
    r = subprocess.run(
        ["claude", "-p", "--output-format", "text"],
        input=prompt, capture_output=True, text=True, timeout=180,
    )
    return r.stdout.strip()


def main():
    results = {}
    for c in cases:
        cid = c["id"]
        claims_txt = "\n".join(f'{cl["claim_id"]}. {cl["text"]}' for cl in c["claims"])
        p1 = run_llm(P1_TMPL.format(evidence=evidence, claims=claims_txt))
        print(f"[{cid}] P1 done ({len(p1)} chars)", flush=True)
        p3 = run_llm(P3_TMPL.format(evidence=evidence, answer=c["answer"]))
        print(f"[{cid}] P3 done ({len(p3)} chars)", flush=True)
        results[cid] = {"type": c["type"], "seeded_error": c["seeded_error"],
                        "p1_raw": p1, "p3_raw": p3}
        (BASE / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print("ALL DONE")


if __name__ == "__main__":
    main()
