#!/usr/bin/env python3
"""도달 분모 체크 — 겨냥형(targeted) 측정에서 "겨냥 실패"와 "순효과 0"을 가른다.

정본 사례: gate/MEASUREMENT_FAILURES.md 사례 6.

겨냥형 측정이란 "특정 부분집합(예: 근거 없는 문서)에 개입이 먹히는지"를 재는 것이다.
이때 지표가 0 → 0으로 나오면 두 가지 서로 다른 사실이 같은 숫자로 나타난다.

    (a) 순효과 0   — 질의가 대상에 닿았는데 순위가 안 바뀜  → 진짜 "효과 없음"
    (b) 겨냥 실패  — 질의가 대상에 애초에 닿지 않음        → 측정 자체가 무효

둘을 가르는 유일한 값이 **도달 건수(reach)** 다: 대상 집합의 원소를 **개입 전 후보**에 하나라도
포함한 질의의 수. reach == 0이면 어떤 지표 변화도 해석해선 안 된다.

이 모듈은 검색 스택에 의존하지 않는다 — 질의별 후보 ID 리스트와 대상 ID 집합만 받는다.

사용:
    from reach_check import reach_report
    rep = reach_report(before={qid: [doc_id, ...]}, after={...}, targets={doc_id, ...})
    print(rep.render())

또는 자기검사:
    python3 reach_check.py --demo
"""
from __future__ import annotations
import sys
from dataclasses import dataclass, field


@dataclass
class ReachReport:
    n_queries: int
    reach: int                      # 대상에 닿은 질의 수 (분모)
    exposure_before: int            # 대상 원소가 후보에 노출된 총 건수 (before)
    exposure_after: int
    target_rank_changes: int        # 대상 문서의 위치·순서가 바뀐 질의 수
    unreached: list = field(default_factory=list)

    def __post_init__(self):
        vals = {"n_queries": self.n_queries, "reach": self.reach,
                "exposure_before": self.exposure_before,
                "exposure_after": self.exposure_after,
                "target_rank_changes": self.target_rank_changes}
        for name, value in vals.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be an integer >= 0")
        if self.reach > self.n_queries:
            raise ValueError("reach cannot exceed n_queries")
        if self.target_rank_changes > self.reach:
            raise ValueError("target_rank_changes cannot exceed reach")
        if self.reach == 0 and (self.exposure_before or self.exposure_after):
            raise ValueError("zero baseline reach requires zero measured exposure")
        if self.reach > 0 and self.exposure_before < self.reach:
            raise ValueError("positive reach requires at least one baseline target exposure per reached query")
        if not isinstance(self.unreached, list) or any(not isinstance(q, str) for q in self.unreached):
            raise ValueError("unreached must be a list of string query IDs")
        if len(set(self.unreached)) != len(self.unreached) or len(self.unreached) > self.n_queries - self.reach:
            raise ValueError("unreached contains duplicates or exceeds the unreached count")

    @property
    def valid(self) -> bool:
        """reach가 0이면 지표 변화를 해석할 수 없다."""
        return self.reach > 0

    @property
    def verdict(self) -> str:
        if not self.valid:
            return "TARGETING_FAILURE"       # 겨냥 실패 — 측정 무효
        if self.exposure_before == self.exposure_after and self.target_rank_changes == 0:
            return "NO_EFFECT"               # 도달했는데 안 움직임 = 진짜 순효과 0
        return "MOVED"

    def render(self) -> str:
        lines = [
            f"질의 {self.n_queries}문 · 도달 {self.reach}건(분모)",
            f"대상 노출:  {self.exposure_before} → {self.exposure_after}",
            f"대상 순서변동: {self.target_rank_changes}건",
            f"판정:       {self.verdict}",
        ]
        if not self.valid:
            lines.append(
                "  🔴 도달 0 — 지표 변화를 '효과 없음'으로 읽지 마라. "
                "seed를 대상 집합에서 다시 뽑을 것.")
        elif self.verdict == "MOVED":
            lines.append(
                "  ⚠️ 움직인 값은 안전 프록시의 기계적 효과일 수 있다. "
                "관련성 개선과 분리해 기재할 것.")
        return "\n".join(lines)


def reach_report(before: dict, after: dict, targets: set, top_k: int = 10) -> ReachReport:
    """
    before/after: {query_id: [doc_id, ...]}  개입 전/후의 후보 리스트(순위 순)
    targets:      겨냥 대상 doc_id 집합
    """
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("before and after must be objects")
    if not isinstance(targets, set) or not targets or any(not isinstance(x, str) for x in targets):
        raise ValueError("targets must be a non-empty set of string IDs")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be an integer > 0")
    all_qids = set(before) | set(after)
    if any(not isinstance(q, str) for q in all_qids):
        raise ValueError("query IDs must be strings")
    if set(before) != set(after):
        missing_before = sorted(set(after) - set(before))
        missing_after = sorted(set(before) - set(after))
        raise ValueError(f"paired A/B requires identical query IDs; missing_before={missing_before}, missing_after={missing_after}")
    qids = sorted(before)
    reach = exp_b = exp_a = target_rank_changes = 0
    unreached = []
    for q in qids:
        raw_b, raw_a = before.get(q, []), after.get(q, [])
        if not isinstance(raw_b, list) or not isinstance(raw_a, list):
            raise ValueError(f"candidate lists required for query {q}")
        if any(not isinstance(x, str) for x in raw_b + raw_a):
            raise ValueError(f"candidate IDs must be strings for query {q}")
        if len(set(raw_b)) != len(raw_b) or len(set(raw_a)) != len(raw_a):
            raise ValueError(f"duplicate candidate ID for query {q}")
        b, a = raw_b[:top_k], raw_a[:top_k]
        hb = sum(1 for d in b if d in targets)
        ha = sum(1 for d in a if d in targets)
        # 효과 지표도 baseline 도달 질의에 한정한다.
        if hb:
            reach += 1
            exp_b += hb
            exp_a += ha
            target_sig_b = tuple((i, d) for i, d in enumerate(b) if d in targets)
            target_sig_a = tuple((i, d) for i, d in enumerate(a) if d in targets)
            if target_sig_b != target_sig_a:
                target_rank_changes += 1
        else:
            unreached.append(q)
    return ReachReport(len(qids), reach, exp_b, exp_a, target_rank_changes, unreached)


def demo():
    T = {"t1", "t2"}
    # (a) 겨냥 실패 — 대상이 후보에 아예 없다. 지표는 0→0이지만 해석 불가.
    r = reach_report({"q1": ["x", "y"]}, {"q1": ["x", "y"]}, T)
    assert r.reach == 0 and r.verdict == "TARGETING_FAILURE", r
    assert not r.valid and r.unreached == ["q1"]

    # (b) 순효과 0 — 닿았는데 아무것도 안 움직임. 같은 0→0이지만 의미가 다르다.
    r = reach_report({"q1": ["t1", "x"]}, {"q1": ["t1", "x"]}, T)
    assert r.reach == 1 and r.verdict == "NO_EFFECT", r
    assert r.exposure_before == r.exposure_after == 1

    # (c) 움직임 — 대상 노출이 줄고 순서가 바뀜
    r = reach_report({"q1": ["t1", "t2", "x"]}, {"q1": ["x", "t1", "y"]}, T)
    assert r.verdict == "MOVED" and r.reach == 1
    assert (r.exposure_before, r.exposure_after) == (2, 1), r
    assert r.target_rank_changes == 1

    # (d) 분모는 top_k 안에서만 센다 — 11위의 대상은 도달이 아니다
    base = [f"x{i}" for i in range(10)] + ["t1"]
    r = reach_report({"q1": base}, {"q1": base}, T, top_k=10)
    assert r.reach == 0, r

    # (e) 비대상 문서만 재정렬되면 대상 효과 MOVED가 아니다
    r = reach_report({"q1": ["t1", "x", "y"]}, {"q1": ["t1", "y", "x"]}, T)
    assert r.verdict == "NO_EFFECT" and r.target_rank_changes == 0, r

    # (f) 중복 후보는 노출을 부풀리므로 거부한다
    try:
        reach_report({"q1": ["t1", "t1"]}, {"q1": ["t1"]}, T)
        raise AssertionError("duplicate candidates accepted")
    except ValueError:
        pass

    print("reach_check demo OK — 6 cases")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
    else:
        print(__doc__)
