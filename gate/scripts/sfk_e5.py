"""부속서8 E5P/E5 준비·채점 도구 (0콜). 판정 콜은 mh_run_candidate.py 가 한다.

  MH_EXP=E5P python sfk_e5.py register        # E4 원장의 c000·c301·c302 harness 를 그대로 복사(프롬프트 해시만 새 문제집 기준)
  MH_EXP=E5P python sfk_e5.py review-sheet    # 본측정 문제집에서 블라인드 검수 30건 → sfk_review_sheet.xlsx + 키
  MH_EXP=E5P python sfk_e5.py pilot-width     # §4: c301−c000 짝 Δ 구간 **폭만** 출력 + 정원 N
  MH_EXP=E5  python sfk_e5.py verdict         # §3: 후보별 축별 Δ 95% 구간과 판정
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
import mh_exp  # noqa: E402
from mh_exp import EXP, TAG  # noqa: E402

SEED, B = 20261124, 2000
W_STAR = 2 * 4 / (1 + 0.84 / 1.96)          # §4 목표 폭 ≈ 5.6%p
CANDS = ("c000", "c301", "c302")
REVIEW_QUOTA = {"S": 10, "C": 10, "I": 10}


def register() -> None:
    from instrument_check_run import load_units
    from mh_run_candidate import archive_path, prompt_sha256, resolve_builder
    rows = {}
    for line in (S / "mh_archive_e4_C2.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["candidate_id"] in CANDS:
            rows[r["candidate_id"]] = r                      # 마지막 등장 행
    units = load_units()
    assert all(u["question"] for u in units), "질문 미기입 단위가 있다 — 질문 동결·재생성 먼저"
    out = archive_path("C2")
    if out.exists():
        raise SystemExit(f"{out.name} 이미 있음 — 덮어쓰지 않는다")
    with out.open("w", encoding="utf-8") as f:
        for cid in CANDS:
            h = dict(rows[cid]["harness"])
            fn, kw, _ = resolve_builder(h)
            h["prompt_sha256"] = prompt_sha256(fn, kw, units)
            f.write(json.dumps({"candidate_id": cid, "origin": "E4 원장 복사(부속서8 §2-6)",
                                "harness": h, "status": "registered"}, ensure_ascii=False) + "\n")
    print(f"{out.name}: {CANDS} 등록, 단위 {len(units)}")


def review_sheet() -> None:
    import openpyxl
    from openpyxl.styles import Alignment, Font
    pre = "sfk4" if EXP.startswith("E6") else "sfk"          # 부속서9: v4 본측정 문제집
    units = json.loads((S / f"{pre}_main.json").read_text(encoding="utf-8"))
    rng = random.Random(SEED)
    pick = []
    for lab, k in REVIEW_QUOTA.items():
        pool = sorted((u for u in units if u["human_label"] == lab), key=lambda u: u["id"])
        pick += rng.sample(pool, k)
    rng.shuffle(pick)
    wb = openpyxl.Workbook()
    info = wb.active
    info.title = "설명"
    title = "SF-K v4 표본 검수 (30건) — 부속서9 §4" if pre == "sfk4" else "SF-K 표본 검수 (30건) — 부속서8 §2-7"
    v4 = [["⚠ 근거 속 문장 일부가 일부러 원 기준서와 반대로 바뀌어 있을 수 있다. 기준서 지식이 아니라 주어진 근거로만 판정한다."]] if pre == "sfk4" else []
    for row in ([title], [""], *v4,
                ["E열: 근거만 보고 S / C / I 중 하나. F열: 질문이 근거와 자연스럽게 맞으면 O, 아니면 X."],
                ["S = 주장이 근거에 그대로 있거나 바로 도출된다"],
                ["C = 근거가 주장과 반대되는 내용을 말한다"],
                ["I = 근거만으로는 확인할 수 없다 (근거가 엉뚱하거나 해당 문장이 빠졌다)"],
                ["G열(메모)은 애매하거나 문장이 어색하면 이유를 한 줄."], [""],
                ["정답은 숨겼다(블라인드). 다 적으면 파일을 그대로 돌려주면 된다."]):
        info.append(row)
    info["A1"].font = Font(bold=True, size=13)
    info.column_dimensions["A"].width = 100
    ws = wb.create_sheet("검수")
    ws.append(["번호", "질문", "근거", "검증할 주장", "판정(S/C/I)", "질문 자연스러움(O/X)", "메모"])
    for i, u in enumerate(pick, 1):
        ws.append([i, u["question"], u["evidence"].strip(), u["claim_text"], None, None, None])
    for c in ws[1]:
        c.font = Font(bold=True)
    for col, w in zip("ABCDEFG", (6, 40, 90, 50, 12, 16, 30)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(S / f"{pre}_review_sheet.xlsx")
    (S / f"{pre}_review_key.json").write_text(json.dumps(
        [{"no": i, "id": u["id"], "kind": u["kind"], "label": u["human_label"]} for i, u in enumerate(pick, 1)],
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{pre}_review_sheet.xlsx + {pre}_review_key.json (30건)")


def _units(cid: str):
    import mh_objectives as M
    labels = M.load_labels(S.parent / mh_exp.SF300)
    per, _ = M.load_runs([str(S / f"mh_{TAG}{cid}_run{r}.jsonl") for r in (1, 2, 3)])
    us = {u.id: u for u in M.build_units(per, labels)}
    assert len(us) == len(labels), f"{cid}: 단위 {len(us)} != 라벨 {len(labels)} (미완 판정?)"
    return us


def paired(cand: str, base: dict, other: dict):
    """군집(짝 id) 재표집 짝 부트스트랩 → 축별 (점 Δ, 하한, 상한)."""
    import mh_objectives as M
    fn = {"recall": M.recall_of, "specificity": M.specificity_of}
    by: dict[str, list[str]] = {}
    for i in base:
        by.setdefault(i.rsplit("-", 1)[0], []).append(i)
    cl = sorted(by)
    rng = random.Random(SEED)
    ds = {ax: [] for ax in fn}
    for _ in range(B):
        sel = [i for c in (rng.choice(cl) for _ in cl) for i in by[c]]
        for ax, f in fn.items():
            a, b = f(other[i] for i in sel), f(base[i] for i in sel)
            if a is not None and b is not None:
                ds[ax].append(a - b)
    out = {}
    for ax, xs in ds.items():
        xs.sort()
        q = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]
        out[ax] = (fn[ax](other.values()) - fn[ax](base.values()), q(.025), q(.975), q(.0125), q(.9875))
    return out, len(cl)


def pilot_width() -> None:
    if EXP not in ("E5P", "E6P"):
        raise SystemExit("pilot-width 는 E5P·E6P 전용")   # E6P = 부속서9 §4 같은 공식
    r, n = paired("c301", _units("c000"), _units("c301"))
    ws = {ax: (v[2] - v[1]) * 100 for ax, v in r.items()}   # 점 Δ·부호는 출력하지 않는다(§4)
    need = math.ceil(n * (max(ws.values()) / W_STAR) ** 2)
    N = max(400, need)
    print(f"파일럿 군집 {n}: 짝 Δ 구간 폭 " + ", ".join(f"{ax} {w:.1f}%p" for ax, w in ws.items()))
    print(f"목표 폭 {W_STAR:.2f}%p → 필요 {need}, 정원 N = {N}" + ("  ⚠ 800 초과 → 본측정 보류·보고(§4)" if N > 800 else ""))


def classify(r: dict, lo_i: int, hi_i: int) -> str:
    lo = [v[lo_i] for v in r.values()]
    hi = [v[hi_i] for v in r.values()]
    if all(x > 0 for x in lo):
        return "지배"
    if all(x < 0 for x in hi):
        return "열위"
    if any(x > 0 for x in lo) and any(x < 0 for x in hi):
        return "맞바꿈"
    return "판정 불가"


def verdict() -> None:
    """§3. Holm(후보 2개): 97.5% 구간으로 먼저 확정되는 후보가 있으면 그 후보는 97.5%, 나머지는 95% 로 판정."""
    if EXP not in ("E5", "E6"):
        raise SystemExit("verdict 는 E5·E6 전용")
    base = _units("c000")
    res = {c: paired(c, base, _units(c)) for c in CANDS[1:]}
    strict = {c: classify(r, 3, 4) for c, (r, _) in res.items()}
    first = [c for c, v in strict.items() if v != "판정 불가"]
    for c, (r, n) in res.items():
        v = strict[c] if (not first or c in first) else classify(r, 1, 2)
        if not first:
            v = "판정 불가"                     # 어느 후보도 97.5% 에서 확정되지 않으면 Holm 상 전부 보류
        print(f"{c} (군집 {n}): " + "; ".join(
            f"{ax} Δ {d*100:+.1f}%p 95%[{lo*100:+.1f}, {hi*100:+.1f}] 97.5%[{l2*100:+.1f}, {h2*100:+.1f}]"
            for ax, (d, lo, hi, l2, h2) in r.items()) + f" → {v}")


def precheck() -> None:
    """§5 기준선 사전 점검(부속서6 IC-0′: recall ≥ 0.30 and CONTRADICTED ≥ 1) + 천장(두 축 > 0.95)."""
    import mh_objectives as M
    if EXP not in ("E5", "E6"):
        raise SystemExit("precheck 는 E5·E6 전용")
    for c in CANDS:
        us = list(_units(c).values())
        k, r, s = M.counts(us), M.recall_of(us), M.specificity_of(us)
        ic0 = "PASS" if (c != "c000" or (r >= 0.30 and k["n_contradicted"] >= 1)) else "FAIL"
        ceil = r > 0.95 and s > 0.95
        print(f"{c}: recall {r:.3f} specificity {s:.3f} CONTRADICTED {k['n_contradicted']} "
              f"UNRESOLVED {k['n_unresolved']} SPLIT {k['n_split']} 단위 {k['n_units']}"
              + (f" IC-0′ {ic0}" if c == "c000" else "") + (" ⚠ 천장" if ceil else ""))


if __name__ == "__main__":
    if EXP not in ("E5P", "E5", "E6P", "E6"):
        raise SystemExit("MH_EXP=E5P·E5·E6P·E6 로 실행")
    {"register": register, "review-sheet": review_sheet, "pilot-width": pilot_width,
     "precheck": precheck, "verdict": verdict}[sys.argv[1]]()
