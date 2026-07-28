"""옆방 표본 구성 — SciFact dev에서 층화 55건. 사전 선언 SIDECHECK_PREREG.md §3.

층화 비율(S 33 / C 11 / I 11)과 seed는 사전 선언에 고정돼 있다. 선별하지 않는다.
"""
import collections
import json
import random
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".cache/scifact/data"
SEED = 20260728                     # 사전 선언 §3 — 변경 금지
QUOTA = {"S": 33, "C": 11, "I": 11}  # 사전 선언 §3 — 변경 금지


def main() -> None:
    dev = [json.loads(l) for l in open(CACHE / "claims_dev.jsonl", encoding="utf-8")]
    corpus = {int(d["doc_id"]): d
              for d in (json.loads(l)
                        for l in open(CACHE / "corpus.jsonl", encoding="utf-8"))}

    pool = []
    for d in dev:
        ev = d.get("evidence") or {}
        if not ev:
            # NOINFO: 인용은 했으나 근거가 주장을 지지하지 않음 -> I
            for did in d.get("cited_doc_ids") or []:
                doc = corpus.get(int(did))
                if not doc:
                    continue
                pool.append({
                    "id": f"SF{d['id']}-{did}",
                    "question": d["claim"],       # SciFact는 질문이 곧 주장
                    "claim_text": d["claim"],
                    "claim_citation": doc["title"],
                    # 근거 미지정이므로 초록 앞 5문장을 근거로 제공
                    "evidence": " ".join(doc["abstract"][:5]),
                    "siblings": [],
                    "human": "I",
                })
            continue
        for did, items in ev.items():
            doc = corpus.get(int(did))
            if not doc:
                continue
            labs = {it["label"] for it in items}
            human = "S" if "SUPPORT" in labs else "C"
            sents = sorted({s for it in items for s in it["sentences"]})
            rationale = " ".join(doc["abstract"][s] for s in sents
                                 if s < len(doc["abstract"]))
            pool.append({
                "id": f"SF{d['id']}-{did}",
                "question": d["claim"],
                "claim_text": d["claim"],
                "claim_citation": doc["title"],
                "evidence": rationale,
                "siblings": [],
                "human": human,
            })

    print("가용 풀:", dict(collections.Counter(u["human"] for u in pool)),
          f"총 {len(pool)}")

    rng = random.Random(SEED)
    rng.shuffle(pool)
    picked, seen = [], collections.Counter()
    for u in pool:
        h = u["human"]
        if seen[h] < QUOTA[h]:
            picked.append(u)
            seen[h] += 1
    picked.sort(key=lambda u: u["id"])

    got = dict(collections.Counter(u["human"] for u in picked))
    print(f"층화 추출(seed={SEED}): {got} 총 {len(picked)}")
    if got != QUOTA:
        raise SystemExit(f"🔴 할당량 미달 {got} != {QUOTA} — 사전 선언 위반, 중단")

    n_prob = sum(1 for u in picked if u["human"] in ("C", "I"))
    print(f"문제 사례 {n_prob}건 ({n_prob/len(picked):.1%})")

    out = GATE / "scripts/sidecheck_units.json"
    out.write_text(json.dumps(picked, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"saved: {out.name}")


if __name__ == "__main__":
    main()
