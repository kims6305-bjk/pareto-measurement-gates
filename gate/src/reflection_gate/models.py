"""게이트 공용 데이터 모델.

설계 원칙
- 근거(Evidence)는 주소(locator)와 원문(excerpt)을 함께 들고 다닌다.
  주소만으로 채점하면 "문단번호는 맞는데 기준서가 틀린" 변조를 못 잡는다.
- 판정은 3상태(VERIFIED / FLAGGED / INDETERMINATE)다. 2상태로 만들면
  "판정 불가"가 조용히 통과(fail-open)로 흘러간다.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple


class GateVerdict(str, Enum):
    """게이트 최종 판정 3상태."""

    VERIFIED = "VERIFIED"            # 결정론 + 의미 레이어 모두 통과
    FLAGGED = "FLAGGED"              # 근거와 충돌하거나 근거가 주장을 지지하지 않음
    INDETERMINATE = "INDETERMINATE"  # 검증 자체가 불가능 — 절대 통과로 강등 금지


class Authority(str, Enum):
    """근거의 권위 등급. 충돌 시 상위 권위가 우선한다."""

    STANDARD = "standard"          # 기준서 본문
    INTERPRETATION = "interpretation"  # 해석서
    GUIDANCE = "guidance"          # 적용지침/결론도출근거
    SECONDARY = "secondary"        # 해설서·블로그 등 2차 자료
    UNKNOWN = "unknown"


class Sensitivity(str, Enum):
    """근거 원문의 취급 등급 (로그/프롬프트 노출 통제용)."""

    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


_WS = re.compile(r"\s+")

#: 기준서를 특정할 수 없는 근거의 표식.
UNKNOWN_STANDARD = "UNKNOWN"


def normalize_text(text: str) -> str:
    """공백 정규화. quote substring 대조는 반드시 이 함수를 거친다."""
    return _WS.sub(" ", (text or "")).strip()


def sha256_of(text: str) -> str:
    """근거 원문 지문. utf-8 고정(Windows 기본 인코딩 의존 제거)."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Locator:
    """인용 주소. (기준서번호, 문단, 하위항) 튜플 전체가 검증 대상이다."""

    standard: str
    paragraph: str
    subitem: Optional[str] = None

    def as_tuple(self) -> Tuple[str, str, Optional[str]]:
        return (self.standard, self.paragraph, self.subitem)

    @property
    def source_id(self) -> str:
        """근거 문서 식별자. 하위항은 문서가 아니라 문서 내 위치이므로 제외."""
        return f"{self.standard}:{self.paragraph}"

    def __str__(self) -> str:  # pragma: no cover - 표시용
        base = f"{self.standard} 문단 {self.paragraph}"
        return f"{base}({self.subitem})" if self.subitem else base


@dataclass(frozen=True)
class EvidenceRecord:
    """검증 대상 근거 1건."""

    source_id: str
    locator: Locator
    excerpt: str
    content_sha256: str = ""
    authority: Authority = Authority.STANDARD
    sensitivity: Sensitivity = Sensitivity.PUBLIC

    def __post_init__(self) -> None:
        if not self.content_sha256:
            object.__setattr__(self, "content_sha256", sha256_of(self.excerpt))

    @property
    def normalized_excerpt(self) -> str:
        return normalize_text(self.excerpt)

    @property
    def standard_known(self) -> bool:
        """기준서를 특정할 수 있는 근거인가."""
        return self.locator.standard != UNKNOWN_STANDARD

    def contains_quote(self, quote: str) -> bool:
        """quote가 근거 원문에 substring으로 실존하는가."""
        q = normalize_text(quote)
        return bool(q) and q in self.normalized_excerpt

    def has_subitem(self, subitem: Optional[str]) -> bool:
        """하위항 (1)/가/① 등이 근거 원문에 실제로 존재하는가."""
        if not subitem:
            return True
        s = normalize_text(subitem)
        body = self.normalized_excerpt
        candidates = {s, f"({s})", f"{s})"}
        # "(1)" 형태로 이미 감싸져 들어온 경우도 허용
        stripped = s.strip("()")
        candidates |= {f"({stripped})", f"{stripped})"}
        return any(c in body for c in candidates)


@dataclass
class Claim:
    """답변에서 추출된 검증 단위 주장 1건."""

    claim_id: str
    text: str
    locator: Optional[Locator] = None
    quote: str = ""
    extra_locators: List[Locator] = field(default_factory=list)

    @property
    def all_locators(self) -> List[Locator]:
        out: List[Locator] = []
        if self.locator is not None:
            out.append(self.locator)
        out.extend(self.extra_locators)
        return out


@dataclass
class EvidenceBundle:
    """한 문항에 제공된 근거 전체."""

    records: List[EvidenceRecord] = field(default_factory=list)

    @property
    def by_source_id(self) -> Dict[str, EvidenceRecord]:
        return {r.source_id: r for r in self.records}

    def get(self, source_id: str) -> Optional[EvidenceRecord]:
        return self.by_source_id.get(source_id)

    def find(self, locator: Locator) -> Optional[EvidenceRecord]:
        return self.get(locator.source_id)

    @property
    def concatenated(self) -> str:
        return "\n\n".join(r.excerpt for r in self.records)


# ab/ab_questions_FROZEN.json 의 evidence_paragraphs 헤더는 두 형태가 섞여 있다:
#   "[1002 재고자산 문단 34] 본문..."   (기준서번호 포함)
#   "[문단 9] 본문..."                  (기준서번호 생략 — 문항의 standard 필드에서 보충)
_HEADER = re.compile(r"\[\s*(?P<std>\d{3,4})?\s*[^\]]*?문단\s*(?P<para>[0-9]+[A-Za-z]?)\s*\]")

#: 문항 메타의 "1115 고객과의 계약에서 생기는 수익" 같은 문자열에서 기준서번호만 뽑는다.
_STD_NUM = re.compile(r"\d{3,4}")


def extract_standard_number(text: Optional[str]) -> Optional[str]:
    m = _STD_NUM.search(text or "")
    return m.group(0) if m else None


def parse_evidence_paragraphs(
    raw: str,
    authority: Authority = Authority.STANDARD,
    sensitivity: Sensitivity = Sensitivity.PUBLIC,
    default_standard: Optional[str] = None,
) -> EvidenceBundle:
    """FROZEN 데이터셋의 evidence_paragraphs 문자열을 EvidenceRecord 목록으로 파싱.

    default_standard: 헤더에 기준서번호가 없을 때 사용할 기준서
      (문항의 standard 필드. "1115 고객과의 계약..." 형태여도 번호만 추출한다).
    """
    fallback = extract_standard_number(default_standard)
    records: List[EvidenceRecord] = []
    matches = list(_HEADER.finditer(raw or ""))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[start:end].strip()
        std = m.group("std") or fallback
        if std is None:
            # 기준서를 특정할 수 없는 근거는 버리지 않고 UNKNOWN 주소로 남긴다 —
            # 조용히 삭제하면 "근거 없음"이 통과로 둔갑할 수 있다.
            std = UNKNOWN_STANDARD
        loc = Locator(standard=std, paragraph=m.group("para"))
        records.append(
            EvidenceRecord(
                source_id=loc.source_id,
                locator=loc,
                excerpt=body,
                content_sha256=sha256_of(body),
                authority=authority,
                sensitivity=sensitivity,
            )
        )
    return EvidenceBundle(records=records)


def bundle_from_records(records: Sequence[EvidenceRecord]) -> EvidenceBundle:
    return EvidenceBundle(records=list(records))
