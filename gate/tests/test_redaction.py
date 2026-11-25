"""공개본 익명화(3b39280) 검증 — 문제집 JSON 은 근거 문자열의 로컬 폴더명만 `<vault>/` 로 바뀌었는지,
그리고 기록된 prompt_sha256(정렬 첫 단위의 프롬프트 해시)에 영향이 없는지 확인한다.

원본은 git 이력(익명화 직전 커밋 3418319)에 그대로 있다. CI 처럼 얕은 클론이면 건너뛴다.
"""
import json
import pathlib
import re
import subprocess

import pytest

G = pathlib.Path(__file__).resolve().parents[1]
ORIG = "3418319"
MANIFEST = json.loads((G / "REDACTION_MANIFEST.json").read_text(encoding="utf-8"))


def _orig(rel):
    r = subprocess.run(["git", "show", f"{ORIG}:gate/{rel}"], cwd=G, capture_output=True)
    if r.returncode:
        pytest.skip(f"익명화 전 커밋 {ORIG} 없음(얕은 클론)")
    return json.loads(r.stdout.decode("utf-8"))


@pytest.mark.parametrize("rel", sorted(MANIFEST["files"]))
def test_placeholder_only_and_first_unit_untouched(rel):
    pub = json.loads((G / rel).read_text(encoding="utf-8"))
    org = _orig(rel)
    assert [u["id"] for u in pub] == [u["id"] for u in org]
    changed = []
    for p, o in zip(pub, org):
        if p == o:
            continue
        changed.append(p["id"])
        for k in p:
            if p[k] != o[k]:
                pat = "^" + re.escape(p[k]).replace(re.escape("<vault>/"), r"[^/\]\n]+/") + "$"
                assert re.match(pat, o[k], re.S), (p["id"], k)
    assert changed == MANIFEST["files"][rel]["changed_ids"]
    first = sorted(u["id"] for u in pub)[0]
    assert first not in changed and pub[0]["id"] not in changed  # prompt_sha256 입력 단위는 원문 그대로
