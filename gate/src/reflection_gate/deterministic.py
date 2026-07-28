"""결정론 레이어 — LLM 없이 100% 재현 가능한 구조 검사.

①스키마 검사: malformed/truncated JSON, 답변 본문은 있는데 claims=[], 중복 claim ID
②인용 주소 검사: (기준서번호, 문단, 하위항) 튜플 전체 + source_id 실존,
  그리고 quote가 근거 원문에 substring으로 실존하는지.

모든 실패는 policy.Reason으로 표현되며, 강제 INDETERMINATE 목록에 걸린다.
"""
from __future__ import annotations

import json
import re
from typing import Any, List, Optional, Tuple

from .models import Claim, EvidenceBundle, Locator, normalize_text
from .policy import DEFAULT_LIMITS, Finding, Limits, Reason

# "1002 문단 34", "[1002 재고자산 문단 34]", "1002 문단 34-(2)", "K-IFRS 1116 문단 9(1)"
_CIT = re.compile(
    r"(?P<standard>\d{3,4})\s*[^\d\[\]]*?문단\s*(?P<paragraph>\d+[A-Za-z]?)"
    r"\s*(?:[-–]\s*)?(?:\((?P<subitem>[^)]{1,12})\))?"
)


def parse_citation(raw: Any) -> Optional[Locator]:
    """문자열 또는 dict 인용을 Locator로 변환. 실패하면 None."""
    if isinstance(raw, dict):
        std = str(raw.get("standard", "")).strip()
        para = str(raw.get("paragraph", "")).strip()
        sub = raw.get("subitem")
        sub = str(sub).strip() if sub not in (None, "") else None
        # paragraph 안에 하위항이 섞여 들어온 경우: "34(2)"
        m = re.fullmatch(r"(\d+[A-Za-z]?)\s*\(([^)]+)\)", para)
        if m:
            para, sub = m.group(1), sub or m.group(2)
        if not std or not para:
            return None
        return Locator(standard=std, paragraph=para, subitem=sub)
    if isinstance(raw, str):
        m = _CIT.search(raw)
        if not m:
            return None
        return Locator(
            standard=m.group("standard"),
            paragraph=m.group("paragraph"),
            subitem=(m.group("subitem") or None),
        )
    return None


def parse_answer_payload(raw: Any) -> Tuple[Optional[dict], List[Finding]]:
    """원시 응답 → dict. 빈 출력/malformed/truncated JSON은 전부 사유를 남긴다."""
    findings: List[Finding] = []
    if raw is None:
        return None, [Finding(Reason.EMPTY_OUTPUT, "응답이 None")]
    if isinstance(raw, dict):
        return raw, findings
    if not isinstance(raw, str):
        return None, [Finding(Reason.SCHEMA_INVALID, f"지원하지 않는 타입: {type(raw).__name__}")]

    text = raw.strip()
    if not text:
        return None, [Finding(Reason.EMPTY_OUTPUT, "응답이 빈 문자열")]

    # 코드펜스 제거만 허용. 그 이상의 '복구'는 하지 않는다 —
    # 잘린 JSON을 정규식으로 억지 복구하면 fail-open 경로가 생긴다.
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        return None, [Finding(Reason.SCHEMA_INVALID, f"JSON 파싱 실패: {exc}")]
    if not isinstance(obj, dict):
        return None, [Finding(Reason.SCHEMA_INVALID, "최상위가 object가 아님")]
    return obj, findings


def check_schema(
    payload: Optional[dict],
    limits: Limits = DEFAULT_LIMITS,
) -> Tuple[List[Claim], List[Finding]]:
    """①스키마 검사. 반환: (claims, findings)."""
    findings: List[Finding] = []
    if payload is None:
        return [], [Finding(Reason.SCHEMA_INVALID, "payload 없음")]

    answer = payload.get("answer")
    if answer is not None and not isinstance(answer, str):
        findings.append(Finding(Reason.SCHEMA_INVALID, "answer가 문자열이 아님"))
        answer = ""
    answer = answer or ""

    raw_claims = payload.get("claims", None)
    if raw_claims is None:
        findings.append(Finding(Reason.SCHEMA_INVALID, "claims 키 없음"))
        raw_claims = []
    if not isinstance(raw_claims, list):
        findings.append(Finding(Reason.SCHEMA_INVALID, "claims가 배열이 아님"))
        raw_claims = []

    if not answer.strip() and not raw_claims:
        findings.append(Finding(Reason.EMPTY_OUTPUT, "answer와 claims 모두 비어 있음"))
        return [], findings

    if len(answer) > limits.max_answer_chars:
        findings.append(
            Finding(Reason.LIMIT_EXCEEDED, f"answer {len(answer)}자 > {limits.max_answer_chars}")
        )

    # 본문 주장은 있는데 claims=[] → 근거 없는 단정 (강제 INDETERMINATE)
    if answer.strip() and not raw_claims:
        findings.append(
            Finding(Reason.CLAIMS_MISSING, "answer 본문은 있으나 claims가 비어 있음")
        )
        return [], findings

    if len(raw_claims) > limits.max_claims:
        findings.append(
            Finding(Reason.LIMIT_EXCEEDED, f"claims {len(raw_claims)}건 > {limits.max_claims}")
        )

    claims: List[Claim] = []
    seen: set = set()
    for idx, item in enumerate(raw_claims):
        if not isinstance(item, dict):
            findings.append(Finding(Reason.SCHEMA_INVALID, f"claims[{idx}]가 object가 아님"))
            continue
        cid = str(item.get("id") or item.get("claim_id") or f"c{idx + 1}")
        if cid in seen:
            findings.append(Finding(Reason.CLAIM_ID_DUPLICATE, f"중복 claim id: {cid}", cid))
            continue
        seen.add(cid)

        text = item.get("text") or item.get("statement") or ""
        if not isinstance(text, str) or not text.strip():
            findings.append(Finding(Reason.SCHEMA_INVALID, f"claims[{idx}] text 누락", cid))
            text = str(text or "")

        raw_cits = item.get("citations")
        if raw_cits is None:
            raw_cits = [item.get("citation")] if item.get("citation") is not None else []
        if not isinstance(raw_cits, list):
            raw_cits = [raw_cits]

        locators: List[Locator] = []
        for c in raw_cits:
            loc = parse_citation(c)
            if loc is None:
                findings.append(
                    Finding(Reason.CITATION_MISSING, f"인용 파싱 실패: {c!r}", cid)
                )
            else:
                locators.append(loc)
        if not locators:
            findings.append(Finding(Reason.CITATION_MISSING, "claim에 유효한 인용 없음", cid))
        if len(locators) > limits.max_locators_per_claim:
            findings.append(
                Finding(
                    Reason.LIMIT_EXCEEDED,
                    f"인용 {len(locators)}건 > 한도 {limits.max_locators_per_claim}",
                    cid,
                )
            )

        quote = item.get("quote") or ""
        if not isinstance(quote, str):
            findings.append(Finding(Reason.SCHEMA_INVALID, "quote가 문자열이 아님", cid))
            quote = ""
        if len(quote) > limits.max_quote_chars:
            findings.append(
                Finding(Reason.LIMIT_EXCEEDED, f"quote {len(quote)}자 초과", cid)
            )

        claims.append(
            Claim(
                claim_id=cid,
                text=text,
                locator=locators[0] if locators else None,
                quote=quote,
                extra_locators=locators[1:],
            )
        )

    return claims, findings


def check_citations(
    claims: List[Claim],
    bundle: EvidenceBundle,
    require_quote: bool = True,
) -> List[Finding]:
    """②인용 주소 검사.

    - source_id(기준서:문단) 실존: 문단번호만 맞고 기준서가 틀린 경우도 잡힌다.
    - 하위항 실존: 근거 원문에 "(3)" 같은 표기가 실제로 있는지.
    - quote 실존: 정규화 후 substring으로 근거 원문에 있는지.
    """
    findings: List[Finding] = []
    index = bundle.by_source_id
    for claim in claims:
        locs = claim.all_locators
        if not locs:
            continue  # CITATION_MISSING은 스키마 단계에서 이미 기록
        matched: List[Locator] = []
        for loc in locs:
            rec = index.get(loc.source_id)
            if rec is None:
                findings.append(
                    Finding(
                        Reason.SOURCE_ID_NOT_FOUND,
                        f"근거에 없는 주소: {loc.standard} 문단 {loc.paragraph}"
                        f" (source_id={loc.source_id})",
                        claim.claim_id,
                    )
                )
                continue
            if not rec.has_subitem(loc.subitem):
                findings.append(
                    Finding(
                        Reason.SUBITEM_NOT_FOUND,
                        f"하위항 ({loc.subitem}) 이 {loc.source_id} 원문에 없음",
                        claim.claim_id,
                    )
                )
                continue
            matched.append(loc)

        if not require_quote:
            continue
        quote = normalize_text(claim.quote)
        if not quote:
            findings.append(
                Finding(Reason.QUOTE_NOT_IN_SOURCE, "quote 누락", claim.claim_id)
            )
            continue
        if not any(index[loc.source_id].contains_quote(quote) for loc in matched):
            findings.append(
                Finding(
                    Reason.QUOTE_NOT_IN_SOURCE,
                    f"quote가 인용 근거 원문에 없음: {quote[:60]!r}",
                    claim.claim_id,
                )
            )
    return findings


def run_deterministic(
    raw_answer: Any,
    bundle: EvidenceBundle,
    limits: Limits = DEFAULT_LIMITS,
    require_quote: bool = True,
) -> Tuple[List[Claim], List[Finding]]:
    """결정론 레이어 전체 실행. (claims, findings) 반환."""
    payload, findings = parse_answer_payload(raw_answer)
    if payload is None:
        return [], findings
    claims, schema_findings = check_schema(payload, limits=limits)
    findings = findings + schema_findings
    findings += check_citations(claims, bundle, require_quote=require_quote)
    return claims, findings
