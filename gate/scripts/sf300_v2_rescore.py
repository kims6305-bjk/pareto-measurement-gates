"""SF-300 v2 정답(운영자 재검수 4건) 생성 + 기존 원자료 재채점 (0콜). 부속서6 추기 6.

v1 정답지(sf300_label_set.json)는 건드리지 않는다. 실행: MH_EXP=E3 .venv/bin/python scripts/sf300_v2_rescore.py
"""
import json
import sys
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE / "scripts"))
import mh_objectives as mo  # noqa: E402
import sf_ic1  # noqa: E402

V1, V2 = GATE / "scripts/sf300_label_set.json", GATE / "scripts/sf300_label_set_v2.json"
# 운영자(bjkim) 판정 2026-11-23, 기준 A안(단독 명제) — sf300_label_review_10.md
CHANGES = {
    "Q042-sf-S052": ("I", "예외 요건의 조건 하나를 단독 사실 진술로 떼어냄"),
    "Q070-sf-S096": ("I", "고려 요건의 조건 하나를 단독 사실 진술로 떼어냄"),
    "Q085-sf-S028": ("I", "'그 상황'이 지시하는 전제 조건이 빠짐"),
    "Q042-sf-S123": ("C", "'다만' 이하 예외를 생략해 모든 경우 인식한다는 뜻이 됨"),
}
RUNS = {
    "opus-5-5": "scripts/mh_e2_c000_run%d.jsonl",
    "sonnet-5-5": "scripts/archive_e3_sonnet55_parser_v2_ceiling_20261123/mh_e3_c000_run%d.jsonl",
    "haiku-5-5": "scripts/mh_e3_c000_run%d.jsonl",
}


def build_v2():
    rows = json.loads(V1.read_text(encoding="utf-8"))
    hit = 0
    for r in rows:
        if r["id"] in CHANGES:
            assert r["human_label"] == "S", r["id"]
            r["human_label_v1"], r["human_label"] = r["human_label"], CHANGES[r["id"]][0]
            r["label_revision"] = "v2 운영자 재검수(A안): " + CHANGES[r["id"]][1]
            hit += 1
    assert hit == len(CHANGES) == 4 and len(rows) == 300
    V2.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def score(labels, pat):
    per, _ = mo.load_runs([str(GATE / (pat % i)) for i in (1, 2, 3)])
    mo.validate_run_ledger(per, labels, "c000")
    u = mo.build_units(per, labels)
    rc, sp = mo.recall_of(u), mo.specificity_of(u)
    return u, {"recall": rc, "specificity": sp, "counts": mo.counts(u),
               "adopt": rc >= .30 and (rc <= .95 or sp <= .95)}


def main():
    build_v2()
    l1, l2 = mo.load_labels(V1), mo.load_labels(V2)
    assert sum(l1[k] != l2[k] for k in l1) == 4
    out = {"label_v2_sha256": mo.sha256_file(V2), "changes": CHANGES, "models": {}}
    for m, pat in RUNS.items():
        _, a = score(l1, pat)
        u, b = score(l2, pat)
        out["models"][m] = {"v1": a, "v2": b}
        if m == "haiku-5-5":
            v = sf_ic1.verdict(l2, {x.id: x.maj for x in u}, sf_ic1.R_ADOPTED)
            out["haiku_ic1_v2"] = v
        print(m, "v1", round(a["recall"], 3), round(a["specificity"], 3),
              "→ v2", round(b["recall"], 3), round(b["specificity"], 3), "adopt", b["adopt"])
    print("haiku IC-1′ v2:", out["haiku_ic1_v2"]["verdict"],
          {k: out["haiku_ic1_v2"][k] for k in ("c1_over_specificity", "c2_under_recall", "c3_both_dominated")})
    (GATE / "scripts/sf300_v2_rescore.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
