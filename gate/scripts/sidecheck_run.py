"""옆방 검침 실행 — 판정기 프롬프트를 그대로 재사용한다(수정 금지).

🔴 핵심: phase3_build_prompts.build()를 import해서 쓴다. 여기서 프롬프트를
새로 짜거나 영어로 번역하면 "무엇을 검증했는지"가 흐려진다. 검증 대상은
K-IFRS에서 81.8%를 낸 **바로 그 판정기**이며, 프롬프트 언어도 그대로 둔다.
(도메인·언어가 바뀌어도 같은 도구가 작동하는지가 질문이므로.)

usage: python sidecheck_run.py <run1|run2|run3> [--room 1|2]
       --room 1 = SciFact(영어·생의학), --room 2 = KLUE-NLI(한국어·비회계)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE / "scripts"))

from phase3_build_prompts import CLAUDE_MODEL, build  # noqa: E402

CLI_TIMEOUT = 120
VALID = {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT"}
ROOMS = {
    "1": ("sidecheck_units.json", "sidecheck_{run}.jsonl", "scifact"),
    "2": ("sidecheck2_units.json", "sidecheck2_{run}.jsonl", "klue-nli"),
}


def call(prompt: str) -> tuple[str, str]:
    """fail-closed — 원래 방과 동일 규약."""
    try:
        p = subprocess.run(
            ["claude", "-p", "--model", CLAUDE_MODEL, "--max-turns", "1"],
            input=prompt, capture_output=True, text=True, timeout=CLI_TIMEOUT,
        )
        raw = (p.stdout or "").strip()
    except Exception as exc:  # noqa: BLE001
        return "UNRESOLVED", f"judge error: {type(exc).__name__}"
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
    run = sys.argv[1] if len(sys.argv) > 1 else "run1"
    room = "1"
    if "--room" in sys.argv:
        room = sys.argv[sys.argv.index("--room") + 1]
    if room not in ROOMS:
        raise SystemExit("--room must be 1 or 2")
    units_file, out_tpl, domain = ROOMS[room]

    units = json.load(open(GATE / "scripts" / units_file, encoding="utf-8"))
    out = GATE / "scripts" / out_tpl.format(run=run)

    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["id"])
            except Exception:  # noqa: BLE001
                pass

    todo = [u for u in units if u["id"] not in done]
    n_prob = sum(1 for u in units if u["human"] in ("C", "I"))
    print(f"[옆방{room}:{domain}] {run}: 대상 {len(units)}건 "
          f"(사람 판정 문제 {n_prob}건), 완료 {len(done)}, 남은 {len(todo)}",
          flush=True)

    n = 0
    with open(out, "a", encoding="utf-8") as fh:
        for u in todo:
            prompt = build(u, with_siblings=True)   # 형제 없음 -> 블록 미삽입
            t0 = time.time()
            label, rationale = call(prompt)
            fh.write(json.dumps({
                "id": u["id"], "run": run, "label": label,
                "rationale": rationale, "human": u["human"],
                "domain": domain, "model": CLAUDE_MODEL,
                "elapsed": round(time.time() - t0, 1),
            }, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            if n % 10 == 0 or n == len(todo):
                print(f"[{n}/{len(todo)}] {u['id']} human={u['human']} -> {label}",
                      flush=True)
    print(f"DONE {domain}/{run}: {n}건 -> {out.name}")


if __name__ == "__main__":
    main()
