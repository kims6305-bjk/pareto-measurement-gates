"""의미 레이어 재채점 — 기존 ab_results.json 238건(119문항×2arm) 전수.

- 결정론 레이어 통과분(VERIFIED)만 semantic judge(claude CLI)로 claim별 판정
- 기권(ABSTAIN)은 대상 아님
- 저지 원문·사유 전문을 jsonl로 남긴다 (GPT 지적 "저지 원문 부재" 해소)
- 재개 가능: 이미 기록된 (qid, arm)은 건너뜀
- fail-closed: CLI 실패/타임아웃/형식오류 → UNRESOLVED → INDETERMINATE
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

from reflection_gate.gate import evaluate  # noqa: E402
from reflection_gate.models import (  # noqa: E402
    parse_evidence_paragraphs,
    extract_standard_number,
)
from reflection_gate.semantic import SemanticJudgement, SemanticLabel  # noqa: E402

WORKSPACE = Path.home() / ".openclaw/workspace"
# 레포 동봉본 우선, 없으면 로컬 원본 (공개 레포에서는 ab/ab_results.json 사용)
_REPO_RESULTS = GATE_DIR.parent / "ab/ab_results.json"
_LOCAL_RESULTS = WORKSPACE / "probe_graph_test/ab_results.json"
RESULTS = _REPO_RESULTS if _REPO_RESULTS.exists() else _LOCAL_RESULTS
FROZEN = GATE_DIR.parent / "ab/ab_questions_FROZEN.json"
OUT_JSONL = GATE_DIR / "scripts/semantic_regrade_judgments.jsonl"
OUT_SUMMARY = GATE_DIR / "scripts/semantic_regrade_summary.json"
MANIFEST = GATE_DIR / "scripts/semantic_regrade_manifest.json"

CLAUDE_MODEL = "claude-sonnet-4-6"  # alias 금지 — 정확한 모델 ID 고정 (GPT 지적)
CLI_TIMEOUT = 120

ABSTAIN = re.compile(r"확인되지\s*않|근거\s*없|답변\s*불가|판단할\s*수\s*없")
LABELS = {l.value for l in SemanticLabel}


def norm_alias(cit: str) -> str:
    m = re.match(r"^\s*(IAS|IFRS)\s*(\d+)\s*(.*)$", cit)
    if m:
        n = int(m.group(2))
        if n >= 1000:
            return f"{n} {m.group(3)}"
        base = 1000 if m.group(1) == "IAS" else 1100
        return f"{base + n} {m.group(3)}"
    return cit


def adapt(parsed: dict, std: str) -> dict:
    out = {"answer": parsed.get("answer", ""), "claims": []}
    for c in parsed.get("claims", []):
        cit = norm_alias(str(c.get("citation", "")).strip())
        if not cit or ABSTAIN.search(cit):
            continue
        if not re.match(r"^\s*제?\s*\d{4}", cit):
            cit = f"{std} {cit}"
        out["claims"].append(
            {"id": str(c.get("claim_id", "")), "text": c.get("text", ""), "citation": cit}
        )
    if not out["claims"] and parsed.get("claims"):
        out["__all_abstain"] = True
    return out


def make_judge(log_rows: list):
    def judge(prompt: str, claim) -> SemanticJudgement:
        t0 = time.time()
        try:
            p = subprocess.run(
                ["claude", "-p", "--model", CLAUDE_MODEL, "--max-turns", "1"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=CLI_TIMEOUT,
            )
            raw = (p.stdout or "").strip()
        except subprocess.TimeoutExpired:
            log_rows.append({"claim_id": claim.claim_id, "error": "timeout", "elapsed": time.time() - t0})
            return SemanticJudgement.unresolved(claim.claim_id, "CLI timeout")
        except Exception as exc:  # noqa: BLE001
            log_rows.append({"claim_id": claim.claim_id, "error": f"{type(exc).__name__}: {exc}"})
            return SemanticJudgement.unresolved(claim.claim_id, f"CLI error: {type(exc).__name__}")

        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            log_rows.append({"claim_id": claim.claim_id, "raw": raw[:500], "error": "no_json"})
            return SemanticJudgement.unresolved(claim.claim_id, "저지 출력에 JSON 없음")
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            log_rows.append({"claim_id": claim.claim_id, "raw": raw[:500], "error": "bad_json"})
            return SemanticJudgement.unresolved(claim.claim_id, "저지 JSON 파싱 실패")
        label = str(obj.get("label", "")).upper()
        if label not in LABELS:
            log_rows.append({"claim_id": claim.claim_id, "raw": raw[:500], "error": "bad_label"})
            return SemanticJudgement.unresolved(claim.claim_id, f"미정의 라벨: {label}")
        rationale = str(obj.get("rationale", ""))
        log_rows.append(
            {
                "claim_id": claim.claim_id,
                "label": label,
                "rationale": rationale,
                "raw": raw[:800],
                "elapsed": round(time.time() - t0, 1),
            }
        )
        return SemanticJudgement(claim_id=claim.claim_id, label=SemanticLabel(label), rationale=rationale)

    return judge


def main() -> None:
    res = json.load(open(RESULTS, encoding="utf-8"))
    frozen = json.load(open(FROZEN, encoding="utf-8"))
    qs = {q["qid"]: q for q in (frozen["questions"] if isinstance(frozen, dict) else frozen)}

    done = set()
    if OUT_JSONL.exists():
        for line in OUT_JSONL.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                done.add((row["qid"], row["arm"]))
            except Exception:  # noqa: BLE001
                pass

    MANIFEST.write_text(
        json.dumps(
            {
                "judge_model": CLAUDE_MODEL,
                "cli": "claude -p --max-turns 1",
                "timeout_s": CLI_TIMEOUT,
                "dataset": "ab/" + FROZEN.name,
                "raw_results": "ab/" + Path(RESULTS).name,
                "started": time.strftime("%Y-%m-%d %H:%M:%S"),
                "resume_skipped": len(done),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    n_total = 0
    with open(OUT_JSONL, "a", encoding="utf-8") as fh:
        for qid, q in sorted(qs.items()):
            r = res[qid]
            std = extract_standard_number(q["standard"]) or ""
            bundle = parse_evidence_paragraphs(q["evidence_paragraphs"], default_standard=q["standard"])
            for arm, parsed in [("A", r["armA"]), ("B", r["armB_final"])]:
                if (qid, arm) in done:
                    continue
                if not parsed.get("claims") and ABSTAIN.search(parsed.get("answer", "")):
                    row = {"qid": qid, "arm": arm, "layer": q["layer"], "verdict": "ABSTAIN_OK", "judgments": []}
                else:
                    a = adapt(parsed, std)
                    if a.pop("__all_abstain", False):
                        row = {"qid": qid, "arm": arm, "layer": q["layer"], "verdict": "ABSTAIN_OK", "judgments": []}
                    else:
                        log_rows: list = []
                        out = evaluate(
                            json.dumps(a, ensure_ascii=False),
                            bundle,
                            judge=make_judge(log_rows),
                            question=q["question"],
                            require_quote=False,
                        )
                        row = {
                            "qid": qid,
                            "arm": arm,
                            "layer": q["layer"],
                            "verdict": out.verdict.value,
                            "findings": [
                                {"reason": f.reason.value, "detail": f.detail, "claim_id": f.claim_id}
                                for f in out.findings
                            ],
                            "claim_labels": out.claim_labels,
                            "judgments": log_rows,
                        }
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
                n_total += 1
                print(f"[{n_total}] {qid} {arm} -> {row['verdict']}", flush=True)

    # 요약
    from collections import Counter

    tally: Counter = Counter()
    rows = [json.loads(l) for l in OUT_JSONL.read_text(encoding="utf-8").splitlines()]
    latest = {}
    for row in rows:
        latest[(row["qid"], row["arm"])] = row
    for (qid, arm), row in latest.items():
        tally[f"{arm}:{row['verdict']}"] += 1
    summary = {"tally": dict(tally), "n_pairs": len(latest), "finished": time.strftime("%Y-%m-%d %H:%M:%S")}
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print("SUMMARY:", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
