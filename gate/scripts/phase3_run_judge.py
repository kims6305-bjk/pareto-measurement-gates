"""Phase 3 저지 실행기 — 조건 A/B × 3판, 재개 가능, fail-closed.

usage:
    python phase3_run_judge.py <cond:A|B> <run:run1|run2|run3> [--smoke N]

사전 선언(PHASE3_PREREGISTRATION.md §5):
  - 모든 채점을 3판 실행하고 다수결로 확정. 단일 실행 수치는 성능이 아니다.
  - 모델 ID 고정(alias 금지). fail-closed: 타임아웃·파싱 실패·미정의 라벨은
    UNRESOLVED로 기록하고 정상 통과시키지 않는다.
  - 기본 대상은 **확증 집합 + 단독 주장 전량**(대조군은 순환 논증 위험 없음, §3.2).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

GATE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE_DIR / "scripts"))

from phase3_build_prompts import (  # noqa: E402
    CLAUDE_MODEL,
    assert_single_variable,
    build,
)

CLI_TIMEOUT = 120
VALID = {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT"}


def call(prompt: str) -> tuple[str, str]:
    """fail-closed: 어떤 실패도 UNRESOLVED. 정상 라벨로 승격하지 않는다."""
    try:
        p = subprocess.run(
            ["claude", "-p", "--model", CLAUDE_MODEL, "--max-turns", "1"],
            input=prompt, capture_output=True, text=True, timeout=CLI_TIMEOUT,
        )
        raw = (p.stdout or "").strip()
    except Exception as exc:  # noqa: BLE001
        return "UNRESOLVED", f"judge error: {type(exc).__name__}"
    if not raw:
        return "UNRESOLVED", "빈 출력"
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return "UNRESOLVED", "출력에 JSON 없음"
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return "UNRESOLVED", "JSON 파싱 실패"
    label = str(obj.get("label", "")).upper()
    if label not in VALID:
        return "UNRESOLVED", f"미정의 라벨: {label}"
    return label, str(obj.get("rationale", ""))


def main() -> None:
    cond = (sys.argv[1] if len(sys.argv) > 1 else "A").upper()
    run = sys.argv[2] if len(sys.argv) > 2 else "run1"
    smoke = 0
    if "--smoke" in sys.argv:
        smoke = int(sys.argv[sys.argv.index("--smoke") + 1])
    if cond not in ("A", "B"):
        raise SystemExit("cond must be A or B")

    units = json.load(open(GATE_DIR / "scripts/phase3_units.json", encoding="utf-8"))
    # 대상: 확증 집합 전량 + 단독 주장(대조군, 집합 무관)
    targets = [u for u in units
               if u["set"] == "confirmatory" or not u["siblings"]]
    targets.sort(key=lambda u: u["id"])
    if smoke:
        targets = targets[:smoke]

    out = GATE_DIR / f"scripts/phase3_judge_{cond}_{run}.jsonl"
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["id"])
            except Exception:  # noqa: BLE001
                pass

    todo = [u for u in targets if u["id"] not in done]
    print(f"조건 {cond} / {run}: 대상 {len(targets)}건, 완료 {len(done)}, 남은 {len(todo)}",
          flush=True)

    n = 0
    with open(out, "a", encoding="utf-8") as fh:
        for u in todo:
            assert_single_variable(u)   # 매 건 변인 오염 재검증 (§2)
            prompt = build(u, with_siblings=(cond == "B"))
            t0 = time.time()
            label, rationale = call(prompt)
            fh.write(json.dumps({
                "id": u["id"], "cond": cond, "run": run, "label": label,
                "rationale": rationale, "set": u["set"],
                "rule_type": u["rule_type"], "qid": u["qid"],
                "n_siblings": len(u["siblings"]),
                "model": CLAUDE_MODEL,
                "elapsed": round(time.time() - t0, 1),
            }, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            if n % 10 == 0 or n == len(todo):
                print(f"[{n}/{len(todo)}] {u['id']} -> {label}", flush=True)
    print(f"DONE {cond}/{run}: {n}건 기록 -> {out.name}")


if __name__ == "__main__":
    main()
