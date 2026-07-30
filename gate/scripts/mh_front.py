"""dominance 판정 + front 갱신 — 순수 계산. LLM 호출 0콜.

정본: `gate/PARETO_META_HARNESS_DESIGN.md`
  §4.1  강한 지배 정의 (2축, 둘 다 최대화)
  §4.2  동률 3경우 — 완전동률 병존 / 한축동률+한축우세는 지배 / 트레이드오프 병존. **스칼라화 금지**
  §4.3  N2 — **CI 가 겹치면 그 축은 동률.** 판정용 CI = ci_qid (F3)
  §4.4  R1~R5 위반 → UNJUDGED (지배도 피지배도 하지 않는다)
  §5.1  파일 2개 스키마 — mh_archive.jsonl(append-only 원장) / mh_front.json(파생 캐시)
  §5.2  진입 3단계 (INVALID → 측정 → 표본요건) + G1 열등이동 차단
  §5.3  제거는 status 전이만. **물리 삭제 금지**
  §5.4  front 상한 8 + 3단 사전식 솎아내기 (crowding distance 는 기각 — 이유는 아래 주석)
  §6.4  종료 조건 T1~T4
  §7.2  INV-4(임계 변경 금지) · INV-5(결과 열람 전 커밋)

usage:
    python mh_front.py front      [--ci qid|claim|none] [--dry-run]
    python mh_front.py add        --objectives mh_c007_objectives.json --harness h.json \
                                  --parents c003 c005 --generation 3 --origin front_pair \
                                  --origin-reason "..."
    python mh_front.py dominance  --a c003 --b c005 [--ci qid|claim|none]
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Sequence

GATE = Path(__file__).resolve().parents[1]
ARCHIVE = GATE / "scripts/mh_archive.jsonl"
FRONT_JSON = GATE / "scripts/mh_front.json"

AXES = ("recall", "precision")            # §3.3 확정. 3개를 넘기지 않는다 (§3.6)
BASELINE_ID = "c000"                      # §5.2 G1 기준
FRONT_CAP = 8                             # §5.4 상한 (F10, INV-4)
STALL_LIMIT = 3                           # §6.4 T1
CALL_BUDGET = 1650                        # §6.4 T2
MODEL_FIXED = "claude-sonnet-4-6"         # §13.1 F6, INV-3 (alias 금지)
CI_KEYS = {"qid": "ci_qid", "claim": "ci_claim", "none": None}
DEFAULT_CI = "qid"                        # F3 — 판정은 보수적인 qid 클러스터 CI
EPS = 1e-9                                # 점 추정 비교용 (스칼라화 아님)

STATUS_ON_FRONT, STATUS_DOMINATED = "ON_FRONT", "DOMINATED"
STATUS_PRUNED, STATUS_UNJUDGED, STATUS_INVALID = "PRUNED", "UNJUDGED", "INVALID"
TERMINAL = {STATUS_PRUNED, STATUS_INVALID}   # §5.3 되돌릴 수 없는 전이

KST = timezone(timedelta(hours=9))


# ══════════════════════════════════════════════════════════════════════════════
# §4 dominance
# ══════════════════════════════════════════════════════════════════════════════
def _pt(rec: dict, axis: str) -> Optional[float]:
    return rec.get("objectives", {}).get(axis, {}).get("value")


def _ci(rec: dict, axis: str, ci_key: str) -> Optional[Sequence[float]]:
    return rec.get("objectives", {}).get(axis, {}).get(ci_key)


def cmp_axis(x: dict, y: dict, axis: str, ci_key: Optional[str]) -> int:
    """축 비교. 반환 +1(x 우세) / 0(동률) / -1(y 우세).

    §4.3 N2: 95% CI 가 겹치면 그 축은 **동률로 간주**한다. 겹침 판정은
    "한쪽 하한이 다른쪽 상한보다 크다" 즉 구간 비겹침이며, 이는 우리 레포가 이미 쓰는
    기준(PHASE1/PHASE3/P4 의 Wilson 비겹침)을 dominance 연산자 안으로 옮긴 것이다.

    ci_key=None 이면 점 추정만 비교한다 (§12.2 ablation A-CI, `--ci none`).
    """
    vx, vy = _pt(x, axis), _pt(y, axis)
    if ci_key is None:
        if vx is None or vy is None:
            return 0
        if vx > vy + EPS:
            return 1
        if vy > vx + EPS:
            return -1
        return 0

    cx, cy = _ci(x, axis, ci_key), _ci(y, axis, ci_key)
    if not cx or not cy:
        return 0                       # CI 미정의 → 동률로 둔다 (fail-closed)
    if cx[0] > cy[1] + EPS:
        return 1
    if cy[0] > cx[1] + EPS:
        return -1
    return 0                           # 겹침 → 동률


def dominates(x: dict, y: dict, ci_key: Optional[str]) -> bool:
    """§4.1 강한 지배: 모든 축에서 열세가 없고 최소 한 축이 우세."""
    c = [cmp_axis(x, y, a, ci_key) for a in AXES]
    return all(v >= 0 for v in c) and any(v > 0 for v in c)


def relation(x: dict, y: dict, ci_key: Optional[str]) -> str:
    """설명용 라벨. §4.2 의 3경우를 문자열로 돌려준다."""
    c = [cmp_axis(x, y, a, ci_key) for a in AXES]
    if all(v == 0 for v in c):
        return "동률(병존)"
    if all(v >= 0 for v in c):
        return "x 지배"
    if all(v <= 0 for v in c):
        return "y 지배"
    return "트레이드오프(비지배)"


# ══════════════════════════════════════════════════════════════════════════════
# 아카이브 입출력 (§5.1 / §5.3 — append-only, 물리 삭제 금지)
# ══════════════════════════════════════════════════════════════════════════════
def load_archive(path: Path = ARCHIVE) -> tuple[list[dict], dict[str, dict]]:
    """반환: (원시 레코드 순서대로, 후보별 최신 스냅샷)

    원장은 append-only 이므로 같은 candidate_id 가 여러 줄 있을 수 있다
    (status 전이마다 새 줄). **뒤에 온 줄이 최신 상태**이며 앞 줄은 지우지 않는다.
    """
    raw: list[dict] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                raw.append(json.loads(line))
    latest: dict[str, dict] = {}
    for rec in raw:                      # 파일 순서 = 시간 순서
        latest[rec["candidate_id"]] = rec
    return raw, latest


def append_archive(rec: dict, path: Path = ARCHIVE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""


def _transition(rec: dict, status: str, by: str, at: str) -> dict:
    """status 전이 = 새 스냅샷 1줄 append. 기존 줄은 건드리지 않는다 (§5.3 제거 A)."""
    new = copy.deepcopy(rec)
    new["status"] = status
    hist = list(new.get("status_history") or [])
    hist.append({"at": at, "status": status, "by": by})
    new["status_history"] = hist
    return new


# ══════════════════════════════════════════════════════════════════════════════
# front 계산
# ══════════════════════════════════════════════════════════════════════════════
def judgeable(rec: dict) -> bool:
    """front 판정 대상인가. §4.4/§5.2 — UNJUDGED·INVALID·PRUNED 는 제외.

    UNJUDGED 는 "지배도 피지배도 하지 않는다"(§5.2 3단계)이므로 비교에서 완전히 빼고,
    PRUNED 는 되돌릴 수 없으므로(§5.3) 영구 제외한다.
    """
    if rec.get("status") in (STATUS_INVALID, STATUS_PRUNED, STATUS_UNJUDGED):
        return False
    if not rec.get("sample_gate", {}).get("passed"):
        return False
    return all(_pt(rec, a) is not None for a in AXES)


def _sort_ids(ids) -> list[str]:
    return sorted(ids)                    # 딕셔너리 순회 비의존 (결정론)


def compute_front(latest: dict[str, dict], ci_key: Optional[str]) -> dict:
    """비지배 집합과 지배관계를 계산한다. 상태를 쓰지 않는 순수 함수."""
    pool = {i: r for i, r in latest.items() if judgeable(r)}
    dominated: dict[str, list[str]] = {}
    for i in _sort_ids(pool):
        by = [j for j in _sort_ids(pool)
              if j != i and dominates(pool[j], pool[i], ci_key)]
        if by:
            dominated[i] = by
    front = [i for i in _sort_ids(pool) if i not in dominated]

    # G1 (§5.2): baseline 에게 지배당한 후보는 부모 후보에서 영구 제외
    g1 = []
    base = pool.get(BASELINE_ID)
    if base is not None:
        g1 = [i for i in _sort_ids(pool)
              if i != BASELINE_ID and dominates(base, pool[i], ci_key)]
    return {"pool": pool, "front": front, "dominated": dominated, "g1_excluded": g1}


def endpoints(front: Sequence[str], pool: dict[str, dict],
              ci_key: Optional[str]) -> dict[str, Optional[str]]:
    """§5.4 1) 끝점 = 축별 최대. 최대가 여럿이면 반대 축이 큰 쪽,
    그래도 같으면 generation 이른 쪽 → id 오름차순 (결정론)."""
    out: dict[str, Optional[str]] = {}
    for k, axis in enumerate(AXES):
        other = AXES[1 - k]
        best = sorted(front, key=lambda i: (-(_pt(pool[i], axis) or 0.0),
                                            -(_pt(pool[i], other) or 0.0),
                                            pool[i].get("generation", 0), i))
        out[axis] = best[0] if best else None
    return out


def _late_first(ids: Sequence[str], pool: dict[str, dict]) -> list[str]:
    """늦게 온 쪽 먼저 = (generation 내림차순, id 내림차순). 결정론적 안정 정렬.

    §4.2-1·§5.4-3 이 정한 방향("늦게 온 동률은 새 정보가 없다")을 한 곳에 모은다.
    """
    xs = sorted(ids, reverse=True)                       # id 내림차순
    return sorted(xs, key=lambda i: -pool[i].get("generation", 0))   # stable sort


def prune_front(front: list[str], pool: dict[str, dict], ci_key: Optional[str],
                cap: int = FRONT_CAP) -> tuple[list[str], list[dict], Optional[str]]:
    """§5.4 3단 사전식 솎아내기.

    🔴 crowding distance 는 쓰지 않는다 — 설계가 기각했다:
       (1) recall 최소 눈금이 1/11 = 9.1%p 로 굵어서 "밀집" 개념이 성립하지 않는다,
       (2) CI 동률 규칙 N2 가 이미 근접성을 벌하므로 거리 기반 솎아내기는 이중 계산이다.

    반환: (남은 front, PRUNED 기록, 예외로 인한 정지 신호)
    """
    if len(front) <= cap:
        return list(front), [], None

    # §5.4 예외: front 절반 이상이 origin=filter_strip 이면 PRUNED 하지 않고 정지
    fs = [i for i in front if pool[i].get("origin") == "filter_strip"]
    if len(fs) * 2 >= len(front):
        return list(front), [], "T4_filter_strip_majority"

    keep = list(front)
    pruned: list[dict] = []
    ep = {v for v in endpoints(front, pool, ci_key).values() if v}

    def n_flagged(i: str) -> int:
        return pool[i].get("measurement", {}).get("n_flagged", 0)

    # 2단계: 두 축 CI 가 모두 다른 front 후보와 겹치는(= 구별되지 않는) 후보부터
    def indistinct(i: str) -> bool:
        for j in keep:
            if j == i:
                continue
            if all(cmp_axis(pool[i], pool[j], a, ci_key) == 0 for a in AXES):
                return True
        return False

    cands = sorted(_late_first([i for i in keep if i not in ep and indistinct(i)], pool),
                   key=n_flagged)                        # n_flagged 오름차순, 동률은 늦게 온 쪽
    for i in cands:
        if len(keep) <= cap:
            break
        keep.remove(i)
        pruned.append({"id": i, "rule": "§5.4-2 전 축 CI 겹침(구별 불가) + n_flagged 최소"})

    # 3단계: 그래도 초과하면 generation 이 큰(늦게 온) 쪽
    rest = _late_first([i for i in keep if i not in ep], pool)
    for i in rest:
        if len(keep) <= cap:
            break
        keep.remove(i)
        pruned.append({"id": i, "rule": "§5.4-3 generation 최대(늦게 온 동률)"})

    return _sort_ids(keep), pruned, None


# ══════════════════════════════════════════════════════════════════════════════
# §6.4 종료 조건 T1~T4
# ══════════════════════════════════════════════════════════════════════════════
def termination(front: list[str], pool: dict[str, dict], latest: dict[str, dict],
                ci_key: Optional[str], stall_rounds: int,
                prune_halt: Optional[str]) -> dict:
    hits: list[str] = []
    if stall_rounds >= STALL_LIMIT:
        hits.append("T1")

    total_calls = sum(r.get("reference_fields", {}).get("search_cost_calls") or 0
                      for r in latest.values())
    if total_calls > CALL_BUDGET:
        hits.append("T2")

    gens = [r.get("generation", 0) for r in latest.values()]
    cur = max(gens) if gens else 0
    if cur > 0:
        valid_now = [i for i, r in latest.items()
                     if r.get("generation", 0) == cur and judgeable(r)]
        if not valid_now:
            hits.append("T3")

    # T4: front 절반 이상이 다른 front 후보와 **전 축 CI 겹침 동률**
    tied = []
    for i in front:
        for j in front:
            if i != j and all(cmp_axis(pool[i], pool[j], a, ci_key) == 0 for a in AXES):
                tied.append(i)
                break
    if front and len(tied) * 2 >= len(front):
        hits.append("T4")
    if prune_halt and "T4" not in hits:
        hits.append("T4")

    return {"triggered": hits, "stop": bool(hits), "cumulative_calls": total_calls,
            "current_generation": cur, "all_axes_tied": _sort_ids(set(tied)),
            "prune_halt": prune_halt}


# ══════════════════════════════════════════════════════════════════════════════
# 서브커맨드 — front
# ══════════════════════════════════════════════════════════════════════════════
def cmd_front(a: argparse.Namespace) -> int:
    archive = Path(a.archive)
    out = Path(a.out)
    raw, latest = load_archive(archive)
    if not latest:
        print(f"아카이브가 비었다: {archive}", file=sys.stderr)
        return 2

    ci_key = CI_KEYS[a.ci]
    res = compute_front(latest, ci_key)
    pool, front0 = res["pool"], res["front"]
    keep, pruned, halt = prune_front(front0, pool, ci_key, cap=a.cap)

    prev = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    prev_front = prev.get("front") or []
    changed = _sort_ids(keep) != _sort_ids(prev_front)
    stall = 0 if changed else int(prev.get("stall_rounds") or 0) + 1

    term = termination(keep, pool, latest, ci_key, stall, halt)
    at = a.computed_at or datetime.now(KST).isoformat(timespec="seconds")

    doc = {
        "computed_at": at,
        "archive_sha256": sha256_file(archive),
        "axes": list(AXES),
        "ci_used": a.ci if ci_key is None else ci_key,
        "front": keep,
        "endpoints": endpoints(keep, pool, ci_key),
        "dominated": [{"id": i, "dominated_by": res["dominated"][i]}
                      for i in _sort_ids(res["dominated"])],
        "pruned": ([{"id": p["id"], "rule": p["rule"], "at": at} for p in pruned]
                   + [{"id": i, "rule": (latest[i].get("status_history") or [{}])[-1]
                       .get("by", "이전 라운드"), "at": "이전"}
                      for i in _sort_ids(latest)
                      if latest[i].get("status") == STATUS_PRUNED]),
        "unjudged": [{"id": i, "violations": latest[i].get("sample_gate", {})
                      .get("violations", [])}
                     for i in _sort_ids(latest)
                     if latest[i].get("status") == STATUS_UNJUDGED
                     or (latest[i].get("status") != STATUS_INVALID
                         and not latest[i].get("sample_gate", {}).get("passed"))],
        "front_size": len(keep),
        "front_changed": changed,
        "stall_rounds": stall,
        # ── §5.1 예시 스키마에 없는 추가 필드 (판정 근거를 파일에 남기려고 신설) ──
        "g1_excluded": res["g1_excluded"],
        "invalid": [i for i in _sort_ids(latest)
                    if latest[i].get("status") == STATUS_INVALID],
        "termination": term,
    }

    if a.dry_run:
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        return 0

    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    # status 전이 append (§5.3 제거 A — 행을 지우지 않는다)
    if not a.no_status_write:
        target = {i: STATUS_ON_FRONT for i in keep}
        target.update({i: STATUS_DOMINATED for i in res["dominated"]})
        target.update({p["id"]: STATUS_PRUNED for p in pruned})
        for i in _sort_ids(target):
            rec = latest[i]
            if rec.get("status") in TERMINAL:
                continue                       # PRUNED·INVALID 는 되돌리지 않는다
            if rec.get("status") == target[i]:
                continue
            by = f"mh_front.py {a.ci} — " + (
                "front 진입" if target[i] == STATUS_ON_FRONT else
                "지배당함: " + ",".join(res["dominated"].get(i, []))
                if target[i] == STATUS_DOMINATED else "크기상한 솎아내기")
            if i in res["g1_excluded"]:
                by += " | G1: baseline 에게 지배당해 부모 후보 영구 제외"
            append_archive(_transition(rec, target[i], by, at), archive)

    print(f"front({a.ci}) {len(keep)}/{len(pool)}: {keep}")
    print(f"  endpoints: {doc['endpoints']}")
    if pruned:
        print(f"  PRUNED: {[p['id'] for p in pruned]}")
    if res["g1_excluded"]:
        print(f"  G1 제외: {res['g1_excluded']}")
    print(f"  front_changed={changed} stall_rounds={stall} "
          f"누적콜={term['cumulative_calls']}")
    if term["stop"]:
        print(f"  🔴 종료 조건 충족: {term['triggered']} — 탐색을 정지한다")
    print(f"saved: {out}")
    return 0


# ══════════════════════════════════════════════════════════════════════════════
# 서브커맨드 — add (§5.2 진입 3단계)
# ══════════════════════════════════════════════════════════════════════════════
def validity_check(harness: dict, latest: dict[str, dict],
                   verify_builder: bool = True) -> list[str]:
    """§5.2 1단계 — INVALID 차단. 실패 사유 목록을 돌려준다.

    build() 가 **문자열을 반환하는지**는 unit 이 필요하므로 여기서 확인하지 않는다 —
    그 검사는 러너(`mh_run_candidate.py`)의 책임이다. 여기서는 import 가능성과
    호출 가능성까지만 본다.
    """
    bad: list[str] = []
    if harness.get("model") != MODEL_FIXED:
        bad.append(f"INV-3 모델 고정 위반: {harness.get('model')!r} != {MODEL_FIXED!r}")
    sha = harness.get("prompt_sha256")
    if not sha:
        bad.append("prompt_sha256 없음")
    else:
        dup = [i for i, r in sorted(latest.items())
               if r.get("harness", {}).get("prompt_sha256") == sha]
        if dup:
            bad.append(f"prompt_sha256 중복 — 기존 후보 {dup} 재측정 금지")
    if verify_builder:
        mod, fn = harness.get("builder_module"), harness.get("builder_fn")
        try:
            m = importlib.import_module(str(mod))
        except Exception as exc:                                    # noqa: BLE001
            bad.append(f"빌더 import 실패: {mod} ({type(exc).__name__})")
        else:
            if not callable(getattr(m, str(fn), None)):
                bad.append(f"빌더 함수 호출 불가: {mod}.{fn}")
    return bad


def cmd_add(a: argparse.Namespace) -> int:
    archive = Path(a.archive)
    obj = json.loads(Path(a.objectives).read_text(encoding="utf-8"))
    harness = json.loads(Path(a.harness).read_text(encoding="utf-8"))
    _, latest = load_archive(archive)

    cid = a.candidate_id or obj["candidate_id"]
    if cid in latest:
        print(f"이미 존재하는 candidate_id: {cid} (원장은 덮어쓰지 않는다)",
              file=sys.stderr)
        return 2

    at = a.computed_at or datetime.now(KST).isoformat(timespec="seconds")
    if not a.origin_reason:
        print("origin_reason 은 비워둘 수 없다 (§5.1)", file=sys.stderr)
        return 2

    rec = {
        "candidate_id": cid,
        "created_at": at,
        "parent_ids": list(a.parents or []),
        "generation": a.generation,
        "origin": a.origin,
        "origin_reason": a.origin_reason,
        "harness": harness,
        "measurement": obj["measurement"],
        "objectives": obj["objectives"],
        "reference_fields": obj["reference_fields"],
        "sample_gate": obj["sample_gate"],
        "status": None,
        "status_history": [],
        "bootstrap": obj.get("bootstrap"),
    }

    # 1단계 유효성
    bad = validity_check(harness, latest, verify_builder=not a.no_verify_builder)
    if bad:
        rec["status"] = STATUS_INVALID
        rec["status_history"] = [{"at": at, "status": STATUS_INVALID,
                                  "by": "; ".join(bad)}]
        append_archive(rec, archive)
        print(f"{cid} INVALID — {bad}")
        return 3

    # 3단계 표본 요건 (2단계 측정은 러너 담당)
    if not obj["sample_gate"]["passed"]:
        rec["status"] = STATUS_UNJUDGED
        rec["status_history"] = [{"at": at, "status": STATUS_UNJUDGED,
                                  "by": f"§4.4 위반 {obj['sample_gate']['violations']}"}]
        append_archive(rec, archive)
        print(f"{cid} UNJUDGED — 표본 요건 위반 {obj['sample_gate']['violations']}")
        return 3

    # G1 (§5.2): baseline 에게 지배당하면 DOMINATED + 부모 후보 영구 제외
    ci_key = CI_KEYS[a.ci]
    base = latest.get(BASELINE_ID)
    if base is not None and cid != BASELINE_ID and dominates(base, rec, ci_key):
        rec["status"] = STATUS_DOMINATED
        rec["status_history"] = [{"at": at, "status": STATUS_DOMINATED,
                                  "by": "G1: baseline c000 에게 지배당함 — "
                                        "부모 후보에서 영구 제외 (§5.2)"}]
        append_archive(rec, archive)
        print(f"{cid} DOMINATED (G1) — baseline 이 지배. 아카이브에는 남는다")
        return 0

    rec["status"] = STATUS_ON_FRONT          # 잠정 — `front` 서브커맨드가 확정한다
    rec["status_history"] = [{"at": at, "status": rec["status"], "by": f"{cid} 진입"}]
    append_archive(rec, archive)
    print(f"{cid} 등록 — 잠정 {rec['status']}. `front` 서브커맨드로 확정하라")
    return 0


# ══════════════════════════════════════════════════════════════════════════════
# 서브커맨드 — dominance
# ══════════════════════════════════════════════════════════════════════════════
def _load_one(ref: str, latest: dict[str, dict]) -> dict:
    if ref in latest:
        return latest[ref]
    p = Path(ref)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    print(f"후보를 찾을 수 없다: {ref}", file=sys.stderr)
    raise SystemExit(2)


def cmd_dominance(a: argparse.Namespace) -> int:
    _, latest = load_archive(Path(a.archive))
    x, y = _load_one(a.a, latest), _load_one(a.b, latest)
    ci_key = CI_KEYS[a.ci]
    print(f"A={x['candidate_id']}  B={y['candidate_id']}  (ci={a.ci})")
    for axis in AXES:
        c = cmp_axis(x, y, axis, ci_key)
        print(f"  {axis:9s} A={_pt(x, axis)} {_ci(x, axis, ci_key or 'ci_qid')} | "
              f"B={_pt(y, axis)} {_ci(y, axis, ci_key or 'ci_qid')} → cmp={c:+d}")
    print(f"  A≻B={dominates(x, y, ci_key)}  B≻A={dominates(y, x, ci_key)}  "
          f"관계={relation(x, y, ci_key)}")
    return 0


# ══════════════════════════════════════════════════════════════════════════════
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--archive", default=str(ARCHIVE))
        p.add_argument("--ci", choices=sorted(CI_KEYS), default=DEFAULT_CI,
                       help="판정용 CI. qid=기본(F3) / claim / none=점추정만(A-CI)")
        p.add_argument("--computed-at", default=None,
                       help="타임스탬프 고정(재현 검증용)")

    p = sub.add_parser("front", help="front 재계산 + mh_front.json 갱신")
    common(p)
    p.add_argument("--out", default=str(FRONT_JSON))
    p.add_argument("--cap", type=int, default=FRONT_CAP)
    p.add_argument("--dry-run", action="store_true", help="파일 쓰지 않고 출력만")
    p.add_argument("--no-status-write", action="store_true",
                   help="status 전이 append 를 생략(조회 전용)")
    p.set_defaults(fn=cmd_front)

    p = sub.add_parser("add", help="후보 1개 등록 (§5.2 진입 3단계)")
    common(p)
    p.add_argument("--objectives", required=True, help="mh_objectives.py 출력 JSON")
    p.add_argument("--harness", required=True, help="harness 블록 JSON (§5.1)")
    p.add_argument("--candidate-id", default=None)
    p.add_argument("--parents", nargs="*", default=[])
    p.add_argument("--generation", type=int, default=0)
    p.add_argument("--origin", default="baseline",
                   choices=["baseline", "front_endpoint", "front_pair", "filter_strip"])
    p.add_argument("--origin-reason", default="")
    p.add_argument("--no-verify-builder", action="store_true",
                   help="빌더 import 검사 생략(오프라인 검증용)")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("dominance", help="두 후보 dominance 판정")
    common(p)
    p.add_argument("--a", required=True, help="후보 id 또는 objectives JSON 경로")
    p.add_argument("--b", required=True)
    p.set_defaults(fn=cmd_dominance)
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    a = build_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
