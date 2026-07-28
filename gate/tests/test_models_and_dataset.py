"""FROZEN 데이터셋 스키마 적합성 + 유틸 회귀 테스트."""
from __future__ import annotations

import json

import pytest
from conftest import FROZEN_PATH

from reflection_gate import (
    GateVerdict,
    Locator,
    parse_citation,
    parse_evidence_paragraphs,
    sha256_of,
)
from reflection_gate.policy import FORCED_INDETERMINATE, Finding, Reason, decide


def test_locator_tuple_and_source_id():
    loc = Locator("1002", "34", "2")
    assert loc.as_tuple() == ("1002", "34", "2")
    assert loc.source_id == "1002:34"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1002 문단 34", ("1002", "34", None)),
        ("[1002 재고자산 문단 34]", ("1002", "34", None)),
        ("1116 문단 9(1)", ("1116", "9", "1")),
        ("1038 문단 21-(2)", ("1038", "21", "2")),
        ("1109 문단 5A", ("1109", "5A", None)),
        ({"standard": "1002", "paragraph": "34(3)"}, ("1002", "34", "3")),
        ("근거 없음", None),
        (None, None),
    ],
)
def test_parse_citation(raw, expected):
    loc = parse_citation(raw)
    assert (loc.as_tuple() if loc else None) == expected


def test_sha256_is_utf8_stable():
    assert sha256_of("재고자산") == sha256_of("재고자산")
    assert len(sha256_of("x")) == 64


def test_decide_priority():
    findings = [
        Finding(Reason.SEMANTIC_CONTRADICTED, ""),
        Finding(Reason.SCHEMA_INVALID, ""),
    ]
    assert decide(findings) is GateVerdict.INDETERMINATE
    assert decide([Finding(Reason.SEMANTIC_CONTRADICTED, "")]) is GateVerdict.FLAGGED
    assert decide([]) is GateVerdict.VERIFIED


def test_forced_indeterminate_covers_policy_list():
    required = {
        Reason.VERIFIER_TIMEOUT,
        Reason.EMPTY_OUTPUT,
        Reason.SCHEMA_INVALID,
        Reason.CLAIMS_MISSING,
        Reason.CLAIM_ID_DUPLICATE,
        Reason.SOURCE_ID_NOT_FOUND,
        Reason.QUOTE_NOT_IN_SOURCE,
        Reason.LIMIT_EXCEEDED,
    }
    assert required <= FORCED_INDETERMINATE


@pytest.mark.skipif(not FROZEN_PATH.exists(), reason="FROZEN 데이터셋 없음")
def test_frozen_dataset_parses_with_utf8():
    """실제 119문항 evidence_paragraphs가 EvidenceRecord로 파싱되는지."""
    with open(FROZEN_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    questions = data["questions"]
    assert len(questions) == 119
    empty = []
    for q in questions:
        b = parse_evidence_paragraphs(
            q["evidence_paragraphs"], default_standard=q.get("standard")
        )
        if not b.records:
            empty.append(q["qid"])
        for r in b.records:
            assert r.standard_known, f"{q['qid']}: 기준서 미상 근거 {r.source_id}"
            assert r.content_sha256 == sha256_of(r.excerpt)
    assert empty == [], f"근거 파싱 실패 문항: {empty}"


@pytest.mark.skipif(not FROZEN_PATH.exists(), reason="FROZEN 데이터셋 없음")
def test_frozen_gold_citations_resolve():
    """gold_citations의 (기준서, 문단) + quote가 근거 원문에 실존해야 한다."""
    with open(FROZEN_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    bad = []
    for q in data["questions"]:
        b = parse_evidence_paragraphs(
            q["evidence_paragraphs"], default_standard=q.get("standard")
        )
        for g in q.get("gold_citations") or []:
            loc = parse_citation(g)
            if loc is None:
                bad.append((q["qid"], "locator 파싱 실패", g))
                continue
            rec = b.get(loc.source_id)
            if rec is None:
                bad.append((q["qid"], "source_id 미존재", loc.source_id))
                continue
            if g.get("quote") and not rec.contains_quote(g["quote"]):
                bad.append((q["qid"], "quote 미존재", g["quote"][:40]))
    assert bad == [], f"gold 인용 검증 실패 {len(bad)}건: {bad[:5]}"
