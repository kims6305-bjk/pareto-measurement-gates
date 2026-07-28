"""Phase 1 judge v2 — 개선판 저지 before/after 실측.

v1 실패 원인(사람 라벨 대조로 실증): claim 고립 채점 — 전체 답변 맥락 없이
쪼개진 claim만 보고 CONTRADICTED/INSUFFICIENT 남발 (P: C 43.8%, I 33.3%).

v2 변경점 (LABELING_PROTOCOL 선언대로):
  - 전체 답변 동봉 + 형제 claim 목록 동봉
  - "불완전성 ≠ 상충" 명시 (저자 라벨 메모에서 실증된 혼동 축)
동일 모델(claude-sonnet-4-6)·동일 55건 — 프롬프트만 변경. 재개 가능, fail-closed.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

GATE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE_DIR / "src"))

from reflection_gate.semantic import (  # noqa: E402
    EVIDENCE_CLOSE,
    EVIDENCE_OPEN,
    OUTPUT_CONTRACT,
    SYSTEM_GUARD,
    sanitize_evidence_text,
)

SHEET_JSON = GATE_DIR / "scripts/phase1_human_label_sheet.json"
OUT_JSONL = GATE_DIR / "scripts/phase1_judge_v2_judgments.jsonl"
MANIFEST = GATE_DIR / "scripts/phase1_judge_v2_manifest.json"

CLAUDE_MODEL = "claude-sonnet-4-6"
CLI_TIMEOUT = 120
LABELS = {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT", "UNRESOLVED"}

V2_GUIDANCE = (
    "판정 지침:\n"
    "1. 검증 대상 claim은 아래 [전체 답변]에서 추출된 일부다. claim을 고립시켜 읽지 말고 "
    "전체 답변의 맥락 안에서 읽어라. 답변의 다른 부분(형제 claim 포함)이 보완하는 내용을 "
    "이 claim의 누락으로 취급하지 마라.\n"
    "2. 불완전성은 상충이 아니다. claim이 근거의 일부만 말하고 있어도, 말한 부분이 근거와 "
    "일치하면 SUPPORTED다. CONTRADICTED는 근거가 claim 내용과 반대되는 것을 진술할 때만 쓴다.\n"
    "3. INSUFFICIENT는 근거 문단이 claim 내용을 지지도 반박도 하지 않을 때만 쓴다."
)


def build_v2_prompt(row: dict, siblings: list[dict]) -> str:
    sib_lines = "\n".join(
        f"- ({s['id'].rsplit('-', 1)[-1]}) {s['claim_text']}" for s in siblings
    ) or "(없음)"
    parts = [
        SYSTEM_GUARD,
        V2_GUIDANCE,
        f"[질문]\n{row['question']}",
        f"[전체 답변]\n{sanitize_evidence_text(row['full_answer'])}",
        f"[같은 답변에서 추출된 형제 claim들]\n{sib_lines}",
        f"[검증할 주장 {row['id']}]\n{row['claim_text']}\n(인용: {row['claim_citation']})",
        f"[근거]\n{EVIDENCE_OPEN}\n{sanitize_evidence_text(row['evidence'])}\n{EVIDENCE_CLOSE}",
        OUTPUT_CONTRACT,
    ]
    return "\n\n".join(parts)


def call_judge(prompt: str) -> tuple[str, str, str]:
    """returns (label, rationale, raw). fail-closed -> UNRESOLVED."""
    try:
        p = subprocess.run(
            ["claude", "-p", "--model", CLAUDE_MODEL, "--max-turns", "1"],
            input=prompt, capture_output=True, text=True, timeout=CLI_TIMEOUT,
        )
        raw = (p.stdout or "").strip()
    except subprocess.TimeoutExpired:
        return "UNRESOLVED", "CLI timeout", ""
    except Exception as exc:  # noqa: BLE001
        return "UNRESOLVED", f"CLI error: {type(exc).__name__}", ""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return "UNRESOLVED", "출력에 JSON 없음", raw[:500]
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return "UNRESOLVED", "JSON 파싱 실패", raw[:500]
    label = str(obj.get("label", "")).upper()
    if label not in LABELS:
        return "UNRESOLVED", f"미정의 라벨: {label}", raw[:500]
    return label, str(obj.get("rationale", "")), raw[:800]


def main() -> None:
    rows = json.load(open(SHEET_JSON, encoding="utf-8"))
    by_qa: dict[str, list[dict]] = {}
    for r in rows:
        qa = r["id"].rsplit("-", 1)[0]  # Q014-A
        by_qa.setdefault(qa, []).append(r)

    done = set()
    if OUT_JSONL.exists():
        for line in OUT_JSONL.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["id"])
            except Exception:  # noqa: BLE001
                pass

    MANIFEST.write_text(json.dumps({
        "judge_model": CLAUDE_MODEL,
        "cli": "claude -p --max-turns 1",
        "timeout_s": CLI_TIMEOUT,
        "prompt_version": "v2 (full answer + sibling claims + incompleteness!=contradiction)",
        "n_claims": len(rows),
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "resume_skipped": len(done),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    n = 0
    with open(OUT_JSONL, "a", encoding="utf-8") as fh:
        for r in rows:
            if r["id"] in done:
                continue
            qa = r["id"].rsplit("-", 1)[0]
            siblings = [s for s in by_qa[qa] if s["id"] != r["id"]]
            t0 = time.time()
            label, rationale, raw = call_judge(build_v2_prompt(r, siblings))
            fh.write(json.dumps({
                "id": r["id"], "v2_label": label, "v2_rationale": rationale,
                "v1_label": r["judge_label"], "raw": raw,
                "elapsed": round(time.time() - t0, 1),
            }, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            print(f"[{n}] {r['id']}: v1={r['judge_label']} -> v2={label}", flush=True)
    print("DONE", n, "claims judged")


if __name__ == "__main__":
    main()
