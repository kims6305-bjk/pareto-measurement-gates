"""계기 검침 — Phase 3 저지를 Phase 1 라벨 55건에 물린다.

사전 선언: INSTRUMENT_CHECK_PREREG.md (실행 전 커밋됨)

핵심: **Phase 3의 프롬프트 빌더를 import해서 그대로 쓴다.** 여기서 프롬프트를
새로 짜면 "무엇을 검침했는지"가 흐려진다. 검침 대상은 실제로 Phase 3에서 돌아간
그 저지여야 한다.

usage:
    python instrument_check_run.py <run1|run2|run3>
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import openpyxl

GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE / "scripts"))

from phase3_build_prompts import CLAUDE_MODEL, build  # noqa: E402

SHEET_XLSX = GATE / "scripts/phase1_human_label_sheet.xlsx"
SHEET_JSON = GATE / "scripts/phase1_human_label_sheet.json"
CLI_TIMEOUT = 120
VALID = {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT"}


def load_units() -> list[dict]:
    """사람 라벨(xlsx G열) + 본문(json)을 합쳐 Phase 3 unit 형식으로 만든다."""
    rows = {r["id"]: r for r in json.load(open(SHEET_JSON, encoding="utf-8"))}

    ws = openpyxl.load_workbook(SHEET_XLSX)["라벨링"]
    labels = {}
    for r in ws.iter_rows(min_row=2):
        vals = [c.value for c in r]
        if vals[0]:
            labels[vals[0]] = vals[6]          # G열 = 사람 라벨 S/C/I

    by_qa: dict[str, list[str]] = {}
    for i in rows:
        by_qa.setdefault(i.rsplit("-", 1)[0], []).append(i)

    units = []
    for i, row in rows.items():
        human = labels.get(i)
        if human not in ("S", "C", "I"):
            continue                            # 라벨 없는 건 검침 대상 아님
        sibs = [{"text": rows[s]["claim_text"],
                 "citation": rows[s]["claim_citation"]}
                for s in by_qa[i.rsplit("-", 1)[0]] if s != i]
        units.append({
            "id": i,
            "question": row["question"],
            "evidence": row["evidence"],
            "claim_text": row["claim_text"],
            "claim_citation": row["claim_citation"],
            "siblings": sibs,
            "human": human,
        })
    units.sort(key=lambda u: u["id"])
    return units


def call(prompt: str) -> tuple[str, str]:
    """fail-closed — Phase 3와 동일 규약."""
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
    units = load_units()
    out = GATE / f"scripts/instrument_check_{run}.jsonl"

    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["id"])
            except Exception:  # noqa: BLE001
                pass

    todo = [u for u in units if u["id"] not in done]
    n_prob = sum(1 for u in units if u["human"] in ("C", "I"))
    print(f"{run}: 대상 {len(units)}건 (사람 판정 문제 {n_prob}건), "
          f"완료 {len(done)}, 남은 {len(todo)}", flush=True)

    n = 0
    with open(out, "a", encoding="utf-8") as fh:
        for u in todo:
            # 🔴 조건 B(형제 포함) 고정 — 사전 선언 §3
            prompt = build(u, with_siblings=True)
            t0 = time.time()
            label, rationale = call(prompt)
            fh.write(json.dumps({
                "id": u["id"], "run": run, "label": label,
                "rationale": rationale, "human": u["human"],
                "n_siblings": len(u["siblings"]),
                "model": CLAUDE_MODEL,
                "elapsed": round(time.time() - t0, 1),
            }, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            if n % 10 == 0 or n == len(todo):
                print(f"[{n}/{len(todo)}] {u['id']} human={u['human']} -> {label}",
                      flush=True)
    print(f"DONE {run}: {n}건 -> {out.name}")


if __name__ == "__main__":
    main()
