"""[사후 탐색 — 판정 무관] E4↔E5 같은 잣대 비교 + 처리시간 축 — 부속서9 §0. 0콜.

같은 잣대 = 두 실험 모두 군집(qid) 재표집 짝 부트스트랩(B=2,000, seed 20261124), 95% 백분위 구간.
처리시간 = 원자료 `elapsed`(CLI 호출 벽시계 초)의 단위별 3판 평균. 🔴 토큰 수가 아니며, 판 병렬 실행·한도 대기가
섞여 있어 비용 지표로는 참고치다.

usage:  python e4_e5_compare.py
"""
from __future__ import annotations

import json
import os
import random
import statistics
import sys
from pathlib import Path

S = Path(__file__).resolve().parent
os.environ.setdefault("MH_EXP", "E5")
sys.path.insert(0, str(S))
import mh_objectives as M  # noqa: E402

SEED, B = 20261124, 2000
EXPS = {"E4": ("e4_", "sf300_label_set_v2.json"), "E5": ("e5_", "sfk_main.json")}
CANDS = ("c000", "c301", "c302")


def load(tag: str, labels_file: str, cid: str):
    labels = M.load_labels(S / labels_file)
    files = [S / f"mh_{tag}{cid}_run{r}.jsonl" for r in (1, 2, 3)]
    per, _ = M.load_runs([str(p) for p in files])
    us = {u.id: u for u in M.build_units(per, labels)}
    el: dict[str, list[float]] = {}
    for p in files:
        for line in p.open(encoding="utf-8"):
            r = json.loads(line)
            el.setdefault(r["id"], []).append(float(r["elapsed"]))
    return us, {i: statistics.mean(v) for i, v in el.items()}


def ci(xs: list[float]) -> tuple[float, float]:
    xs = sorted(xs)
    return xs[int(.025 * len(xs))], xs[min(len(xs) - 1, int(.975 * len(xs)))]


def main() -> None:
    out = {}
    for exp, (tag, lf) in EXPS.items():
        data = {c: load(tag, lf, c) for c in CANDS}
        base_u, base_t = data["c000"]
        by: dict[str, list[str]] = {}
        for i, u in base_u.items():
            by.setdefault(u.qid, []).append(i)
        cl = sorted(by)
        res = {"n_clusters": len(cl), "n_units": len(base_u), "abs": {}, "delta": {}}
        for c in CANDS:
            us, t = data[c]
            res["abs"][c] = {"recall": round(M.recall_of(us.values()), 4),
                             "specificity": round(M.specificity_of(us.values()), 4),
                             "sec_per_call": round(statistics.mean(t.values()), 2)}
        rng = random.Random(SEED)
        draws = {c: {"recall": [], "specificity": [], "sec": []} for c in CANDS[1:]}
        for _ in range(B):
            sel = [i for k in (rng.choice(cl) for _ in cl) for i in by[k]]
            b_r = M.recall_of(base_u[i] for i in sel)
            b_s = M.specificity_of(base_u[i] for i in sel)
            b_t = statistics.mean(base_t[i] for i in sel)
            for c in CANDS[1:]:
                us, t = data[c]
                r, s = M.recall_of(us[i] for i in sel), M.specificity_of(us[i] for i in sel)
                if None not in (r, s, b_r, b_s):
                    draws[c]["recall"].append(r - b_r)
                    draws[c]["specificity"].append(s - b_s)
                draws[c]["sec"].append(statistics.mean(t[i] for i in sel) - b_t)
        for c in CANDS[1:]:
            res["delta"][c] = {ax: [round(x, 4) for x in ci(v)] for ax, v in draws[c].items()}
            res["delta"][c]["width_recall_pp"] = round(100 * (res["delta"][c]["recall"][1] - res["delta"][c]["recall"][0]), 1)
        out[exp] = res
    (S / "e4_e5_compare.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
