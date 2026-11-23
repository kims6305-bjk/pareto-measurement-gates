"""실험 스위치 — `MH_EXP=E2` 일 때만 부속서5(E2) 값을 쓴다. 기본은 E1(기록 재현 보존).

E2 값이 E1 상수를 덮어쓰면 끝난 E1 의 재현 검사가 깨지므로, 상수는 모듈마다
`X = E2값 if E2 else E1값` 으로만 갈라 둔다. 파일 이름도 E2 접두어로 분리한다.
"""
import os

EXP = os.environ.get("MH_EXP", "E1")
if EXP not in ("E1", "E2", "E3", "E4", "E5P", "E5"):
    raise SystemExit(f"MH_EXP={EXP!r} — E1·E2·E3·E4·E5P·E5 만 허용")
# E3(부속서6) = E2 설계, 판정기만 다름. E4 = 부속서7. E5P/E5 = 부속서8 파일럿/본측정(SF-K)
E2 = EXP in ("E2", "E3", "E4", "E5P", "E5")
TAG = {"E2": "e2_", "E3": "e3_", "E4": "e4_", "E5P": "e5p_", "E5": "e5_"}.get(EXP, "")   # 원자료·원장·매니페스트 파일 접두어
# 판정기: E2 = 부속서5 §1, E3 = 부속서6 §2(후보 순서 sonnet-5-5 → haiku-5-5(추기 1), 교체는 부속서6 추기 커밋 뒤에만)
JUDGE = {"E2": "claude-opus-5-5", "E3": "claude-haiku-5-5", "E4": "claude-haiku-5-5",
         "E5P": "claude-haiku-5-5", "E5": "claude-haiku-5-5"}.get(EXP)
# 정답지: E4 = SF-300 v2(부속서6 추기 6, 운영자 재검수 4건). E5P/E5 = SF-K 분할(부속서8 §2). 상대 경로(gate/ 기준).
SF300 = {"E4": "scripts/sf300_label_set_v2.json", "E5P": "scripts/sfk_pilot.json",
         "E5": "scripts/sfk_main.json"}.get(EXP, "scripts/sf300_label_set.json")
# 운영자 검수 기록(INV-2 대상). E5* = 부속서8 §2-7 블라인드 30건.
REVIEW_XLSX = ("scripts/sfk_review_sheet_completed.xlsx" if EXP in ("E5P", "E5")
               else "scripts/sf300_review_sheet_completed.xlsx")
