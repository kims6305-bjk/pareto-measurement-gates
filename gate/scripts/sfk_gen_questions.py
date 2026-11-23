"""SF-K 질문 문장 생성 — 부속서8 §2-4. 군집당 1콜(claude-sonnet-5-5, 판정기와 다른 모델).

근거 두 문단만 보여준다(주장·라벨 비노출). 결과는 sfk_questions_raw.jsonl 에 이어쓰기(resume),
끝나면 sfk_questions_FROZEN.json 으로 동결한다. 동결 파일이 있으면 아무것도 하지 않는다(재생성 금지).

usage:  python sfk_gen_questions.py [--workers 3]
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

S = Path(__file__).resolve().parent
RAW = S / "sfk_questions_raw.jsonl"
FROZEN = S / "sfk_questions_FROZEN.json"
MODEL = "claude-sonnet-5-5"
PROMPT = """다음은 K-IFRS 기업회계기준서 제{std}호 「{title}」의 문단 발췌다.

{evidence}

이 발췌를 읽은 실무 회계 담당자가 물어볼 법한 질문을 한국어 한 문장으로 써라.
- 발췌 안의 내용으로 답할 수 있는 질문이어야 한다.
- 문단 번호나 "이 발췌"를 언급하지 마라. 답을 질문에 담지 마라.
- 기준서 이름은 보통 쓰지 않는다. 꼭 필요할 때만 위 이름을 짧게(예: 제1116호) 쓰고, 다른 기준서 이름을 지어내거나 "이 기준서"라고 쓰지 마라.
출력은 JSON 한 줄만: {{"question": "..."}}"""
lock = threading.Lock()
sys.path.insert(0, str(S))
from sfk_build_label_set import source_files  # noqa: E402
TITLES = {p.name[:4]: p.name[5:-3] for p in source_files()}


def ask(cid: str, evidence: str) -> None:
    p = subprocess.run([shutil.which("claude") or "claude", "-p", "--model", MODEL, "--max-turns", "1"],
                       input=PROMPT.format(std=cid[1:5], title=TITLES[cid[1:5]], evidence=evidence), capture_output=True, text=True, timeout=180)
    raw = (p.stdout or "").strip()
    if re.search(r"hit your .{0,30}limit|rate.?limit|usage limit", raw + (p.stderr or ""), re.I):
        raise SystemExit(f"rate_limit: {raw[:200]}")
    if p.returncode != 0:
        raise SystemExit(f"CLI 실패 exit={p.returncode}: {((p.stderr or '') + raw)[:200]}")
    objs, dec, i = [], json.JSONDecoder(), raw.find("{")
    while i >= 0:                                  # 자기 정정으로 JSON 이 여러 개면 마지막 것(부속서6 추기 3 과 같은 규약)
        try:
            o, end = dec.raw_decode(raw, i)
            objs.append(o)
            i = raw.find("{", end)
        except json.JSONDecodeError:
            i = raw.find("{", i + 1)
    q = str(objs[-1].get("question", "")).strip() if objs and isinstance(objs[-1], dict) else ""
    if not (10 <= len(q) <= 200) or "\n" in q:
        raise SystemExit(f"{cid}: 질문 형식 위반 {raw[:200]!r}")   # 조용히 넘기지 않는다
    with lock, RAW.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"cid": cid, "question": q, "model": MODEL}, ensure_ascii=False) + "\n")


def main() -> None:
    if FROZEN.exists():
        raise SystemExit("동결 파일이 이미 있다 — 재생성 금지(부속서8 §2-4)")
    ev = {u["pair"]: u["evidence"] for split in ("pilot", "main")
          for u in json.loads((S / f"sfk_{split}.json").read_text(encoding="utf-8")) if u["kind"] == "S"}
    done = {json.loads(l)["cid"] for l in RAW.open(encoding="utf-8")} if RAW.exists() else set()
    todo = sorted(c for c in ev if c not in done)
    print(f"군집 {len(ev)}, 완료 {len(done)}, 남음 {len(todo)}", flush=True)
    w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 3
    with ThreadPoolExecutor(w) as ex:
        for f in [ex.submit(ask, c, ev[c]) for c in todo]:
            f.result()
    got = {}
    for l in RAW.open(encoding="utf-8"):
        r = json.loads(l)
        got.setdefault(r["cid"], r["question"])          # 중복 기록이면 첫 것
    assert set(got) == set(ev), f"누락 {len(set(ev) - set(got))}"
    FROZEN.write_text(json.dumps(dict(sorted(got.items())), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"동결: {len(got)}개 → {FROZEN.name}")


if __name__ == "__main__":
    main()
