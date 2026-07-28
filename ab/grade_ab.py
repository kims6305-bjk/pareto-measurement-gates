#!/usr/bin/env python3
"""블라인드 채점기 — evals.md ② 판정용.

층별 채점 규칙 (FROZEN 시점에 고정된 기준):
- 인용오류(주지표, 기계 대조 — 토큰 0):
  * 어떤 claim의 citation 문단번호가 evidence에 실존하지 않으면 → 날조 인용 (오류)
  * no_answer층: claims가 비어있지 않으면 → 근거 밖 답변 (오류)
    (검수 시 명문화: 근거 밖 지식 인용 답변 = 실패)
- 답변정확도(가드레일 1, LLM 블라인드 저지):
  * 저지는 arm 라벨을 모른다. (question, gold, candidate)만 받음
  * 두 arm 답변을 무작위 순서·중립 라벨로 제시
- 과교정(가드레일 2, 기계+저지):
  * arm B에서 revise가 일어난 문항만: draft 정답 → final 오답 전환 건수

사용:
  python3 grade_ab.py mech          # 기계 채점만 (즉시)
  python3 grade_ab.py judge         # LLM 저지 (238콜, 증분 저장·재개 가능)
  python3 grade_ab.py report        # McNemar 포함 최종 판정
"""
import json, re, random, subprocess, sys, time, pathlib
from math import comb

BASE = pathlib.Path(__file__).parent
FROZEN = json.loads((BASE / "ab_questions_FROZEN.json").read_text())
RESULTS = json.loads((BASE / "ab_results.json").read_text())
GRADES = BASE / "ab_grades.json"

QMAP = {q["qid"]: q for q in FROZEN["questions"]}

JUDGE_TMPL = """[역할]
너는 회계 답변 채점자다. 모범답안과 후보 답변을 비교해 정답 여부만 판정한다.

[규칙]
- 표현이 달라도 핵심 결론과 근거 문단이 모범답안과 실질적으로 같으면 정답.
- 모범답안이 "답할 수 없음" 취지인 경우: 후보가 "제공된 자료에서 확인되지 않음"
  취지로 답했으면 정답, 구체적 수치/조문을 단정했으면 오답.
- JSON만 출력: {{"correct": true|false, "reason": "한 문장"}}

[질문]
{question}

[모범답안]
{gold}

[후보 답변]
{candidate}"""


def paras_in_evidence(ev: str):
    return set(re.findall(r"문단 (\w+)", ev))


def cited_paras(ans):
    out = set()
    for c in (ans or {}).get("claims") or []:
        cit = str(c.get("citation", ""))
        # 하위 항호 "(1)", "-(2)" 제거 후 "문단 N"의 N만 추출
        cit_clean = re.sub(r"[-–]?\s*\((\d+)\)", "", cit)
        m = re.findall(r"문단\s*(\d+[A-Za-z]?)", cit_clean)
        if m:
            out |= set(m)
        else:
            # "1002 9" 형태 fallback: 기준서번호(4자리)를 뺀 마지막 수
            nums = [x for x in re.findall(r"\b(\d+[A-Za-z]?)\b", cit_clean)
                    if not re.fullmatch(r"\d{4}", x)]
            if nums:
                out.add(nums[-1])
    return out


def mech_citation_error(q, ans) -> bool:
    """True = 인용오류 있음.
    기준 (FROZEN 채점 규칙):
    - 파싱 실패 = 오류
    - no_answer층: claims 비어있지 않으면 근거 밖 답변 = 오류
    - normal/distractor층: ①인용 0건 ②evidence 밖 문단 인용(날조)
      ③gold 문단을 하나도 인용 안 함(distractor의 함정 문단만 인용 포함) = 오류
    """
    if ans is None:
        return True  # 파싱 실패 = 오류 처리
    if q["layer"] == "no_answer":
        return bool(ans.get("claims"))  # 근거 밖 답변
    ev_paras = paras_in_evidence(q["evidence_paragraphs"])
    cited = cited_paras(ans)
    if not cited:
        return True  # normal/distractor에서 인용 0건 = 오류
    if not cited.issubset(ev_paras):
        return True  # evidence 밖 문단 인용 = 날조
    gold = {str(c.get("paragraph", "")) for c in q.get("gold_citations") or []}
    gold = {re.sub(r"\(.*\)", "", p).strip() for p in gold}
    if gold and not (cited & gold):
        return True  # gold 문단 미인용 (함정 문단만 인용한 경우 포함)
    return False


def load_grades():
    if GRADES.exists():
        return json.loads(GRADES.read_text())
    return {}


def save_grades(g):
    GRADES.write_text(json.dumps(g, ensure_ascii=False, indent=1))


def cmd_mech():
    g = load_grades()
    for qid, rec in RESULTS.items():
        q = QMAP[qid]
        ent = g.setdefault(qid, {})
        ent["citeA_err"] = mech_citation_error(q, rec.get("armA"))
        ent["citeB_err"] = mech_citation_error(q, rec.get("armB_final"))
        if rec.get("armB_needs_revision"):
            ent["citeB_draft_err"] = mech_citation_error(q, rec.get("armB_draft"))
    save_grades(g)
    a = sum(1 for e in g.values() if e["citeA_err"])
    b = sum(1 for e in g.values() if e["citeB_err"])
    n = len(g)
    print(f"기계 인용채점: n={n}  armA 오류 {a} ({a/n:.1%})  armB 오류 {b} ({b/n:.1%})")


def run_llm(prompt, retries=2):
    for att in range(retries + 1):
        try:
            r = subprocess.run(["claude", "-p", "--output-format", "text"],
                               input=prompt, capture_output=True, text=True, timeout=180)
            if r.stdout.strip():
                return r.stdout.strip()
        except subprocess.TimeoutExpired:
            pass
        time.sleep(5 * (att + 1))
    return ""


def parse_json(raw):
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
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


def judge_one(q, ans):
    if ans is None:
        return False, "(no answer json)"
    cand = ans.get("answer", "")
    gold = q["gold_answer"] if q["layer"] != "no_answer" else \
        "이 질문은 제공된 근거 문단만으로는 답할 수 없다. '제공된 자료에서 확인되지 않음' 취지가 정답."
    raw = run_llm(JUDGE_TMPL.format(question=q["question"], gold=gold, candidate=cand))
    p = parse_json(raw)
    return bool(p and p.get("correct")), raw


def cmd_judge():
    g = load_grades()
    # 블라인드: (qid, arm) 태스크를 셔플해 순서로도 arm 추정 불가하게
    tasks = []
    for qid, rec in RESULTS.items():
        if "accA" not in g.get(qid, {}):
            tasks.append((qid, "A"))
        if "accB" not in g.get(qid, {}):
            tasks.append((qid, "B"))
        if RESULTS[qid].get("armB_needs_revision") and "accB_draft" not in g.get(qid, {}):
            tasks.append((qid, "Bd"))
    random.seed()  # 실행마다 다른 순서
    random.shuffle(tasks)
    print(f"judge tasks: {len(tasks)}", flush=True)
    for i, (qid, arm) in enumerate(tasks, 1):
        q = QMAP[qid]
        rec = RESULTS[qid]
        ans = {"A": rec.get("armA"), "B": rec.get("armB_final"),
               "Bd": rec.get("armB_draft")}[arm]
        ok, raw = judge_one(q, ans)
        key = {"A": "accA", "B": "accB", "Bd": "accB_draft"}[arm]
        g.setdefault(qid, {})[key] = ok
        g[qid][key + "_raw"] = raw[:500]
        save_grades(g)
        print(f"[{i}/{len(tasks)}] {qid}/{arm} {'✓' if ok else '✗'}", flush=True)
    print("JUDGE DONE", flush=True)


def mcnemar_p(b, c):
    """양측 exact McNemar. b,c = 불일치 쌍 수."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(k + 1)) / 2 ** n * 2
    return min(1.0, p)


def cmd_report():
    g = load_grades()
    n = len(g)
    # 주지표: 인용오류율 McNemar
    b = sum(1 for e in g.values() if e["citeA_err"] and not e["citeB_err"])  # B가 개선
    c = sum(1 for e in g.values() if not e["citeA_err"] and e["citeB_err"])  # B가 악화
    a_err = sum(1 for e in g.values() if e["citeA_err"])
    b_err = sum(1 for e in g.values() if e["citeB_err"])
    p_cite = mcnemar_p(b, c)
    print(f"== 주지표: 인용오류율 (기계 대조) ==")
    print(f"  armA {a_err}/{n} ({a_err/n:.1%})  armB {b_err}/{n} ({b_err/n:.1%})")
    print(f"  불일치쌍: A오류→B정상 {b} / A정상→B오류 {c}  McNemar p={p_cite:.4f}")

    # 가드레일1: 정확도
    have = [e for e in g.values() if "accA" in e and "accB" in e]
    if have:
        accA = sum(1 for e in have if e["accA"])
        accB = sum(1 for e in have if e["accB"])
        b2 = sum(1 for e in have if not e["accA"] and e["accB"])
        c2 = sum(1 for e in have if e["accA"] and not e["accB"])
        p_acc = mcnemar_p(b2, c2)
        print(f"== 가드레일1: 답변정확도 (블라인드 저지) ==")
        print(f"  armA {accA}/{len(have)} ({accA/len(have):.1%})  armB {accB}/{len(have)} ({accB/len(have):.1%})")
        print(f"  A✗→B✓ {b2} / A✓→B✗ {c2}  McNemar p={p_acc:.4f}")

    # 가드레일2: 과교정 (revise 발생 문항에서 draft✓→final✗)
    over = 0; rev_n = 0
    for qid, e in g.items():
        if "accB_draft" in e and "accB" in e:
            rev_n += 1
            if e["accB_draft"] and not e["accB"]:
                over += 1
    print(f"== 가드레일2: 과교정 ==")
    print(f"  revise 발생 {rev_n}건 중 정답→오답 {over}건  전체 대비 {over/n:.2%} (임계 0.5%)")

    # 층별 분해
    print(f"== 층별 인용오류 ==")
    from collections import defaultdict
    lay = defaultdict(lambda: [0, 0, 0])
    for qid, e in g.items():
        L = QMAP[qid]["layer"]
        lay[L][0] += 1
        lay[L][1] += e["citeA_err"]
        lay[L][2] += e["citeB_err"]
    for L, (tot, ea, eb) in lay.items():
        print(f"  {L:10s} n={tot:3d}  A오류 {ea}  B오류 {eb}")


if __name__ == "__main__":
    {"mech": cmd_mech, "judge": cmd_judge, "report": cmd_report}[sys.argv[1]]()
