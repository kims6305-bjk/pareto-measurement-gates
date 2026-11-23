"""실험 스위치 — `MH_EXP=E2` 일 때만 부속서5(E2) 값을 쓴다. 기본은 E1(기록 재현 보존).

E2 값이 E1 상수를 덮어쓰면 끝난 E1 의 재현 검사가 깨지므로, 상수는 모듈마다
`X = E2값 if E2 else E1값` 으로만 갈라 둔다. 파일 이름도 E2 접두어로 분리한다.
"""
import os

EXP = os.environ.get("MH_EXP", "E1")
if EXP not in ("E1", "E2"):
    raise SystemExit(f"MH_EXP={EXP!r} — E1 또는 E2 만 허용")
E2 = EXP == "E2"
TAG = "e2_" if E2 else ""          # 원자료·원장·매니페스트 파일 접두어
