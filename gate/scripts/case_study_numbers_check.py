"""케이스 스터디 3판 수치·리터럴 보존 대조 — 번역 중 값이 새는지 잰다.

구조 대조(readme_parity_check)가 통과해도 문장 안의 수치가 빠질 수 있다.
출현 '횟수'까지 대조한다 — 번역하면서 반복 표현을 한 번으로 줄이면 논지가 죽는다.
"""
import re
import sys
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "docs"
BASE = D / "CASE_STUDY.md"
TARGETS = [D / "CASE_STUDY.en.md", D / "CASE_STUDY.zh-CN.md"]

# 본문 논지를 지탱하는 값들. 하나라도 빠지면 주장이 근거를 잃는다.
TOKENS = [
    # 콜 수·규모
    "2,145", "1,650", "165", "37",
    # 게이트 판정 수치
    "0.84%", "99.2%", "81.8%", "9/11", "0.5%",
    # p값·신뢰구간
    "0.031", "0.0625", "52.3%", "94.9%",
    # 파레토 3표 합의
    "90.0%", "38.9%", "35.2%",
    # Phase 2 기저율
    "3.3%", "1/30", "201", "171", "55",
    # 옆방 검증 축 분리
    "72.7%", "92.7%", "36.4%", "3.0%", "95.7%", "64.7%", "69.2%",
    # 문헌 수치
    "9.5", "55.9", "71.4", "86.6", "93.4", "61%", "88%", "3.6",
    # 실패 모드
    "12", "9/9", "271", "54",
    # 근거 문단
    "1019", "103",
    # 모델 고정
    "claude-sonnet-4-6",
    # 라벨 스키마 (번역되면 안 되는 리터럴)
    "SUPPORTED", "CONTRADICTED", "INSUFFICIENT",
    # 데이터셋 라이선스
    "CC BY-NC 2.0", "CC BY-SA 4.0", "K-IFRS",
]
ARXIV = r"arXiv:\d{4}\.\d{4,5}"

base_txt = BASE.read_text(encoding="utf-8")
base_arxiv = sorted(re.findall(ARXIV, base_txt))

print(f"기준 {BASE.name}: 토큰 {len(TOKENS)}종 / arXiv {len(base_arxiv)}건\n")
print(f"{'토큰':<22}{BASE.name:>18}" + "".join(f"{t.name:>22}" for t in TARGETS))

fail = False
for tok in TOKENS:
    n_base = base_txt.count(tok)
    if n_base == 0:
        continue
    counts = [t.read_text(encoding="utf-8").count(tok) for t in TARGETS]
    ok = all(c == n_base for c in counts)
    fail |= not ok
    mark = "✅" if ok else "🔴"
    print(f"{mark} {tok:<20}{n_base:>18}" + "".join(f"{c:>22}" for c in counts))

for t in TARGETS:
    a = sorted(re.findall(ARXIV, t.read_text(encoding="utf-8")))
    if a != base_arxiv:
        fail = True
        print(f"\n🔴 {t.name} arXiv 불일치: {set(base_arxiv) ^ set(a)}")

print()
if fail:
    sys.exit("🔴 수치·리터럴 보존 실패")
print("✅ 케이스 스터디 3판 수치·리터럴 전부 보존")
