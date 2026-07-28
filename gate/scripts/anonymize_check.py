"""익명화 전수검사 — public-repo-release 스킬 게이트.

부분 grep이 아니라 단어장 rglob 전수검사. "0건 ✅"가 나와야 push 가능.
실측 교훈: 코드 주석·docstring이 최다 누출 경로다.
"""
import re
import sys
from pathlib import Path

P = Path("/Users/bjkim/.openclaw/workspace/projects/probe-graph-public")

BAD = [
    "bjkim", "유성", "회계사", "세무사", "카카오", "openclaw", r"\.hermes",
    "kims6305", "아빠",
    "텔레그램", "telegram", "live-bot-safe", "citation-audit-shadow",
    "accountant-", "tax-yuseong", "secretary-", "kalkim", "kbj20514",
]
# 회사명은 단어 경계를 요구한다. 짧은 한글 회사명(전방·경방)은 일반 용어
# (전방/후방, anterior 번역어 등)와 충돌하므로 문맥 한정 패턴으로만 잡는다.
# 실측 오탐: 생의학 근거의 "전방 막(anterior membrane)"이 회사명으로 걸렸다.
BAD_STRICT = [
    r"디아이동일", r"일신방직",
    r"\(주\)\s*경방", r"경방\s*\(주\)", r"주식회사\s*경방",
    r"\(주\)\s*전방", r"전방\s*\(주\)", r"주식회사\s*전방",
]
EXT = {".md", ".py", ".json", ".sh", ".yml", ".yaml", ".txt", ".jsonl", ".toml"}
# 검사·검수 스크립트는 경로/단어장 자체를 코드에 담으므로 스캔 대상에서 제외한다.
SELF = {"anonymize_check.py", "readme_parity_check.py"}

files = [f for f in P.rglob("*")
         if f.is_file() and f.suffix in EXT and ".git" not in f.parts
         and ".venv" not in f.parts
         and f.name not in SELF]

hits = {}
for f in files:
    try:
        txt = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        continue
    for w in BAD + BAD_STRICT:
        for m in re.finditer(w, txt, re.I):
            line = txt[: m.start()].count("\n") + 1
            hits.setdefault(w, []).append(f"{f.relative_to(P)}:{line}")

print(f"스캔: {len(files)}개 파일 / 단어장 {len(BAD)+len(BAD_STRICT)}개")
if not hits:
    print("\n익명화 전수검사: 0건 ✅  push 가능")
    sys.exit(0)

total = sum(len(v) for v in hits.values())
print(f"\n🔴 누출 {total}건 — push 차단\n")
for w, locs in sorted(hits.items(), key=lambda x: -len(x[1])):
    print(f"'{w}' {len(locs)}건")
    for loc in locs[:10]:
        print(f"    {loc}")
    if len(locs) > 10:
        print(f"    ... 외 {len(locs)-10}건")
sys.exit(1)
