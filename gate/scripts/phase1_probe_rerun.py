"""Probe rerun for consensus filtering — usage: python phase1_probe_rerun.py <run_tag>

Same prompt/model as phase1_probe_unsupported.py; only the output file differs.
Purpose: keep ONLY claims where the probe fires consistently, and remove the
unstable YES hits (which we suspect are the bulk of the 13 false alarms).
Pre-declared rule (before seeing results): route to human review only when the
probe answers YES in ALL 3 runs; drop split-YES back to auto-PASS.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

GATE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE_DIR / "scripts"))
sys.path.insert(0, str(GATE_DIR / "src"))

from phase1_probe_unsupported import SHEET_JSON, build_prompt, call  # noqa: E402

run_tag = sys.argv[1] if len(sys.argv) > 1 else "run2"
BASE = GATE_DIR / "scripts/phase1_probe_unsupported.jsonl"
OUT = GATE_DIR / f"scripts/phase1_probe_unsupported_{run_tag}.jsonl"


def main() -> None:
    rows = {r["id"]: r for r in json.load(open(SHEET_JSON, encoding="utf-8"))}
    targets = [json.loads(l)["id"] for l in BASE.read_text(encoding="utf-8").splitlines()]

    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["id"])
            except Exception:  # noqa: BLE001
                pass

    n = 0
    with open(OUT, "a", encoding="utf-8") as fh:
        for cid in targets:
            if cid in done:
                continue
            t0 = time.time()
            verdict, rationale = call(build_prompt(rows[cid]))
            fh.write(json.dumps({"id": cid, "unsupported": verdict, "rationale": rationale,
                                 "run": run_tag, "elapsed": round(time.time() - t0, 1)},
                                ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            print(f"[{n}/{len(targets)}] {cid} -> {verdict}", flush=True)
    print(f"DONE {run_tag}: {n}")


if __name__ == "__main__":
    main()
