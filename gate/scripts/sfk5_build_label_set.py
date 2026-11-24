"""SF-K v5 — 부속서12. v4 문제집(군집·질문·S 단위·Idrop 불변)에서 **강한 판정기가 전부 맞힌 쉬운 오류형**
(C·Ccf·Iswap, E7 sonnet·opus 303/304)을 **한 단어 최소 편집** 모순으로 바꾼다. 결정론, LLM 0콜.
  Cmin   = 주장만 한 단어(반의어·역할어) 또는 기간·비율 숫자를 바꿈, 근거는 원문 창 그대로 (정답 C)
  Ccfmin = 근거 속 그 문장만 같은 방식으로 바꿈, 주장은 원문 그대로 (정답 C, 기억으로는 참)
편집 불가 문장이면 v4 오류 단위를 그대로 둔다.
usage: python sfk5_build_label_set.py [--check]
"""
import hashlib
import json
import re
import sys
from pathlib import Path

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
from sf_build_label_set import h, norm  # noqa: E402
from sfk4_build_label_set import SEED, clusters, ev, replaced  # noqa: E402

_B = r"(?=[\s,.)’”]|[을를은는이가과와의에도나로으및])"     # 단어 끝(조사·구두점) — 합성어 속(자산손상·투자자산) 편집 금지
PAIRS = [(a, b, bound) for bound, ps in (
    (False, [("리스이용자", "리스제공자"), ("피취득자", "취득자"), ("지배기업", "종속기업"), ("당기손익", "기타포괄손익"),
             ("유형자산", "무형자산"), ("금융자산", "금융부채"), ("우발자산", "우발부채"), ("증가", "감소"),
             ("초과", "미만"), ("차변", "대변"), ("유리한", "불리한"), ("포함한다", "제외한다")]),
    (True, [("이상", "이하"), ("자산", "부채"), ("수익", "비용"), ("유입", "유출"), ("장기", "단기"), ("직접", "간접")]))
    for a, b in ps]   # 뺀 쌍(라벨 잡음): 최초↔후속(비문), 손실↔이익(변동이익 문맥에서 둘 다 참)


def pat(w: str, bound: bool) -> str:
    return (rf"(?<![가-힣]){w}{_B}" if bound else rf"(?<!피){w}" if w == "취득자" else w)


NUM = re.compile(r"(?<![\d.,])(\d{1,3})(개월|일|%|퍼센트|년(?!도))")   # 연도(2011년)는 4자리라 제외
JOSA = [("이나", "나"), ("으로", "로"), ("을", "를"), ("은", "는"), ("과", "와"), ("이 ", "가 ")]   # (받침 O, 받침 X)


def josa(s: str, end: int) -> str:
    """end 앞 글자 받침에 맞게 바로 뒤 조사를 고친다(부채을 → 부채를)."""
    has = (ord(s[end - 1]) - 0xAC00) % 28 != 0 if "가" <= s[end - 1] <= "힣" else None
    for o, x in JOSA:
        for cur, want in ((o, x), (x, o)):
            if has is not None and s.startswith(cur, end) and want == (o if has else x) and cur != want:
                return s[:end] + want + s[end + len(cur):]
    return s
LABEL5 = {"Cmin": "C", "Ccfmin": "C"}
EASY = ("C", "Ccf", "Iswap")
OUT = {sp: S / f"sfk5_{sp}.json" for sp in ("pilot", "main")}


def minedit(s: str):
    """첫 적용 가능 규칙 하나로 한 군데만 바꾼다. 반대어가 이미 문장에 있으면(대비 문장) 그 쌍은 건너뛴다."""
    for a, b, bound in PAIRS:
        for x, y in ((a, b), (b, a)):
            m = re.search(pat(x, bound), s)
            if m and y not in s[:m.start()] + s[m.end():] and s[:m.start()].count("‘") == s[:m.start()].count("’"):   # 대비문·인용 제목 속 편집 금지
                return josa(s[:m.start()] + y + s[m.end():], m.start() + len(y))
    m = NUM.search(s)
    if m and int(m.group(1)) > 0:
        return s[:m.start(1)] + str(int(m.group(1)) * 2) + s[m.end(1):]
    return None


def build() -> tuple:
    cl = {c["cid"]: c for c in clusters()}
    out, n = {}, {}
    for sp in OUT:
        units = json.loads((S / f"sfk4_{sp}.json").read_text(encoding="utf-8"))
        new = []
        for u in units:
            c = cl[u["pair"]]
            # 주장 문장: v4 문장 먼저, 안 되면 같은 창의 다른 후보 문장(질문은 창 근거로만 만들었으므로 무관)
            order = [u["source"]["sentence"]] + [s for _, s in sorted(c["cands"], key=lambda t: h(SEED, "v5c", u["pair"], t[1]))]
            sent = next((s for s in order if minedit(s)), None) if u["kind"] in EASY else None
            if sent:
                e = minedit(sent)
                j = next(i for i, (_, b) in enumerate(c["win"]) if sent in b)
                full = ev(c["std"], *c["win"])
                kind = "Cmin" if int(h(SEED, "v5", u["pair"]), 16) % 2 else "Ccfmin"
                claim, evi = (e, full) if kind == "Cmin" else (sent, ev(c["std"], *replaced(c, j, sent, e)))
                if norm(claim) not in norm(evi):
                    u = dict(u, id=f"{u['pair']}-{kind}", kind=kind, human_label="C", claim_text=claim, evidence=evi,
                             source=dict(u["source"], sentence=sent, evidence_from=u["pair"], edited=e),
                             claim_citation=f"{c['std']} 문단 {c['win'][j][0]}")
            n[f"{sp}:{u['kind']}"] = n.get(f"{sp}:{u['kind']}", 0) + 1
            new.append(u)
        out[sp] = sorted(new, key=lambda u: u["id"])
    return out, n


def check(d: dict) -> None:
    for sp, us in d.items():
        v4 = json.loads((S / f"sfk4_{sp}.json").read_text(encoding="utf-8"))
        assert {u["pair"] for u in us} == {u["pair"] for u in v4} and len(us) == len(v4), sp
        keep = {u["id"]: u for u in v4 if u["kind"] not in EASY}
        for u in us:
            if u["id"] in keep:
                assert u == keep[u["id"]], u["id"]                         # S·Scf·Idrop 바이트 불변
            if u["kind"] in LABEL5:
                assert u["human_label"] == "C" and norm(u["claim_text"]) not in norm(u["evidence"]), u["id"]
                e, s = u["source"]["edited"], u["source"]["sentence"]
                assert e != s and len(e) - len(s) in range(-3, 5), u["id"]   # 한 단어급 편집
                if u["kind"] == "Cmin":
                    assert u["claim_text"] == e and norm(s) in norm(u["evidence"]), u["id"]
                else:
                    assert u["claim_text"] == s and norm(e) in norm(u["evidence"]), u["id"]


def selftest() -> None:
    assert minedit("리스이용자는 사용권자산을 인식한다.") == "리스제공자는 사용권자산을 인식한다."
    assert minedit("피취득자의 자산과 부채를 측정한다.") == "취득자의 자산과 부채를 측정한다."   # 자산·부채 대비문 건너뜀
    assert minedit("12개월 이내에 결제한다.") == "24개월 이내에 결제한다."
    assert minedit("공정가치로 측정한다.") is None
    assert minedit("모든 수익과 비용으로 구성된다.") is None and minedit("‘고객과의 계약에서 생기는 수익’에 따라") is None
    assert minedit("자산손상 징후를 본다.") is None and minedit("투자자의 이익이 달라진다.") is None
    assert minedit("자산을 인식한다.") == "부채를 인식한다." and minedit("부채는 크다.") == "자산은 크다."
    assert minedit("2011년 1월 1일 이후 시작하는 회계연도") is None or "2011년" in minedit("2011년 1월 1일 이후 시작하는 회계연도")


if __name__ == "__main__":
    selftest()
    d, n = build()
    check(d)
    blobs = {OUT[sp]: json.dumps(us, ensure_ascii=False, indent=1, sort_keys=True) + "\n" for sp, us in d.items()}
    if "--check" in sys.argv:
        ok = all(p.exists() and p.read_text(encoding="utf-8") == b for p, b in blobs.items())
        print("check:", "OK" if ok else "FAIL")
        raise SystemExit(0 if ok else 1)
    for p, b in blobs.items():
        p.write_text(b, encoding="utf-8")
        print(p.name, hashlib.sha256(b.encode()).hexdigest()[:16])
    print(dict(sorted(n.items())))
