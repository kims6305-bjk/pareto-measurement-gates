"""케이스 스터디 원자료(DEVLOG) → 레포 공개 문서 변환.

결정론적 변환만 한다. 본문 서술은 손대지 않고,
①내부용 메타(주석 헤더·인계 메모) 제거 ②이미지 참조를 레포 상대경로로
③화자 표기 통일(1인 저자 원칙) ④언어 스위처 삽입.

원자료 경로는 인자로 받는다 (레포 밖 경로를 코드에 박지 않기 위해).
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "CASE_STUDY.md"

src_path = Path(sys.argv[1])
t = src_path.read_text(encoding="utf-8")

# 1) 내부용 HTML 주석 헤더 제거
t = re.sub(r"^<!--.*?-->\n\n", "", t, flags=re.S)

# 2) 내부 인계 메모 절 제거 (레포 독자에게 무의미)
idx = t.find("## 🔴 작가봇 인계 메모")
if idx < 0:
    sys.exit("인계 메모 절을 찾지 못했다 — 원자료 형식 확인 필요")
t = re.sub(r"\n---\s*$", "", t[:idx].rstrip()).rstrip()

# 3) 이미지 참조 → 마크다운 이미지 (docs/ 내 상대경로)
t, n_img = re.subn(
    r"\*\*\[이미지: 2026-07-28_pareto-harness-gate_([a-z_]+\.png) — ([^\]]+)\]\*\*",
    lambda m: f"![{m.group(2).strip()}]({m.group(1)})",
    t,
)

# 4) 화자 통일 — 레포는 1인 저자 단수 원칙
for a, b in [
    ("저자의 질문:", "저자의 질문:"),
    ("사용자 질문:", "저자의 질문:"),
    ("사용자가 물었다", "저자가 물었다"),
    ("사용자가 짚은 것", "저자가 짚은 것"),
    ("사용자의 한 마디", "저자의 한 마디"),
    ("사용자가 설계를 고쳤다", "저자가 설계를 고쳤다"),
    ("사용자가 명시 요청함", "저자가 명시 요청함"),
]:
    t = t.replace(a, b)
# 화자를 가리키는 "사용자"만 남으면 안 된다. 단, "API 사용자"처럼 일반명사로
# 쓰인 것은 정상이므로 제외한다(실측: 이 검사가 §0의 API 사용자를 오탐했다).
leftover = [
    ln for ln in t.split("\n")
    if re.search(r"(?<!API )사용자(?!들)", ln)
]
if leftover:
    sys.exit(f"화자 표기 미변환 {len(leftover)}건: {leftover[:3]}")

# 5) 제목 + 언어 스위처
old_h1 = "# DEVLOG — 파레토: 하네스를 꽉 잡는다고 좋은 게 아니다"
if old_h1 not in t:
    sys.exit("H1을 찾지 못했다")
t = t.replace(
    old_h1,
    "# 케이스 스터디 — 파레토: 하네스를 꽉 잡는다고 좋은 게 아니다\n\n"
    "[English](CASE_STUDY.en.md) | **한국어** | [中文](CASE_STUDY.zh-CN.md)\n\n"
    "> 본 레포가 만들어진 하루의 개발 기록입니다. 설계 근거·실패·판정 과정을 순서대로\n"
    "> 남긴 것이며, 결과 요약은 [README](../README.md)를 보세요.",
    1,
)

# 6) 데이터 출처 부기
t += """

---

## 부록 — 데이터 출처

- SciFact (CC BY-NC 2.0, arXiv:2004.14500)
- KLUE-NLI (CC BY-SA 4.0, arXiv:2105.09680)
- K-IFRS 공개 기준서

**원본 데이터셋은 본 레포에 재배포하지 않습니다.** 재현 스크립트가 원천에서 내려받습니다.
"""

# 7) 레포 절대 URL 제거 — 계정 식별자가 들어가고, 레포 내부 문서라 상대링크가 맞다.
t = re.sub(
    r"\*\*레포\*\*: https://github\.com/\S+ \(MIT, README 한/영/중\)\n",
    "**레포**: 이 문서가 속한 레포 (MIT, README [한](../README.md) / "
    "[영](../README.en.md) / [중](../README.zh-CN.md))\n",
    t,
)
t = re.sub(
    r"- \*\*공개 레포\*\*: https://github\.com/\S+ \(MIT, README 한/영/중\)",
    "- **공개 레포**: 이 문서가 속한 레포 (MIT, README 한/영/중)",
    t,
)

# 8) 근거 인용의 출처를 명시 — 번역본에서 원문이 한국어 회계 기준서임이
#    드러나야 독자가 인용을 검증할 수 있다(번역 3판 정렬).
t = t.replace(
    "**근거 (1019 문단 103)**",
    "**근거 (K-IFRS 1019 문단 103, 한국어 기준서 원문)**",
)

OUT.write_text(t, encoding="utf-8")
print(f"이미지 참조 변환: {n_img}건")
print(f"분량 {len(t):,}자 / {t.count(chr(10)) + 1}줄")
print(
    "헤딩", len(re.findall(r"^#{1,6} ", t, re.M)),
    "| 표행", len(re.findall(r"^\|", t, re.M)),
    "| 코드펜스", t.count("```"),
    "| 이미지", len(re.findall(r"^!\[", t, re.M)),
)
print("saved:", OUT.relative_to(REPO))
