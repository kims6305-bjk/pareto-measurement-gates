"""Dump the probe's stable-YES cases (3/3) with claim, evidence, human label,
memo, and all three rationales — for false-alarm pattern mining.
"""
import json
from pathlib import Path

G = Path("<repo>/gate/scripts")
rows = {r["id"]: r for r in json.load(open(G / "phase1_human_label_sheet.json", encoding="utf-8"))}
res = json.load(open(G / "phase1_judge_pr_result.json", encoding="utf-8"))
scored = {r["id"]: r for r in res["records"] if "명제없음" not in r["memo"]}

probe = {}
for name in ("phase1_probe_unsupported.jsonl", "phase1_probe_unsupported_run2.jsonl",
             "phase1_probe_unsupported_run3.jsonl"):
    for line in (G / name).read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        probe.setdefault(r["id"], []).append((r["unsupported"], r.get("rationale", "")))

yes3 = [i for i in probe if len(probe[i]) == 3 and all(v == "YES" for v, _ in probe[i])]
out = []
for i in sorted(yes3):
    h = scored[i]["human"]
    kind = "TRUE_HIT" if h in "CI" else "FALSE_ALARM"
    row = rows[i]
    out.append({
        "id": i, "kind": kind, "human": h, "memo": scored[i]["memo"],
        "question": row["question"],
        "claim": row["claim_text"], "citation": row["claim_citation"],
        "evidence": row["evidence"],
        "rationales": [r for _, r in probe[i]],
    })
Path("/tmp/probe_yes3_dump.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"3판YES {len(out)}건 (오탐 {sum(1 for o in out if o['kind']=='FALSE_ALARM')})")
print("saved /tmp/probe_yes3_dump.json",
      Path("/tmp/probe_yes3_dump.json").stat().st_size, "bytes")

# also dump the structural miss
miss = "Q107-A-c2"
row = rows[miss]
Path("/tmp/probe_miss.json").write_text(json.dumps({
    "id": miss, "human": scored[miss]["human"], "memo": scored[miss]["memo"],
    "question": row["question"], "claim": row["claim_text"],
    "citation": row["claim_citation"], "evidence": row["evidence"],
    "rationales": [r for _, r in probe.get(miss, [])],
}, ensure_ascii=False, indent=2), encoding="utf-8")
print("saved /tmp/probe_miss.json")
