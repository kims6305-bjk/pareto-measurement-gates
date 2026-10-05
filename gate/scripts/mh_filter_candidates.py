"""filter_strip material (design §6.5-1) — 0 LLM calls, deterministic.

For each front candidate, enumerate instability to strip, in priority order:
  a. SPLIT units (n_split > 0) and their rationales
  b. false alarms (human S → flagged) and their rationales
  c. "cost-only" diff: child whose JUDGE text got longer than its single parent's
     while no axis improved (mh_front.cmp_axis ≤ 0 on both axes, judgment CI)
The first non-empty level wins; inside it the candidate with the most items, then id.
None → filter_strip is skipped this round and the driver records that (§6.5-4).
The deletion itself is written by the proposer in `delete_only` mode (mh_propose.py).

usage:
    python mh_filter_candidates.py --archive mh_archive_C2.jsonl --front mh_front_C2.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE / "scripts"))

import mh_front as mf  # noqa: E402
import mh_objectives as mo  # noqa: E402
from mh_pair_diagnose import LABELS, unit_table  # noqa: E402
from mh_propose import surfaces_of  # noqa: E402


def _judge_len(rec: dict) -> int:
    return sum(len(v) for k, v in surfaces_of(rec["harness"]).items() if k.startswith("JUDGE."))


def material(front: list[str], latest: dict[str, dict], tables: dict[str, dict],
             ci_key: Optional[str] = mf.CI_KEYS[mf.DEFAULT_CI]) -> Optional[dict]:
    levels: dict[str, dict[str, list]] = {"a_split": {}, "b_false_alarm": {}, "c_cost_only": {}}
    for cid in sorted(front):
        t = tables[cid]
        sp = [{"id": u, "rationales": t[u]["rationales"]} for u in sorted(t)
              if t[u]["maj"] == mo.SPLIT]
        fa = [{"id": u, "judge": t[u]["maj"], "rationales": t[u]["rationales"]}
              for u in sorted(t) if t[u]["human"] == "S" and t[u]["maj"] in mo.PROBLEM]
        if sp:
            levels["a_split"][cid] = sp
        if fa:
            levels["b_false_alarm"][cid] = fa
        rec = latest[cid]
        par = rec.get("parent_ids") or []
        if len(par) == 1 and par[0] in latest and latest[par[0]].get("objectives"):
            p = latest[par[0]]
            if (_judge_len(rec) > _judge_len(p)
                    and all(mf.cmp_axis(rec, p, a, ci_key) <= 0 for a in mf.AXES)):
                levels["c_cost_only"][cid] = [{"parent": p["candidate_id"],
                                               "edited_surface":
                                               rec["harness"].get("edited_surface"),
                                               "diff": rec["harness"].get("diff_from_parent")}]
    for level, by_c in levels.items():
        if by_c:
            cid = sorted(by_c, key=lambda c: (-len(by_c[c]), c))[0]
            return {"level": level, "candidate": cid, "items": by_c[cid]}
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--front", required=True)
    ap.add_argument("--raw-dir", default=str(GATE / "scripts"))
    ap.add_argument("--labels", default=str(LABELS))
    a = ap.parse_args()
    _, latest = mf.load_archive(Path(a.archive))
    front = json.loads(Path(a.front).read_text(encoding="utf-8"))["front"]
    labels = mo.load_labels(Path(a.labels))
    tables = {c: unit_table(latest[c], Path(a.raw_dir), labels) for c in front}
    print(json.dumps(material(front, latest, tables) or {"filter_strip": "skip — nothing to strip"},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
