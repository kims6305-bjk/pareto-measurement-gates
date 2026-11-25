"""SF-K 주입 오류 라벨셋 생성기 — 부속서8 §2. 결정론, LLM 0콜.

원천 = 옵시디언 K-IFRS 전문 본문 43개. 군집 = 같은 기준서의 연속 문단 짝(겹치지 않음).
정답은 sf_build_label_set.py 와 같은 규칙으로 구성 단계에서 정해진다 (S · C-neg · I-swap · I-drop).
질문 문장은 sfk_questions_FROZEN.json(군집 id → 질문)에서 읽는다. 없으면 question=null.

usage:
    python sfk_build_label_set.py            # 파일럿 100 + 본측정 N(기본 400) 생성
    python sfk_build_label_set.py --n 520    # 정원 확정 추기 후
    python sfk_build_label_set.py --check    # 재생성 결과가 커밋본과 바이트 동일한지 + 구성 검사
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf_build_label_set import DROP_SIM, LABEL, h, negate, norm, sim  # noqa: E402

GATE = Path(__file__).resolve().parents[1]
SRC = Path(os.environ.get("SFK_KIFRS_DIR", "/nonexistent-kifrs-corpus"))  # 로컬 K-IFRS 전문 폴더(레포 밖)
AB = GATE.parent / "ab/ab_questions_FROZEN.json"
QFILE = GATE / "scripts/sfk_questions_FROZEN.json"
OUT = {k: GATE / f"scripts/sfk_{k}.json" for k in ("meta", "pilot", "main")}
SEED = 20261126                              # 추기 2: 검수 v2 결함으로 새 seed 재생성 (v1 = 20261124, v2 = 20261125)
PILOT_N = 100
CAP = 0.10                                   # 한 기준서 상한 = 정원의 10%
FAULT_CYCLE = ("C", "Iswap", "C", "Idrop")
LIST_ITEM = re.compile(r"^\s*[-*]\s|^\s*(?:\(\d+\)|\d+\.|[가-하]\.|\([가-하]\))\s")
CONNECTIVE = re.compile(r"^(?:따라서|그러나|그러므로|그런데|또한|하지만|즉|이러한|이와 같은|이 경우|이때|그러한|위의|앞의|예를 들어|예컨대|마찬가지로|이에 따라|이 개정|동 개정)")
NEG_AWKWARD = re.compile(r"(?:때문|것)이다\.$"   # 추기 1: '~때문이 아니다'·'~것이 아니다' 는 비문 → C-neg 부적격
                         r"|(?:하고|하며|하되|이고|이며|되고|되며),? |거나,? |도록,? |도 [^.]*수 있다\.$")   # 추기 2: 복문은 끝 술어만 부정돼 비문
DEPENDENT = re.compile(r"때문이다\.$")        # 추기 2: 앞 문장에 기대는 이유문 → 주장 후보 제외
PARA = re.compile(r"^### 문단 (\S+)\s*$", re.M)


def source_files() -> list[Path]:
    return sorted(p for p in SRC.glob("*.md") if re.match(r"^1\d{3} ", p.name) and " — " not in p.name)


def paras(text: str) -> list[tuple[str, str]]:
    ms = list(PARA.finditer(text))
    out = []
    for i, m in enumerate(ms):
        body = text[m.end(): ms[i + 1].start() if i + 1 < len(ms) else len(text)]
        out.append((m.group(1), re.split(r"^#{1,2} ", body, flags=re.M)[0].strip()))
    return out


def sents(t: str) -> list[str]:
    out = []
    for raw in re.split(r"(?<=다\.)\s+", t):
        if LIST_ITEM.match(raw) or CONNECTIVE.match(raw.strip()):
            continue                         # 추기 1: 목록 조각(주어 탈락)·앞 문맥 의존 문장 제외
        s = re.sub(r"^\s*[-*]?\s*(?:\(\d+\)|\d+\.|[가-하]\.|\([가-하]\))?\s*", "", raw.strip())
        if (s.endswith("다.") and 20 <= len(s) <= 160 and "\n" not in s and not s.startswith("#")
                and not re.search(r"다음[^.]*다\.$", s) and not DEPENDENT.search(s) and s not in out):
            out.append(s)
    return out


def clusters() -> list[dict]:
    ab_norm = norm(" ".join(q["evidence_paragraphs"] for q in json.loads(AB.read_text(encoding="utf-8"))["questions"]))
    out = []
    for p in source_files():
        std = p.name[:4]
        ps = paras(p.read_text(encoding="utf-8"))
        k = 0
        while k + 1 < len(ps):
            (la, a), (lb, b) = ps[k], ps[k + 1]
            ss = sents(a)
            if (not a or not b or norm(a) in ab_norm or norm(b) in ab_norm
                    or not ss or len(norm(b)) < 40):
                k += 1
                continue
            # id 첫 '-' 앞 = Unit.qid(군집) 이 되도록 문단 번호 속 '-' 는 '_' 로
            out.append({"cid": f"K{std}p{la.replace('-', '_')}", "hkey": f"K{std}-{la}",   # hkey = 추출 해시 키(4952f6d 표본 유지)
                        "std": std, "a": (la, a), "b": (lb, b), "sents": ss})
            k += 2
    return out


def ev(std: str, *blocks: tuple[str, str]) -> str:
    return "\n\n".join(f"[{std} 문단 {lab}]\n{body}" for lab, body in blocks)


def fault(kind: str, c: dict, claim: str, pool: list[dict]):
    if kind == "C":
        neg = None if NEG_AWKWARD.search(claim) else negate(claim)
        full = ev(c["std"], c["a"], c["b"])
        return (neg, full, c["cid"]) if neg and norm(neg) not in norm(full) else None
    if kind == "Idrop":                      # 주장이 든 k 문단을 통째로 뺀다
        rest = c["b"][1]
        left = [x for x in re.split(r"(?<=다\.)\s+|\n", rest) if len(x.strip()) > 5]
        ok = norm(claim) not in norm(rest) and max((sim(claim, x) for x in left), default=1) < DROP_SIM
        return (claim, ev(c["std"], c["b"]), c["cid"]) if ok else None
    others = sorted((o for o in pool if o["std"] != c["std"]
                     and norm(claim) not in norm(o["a"][1] + o["b"][1])),
                    key=lambda o: h(SEED, "swap", c["hkey"], claim, o["hkey"]))
    o = others[0]
    return (claim, ev(o["std"], o["a"], o["b"]), o["cid"])


def make_units(c: dict, idx: int, pool: list[dict]) -> list[dict] | None:
    claim = sorted(c["sents"], key=lambda s: h(SEED, "claim", c["hkey"], s))[0]
    first = FAULT_CYCLE[idx % len(FAULT_CYCLE)]
    for kind in (first,) + tuple(k for k in ("C", "Iswap", "Idrop") if k != first):
        if made := fault(kind, c, claim, pool):
            break
    else:
        return None
    cite = f"{c['std']} 문단 {c['a'][0]}"
    base = {"pair": c["cid"], "claim_citation": cite, "siblings": [], "std": c["std"]}
    s_unit = dict(base, id=f"{c['cid']}-S", kind="S", human_label="S",
                  evidence=ev(c["std"], c["a"], c["b"]), claim_text=claim,
                  source={"cid": c["cid"], "sentence": claim, "evidence_from": c["cid"]})
    f_unit = dict(base, id=f"{c['cid']}-{kind}", kind=kind, human_label=LABEL[kind],
                  evidence=made[1], claim_text=made[0],
                  source={"cid": c["cid"], "sentence": claim, "evidence_from": made[2]})
    return [s_unit, f_unit]


def stratified(cands: list[dict], n: int, seed: int = SEED) -> list[dict]:
    """기준서별 비례 배분(최대 잔여법) + 상한. 기준서 안에서는 seed 해시 순서. seed 인자 = 부속서9(v4) 재사용."""
    by: dict[str, list[dict]] = {}
    for c in sorted(cands, key=lambda c: h(seed, "draw", c["hkey"])):
        by.setdefault(c["std"], []).append(c)
    cap, total = int(n * CAP), len(cands)
    quota = {s: min(cap, len(v), n * len(v) // total) for s, v in by.items()}
    rem = sorted(by, key=lambda s: (-(n * len(by[s]) % total), s))
    while sum(quota.values()) < n:           # 남은 자리를 잔여 큰 순으로 1개씩
        moved = False
        for s in rem:
            if sum(quota.values()) < n and quota[s] < min(cap, len(by[s])):
                quota[s] += 1
                moved = True
        if not moved:
            raise SystemExit(f"정원 {n} 을 상한 {cap} 안에서 채울 수 없다")
    return [c for s in sorted(by) for c in by[s][:quota[s]]]


def build(n_main: int) -> dict:
    pool = clusters()
    questions = json.loads(QFILE.read_text(encoding="utf-8")) if QFILE.exists() else {}
    made = []                                # 오류를 만들 수 있는 군집만 (짝째 버림)
    for idx, c in enumerate(sorted(pool, key=lambda c: h(SEED, "cycle", c["hkey"]))):
        if (us := make_units(c, idx, pool)):
            made.append((c, us))
    by_cid = {c["cid"]: us for c, us in made}
    pilot = stratified([c for c, _ in made], PILOT_N)
    pilot_ids = {c["cid"] for c in pilot}
    main = stratified([c for c, _ in made if c["cid"] not in pilot_ids], n_main)

    def units(cs):
        return sorted((dict(u, question=questions.get(u["pair"])) for c in cs for u in by_cid[c["cid"]]),
                      key=lambda u: u["id"])
    manifest = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files()}
    return {"meta": {"seed": SEED, "n_clusters_eligible": len(pool), "n_clusters_faultable": len(made),
                     "pilot_n": PILOT_N, "main_n": n_main, "cap": CAP,
                     "questions_file_sha256": hashlib.sha256(QFILE.read_bytes()).hexdigest() if QFILE.exists() else None,
                     "source_manifest": manifest},
            "pilot": units(pilot), "main": units(main)}


def check_construction(d: dict) -> None:
    for split in ("pilot", "main"):
        us = d[split]
        assert len(us) == 2 * d["meta"][f"{split}_n"], split
        cids = {u["pair"] for u in us}
        assert len(cids) == d["meta"][f"{split}_n"]
        for u in us:
            in_ev = norm(u["claim_text"]) in norm(u["evidence"])
            if u["kind"] == "S":
                assert in_ev, u["id"]
            else:
                assert not in_ev, u["id"]     # 오류 단위의 주장은 근거에 그대로 있으면 안 된다
            if u["kind"] == "Iswap":
                assert not u["evidence"].startswith(f"[{u['std']} "), u["id"]
        cnt: dict[str, int] = {}
        for c in cids:
            cnt[c[1:5]] = cnt.get(c[1:5], 0) + 1
        assert max(cnt.values()) <= int(d["meta"][f"{split}_n"] * CAP), cnt
    assert not ({u["pair"] for u in d["pilot"]} & {u["pair"] for u in d["main"]}), "파일럿·본측정 겹침"


def main() -> None:
    args = sys.argv[1:]
    n = int(args[args.index("--n") + 1]) if "--n" in args else 400
    d = build(n)
    check_construction(d)
    # 러너·채점기(load_units·load_labels)는 단위 리스트 json 을 읽으므로 분할별 파일로 쓴다.
    blobs = {OUT[k]: json.dumps(d[k], ensure_ascii=False, indent=1, sort_keys=True) + "\n" for k in OUT}
    if "--check" in args:
        same = all(p.exists() and p.read_text(encoding="utf-8") == b for p, b in blobs.items())
        print("check:", "OK (바이트 동일 + 구성 검사 통과)" if same else "FAIL (커밋본과 다름)")
        raise SystemExit(0 if same else 1)
    for p, b in blobs.items():
        p.write_text(b, encoding="utf-8")
    kinds: dict[str, int] = {}
    for u in d["main"]:
        kinds[u["kind"]] = kinds.get(u["kind"], 0) + 1
    print(json.dumps({k: v for k, v in d["meta"].items() if k != "source_manifest"}, ensure_ascii=False),
          "main kinds", kinds, "files", len(d["meta"]["source_manifest"]))


if __name__ == "__main__":
    main()
