"""부속서9 E6P 원장 등록 — E5 원장의 c000 행 복사, prompt_sha256 만 v4 파일럿 단위로 재계산. 0콜.
usage: MH_EXP=E6P python sfk_e6_register.py
"""
import json
import sys
from pathlib import Path

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
from instrument_check_run import load_units  # noqa: E402
from mh_exp import EXP  # noqa: E402
from mh_run_candidate import archive_path, prompt_sha256, resolve_builder  # noqa: E402

assert EXP in ("E6P", "E6"), "MH_EXP=E6P·E6 로 실행"
CANDS = sys.argv[1:] or ["c000"]   # 부속서9 §4 폭 파일럿: c301 c302 추가 등록(append)
rows = {json.loads(l)["candidate_id"]: json.loads(l) for l in (S / "mh_archive_e5_C2.jsonl").open(encoding="utf-8")}
units = load_units()
assert all(u["question"] for u in units), "질문 미기입 단위가 있다"
out = archive_path("C2")
have = {json.loads(l)["candidate_id"] for l in out.open(encoding="utf-8")} if out.exists() else set()
if have & set(CANDS):
    raise SystemExit(f"{out.name} 에 이미 있음 {sorted(have & set(CANDS))} — 덮어쓰지 않는다")
with out.open("a", encoding="utf-8") as f:
    for cid in CANDS:
        h = dict(rows[cid]["harness"])
        fn, kw, _ = resolve_builder(h)
        h["prompt_sha256"] = prompt_sha256(fn, kw, units)
        f.write(json.dumps({"candidate_id": cid, "origin": "E5 원장 복사(부속서9 §2·§4)", "harness": h,
                            "status": "registered"}, ensure_ascii=False) + "\n")
        print(out.name, cid, "등록, 단위", len(units), h["prompt_sha256"][:12])
