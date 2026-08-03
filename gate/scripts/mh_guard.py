"""INV 가드 + 매니페스트 — 매 라운드 시작 시 호출한다.

사전 선언 §13.1 F7·F12, 정본 §7 INV-2(라벨 시트 불변)·INV-3(모델 고정),
부속서1 U13: 매니페스트는 mh_guard.py 가 생성·검증한다.

- 최초 호출: `mh_manifest.json` 생성 (라벨 시트 sha256 2종 + 실행 환경).
- 이후 호출: 현재값과 대조, 불일치면 SystemExit (fail-closed).
- INV-6(proposer 는 축 점수를 계산하지 않는다)은 절차 규율이라 코드로 강제할 수 없으나,
  이 파일이 mh_objectives 를 import 하지 않는 것으로 경계를 지킨다.

usage:
    python mh_guard.py            # 검사 (없으면 생성)
    python mh_guard.py --check    # 검사만 (없으면 실패)
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE / "scripts"))

from phase3_build_prompts import CLAUDE_MODEL  # noqa: E402

MANIFEST = GATE / "scripts/mh_manifest.json"
LABEL_XLSX = GATE / "scripts/phase1_human_label_sheet.xlsx"
LABEL_JSON = GATE / "scripts/phase1_human_label_sheet.json"

EXIT_VIOLATION = 4


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def current_state() -> dict:
    return {
        "label_sheet_xlsx_sha256": sha256(LABEL_XLSX),   # F7
        "label_sheet_json_sha256": sha256(LABEL_JSON),   # F7
        "model": CLAUDE_MODEL,                            # INV-3 / F12
        "python": platform.python_version(),              # F12
        "platform": platform.platform(),                  # F12
    }


def main() -> None:
    check_only = "--check" in sys.argv
    state = current_state()

    if not MANIFEST.exists():
        if check_only:
            print("mh_guard: 매니페스트 없음 (--check 모드)", file=sys.stderr)
            raise SystemExit(EXIT_VIOLATION)
        MANIFEST.write_text(json.dumps(state, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        print(f"mh_guard: 매니페스트 생성 -> {MANIFEST.name}")
        return

    baseline = json.loads(MANIFEST.read_text(encoding="utf-8"))
    violations = []
    # INV-2: 라벨 시트 불변. INV-3: 모델 고정. python/platform 은 기록만(경고).
    for key in ("label_sheet_xlsx_sha256", "label_sheet_json_sha256", "model"):
        if baseline.get(key) != state[key]:
            violations.append(
                f"{key}: manifest={baseline.get(key)} != current={state[key]}")
    for key in ("python", "platform"):
        if baseline.get(key) != state[key]:
            print(f"mh_guard WARNING: {key} 변경됨 "
                  f"({baseline.get(key)} -> {state[key]})", file=sys.stderr)

    if violations:
        for v in violations:
            print(f"mh_guard VIOLATION: {v}", file=sys.stderr)
        raise SystemExit(EXIT_VIOLATION)
    print("mh_guard: PASS (INV-2 라벨 불변 · INV-3 모델 고정)")


if __name__ == "__main__":
    main()
