"""SF-300 주입 오류 라벨셋 생성기 — 부속서5 §2. 결정론, LLM 0콜.

정답은 구성 단계에서 정해진다:
  S      원천 문장 그대로 + 원천 근거          → S
  C-neg  원천 문장의 술어를 규칙표로 부정 1회  → C
  I-swap 원천 문장 그대로 + 다른 기준서 근거   → I
  I-drop 원천 문장 그대로 + 그 문장 삭제 근거  → I

usage:
    python sf_build_label_set.py            # sf300_label_set.json + 검수 시트/키 생성
    python sf_build_label_set.py --check    # 재생성 결과가 커밋본과 바이트 동일한지
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

GATE = Path(__file__).resolve().parents[1]
SRC = GATE.parent / "ab/ab_questions_FROZEN.json"
OUT = GATE / "scripts/sf300_label_set.json"
REVIEW_XLSX = GATE / "scripts/sf300_review_sheet.xlsx"
REVIEW_KEY = GATE / "scripts/sf300_review_key.json"

SF_SEED = 20261123
QUOTA = {"S": 150, "C": 75, "Iswap": 38, "Idrop": 37}
FAULT_CYCLE = ("C", "Iswap", "C", "Idrop")   # 짝의 오류 유형 1순위 (만석·부적격이면 다음)
REVIEW_QUOTA = {"S": 10, "C": 10, "Iswap": 5, "Idrop": 5}
LABEL = {"S": "S", "C": "C", "Iswap": "I", "Idrop": "I"}
DROP_SIM = 0.4        # I-drop: 남은 근거 문장 중 주장 3-gram 포함률 최댓값이 이 값 이상이면 부적격
NEG_BLOCK = re.compile(r"못|아니|않|모두|어느 때|적어도")   # 이중부정·범위 모호 → C-neg 부적격

HEAD = re.compile(r"^\[(?:(\d{4})\s*)?(문단[^\]]*?|[^\]]*?)\]", re.M)   # [1016 … 문단 7] · [문단 9](기준서=q.standard)

# 부정 규칙표 (부속서5 §2) — 구체적인 것부터. 맞는 규칙이 없으면 C-neg 부적격.
NEG_RULES = (
    (r"하지 (?:아니|않)한다\.$", "한다."),
    (r"하지 않는다\.$", "한다."),
    (r"되지 (?:아니|않)한다\.$", "된다."),
    (r"되지 않는다\.$", "된다."),
    (r"수 없다\.$", "수 있다."),
    (r"수 있다\.$", "수 없다."),
    (r"(?:하여야|해야) 한다\.$", "하지 않아야 한다."),
    (r"(?<=\S)된다\.$", "되지 않는다."),
    (r"(?<=[가-힣])이다\.$", "이 아니다."),
    (r"(?<=[가-힣])한다\.$", "하지 않는다."),
)


def h(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()


def norm(s: str) -> str:
    return re.sub(r"[\s\.,·()\[\]「」\"'’‘“”]", "", s)


def negate(s: str) -> str | None:
    body = re.sub(r"(?:하지 (?:아니|않)한다|되지 (?:아니|않)한다|하지 않는다|되지 않는다)\.$", "", s)
    if NEG_BLOCK.search(body):
        return None                        # 술어 밖에 부정·전칭이 있으면 1회 부정이 모호
    if re.search(r"[아-힣]야 한다\.$", s) and not re.search(r"(?:하여야|해야) 한다\.$", s):
        return None                        # '-어야 한다' 일반형은 어간 모호 → 부적격
    for pat, rep in NEG_RULES:
        if re.search(pat, s):
            return re.sub(pat, rep, s, count=1)
    return None


def sim(claim: str, other: str) -> float:
    """주장 3-gram 중 other 에도 있는 비율."""
    g = lambda t: {t[i:i + 3] for i in range(len(t) - 2)}
    a = g(norm(claim))
    return len(a & g(norm(other))) / max(1, len(a))


def blocks(evidence: str, std0: str = "") -> list[tuple[str, str, str]]:
    """[(기준서번호, 인용, 본문)]"""
    heads = list(HEAD.finditer(evidence))
    out = []
    for i, m in enumerate(heads):
        body = evidence[m.end(): heads[i + 1].start() if i + 1 < len(heads) else len(evidence)]
        std, rest = m.group(1) or std0, m.group(2)
        para = re.search(r"문단\s*(.+)$", rest)
        cite = f"{std} 문단 {para.group(1).strip()}" if para else f"{std} {rest}".strip()
        out.append((std, cite, body))
    return out


def sentences(qs: list[dict]) -> list[dict]:
    seen, out = set(), []
    for q in sorted(qs, key=lambda q: q["qid"]):
        for std, cite, body in blocks(q["evidence_paragraphs"], q["standard"][:4]):
            for raw in re.split(r"(?<=다\.)\s+", body):
                s = re.sub(r"^\s*[-*]?\s*(?:\(\d+\)|\d+\.|[가-하]\.|\([가-하]\))?\s*", "", raw.strip())
                if (not s.endswith("다.") or not 20 <= len(s) <= 160 or "\n" in s
                        or s.startswith("#") or re.search(r"다음[^.]*다\.$", s) or s in seen):
                    continue
                seen.add(s)
                out.append({"qid": q["qid"], "std": std, "cite": cite, "text": s})
    return out


def stds_of(q: dict) -> set[str]:
    return {std for std, _, _ in blocks(q["evidence_paragraphs"], q["standard"][:4])}


def fault(kind: str, s: dict, q: dict, qs: list[dict]) -> tuple[str, str, str] | None:
    """(주장, 근거, 근거 원천 qid) 또는 부적격 None."""
    claim, evidence = s["text"], q["evidence_paragraphs"]
    if kind == "C":
        neg = negate(claim)
        return (neg, evidence, s["qid"]) if neg and norm(neg) not in norm(evidence) else None
    if kind == "Idrop":                     # 주장이 든 문단 블록을 통째로 뺀다 (빈 번호 등 흔적 방지)
        heads = list(HEAD.finditer(evidence))
        for i, m in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(evidence)
            if claim in evidence[m.start():end]:
                rest = (evidence[:m.start()] + evidence[end:]).strip()
                left = [x for x in re.split(r"(?<=다\.)\s+|\n", HEAD.sub("", rest)) if len(x.strip()) > 5]
                ok = len(norm(HEAD.sub("", rest))) >= 40 and max((sim(claim, x) for x in left), default=1) < DROP_SIM
                return (claim, rest, s["qid"]) if ok else None
        return None
    others = sorted((o for o in qs if o["qid"] != s["qid"]
                     and s["std"] not in stds_of(o)
                     and norm(claim) not in norm(o["evidence_paragraphs"])),
                    key=lambda o: h(SF_SEED, "swap", s["qid"], claim, o["qid"]))
    return (claim, others[0]["evidence_paragraphs"], others[0]["qid"]) if others else None


def build() -> tuple[list[dict], dict]:
    """짝 설계: 원천 문장 1개 → S 1건 + 오류 1건 (부속서5 §9 추기 2)."""
    qs = json.loads(SRC.read_text(encoding="utf-8"))["questions"]
    byq = {q["qid"]: q for q in qs}
    pool = sorted(sentences(qs), key=lambda s: h(SF_SEED, s["qid"], s["text"]))
    filled = {k: 0 for k in QUOTA}
    units = []

    def add(kind: str, s: dict, q: dict, claim: str, evidence: str, src_ev: str, pair: str) -> str:
        filled[kind] += 1
        uid = f"{s['qid']}-sf-{kind}{filled[kind]:03d}"
        units.append({
            "id": uid, "kind": kind, "human_label": LABEL[kind], "pair": pair,
            "question": q["question"], "evidence": evidence,
            "claim_text": claim, "claim_citation": s["cite"], "siblings": [],
            "source": {"qid": s["qid"], "sentence": s["text"], "evidence_from": src_ev},
        })
        return uid

    for idx, s in enumerate(pool):
        if filled == QUOTA:
            break
        q = byq[s["qid"]]
        first = FAULT_CYCLE[idx % len(FAULT_CYCLE)]
        made = None
        for kind in (first,) + tuple(k for k in ("C", "Iswap", "Idrop") if k != first):
            if filled[kind] < QUOTA[kind] and (made := fault(kind, s, q, qs)):
                break
        if not made:
            continue                        # 오류를 만들 수 없는 문장은 짝째 버린다
        pair = h(SF_SEED, "pair", s["qid"], s["text"])[:12]
        add("S", s, q, s["text"], q["evidence_paragraphs"], s["qid"], pair)
        add(kind, s, q, *made, pair)
    if filled != QUOTA:
        raise SystemExit(f"정원 미달: {filled} != {QUOTA} (원천 문장 {len(pool)})")
    units.sort(key=lambda u: u["id"])
    meta = {"seed": SF_SEED, "n_pool": len(pool), "filled": filled}
    return units, meta


def review_sample(units: list[dict]) -> list[dict]:
    pick = []
    for kind, k in REVIEW_QUOTA.items():
        cand = sorted((u for u in units if u["kind"] == kind),
                      key=lambda u: h(SF_SEED, "review", u["id"]))
        taken = {u["pair"] for u in pick}
        pick += [u for u in cand if u["pair"] not in taken][:k]   # 같은 짝 두 건 동시 출제 금지
    return sorted(pick, key=lambda u: h(SF_SEED, "order", u["id"]))   # 유형이 섞이게


def write_review(sample: list[dict]) -> None:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = openpyxl.Workbook()
    info = wb.active
    info.title = "설명"
    for row in (
        ["SF-300 표본 검수 (30건) — 부속서5 §2"],
        [""],
        ["할 일: '검수' 시트 E열에 S / C / I 중 하나를 적는다. 회계 지식이 아니라 '근거만 보고' 판단한다."],
        ["S = 주장이 근거에 그대로 있거나 바로 도출된다"],
        ["C = 근거가 주장과 반대되는 내용을 말한다"],
        ["I = 근거만으로는 확인할 수 없다 (근거가 엉뚱하거나 해당 문장이 빠졌다)"],
        ["H열(메모)은 애매하면 이유를 한 줄."],
        [""],
        ["정답은 일부러 숨겼다(블라인드). 다 적으면 이 파일을 그대로 돌려주면 된다."],
    ):
        info.append(row)
    info["A1"].font = Font(bold=True, size=13)
    info.column_dimensions["A"].width = 100

    ws = wb.create_sheet("검수")
    head = ["번호", "질문", "근거", "검증할 주장", "판정(S/C/I)", "메모"]   # id 는 유형을 노출 → 키 파일에만
    ws.append(head)
    for i, u in enumerate(sample, 1):
        ws.append([i, u["question"], u["evidence"].strip(), u["claim_text"], None, None])
    fill = PatternFill("solid", fgColor="FFF2CC")
    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="D9E1F2")
    for col, w in zip("ABCDEF", (6, 40, 80, 45, 12, 30)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
        row[4].fill = fill
    dv = DataValidation(type="list", formula1='"S,C,I"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add(f"E2:E{len(sample) + 1}")
    ws.freeze_panes = "C2"
    wb.save(REVIEW_XLSX)


def main() -> None:
    units, meta = build()
    blob = json.dumps(units, ensure_ascii=False, indent=1) + "\n"
    if "--check" in sys.argv:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == blob
        print("sf_build --check:", "IDENTICAL" if same else "DIFFERENT")
        raise SystemExit(0 if same else 1)
    OUT.write_text(blob, encoding="utf-8")
    sample = review_sample(units)
    REVIEW_KEY.write_text(json.dumps(
        [{"no": i, "id": u["id"], "kind": u["kind"], "label": u["human_label"]}
         for i, u in enumerate(sample, 1)], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_review(sample)
    print(json.dumps(meta, ensure_ascii=False))
    print(f"saved {OUT.name} ({len(units)}건, sha256 {hashlib.sha256(blob.encode()).hexdigest()[:12]}…), "
          f"{REVIEW_XLSX.name} ({len(sample)}건)")


if __name__ == "__main__":
    main()
