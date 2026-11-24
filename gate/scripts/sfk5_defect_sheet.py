"""부속서13 §2 — v5 라벨 결함률 블라인드 검수 (S·Scf·Idrop 각 30). LLM 0콜, 판정기 응답 미사용.
usage: python sfk5_defect_sheet.py make            → sfk5d_review_sheet.xlsx + sfk5d_review_key.json
       python sfk5_defect_sheet.py score <완료.xlsx> → 유형별 결함률 + Wilson 95% → sfk5d_review_verdict.json
"""
import json
import math
import random
import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font

S = Path(__file__).resolve().parent
SEED, PER, KINDS = 20261125, 30, ("S", "Scf", "Idrop")
SHEET, KEY, VERDICT = (S / f"sfk5d_review_{x}" for x in ("sheet.xlsx", "key.json", "verdict.json"))
HEAD = ["번호", "질문", "근거", "검증할 주장", "판정(S/C/I)", "질문 자연스러움(O/X)", "메모"]


def pick() -> list:
    units = json.loads((S / "sfk5_main.json").read_text(encoding="utf-8"))
    seen = {k["id"] for p in ("sfk4", "sfk5") for k in json.loads((S / f"{p}_review_key.json").read_text(encoding="utf-8"))}
    rng = random.Random(SEED)
    out = []
    for k in KINDS:
        out += rng.sample(sorted((u for u in units if u["kind"] == k and u["id"] not in seen), key=lambda u: u["id"]), PER)
    rng.shuffle(out)
    return out


def make() -> None:
    us = pick()
    wb = openpyxl.Workbook()
    info = wb.active
    info.title = "설명"
    for row in (["SF-K v5 라벨 결함률 검수 (90건) — 부속서13 §2"], [""],
                ["⚠ 근거 속 문장 일부가 일부러 원 기준서와 반대로 바뀌어 있을 수 있다. 기준서 지식이 아니라 주어진 근거로만 판정한다."],
                ["E열: 근거만 보고 S / C / I 중 하나. F열: 질문이 근거와 자연스럽게 맞으면 O, 아니면 X."],
                ["S = 주장이 근거에 그대로 있거나 바로 도출된다"],
                ["C = 근거가 주장과 반대되는 내용을 말한다"],
                ["I = 근거만으로는 확인할 수 없다 (근거가 엉뚱하거나 해당 문장이 빠졌다)"],
                ["G열(메모)은 애매하거나 문장이 어색하면 이유를 한 줄."], [""],
                ["정답은 숨겼다(블라인드). 다 적으면 파일을 그대로 돌려주면 된다. 여러 번 나눠 해도 된다."]):
        info.append(row)
    info["A1"].font = Font(bold=True, size=13)
    info.column_dimensions["A"].width = 100
    ws = wb.create_sheet("검수")
    ws.append(HEAD)
    for i, u in enumerate(us, 1):
        ws.append([i, u["question"], u["evidence"].strip(), u["claim_text"], None, None, None])
    for c in ws[1]:
        c.font = Font(bold=True)
    for col, w in zip("ABCDEFG", (6, 40, 90, 50, 12, 16, 30)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(SHEET)
    KEY.write_text(json.dumps([{"no": i, "id": u["id"], "kind": u["kind"], "label": u["human_label"]}
                               for i, u in enumerate(us, 1)], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(SHEET.name, KEY.name, len(us))


def wilson(k: int, n: int, z: float = 1.96) -> tuple:
    if not n:
        return (None, None)
    p, d = k / n, 1 + z * z / n
    c, r = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0, c - r), 3), round(min(1, c + r), 3))


def score(path: str) -> None:
    key = json.loads(KEY.read_text(encoding="utf-8"))
    orig = list(openpyxl.load_workbook(SHEET)["검수"].iter_rows(min_row=2, values_only=True))
    done = [r for r in openpyxl.load_workbook(path)["검수"].iter_rows(min_row=2, values_only=True) if r and r[0] is not None]
    assert len(done) == len(key), f"행 수 {len(done)} ≠ {len(key)}"
    tamper = [o[0] for o, d in zip(orig, done) if tuple(o[:4]) != tuple(d[:4])]
    out = {"tamper": tamper, "blank": [], "by_kind": {}}
    for kd in KINDS:
        rows = [(k, d) for k, d in zip(key, done) if k["kind"] == kd]
        lab = [(k, str(d[4] or "").strip().upper()[:1], d) for k, d in rows]
        out["blank"] += [k["no"] for k, l, _ in lab if not l]
        n = sum(1 for _, l, _ in lab if l)
        bad = [{"no": k["no"], "id": k["id"], "gold": k["label"], "op": l, "memo": d[6]} for k, l, d in lab if l and l != k["label"]]
        qx = sum(1 for _, _, d in lab if str(d[5] or "").strip().upper() == "X")
        out["by_kind"][kd] = {"n": n, "defect": len(bad), "rate": round(len(bad) / n, 3) if n else None,
                              "wilson95": wilson(len(bad), n), "question_X": qx, "full_cleanup": bool(n and len(bad) / n >= 0.10),
                              "items": bad}
    VERDICT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: {x: v[x] for x in ("n", "defect", "rate", "wilson95", "question_X", "full_cleanup")}
                      for k, v in out["by_kind"].items()}, ensure_ascii=False), "tamper", tamper, "blank", len(out["blank"]))


if __name__ == "__main__":
    assert wilson(0, 30) == (0, 0.114) and wilson(3, 30)[0] < 0.1 < wilson(3, 30)[1]
    {"make": make, "score": lambda: score(sys.argv[2])}[sys.argv[1]]()
