"""SF-K v4 주입 오류 라벨셋 생성기 — 부속서9 §2. 결정론, LLM 0콜.

v3(sfk_build_label_set.py) 대비 바뀌는 것(난이도 상향):
  1. 군집 = 같은 기준서의 **연속 4문단** 창(겹치지 않음). 근거가 길어 주의 분산이 커진다 — E4(SF300, 다문단 근거) haiku
     0.844/0.925 vs E5(2문단) 0.958/0.970 이 근거(e4_e5_compare.py).
  2. 지식 충돌형 2종 추가. Scf = 근거 속 문장과 주장을 **함께** 부정(정답 S, 기억과 반대). Ccf = 근거 속 문장만 부정하고
     주장은 원문 그대로(정답 C, 기억으로는 참).
  3. 오류 순환 = Idrop, Ccf, C, Idrop, Ccf, Iswap (I-drop 비중 상향 — E5 기준선 미검출 13/29 가 I-drop).
  4. 부정 결함 가드(e5_label_audit.py 결함 2건 + 7건 열람): '수 있다/없다' 부정은 부분·존재 범위어가 있으면 부적격,
     '이와 반대로'·'반대로'·'한편' 시작 문장은 주장 후보 제외.

usage:
    python sfk4_build_label_set.py            # 파일럿 100 + 본측정 N(기본 626, 추기3)
    python sfk4_build_label_set.py --n 520
    python sfk4_build_label_set.py --check    # 바이트 동일 + 구성 검사
    python sfk4_build_label_set.py --count    # 원천 풀만 센다(0 파일 쓰기)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sf_build_label_set import DROP_SIM, LABEL, h, negate, norm, sim  # noqa: E402
from sfk_build_label_set import AB, CONNECTIVE, NEG_AWKWARD, ev, paras, sents, source_files, stratified  # noqa: E402

GATE = Path(__file__).resolve().parents[1]
S = GATE / "scripts"
OUT = {k: S / f"sfk4_{k}.json" for k in ("meta", "pilot", "main")}
QFILES = [S / f"sfk4_questions_{sp}_FROZEN.json" for sp in ("pilot", "main")]
SEED = 20261128
W = 4                                        # 창 문단 수
PILOT_N = 100
FAULT_CYCLE = ("Idrop", "Ccf", "C", "Idrop", "Ccf", "Iswap")
LABEL4 = dict(LABEL, Scf="S", Ccf="C")
MODAL = re.compile(r"수 (?:있|없)다\.$")
PARTIAL = re.compile(r"일부|경우에 따라|경우도|때도|어떤 |도 있다")   # 존재·부분 범위 → '수 있다' 부정은 모순이 아님
CONNECTIVE4 = re.compile(r"^(?:이와 반대로|반대로|한편)")


def neg4(s: str) -> str | None:
    if NEG_AWKWARD.search(s) or (MODAL.search(s) and PARTIAL.search(s)):
        return None
    return negate(s)


def clusters() -> list[dict]:
    ab_norm = norm(" ".join(q["evidence_paragraphs"] for q in json.loads(AB.read_text(encoding="utf-8"))["questions"]))
    out = []
    for p in source_files():
        std = p.name[:4]
        ps = paras(p.read_text(encoding="utf-8"))
        k = 0
        while k + W <= len(ps):
            win = ps[k:k + W]
            cands = [(j, s) for j, (_, body) in enumerate(win) for s in sents(body)
                     if not CONNECTIVE.match(s) and not CONNECTIVE4.match(s) and s in body]
            if any(not b or norm(b) in ab_norm for _, b in win) or not cands:
                k += 1
                continue
            la = win[0][0]
            out.append({"cid": f"K{std}w{la.replace('-', '_')}", "hkey": f"K4-{std}-{la}", "std": std,
                        "win": win, "cands": cands})
            k += W
    return out


def others(c: dict, j: int) -> list[str]:
    """창 안에서 j 문단 밖 + j 문단의 주장 외 문장들 (재진술 가드용)."""
    return [x for i, (_, b) in enumerate(c["win"]) for x in re.split(r"(?<=다\.)\s+|\n", b)
            if len(x.strip()) > 5 and i != j]


def replaced(c: dict, j: int, old: str, new: str) -> list[tuple[str, str]]:
    return [(lab, b.replace(old, new, 1) if i == j else b) for i, (lab, b) in enumerate(c["win"])]


def fault(kind: str, c: dict, j: int, claim: str, pool: list[dict]):
    full = ev(c["std"], *c["win"])
    rest_ok = max((sim(claim, x) for x in others(c, j)), default=0) < DROP_SIM
    if kind == "C":
        neg = neg4(claim)
        return (neg, full, c["cid"]) if neg and norm(neg) not in norm(full) else None
    if kind == "Ccf":
        neg = neg4(claim)
        if not neg or not rest_ok:
            return None
        e = ev(c["std"], *replaced(c, j, claim, neg))
        return (claim, e, c["cid"]) if norm(claim) not in norm(e) else None
    if kind == "Idrop":
        keep = [b for i, b in enumerate(c["win"]) if i != j]
        e = ev(c["std"], *keep)
        return (claim, e, c["cid"]) if rest_ok and norm(claim) not in norm(e) else None
    o = sorted((o for o in pool if o["std"] != c["std"]
                and norm(claim) not in norm(" ".join(b for _, b in o["win"]))),
               key=lambda o: h(SEED, "swap", c["hkey"], claim, o["hkey"]))[0]
    return (claim, ev(o["std"], *o["win"]), o["cid"])


def make_units(c: dict, idx: int, pool: list[dict]) -> list[dict] | None:
    j, claim = sorted(c["cands"], key=lambda t: h(SEED, "claim", c["hkey"], t[1]))[0]
    first = FAULT_CYCLE[idx % len(FAULT_CYCLE)]
    for kind in (first,) + tuple(k for k in ("Idrop", "Ccf", "C", "Iswap") if k != first):
        if made := fault(kind, c, j, claim, pool):
            break
    else:
        return None
    s_kind, s_claim, s_ev = "S", claim, ev(c["std"], *c["win"])
    neg = neg4(claim)
    if int(h(SEED, "stype", c["hkey"]), 16) % 2 and neg:
        e = ev(c["std"], *replaced(c, j, claim, neg))
        if norm(claim) not in norm(e):                 # 같은 문장이 창에 또 있으면 S 로 둔다
            s_kind, s_claim, s_ev = "Scf", neg, e
    cite = f"{c['std']} 문단 {c['win'][j][0]}"
    base = {"pair": c["cid"], "claim_citation": cite, "siblings": [], "std": c["std"]}
    src = {"cid": c["cid"], "sentence": claim}
    s_unit = dict(base, id=f"{c['cid']}-{s_kind}", kind=s_kind, human_label="S", evidence=s_ev, claim_text=s_claim,
                  source=dict(src, evidence_from=c["cid"]))
    f_unit = dict(base, id=f"{c['cid']}-{kind}", kind=kind, human_label=LABEL4[kind], evidence=made[1],
                  claim_text=made[0], source=dict(src, evidence_from=made[2]))
    return [s_unit, f_unit]


def build(n_main: int) -> dict:
    pool = clusters()
    qs: dict[str, str] = {}
    for q in QFILES:
        if q.exists():
            qs.update(json.loads(q.read_text(encoding="utf-8")))
    made = [(c, us) for idx, c in enumerate(sorted(pool, key=lambda c: h(SEED, "cycle", c["hkey"])))
            if (us := make_units(c, idx, pool))]
    by_cid = {c["cid"]: us for c, us in made}
    pilot = stratified([c for c, _ in made], PILOT_N, seed=SEED)
    pids = {c["cid"] for c in pilot}
    main = stratified([c for c, _ in made if c["cid"] not in pids], n_main, seed=SEED)

    def units(cs):
        return sorted((dict(u, question=qs.get(u["pair"])) for c in cs for u in by_cid[c["cid"]]), key=lambda u: u["id"])
    return {"meta": {"seed": SEED, "window": W, "n_clusters_eligible": len(pool), "n_clusters_faultable": len(made),
                     "pilot_n": PILOT_N, "main_n": n_main,
                     "questions_sha256": {q.name: hashlib.sha256(q.read_bytes()).hexdigest() for q in QFILES if q.exists()},
                     "source_manifest": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files()}},
            "pilot": units(pilot), "main": units(main)}


def check_construction(d: dict) -> None:
    for split in ("pilot", "main"):
        us = d[split]
        assert len(us) == 2 * d["meta"][f"{split}_n"] and len({u["pair"] for u in us}) == d["meta"][f"{split}_n"], split
        for u in us:
            in_ev = norm(u["claim_text"]) in norm(u["evidence"])
            assert in_ev == (u["kind"] in ("S", "Scf")), u["id"]       # S 류만 주장이 근거에 그대로 있다
            assert u["human_label"] == LABEL4[u["kind"]], u["id"]
            if u["kind"] in ("Scf", "Ccf"):
                assert norm(u["source"]["sentence"]) not in norm(u["evidence"]), u["id"]   # 원문 문장이 근거에서 지워졌다
            if u["kind"] == "Ccf":
                assert norm(neg4(u["claim_text"]) or "") in norm(u["evidence"]), u["id"]
            if u["kind"] == "Iswap":
                assert not u["evidence"].startswith(f"[{u['std']} "), u["id"]
    assert not ({u["pair"] for u in d["pilot"]} & {u["pair"] for u in d["main"]}), "파일럿·본측정 겹침"


def main() -> None:
    args = sys.argv[1:]
    if "--count" in args:
        pool = clusters()
        made = [c for idx, c in enumerate(sorted(pool, key=lambda c: h(SEED, "cycle", c["hkey"])))
                if make_units(c, idx, pool)]
        print(f"창 {len(pool)}, 단위 생성 가능 {len(made)}, 기준서 {len({c['std'] for c in made})}")
        return
    d = build(int(args[args.index("--n") + 1]) if "--n" in args else 626)   # 부속서9 추기3: 폭 파일럿 정원 N=626
    check_construction(d)
    blobs = {OUT[k]: json.dumps(d[k], ensure_ascii=False, indent=1, sort_keys=True) + "\n" for k in OUT}
    if "--check" in args:
        same = all(p.exists() and p.read_text(encoding="utf-8") == b for p, b in blobs.items())
        print("check:", "OK (바이트 동일 + 구성 검사 통과)" if same else "FAIL (커밋본과 다름)")
        raise SystemExit(0 if same else 1)
    for p, b in blobs.items():
        p.write_text(b, encoding="utf-8")
    kinds: dict[str, int] = {}
    for sp in ("pilot", "main"):
        for u in d[sp]:
            kinds[f"{sp}:{u['kind']}"] = kinds.get(f"{sp}:{u['kind']}", 0) + 1
    print(json.dumps({k: v for k, v in d["meta"].items() if k != "source_manifest"}, ensure_ascii=False), kinds)


if __name__ == "__main__":
    main()
