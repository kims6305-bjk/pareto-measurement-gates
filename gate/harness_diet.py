#!/usr/bin/env python3
"""하네스 순편익 파레토 판정기.

레이어 OFF(baseline)와 ON(candidate)을 같은 고정 평가셋에서 재고,
품질(higher is better)과 운영비(lower is better)의 지배관계를 판정한다.
사용자가 upstream에서 확정·반올림한 점추정치를 exact 비교하며,
통계적 유의성·허용오차 판단은 이 도구의 범위가 아니다.

판정:
  KEEP         ON이 OFF를 지배 — 켜는 편이 파레토 최적
  REMOVE       OFF가 ON을 지배 — 끄는 편이 파레토 최적
  TEST_THIN    둘 다 비지배 — 실패군에만 켠 조건부 후보를 새로 측정
  EQUAL        두 점이 동일 — 더 단순한 OFF 권고(YAGNI)
  NOT_MEASURED 대상 도달 0 — 효과 없음 단정 금지

실제 파일/설정 삭제는 하지 않는다. 사용자가 결과를 보고 제거한다.

사용:
  python3 gate/harness_diet.py --off quality=0.95,cost=10 --on quality=0.95,cost=14
  python3 gate/harness_diet.py --json measurement.json
  python3 gate/harness_diet.py --demo

JSON:
  {"off":{"quality":0.95,"cost":10}, "on":{"quality":0.96,"cost":12},
   "reach":17, "quality_name":"accuracy", "cost_name":"review_minutes"}
"""
from __future__ import annotations
import argparse, json, math, pathlib, sys
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Point:
    quality: float  # 높을수록 좋음
    cost: float     # 낮을수록 좋음

    def __post_init__(self) -> None:
        object.__setattr__(self, "quality", _finite_nonnegative("quality", self.quality))
        object.__setattr__(self, "cost", _finite_nonnegative("cost", self.cost))


@dataclass
class Verdict:
    verdict: str
    reason: str
    recommendation: str
    quality_delta: float
    cost_delta: float
    off_dominates_on: bool
    on_dominates_off: bool
    pareto_front: list[str]
    reach: int | None = None

    def to_dict(self):
        return asdict(self)


def _finite_nonnegative(name: str, value) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number, not bool")
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number")
    if not math.isfinite(x) or x < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return x


def point(obj: object, label: str) -> Point:
    if not isinstance(obj, dict):
        raise ValueError(f"{label} must be an object")
    keys = set(obj)
    if keys != {"quality", "cost"}:
        raise ValueError(f"{label} requires exactly quality,cost")
    return Point(_finite_nonnegative(f"{label}.quality", obj["quality"]),
                 _finite_nonnegative(f"{label}.cost", obj["cost"]))


def dominates(a: Point, b: Point) -> bool:
    """a가 b보다 품질은 이상, 비용은 이하이며 하나는 엄격히 우월."""
    no_worse = a.quality >= b.quality and a.cost <= b.cost
    strict = a.quality > b.quality or a.cost < b.cost
    return no_worse and strict


def judge(off: Point, on: Point, reach: int | None = None) -> Verdict:
    if reach is not None:
        if isinstance(reach, bool) or not isinstance(reach, int) or reach < 0:
            raise ValueError("reach must be an integer >= 0 (bool is not accepted)")
        if reach == 0:
            return Verdict(
                "NOT_MEASURED", "대상 도달 0 — 겨냥 실패와 순효과 0을 구분할 수 없음",
                "대상에서 seed를 뽑고 도달 분모가 1 이상인 같은 A/B를 다시 실행",
                on.quality - off.quality, on.cost - off.cost, False, False,
                ["OFF", "ON"], reach)

    od = dominates(off, on)
    nd = dominates(on, off)
    dq, dc = on.quality - off.quality, on.cost - off.cost
    if nd:
        return Verdict("KEEP", "ON이 OFF를 지배(품질 이상·비용 이하, 최소 한 축 엄격 개선)",
                       "ON 유지", dq, dc, od, nd, ["ON"], reach)
    if od:
        return Verdict("REMOVE", "OFF가 ON을 지배(ON은 순편익 없는 열등 이동)",
                       "사용자 승인 후 하네스 제거/비활성화", dq, dc, od, nd, ["OFF"], reach)
    if dq == 0 and dc == 0:
        return Verdict("EQUAL", "OFF와 ON이 측정상 동일", "더 단순한 OFF 권고(YAGNI)",
                       dq, dc, od, nd, ["OFF", "ON"], reach)
    return Verdict(
        "TEST_THIN", "OFF와 ON이 모두 파레토 전선 — 목적함수 없이는 우열 확정 불가",
        "실패군에만 ON인 THIN 후보를 같은 품질·비용 축으로 측정한 뒤 3점 재판정",
        dq, dc, od, nd, ["OFF", "ON"], reach)


def parse_pair(text: str) -> Point:
    vals = {}
    for item in text.split(","):
        if "=" not in item:
            raise ValueError("point format: quality=N,cost=N")
        k, v = item.split("=", 1)
        k = k.strip()
        if k in vals:
            raise ValueError(f"duplicate point key: {k}")
        vals[k] = v.strip()
    return point(vals, "point")


def safe_label(value, fallback: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 80:
        raise ValueError(f"{fallback}_name must be a non-empty string <= 80 chars")
    if not value.isprintable():
        raise ValueError(f"{fallback}_name contains control or formatting characters")
    return value


def render(v: Verdict, qname="quality", cname="cost") -> str:
    sign = lambda x: f"{x:+.6g}"
    return "\n".join([
        f"판정: {v.verdict}",
        f"Δ{qname}: {sign(v.quality_delta)} (높을수록 좋음)",
        f"Δ{cname}: {sign(v.cost_delta)} (낮을수록 좋음)",
        f"파레토 전선: {', '.join(v.pareto_front)}",
        f"근거: {v.reason}",
        f"권고: {v.recommendation}",
    ])


def demo():
    assert judge(Point(.9, 10), Point(.91, 9)).verdict == "KEEP"
    assert judge(Point(.9, 10), Point(.9, 11)).verdict == "REMOVE"
    assert judge(Point(.9, 10), Point(.91, 12)).verdict == "TEST_THIN"
    assert judge(Point(.9, 10), Point(.9, 10)).verdict == "EQUAL"
    assert judge(Point(.9, 10), Point(.95, 8), reach=0).verdict == "NOT_MEASURED"
    try:
        point({"quality": -1, "cost": 2}, "off")
        raise AssertionError("negative quality accepted")
    except ValueError:
        pass
    print("harness_diet demo OK — 6 cases")


def strict_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--off", help="quality=N,cost=N")
    ap.add_argument("--on", help="quality=N,cost=N")
    ap.add_argument("--json", type=pathlib.Path)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--json-output", action="store_true")
    ns = ap.parse_args(argv)
    if ns.demo:
        demo(); return 0
    if ns.json and (ns.off or ns.on):
        ap.error("--json cannot be combined with --off/--on")
    if bool(ns.off) != bool(ns.on):
        ap.error("--off and --on must be provided together")
    if ns.json:
        d = json.loads(ns.json.read_text(encoding="utf-8"), object_pairs_hook=strict_object)
        if not isinstance(d, dict):
            raise ValueError("JSON top level must be an object")
        allowed = {"off", "on", "reach", "quality_name", "cost_name"}
        extra = set(d) - allowed
        if extra:
            raise ValueError(f"unknown JSON keys: {sorted(extra)}")
        off, on = point(d.get("off"), "off"), point(d.get("on"), "on")
        reach = d.get("reach")
        qname = safe_label(d.get("quality_name", "quality"), "quality")
        cname = safe_label(d.get("cost_name", "cost"), "cost")
    elif ns.off and ns.on:
        off, on, reach = parse_pair(ns.off), parse_pair(ns.on), None
        qname, cname = "quality", "cost"
    else:
        ap.error("provide --json or both --off and --on")
    v = judge(off, on, reach)
    print(json.dumps(v.to_dict(), ensure_ascii=False, indent=2) if ns.json_output
          else render(v, qname, cname))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)
