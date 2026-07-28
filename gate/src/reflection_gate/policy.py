"""INDETERMINATE 강제 정책 — fail-closed.

핵심 규칙: "판정 불가"는 절대 통과가 아니다.
아래 사유가 하나라도 걸리면 최종 판정은 INDETERMINATE로 고정되며,
어떤 예외(exception)도 조용히 삼켜서 정상 통과(fail-open)시키지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional

from .models import GateVerdict


class Reason(str, Enum):
    """검증 실패/불가 사유 코드."""

    # --- 강제 INDETERMINATE 목록 ---
    VERIFIER_TIMEOUT = "verifier_timeout"            # 검증기 타임아웃
    EMPTY_OUTPUT = "empty_output"                    # 빈 출력
    SCHEMA_INVALID = "schema_invalid"                # JSON 스키마 실패 / malformed / truncated
    CLAIMS_MISSING = "claims_missing"                # 답변 본문은 있는데 claims=[]
    CLAIM_ID_DUPLICATE = "claim_id_duplicate"        # 중복 claim ID
    CITATION_MISSING = "citation_missing"            # claim에 인용 자체가 없음
    SOURCE_ID_NOT_FOUND = "source_id_not_found"      # 존재하지 않는 source ID (기준서/문단 불일치)
    SUBITEM_NOT_FOUND = "subitem_not_found"          # 존재하지 않는 하위항
    QUOTE_NOT_IN_SOURCE = "quote_not_in_source"      # quote가 근거 원문에 없음
    LIMIT_EXCEEDED = "limit_exceeded"                # claim/인용 수 한도 초과
    SEMANTIC_UNRESOLVED = "semantic_unresolved"      # 의미 판정 불가 / 판정기 오류
    INTERNAL_ERROR = "internal_error"                # 게이트 내부 예외 (fail-closed)

    # --- FLAGGED 사유 ---
    SEMANTIC_CONTRADICTED = "semantic_contradicted"  # 근거가 주장을 반박
    SEMANTIC_INSUFFICIENT = "semantic_insufficient"  # 근거가 주장을 지지하기에 불충분


#: 걸리면 무조건 INDETERMINATE로 강등되는 사유 (fail-closed 목록).
FORCED_INDETERMINATE: frozenset = frozenset(
    {
        Reason.VERIFIER_TIMEOUT,
        Reason.EMPTY_OUTPUT,
        Reason.SCHEMA_INVALID,
        Reason.CLAIMS_MISSING,
        Reason.CLAIM_ID_DUPLICATE,
        Reason.CITATION_MISSING,
        Reason.SOURCE_ID_NOT_FOUND,
        Reason.SUBITEM_NOT_FOUND,
        Reason.QUOTE_NOT_IN_SOURCE,
        Reason.LIMIT_EXCEEDED,
        Reason.SEMANTIC_UNRESOLVED,
        Reason.INTERNAL_ERROR,
    }
)

#: FLAGGED로 이어지는 사유.
FLAGGING: frozenset = frozenset(
    {Reason.SEMANTIC_CONTRADICTED, Reason.SEMANTIC_INSUFFICIENT}
)


@dataclass(frozen=True)
class Limits:
    """한도. 초과 시 LIMIT_EXCEEDED (→ INDETERMINATE)."""

    max_claims: int = 32
    max_locators_per_claim: int = 3
    max_quote_chars: int = 2000
    max_answer_chars: int = 20000


DEFAULT_LIMITS = Limits()


@dataclass(frozen=True)
class Finding:
    """검증 중 발견된 사유 1건."""

    reason: Reason
    detail: str = ""
    claim_id: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - 표시용
        head = f"[{self.reason.value}]"
        if self.claim_id:
            head += f" claim={self.claim_id}"
        return f"{head} {self.detail}".strip()


@dataclass
class GateResult:
    """게이트 최종 산출물."""

    verdict: GateVerdict
    findings: List[Finding] = field(default_factory=list)
    claim_labels: dict = field(default_factory=dict)  # claim_id -> SemanticLabel.value

    @property
    def reasons(self) -> List[Reason]:
        return [f.reason for f in self.findings]

    def has(self, reason: Reason) -> bool:
        return reason in self.reasons

    @property
    def passed(self) -> bool:
        return self.verdict is GateVerdict.VERIFIED


def decide(findings: List[Finding]) -> GateVerdict:
    """사유 목록 → 판정. 강제 INDETERMINATE가 FLAGGED보다 우선한다."""
    reasons = {f.reason for f in findings}
    if reasons & FORCED_INDETERMINATE:
        return GateVerdict.INDETERMINATE
    if reasons & FLAGGING:
        return GateVerdict.FLAGGED
    return GateVerdict.VERIFIED


def fail_closed(fn: Callable[..., Any]) -> Callable[..., Any]:
    """어떤 예외도 통과로 흘리지 않는 래퍼.

    감싼 함수가 예외를 던지면 GateResult(INDETERMINATE, INTERNAL_ERROR)를 돌려준다.
    타임아웃 계열 예외는 VERIFIER_TIMEOUT으로 분류한다.
    """

    def wrapper(*args: Any, **kwargs: Any) -> GateResult:
        try:
            return fn(*args, **kwargs)
        except TimeoutError as exc:  # noqa: PERF203
            return GateResult(
                verdict=GateVerdict.INDETERMINATE,
                findings=[Finding(Reason.VERIFIER_TIMEOUT, f"{type(exc).__name__}: {exc}")],
            )
        except BaseException as exc:  # noqa: BLE001 - fail-closed가 목적
            return GateResult(
                verdict=GateVerdict.INDETERMINATE,
                findings=[Finding(Reason.INTERNAL_ERROR, f"{type(exc).__name__}: {exc}")],
            )

    wrapper.__name__ = getattr(fn, "__name__", "fail_closed_wrapper")
    wrapper.__doc__ = fn.__doc__
    return wrapper
