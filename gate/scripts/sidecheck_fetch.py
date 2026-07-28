"""SciFact 다운로드 — 옆방 검증용. 원본 데이터는 레포에 재배포하지 않는다.

라이선스: CC BY-NC 2.0 (Wadden et al., EMNLP 2020, arXiv:2004.14500)
비상업적 연구 목적. 데이터는 <repo> 밖 캐시에 받는다.
"""
import tarfile
import urllib.request
from pathlib import Path

URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
CACHE = Path.home() / ".cache/scifact"


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    tgz = CACHE / "data.tar.gz"
    if not tgz.exists():
        print(f"다운로드: {URL}")
        urllib.request.urlretrieve(URL, tgz)
    else:
        print(f"캐시 사용: {tgz}")

    if not (CACHE / "data/claims_dev.jsonl").exists():
        with tarfile.open(tgz) as tf:
            tf.extractall(CACHE)  # noqa: S202
    for f in ("data/claims_dev.jsonl", "data/corpus.jsonl"):
        p = CACHE / f
        n = sum(1 for _ in open(p, encoding="utf-8"))
        print(f"  {f}: {n}행")
    print(f"\n캐시 위치: {CACHE}  (레포에 재배포하지 않음)")


if __name__ == "__main__":
    main()
