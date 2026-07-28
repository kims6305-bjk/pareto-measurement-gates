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
    "kims6305", "디아이동일", "일신방직", "경방", "전방", "아빠",
    "텔레그램", "telegram", "live-bot-safe", "citation-audit-shadow",
    "accountant-", "tax-yuseong", "secretary-", "kalkim", "kbj20514",
]
EXT = {".md", ".py", ".json", ".sh", ".yml", ".yaml", ".txt", ".jsonl", ".toml"}

files = [f for f in P.rglob("*")
         if f.is_file() and f.suffix in EXT and ".git" not in f.parts
         and ".venv" not in f.parts
         and f.name != Path(__file__).name]   # 검사기 자신의 단어장은 제외

hits = {}
for f in files:
    try:
        txt = f.read_text(encoding="utf-8", errors="ignore")
    except Exception:  # noqa: BLE001
        continue
    for w in BAD:
        for m in re.finditer(w, txt, re.I):
            line = txt[: m.start()].count("\n") + 1
            hits.setdefault(w, []).append(f"{f.relative_to(P)}:{line}")

print(f"스캔: {len(files)}개 파일 / 단어장 {len(BAD)}개")
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
