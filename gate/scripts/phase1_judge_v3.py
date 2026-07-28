"""Phase 1 judge v3 — v2의 과관용(불완전성 면죄부 남용) 교정판.

v2 실측 결과: agreement 88.9%로 개선됐지만 C 재현율 37.5%로 붕괴 —
"불완전성 ≠ 상충" 지침이 너무 넓어서, claim이 결합조건의 일부만으로
결론을 단정하는 경우(필요조건↔충분조건 혼동)까지 SUPPORTED로 통과시킴.
사람 라벨 잔여 불일치 6건 중 5건이 이 축 (Q068·Q042-B-c3·Q049-B-c1).

v3 변경: 지침 2를 "서술의 불완전성"과 "규칙의 왜곡"으로 이분.
동일 모델·동일 55건·프롬프트만 변경. fail-closed, 재개 가능.

⚠️ 방법론 주의: v2→v3 반복은 이 55건 라벨셋에 대한 개발(dev) 튜닝이다.
v3 수치는 이 셋에 과적합됐을 수 있으므로 최종 채택 판정은
prereg v2의 신선한 데이터 재라벨로만 한다 (LABELING_PROTOCOL 취지).
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
OUT_JSONL = GATE_DIR / "scripts/phase1_judge_v3_judgments.jsonl"
MANIFEST = GATE_DIR / "scripts/phase1_judge_v3_manifest.json"

CLAUDE_MODEL = "claude-sonnet-4-6"
CLI_TIMEOUT = 120
LABELS = {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT", "UNRESOLVED"}

V3_GUIDANCE = (
    "판정 지침:\n"
    "1. 검증 대상 claim은 [전체 답변]에서 추출된 일부다. 전체 답변의 맥락 안에서 읽어라. "
    "답변의 다른 부분(형제 claim 포함)이 보완하는 내용을 이 claim의 누락으로 취급하지 마라.\n"
    "2. '서술의 불완전성'과 '규칙의 왜곡'을 구분하라.\n"
    "   - 서술의 불완전성(SUPPORTED): claim이 근거의 일부만 서술하지만, 서술한 부분이 근거와 "
    "일치하고, 빠진 부분을 전체 답변이 보완하거나 claim이 결론을 단정하지 않는 경우.\n"
    "   - 규칙의 왜곡(CONTRADICTED): 근거는 여러 조건의 동시 충족(또는 '~중 이른 날' 같은 "
    "선택 규칙)을 요구하는데, claim이 그 일부만으로 결론이 성립한다고 단정하는 경우. "
    "필요조건을 충분조건처럼 말하면 빠진 조건을 답변의 다른 곳이 언급했더라도 그 claim은 "
    "규칙을 왜곡한 것이다.\n"
    "3. CONTRADICTED는 근거가 claim 내용과 반대되는 것을 진술하거나 위 '규칙의 왜곡'에 "
    "해당할 때 쓴다.\n"
    "4. INSUFFICIENT는 근거 문단이 claim 내용을 지지도 반박도 하지 않을 때만 쓴다. "
    "claim이 근거에 없는 구체적 사실(예: 특정 절차가 이미 이행되었다는 단정)을 담고 있으면 "
    "회계적으로 그럴듯해도 INSUFFICIENT다."
)


def build_v3_prompt(row: dict, siblings: list[dict]) -> str:
    sib_lines = "\n".join(
        f"- ({s['id'].rsplit('-', 1)[-1]}) {s['claim_text']}" for s in siblings
    ) or "(없음)"
    parts = [
        SYSTEM_GUARD,
        V3_GUIDANCE,
        f"[질문]\n{row['question']}",
        f"[전체 답변]\n{sanitize_evidence_text(row['full_answer'])}",
        f"[같은 답변에서 추출된 형제 claim들]\n{sib_lines}",
        f"[검증할 주장 {row['id']}]\n{row['claim_text']}\n(인용: {row['claim_citation']})",
        f"[근거]\n{EVIDENCE_OPEN}\n{sanitize_evidence_text(row['evidence'])}\n{EVIDENCE_CLOSE}",
        OUTPUT_CONTRACT,
    ]
    return "\n\n".join(parts)


def call_judge(prompt: str) -> tuple[str, str, str]:
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
        by_qa.setdefault(r["id"].rsplit("-", 1)[0], []).append(r)

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
        "prompt_version": "v3 (v2 + incompleteness-vs-rule-distortion split)",
        "dev_set_warning": "v3 is tuned against the 55-claim labeled set; final adoption requires fresh prereg-v2 labels",
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
            label, rationale, raw = call_judge(build_v3_prompt(r, siblings))
            fh.write(json.dumps({
                "id": r["id"], "v3_label": label, "v3_rationale": rationale,
                "v1_label": r["judge_label"], "raw": raw,
                "elapsed": round(time.time() - t0, 1),
            }, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            print(f"[{n}] {r['id']} -> v3={label}", flush=True)
    print("DONE", n, "claims judged")


if __name__ == "__main__":
    main()
