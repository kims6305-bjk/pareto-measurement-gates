"""False-alarm pattern mining on the probe's stable-YES set (n=14).

Observed pattern (read from all 14 rationales):
  ALL 12 false alarms are the SAME failure mode — the answer DECOMPOSES a
  multi-part rule across sibling claims (c1 cites 문단 71-(1), c2 cites 71-(2)),
  and the probe, seeing one claim in isolation, reports "the other conditions
  are omitted". The omission is an artifact of per-claim scoring, not of the
  answer.
  The 2 true hits (Q068-A-c1/c2) look identical structurally — but the evidence
  there is a SELECTION rule ("다음 중 이른 날"), where naming one branch as the
  answer really is wrong, whereas the false alarms sit on CONJUNCTIVE /
  COMPOSITIONAL rules ("모두 충족", "다음 요소로 구성된다", a formula), where
  restating one part is legitimate decomposition.

Candidate filters are measured, not assumed. Overfit risk is reported.
"""
import json
import re
from pathlib import Path
from collections import defaultdict

G = Path("<repo>/gate/scripts")
rows = {r["id"]: r for r in json.load(open(G / "phase1_human_label_sheet.json", encoding="utf-8"))}
res = json.load(open(G / "phase1_judge_pr_result.json", encoding="utf-8"))
scored = {r["id"]: r for r in res["records"] if "명제없음" not in r["memo"]}

probe = defaultdict(list)
for name in ("phase1_probe_unsupported.jsonl", "phase1_probe_unsupported_run2.jsonl",
             "phase1_probe_unsupported_run3.jsonl"):
    for line in (G / name).read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        probe[r["id"]].append(r["unsupported"])

yes3 = sorted(i for i in probe if len(probe[i]) == 3 and all(v == "YES" for v in probe[i]))
human = {i: scored[i]["human"] for i in scored}

# --- signal 1: sibling decomposition -----------------------------------
# another claim in the SAME answer cites a different sub-item of the same paragraph
SUB = re.compile(r"[\(-]\s*([0-9가나다라마])\s*\)")
BASE = re.compile(r"[\(-]\s*[0-9가나다라마]\s*\)\s*$")


def base_cite(c):
    return BASE.sub("", c).strip().rstrip("-").strip()


by_answer = defaultdict(list)
for i in rows:
    by_answer[i.rsplit("-", 1)[0]].append(i)


def has_sibling_subitem(cid):
    cite = rows[cid]["claim_citation"]
    mine = SUB.findall(cite)
    if not mine:
        return False
    b = base_cite(cite)
    for sib in by_answer[cid.rsplit("-", 1)[0]]:
        if sib == cid:
            continue
        sc = rows[sib]["claim_citation"]
        if base_cite(sc) == b and SUB.findall(sc) and SUB.findall(sc) != mine:
            return True
    return False


# --- signal 2: rule type in the evidence -------------------------------
SELECTION = ("중 이른 날", "중 이른", "둘 중", "중 빠른", "중 늦은", "중 하나")
CONJUNCTIVE = ("모두 충족", "모두 해당", "요소로 구성", "항목으로 구성", "모두 확인")


def rule_type(cid):
    ev = rows[cid]["evidence"]
    if any(k in ev for k in SELECTION):
        return "SELECTION"
    if any(k in ev for k in CONJUNCTIVE):
        return "CONJUNCTIVE"
    return "OTHER"


print(f"{'id':<14}{'사람':<5}{'형제분해':<10}{'규칙유형':<12}")
for i in yes3:
    print(f"{i:<14}{human[i]:<5}{str(has_sibling_subitem(i)):<10}{rule_type(i):<12}")

# --- candidate filters --------------------------------------------------
filters = {
    "F0 무필터": lambda i: True,
    "F1 형제분해면 제외": lambda i: not has_sibling_subitem(i),
    "F2 연언·구성규칙이면 제외": lambda i: rule_type(i) != "CONJUNCTIVE",
    "F3 형제분해 AND 연언이면 제외": lambda i: not (has_sibling_subitem(i) and rule_type(i) == "CONJUNCTIVE"),
    "F4 선택규칙만 통과": lambda i: rule_type(i) == "SELECTION",
}
print()
for name, fn in filters.items():
    kept = [i for i in yes3 if fn(i)]
    tp = [i for i in kept if human[i] in "CI"]
    fa = [i for i in kept if human[i] == "S"]
    prec = len(tp) / len(kept) if kept else None
    print(f"{name:<24} 검토 {len(kept):>2}건  진짜 {len(tp)}  헛검토 {len(fa):>2}  "
          f"정밀도 {'n/a' if prec is None else f'{prec:.1%}'}")

out = {i: {"human": human[i], "sibling_decomposition": has_sibling_subitem(i),
           "rule_type": rule_type(i)} for i in yes3}
(G / "phase1_probe_falsealarm_patterns.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nsaved: scripts/phase1_probe_falsealarm_patterns.json")
