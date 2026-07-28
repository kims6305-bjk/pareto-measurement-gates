"""readme_parity_check 네거티브 컨트롤 — 검사기가 실제로 막는지 확인한다.

새로 만든 검사가 0건을 내는 것은 아무것도 증명하지 않는다.
막혀야 할 것을 일부러 넣어 실제로 막히는지 확인해야 의미가 있다.

레포 원본은 건드리지 않는다. 레포 전체를 임시 디렉토리로 복사한 뒤
그 사본에 결함을 주입하고, 사본 안의 검사기를 돌린다.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TARGET = "docs/CASE_STUDY.en.md"

# (이름, 주입할 결함) — 각각이 검사기에 걸려야 한다.
DEFECTS = [
    ("링크 1개 추가", "\n[leak test](../README.md)\n"),
    ("헤딩 1개 추가", "\n## Injected heading\n"),
    ("표 행 1개 추가", "\n| a | b |\n"),
    ("이미지 1개 추가", "\n![x](pareto_chart.png)\n"),
    ("1인칭 복수", "\nSo we found the optimum here.\n"),
]


def run_check(root: Path) -> int:
    return subprocess.run(
        [sys.executable, str(root / "gate/scripts/readme_parity_check.py"), "case"],
        capture_output=True, text=True,
    ).returncode


with tempfile.TemporaryDirectory() as td:
    sandbox = Path(td) / "repo"
    shutil.copytree(REPO, sandbox,
                    ignore=shutil.ignore_patterns(".git", ".venv", "*.jsonl"))

    baseline = run_check(sandbox)
    print(f"① 결함 없음 → exit={baseline} " + ("✅" if baseline == 0 else "🔴 통과해야 정상"))
    if baseline != 0:
        sys.exit("baseline이 이미 실패한다 — 네거티브 컨트롤 이전에 이것부터 고쳐야 한다")

    pristine = (sandbox / TARGET).read_text(encoding="utf-8")
    failures = []
    for name, defect in DEFECTS:
        (sandbox / TARGET).write_text(pristine + defect, encoding="utf-8")
        code = run_check(sandbox)
        ok = code == 1
        print(f"② {name} → exit={code} " + ("✅ 잡음" if ok else "🔴 못 잡음"))
        if not ok:
            failures.append(name)
        (sandbox / TARGET).write_text(pristine, encoding="utf-8")

    restored = run_check(sandbox)
    print(f"③ 복원 후 → exit={restored} " + ("✅" if restored == 0 else "🔴"))

    if failures or restored != 0:
        sys.exit(f"\n🔴 네거티브 컨트롤 실패: {failures or '복원 실패'}")
    print("\n✅ 네거티브 컨트롤 통과 — 검사기가 실제로 결함을 막는다")
    print("   (레포 원본은 수정되지 않았다 — 임시 사본에만 주입)")
