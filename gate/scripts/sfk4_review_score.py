"""부속서9 §4 운영자 블라인드 검수 채점 (0콜).
usage: python sfk4_review_score.py <완료 xlsx>
검사: 원본(질문·근거·주장) 변조 없음, 라벨 일치, 질문 X 의 유형 분포. 결함 3건 이상이면 FAIL(부속서8 §2-7 규칙 승계).
"""
import json
import sys
from pathlib import Path

import openpyxl

S = Path(__file__).resolve().parent
PRE = sys.argv[2] if len(sys.argv) > 2 else "sfk4"   # 부속서12: sfk5
key = json.loads((S / f"{PRE}_review_key.json").read_text(encoding="utf-8"))
orig = list(openpyxl.load_workbook(S / f"{PRE}_review_sheet.xlsx")["검수"].iter_rows(min_row=2, values_only=True))
done = list(openpyxl.load_workbook(sys.argv[1])["검수"].iter_rows(min_row=2, values_only=True))
done = [r for r in done if r and r[0] is not None]
assert len(done) == len(key) == 30, f"행 수 {len(done)}"
tamper = [o[0] for o, d in zip(orig, done) if tuple(o[:4]) != tuple(d[:4])]
mis, qx, blank = [], [], []
for k, d in zip(key, done):
    lab = str(d[4] or "").strip().upper()[:1]
    if not lab:
        blank.append(k["no"])
    elif lab != k["label"]:
        mis.append({"no": k["no"], "id": k["id"], "kind": k["kind"], "gold": k["label"], "op": lab, "memo": d[6]})
    if str(d[5] or "").strip().upper() == "X":
        qx.append((k["no"], k["kind"], d[6]))
out = {"n": 30, "agree": 30 - len(mis) - len(blank), "blank": blank, "tamper": tamper, "mismatch": mis,
       "question_X": [{"no": n, "kind": kd, "memo": m} for n, kd, m in qx]}
(S / f"{PRE}_review_verdict.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
print("PASS" if not tamper and not blank and len(mis) < 3 else "FAIL/검토 필요")
