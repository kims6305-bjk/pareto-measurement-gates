"""부속서13 추기1 — E9 원자료 이월: E8 행 중 v5.1 단위가 v5 와 바이트 동일한 id 만 복사. 0콜.
usage: MH_EXP=E9 python sfk_e9_carry.py
"""
import json
from pathlib import Path

S = Path(__file__).resolve().parent
v5 = {u["id"]: u for u in json.loads((S / "sfk5_main.json").read_text(encoding="utf-8"))}
v51 = {u["id"]: u for u in json.loads((S / "sfk51_main.json").read_text(encoding="utf-8"))}
same = {i for i, u in v51.items() if v5.get(i) == u}
assert len(v51) == 1252 and len(v51) - len(same) == 17, len(v51) - len(same)
for m in ("claude-opus-5-5", "claude-haiku-5-5"):
    for c in ("c000", "c401"):
        src, out = S / f"mh_e8_arm_{m}_{c}_run1.jsonl", S / f"mh_e9_arm_{m}_{c}_run1.jsonl"
        assert not out.exists(), f"{out.name} 이미 있음 — 덮어쓰지 않는다"
        rows = [json.loads(l) for l in src.open(encoding="utf-8")]
        keep = [dict(r, carried_from="E8") for r in rows if r["id"] in same]
        assert len(keep) == len(same), (m, c, len(keep))
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
        print(out.name, "이월", len(keep), "새로 호출", 1252 - len(keep))
