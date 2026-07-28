"""3판 README의 신규 수치·라이선스 표기 보존 검사 (parity_check 보완).

parity_check는 구조와 코드 리터럴을 본다. 이 스크립트는 이번 갱신에서
새로 들어간 실측 수치가 3판 모두에 살아있는지 확인한다.
"""
import sys
from pathlib import Path

P = Path("/Users/bjkim/.openclaw/workspace/projects/probe-graph-public")
FILES = ["README.md", "README.en.md", "README.zh-CN.md"]

# 이번 옆방 검증에서 새로 들어간 수치·식별자
MUST = ["2/2 PASS", "36.4", "3.0", "92.7", "72.7", "95.7", "64.7",
        "81.8", "100%", "2004.14500", "2105.09680",
        "SIDECHECK_PREREG.md", "SIDECHECK_RESULT.md", "--room"]

texts = {f: (P / f).read_text(encoding="utf-8") for f in FILES}
fail = False
print(f"{'토큰':<22} " + " ".join(f"{f:>16}" for f in FILES))
for tok in MUST:
    counts = [texts[f].count(tok) for f in FILES]
    ok = all(c > 0 for c in counts)
    if not ok:
        fail = True
    mark = "✅" if ok else "🔴"
    print(f"{mark} {tok:<20} " + " ".join(f"{c:>16}" for c in counts))

print()
if fail:
    print("🔴 일부 수치가 번역판에서 소실됨")
    sys.exit(1)
print("✅ 신규 수치·링크 전부 3판 보존")
