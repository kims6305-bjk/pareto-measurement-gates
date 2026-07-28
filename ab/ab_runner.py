#!/usr/bin/env python3
"""A/B 실측 러너 — probe-graph evals.md ② 게이트.

arm A (control): answer 단독
arm B (probe):   answer → P1 인용대조(주장 리스트만) → [코드 유도 needs_revision] → revise 캡=1

- 두 arm 모두 같은 answer 프롬프트·같은 모델(claude CLI)·같은 날 실행
- needs_revision은 모델 필드를 믿지 않고 코드에서 any(verdict != "일치")로 유도
  (probe-graph 스킬 함정: 모델이 근거없음 잡고도 false로 내는 케이스 실측 재현됨)
- 문항별 증분 저장(ab_results.json), 재개 가능(이미 done인 qid 스킵)

사용: python3 ab_runner.py [--limit N] [--only QID,QID]
"""
import json, re, subprocess, sys, time, pathlib

BASE = pathlib.Path(__file__).parent
FROZEN = BASE / "ab_questions_FROZEN.json"
OUT = BASE / "ab_results.json"

ANSWER_TMPL = """[역할]
너는 한국 K-IFRS 기반 회계 질의응답 봇이다. 아래 '근거 문단'만을 근거로 질문에 답한다.

[규칙]
- 근거 문단에 없는 내용은 답하지 마라. 근거로 답할 수 없으면 answer에
  "제공된 자료에서 확인되지 않음"이라고 명시하고 claims는 빈 배열로 둔다.
- 답변에 사용한 모든 주장을 claims 배열에 원자적으로 분해해 나열하라.
  각 주장에는 근거 문단 번호(citation)를 붙인다.
- JSON만 출력. 다른 텍스트 금지.

[출력 형식]
{{"answer": "답변 본문 (2~4문장, 문단 번호 인용 포함)",
  "claims": [{{"claim_id": 1, "text": "원자적 주장 한 문장", "citation": "기준서번호 문단번호"}}]}}

[근거 문단]
{evidence}

[질문]
{question}"""

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
{{"items": [{{"claim_id": 1, "verdict": "일치|근거없음|불일치",
   "quote": "근거 문서 원문 발췌 또는 없음",
   "specific_error": "불일치일 때만 한 문장. 그 외 null"}}]}}

[근거 문서]
{evidence}

[주장 목록]
{claims}"""

REVISE_TMPL = """[역할]
아래 답변에서 검증자가 지적한 항목만 수정한다.

[규칙]
- 지적된 항목만 고친다. 다른 문장은 한 글자도 바꾸지 마라.
- '근거없음' 항목: 다른 조문/수치로 대체하지 말고 "제공된 자료에서 확인되지
  않음"으로 바꾼다. 새 인용을 만들어내지 마라.
- '불일치' 항목: 검증자가 발췌한 근거 원문에 맞게만 고친다.
- JSON만 출력: {{"answer": "...", "claims": [...]}} (원본과 같은 스키마)

[원본 답변(JSON)]
{draft}

[검증자 지적]
{probe_output}"""


def run_llm(prompt: str, retries: int = 2) -> str:
    for attempt in range(retries + 1):
        try:
            r = subprocess.run(
                ["claude", "-p", "--output-format", "text"],
                input=prompt, capture_output=True, text=True, timeout=240,
            )
            out = r.stdout.strip()
            if out:
                return out
        except subprocess.TimeoutExpired:
            pass
        time.sleep(5 * (attempt + 1))
    return ""


def parse_json(raw: str):
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def claims_text(ans: dict) -> str:
    cs = ans.get("claims") or []
    return "\n".join(f'{c.get("claim_id", i+1)}. {c.get("text","")} [{c.get("citation","")}]'
                     for i, c in enumerate(cs))


def load_results():
    if OUT.exists():
        return json.loads(OUT.read_text())
    return {}


def save_results(res):
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1))


def run_question(q: dict) -> dict:
    ev = q["evidence_paragraphs"]
    qtext = q["question"]
    rec = {"layer": q["layer"], "standard": q["standard"]}

    # ---- arm A: answer only ----
    a_raw = run_llm(ANSWER_TMPL.format(evidence=ev, question=qtext))
    rec["armA_raw"] = a_raw
    rec["armA"] = parse_json(a_raw)

    # ---- arm B: answer -> P1 -> (revise cap=1) ----
    b_raw = run_llm(ANSWER_TMPL.format(evidence=ev, question=qtext))
    rec["armB_draft_raw"] = b_raw
    draft = parse_json(b_raw)
    rec["armB_draft"] = draft

    if draft and draft.get("claims"):
        p1_raw = run_llm(P1_TMPL.format(evidence=ev, claims=claims_text(draft)))
        rec["armB_p1_raw"] = p1_raw
        p1 = parse_json(p1_raw)
        rec["armB_p1"] = p1
        # 코드 유도 판정 — 모델 needs_revision 불신
        needs = bool(p1 and any(it.get("verdict") != "일치" for it in p1.get("items", [])))
        rec["armB_needs_revision"] = needs
        if needs:
            rv_raw = run_llm(REVISE_TMPL.format(
                draft=json.dumps(draft, ensure_ascii=False),
                probe_output=json.dumps(p1, ensure_ascii=False)))
            rec["armB_revised_raw"] = rv_raw
            rec["armB_final"] = parse_json(rv_raw) or draft
        else:
            rec["armB_final"] = draft
    else:
        # claims 비면(모른다 답변 등) 프로브 스킵 — 검증할 주장 없음
        rec["armB_p1"] = None
        rec["armB_needs_revision"] = False
        rec["armB_final"] = draft

    rec["done"] = True
    rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return rec


def main():
    args = sys.argv[1:]
    limit = None
    only = None
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    if "--only" in args:
        only = set(args[args.index("--only") + 1].split(","))

    qs = json.loads(FROZEN.read_text())["questions"]
    if only:
        qs = [q for q in qs if q["qid"] in only]
    res = load_results()
    todo = [q for q in qs if not res.get(q["qid"], {}).get("done")]
    if limit:
        todo = todo[:limit]
    print(f"total {len(qs)} / done {len(qs)-len(todo)} / todo {len(todo)}", flush=True)

    for i, q in enumerate(todo, 1):
        t0 = time.time()
        try:
            res[q["qid"]] = run_question(q)
        except Exception as e:
            print(f"[{q['qid']}] ERROR {e}", flush=True)
            continue
        save_results(res)
        r = res[q["qid"]]
        ok_a = "A✓" if r.get("armA") else "A✗"
        ok_b = "B✓" if r.get("armB_final") else "B✗"
        rev = "rev" if r.get("armB_needs_revision") else "-"
        print(f"[{i}/{len(todo)}] {q['qid']} {ok_a} {ok_b} {rev} ({time.time()-t0:.0f}s)",
              flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
