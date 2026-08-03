# c000(baseline) 원장 행 생성 — §5.1 스키마, 현 빌더 그대로(§9.2)
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
from phase3_build_prompts import CLAUDE_MODEL, build  # noqa: E402
from instrument_check_run import load_units  # noqa: E402

units = load_units()
psha = hashlib.sha256(build(units[0], with_siblings=True).encode()).hexdigest()
lsha_x = hashlib.sha256(
    Path("scripts/phase1_human_label_sheet.xlsx").read_bytes()).hexdigest()

row = {
    "candidate_id": "c000",
    "created_at": "2026-08-03T12:00:00+09:00",
    "parent_ids": [],
    "generation": 0,
    "origin": "baseline",
    "origin_reason": "Phase 3 빌더 현 상태 그대로 (설계 §9.2). 측정 = IC-0 재실행 (부속서1 U8).",
    "harness": {
        "builder_module": "phase3_build_prompts",
        "builder_fn": "build",
        "builder_kwargs": {"with_siblings": True},
        "prompt_sha256": psha,
        "model": CLAUDE_MODEL,
        "diff_from_parent": "없음 (baseline)",
        "edited_surface": [],
    },
    "measurement": {"label_sheet_sha256": lsha_x, "n_units": len(units),
                    "n_runs": 0, "raw_files": []},
    "objectives": None,
    "reference_fields": {},
    "sample_gate": {"passed": False, "violations": ["미측정"]},
    "status": "UNJUDGED",
    "status_history": [{"at": "2026-08-03T12:00:00+09:00",
                        "status": "UNJUDGED", "by": "c000 등록 (미측정)"}],
}
p = Path("scripts/mh_archive_C2.jsonl")
p.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", p, "| units:", len(units), "| prompt_sha:", psha[:12])
