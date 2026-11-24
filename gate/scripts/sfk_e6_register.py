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

assert EXP == "E6P", "MH_EXP=E6P 로 실행"
row = [json.loads(l) for l in (S / "mh_archive_e5_C2.jsonl").open(encoding="utf-8")
       if json.loads(l)["candidate_id"] == "c000"][-1]
units = load_units()
assert len(units) == 200 and all(u["question"] for u in units), "파일럿 단위 200·질문 기입 필요"
out = archive_path("C2")
if out.exists():
    raise SystemExit(f"{out.name} 이미 있음 — 덮어쓰지 않는다")
h = dict(row["harness"])
fn, kw, _ = resolve_builder(h)
h["prompt_sha256"] = prompt_sha256(fn, kw, units)
out.write_text(json.dumps({"candidate_id": "c000", "origin": "E5 원장 복사(부속서9 §2)", "harness": h,
                           "status": "registered"}, ensure_ascii=False) + "\n", encoding="utf-8")
print(out.name, "c000 등록, 단위", len(units), h["prompt_sha256"][:12])
