"""S3 pair diagnosis (design §6.2) — 0 LLM calls, deterministic.

Input: the two front endpoints A (recall) and B (precision) and their raw 3-run jsonl.
Output: 4 quadrants + BOTH_FAIL clusters by qid (largest first) + forbidden surfaces.

"Agrees with human" (IMPL_NOTES D6): maj ∉ {SPLIT, UNRESOLVED} and
(human ∈ {C,I}) == (maj ∈ PROBLEM) — the same binary the two axes use.

usage:
    python mh_pair_diagnose.py --archive mh_archive_C2.jsonl --front mh_front_C2.json \
        [--raw-dir scripts] [--labels scripts/phase1_human_label_sheet.xlsx]
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE / "scripts"))

import mh_front as mf  # noqa: E402
import mh_objectives as mo  # noqa: E402

LABELS = GATE / "scripts/phase1_human_label_sheet.xlsx"


def unit_table(rec: dict, raw_dir: Path, labels: dict[str, str]) -> dict[str, dict]:
    """candidate record → {uid: {human, maj, rationales}} from its raw_files."""
    files = [str(raw_dir / f) for f in rec["measurement"]["raw_files"]]
    per, _ = mo.load_runs(files)
    out = {}
    for uid in sorted(per):
        human = labels.get(uid)
        if human not in ("S", "C", "I"):
            continue
        rows = sorted(per[uid], key=lambda r: str(r.get("run", "")))
        out[uid] = {"human": human, "maj": mo.majority([r["label"] for r in rows]),
                    "rationales": [str(r.get("rationale", "")) for r in rows]}
    return out


def correct(u: dict) -> bool:
    if u["maj"] in (mo.SPLIT, "UNRESOLVED"):
        return False
    return (u["human"] in mo.HUMAN_PROBLEM) == (u["maj"] in mo.PROBLEM)


def diagnose(a: dict, b: dict, ta: dict, tb: dict) -> dict:
    """a, b = archive records; ta, tb = their unit_table()."""
    quad: dict[str, list[str]] = {k: [] for k in ("BOTH_OK", "A_ONLY", "B_ONLY", "BOTH_FAIL")}
    for uid in sorted(set(ta) & set(tb)):
        ca, cb = correct(ta[uid]), correct(tb[uid])
        quad["BOTH_OK" if ca and cb else "A_ONLY" if ca else "B_ONLY" if cb
             else "BOTH_FAIL"].append(uid)
    by_q: dict[str, list[str]] = collections.defaultdict(list)
    for uid in quad["BOTH_FAIL"]:
        by_q[uid.split("-")[0]].append(uid)
    clusters = sorted(by_q.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    target = None
    if clusters:
        qid, ids = clusters[0]
        target = {"qid": qid, "units": [
            {"id": i, "human": ta[i]["human"], "A_label": ta[i]["maj"],
             "B_label": tb[i]["maj"], "A_rationales": ta[i]["rationales"],
             "B_rationales": tb[i]["rationales"]} for i in ids]}
    forbidden = sorted(set((a.get("harness") or {}).get("edited_surface") or [])
                       | set((b.get("harness") or {}).get("edited_surface") or []))
    return {"A": a["candidate_id"], "B": b["candidate_id"],
            "quadrants": {k: len(v) for k, v in quad.items()},
            "both_fail_clusters": [{"qid": q, "n": len(v), "ids": v} for q, v in clusters],
            "target": target, "forbidden_surfaces": forbidden}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--front", required=True, help="mh_front.py front --out JSON")
    ap.add_argument("--raw-dir", default=str(GATE / "scripts"))
    ap.add_argument("--labels", default=str(LABELS))
    a = ap.parse_args()
    _, latest = mf.load_archive(Path(a.archive))
    ep = json.loads(Path(a.front).read_text(encoding="utf-8"))["endpoints"]
    if ep["recall"] == ep["precision"]:
        print(json.dumps({"S3": "empty — A == B (front size 1)"}))
        return 0
    labels = mo.load_labels(Path(a.labels))
    ra, rb = latest[ep["recall"]], latest[ep["precision"]]
    d = diagnose(ra, rb, unit_table(ra, Path(a.raw_dir), labels),
                 unit_table(rb, Path(a.raw_dir), labels))
    print(json.dumps(d, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
