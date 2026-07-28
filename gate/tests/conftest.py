"""공용 픽스처. 근거 데이터는 ab/ab_questions_FROZEN.json 실물 스키마를 따른다."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from reflection_gate import (  # noqa: E402
    Authority,
    Claim,
    EvidenceRecord,
    Locator,
    Sensitivity,
    SemanticJudgement,
    SemanticLabel,
    bundle_from_records,
    parse_evidence_paragraphs,
)

REPO = pathlib.Path(__file__).resolve().parents[2]
FROZEN_PATH = REPO / "ab" / "ab_questions_FROZEN.json"

# FROZEN 파일이 없는 환경(공개 체크아웃 등)에서도 테스트가 돌도록 동일 스키마 fallback 유지.
_FALLBACK_EVIDENCE = (
    "[1002 재고자산 문단 33] 매 후속기간에 순실현가능가치를 재평가한다. "
    "재고자산의 감액을 초래했던 상황이 해소되거나 경제상황의 변동으로 순실현가능가치가 "
    "상승한 명백한 증거가 있는 경우에는 최초의 장부금액을 초과하지 않는 범위 내에서 평가손실을 환입한다.\n\n"
    "[1002 재고자산 문단 34] 재고자산의 판매시, 관련된 수익을 인식하는 기간에 재고자산의 "
    "장부금액을 비용으로 인식한다. 순실현가능가치의 상승으로 인한 재고자산 평가손실의 환입은 "
    "환입이 발생한 기간의 비용으로 인식된 재고자산 금액의 차감액으로 인식한다."
)


def _load_q010() -> str:
    if FROZEN_PATH.exists():
        with open(FROZEN_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        for q in data["questions"]:
            if q["qid"] == "Q010":
                return q["evidence_paragraphs"]
    return _FALLBACK_EVIDENCE


@pytest.fixture(scope="session")
def raw_evidence() -> str:
    return _load_q010()


@pytest.fixture()
def bundle(raw_evidence):
    """1002 문단 33 / 34 두 건이 든 근거 묶음."""
    b = parse_evidence_paragraphs(raw_evidence)
    assert len(b.records) == 2, f"근거 파싱 실패: {len(b.records)}건"
    assert set(b.by_source_id) == {"1002:33", "1002:34"}
    return b


@pytest.fixture()
def quote_p34(bundle) -> str:
    """문단 34 원문에 실존하는 인용 문장."""
    return "순실현가능가치의 상승으로 인한 재고자산 평가손실의 환입은"


@pytest.fixture()
def quote_p33(bundle) -> str:
    return "최초의 장부금액을 초과하지 않는 범위 내에서 평가손실을 환입한다."


@pytest.fixture()
def subitem_bundle():
    """하위항 (1)/(2) 가 실재하는 근거 — 존재하지 않는 하위항 테스트용."""
    body = (
        "다음 각 목의 요건을 모두 충족해야 한다. "
        "(1) 자산에서 생기는 미래경제적효익의 유입 가능성이 높다. "
        "(2) 자산의 원가를 신뢰성 있게 측정할 수 있다."
    )
    loc = Locator(standard="1038", paragraph="21")
    return bundle_from_records(
        [
            EvidenceRecord(
                source_id=loc.source_id,
                locator=loc,
                excerpt=body,
                authority=Authority.STANDARD,
                sensitivity=Sensitivity.PUBLIC,
            )
        ]
    )


def make_judge(label: SemanticLabel, rationale: str = "mock"):
    """모든 claim에 동일 라벨을 돌려주는 mock 판정기."""

    def _judge(prompt: str, claim: Claim) -> SemanticJudgement:
        return SemanticJudgement(claim_id=claim.claim_id, label=label, rationale=rationale)

    return _judge


ALL_SUPPORTED = make_judge(SemanticLabel.SUPPORTED)
