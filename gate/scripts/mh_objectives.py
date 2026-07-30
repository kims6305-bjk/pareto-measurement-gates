"""목적 벡터 계산기 — 후보 1개의 3판 jsonl + 사람 라벨 → (recall, precision) + 부트스트랩 CI.

정본: `gate/PARETO_META_HARNESS_DESIGN.md`
  §3.3  축 정의 (recall / precision). **instrument_check_score.py 의 정의를 그대로 쓴다.**
  §4.3  노이즈 처리 — 부트스트랩 CI 2종(claim·qid 클러스터). 판정은 ci_qid.
  §4.4  최소 표본 요건 R1~R5 — 위반 시 판정 거부(UNJUDGED).
  §5.1  출력 필드명 = `mh_archive.jsonl` 스키마의 measurement / objectives /
        reference_fields / sample_gate 블록.
  §8.2  IC-2 — 이 계산기 자체의 검침(`--selftest`).
  §13.1 F1 seed=20260730 · F2 B=2000 · F3 두 CI 계산·판정은 ci_qid · F4 percentile 2.5/97.5

🔴 이 파일은 front 를 계산하지 않는다(그것은 `mh_front.py`). LLM 호출도 하지 않는다.
🔴 INV-5: 결과 열람 전에 커밋한다.
🔴 결정론: 같은 입력·같은 seed → 같은 출력. 타임스탬프를 출력에 넣지 않는다(diff 가 비어야 함).

usage:
    python mh_objectives.py --candidate-id c000 \
        --runs 'scripts/instrument_check_run*.jsonl' \
        --labels scripts/phase1_human_label_sheet.xlsx \
        --out scripts/mh_c000_objectives.json
    python mh_objectives.py --selftest
"""
from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import json
import statistics
import sys
from pathlib import Path
from typing import Iterable, Optional, Sequence

GATE = Path(__file__).resolve().parents[1]

# ── §13.1 고정값 (F1·F2·F4) — 실행마다 바꾸지 않는다 ────────────────────────────
SEED = 20260730          # F1
B = 2000                 # F2
CI_LO_PCT, CI_HI_PCT = 2.5, 97.5   # F4
CI_USED_FOR_JUDGMENT = "ci_qid"    # F3 — 판정은 보수적인(넓은) qid 클러스터 CI

# ── §3.3 축 정의 — instrument_check_score.py L15 와 동일 집합 ──────────────────
PROBLEM = {"CONTRADICTED", "INSUFFICIENT"}
VALID_JUDGE = {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT", "UNRESOLVED"}
HUMAN_PROBLEM = ("C", "I")
SPLIT = "SPLIT"

# ── §4.4 최소 표본 요건 R1~R5 (INV-4: 본 실행 중 변경 금지) ────────────────────
R1_MIN_PROBLEM = 8       # 사람 라벨 문제건 수
R2_MIN_FLAGGED = 5       # 판정기 문제판정 수 (precision 분모)
R3_N_RUNS = 3            # 정확히 3판
R4_MAX_UNRESOLVED = 0.10
R5_MAX_SPLIT = 0.20

# 종료 코드 — 요구사항 5 "미달이면 판정 거부(에러 코드로 구분)"
EXIT_OK = 0
EXIT_INPUT = 2           # 입력 오류(라벨 불일치·파일 없음 등)
EXIT_SAMPLE_GATE = 3     # R1~R5 위반 → 판정 거부(UNJUDGED). JSON 은 그래도 쓴다


# ══════════════════════════════════════════════════════════════════════════════
# 단위(unit) 자료구조
# ══════════════════════════════════════════════════════════════════════════════
class Unit:
    """채점 단위 1건 = claim 1개.

    qid = **문항** 식별자. id 포맷은 `{qid}-{arm}-c{claim_id}`
    (`phase3_build_prompts.py` L118 실측) 이므로 `id.split("-")[0]`.
    §4.3 이 인용한 `phase3_power_check.py` 의 "독립 단위는 주장이 아니라 문항이다" 에서
    문항 = qid 이며, arm 은 같은 문항에 대한 두 답변이므로 같은 클러스터로 묶는다
    (arm 을 쪼개면 클러스터가 33개, 문항으로 묶으면 28개 — **넓은 CI = 보수적**).
    """

    __slots__ = ("id", "qid", "human", "maj")

    def __init__(self, uid: str, human: str, maj: str) -> None:
        self.id = uid
        self.qid = uid.split("-")[0]
        self.human = human
        self.maj = maj

    def __repr__(self) -> str:  # pragma: no cover - 디버깅용
        return f"Unit({self.id}, human={self.human}, maj={self.maj})"

    @property
    def is_problem(self) -> bool:
        return self.human in HUMAN_PROBLEM

    @property
    def is_flagged(self) -> bool:
        return self.maj in PROBLEM


# ══════════════════════════════════════════════════════════════════════════════
# 3판 다수결 (§3.3 / instrument_check_score.py main())
# ══════════════════════════════════════════════════════════════════════════════
def majority(labels: Sequence[str]) -> str:
    """2표 이상 최다 라벨, 아니면 SPLIT.

    instrument_check_score.py 는 `Counter(...).most_common()` 의 첫 항목이 2표 이상일 때만
    채택하고 그 외는 "SPLIT" 으로 둔다. 여기서는 동일 규칙에 **결정론 보강**만 더한다:
    같은 득표수일 때 Counter 는 삽입 순서(=파일 읽는 순서)에 의존하므로 라벨 문자열로
    정렬한다. 3판에서는 2표 이상 최다가 유일하므로 두 구현의 결과는 항상 같다.
    """
    cnt = collections.Counter(labels)
    top = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))
    if top and top[0][1] >= 2:
        return top[0][0]
    return SPLIT


# ══════════════════════════════════════════════════════════════════════════════
# 축 계산 (§3.3) — 정의를 새로 만들지 않는다
# ══════════════════════════════════════════════════════════════════════════════
def counts(units: Iterable[Unit]) -> dict:
    """§3.3 의 카운트. instrument_check_score.py 와 글자 단위로 같은 정의."""
    us = list(units)
    prob = [u for u in us if u.is_problem]
    flagged = [u for u in us if u.is_flagged]
    detected = [u for u in prob if u.is_flagged]
    return {
        "n_units": len(us),
        "n_problem": len(prob),
        "n_flagged": len(flagged),
        "n_detected": len(detected),
        "n_contradicted": sum(1 for u in prob if u.maj == "CONTRADICTED"),
        "n_split": sum(1 for u in us if u.maj == SPLIT),
        "n_unresolved": sum(1 for u in us if u.maj == "UNRESOLVED"),
    }


def recall_of(units: Iterable[Unit]) -> Optional[float]:
    c = counts(units)
    if c["n_problem"] == 0:
        return None          # 분모 0 → 미정의 (§4.4 R1 이 애초에 8건 미만을 거부)
    return c["n_detected"] / c["n_problem"]


def precision_of(units: Iterable[Unit]) -> Optional[float]:
    """🔴 기존 구현과의 유일한 정의 차이 — 분모 0 처리.

    `instrument_check_score.py` 는 `flagged` 가 비면 `0.0` 을 반환한다(보고 전용이므로 무해).
    설계 §4.4 R2 는 그 0.0 을 "정밀도 0%" 로 읽는 것을 **오판**으로 명시했고,
    §8.2 IC-2 (c) 는 `n_flagged = 0` 일 때 **미정의로 반환(0.0 아님)** 하라고 요구한다.
    그래서 여기서는 `None` 을 돌려준다. 분자·분모가 있을 때의 값은 기존과 동일하다.
    """
    c = counts(units)
    if c["n_flagged"] == 0:
        return None
    return c["n_detected"] / c["n_flagged"]


AXES = ("recall", "precision")
_AXIS_FN = {"recall": recall_of, "precision": precision_of}


# ══════════════════════════════════════════════════════════════════════════════
# 부트스트랩 CI (§4.3 N1, F1~F4)
# ══════════════════════════════════════════════════════════════════════════════
def percentile(xs: Sequence[float], q: float) -> float:
    """선형보간 percentile. numpy 없이 결정론적으로 계산한다(새 의존성 금지)."""
    if not xs:
        raise ValueError("empty sequence")
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = (len(s) - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    frac = pos - lo
    return s[lo] * (1.0 - frac) + s[hi] * frac


class _Rng:
    """표준 random 대신 최소 LCG — CPython 버전 간 구현 변화에 영향받지 않게 한다.

    `random.Random.choices`/`randrange` 는 내부 알고리즘이 바뀌면 같은 seed 에서도
    다른 수열이 나올 수 있다. 재현 패키지(§13.3)가 "비트 단위 동일"을 요구하므로
    수열 생성 자체를 이 파일에 고정한다.
    """

    __slots__ = ("state",)
    _A = 6364136223846793005
    _C = 1442695040888963407
    _M = 1 << 64

    def __init__(self, seed: int) -> None:
        self.state = seed % self._M

    def next_below(self, n: int) -> int:
        """[0, n) 정수. 상위 비트를 쓴다(하위 비트 주기 문제 회피)."""
        self.state = (self._A * self.state + self._C) % self._M
        return ((self.state >> 17) * n) >> 47


def _resample_claim(units: Sequence[Unit], rng: _Rng) -> list[Unit]:
    n = len(units)
    return [units[rng.next_below(n)] for _ in range(n)]


def _resample_qid(clusters: Sequence[tuple[str, tuple[Unit, ...]]],
                  rng: _Rng) -> list[Unit]:
    k = len(clusters)
    out: list[Unit] = []
    for _ in range(k):
        out.extend(clusters[rng.next_below(k)][1])
    return out


def bootstrap(units: Sequence[Unit], mode: str, *, b: int = B,
              seed: int = SEED) -> dict:
    """mode='claim' | 'qid'. 반환: {axis: {"ci":[lo,hi]|None, "n_valid":int}}

    §4.3 N1 의 절차 그대로: **하나의 리샘플에서 두 축을 함께** 계산해 축 간 상관을 반영한다.
    분모가 0 이 되는 리샘플은 그 축에서만 제외한다(설계는 이 경우를 규정하지 않았다 —
    보고서에 미규정 항목으로 남긴다). 두 mode 는 각각 같은 seed 에서 독립적으로
    시작하므로 한쪽만 계산해도 결과가 같다.
    """
    us = sorted(units, key=lambda u: u.id)          # 딕셔너리 순회 순서 비의존
    if mode == "claim":
        rng, draw = _Rng(seed), lambda r: _resample_claim(us, r)
    elif mode == "qid":
        grouped: dict[str, list[Unit]] = collections.defaultdict(list)
        for u in us:
            grouped[u.qid].append(u)
        clusters = tuple((q, tuple(grouped[q])) for q in sorted(grouped))
        rng, draw = _Rng(seed), lambda r: _resample_qid(clusters, r)
    else:  # pragma: no cover - 방어
        raise ValueError(f"unknown mode: {mode}")

    samples: dict[str, list[float]] = {a: [] for a in AXES}
    for _ in range(b):
        s = draw(rng)
        for axis in AXES:
            v = _AXIS_FN[axis](s)
            if v is not None:
                samples[axis].append(v)

    out = {}
    for axis in AXES:
        xs = samples[axis]
        out[axis] = {
            "ci": None if not xs else [round(percentile(xs, CI_LO_PCT), 4),
                                       round(percentile(xs, CI_HI_PCT), 4)],
            "n_valid": len(xs),
        }
    return out


# ══════════════════════════════════════════════════════════════════════════════
# §4.4 표본 요건 R1~R5
# ══════════════════════════════════════════════════════════════════════════════
def sample_gate(c: dict, n_runs: int, n_unresolved_raw: int,
                n_raw_rows: int) -> dict:
    """R1~R5 검사. 반환: {"passed": bool, "violations": ["R2", ...]}"""
    v: list[str] = []
    if c["n_problem"] < R1_MIN_PROBLEM:
        v.append("R1")
    if c["n_flagged"] < R2_MIN_FLAGGED:
        v.append("R2")
    if n_runs != R3_N_RUNS:
        v.append("R3")

    # R4: 설계는 UNRESOLVED "비율" 의 분모를 규정하지 않았다.
    # 단위 다수결 기준과 원자료(건×판) 기준을 모두 계산해 **큰 쪽**으로 판정한다
    # (fail-closed — 판정을 거부하는 쪽이 보수적이다). 보고서에 미규정 항목으로 남긴다.
    unit_ratio = c["n_unresolved"] / c["n_units"] if c["n_units"] else 1.0
    raw_ratio = n_unresolved_raw / n_raw_rows if n_raw_rows else 1.0
    if max(unit_ratio, raw_ratio) >= R4_MAX_UNRESOLVED:
        v.append("R4")

    split_ratio = c["n_split"] / c["n_units"] if c["n_units"] else 1.0
    if split_ratio >= R5_MAX_SPLIT:
        v.append("R5")
    return {"passed": not v, "violations": v}


# ══════════════════════════════════════════════════════════════════════════════
# 입력 로딩
# ══════════════════════════════════════════════════════════════════════════════
def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_labels(path: Path) -> dict[str, str]:
    """사람 라벨(정답지). 루프 밖 자산이므로 **읽기만** 한다 (INV-1·INV-2).

    지원 포맷
      - `.xlsx` : 시트 `라벨링`, G열 = S/C/I  (instrument_check_run.load_units 와 동일)
      - `.json` : `[{"id":..., "human_label":"S"}...]` 또는 `{"id": "S", ...}`
    """
    if path.suffix == ".xlsx":
        try:
            import openpyxl                     # 기존 venv 에 있음(신규 의존성 아님)
        except ImportError as exc:  # pragma: no cover
            raise SystemExit(f"openpyxl 필요: {exc}")
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True)["라벨링"]
        labels = {}
        for row in ws.iter_rows(min_row=2):
            vals = [c.value for c in row]
            if vals and vals[0] and len(vals) > 6 and vals[6] in ("S", "C", "I"):
                labels[str(vals[0])] = str(vals[6])
        return labels

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items() if v in ("S", "C", "I")}
    labels = {}
    for row in data:
        lab = row.get("human_label") or row.get("human")
        if lab in ("S", "C", "I"):
            labels[str(row["id"])] = lab
    return labels


def load_runs(patterns: Sequence[str]) -> tuple[dict[str, list[dict]], list[str]]:
    """3판 jsonl 로딩. 필드 구조는 instrument_check_run.py 출력 그대로
    (id / run / label / rationale / human / model / elapsed).
    """
    files: list[str] = []
    for pat in patterns:
        hit = sorted(glob.glob(pat))
        if not hit and Path(pat).exists():
            hit = [pat]
        if not hit:
            print(f"run 파일 없음: {pat}", file=sys.stderr)
            raise SystemExit(EXIT_INPUT)
        files.extend(hit)
    files = sorted(dict.fromkeys(files))         # 중복 제거 + 정렬(결정론)

    per: dict[str, list[dict]] = collections.defaultdict(list)
    for f in files:
        for line in Path(f).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            per[d["id"]].append(d)
    return per, [Path(f).name for f in files]


def build_units(per: dict[str, list[dict]], labels: dict[str, str]) -> list[Unit]:
    """라벨이 있는 id 만 단위로 삼는다(instrument_check_run.load_units 와 동일 필터)."""
    units = []
    for uid in sorted(per):
        human = labels.get(uid)
        if human not in ("S", "C", "I"):
            continue
        rows = sorted(per[uid], key=lambda r: str(r.get("run", "")))
        # 원자료에 human 이 들어 있으면 라벨 시트와 일치해야 한다(정답지 불변 검증).
        for r in rows:
            if r.get("human") not in (None, "", human):
                print(f"라벨 불일치 {uid}: 시트={human} 원자료={r.get('human')}",
                      file=sys.stderr)
                raise SystemExit(EXIT_INPUT)
        units.append(Unit(uid, human, majority([r["label"] for r in rows])))
    return units


# ══════════════════════════════════════════════════════════════════════════════
# 결과 조립 (§5.1 스키마 필드명)
# ══════════════════════════════════════════════════════════════════════════════
def build_result(candidate_id: str, units: Sequence[Unit], per: dict,
                 raw_files: Sequence[str], label_sha: str, *,
                 search_cost_calls: Optional[int] = None,
                 b: int = B, seed: int = SEED) -> dict:
    c = counts(units)
    ids = {u.id for u in units}
    rows = [r for uid in sorted(per) if uid in ids for r in per[uid]]
    n_runs = len({str(r.get("run", "")) for r in rows})
    n_unresolved_raw = sum(1 for r in rows if r.get("label") == "UNRESOLVED")

    ci_claim = bootstrap(units, "claim", b=b, seed=seed)
    ci_qid = bootstrap(units, "qid", b=b, seed=seed)

    objectives = {}
    for axis in AXES:
        val = _AXIS_FN[axis](units)
        objectives[axis] = {
            "value": None if val is None else round(val, 4),
            "ci_claim": ci_claim[axis]["ci"],
            "ci_qid": ci_qid[axis]["ci"],
        }

    elapsed = [r["elapsed"] for r in rows if isinstance(r.get("elapsed"), (int, float))]
    chars = [r["prompt_chars"] for r in rows
             if isinstance(r.get("prompt_chars"), (int, float))]

    gate = sample_gate(c, n_runs, n_unresolved_raw, len(rows))

    return {
        "candidate_id": candidate_id,
        "measurement": {
            "label_sheet_sha256": label_sha,
            "n_units": c["n_units"],
            "n_runs": n_runs,
            "n_problem": c["n_problem"],
            "n_flagged": c["n_flagged"],
            "n_detected": c["n_detected"],
            "n_split": c["n_split"],
            "n_unresolved": c["n_unresolved"],
            "raw_files": list(raw_files),
        },
        "objectives": objectives,
        "reference_fields": {
            # §3.5 참고 필드 — 기록하되 판정에 쓰지 않는다
            "elapsed_median": round(statistics.median(elapsed), 2) if elapsed else None,
            "prompt_chars_median": (int(statistics.median(chars)) if chars else None),
            "search_cost_calls": (len(rows) if search_cost_calls is None
                                  else search_cost_calls),
        },
        "sample_gate": gate,
        # ── 아래 2개는 §5.1 예시 스키마에 없는 추가 블록 ─────────────────────
        # bootstrap: §13.1 F1 이 "후보마다 seed 를 mh_archive.jsonl 에 기록" 하라고
        #   요구하는데 §5.1 스키마에 해당 필드가 없다. 요구를 지키려고 블록을 신설했다.
        # diagnostics: 판정 미사용. 미검출/SPLIT 목록 — §6.5 filter_strip 의 재료.
        "bootstrap": {
            "seed": seed, "B": b,
            "ci_method": f"percentile_{CI_LO_PCT}_{CI_HI_PCT}",
            "ci_used_for_judgment": CI_USED_FOR_JUDGMENT,
            "n_valid_resamples": {a: {"claim": ci_claim[a]["n_valid"],
                                      "qid": ci_qid[a]["n_valid"]} for a in AXES},
            "cluster_unit": "qid(문항) = id.split('-')[0]",
        },
        "diagnostics": {
            "n_contradicted": c["n_contradicted"],
            "n_unresolved_raw": n_unresolved_raw,
            "misses": [{"id": u.id, "human": u.human, "judge": u.maj}
                       for u in units if u.is_problem and not u.is_flagged],
            "false_alarms": [{"id": u.id, "judge": u.maj}
                             for u in units if u.is_flagged and not u.is_problem],
            "splits": [u.id for u in units if u.maj == SPLIT],
        },
    }


# ══════════════════════════════════════════════════════════════════════════════
# §8.2 IC-2 — CI 계산기 자기검침 (0콜)
# ══════════════════════════════════════════════════════════════════════════════
def _synth(n_prob: int, n_ok: int, judge_prob: bool,
           flag_ok: bool = False) -> list[Unit]:
    """합성 단위. qid 를 2건씩 묶어 클러스터 부트스트랩도 자명하지 않게 만든다."""
    us = []
    for i in range(n_prob):
        us.append(Unit(f"Q{i // 2:03d}-A-c{i}", "C",
                       "CONTRADICTED" if judge_prob else "SUPPORTED"))
    for i in range(n_ok):
        us.append(Unit(f"P{i // 2:03d}-A-c{i}", "S",
                       "INSUFFICIENT" if flag_ok else "SUPPORTED"))
    return us


def selftest(verbose: bool = True) -> bool:
    ok = True

    def chk(name: str, cond: bool, got: object = "") -> None:
        nonlocal ok
        ok = ok and cond
        if verbose:
            print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {got}")

    # (a) 전건 정탐 → recall CI = [1.0, 1.0]
    a = _synth(12, 20, judge_prob=True)
    ra = bootstrap(a, "qid")["recall"]["ci"]
    chk("(a) 전건 정탐 recall CI == [1.0, 1.0]", ra == [1.0, 1.0], ra)

    # (b) 전건 미탐 → recall CI = [0.0, 0.0]
    b_units = _synth(12, 20, judge_prob=False)
    rb = bootstrap(b_units, "qid")["recall"]["ci"]
    chk("(b) 전건 미탐 recall CI == [0.0, 0.0]", rb == [0.0, 0.0], rb)

    # (c) n_flagged = 0 → precision 미정의(None). 0.0 이 아니어야 한다 (§4.4 R2)
    pc = precision_of(b_units)
    chk("(c) n_flagged=0 → precision is None (0.0 아님)", pc is None, pc)
    cib = bootstrap(b_units, "qid")["precision"]["ci"]
    chk("(c) n_flagged=0 → precision CI is None", cib is None, cib)

    # 결정론: 같은 seed 2회 → 비트 단위 동일
    m = _synth(11, 44, judge_prob=True, flag_ok=True)
    d1, d2 = bootstrap(m, "qid"), bootstrap(m, "qid")
    chk("결정론(qid) 2회 호출 동일", d1 == d2, d1["recall"]["ci"])
    c1, c2 = bootstrap(m, "claim"), bootstrap(m, "claim")
    chk("결정론(claim) 2회 호출 동일", c1 == c2, c1["recall"]["ci"])

    # 보수성: qid 클러스터 CI 가 claim CI 보다 좁지 않아야 한다(§4.3 판정용 근거)
    w_qid = d1["precision"]["ci"][1] - d1["precision"]["ci"][0]
    w_clm = c1["precision"]["ci"][1] - c1["precision"]["ci"][0]
    chk("qid CI 폭 >= claim CI 폭", w_qid >= w_clm - 1e-9,
        f"qid={w_qid:.4f} claim={w_clm:.4f}")

    if verbose:
        print(f"\nIC-2 {'PASS' if ok else 'FAIL'} — CI 계산기 검침 (0콜)")
    return ok


# ══════════════════════════════════════════════════════════════════════════════
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--candidate-id", help="후보 id (예: c000)")
    ap.add_argument("--runs", nargs="+", default=[],
                    help="3판 jsonl 경로 또는 글롭 (예: 'scripts/mh_c000_run*.jsonl')")
    ap.add_argument("--labels", help="사람 라벨 파일 (.xlsx 또는 .json)")
    ap.add_argument("--out", help="출력 JSON 경로 (미지정 시 stdout)")
    ap.add_argument("--search-cost-calls", type=int, default=None,
                    help="§3.5 참고 필드. 기본값 = 원자료 행 수")
    ap.add_argument("--seed", type=int, default=SEED, help=f"기본 {SEED} (F1)")
    ap.add_argument("--bootstrap-b", type=int, default=B, help=f"기본 {B} (F2)")
    ap.add_argument("--selftest", action="store_true", help="§8.2 IC-2 자기검침 (0콜)")
    a = ap.parse_args(argv)

    if a.selftest:
        return EXIT_OK if selftest() else 1
    if not (a.candidate_id and a.runs and a.labels):
        ap.error("--candidate-id / --runs / --labels 필수 (또는 --selftest)")

    label_path = Path(a.labels)
    labels = load_labels(label_path)
    if not labels:
        print(f"라벨 0건 — 정답지를 읽지 못했다: {label_path}", file=sys.stderr)
        return EXIT_INPUT
    per, files = load_runs(a.runs)
    units = build_units(per, labels)
    if not units:
        print("라벨과 매칭되는 단위 0건", file=sys.stderr)
        return EXIT_INPUT

    res = build_result(a.candidate_id, units, per, files, sha256_file(label_path),
                       search_cost_calls=a.search_cost_calls,
                       b=a.bootstrap_b, seed=a.seed)

    txt = json.dumps(res, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")
        print(f"saved: {a.out}", file=sys.stderr)
    else:
        sys.stdout.write(txt)

    m, o, g = res["measurement"], res["objectives"], res["sample_gate"]
    print(f"[{a.candidate_id}] units={m['n_units']} runs={m['n_runs']} "
          f"problem={m['n_problem']} flagged={m['n_flagged']} "
          f"detected={m['n_detected']} split={m['n_split']}", file=sys.stderr)
    for axis in AXES:
        v = o[axis]["value"]
        print(f"  {axis:9s} = {'미정의' if v is None else f'{v:.4f}'}  "
              f"ci_claim={o[axis]['ci_claim']}  ci_qid={o[axis]['ci_qid']}",
              file=sys.stderr)
    if not g["passed"]:
        print(f"  🔴 판정 거부 — 표본 요건 위반 {g['violations']} → UNJUDGED",
              file=sys.stderr)
        return EXIT_SAMPLE_GATE
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
