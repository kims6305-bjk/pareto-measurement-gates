"""E4 사후 탐색 진단 (0콜) — 부속서7 추기 2. **판정에 쓰지 않는다.**

①짝비교(같은 문항 군집 재표집) 차이 CI vs 단독 CI ②판 간 뒤집힘 vs 후보 교체로 바뀐 단위
③판 수 R 을 늘렸을 때 짝비교 CI 폭 모의(단위별 문제판정 확률 = k/3, Jeffreys (k+.5)/4 두 가지).
실행: cd gate && MH_EXP=E4 .venv/bin/python scripts/e4_posthoc_diag.py
"""
import collections, json, os, random, sys
from pathlib import Path

os.environ.setdefault("MH_EXP", "E4")
S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
import mh_objectives as M  # noqa: E402

CANDS = ("c000", "c301", "c302")
labels = M.load_labels(S / "sf300_label_set_v2.json")
U, K = {}, {}
for c in CANDS:
    files = [str(S / f"mh_e4_{c}_run{r}.jsonl") for r in (1, 2, 3)]
    per, _ = M.load_runs(files)
    U[c] = {u.id: u for u in M.build_units(per, labels)}
    k = collections.Counter()
    for f in files:
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            k[d["id"]] += d["label"] in M.PROBLEM
    K[c] = k
ids = sorted(U["c000"])
assert len(ids) == 300 and all(set(U[c]) == set(ids) for c in CANDS)
byq = collections.defaultdict(list)
for i in ids:
    byq[i.split("-")[0]].append(i)
qids = sorted(byq)
in_axis = {"recall": lambda i: labels[i] in M.HUMAN_PROBLEM, "specificity": lambda i: labels[i] == "S"}
fn = {"recall": M.recall_of, "specificity": M.specificity_of}


def resample(rng):
    return [i for q in (rng.choice(qids) for _ in qids) for i in byq[q]]


def ci(xs):
    xs = sorted(xs)
    return xs[int(.025 * len(xs))], xs[int(.975 * len(xs))]


print(f"독립 군집(qid) {len(qids)}, 단위 {len(ids)}")
for c in CANDS:
    unstable = sum(1 for i in ids if 0 < K[c][i] < 3)
    print(f"[②] {c}: 3판 판정 갈린 단위 {unstable}/300")

rng = random.Random(20260730)
for cand in CANDS[1:]:
    for ax in ("recall", "specificity"):
        ds, base = [], []
        for _ in range(2000):
            sel = resample(rng)
            a = fn[ax]([U[cand][i] for i in sel]); b = fn[ax]([U["c000"][i] for i in sel])
            if a is not None and b is not None:
                ds.append(a - b); base.append(b)
        d0 = fn[ax](U[cand].values()) - fn[ax](U["c000"].values())
        lo, hi = ci(ds); blo, bhi = ci(base)
        flips = sum(1 for i in ids if in_axis[ax](i) and U[cand][i].is_flagged != U["c000"][i].is_flagged)
        print(f"[①] {cand} {ax}: 차이 {d0*100:+.1f}%p 짝CI [{lo*100:+.1f},{hi*100:+.1f}] 폭 {(hi-lo)*100:.1f}"
              f" | c000 단독 폭 {(bhi-blo)*100:.1f} | 후보 교체로 바뀐 단위 {flips}")


def sim_width(cand, ax, R, pf, B=800):
    r = random.Random(1); ds = []
    P = {c: {i: pf(K[c][i]) for i in ids} for c in ("c000", cand)}
    for _ in range(B):
        pool = [i for i in resample(r) if in_axis[ax](i)]
        def rate(c):
            f = sum(1 for i in pool if sum(r.random() < P[c][i] for _ in range(R)) * 2 > R) / len(pool)
            return f if ax == "recall" else 1 - f
        ds.append(rate(cand) - rate("c000"))
    lo, hi = ci(ds); return (hi - lo) * 100


for name, pf in {"k/3": lambda k: k / 3, "jeffreys": lambda k: (k + .5) / 4}.items():
    for cand in CANDS[1:]:
        for ax in ("recall", "specificity"):
            print(f"[③] {name} {cand} {ax} 짝CI 폭: " +
                  " ".join(f"R{R}={sim_width(cand, ax, R, pf):.1f}" for R in (3, 5, 9, 99)))
