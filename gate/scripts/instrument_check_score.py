"""계기 검침 채점 — 사전 선언 INSTRUMENT_CHECK_PREREG.md §4 기준을 그대로 적용.

🔴 이 파일은 **결과를 보기 전에 커밋한다.** Phase 3에서 유효했던 장치다.
   기준을 결과에 맞춰 고르는 것을 구조적으로 막는다.
"""
from __future__ import annotations

import collections
import glob
import json
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
PROBLEM = {"CONTRADICTED", "INSUFFICIENT"}
RECALL_THRESHOLD = 0.30          # 사전 선언 §4 — 변경 금지


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    z, p = 1.959963985, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - h), min(1.0, c + h)


def main() -> None:
    per = collections.defaultdict(list)
    for f in sorted(glob.glob(str(GATE / "scripts/instrument_check_run*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            per[d["id"]].append(d)

    maj = {}
    for i, rows in per.items():
        cnt = collections.Counter(r["label"] for r in rows).most_common()
        maj[i] = (cnt[0][0] if cnt[0][1] >= 2 else "SPLIT", rows[0]["human"])

    n_runs = len({r["run"] for rows in per.values() for r in rows})
    print(f"단위 {len(maj)}건 / {n_runs}판 다수결\n")

    # --- 혼동행렬 ------------------------------------------------------
    cm = collections.Counter((h, j) for j, h in maj.values())
    print("=== 사람 라벨 × 저지 판정 ===")
    for h in ("S", "C", "I"):
        row = {j: c for (hh, j), c in cm.items() if hh == h}
        if row:
            print(f"  human={h}: {dict(sorted(row.items()))}")

    # --- 사전 기준 적용 -------------------------------------------------
    prob_ids = [i for i, (_, h) in maj.items() if h in ("C", "I")]
    detected = [i for i in prob_ids if maj[i][0] in PROBLEM]
    n_contra = sum(1 for i in prob_ids if maj[i][0] == "CONTRADICTED")
    recall = len(detected) / len(prob_ids) if prob_ids else 0.0
    lo, hi = wilson(len(detected), len(prob_ids))

    print(f"\n=== 검출 회수율 (사전 선언 §4) ===")
    print(f"  사람 판정 문제 {len(prob_ids)}건 중 저지가 검출 {len(detected)}건")
    print(f"  recall = {recall:.1%}  Wilson 95% [{lo:.1%}, {hi:.1%}]")
    print(f"  그중 CONTRADICTED = {n_contra}건")

    # 정밀도는 보고만 (게이트에 쓰지 않는다 — §4)
    flagged = [i for i, (j, _) in maj.items() if j in PROBLEM]
    prec = len(detected) / len(flagged) if flagged else 0.0
    print(f"  [참고] 저지 문제판정 {len(flagged)}건, 정밀도 {prec:.1%} (게이트 미사용)")

    splits = [i for i, (j, _) in maj.items() if j == "SPLIT"]
    print(f"  SPLIT(3판 갈림) {len(splits)}건 — 문제 판정으로 세지 않음")

    # --- 판정 ------------------------------------------------------------
    if recall == 0:
        verdict, hyp = "FAIL", "가설 I 확정 (계기 고장) → 저지 폐기, v3 계열 재구성"
    elif recall < RECALL_THRESHOLD:
        verdict, hyp = "DEGRADED", "계기 둔감 → 저지 교정 후 재검침"
    elif n_contra < 1:
        verdict, hyp = "DEGRADED", "CONTRADICTED 0건 → 규칙왜곡 축 미검출, 저지 교정"
    else:
        verdict, hyp = "PASS", "가설 C 지지 (계기 정상) → 저지 유지, 표본을 바꾼다"

    print(f"\n{'='*54}\n판정: {verdict}\n{hyp}\n{'='*54}")

    misses = [{"id": i, "human": maj[i][1], "judge": maj[i][0]}
              for i in prob_ids if maj[i][0] not in PROBLEM]
    if misses:
        print(f"\n미검출 {len(misses)}건:")
        for m in misses:
            print(f"  {m['id']}  human={m['human']} -> judge={m['judge']}")

    (GATE / "scripts/instrument_check_result.json").write_text(json.dumps({
        "n_units": len(maj), "n_runs": n_runs,
        "n_problem": len(prob_ids), "n_detected": len(detected),
        "recall": round(recall, 4), "recall_wilson": [round(lo, 4), round(hi, 4)],
        "n_contradicted": n_contra,
        "precision_reported_only": round(prec, 4),
        "n_split": len(splits),
        "threshold": RECALL_THRESHOLD,
        "verdict": verdict, "interpretation": hyp,
        "misses": misses,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved: instrument_check_result.json")


if __name__ == "__main__":
    main()
