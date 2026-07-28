"""옆방 검침 채점 — 사전 선언 SIDECHECK_PREREG.md §4 기준을 그대로 적용.

🔴 결과를 보기 전에 커밋한다. 임계(30%)는 원래 방과 동일하며 옆방용으로
   조정하지 않는다 — 조정하면 검증이 무의미해진다.
"""
from __future__ import annotations

import collections
import glob
import json
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
PROBLEM = {"CONTRADICTED", "INSUFFICIENT"}
RECALL_THRESHOLD = 0.30          # 사전 선언 §4 — 원래 방과 동일, 변경 금지


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
    for f in sorted(glob.glob(str(GATE / "scripts/sidecheck_run*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            per[d["id"]].append(d)

    maj = {}
    for i, rows in per.items():
        cnt = collections.Counter(r["label"] for r in rows).most_common()
        maj[i] = (cnt[0][0] if cnt[0][1] >= 2 else "SPLIT", rows[0]["human"])

    n_runs = len({r["run"] for rows in per.values() for r in rows})
    print(f"옆방(SciFact) 단위 {len(maj)}건 / {n_runs}판 다수결\n")

    cm = collections.Counter((h, j) for j, h in maj.values())
    print("=== 사람 라벨 × 판정기 ===")
    for h in ("S", "C", "I"):
        row = {j: c for (hh, j), c in cm.items() if hh == h}
        if row:
            print(f"  human={h}: {dict(sorted(row.items()))}")

    prob_ids = [i for i, (_, h) in maj.items() if h in ("C", "I")]
    detected = [i for i in prob_ids if maj[i][0] in PROBLEM]
    n_contra = sum(1 for i in prob_ids if maj[i][0] == "CONTRADICTED")
    recall = len(detected) / len(prob_ids) if prob_ids else 0.0
    lo, hi = wilson(len(detected), len(prob_ids))

    print("\n=== 검출 회수율 (사전 선언 §4, 임계 30%) ===")
    print(f"  사람 판정 문제 {len(prob_ids)}건 중 검출 {len(detected)}건")
    print(f"  recall = {recall:.1%}  Wilson 95% [{lo:.1%}, {hi:.1%}]")
    print(f"  그중 CONTRADICTED = {n_contra}건")

    flagged = [i for i, (j, _) in maj.items() if j in PROBLEM]
    prec = len(detected) / len(flagged) if flagged else 0.0
    print(f"  [참고] 판정기 문제판정 {len(flagged)}건, 정밀도 {prec:.1%} (게이트 미사용)")

    splits = [i for i, (j, _) in maj.items() if j == "SPLIT"]
    print(f"  SPLIT(3판 갈림) {len(splits)}건 — 문제 판정으로 세지 않음")

    if recall == 0:
        verdict = "FAIL"
        act = "절차가 K-IFRS 전용 → README 범용성 주장 철회"
    elif recall < RECALL_THRESHOLD:
        verdict = "DEGRADED"
        act = "검출력이 도메인 의존적 → '미검증' 유지 + 저하 관측 명시"
    elif n_contra < 1:
        verdict = "DEGRADED"
        act = "CONTRADICTED 0건 → 상충 축 미검출, 저하로 처리"
    else:
        verdict = "PASS"
        act = "도메인 밖에서도 작동 → '미검증' 표기를 실측 결과로 교체"

    print(f"\n{'='*58}\n판정: {verdict}\n{act}\n{'='*58}")

    # 원래 방과 병기 (수치 비교가 아니라 판정 비교 — 사전 선언 §3.1)
    ic = GATE / "scripts/instrument_check_result.json"
    if ic.exists():
        home = json.load(open(ic, encoding="utf-8"))
        print("\n=== 두 도메인 병기 (판정 비교 — 수치 직접 비교 금지 §3.1) ===")
        print(f"  K-IFRS(ko) : recall {home['recall']:.1%} "
              f"({home['n_detected']}/{home['n_problem']}), SPLIT {home['n_split']} "
              f"-> {home['verdict']}")
        print(f"  SciFact(en): recall {recall:.1%} "
              f"({len(detected)}/{len(prob_ids)}), SPLIT {len(splits)} -> {verdict}")

    misses = [{"id": i, "human": maj[i][1], "judge": maj[i][0]}
              for i in prob_ids if maj[i][0] not in PROBLEM]
    if misses:
        print(f"\n미검출 {len(misses)}건 (앞 10):")
        for m in misses[:10]:
            print(f"  {m['id']}  human={m['human']} -> judge={m['judge']}")

    (GATE / "scripts/sidecheck_result.json").write_text(json.dumps({
        "domain": "scifact", "n_units": len(maj), "n_runs": n_runs,
        "n_problem": len(prob_ids), "n_detected": len(detected),
        "recall": round(recall, 4), "recall_wilson": [round(lo, 4), round(hi, 4)],
        "n_contradicted": n_contra,
        "precision_reported_only": round(prec, 4),
        "n_split": len(splits), "threshold": RECALL_THRESHOLD,
        "verdict": verdict, "action": act, "misses": misses,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved: sidecheck_result.json")


if __name__ == "__main__":
    main()
