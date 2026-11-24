"""부속서11 — E7: 판정기 2종(sonnet·opus) × 하네스 2종(c000·c401), E6 문제집 1,252단위, 1판.
  MH_EXP=E6 python sfk_e7.py arm <model> <cid> [--workers N]   # 이어받기 가능
  MH_EXP=E6 python sfk_e7.py verdict
"""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
from mh_exp import EXP, TAG  # noqa: E402

MODELS = ("claude-sonnet-5-5", "claude-opus-5-5")
CIDS = ("c000", "c401")
lock = threading.Lock()


def out_path(model: str, cid: str) -> Path:
    return S / f"mh_{TAG}arm_{model}_{cid}_run1.jsonl"


def arm(model: str, cid: str, workers: int) -> None:
    from instrument_check_run import call, load_units
    from mh_guard import ledger_lock
    from mh_run_candidate import guard, load_candidate, prompt_sha256, resolve_builder
    assert EXP == "E6" and model in MODELS and cid in CIDS, (EXP, model, cid)
    guard()
    fn, kw, _ = resolve_builder(load_candidate("C2", cid)["harness"])   # 원장 등록본 그대로(모델만 교체)
    units = load_units()
    sha = prompt_sha256(fn, kw, units)
    out = out_path(model, cid)
    with ledger_lock(out):
        done = {json.loads(l)["id"] for l in out.open(encoding="utf-8")} if out.exists() else set()
        todo = [u for u in units if u["id"] not in done]
        print(f"[E7] {model} {cid}: 대상 {len(units)}, 완료 {len(done)}, 남은 {len(todo)}", flush=True)

        def one(u):
            t0 = time.time()
            label, why = call(fn(u, **kw), model)
            with lock, out.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"id": u["id"], "run": "run1", "label": label, "rationale": why, "human": None,
                                    "candidate_id": cid, "condition": "C2", "model": model, "prompt_sha256": sha,
                                    "elapsed": round(time.time() - t0, 1)}, ensure_ascii=False) + "\n")
        with ThreadPoolExecutor(workers) as ex:
            for i, f in enumerate([ex.submit(one, u) for u in todo], 1):
                f.result()                                   # fail-closed
                if i % 50 == 0 or i == len(todo):
                    print(f"[{i}/{len(todo)}]", flush=True)


def units_of(model: str, cid: str) -> dict:
    import mh_objectives as M
    from mh_exp import SF300
    labels = M.load_labels(S.parent / SF300)
    rows = [json.loads(l) for l in out_path(model, cid).open(encoding="utf-8")]
    got = {r["id"]: r for r in rows}
    assert len(got) == len(rows) == len(labels), f"{model} {cid}: 행 {len(rows)} 고유 {len(got)} 라벨 {len(labels)}"
    assert {r["model"] for r in rows} == {model}, "판정기 혼입"
    return {i: M.Unit(i, labels[i], got[i]["label"]) for i in sorted(labels)}


def verdict() -> None:
    """§4. 모델 2개 = 가족 2 → Holm: 97.5% 로 먼저 확정되는 모델은 97.5%, 나머지는 95%."""
    import mh_objectives as M
    from sfk_e5 import classify, paired
    assert EXP == "E6"
    res = {}
    for m in MODELS:
        b, o = units_of(m, "c000"), units_of(m, "c401")
        r, n = paired("c401", b, o)
        res[m] = r
        print(f"{m}: c000 {M.recall_of(b.values()):.3f}/{M.specificity_of(b.values()):.3f} → "
              f"c401 {M.recall_of(o.values()):.3f}/{M.specificity_of(o.values()):.3f} (군집 {n}, "
              f"UNRESOLVED {sum(u.maj not in ('SUPPORTED', 'CONTRADICTED', 'INSUFFICIENT') for u in o.values())})")
        print("   " + "; ".join(f"{ax} Δ {d*100:+.1f}%p 95%[{lo*100:+.1f}, {hi*100:+.1f}] 97.5%[{l2*100:+.1f}, {h2*100:+.1f}]"
                                 for ax, (d, lo, hi, l2, h2) in r.items()))
    strict = {m: classify(r, 3, 4) for m, r in res.items()}
    first = [m for m, v in strict.items() if v != "판정 불가"]
    for m, r in res.items():
        v = strict[m] if first else classify(r, 3, 4)
        if first and m not in first:
            v = classify(r, 1, 2)
        print(f"판정 {m}: {v}  (Holm: {'97.5%' if (m in first or not first) else '95%'})")


if __name__ == "__main__":
    if sys.argv[1] == "arm":
        arm(sys.argv[2], sys.argv[3], int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 3)
    else:
        verdict()
