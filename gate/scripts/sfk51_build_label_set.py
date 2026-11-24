"""SF-K v5.1 — 부속서13 §1. v5 생성기에서 이상↔이하 쌍만 뺀다(관용구 훼손 결함). LLM 0콜, 결정론.
usage: python sfk51_build_label_set.py [--check]
"""
import hashlib
import json
import re
import sys
from pathlib import Path

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
import sfk5_build_label_set as v5  # noqa: E402

v5.PAIRS[:] = [p for p in v5.PAIRS if p[:2] != ("이상", "이하")]   # minedit 이 모듈 전역 PAIRS 를 읽는다
OUT = {sp: S / f"sfk51_{sp}.json" for sp in ("pilot", "main")}


def edited_word(u: dict) -> str:
    s, e = u["source"]["sentence"], u["source"]["edited"]
    j = next(x for x in range(len(s)) if x >= len(e) or s[x] != e[x])
    return s[max(0, j - 1):j + 3] + "|" + e[max(0, j - 1):j + 3]


def check51(d: dict) -> dict:
    n = {}
    for sp, us in d.items():
        # 군집당 단위가 2개(S + 오류형)라 id 로 비교
        o_all = {u["id"]: u for u in json.loads((S / f"sfk5_{sp}.json").read_text(encoding="utf-8"))}
        n_all = {u["id"]: u for u in us}
        diff_pairs = {u["pair"] for i, u in o_all.items() if n_all.get(i) != u} | {u["pair"] for i, u in n_all.items() if o_all.get(i) != u}
        ii = {u["pair"] for u in o_all.values() if u["kind"] in v5.LABEL5 and re.search("이상|이하", edited_word(u))}
        assert diff_pairs == ii, (sp, sorted(diff_pairs ^ ii))
        assert not any(u["kind"] in v5.LABEL5 and re.search("이상|이하", edited_word(u)) for u in us), sp
        n[sp] = len(diff_pairs)
    return n


if __name__ == "__main__":
    d, cnt = v5.build()
    v5.check(d)
    n = check51(d)
    blobs = {OUT[sp]: json.dumps(us, ensure_ascii=False, indent=1, sort_keys=True) + "\n" for sp, us in d.items()}
    if "--check" in sys.argv:
        ok = all(p.exists() and p.read_text(encoding="utf-8") == b for p, b in blobs.items())
        print("check:", "OK" if ok else "FAIL")
        raise SystemExit(0 if ok else 1)
    for p, b in blobs.items():
        p.write_text(b, encoding="utf-8")
        print(p.name, hashlib.sha256(b.encode()).hexdigest()[:16])
    print("v5 대비 바뀐 군집", n, dict(sorted(cnt.items())))
