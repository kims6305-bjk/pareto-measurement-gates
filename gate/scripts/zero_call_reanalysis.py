#!/usr/bin/env python3
"""0콜 재분석 (2026-10-06) — 기존 원자료만 읽어 새 측정을 낸다. LLM 호출 없음.

  1. 판정기 판간 일치도 (Fleiss κ · 만장일치율) + 조건 A/B 다수결 일치도 (Cohen κ)
  2. c000 recall/precision 의 claim(iid) vs qid-클러스터 부트스트랩 CI + 설계효과
  3. 그림 F1~F4 — 수치는 전부 results.json 에서 읽고, 그린 값(artist)을 JSON 과 대조한다

정의는 새로 만들지 않는다: 다수결·축·리샘플러·RNG 는 mh_objectives.py, Phase 3 다수결·Wilson 은
phase3_score.py 를 import 해 쓴다(읽기 전용).

usage (gate/ 에서, 시스템 python3 — matplotlib 이 uv venv 에 없다):
    python3 scripts/zero_call_reanalysis.py            # results.json + figures 생성
    python3 scripts/zero_call_reanalysis.py --selftest # 재계산 후 저장본과 비교, 드리프트면 exit 1
"""
from __future__ import annotations

import collections
import json
import re
import statistics
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GATE = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import mh_objectives as mo  # noqa: E402
import phase3_score as p3   # noqa: E402

OUT = GATE / "reanalysis_20261006"
FIG = OUT / "figures"
RESULTS = OUT / "results.json"
ARCHIVE = SCRIPTS / "archive_sonnet46_20261006"   # c000 만 유효. mh_ic1_* 는 무효 — 읽지 않는다
LABELS = SCRIPTS / "phase1_human_label_sheet.xlsx"
B_NEW = 10_000
SEED = mo.SEED
CATS = ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT", "UNRESOLVED")


# ── 일치도 ──────────────────────────────────────────────────────────────────
def fleiss(rows: list[list[str]], cats) -> float | None:
    """rows = 단위별 평정 라벨 목록(평정자 수 동일). P_e == 1 이면 미정의(None)."""
    n = len(rows[0])
    N = len(rows)
    assert all(len(r) == n and set(r) <= set(cats) for r in rows), "평정자 수 불일치 또는 범주 밖 라벨"
    counts = [[r.count(c) for c in cats] for r in rows]
    p_j = [sum(c[j] for c in counts) / (N * n) for j in range(len(cats))]
    P_i = [(sum(x * x for x in c) - n) / (n * (n - 1)) for c in counts]
    P_bar, P_e = sum(P_i) / N, sum(p * p for p in p_j)
    return None if abs(1 - P_e) < 1e-12 else (P_bar - P_e) / (1 - P_e)


def cohen(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if abs(1 - pe) < 1e-12 else (po - pe) / (1 - pe)


def binarize(labels):
    return ["P" if x in mo.PROBLEM else "N" for x in labels]


def agreement(per_labels: dict[str, list[str]]) -> dict:
    rows = [per_labels[k] for k in sorted(per_labels)]
    assert rows and all(len(r) == 3 for r in rows), "3판 아님"
    k4, k2 = fleiss(rows, CATS), fleiss([binarize(r) for r in rows], ("P", "N"))
    return {
        "n_units": len(rows),
        "n_unanimous": sum(len(set(r)) == 1 for r in rows),
        "pct_unanimous": round(sum(len(set(r)) == 1 for r in rows) / len(rows), 4),
        "n_unanimous_binary": sum(len(set(binarize(r))) == 1 for r in rows),
        "fleiss_kappa_4cat": None if k4 is None else round(k4, 4),
        "fleiss_kappa_binary": None if k2 is None else round(k2, 4),
        "label_totals": dict(sorted(collections.Counter(x for r in rows for x in r).items())),
    }


def read_runs(paths) -> dict[str, list[str]]:
    per = collections.defaultdict(dict)
    for f in paths:
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                assert d["run"] not in per[d["id"]], f"중복 {d['id']}/{d['run']}"
                per[d["id"]][d["run"]] = d["label"]
    return {k: [v[r] for r in sorted(v)] for k, v in per.items()}


# ── 부트스트랩 (mo.bootstrap 과 같은 순서로 표본을 뽑되 표본 자체를 보관) ──────
def boot_samples(units, mode: str, b: int, seed: int = SEED) -> dict[str, list[float]]:
    us = sorted(units, key=lambda u: u.id)
    rng = mo._Rng(seed)
    if mode == "claim":
        draw = lambda: mo._resample_claim(us, rng)  # noqa: E731
    else:
        g = collections.defaultdict(list)
        for u in us:
            g[u.qid].append(u)
        cl = tuple((q, tuple(g[q])) for q in sorted(g))
        draw = lambda: mo._resample_qid(cl, rng)  # noqa: E731
    out = {a: [] for a in mo.AXES}
    for _ in range(b):
        s = draw()
        for a in mo.AXES:
            v = mo._AXIS_FN[a](s)
            if v is not None:
                out[a].append(v)
    return out


def ci(xs):
    return [round(mo.percentile(xs, mo.CI_LO_PCT), 4), round(mo.percentile(xs, mo.CI_HI_PCT), 4)]


def cluster_block(units, b: int) -> dict:
    res = {}
    samp = {m: boot_samples(units, m, b) for m in ("claim", "qid")}
    for a in mo.AXES:
        vc, vq = statistics.pvariance(samp["claim"][a]), statistics.pvariance(samp["qid"][a])
        res[a] = {
            "value": round(mo._AXIS_FN[a](units), 4),
            "ci_iid": ci(samp["claim"][a]), "ci_qid": ci(samp["qid"][a]),
            "sd_iid": round(vc ** 0.5, 4), "sd_qid": round(vq ** 0.5, 4),
            "design_effect": round(vq / vc, 4),
            "n_valid": {"iid": len(samp["claim"][a]), "qid": len(samp["qid"][a])},
        }
    return res


def c000_units(pattern: str):
    labels = mo.load_labels(LABELS)
    per, files = mo.load_runs([pattern])
    mo.validate_run_ledger(per, labels, "c000")
    return mo.build_units(per, labels), per, files


def c000_block(pattern: str, archived_json: Path | None) -> dict:
    units, per, files = c000_units(pattern)
    c = mo.counts(units)
    sizes = collections.Counter(u.qid for u in units)
    prob_per_q = collections.Counter(u.qid for u in units if u.is_problem)
    conf = collections.defaultdict(lambda: collections.Counter())
    for u in units:
        conf[u.human][u.maj] += 1
    tp = c["n_detected"]
    fp = c["n_flagged"] - tp
    fn = c["n_problem"] - tp
    blk = {
        "raw_files": files,
        "counts": c,
        "agreement_3run": agreement({k: [r["label"] for r in sorted(v, key=lambda r: r["run"])]
                                     for k, v in per.items()}),
        "confusion_human_x_judgeMajority": {h: dict(sorted(conf[h].items())) for h in sorted(conf)},
        "binary_2x2": {"TP": tp, "FP": fp, "FN": fn, "TN": c["n_units"] - tp - fp - fn},
        "clusters": {
            "n_units": len(units), "n_clusters": len(sizes),
            "size_distribution": {str(k): v for k, v in sorted(collections.Counter(sizes.values()).items())},
            "n_clusters_with_problem": len(prob_per_q),
            "problems_per_problem_cluster": {str(k): v for k, v in
                                             sorted(collections.Counter(prob_per_q.values()).items())},
        },
        "bootstrap_B10000": cluster_block(units, B_NEW),
    }
    # 재현 검사: mo.bootstrap (B=2000) == 내 표본기 (B=2000) == 보관 objectives.json
    old = {m: mo.bootstrap(units, m, b=mo.B, seed=SEED) for m in ("claim", "qid")}
    mine = {m: boot_samples(units, m, mo.B) for m in ("claim", "qid")}
    rep = {}
    for a in mo.AXES:
        r = {"mo_ci_claim": old["claim"][a]["ci"], "mo_ci_qid": old["qid"][a]["ci"],
             "resampler_ci_claim": ci(mine["claim"][a]), "resampler_ci_qid": ci(mine["qid"][a])}
        r["resampler_matches_mo"] = (r["mo_ci_claim"] == r["resampler_ci_claim"]
                                     and r["mo_ci_qid"] == r["resampler_ci_qid"])
        if archived_json:
            arch = json.loads(archived_json.read_text(encoding="utf-8"))["objectives"][a]
            r["archived_ci_claim"], r["archived_ci_qid"] = arch["ci_claim"], arch["ci_qid"]
            r["matches_archived"] = (arch["ci_claim"] == r["mo_ci_claim"]
                                     and arch["ci_qid"] == r["mo_ci_qid"]
                                     and arch["value"] == round(mo._AXIS_FN[a](units), 4))
        rep[a] = r
    blk["reproduction_B2000"] = rep
    return blk


# ── Phase 3 ────────────────────────────────────────────────────────────────
def phase3_block() -> dict:
    out = {"model": "claude-sonnet-4-6"}
    raw = {}
    for cond in ("A", "B"):
        raw[cond] = read_runs(sorted(SCRIPTS.glob(f"phase3_judge_{cond}_run*.jsonl")))
        out[f"agreement_3run_{cond}"] = agreement(raw[cond])
    A, B = p3.load("A"), p3.load("B")
    rates = {}
    for cond, M in (("A", A), ("B", B)):
        maj = [v for v in M.values() if v["status"] == "majority"]
        k = sum(v["label"] in mo.PROBLEM for v in maj)
        lo, hi = p3.wilson(k, len(maj))
        rk = sum(x in mo.PROBLEM for r in raw[cond].values() for x in r)
        rn = sum(len(r) for r in raw[cond].values())
        rlo, rhi = p3.wilson(rk, rn)
        rates[cond] = {"majority": {"k": k, "n": len(maj), "rate": round(k / len(maj), 4),
                                    "wilson": [round(lo, 4), round(hi, 4)]},
                       "raw_rows": {"k": rk, "n": rn, "rate": round(rk / rn, 4),
                                    "wilson": [round(rlo, 4), round(rhi, 4)]},
                       "status_counts": dict(sorted(collections.Counter(v["status"] for v in M.values()).items()))}
    out["problem_rates"] = rates
    common = sorted(c for c in set(A) & set(B)
                    if A[c]["status"] == "majority" and B[c]["status"] == "majority")
    a4, b4 = [A[c]["label"] for c in common], [B[c]["label"] for c in common]
    k4, k2 = cohen(a4, b4), cohen(binarize(a4), binarize(b4))
    out["A_vs_B_majority"] = {
        "n_common_both_majority": len(common),
        "n_agree": sum(x == y for x, y in zip(a4, b4)),
        "pct_agree": round(sum(x == y for x, y in zip(a4, b4)) / len(common), 4),
        "cohen_kappa_4cat": None if k4 is None else round(k4, 4),
        "cohen_kappa_binary": None if k2 is None else round(k2, 4),
        "crosstab": {f"{x}->{y}": n for (x, y), n in sorted(collections.Counter(zip(a4, b4)).items())},
    }
    return out


# ── 사례 1 축 뒤집힘 (MEASUREMENT_FAILURES.md 표를 파싱) ──────────────────────
def axis_flip_block() -> dict:
    doc = (GATE / "MEASUREMENT_FAILURES.md").read_text(encoding="utf-8")
    sec = doc.split("## 사례 1.")[1].split("## 사례 2.")[0]
    rows = {}
    for key, pat in (("precision_slot", r"\| precision@10 \(슬롯 기준.*?\| \**([\d.]+)\** \| \**([\d.]+)\** \|"),
                     ("precision_unique", r"\| precision@10 \(고유문서 기준\) \| \**([\d.]+)\** \| \**([\d.]+)\** \|"),
                     ("distinct_correct_docs", r"\| \*\*distinct_correct_docs\*\* \| \**([\d.]+)\** \| \**([\d.]+)\** \|")):
        m = re.search(pat, sec)
        assert m, f"MEASUREMENT_FAILURES.md 사례 1 표 파싱 실패: {key}"
        off, on = float(m.group(1)), float(m.group(2))
        rows[key] = {"off": off, "on": on, "delta": round(on - off, 4),
                     "rel_change": round((on - off) / off, 4)}
    return {"source": "MEASUREMENT_FAILURES.md 사례 1 표 (dedup OFF→ON)", "axes": rows}


def compute() -> dict:
    other = {}
    for name, pat in (("instrument_check", "instrument_check_run*.jsonl"),
                      ("sidecheck_scifact", "sidecheck_run*.jsonl"),
                      ("sidecheck2_klue", "sidecheck2_run*.jsonl")):
        other[name] = agreement(read_runs(sorted(SCRIPTS.glob(pat))))
    return {
        "meta": {"llm_calls": 0, "seed": SEED, "B": B_NEW, "ci": "percentile 2.5/97.5",
                 "cluster_unit": "qid = id.split('-')[0] (mh_objectives.Unit)",
                 "labels": LABELS.name, "labels_sha256": mo.sha256_file(LABELS)},
        "phase3": phase3_block(),
        "c000_archive_sonnet46": c000_block(str(ARCHIVE / "mh_c000_run*.jsonl"),
                                            ARCHIVE / "mh_c000_objectives.json"),
        "instrument_check_sonnet46": c000_block(str(SCRIPTS / "instrument_check_run*.jsonl"), None),
        "other_3run_agreement": other,
        "axis_flip_case1": axis_flip_block(),
    }


# ── 그림 ───────────────────────────────────────────────────────────────────
def figures(R: dict) -> dict:
    """그리고, 실제 artist 에서 읽은 값을 돌려준다(검사용)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    names = {f.name for f in font_manager.fontManager.ttflist}
    for f in ("AppleGothic", "Apple SD Gothic Neo"):
        if f in names:
            plt.rcParams["font.family"] = f
            break
    plt.rcParams["axes.unicode_minus"] = False
    FIG.mkdir(parents=True, exist_ok=True)
    drawn = {}

    def err_bars(ax, xs, vals, cis, color, label=None):
        lo = [v - c[0] for v, c in zip(vals, cis)]
        hi = [c[1] - v for v, c in zip(vals, cis)]
        eb = ax.errorbar(xs, vals, yerr=[lo, hi], fmt="o", color=color, capsize=6, label=label, ms=8)
        seg = eb.lines[2][0].get_segments()
        return {"y": [round(float(y), 4) for y in eb.lines[0].get_ydata()],
                "ci": [[round(float(s[0][1]), 4), round(float(s[1][1]), 4)] for s in seg]}

    # F1 Phase 3 A vs B 문제판정률 + Wilson
    pr = R["phase3"]["problem_rates"]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    d1 = {}
    for off, kind, col, lab in ((-0.1, "majority", "#1f4e79", "3판 다수결 단위"),
                                (0.1, "raw_rows", "#c55a11", "판×단위 원자료 행")):
        vals = [pr[c][kind]["rate"] for c in ("A", "B")]
        d1[kind] = err_bars(ax, [0 + off, 1 + off], vals, [pr[c][kind]["wilson"] for c in ("A", "B")], col, lab)
        for x, c in zip((0 + off, 1 + off), ("A", "B")):
            ax.annotate(f"{pr[c][kind]['k']}/{pr[c][kind]['n']}", (x, pr[c][kind]["wilson"][1]),
                        textcoords="offset points", xytext=(0, 5), ha="center", fontsize=9)
    ax.set_xticks([0, 1], ["조건 A (단독)", "조건 B (형제 문맥)"])
    ax.set_ylabel("문제 판정률 (CONTRADICTED+INSUFFICIENT)")
    ax.set_title("F1. Phase 3 조건별 문제 판정률 · Wilson 95% CI (claude-sonnet-4-6)")
    ax.legend(loc="upper left")
    ax.set_xlim(-0.6, 1.6)
    ax.margins(y=0.15)
    fig.tight_layout()
    fig.savefig(FIG / "F1_phase3_problem_rates.png", dpi=160)
    plt.close(fig)
    drawn["F1"] = d1

    # F2 c000 recall/precision iid vs qid CI
    bs = R["c000_archive_sonnet46"]["bootstrap_B10000"]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    d2 = {}
    for off, mode, col, lab in ((-0.1, "iid", "#7f7f7f", "단위(i.i.d.) 부트스트랩"),
                                (0.1, "qid", "#1f4e79", "문항(qid) 클러스터 부트스트랩")):
        vals = [bs[a]["value"] for a in mo.AXES]
        d2[mode] = err_bars(ax, [0 + off, 1 + off], vals, [bs[a][f"ci_{mode}"] for a in mo.AXES], col, lab)
    for i, a in enumerate(mo.AXES):
        ax.annotate(f"설계효과 {bs[a]['design_effect']:.2f}", (i, 0.02), ha="center", fontsize=9)
    ax.set_xticks([0, 1], ["recall", "precision"])
    ax.set_ylim(0, 1.08)
    cl = R["c000_archive_sonnet46"]["clusters"]
    ax.set_title(f"F2. c000 축 값과 95% CI — 단위 {cl['n_units']}개 / 클러스터 {cl['n_clusters']}개, B={R['meta']['B']}")
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "F2_c000_iid_vs_cluster_ci.png", dpi=160)
    plt.close(fig)
    drawn["F2"] = d2

    # F3 사례 1 축 뒤집힘
    ax_rows = R["axis_flip_case1"]["axes"]
    keys = ["precision_slot", "precision_unique", "distinct_correct_docs"]
    labels = ["precision@10\n(슬롯 분모, 틀린 축)", "precision@10\n(고유문서 분모)", "distinct_correct_docs\n(절대 계수)"]
    vals = [ax_rows[k]["rel_change"] * 100 for k in keys]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(range(3), vals, color=["#c00000" if v < 0 else "#2e7d32" for v in vals])
    for i, k in enumerate(keys):
        r = ax_rows[k]
        ax.annotate(f"{r['off']} → {r['on']}", (i, vals[i]), textcoords="offset points",
                    xytext=(0, 5 if vals[i] >= 0 else -14), ha="center", fontsize=9)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(range(3), labels)
    ax.set_ylabel("dedup ON의 상대 변화 (%)")
    ax.margins(y=0.2)
    ax.set_title("F3. 같은 개입, 축에 따라 판정 부호가 뒤집힌다 (계측 실패 사례 1)")
    fig.tight_layout()
    fig.savefig(FIG / "F3_axis_flip_case1.png", dpi=160)
    plt.close(fig)
    drawn["F3"] = [round(b.get_height(), 4) for b in bars]

    # F4 판간 일치도
    src = [("Phase3 A", R["phase3"]["agreement_3run_A"]), ("Phase3 B", R["phase3"]["agreement_3run_B"]),
           ("c000\n(archive)", R["c000_archive_sonnet46"]["agreement_3run"]),
           ("계기검침", R["instrument_check_sonnet46"]["agreement_3run"]),
           ("옆방1\nSciFact", R["other_3run_agreement"]["sidecheck_scifact"]),
           ("옆방2\nKLUE", R["other_3run_agreement"]["sidecheck2_klue"])]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    xs = range(len(src))
    b1 = ax.bar([x - 0.2 for x in xs], [s["pct_unanimous"] for _, s in src], 0.4, color="#1f4e79", label="3판 만장일치율")
    kap = [s["fleiss_kappa_4cat"] for _, s in src]
    b2 = ax.bar([x + 0.2 for x in xs], [0 if k is None else k for k in kap], 0.4, color="#c55a11",
                label="Fleiss κ (4범주)")
    for x, (_, s), k in zip(xs, src, kap):
        ax.annotate(f"n={s['n_units']}", (x - 0.2, s["pct_unanimous"]), textcoords="offset points",
                    xytext=(0, 3), ha="center", fontsize=8)
        ax.annotate("미정의" if k is None else f"{k:.2f}", (x + 0.2, 0 if k is None else k),
                    textcoords="offset points", xytext=(0, 3), ha="center", fontsize=8)
    ax.set_xticks(list(xs), [n for n, _ in src])
    ax.set_ylim(0, 1.12)
    ax.set_title("F4. 같은 판정기(claude-sonnet-4-6) 3판 간 일치도 — 안정성이지 이식성이 아니다")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / "F4_judge_run_agreement.png", dpi=160)
    plt.close(fig)
    drawn["F4"] = {"unanimous": [round(b.get_height(), 4) for b in b1],
                   "kappa": [round(b.get_height(), 4) for b in b2]}
    return drawn


def check_figures(drawn: dict) -> list[str]:
    """results.json 을 다시 읽어 그린 값과 대조한다. 실패 목록 반환."""
    R = json.loads(RESULTS.read_text(encoding="utf-8"))
    bad = []

    def eq(name, got, want):
        if got != want:
            bad.append(f"{name}: drawn={got} json={want}")

    pr = R["phase3"]["problem_rates"]
    for kind in ("majority", "raw_rows"):
        eq(f"F1 {kind} y", drawn["F1"][kind]["y"], [pr[c][kind]["rate"] for c in ("A", "B")])
        eq(f"F1 {kind} ci", drawn["F1"][kind]["ci"], [pr[c][kind]["wilson"] for c in ("A", "B")])
    bs = R["c000_archive_sonnet46"]["bootstrap_B10000"]
    for m in ("iid", "qid"):
        eq(f"F2 {m} y", drawn["F2"][m]["y"], [bs[a]["value"] for a in mo.AXES])
        eq(f"F2 {m} ci", drawn["F2"][m]["ci"], [bs[a][f"ci_{m}"] for a in mo.AXES])
    ar = R["axis_flip_case1"]["axes"]
    eq("F3", drawn["F3"], [round(ar[k]["rel_change"] * 100, 4)
                          for k in ("precision_slot", "precision_unique", "distinct_correct_docs")])
    srcs = [R["phase3"]["agreement_3run_A"], R["phase3"]["agreement_3run_B"],
            R["c000_archive_sonnet46"]["agreement_3run"], R["instrument_check_sonnet46"]["agreement_3run"],
            R["other_3run_agreement"]["sidecheck_scifact"], R["other_3run_agreement"]["sidecheck2_klue"]]
    eq("F4 unanimous", drawn["F4"]["unanimous"], [s["pct_unanimous"] for s in srcs])
    eq("F4 kappa", drawn["F4"]["kappa"], [s["fleiss_kappa_4cat"] or 0 for s in srcs])
    return bad


def dump(R) -> str:
    return json.dumps(R, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def selftest() -> int:
    ok = True

    def chk(name, cond, got=""):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {got}")

    # 공식 검산 — Fleiss(1971) 위키 예제 κ=0.210, Cohen 교과서 2x2 κ=0.4
    wiki = [[0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1],
            [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7]]
    rows = [[c for c, n in zip("abcde", r) for _ in range(n)] for r in wiki]
    k = fleiss(rows, "abcde")
    chk("Fleiss 위키 예제 = 0.210", round(k, 3) == 0.210, round(k, 4))
    a = ["y"] * 20 + ["y"] * 5 + ["n"] * 10 + ["n"] * 15
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    chk("Cohen 2x2 예제 = 0.4", round(cohen(a, b), 6) == 0.4, cohen(a, b))
    chk("상수 라벨 → κ 미정의(None)", fleiss([["SUPPORTED"] * 3] * 5, CATS) is None)
    chk("mo IC-2 selftest", mo.selftest(verbose=False))

    R = compute()
    for name in ("c000_archive_sonnet46", "instrument_check_sonnet46"):
        for ax_, r in R[name]["reproduction_B2000"].items():
            chk(f"{name} {ax_} 내 리샘플러 == mo.bootstrap (B=2000)", r["resampler_matches_mo"])
    for ax_, r in R["c000_archive_sonnet46"]["reproduction_B2000"].items():
        chk(f"c000 {ax_} == 보관 mh_c000_objectives.json", r["matches_archived"],
            f"qid={r['mo_ci_qid']} archived={r['archived_ci_qid']}")
    chk("Phase 3 A/B 공통 다수결 단위 == phase3_result.json n_usable(273)",
        R["phase3"]["A_vs_B_majority"]["n_common_both_majority"]
        == json.loads((SCRIPTS / "phase3_result.json").read_text())["n_usable"])
    chk("LLM 호출 0", R["meta"]["llm_calls"] == 0)

    if not RESULTS.exists():
        chk("저장된 results.json 존재", False, RESULTS)
    else:
        saved = RESULTS.read_text(encoding="utf-8")
        chk("재계산 == 저장된 results.json (드리프트 없음)", dump(R) == saved)
        bad = check_figures(figures(json.loads(saved)))
        chk("그림 artist 값 == results.json", not bad, bad[:3])
    print(f"\nzero_call_reanalysis selftest {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    R = compute()
    OUT.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(dump(R), encoding="utf-8")
    bad = check_figures(figures(json.loads(RESULTS.read_text(encoding="utf-8"))))
    if bad:
        print("그림-JSON 불일치:", *bad, sep="\n  ")
        return 1
    print(f"saved {RESULTS.relative_to(GATE)} + {len(list(FIG.glob('*.png')))} figures; plot check PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
