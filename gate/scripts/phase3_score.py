"""Phase 3 집계·판정 — 사전 선언(PHASE3_PREREGISTRATION.md §4)을 코드로 옮긴 것.

**이 스크립트는 결과를 보기 전에 작성·커밋한다.** 판정 기준을 결과에 맞춰 고르는
순환을 막는 것이 목적이며, 재량 파라미터가 없다.

§5 재현성 규율:
  - 3판 다수결로 확정. split(3판이 갈림)은 주검정에서 제외하되 건수를 반드시 보고.
  - UNRESOLVED가 하나라도 섞이면 그 건은 unresolved로 분류(정상 라벨로 승격 금지).
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

GATE = Path(__file__).resolve().parents[1] / "scripts"

PROBLEM = {"CONTRADICTED", "INSUFFICIENT"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def mcnemar_exact(b: int, c: int) -> float:
    """불일치쌍 (b, c)의 양측 정확검정 p값 (이항 p=0.5)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def load(cond: str) -> dict[str, dict]:
    """3판 다수결로 확정. 반환: id -> {label, status, runs}"""
    runs = defaultdict(dict)
    for r in ("run1", "run2", "run3"):
        f = GATE / f"phase3_judge_{cond}_{r}.jsonl"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            runs[row["id"]][r] = row

    out = {}
    for cid, rs in runs.items():
        labels = [rs[r]["label"] for r in sorted(rs)]
        if len(labels) < 3:
            out[cid] = {"label": None, "status": "incomplete", "runs": labels}
            continue
        if "UNRESOLVED" in labels:
            out[cid] = {"label": None, "status": "unresolved", "runs": labels}
            continue
        cnt = Counter(labels)
        top, n_top = cnt.most_common(1)[0]
        # 3판 중 2표 이상이면 다수결 확정, 3판 모두 다르면 split
        status = "majority" if n_top >= 2 else "split"
        meta = next(iter(rs.values()))
        out[cid] = {"label": top if status == "majority" else None,
                    "status": status, "runs": labels,
                    "set": meta["set"], "rule_type": meta["rule_type"],
                    "qid": meta["qid"], "n_siblings": meta["n_siblings"]}
    return out


def main() -> None:
    A, B = load("A"), load("B")
    common = sorted(set(A) & set(B))
    print(f"양 조건 모두 기록된 단위: {len(common)}건\n")

    # --- §5 규율: 불안정분 집계 후 제외 ---------------------------------
    excluded = [c for c in common
                if A[c]["status"] != "majority" or B[c]["status"] != "majority"]
    usable = [c for c in common if c not in excluded]
    ex_reason = Counter()
    for c in excluded:
        ex_reason[f"A:{A[c]['status']}/B:{B[c]['status']}"] += 1
    print("=== 주검정 제외 (사전 선언 §5 — 건수 반드시 보고) ===")
    print(f"제외 {len(excluded)}건 / 사용 {len(usable)}건")
    for k, v in ex_reason.most_common():
        print(f"   {k}: {v}건")
    print()

    meta = {c: (B[c] if "set" in B[c] else A[c]) for c in usable}
    sib = [c for c in usable if meta[c]["n_siblings"] >= 1]
    solo = [c for c in usable if meta[c]["n_siblings"] == 0]
    conf_sib = [c for c in sib if meta[c]["set"] == "confirmatory"]

    def flips(ids):
        """A가 문제판정(C/I) -> B가 SUPPORTED = 개선 방향 뒤집힘"""
        improve = [c for c in ids
                   if A[c]["label"] in PROBLEM and B[c]["label"] == "SUPPORTED"]
        worsen = [c for c in ids
                  if A[c]["label"] == "SUPPORTED" and B[c]["label"] in PROBLEM]
        other = [c for c in ids
                 if A[c]["label"] != B[c]["label"]
                 and c not in improve and c not in worsen]
        return improve, worsen, other

    # --- 음성 대조군 (§3.2: 확증/탐색 구분 없이 전량) --------------------
    s_imp, s_wor, s_oth = flips(solo)
    n_solo_mismatch = len(s_imp) + len(s_wor) + len(s_oth)
    solo_lo, solo_hi = wilson(n_solo_mismatch, len(solo))
    print("=== 음성 대조군 (단독 주장 — A/B 프롬프트 동일) ===")
    print(f"불일치 {n_solo_mismatch}/{len(solo)}건 "
          f"= {n_solo_mismatch/max(1,len(solo)):.1%}  "
          f"Wilson 95% [{solo_lo:.1%}, {solo_hi:.1%}]")
    print(f"⚠️ 표본 {len(solo)}건 — 0건이어도 '노이즈 없음'이라고 말하지 않는다(§3.2).")
    print()

    # --- H1: 확증 집합 형제 보유, 쌍대 McNemar --------------------------
    imp, wor, oth = flips(conf_sib)
    p = mcnemar_exact(len(imp), len(wor))
    print("=== H1: 형제 문맥이 문제판정을 줄이는가 (확증 집합) ===")
    print(f"대상 {len(conf_sib)}건")
    print(f"  개선 뒤집힘 (A:문제 -> B:SUPPORTED): {len(imp)}건")
    print(f"  악화 뒤집힘 (A:SUPPORTED -> B:문제): {len(wor)}건")
    print(f"  기타 라벨 변화: {len(oth)}건")
    print(f"  McNemar 양측 정확검정 p = {p:.4f}")
    flip_rate = (len(imp) + len(wor) + len(oth)) / max(1, len(conf_sib))
    f_lo, f_hi = wilson(len(imp) + len(wor) + len(oth), len(conf_sib))
    print(f"  전체 불일치율 {flip_rate:.1%} Wilson [{f_lo:.1%}, {f_hi:.1%}]")

    c1 = p < 0.05
    c2 = len(imp) > len(wor)
    c3 = f_lo > solo_hi        # 대조군 구간과 겹치면 미충족(§3.2)
    print(f"\n  ① p<0.05          : {'✅' if c1 else '❌'}")
    print(f"  ② 개선 방향 우세   : {'✅' if c2 else '❌'}")
    print(f"  ③ 대조군 초과(구간 비겹침): {'✅' if c3 else '❌'} "
          f"(형제 하한 {f_lo:.1%} vs 대조군 상한 {solo_hi:.1%})")
    h1 = c1 and c2 and c3
    print(f"  => H1 {'채택' if h1 else '기각/판정 불가'}")
    print()

    # --- H2: 규칙유형 구분선. 주장 단위 + 문항 단위 병기 (§3.1) ----------
    print("=== H2: 연언 vs 선택 규칙 구분선 (확증 집합) ===")
    rates = {}
    for rt in ("CONJUNCTIVE", "SELECTION"):
        ids = [c for c in conf_sib if meta[c]["rule_type"] == rt]
        i2, w2, o2 = flips(ids)
        k = len(i2) + len(w2) + len(o2)
        lo, hi = wilson(k, len(ids))
        qids = {meta[c]["qid"] for c in ids}
        flip_q = {meta[c]["qid"] for c in (i2 + w2 + o2)}
        rates[rt] = {"k": k, "n": len(ids), "lo": lo, "hi": hi,
                     "questions": len(qids), "flip_questions": len(flip_q),
                     "q_rate": len(flip_q) / max(1, len(qids))}
        print(f"  {rt:12s} 주장 {k}/{len(ids)} = {k/max(1,len(ids)):.1%} "
              f"Wilson [{lo:.1%}, {hi:.1%}]")
        print(f"  {'':12s} 문항 {len(flip_q)}/{len(qids)} = "
              f"{len(flip_q)/max(1,len(qids)):.1%}  ← 독립 단위")

    cj, sl = rates["CONJUNCTIVE"], rates["SELECTION"]
    claim_sep = cj["lo"] > sl["hi"]
    q_dir = cj["q_rate"] > sl["q_rate"]
    print(f"\n  ④ 주장 단위 구간 비겹침: {'✅' if claim_sep else '❌'} "
          f"(CONJ 하한 {cj['lo']:.1%} vs SEL 상한 {sl['hi']:.1%})")
    print(f"  ⑤ 문항 단위 방향 일치  : {'✅' if q_dir else '❌'} "
          f"(CONJ {cj['q_rate']:.0%} vs SEL {sl['q_rate']:.0%})")
    if claim_sep and q_dir:
        h2, note = True, "채택"
    elif claim_sep and not q_dir:
        h2, note = False, "군집화로 판정 불가 (주장 단위만 유의, 문항 단위 불일치 — §3.1-2)"
    else:
        h2, note = False, "기각"
    print(f"  => H2 {note}")
    print(f"\n  🔴 병기 의무(§3.1-3): CONJUNCTIVE는 문항 {cj['questions']}개, "
          f"SELECTION은 문항 {sl['questions']}개에서 나온 결과다.")

    # --- 탐색 집합 (보고만, 주장 근거 아님) -----------------------------
    expl_sib = [c for c in sib if meta[c]["set"] == "exploratory"]
    ei, ew, eo = flips(expl_sib)
    print(f"\n=== 탐색 집합 (가설 생성 표본 — 참고 보고만) ===")
    print(f"  {len(expl_sib)}건 중 불일치 {len(ei)+len(ew)+len(eo)}건 "
          f"(개선 {len(ei)} / 악화 {len(ew)} / 기타 {len(eo)})")
    print("  ⚠️ 이 수치는 주장의 근거가 아니다(순환 논증 — §0).")

    out = GATE / "phase3_result.json"
    out.write_text(json.dumps({
        "n_common": len(common), "n_excluded": len(excluded),
        "exclusion_reasons": dict(ex_reason), "n_usable": len(usable),
        "negative_control": {"n": len(solo), "mismatch": n_solo_mismatch,
                             "wilson": [solo_lo, solo_hi]},
        "h1": {"n": len(conf_sib), "improve": len(imp), "worsen": len(wor),
               "other": len(oth), "mcnemar_p": p,
               "flip_rate": flip_rate, "wilson": [f_lo, f_hi],
               "criteria": {"p<0.05": c1, "direction": c2, "above_control": c3},
               "accepted": h1},
        "h2": {"rates": rates, "claim_separated": claim_sep,
               "question_direction": q_dir, "verdict": note, "accepted": h2},
        "exploratory": {"n": len(expl_sib), "improve": len(ei),
                        "worsen": len(ew), "other": len(eo)},
        "improve_ids": imp, "worsen_ids": wor,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved: {out.name}")


if __name__ == "__main__":
    main()
