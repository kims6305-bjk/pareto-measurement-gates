#!/usr/bin/env python3
"""하네스 순편익 파레토 판정기.

레이어 OFF(baseline)와 ON(candidate)을 같은 고정 평가셋에서 재고,
품질(higher is better)과 운영비(lower is better)의 지배관계를 판정한다.
사용자가 upstream에서 확정·반올림한 점추정치를 exact 비교한다.
구간(`quality_ci`/`cost_ci`, upstream이 계산한 [lo,hi])을 양쪽에 주면 건전한 구간
지배를 쓴다: 모든 축에서 한쪽 최악값이 상대 최선값 이상일 때만 지배, 한 축이라도
걸쳐 겹치면 UNRESOLVED(미결). 겹침을 동률로 치지 않는다(동률로 치면 지배가 비추이적).
mh_front 도 부속서4(2026-11-23)부터 같은 쌍별 규칙을 쓴다.
구간 계산은 이 도구 밖이다. 구간 없이 exact 비교하면 119건 중 1건 차이로도 판정이 바뀐다.
양쪽에 `cohort`(평가셋 해시 등)를 주면 다를 때 INCOMPARABLE로 판정을 거부한다.
비용 10/14는 데모값이지 실측치가 아니다.

판정:
  KEEP         ON이 OFF를 지배 — 켜는 편이 파레토 최적
  REMOVE       OFF가 ON을 지배 — 끄는 편이 파레토 최적
  TEST_THIN    둘 다 비지배(상충 확정) — 실패군에만 켠 조건부 후보를 새로 측정
  EQUAL        두 점추정이 동일 — 더 단순한 OFF 권고(YAGNI)
  UNRESOLVED   구간이 겹쳐 지배도 상충도 확정 불가 — 재측정, 그 전엔 OFF 유지
  NOT_MEASURED 대상 도달 0 — 효과 없음 단정 금지
  INCOMPARABLE 평가셋(cohort)이 달라 같은 실험으로 비교할 수 없음

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
    quality_ci: tuple | None = None
    cost_ci: tuple | None = None
    cohort: str | None = None

    def __post_init__(self) -> None:
        for axis in ("quality", "cost"):
            x = _finite_nonnegative(axis, getattr(self, axis))
            object.__setattr__(self, axis, x)
            ci = getattr(self, axis + "_ci")
            if ci is not None:
                if not isinstance(ci, (list, tuple)) or len(ci) != 2:
                    raise ValueError(f"{axis}_ci must be [lo, hi]")
                lo, hi = (_finite_nonnegative(f"{axis}_ci", v) for v in ci)
                if not lo <= x <= hi:
                    raise ValueError(f"{axis}_ci must contain the point: {lo} <= {x} <= {hi}")
                object.__setattr__(self, axis + "_ci", (lo, hi))
        if self.cohort is not None:
            object.__setattr__(self, "cohort", safe_label(self.cohort, "cohort"))


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
    optional = {"quality_ci", "cost_ci", "cohort"}
    if not {"quality", "cost"} <= keys or keys - {"quality", "cost"} - optional:
        raise ValueError(f"{label} requires quality,cost (optional: quality_ci,cost_ci,cohort)")
    return Point(_finite_nonnegative(f"{label}.quality", obj["quality"]),
                 _finite_nonnegative(f"{label}.cost", obj["cost"]),
                 obj.get("quality_ci"), obj.get("cost_ci"), obj.get("cohort"))


def _intervals(a: Point, b: Point) -> list[tuple[tuple, tuple]]:
    """축별 (a구간, b구간)을 '높을수록 좋음' 방향으로 정규화. 구간 없으면 [x,x]."""
    out = []
    for axis, sign in (("quality", 1), ("cost", -1)):
        ca, cb = getattr(a, axis + "_ci"), getattr(b, axis + "_ci")
        if (ca is None) != (cb is None):
            raise ValueError(f"{axis}_ci must be given for both OFF and ON or neither")
        ia = ca or (getattr(a, axis),) * 2
        ib = cb or (getattr(b, axis),) * 2
        if sign < 0:
            ia, ib = (-ia[1], -ia[0]), (-ib[1], -ib[0])
        out.append((ia, ib))
    return out


def dominates(a: Point, b: Point) -> bool:
    """건전한(sound) 구간 지배: 모든 축에서 a의 최악값이 b의 최선값 이상이고,
    한 축은 엄격히 초과. 이때 구간 안 어떤 참값 조합에서도 a가 b를 지배한다.
    구간이 없으면 [x,x]라 기존 점 비교와 같다. (clpi separatedN의 클린룸 재구성)"""
    iv = _intervals(a, b)
    return all(ia[0] >= ib[1] for ia, ib in iv) and any(ia[0] > ib[1] for ia, ib in iv)


def _undecided(a: Point, b: Point) -> bool:
    """어느 쪽도 상대 이상이라 말할 수 없는 축(구간이 걸쳐 겹침)이 있는가."""
    return any(ia[0] < ib[1] and ib[0] < ia[1] for ia, ib in _intervals(a, b))


def judge(off: Point, on: Point, reach: int | None = None) -> Verdict:
    dq, dc = on.quality - off.quality, on.cost - off.cost
    if (off.cohort is None) != (on.cohort is None):
        raise ValueError("cohort must be given for both OFF and ON or neither")
    if off.cohort != on.cohort:
        return Verdict("INCOMPARABLE", f"평가셋 불일치: OFF={off.cohort} ON={on.cohort}",
                       "같은 평가셋에서 OFF/ON을 다시 측정", dq, dc, False, False, [], reach)
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
    if nd:
        return Verdict("KEEP", "ON이 OFF를 지배(품질 이상·비용 이하, 최소 한 축 엄격 개선)",
                       "ON 유지", dq, dc, od, nd, ["ON"], reach)
    if od:
        return Verdict("REMOVE", "OFF가 ON을 지배(ON은 순편익 없는 열등 이동)",
                       "사용자 승인 후 하네스 제거/비활성화", dq, dc, od, nd, ["OFF"], reach)
    if dq == 0 and dc == 0:
        return Verdict("EQUAL", "OFF와 ON의 점추정이 동일", "더 단순한 OFF 권고(YAGNI)",
                       dq, dc, od, nd, ["OFF", "ON"], reach)
    if _undecided(on, off):
        return Verdict(
            "UNRESOLVED", "구간이 겹치는 축이 있어 지배·상충 어느 쪽도 확정 불가(미결)",
            "표본을 늘려 재측정. 그 전까지 더 단순한 OFF 유지(지배 근거로 쓰지 말 것)",
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
    # 품질은 구간 분리로 ON 우세, 비용은 겹침 → 겹침=동률이면 KEEP이지만 건전 규칙은 미결
    assert judge(Point(.80, 10, (.78, .82), (9, 11)),
                 Point(.90, 10.5, (.88, .92), (9.5, 11.5))).verdict == "UNRESOLVED"
    assert judge(Point(.80, 9.5, (.78, .82), (9, 9.9)),
                 Point(.90, 9, (.88, .92), (8, 9))).verdict == "KEEP"   # 접촉(9.9 vs 9)은 분리
    try:
        point({"quality": -1, "cost": 2}, "off")
        raise AssertionError("negative quality accepted")
    except ValueError:
        pass
    print("harness_diet demo OK - 8 cases")


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
    ap.add_argument("--reach", type=int, help="대상 도달 건수 (0이면 NOT_MEASURED)")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--json-output", action="store_true")
    ns = ap.parse_args(argv)
    if ns.demo:
        demo(); return 0
    if ns.json and (ns.off or ns.on or ns.reach is not None):
        ap.error("--json cannot be combined with --off/--on/--reach")
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
        off, on, reach = parse_pair(ns.off), parse_pair(ns.on), ns.reach
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
