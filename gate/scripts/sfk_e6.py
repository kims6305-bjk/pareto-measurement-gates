"""부속서9 E6P — 강한 모델 팔(1판) 러너 + 수준 게이트 (판정기 3판은 mh_run_candidate.py 가 한다).

  MH_EXP=E6P python sfk_e6.py arm claude-opus-5-5 [--workers 4]   # c000 프롬프트 그대로, 200단위 1판, 이어하기
  MH_EXP=E6P python sfk_e6.py level                                # §3 수준 게이트 (0콜)

팔 = claude-opus-5-5 · claude-sonnet-5-5 (claude -p) / gpt-6-astra · gpt-6.2-sol (codex exec, reasoning medium).
원자료 = mh_e6p_arm_<model>_c000_run1.jsonl. 판정 파싱은 instrument_check_run.parse 그대로.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
from mh_exp import EXP, TAG  # noqa: E402

ARMS = ("claude-opus-5-5", "claude-sonnet-5-5", "gpt-6-astra", "gpt-6.2-sol")
CEIL, FLOOR, STRONG_CEIL = 0.93, 0.70, 0.95      # §3 — 결과 열람 전 고정
lock = threading.Lock()


def out_path(model: str) -> Path:
    return S / f"mh_{TAG}arm_{model}_c000_run1.jsonl"


def call_codex(prompt: str, model: str) -> tuple[str, str]:
    from instrument_check_run import parse
    with tempfile.NamedTemporaryFile("r", suffix=".txt") as o:
        p = subprocess.run([shutil.which("codex") or "codex", "exec", "-m", model, "--skip-git-repo-check",
                            "-s", "read-only", "--ephemeral", "-c", "model_reasoning_effort=medium", "-o", o.name, "-"],
                           input=prompt, capture_output=True, text=True, timeout=300)
        raw = Path(o.name).read_text(encoding="utf-8").strip()
    if re.search(r"usage limit|rate.?limit|hit your .{0,30}limit", (p.stderr or "")[-2000:] + raw, re.I) and not raw:
        raise SystemExit(f"codex rate_limit: {(p.stderr or '')[-200:]}")
    if p.returncode != 0 or not raw:                  # 호출 실패는 판정이 아니다 — 쓰지 않고 멈춘다
        raise SystemExit(f"codex 실패 exit={p.returncode}: {(p.stderr or '')[-200:]}")
    return parse(raw)


def call_hermes(prompt: str, model: str) -> tuple[str, str]:
    """gpt1 레인(Hermes openai-codex pool, --safe-mode). codex CLI(gpt2) 크레딧 소진 뒤 이어받기 — 부속서9 추기1.
    🔴 이 레인은 429 면 조용히 다른 모델로 폴백하고 rc0 을 낸다 → 세션 실제 모델을 state.db 에서 대조, 다르면 멈춘다."""
    import os
    import sqlite3
    from instrument_check_run import parse
    p = subprocess.run([os.path.expanduser("~/.local/bin/hermes"), "--safe-mode", "chat", "--provider", "openai-codex",
                        "-m", model, "-t", "todo", "--reasoning", "medium", "--query-file", "-", "--oneshot", "-Q"],
                       input=prompt, capture_output=True, text=True, timeout=400)
    sid = re.findall(r"session_id:\s*(\S+)", p.stderr or "")
    if p.returncode != 0 or not p.stdout.strip() or not sid:
        raise SystemExit(f"hermes 실패 rc={p.returncode}: {(p.stderr or '')[-200:]}")
    db = sqlite3.connect(f"file:{os.path.expanduser('~/.hermes/state.db')}?mode=ro", uri=True)
    got = db.execute("select model from session_model_usage where session_id=? and task='' and api_call_count>0",
                     (sid[-1],)).fetchall()
    if [r[0] for r in got] != [model]:
        raise SystemExit(f"모델 불일치(폴백 의심) {sid[-1]}: {got}")
    return parse(p.stdout)


LANE = __import__("os").environ.get("E6_GPT_LANE", "codex")   # codex = gpt2(CLI), hermes = gpt1(pool)


def arm(model: str, workers: int) -> None:
    from instrument_check_run import call, load_units
    from mh_guard import ledger_lock
    from mh_run_candidate import guard, load_candidate, prompt_sha256, resolve_builder
    assert model in ARMS, model
    guard()
    fn, kw, _ = resolve_builder(load_candidate("C2", "c000")["harness"])
    units = load_units()
    sha = prompt_sha256(fn, kw, units)
    out = out_path(model)
    with ledger_lock(out):
        done = {json.loads(l)["id"] for l in out.open(encoding="utf-8")} if out.exists() else set()
        todo = [u for u in units if u["id"] not in done]
        print(f"[{EXP}] arm {model}: 대상 {len(units)}, 완료 {len(done)}, 남은 {len(todo)}", flush=True)

        def one(u):
            t0 = time.time()
            prompt = fn(u, **kw)
            gpt = model.startswith("gpt")
            label, why = ((call_hermes if LANE == "hermes" else call_codex)(prompt, model) if gpt
                          else call(prompt, model))
            with lock, out.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"id": u["id"], "run": "run1", "label": label, "rationale": why, "human": None,
                                    "candidate_id": "c000", "condition": "C2", "model": model,
                                    "prompt_sha256": sha, "elapsed": round(time.time() - t0, 1),
                                    **({"lane": LANE} if gpt else {})},
                                   ensure_ascii=False) + "\n")
        with ThreadPoolExecutor(workers) as ex:
            for i, f in enumerate([ex.submit(one, u) for u in todo], 1):
                f.result()                            # 첫 실패에서 멈춘다(fail-closed)
                if i % 20 == 0 or i == len(todo):
                    print(f"[{i}/{len(todo)}]", flush=True)


def axes(units) -> tuple[float, float]:
    import mh_objectives as M
    return M.recall_of(units), M.specificity_of(units)


def level() -> None:
    """§3. 판정기(haiku c000 3판 다수결) 게이트 + 강한 모델 팔(1판) 게이트 + 유형별 검출률(탐색, 판정 무관)."""
    import mh_objectives as M
    from mh_exp import SF300
    labels = M.load_labels(S.parent / SF300)
    kinds = {u["id"]: u["kind"] for u in json.loads((S.parent / SF300).read_text(encoding="utf-8"))}
    per, _ = M.load_runs([str(S / f"mh_{TAG}c000_run{r}.jsonl") for r in (1, 2, 3)])
    rows = {"claude-haiku-5-5 (c000, 3판)": M.build_units(per, labels)}
    for m in ARMS:
        got = {json.loads(l)["id"]: json.loads(l)["label"] for l in out_path(m).open(encoding="utf-8")}
        assert set(got) == set(labels), f"{m}: 미완 {len(set(labels) - set(got))}"   # fail-closed
        rows[f"{m} (c000, 1판)"] = [M.Unit(i, labels[i], got[i]) for i in sorted(labels)]
    assert len(rows["claude-haiku-5-5 (c000, 3판)"]) == len(labels), "판정기 3판 미완"
    strong_ok = 0
    for name, us in rows.items():
        r, s = axes(us)
        by = {}
        for k in sorted(set(kinds.values())):
            ks = [u for u in us if kinds[u.id] == k]
            ok = sum((u.is_flagged if u.is_problem else not u.is_flagged) for u in ks)
            by[k] = f"{ok}/{len(ks)}"
        tag = ""
        if name.startswith("claude-haiku"):
            tag = ("PASS" if max(r, s) <= CEIL and min(r, s) >= FLOOR
                   else "CEILING" if max(r, s) > CEIL else "FLOOR")
        elif min(r, s) <= STRONG_CEIL:
            strong_ok += 1
        print(f"{name}: recall {r:.3f} specificity {s:.3f} {tag}  유형별 {by}")
    print(f"강한 모델 중 min축 ≤ {STRONG_CEIL}: {strong_ok}/{len(ARMS)} → "
          + ("2요인 본측정 자격(운영자 결정)" if strong_ok >= 2 else "2요인 자격 없음 — 판정기 1요인"))


if __name__ == "__main__":
    if EXP != "E6P":
        raise SystemExit("MH_EXP=E6P 로 실행")
    if sys.argv[1] == "arm":
        arm(sys.argv[2], int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4)
    else:
        level()
