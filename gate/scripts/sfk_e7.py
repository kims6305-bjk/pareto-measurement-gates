"""부속서11 — E7: 판정기 2종(sonnet·opus) × 하네스 2종(c000·c401), E6 문제집 1,252단위, 1판.
부속서12 — E8P/E8: 같은 설계를 SF-K v5 에서. 판정기에 haiku 추가(재현 확인용, 확증 가족 밖).
  MH_EXP=E8P python sfk_e7.py level                         # §3 해상도·바닥 게이트(c000 만)
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

STRONG = ("claude-opus-5-5",) if EXP == "E8" else ("claude-sonnet-5-5", "claude-opus-5-5")   # Holm 확증 가족 (E8 = 부속서12 추기1 게이트 통과분)
MODELS = STRONG + (("claude-haiku-5-5",) if EXP in ("E8P", "E8") else ())
CIDS = ("c000", "c401")
lock = threading.Lock()


def out_path(model: str, cid: str) -> Path:
    return S / f"mh_{TAG}arm_{model}_{cid}_run1.jsonl"


def arm(model: str, cid: str, workers: int) -> None:
    from instrument_check_run import call, load_units
    from mh_guard import ledger_lock
    from mh_run_candidate import guard, load_candidate, prompt_sha256, resolve_builder
    assert EXP in ("E6", "E8P", "E8") and model in MODELS and cid in CIDS, (EXP, model, cid)
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
    assert EXP in ("E6", "E8")
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
    for m in set(MODELS) - set(STRONG):          # 부속서12 §4: haiku = 재현 확인, 95% 단독
        print(f"재현 {m}: {classify(res.pop(m), 1, 2)}  (확증 가족 밖, 95%)")
    hi = (3, 4) if len(res) > 1 else (1, 2)      # 가족 1 이면 Holm = 95%
    strict = {m: classify(r, *hi) for m, r in res.items()}
    first = [m for m, v in strict.items() if v != "판정 불가"]
    for m, r in res.items():
        v = strict[m] if first else classify(r, *hi)
        if first and m not in first:
            v = classify(r, 1, 2)
        print(f"판정 {m}: {v}  (Holm: {('97.5%' if hi == (3, 4) else '95%') if (m in first or not first) else '95%'})")


def level() -> None:
    """부속서12 §3 (결과 전 고정). c000 1판. 해상도: 강한 판정기 recall ≤ 0.95 인 수 → 본측정 판정기 결정.
    바닥: haiku min(recall, specificity) ≥ 0.60."""
    import mh_objectives as M
    from mh_exp import SF300
    assert EXP == "E8P"
    kinds = {u["id"]: u["kind"] for u in json.loads((S.parent / SF300).read_text(encoding="utf-8"))}
    ok = []
    for m in MODELS:
        us = units_of(m, "c000")
        r, s = M.recall_of(us.values()), M.specificity_of(us.values())
        by = {}
        for u in us.values():
            k = by.setdefault(kinds[u.id], [0, 0])
            k[0] += u.is_flagged if u.is_problem else not u.is_flagged
            k[1] += 1
        if m in STRONG:
            tag = "해상도 PASS" if r <= 0.95 else "CEILING"
            ok += [m] if r <= 0.95 else []
        else:
            tag = "바닥 PASS" if min(r, s) >= 0.60 else "FLOOR"
        print(f"{m}: recall {r:.3f} specificity {s:.3f} {tag}  유형별 {dict((k, f'{a}/{b}') for k, (a, b) in sorted(by.items()))}")
    print(f"본측정 확증 판정기: {ok or '없음 → v5 천장, 본측정 보류'}")


if __name__ == "__main__":
    if sys.argv[1] == "level":
        level()
    elif sys.argv[1] == "arm":
        arm(sys.argv[2], sys.argv[3], int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 3)
    else:
        verdict()
