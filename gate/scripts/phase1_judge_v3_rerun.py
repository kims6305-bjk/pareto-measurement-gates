"""v3 저지 재실행 (앙상블용 추가 표본) — usage: python phase1_judge_v3_rerun.py <run_tag>

phase1_judge_v3.py와 동일 프롬프트·동일 모델, 출력 파일만 run_tag로 분리.
샘플링 변동을 표본으로 쓰는 앙상블(any-flag) 실측용. 재개 가능, fail-closed.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

GATE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE_DIR / "scripts"))
sys.path.insert(0, str(GATE_DIR / "src"))

from phase1_judge_v3 import SHEET_JSON, build_v3_prompt, call_judge  # noqa: E402

run_tag = sys.argv[1] if len(sys.argv) > 1 else "run2"
OUT_JSONL = GATE_DIR / f"scripts/phase1_judge_v3_{run_tag}.jsonl"


def main() -> None:
    rows = json.load(open(SHEET_JSON, encoding="utf-8"))
    by_qa: dict[str, list[dict]] = {}
    for r in rows:
        by_qa.setdefault(r["id"].rsplit("-", 1)[0], []).append(r)

    done = set()
    if OUT_JSONL.exists():
        for line in OUT_JSONL.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["id"])
            except Exception:  # noqa: BLE001
                pass

    n = 0
    with open(OUT_JSONL, "a", encoding="utf-8") as fh:
        for r in rows:
            if r["id"] in done:
                continue
            qa = r["id"].rsplit("-", 1)[0]
            siblings = [s for s in by_qa[qa] if s["id"] != r["id"]]
            t0 = time.time()
            label, rationale, raw = call_judge(build_v3_prompt(r, siblings))
            fh.write(json.dumps({
                "id": r["id"], "v3_label": label, "v3_rationale": rationale,
                "run": run_tag, "elapsed": round(time.time() - t0, 1),
            }, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            print(f"[{n}] {r['id']} -> {label}", flush=True)
    print(f"DONE {run_tag}:", n)


if __name__ == "__main__":
    main()
