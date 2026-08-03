"""러너 — 후보 1개를 3판(55×3=165콜) 측정한다. 재개 가능·fail-closed.

정본 §9.1: 후보 정의는 원장(mh_archive_<COND>.jsonl)의 `harness` 필드에서 읽는다.
정본 §9.2: `instrument_check_run.py` 의 `load_units()`·`call()` 을 재사용한다.
부속서1 U8: baseline c000 의 측정이 곧 IC-0 재실행이다 (신규 파일 경로,
기존 instrument_check_run*.jsonl 은 보존).
부속서1 U4: 조건별 원장 분리 = 파일 분리 (mh_archive_C0/C1/C2.jsonl).

🔴 이 파일은 축 점수를 계산하지 않는다(mh_objectives.py). front 도 계산하지 않는다
   (mh_front.py). 측정 원자료 jsonl 만 쓴다 — INV-6 경계.
🔴 매 실행 시작 시 mh_guard.py 검사를 통과해야 한다 (INV-2·INV-3).

usage:
    python mh_run_candidate.py --candidate-id c000 --condition C2 --run run1
    python mh_run_candidate.py --candidate-id c000 --condition C2 --all-runs
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
import time
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE / "scripts"))

from instrument_check_run import call, load_units  # noqa: E402

RUNS = ("run1", "run2", "run3")
CONDITIONS = ("C0", "C1", "C2")


def archive_path(condition: str) -> Path:
    return GATE / f"scripts/mh_archive_{condition}.jsonl"


def load_candidate(condition: str, cid: str) -> dict:
    """원장에서 후보 정의(마지막 등장 행)를 읽는다. 없으면 실패."""
    p = archive_path(condition)
    if not p.exists():
        raise SystemExit(f"원장 없음: {p} — 후보를 먼저 원장에 append 하라 (§5.2)")
    found = None
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("candidate_id") == cid:
            found = row
    if found is None:
        raise SystemExit(f"후보 {cid} 가 {p.name} 에 없음")
    return found


def resolve_builder(harness: dict):
    """원장의 harness 필드 → 실제 빌더 함수. 추측 금지(§5.1) — 명시 필드만."""
    module = importlib.import_module(harness["builder_module"])
    fn = getattr(module, harness["builder_fn"])
    kwargs = harness.get("builder_kwargs", {})
    model = harness["model"]
    return fn, kwargs, model


def prompt_sha256(fn, kwargs, units) -> str:
    """고정 unit(정렬 첫 번째)에 빌더를 적용한 프롬프트의 해시 — §5.1 재측정 방지."""
    return hashlib.sha256(fn(units[0], **kwargs).encode("utf-8")).hexdigest()


def guard() -> None:
    r = subprocess.run([sys.executable, str(GATE / "scripts/mh_guard.py")],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip(), file=sys.stderr)
        raise SystemExit(r.returncode)


def run_one(cid: str, condition: str, run: str, fn, kwargs, model,
            expected_sha: str | None) -> None:
    units = load_units()
    actual_sha = prompt_sha256(fn, kwargs, units)
    if expected_sha and actual_sha != expected_sha:
        raise SystemExit(
            f"prompt_sha256 불일치: 원장={expected_sha[:12]}… "
            f"실측={actual_sha[:12]}… — 원장의 harness 정의와 실물 빌더가 다르다")

    out = GATE / f"scripts/mh_{cid}_{run}.jsonl"
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["id"])
            except Exception:  # noqa: BLE001
                pass
    todo = [u for u in units if u["id"] not in done]
    print(f"{cid}/{condition}/{run}: 대상 {len(units)}건, "
          f"완료 {len(done)}, 남은 {len(todo)}", flush=True)

    n = 0
    with open(out, "a", encoding="utf-8") as fh:
        for u in todo:
            prompt = fn(u, **kwargs)
            t0 = time.time()
            label, rationale = call(prompt)
            fh.write(json.dumps({
                "id": u["id"], "run": run, "label": label,
                "rationale": rationale, "human": u["human"],
                "n_siblings": len(u["siblings"]),
                "candidate_id": cid, "condition": condition,
                "model": model, "prompt_sha256": actual_sha,
                "elapsed": round(time.time() - t0, 1),
            }, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            if n % 10 == 0 or n == len(todo):
                print(f"[{n}/{len(todo)}] {u['id']} human={u['human']} -> {label}",
                      flush=True)
    print(f"DONE {cid}/{run}: 신규 {n}건 -> {out.name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate-id", required=True)
    ap.add_argument("--condition", required=True, choices=CONDITIONS)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--run", choices=RUNS)
    g.add_argument("--all-runs", action="store_true")
    args = ap.parse_args()

    guard()
    row = load_candidate(args.condition, args.candidate_id)
    fn, kwargs, model = resolve_builder(row["harness"])
    expected_sha = row["harness"].get("prompt_sha256") or None

    runs = RUNS if args.all_runs else (args.run,)
    for run in runs:
        run_one(args.candidate_id, args.condition, run, fn, kwargs, model,
                expected_sha)


if __name__ == "__main__":
    main()
