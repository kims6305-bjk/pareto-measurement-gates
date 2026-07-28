"""게이트 오케스트레이터 — 결정론 레이어 → 의미 레이어 순으로 실행.

순서가 규율이다. 구조 검사에서 걸린 답변은 의미 레이어로 내려보내지 않는다
(LLM에게 변조된 인용을 해석할 기회를 주지 않기 위해서).
"""
from __future__ import annotations

from typing import Any, Optional

from .deterministic import run_deterministic
from .models import EvidenceBundle, GateVerdict
from .policy import (
    DEFAULT_LIMITS,
    Finding,
    GateResult,
    Limits,
    Reason,
    decide,
    fail_closed,
)
from .semantic import JudgeFn, SemanticLabel, judge_claims

_LABEL_TO_REASON = {
    SemanticLabel.CONTRADICTED: Reason.SEMANTIC_CONTRADICTED,
    SemanticLabel.INSUFFICIENT: Reason.SEMANTIC_INSUFFICIENT,
    SemanticLabel.UNRESOLVED: Reason.SEMANTIC_UNRESOLVED,
}


@fail_closed
def evaluate(
    raw_answer: Any,
    bundle: EvidenceBundle,
    judge: Optional[JudgeFn] = None,
    question: Optional[str] = None,
    limits: Limits = DEFAULT_LIMITS,
    require_quote: bool = True,
    require_semantic: bool = True,
) -> GateResult:
    """답변 1건을 검증해 GateResult를 돌려준다.

    require_semantic=False이면 결정론 레이어만으로 판정한다
    (판정기를 못 붙인 환경에서 구조 검사만 돌릴 때 사용).
    """
    claims, findings = run_deterministic(
        raw_answer, bundle, limits=limits, require_quote=require_quote
    )

    # 구조 검사 실패 → 의미 레이어로 내려보내지 않는다.
    if decide(findings) is not GateVerdict.VERIFIED:
        return GateResult(verdict=decide(findings), findings=findings)

    if not require_semantic:
        return GateResult(verdict=decide(findings), findings=findings)

    labels = {}
    for j in judge_claims(claims, bundle, judge, question=question):
        labels[j.claim_id] = j.label.value
        reason = _LABEL_TO_REASON.get(j.label)
        if reason is not None:
            findings.append(Finding(reason, j.rationale, j.claim_id))

    return GateResult(verdict=decide(findings), findings=findings, claim_labels=labels)
