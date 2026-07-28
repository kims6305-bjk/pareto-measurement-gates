"""옆방 2 (KLUE-NLI) 표본 구성 — 사전 선언 SIDECHECK_PREREG.md §8.3.

언어를 원래 방과 같게(한국어) 고정하고 도메인·라벨러만 바꾼다.
옆방 1(SciFact)과 seed·층화·N이 완전히 동일해야 축 분리가 성립한다.

라이선스: KLUE CC BY-SA 4.0 — 원본을 레포에 재배포하지 않는다.
"""
import collections
import json
import random
import urllib.parse
import urllib.request
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".cache/klue_nli"
SEED = 20260728                      # 사전 선언 §8.3 — 옆방 1과 동일
QUOTA = {"S": 33, "C": 11, "I": 11}  # 사전 선언 §8.3 — 옆방 1과 동일

# KLUE-NLI label -> 계기 검침 라벨 (1:1)
LABEL_MAP = {0: "S", 1: "I", 2: "C"}   # entailment / neutral / contradiction

API = ("https://datasets-server.huggingface.co/rows"
       "?dataset=klue%2Fklue&config=nli&split=validation&offset={off}&length=100")


def fetch() -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / "validation.json"
    if cached.exists():
        print(f"캐시 사용: {cached}")
        return json.loads(cached.read_text(encoding="utf-8"))

    rows = []
    for off in range(0, 3000, 100):
        with urllib.request.urlopen(API.format(off=off), timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
        rows.extend(x["row"] for x in d["rows"])
        print(f"  fetched {len(rows)}", end="\r", flush=True)
        if len(d["rows"]) < 100:
            break
    cached.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(f"\n다운로드 {len(rows)}행 -> {cached} (레포 재배포 없음)")
    return rows


def main() -> None:
    rows = fetch()
    pool = []
    for r in rows:
        h = LABEL_MAP.get(r["label"])
        if h is None:
            continue
        pool.append({
            "id": r["guid"],
            "question": r["hypothesis"],     # 검증 대상 명제
            "claim_text": r["hypothesis"],
            "claim_citation": r.get("source", "klue-nli"),
            "evidence": r["premise"],
            "siblings": [],
            "human": h,
        })

    print("가용 풀:", dict(collections.Counter(u["human"] for u in pool)),
          f"총 {len(pool)}")

    rng = random.Random(SEED)
    rng.shuffle(pool)
    picked, seen = [], collections.Counter()
    for u in pool:
        if seen[u["human"]] < QUOTA[u["human"]]:
            picked.append(u)
            seen[u["human"]] += 1
    picked.sort(key=lambda u: u["id"])

    got = dict(collections.Counter(u["human"] for u in picked))
    print(f"층화 추출(seed={SEED}): {got} 총 {len(picked)}")
    if got != QUOTA:
        raise SystemExit(f"🔴 할당량 미달 {got} != {QUOTA} — 사전 선언 위반, 중단")

    n_prob = sum(1 for u in picked if u["human"] in ("C", "I"))
    print(f"문제 사례 {n_prob}건 ({n_prob/len(picked):.1%})")

    out = GATE / "scripts/sidecheck2_units.json"
    out.write_text(json.dumps(picked, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"saved: {out.name}")


if __name__ == "__main__":
    main()
