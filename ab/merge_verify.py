#!/usr/bin/env python3
"""3분할 문항 병합 + 부모 에이전트 독립 재검증 — 자식 자기보고 불신 원칙.
검증기도 자식 것을 재사용하지 않고 독립 구현."""
import json, re, pathlib
from collections import Counter

BASE = pathlib.Path(__file__).parent
corpus = json.loads((BASE / "corpus.json").read_text())

def norm(s):
    return re.sub(r"\s+", "", s)

# 기준서별 정규화 전문 캐시
flat = {code: norm(" ".join(d["paras"].values())) for code, d in corpus.items()}

merged, fails = [], []
seen_qid = set()
for i in (1, 2, 3):
    qs = json.loads((BASE / f"ab_questions_part{i}.json").read_text())
    qs = qs["questions"] if isinstance(qs, dict) else qs
    merged.extend(qs)

for q in merged:
    qid = q.get("qid", "?")
    # 스키마
    for k in ("qid", "layer", "standard", "question", "evidence_paragraphs",
              "gold_answer", "gold_citations", "trap_note"):
        if k not in q:
            fails.append((qid, f"missing key {k}"))
    if qid in seen_qid:
        fails.append((qid, "duplicate qid"))
    seen_qid.add(qid)
    layer = q.get("layer")
    if layer not in ("normal", "no_answer", "distractor"):
        fails.append((qid, f"bad layer {layer}"))
    cits = q.get("gold_citations", [])
    if layer == "no_answer":
        if cits:
            fails.append((qid, "no_answer but citations non-empty"))
    else:
        if not cits:
            fails.append((qid, "citations empty"))
    # quote 실존 (corpus 대조 — 독립 검증 핵심)
    ev_n = norm(q.get("evidence_paragraphs", ""))
    for c in cits:
        code = str(c.get("standard", "")).split()[0]
        qt = c.get("quote", "")
        if code not in flat:
            fails.append((qid, f"unknown standard {code}")); continue
        if norm(qt) not in flat[code]:
            fails.append((qid, f"quote not in corpus: {qt[:30]}"))
        if norm(qt) not in ev_n:
            fails.append((qid, f"quote not in evidence: {qt[:30]}"))
    # 질문 원문 복붙 검사
    if norm(q.get("question", "")) and norm(q["question"]) in ev_n:
        fails.append((qid, "question is verbatim copy of evidence"))

layers = Counter(q["layer"] for q in merged)
stds = Counter(q["standard"].split()[0] for q in merged)
n = len(merged)
print(f"총 문항: {n}")
print(f"층: {dict(layers)} | no_answer {layers['no_answer']/n:.0%}, distractor {layers['distractor']/n:.0%}")
print(f"기준서 {len(stds)}종: {dict(stds)}")
print(f"FAILS: {len(fails)}")
for f in fails[:20]:
    print(" ", f)

if not fails:
    out = {"meta": {"n": n, "layers": dict(layers), "standards": dict(stds),
                    "status": "draft — 사람 검수·고정 선언 전 실험 시작 금지"},
           "questions": merged}
    (BASE / "ab_questions_draft.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1))
    print("MERGED -> ab_questions_draft.json")
