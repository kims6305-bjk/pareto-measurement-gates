"""reflection_gate — fail-closed 4단계 인용 검증 게이트 (Phase 0 골격).

레이어
  1. 스키마 검사      (deterministic.check_schema)
  2. 인용 주소/원문 검사 (deterministic.check_citations)
  3. 의미 검사        (semantic — 주입형 판정기, Phase 0에서는 인터페이스만)
  4. 정책 판정        (policy.decide — 강제 INDETERMINATE 우선)
"""
from .deterministic import (
    check_citations,
    check_schema,
    parse_answer_payload,
    parse_citation,
    run_deterministic,
)
from .gate import evaluate
from .models import (
    Authority,
    Claim,
    EvidenceBundle,
    EvidenceRecord,
    GateVerdict,
    Locator,
    Sensitivity,
    bundle_from_records,
    extract_standard_number,
    parse_evidence_paragraphs,
    sha256_of,
)
from .policy import (
    DEFAULT_LIMITS,
    FLAGGING,
    FORCED_INDETERMINATE,
    Finding,
    GateResult,
    Limits,
    Reason,
    decide,
    fail_closed,
)
from .semantic import (
    SemanticJudge,
    SemanticJudgement,
    SemanticLabel,
    build_claim_prompt,
    judge_claims,
    sanitize_evidence_text,
)

__version__ = "0.1.0"

__all__ = [
    "Authority",
    "Claim",
    "DEFAULT_LIMITS",
    "EvidenceBundle",
    "EvidenceRecord",
    "FLAGGING",
    "FORCED_INDETERMINATE",
    "Finding",
    "GateResult",
    "GateVerdict",
    "Limits",
    "Locator",
    "Reason",
    "SemanticJudge",
    "SemanticJudgement",
    "SemanticLabel",
    "Sensitivity",
    "build_claim_prompt",
    "bundle_from_records",
    "check_citations",
    "check_schema",
    "decide",
    "evaluate",
    "extract_standard_number",
    "fail_closed",
    "judge_claims",
    "parse_answer_payload",
    "parse_citation",
    "parse_evidence_paragraphs",
    "run_deterministic",
    "sanitize_evidence_text",
    "sha256_of",
]
