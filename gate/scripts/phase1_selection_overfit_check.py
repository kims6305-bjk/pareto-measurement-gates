"""Overfit check for the SELECTION-rule filter (F4).

F4 scored 100% precision on the stable-YES set, but the only 2 true hits were
also the only 2 SELECTION cases — the filter may simply be memorizing them.
Controls run here:
  C1. How many SELECTION-rule claims exist in the WHOLE scored set (not just
      the probe's YES set)? If SELECTION is rare and always a problem, the
      signal is real; if it is common and mostly fine, F4 is memorization.
  C2. Does SELECTION alone (no probe at all) work as a router?
  C3. Leave-one-answer-out: drop the Q068 answer entirely and see whether the
      filter still has any positive left to find. (If not, F4 is supported by
      exactly one answer = not evidence.)
"""
import json
import re
from pathlib import Path
from collections import defaultdict

G = Path("<repo>/gate/scripts")
rows = {r["id"]: r for r in json.load(open(G / "phase1_human_label_sheet.json", encoding="utf-8"))}
res = json.load(open(G / "phase1_judge_pr_result.json", encoding="utf-8"))
scored = {r["id"]: r for r in res["records"] if "명제없음" not in r["memo"]}
human = {i: scored[i]["human"] for i in scored}

SELECTION = ("중 이른 날", "중 이른", "둘 중", "중 빠른", "중 늦은", "중 하나")


def is_sel(cid):
    return any(k in rows[cid]["evidence"] for k in SELECTION)


sel = [i for i in scored if is_sel(i)]
print("=== C1. 전체 채점 대상에서 선택규칙(SELECTION) 근거 분포 ===")
print(f"선택규칙 근거를 가진 주장: {len(sel)}/{len(scored)}건 -> {sel}")
for i in sel:
    print(f"   {i}: 사람={human[i]}  인용={rows[i]['claim_citation']}")
probs = [i for i in sel if human[i] in "CI"]
print(f"이 중 실제 문제 {len(probs)}건 = 정밀도 {len(probs)/len(sel):.1%} "
      f"(전체 기저율 {sum(1 for i in human if human[i] in 'CI')/len(human):.1%})")

print("\n=== C2. 선택규칙 단독 라우터 (프로브 없이) ===")
print(f"검토 {len(sel)}건으로 문제 {len(probs)}건 회수. "
      f"프로브 3판YES(14건)로 2건 회수한 것과 비교.")

print("\n=== C3. Leave-one-answer-out (Q068 답변 제외) ===")
sel_wo = [i for i in sel if not i.startswith("Q068")]
probs_wo = [i for i in sel_wo if human[i] in "CI"]
print(f"Q068 제외 시 선택규칙 주장 {len(sel_wo)}건, 그중 실제 문제 {len(probs_wo)}건")
if not probs_wo:
    print("-> 이 필터를 지지하는 양성 사례가 Q068 답변 하나뿐. n=1 = 증거 아님(과적합).")
else:
    print("-> 독립 답변에서도 양성 존재. 약하지만 신호 가능성 있음.")

# how many distinct answers back each signal
ans = lambda i: i.rsplit("-", 1)[0]
print(f"\n선택규칙 양성이 걸친 서로 다른 답변 수: {len({ans(i) for i in probs})} "
      f"({sorted({ans(i) for i in probs})})")
print(f"전체 문제 10건이 걸친 서로 다른 답변 수: "
      f"{len({ans(i) for i in human if human[i] in 'CI'})} "
      f"({sorted({ans(i) for i in human if human[i] in 'CI'})})")
