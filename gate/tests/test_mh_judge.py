"""mh_objectives.py / mh_front.py 판정기 테스트.

정본: `gate/PARETO_META_HARNESS_DESIGN.md` §3.3 · §4 · §5.
🔴 INV-5 — 이 테스트와 판정기는 결과 열람 전에 커밋한다.

데이터 출처 표기 (요구사항)
  - `test_real_data_*` 는 **실제 원자료**를 쓴다:
    `gate/scripts/instrument_check_run{1,2,3}.jsonl` + 같은 파일의 `human` 필드(사람 라벨).
    (xlsx 정답지와의 일치는 `test_real_data_xlsx_labels_match_jsonl` 이 확인한다.)
  - 그 외 dominance / front / 상한 솎아내기 테스트는 **합성 fixture** 다.
    실제 후보가 아직 1개(c000)뿐이어서 다후보 front 를 실측으로 만들 수 없기 때문이다.
    합성값은 판정식 검증용이며 어떤 실측 주장도 하지 않는다.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

GATE = Path(__file__).resolve().parents[1]
SCRIPTS = GATE / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import mh_front as mf          # noqa: E402
import mh_objectives as mo     # noqa: E402

RUN_GLOB = "instrument_check_run*.jsonl"
REAL_RUNS = sorted(SCRIPTS.glob(RUN_GLOB))
IC_RESULT = SCRIPTS / "instrument_check_result.json"
LABEL_XLSX = SCRIPTS / "phase1_human_label_sheet.xlsx"
PY = sys.executable


# ══════════════════════════════════════════════════════════════════════════════
# 합성 후보 생성기 (dominance / front 테스트용)
# ══════════════════════════════════════════════════════════════════════════════
def cand(cid: str, r: float, p: float, ci_r, ci_p, *, generation: int = 0,
         n_flagged: int = 13, origin: str = "front_endpoint",
         status: str = "ON_FRONT", passed: bool = True, calls: int = 165) -> dict:
    """§5.1 스키마 최소 부분집합. 판정에 쓰는 필드만 채운다."""
    return {
        "candidate_id": cid,
        "generation": generation,
        "origin": origin,
        "harness": {"model": mf.MODEL_FIXED, "prompt_sha256": f"sha-{cid}",
                    "builder_module": "json", "builder_fn": "dumps"},
        "measurement": {"n_units": 55, "n_runs": 3, "n_problem": 11,
                        "n_flagged": n_flagged, "n_detected": 9, "n_split": 0,
                        "n_unresolved": 0},
        "objectives": {
            "recall": {"value": r, "ci_claim": list(ci_r), "ci_qid": list(ci_r)},
            "precision": {"value": p, "ci_claim": list(ci_p), "ci_qid": list(ci_p)},
        },
        "reference_fields": {"elapsed_median": 4.6, "prompt_chars_median": 3184,
                             "search_cost_calls": calls},
        "sample_gate": {"passed": passed, "violations": []},
        "status": status,
        "status_history": [],
    }


def write_archive(tmp_path: Path, cands) -> Path:
    p = tmp_path / "mh_archive.jsonl"
    with open(p, "w", encoding="utf-8") as fh:
        for c in cands:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    return p


# ══════════════════════════════════════════════════════════════════════════════
# 1. dominance 판정 진리표 (§4.1 · §4.2 · §4.3 N2)
# ══════════════════════════════════════════════════════════════════════════════
QID = "ci_qid"


def test_dominance_clear_dominate():
    """명확 지배 — 두 축 모두 CI 비겹침으로 우세."""
    x = cand("cA", 0.95, 0.95, [0.90, 1.00], [0.90, 1.00])
    y = cand("cB", 0.30, 0.30, [0.10, 0.50], [0.10, 0.50])
    assert mf.dominates(x, y, QID) is True
    assert mf.dominates(y, x, QID) is False
    assert mf.relation(x, y, QID) == "x 지배"


def test_dominance_clear_dominated():
    """명확 피지배 — 위 케이스의 반대 방향에서도 대칭으로 성립."""
    x = cand("cA", 0.30, 0.30, [0.10, 0.50], [0.10, 0.50])
    y = cand("cB", 0.95, 0.95, [0.90, 1.00], [0.90, 1.00])
    assert mf.dominates(x, y, QID) is False
    assert mf.dominates(y, x, QID) is True
    assert mf.relation(x, y, QID) == "y 지배"


def test_dominance_exact_tie_both_survive():
    """§4.2-1 완전 동률 — 서로 지배하지 않고 둘 다 front 에 남는다."""
    x = cand("cA", 0.80, 0.70, [0.60, 0.95], [0.50, 0.85])
    y = cand("cB", 0.80, 0.70, [0.60, 0.95], [0.50, 0.85], generation=1)
    assert mf.dominates(x, y, QID) is False
    assert mf.dominates(y, x, QID) is False
    assert mf.relation(x, y, QID) == "동률(병존)"
    res = mf.compute_front({"cA": x, "cB": y}, QID)
    assert res["front"] == ["cA", "cB"]


def test_dominance_ci_overlap_is_tie():
    """🔴 §4.3 N2 — 점 추정은 x 가 앞서지만 두 축 CI 가 겹치면 동률(비지배)."""
    x = cand("cA", 0.90, 0.80, [0.60, 1.00], [0.55, 0.95])
    y = cand("cB", 0.72, 0.65, [0.45, 0.95], [0.40, 0.88])
    assert mf.cmp_axis(x, y, "recall", QID) == 0
    assert mf.cmp_axis(x, y, "precision", QID) == 0
    assert mf.dominates(x, y, QID) is False
    # 점 추정 모드(ablation A-CI)에서는 같은 쌍이 지배로 판정된다 — CI 규칙의 효과 자체
    assert mf.dominates(x, y, None) is True


def test_dominance_one_axis_tie_one_axis_better():
    """§4.2-2 한 축 동률 + 한 축 우세 → 지배. PHASE1 3표 합의와 같은 형태."""
    x = cand("cA", 0.90, 0.95, [0.70, 1.00], [0.90, 1.00])
    y = cand("cB", 0.90, 0.40, [0.70, 1.00], [0.20, 0.60])
    assert mf.cmp_axis(x, y, "recall", QID) == 0
    assert mf.cmp_axis(x, y, "precision", QID) == +1
    assert mf.dominates(x, y, QID) is True


def test_dominance_tradeoff_non_dominated():
    """§4.2-3 한 축 우세 + 다른 축 열세 → 지배 아님(트레이드오프)."""
    x = cand("cA", 0.98, 0.40, [0.92, 1.00], [0.25, 0.55])
    y = cand("cB", 0.55, 0.95, [0.35, 0.70], [0.88, 1.00])
    assert mf.dominates(x, y, QID) is False
    assert mf.dominates(y, x, QID) is False
    assert mf.relation(x, y, QID) == "트레이드오프(비지배)"


def test_unjudged_neither_dominates_nor_dominated():
    """§5.2 3단계 — 표본 요건 미달 후보는 front 비교에서 완전히 빠진다."""
    good = cand("cA", 0.95, 0.95, [0.90, 1.00], [0.90, 1.00])
    bad = cand("cZ", 0.10, 0.10, [0.00, 0.20], [0.00, 0.20], passed=False)
    res = mf.compute_front({"cA": good, "cZ": bad}, QID)
    assert res["front"] == ["cA"]
    assert "cZ" not in res["dominated"]
    assert mf.judgeable(bad) is False


# ══════════════════════════════════════════════════════════════════════════════
# 2. 🔴 네거티브 컨트롤 — "전부 CONTRADICTED" 가짜 후보 (§3.3 · §8.2 IC-1)
# ══════════════════════════════════════════════════════════════════════════════
def _units_from_rows(rows_by_id: dict) -> list:
    return [mo.Unit(uid, rows_by_id[uid][0]["human"],
                    mo.majority([r["label"] for r in rows_by_id[uid]]))
            for uid in sorted(rows_by_id)]


def _real_rows() -> dict:
    per, _ = mo.load_runs([str(SCRIPTS / RUN_GLOB)])
    return per


def _synth_rows(n_problem: int = 11, n_ok: int = 44) -> dict:
    """실제 원자료가 없는 환경용 **합성 fixture**. 문항당 2건씩 묶는다."""
    per = {}
    for i in range(n_problem):
        uid = f"Q{i // 2:03d}-A-c{i}"
        lab = "CONTRADICTED" if i < 9 else "SUPPORTED"    # 9/11 검출 = 실측과 같은 비율
        per[uid] = [{"id": uid, "run": f"run{k}", "label": lab, "human": "C"}
                    for k in (1, 2, 3)]
    for i in range(n_ok):
        uid = f"P{i // 2:03d}-A-c{i}"
        lab = "CONTRADICTED" if i < 4 else "SUPPORTED"    # 오탐 4건
        per[uid] = [{"id": uid, "run": f"run{k}", "label": lab, "human": "S"}
                    for k in (1, 2, 3)]
    return per


def _all_contradicted(per: dict) -> dict:
    """가짜 후보: 무엇을 받아도 CONTRADICTED 를 낸다 → recall 은 1.0."""
    out = {}
    for uid, rows in per.items():
        out[uid] = [dict(r, label="CONTRADICTED") for r in rows]
    return out


def test_negative_control_all_contradicted_cannot_monopolize_front():
    """recall 만 보면 1위가 되는 가짜 후보가 precision 축 때문에 front 를 독점하지 못한다.

    설계 §3.3 이 precision 을 축으로 올린 이유가 정확히 이 병리다.
    """
    per = _real_rows() if REAL_RUNS else _synth_rows()
    base_units = _units_from_rows(per)
    neg_units = _units_from_rows(_all_contradicted(per))

    base = mo.build_result("c000", base_units, per, [], "sha-label")
    # 가짜 후보의 원자료 = 전부 CONTRADICTED 로 바꾼 것
    neg_per = _all_contradicted(per)
    neg = mo.build_result("c_neg_all", neg_units, neg_per, [], "sha-label")

    # recall 은 만점, precision 은 무너진다
    assert neg["objectives"]["recall"]["value"] == 1.0
    assert neg["objectives"]["precision"]["value"] < base["objectives"]["precision"]["value"]
    assert neg["measurement"]["n_flagged"] == neg["measurement"]["n_units"]

    for rec in (base, neg):
        rec.update({"generation": 0, "origin": "baseline", "status": "ON_FRONT",
                    "harness": {"model": mf.MODEL_FIXED,
                                "prompt_sha256": rec["candidate_id"]}})

    # 어느 쪽도 상대를 지배하지 못한다 → 가짜 후보가 front 를 독점하지 않는다
    assert mf.dominates(neg, base, QID) is False
    assert mf.dominates(neg, base, None) is False        # 점 추정에서도 마찬가지
    res = mf.compute_front({"c000": base, "c_neg_all": neg}, QID)
    assert "c000" in res["front"], "baseline 이 front 에서 밀려나면 축 설계 실패"

    # 그리고 precision 축은 과검출을 실제로 벌한다 (점 추정 기준. IC-1 의 축 판별력)
    assert mf.cmp_axis(base, neg, "precision", None) == +1


def test_negative_control_single_axis_would_have_won():
    """대조 확인 — recall 만 축이면 가짜 후보가 이겼다(= 단일 축 게이트의 실패)."""
    per = _real_rows() if REAL_RUNS else _synth_rows()
    base = mo.recall_of(_units_from_rows(per))
    neg = mo.recall_of(_units_from_rows(_all_contradicted(per)))
    assert neg > base


# ══════════════════════════════════════════════════════════════════════════════
# 3. front 상한 초과 솎아내기 — 결정론 (§5.4)
# ══════════════════════════════════════════════════════════════════════════════
def _twelve_tied():
    """12개 후보. CI 를 크게 겹치게 두어 전부 비지배가 되도록 만든 **합성 fixture**."""
    out = {}
    for k in range(12):
        cid = f"c{k:03d}"
        r = 0.60 + 0.01 * k
        p = 0.90 - 0.01 * k
        out[cid] = cand(cid, round(r, 4), round(p, 4),
                        [0.30, 1.00], [0.30, 1.00],
                        generation=k // 4, n_flagged=5 + k)
    return out


def test_front_cap_prune_is_deterministic():
    pool = _twelve_tied()
    res = mf.compute_front(pool, QID)
    assert len(res["front"]) == 12, "겹침 동률이면 전부 비지배여야 한다 (§4.3 N3)"

    keep1, pruned1, halt1 = mf.prune_front(res["front"], pool, QID)
    keep2, pruned2, halt2 = mf.prune_front(res["front"], pool, QID)
    assert keep1 == keep2 and [p["id"] for p in pruned1] == [p["id"] for p in pruned2]
    assert halt1 is None and halt2 is None
    assert len(keep1) == mf.FRONT_CAP

    # 끝점 보호 (§5.4-1) — c000 은 n_flagged 최소지만 precision 끝점이므로 살아남는다
    ep = mf.endpoints(res["front"], pool, QID)
    assert ep == {"recall": "c011", "precision": "c000"}
    assert ep["recall"] in keep1 and ep["precision"] in keep1
    # §5.4-2 — 구별 불가 후보 중 n_flagged 작은 순으로 정확히 4개가 솎인다
    assert [p["id"] for p in pruned1] == ["c001", "c002", "c003", "c004"]
    assert all("§5.4-2" in p["rule"] for p in pruned1)


def test_front_cap_prune_step3_by_generation():
    """§5.4-3 — 전부 구별 가능한(트레이드오프) 12개면 2단계가 비어 3단계로 내려간다.

    합성 fixture: CI 폭 ±0.01, 이웃 간 간격 0.07 → 모든 쌍이 CI 비겹침 트레이드오프.
    """
    pool = {}
    for k in range(12):
        cid = f"c{k:03d}"
        r, p = round(0.10 + 0.07 * k, 4), round(0.90 - 0.07 * k, 4)
        pool[cid] = cand(cid, r, p, [r - 0.01, r + 0.01], [p - 0.01, p + 0.01],
                         generation=k // 4, n_flagged=13)
    res = mf.compute_front(pool, QID)
    assert len(res["front"]) == 12
    keep, pruned, halt = mf.prune_front(res["front"], pool, QID)
    assert halt is None and len(keep) == mf.FRONT_CAP
    assert all("§5.4-3" in p["rule"] for p in pruned)
    # generation 큰(늦게 온) 쪽부터. 단 끝점 c011(recall 최대)은 보호된다
    assert [p["id"] for p in pruned] == ["c010", "c009", "c008", "c007"]
    assert "c011" in keep and "c000" in keep
    assert mf.prune_front(res["front"], pool, QID)[0] == keep      # 결정론


def test_front_cap_filter_strip_majority_halts_instead_of_pruning():
    """§5.4 예외 — front 절반 이상이 filter_strip 이면 솎지 않고 정지 신호."""
    pool = _twelve_tied()
    for k in range(6):
        pool[f"c{k:03d}"]["origin"] = "filter_strip"
    res = mf.compute_front(pool, QID)
    keep, pruned, halt = mf.prune_front(res["front"], pool, QID)
    assert pruned == [] and len(keep) == 12
    assert halt == "T4_filter_strip_majority"


def test_pruned_is_permanent_and_excluded():
    """§5.3 — PRUNED 는 되돌릴 수 없고 front 판정에서 영구 제외."""
    pool = _twelve_tied()
    pool["c003"]["status"] = "PRUNED"
    res = mf.compute_front(pool, QID)
    assert "c003" not in res["front"]
    assert mf.judgeable(pool["c003"]) is False


# ══════════════════════════════════════════════════════════════════════════════
# 4. 최소 표본 요건 R1~R5 (§4.4) — 미달이면 판정 거부
# ══════════════════════════════════════════════════════════════════════════════
def test_sample_gate_r1_too_few_problems():
    per = _synth_rows(n_problem=5, n_ok=40)      # 합성 fixture
    units = _units_from_rows(per)
    res = mo.build_result("cR1", units, per, [], "sha")
    assert "R1" in res["sample_gate"]["violations"]
    assert res["sample_gate"]["passed"] is False


def test_sample_gate_r2_precision_undefined_not_zero():
    """🔴 §4.4 R2 의 함정 — flagged 0 이면 precision 은 0.0 이 아니라 미정의."""
    per = {}
    for i in range(12):
        uid = f"Q{i // 2:03d}-A-c{i}"
        per[uid] = [{"id": uid, "run": f"run{k}", "label": "SUPPORTED", "human": "C"}
                    for k in (1, 2, 3)]
    units = _units_from_rows(per)
    res = mo.build_result("cR2", units, per, [], "sha")
    assert res["objectives"]["precision"]["value"] is None
    assert res["objectives"]["precision"]["ci_qid"] is None
    assert "R2" in res["sample_gate"]["violations"]


def test_sample_gate_r3_requires_exactly_three_runs():
    per = _synth_rows()
    per2 = {uid: rows[:2] for uid, rows in per.items()}   # 2판만
    res = mo.build_result("cR3", _units_from_rows(per2), per2, [], "sha")
    assert "R3" in res["sample_gate"]["violations"]


def test_sample_gate_r5_split_ratio():
    """3판이 전부 갈리면 SPLIT — 비율 20% 이상이면 '측정이 고장난 것'으로 본다."""
    per = {}
    for i in range(20):
        uid = f"Q{i // 2:03d}-A-c{i}"
        human = "C" if i < 10 else "S"
        per[uid] = [{"id": uid, "run": "run1", "label": "SUPPORTED", "human": human},
                    {"id": uid, "run": "run2", "label": "CONTRADICTED", "human": human},
                    {"id": uid, "run": "run3", "label": "INSUFFICIENT", "human": human}]
    units = _units_from_rows(per)
    assert all(u.maj == mo.SPLIT for u in units)
    res = mo.build_result("cR5", units, per, [], "sha")
    assert res["measurement"]["n_split"] == 20
    assert "R5" in res["sample_gate"]["violations"]


def test_majority_matches_instrument_check_rule():
    assert mo.majority(["A", "A", "B"]) == "A"
    assert mo.majority(["A", "B", "C"]) == mo.SPLIT
    assert mo.majority(["A", "A", "A"]) == "A"


# ══════════════════════════════════════════════════════════════════════════════
# 5. 부트스트랩 결정론 (§13.1 F1·F2, §8.2 IC-2)
# ══════════════════════════════════════════════════════════════════════════════
def test_bootstrap_determinism_same_seed():
    units = _units_from_rows(_real_rows() if REAL_RUNS else _synth_rows())
    a1 = mo.bootstrap(units, "qid")
    a2 = mo.bootstrap(units, "qid")
    b1 = mo.bootstrap(units, "claim")
    b2 = mo.bootstrap(units, "claim")
    assert a1 == a2 and b1 == b2
    # seed 를 바꾸면 CI 가 (일반적으로) 달라진다 — seed 가 실제로 쓰이는지 확인
    assert mo.bootstrap(units, "qid", seed=1) != a1


def test_bootstrap_qid_ci_is_not_narrower_than_claim():
    """§4.3 — 판정에 쓰는 qid 클러스터 CI 가 claim CI 보다 좁으면 '보수적' 근거가 깨진다."""
    units = _units_from_rows(_real_rows() if REAL_RUNS else _synth_rows())
    q = mo.bootstrap(units, "qid")["precision"]["ci"]
    c = mo.bootstrap(units, "claim")["precision"]["ci"]
    assert (q[1] - q[0]) >= (c[1] - c[0]) - 1e-9


def test_ic2_selftest_passes():
    assert mo.selftest(verbose=False) is True


# ══════════════════════════════════════════════════════════════════════════════
# 6. 실제 원자료 대조 (§3.3 — 기존 계산과 동일 정의여야 한다)
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.skipif(not REAL_RUNS or not IC_RESULT.exists(),
                    reason="실제 원자료 없음 — 합성 fixture 테스트로 충분")
def test_real_data_matches_instrument_check_result():
    ic = json.loads(IC_RESULT.read_text(encoding="utf-8"))
    per = _real_rows()
    units = _units_from_rows(per)
    res = mo.build_result("c000", units, per, [], "sha")
    m = res["measurement"]
    assert (m["n_units"], m["n_problem"], m["n_detected"], m["n_split"]) == \
           (ic["n_units"], ic["n_problem"], ic["n_detected"], ic["n_split"])
    assert res["objectives"]["recall"]["value"] == ic["recall"]
    assert res["objectives"]["precision"]["value"] == ic["precision_reported_only"]
    assert res["diagnostics"]["n_contradicted"] == ic["n_contradicted"]
    assert [d["id"] for d in res["diagnostics"]["misses"]] == \
           [d["id"] for d in ic["misses"]]


@pytest.mark.skipif(not LABEL_XLSX.exists() or not REAL_RUNS,
                    reason="라벨 시트 없음")
def test_real_data_xlsx_labels_match_jsonl():
    """INV-2 정신 — 정답지(xlsx)와 원자료의 human 필드가 어긋나면 비교 불가."""
    labels = mo.load_labels(LABEL_XLSX)
    per = _real_rows()
    units = mo.build_units(per, labels)          # 불일치면 SystemExit
    assert len(units) == 55
    assert sum(1 for u in units if u.is_problem) == 11


@pytest.mark.skipif(not REAL_RUNS or not LABEL_XLSX.exists(), reason="실제 원자료 없음")
def test_cli_determinism_two_runs_identical(tmp_path):
    """요구사항 검증 3 — 같은 입력 2회 실행 → 출력 diff 가 비어야 한다."""
    outs = []
    for k in (1, 2):
        o = tmp_path / f"o{k}.json"
        cp = subprocess.run(
            [PY, str(SCRIPTS / "mh_objectives.py"), "--candidate-id", "c000",
             "--runs", str(SCRIPTS / RUN_GLOB), "--labels", str(LABEL_XLSX),
             "--out", str(o)], capture_output=True, text=True)
        assert cp.returncode == 0, cp.stderr
        outs.append(o.read_text(encoding="utf-8"))
    assert outs[0] == outs[1]


def test_cli_exit_code_on_sample_gate_violation(tmp_path):
    """미달이면 종료 코드 3 으로 판정 거부."""
    runs = tmp_path / "x_run1.jsonl"
    per = _synth_rows(n_problem=4, n_ok=6)       # 합성 fixture — R1 위반
    labels = {}
    with open(runs, "w", encoding="utf-8") as fh:
        for uid, rows in sorted(per.items()):
            labels[uid] = rows[0]["human"]
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    lab = tmp_path / "labels.json"
    lab.write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")

    cp = subprocess.run(
        [PY, str(SCRIPTS / "mh_objectives.py"), "--candidate-id", "cX",
         "--runs", str(runs), "--labels", str(lab), "--out", str(tmp_path / "o.json")],
        capture_output=True, text=True)
    assert cp.returncode == mo.EXIT_SAMPLE_GATE, cp.stderr
    doc = json.loads((tmp_path / "o.json").read_text(encoding="utf-8"))
    assert doc["sample_gate"]["passed"] is False and "R1" in doc["sample_gate"]["violations"]


# ══════════════════════════════════════════════════════════════════════════════
# 7. 아카이브 입출력 — append-only (§5.3)
# ══════════════════════════════════════════════════════════════════════════════
def test_front_cli_appends_status_without_overwriting(tmp_path):
    pool = {
        "c000": cand("c000", 0.95, 0.95, [0.90, 1.00], [0.90, 1.00], status="ON_FRONT"),
        "c001": cand("c001", 0.20, 0.20, [0.05, 0.35], [0.05, 0.35], status="ON_FRONT",
                     generation=1),
    }
    arc = write_archive(tmp_path, [pool["c000"], pool["c001"]])
    before = arc.read_text(encoding="utf-8")
    out = tmp_path / "mh_front.json"

    rc = mf.main(["front", "--archive", str(arc), "--out", str(out),
                  "--computed-at", "2026-07-31T00:00:00+09:00"])
    assert rc == 0
    after = arc.read_text(encoding="utf-8")
    assert after.startswith(before), "기존 레코드를 덮어쓰면 안 된다 (append-only)"
    assert len(after.splitlines()) == len(before.splitlines()) + 1

    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["front"] == ["c000"]
    assert doc["dominated"] == [{"id": "c001", "dominated_by": ["c000"]}]
    assert doc["g1_excluded"] == ["c001"]          # G1 — baseline 에게 지배당함
    assert doc["ci_used"] == "ci_qid"

    _, latest = mf.load_archive(arc)
    assert latest["c001"]["status"] == "DOMINATED"
    assert latest["c001"]["status_history"][-1]["status"] == "DOMINATED"
    assert "G1" in latest["c001"]["status_history"][-1]["by"]


def test_front_stall_rounds_increments_when_unchanged(tmp_path):
    """§6.4 T1 — front 가 갱신되지 않으면 stall_rounds 가 쌓인다."""
    arc = write_archive(tmp_path, [cand("c000", 0.9, 0.9, [0.8, 1.0], [0.8, 1.0])])
    out = tmp_path / "f.json"
    seen = []
    for _ in range(4):
        mf.main(["front", "--archive", str(arc), "--out", str(out),
                 "--computed-at", "2026-07-31T00:00:00+09:00", "--no-status-write"])
        seen.append(json.loads(out.read_text(encoding="utf-8")))
    assert seen[0]["front_changed"] is True and seen[0]["stall_rounds"] == 0
    assert [d["stall_rounds"] for d in seen] == [0, 1, 2, 3]
    assert "T1" in seen[-1]["termination"]["triggered"]


def test_front_ci_none_mode_changes_membership(tmp_path):
    """ablation A-CI — 점 추정 모드에서는 CI 겹침 동률이 지배로 바뀐다."""
    a = cand("c000", 0.90, 0.80, [0.60, 1.00], [0.55, 0.95])
    b = cand("c001", 0.72, 0.65, [0.45, 0.95], [0.40, 0.88], generation=1)
    arc = write_archive(tmp_path, [a, b])
    out = tmp_path / "f.json"
    mf.main(["front", "--archive", str(arc), "--out", str(out), "--dry-run"])
    assert mf.compute_front({"c000": a, "c001": b}, "ci_qid")["front"] == ["c000", "c001"]
    assert mf.compute_front({"c000": a, "c001": b}, None)["front"] == ["c000"]


def test_add_rejects_model_alias_and_duplicate_prompt(tmp_path):
    """§5.2 1단계 — INV-3 모델 고정 위반과 prompt_sha256 중복은 INVALID."""
    base = cand("c000", 0.9, 0.9, [0.8, 1.0], [0.8, 1.0])
    arc = write_archive(tmp_path, [base])
    _, latest = mf.load_archive(arc)

    bad_model = {"model": "claude-sonnet-latest", "prompt_sha256": "new",
                 "builder_module": "json", "builder_fn": "dumps"}
    assert any("INV-3" in v for v in mf.validity_check(bad_model, latest))

    dup = {"model": mf.MODEL_FIXED, "prompt_sha256": "sha-c000",
           "builder_module": "json", "builder_fn": "dumps"}
    assert any("중복" in v for v in mf.validity_check(dup, latest))

    no_builder = {"model": mf.MODEL_FIXED, "prompt_sha256": "new2",
                  "builder_module": "no_such_module_xyz", "builder_fn": "build"}
    assert any("import 실패" in v for v in mf.validity_check(no_builder, latest))

    ok = {"model": mf.MODEL_FIXED, "prompt_sha256": "new3",
          "builder_module": "json", "builder_fn": "dumps"}
    assert mf.validity_check(ok, latest) == []


def test_add_unjudged_candidate_enters_archive_but_not_front(tmp_path):
    """§5.2 3단계 — UNJUDGED 는 원장에 남고 front 판정에서만 빠진다."""
    arc = tmp_path / "mh_archive.jsonl"
    obj = {
        "candidate_id": "c009",
        "measurement": {"n_units": 55, "n_runs": 3, "n_problem": 11, "n_flagged": 2,
                        "n_detected": 1, "n_split": 0, "n_unresolved": 0,
                        "label_sheet_sha256": "sha", "raw_files": []},
        "objectives": {"recall": {"value": 0.09, "ci_claim": [0.0, 0.3],
                                  "ci_qid": [0.0, 0.3]},
                       "precision": {"value": 0.5, "ci_claim": [0.0, 1.0],
                                     "ci_qid": [0.0, 1.0]}},
        "reference_fields": {"elapsed_median": 4.6, "prompt_chars_median": 100,
                             "search_cost_calls": 165},
        "sample_gate": {"passed": False, "violations": ["R2"]},
    }
    op = tmp_path / "obj.json"
    op.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    hp = tmp_path / "h.json"
    hp.write_text(json.dumps({"model": mf.MODEL_FIXED, "prompt_sha256": "s9",
                              "builder_module": "json", "builder_fn": "dumps"}),
                  encoding="utf-8")

    rc = mf.main(["add", "--archive", str(arc), "--objectives", str(op),
                  "--harness", str(hp), "--origin", "front_endpoint",
                  "--origin-reason", "테스트", "--generation", "1",
                  "--computed-at", "2026-07-31T00:00:00+09:00"])
    assert rc == 3
    _, latest = mf.load_archive(arc)
    assert latest["c009"]["status"] == "UNJUDGED"
    assert mf.compute_front(latest, "ci_qid")["front"] == []


def test_dominance_subcommand_runs(tmp_path, capsys):
    arc = write_archive(tmp_path, [
        cand("c000", 0.95, 0.95, [0.90, 1.00], [0.90, 1.00]),
        cand("c001", 0.20, 0.20, [0.05, 0.35], [0.05, 0.35], generation=1)])
    rc = mf.main(["dominance", "--archive", str(arc), "--a", "c000", "--b", "c001"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "A≻B=True" in out and "B≻A=False" in out


def test_t2_budget_termination(tmp_path):
    """§6.4 T2 — 누적 콜이 1,650 을 넘으면 정지."""
    cands = [cand(f"c{k:03d}", 0.9, 0.9, [0.8, 1.0], [0.8, 1.0], generation=k,
                  calls=165) for k in range(11)]
    for k, c in enumerate(cands):       # 서로 다른 프롬프트 해시 유지
        c["harness"]["prompt_sha256"] = f"sha{k}"
    arc = write_archive(tmp_path, cands)
    out = tmp_path / "f.json"
    mf.main(["front", "--archive", str(arc), "--out", str(out), "--no-status-write",
             "--computed-at", "2026-07-31T00:00:00+09:00"])
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["termination"]["cumulative_calls"] == 11 * 165
    assert "T2" in doc["termination"]["triggered"]
