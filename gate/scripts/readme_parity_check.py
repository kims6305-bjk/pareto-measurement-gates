"""다국어 README 구조 대조 — 자식 자기보고를 믿지 않고 직접 잰다.

public-repo-release 스킬 §다국어 README 검수 게이트.
헤딩 수·레벨 시퀀스, 표 행, 코드펜스, 링크, 코드 리터럴 보존을 원본과 대조한다.
"""
import re
import sys
from pathlib import Path

P = Path("/Users/bjkim/.openclaw/workspace/projects/probe-graph-public")
BASE = "README.md"
TARGETS = ["README.en.md", "README.zh-CN.md"]

# 본문에 인용된 코드 리터럴 — 번역되면 복붙 시 안 도는 문서가 된다.
LITERALS = [
    "verdict='근거없음'",
    'any(verdict != "일치")',
    "[전체 답변]",
    "claims: []",
    "CONTRADICTED",
    "INSUFFICIENT",
    "SUPPORTED",
    "instrument_check_run.py",
    "instrument_check_score.py",
    "load_units()",
    "ab_questions_FROZEN.json",
]
NUMBERS = ["81.8%", "9/11", "1,650", "165", "38.9%", "35.2%", "3.3%", "0.84%",
           "99.2%", "p=0.125", "52.3%", "94.9%"]
ARXIV = r"arXiv:\d{4}\.\d{4,5}"


def profile(path: Path) -> dict:
    txt = path.read_text(encoding="utf-8")
    lines = txt.split("\n")
    # 코드펜스 안의 #는 헤딩이 아니다
    heads, infence = [], False
    for ln in lines:
        if ln.strip().startswith("```"):
            infence = not infence
            continue
        if infence:
            continue
        m = re.match(r"^(>?\s*)(#{1,6})\s", ln)
        if m:
            heads.append(len(m.group(2)))
    return {
        "headings": heads,
        "n_head": len(heads),
        "fences": txt.count("```"),
        "table_rows": sum(1 for ln in lines
                          if ln.strip().startswith("|") and not infence),
        "sep_rows": sum(1 for ln in lines if re.match(r"^\|[\s:|-]+\|$", ln.strip())),
        "links": re.findall(r"\]\(([^)]+)\)", txt),
        "arxiv": sorted(set(re.findall(ARXIV, txt))),
        "text": txt,
    }


base = profile(P / BASE)
print(f"기준 {BASE}: 헤딩 {base['n_head']} / 코드펜스 {base['fences']} / "
      f"표행 {base['table_rows']} / 링크 {len(base['links'])} / "
      f"arXiv {len(base['arxiv'])}\n")

fail = False
for t in TARGETS:
    p = P / t
    if not p.exists():
        print(f"🔴 {t} 없음")
        fail = True
        continue
    prof = profile(p)
    print(f"=== {t} ===")

    issues = []
    if prof["n_head"] != base["n_head"]:
        issues.append(f"헤딩 수 {prof['n_head']} != {base['n_head']}")
    elif prof["headings"] != base["headings"]:
        d = [i for i, (a, b) in enumerate(zip(base["headings"], prof["headings"]))
             if a != b]
        issues.append(f"헤딩 레벨 시퀀스 불일치 (index {d[:5]})")
    if prof["fences"] != base["fences"]:
        issues.append(f"코드펜스 {prof['fences']} != {base['fences']}")
    if prof["table_rows"] != base["table_rows"]:
        issues.append(f"표 행 {prof['table_rows']} != {base['table_rows']}")
    if prof["arxiv"] != base["arxiv"]:
        issues.append(f"arXiv ID 불일치: {set(base['arxiv']) ^ set(prof['arxiv'])}")

    # 코드 리터럴 보존
    for lit in LITERALS:
        if lit in base["text"] and lit not in prof["text"]:
            issues.append(f"코드 리터럴 소실: {lit!r}")
    # 수치 보존
    for num in NUMBERS:
        if num in base["text"] and num not in prof["text"]:
            issues.append(f"수치 소실: {num!r}")
    # 상대링크 실존
    for ln in prof["links"]:
        if ln.startswith(("http", "#", "mailto")):
            continue
        if not (P / ln.split("#")[0]).exists():
            issues.append(f"깨진 상대링크: {ln}")
    # 저자 복수형
    for bad in ["authors", "作者们", "저자들", " we ", " We "]:
        if bad in prof["text"]:
            issues.append(f"복수/1인칭 표기 발견: {bad!r}")

    if issues:
        fail = True
        for i in issues:
            print(f"  🔴 {i}")
    else:
        print(f"  ✅ 헤딩 {prof['n_head']} / 펜스 {prof['fences']} / "
              f"표행 {prof['table_rows']} / 링크 {len(prof['links'])} — 전부 일치")
    print()

sys.exit(1 if fail else 0)
