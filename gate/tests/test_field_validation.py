#!/usr/bin/env python3
"""공개 원자료 + 2026-08-28 필드 집계로 새 측정기 실측 회귀검증."""
import hashlib, json, pathlib, sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "gate"))
from harness_diet import Point, judge, point, parse_pair, safe_label, strict_object as strict_measurement_object, main as harness_main
from reach_check import ReachReport, reach_report


def strict_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def test_public_ab():
    """119문 공개 A/B 원자료를 직접 재집계 — 문서 숫자 하드코딩 금지."""
    grades_path = ROOT / "ab/ab_grades.json"
    questions_path = ROOT / "ab/ab_questions_FROZEN.json"
    grades_raw, questions_raw = grades_path.read_bytes(), questions_path.read_bytes()
    assert hashlib.sha256(grades_raw).hexdigest() == "0058053fe6c51b817c81bcc80e778754d07b3f4a92251a29f45f7659422969a5"
    assert hashlib.sha256(questions_raw).hexdigest() == "29aad055199a99e51ad65d1f6d62d44142c5974cc14e898fb5aeb5bcc09d9d30"
    grades = json.loads(grades_raw, object_pairs_hook=strict_object)
    frozen = json.loads(questions_raw, object_pairs_hook=strict_object)
    qids = [q["qid"] for q in frozen["questions"]]
    assert len(qids) == len(set(qids)) == 119 and all(isinstance(q, str) for q in qids)
    assert set(grades) == set(qids)
    required_fields = {"citeA_err", "citeB_err", "accA", "accB"}
    draft_fields = {"citeB_draft_err", "accB_draft"}
    for qid, record in grades.items():
        assert isinstance(record, dict) and set(record) in (required_fields, required_fields | draft_fields), qid
        assert all(type(value) is bool for value in record.values()), qid
    n = len(grades)
    cite_a = sum(x["citeA_err"] for x in grades.values())
    cite_b = sum(x["citeB_err"] for x in grades.values())
    acc_a = sum(x["accA"] for x in grades.values())
    acc_b = sum(x["accB"] for x in grades.values())
    over = sum(x["accA"] and not x["accB"] for x in grades.values())
    assert (n, cite_a, cite_b, acc_a, acc_b, over) == (119, 0, 0, 118, 118, 1)

    # 품질=정답률(높을수록 좋음), 비용=과교정률(낮을수록 좋음)
    v = judge(Point(acc_a / n, 0.0), Point(acc_b / n, over / n), reach=n)
    assert v.verdict == "REMOVE", v
    print(f"public A/B {n}문 직접집계 → REMOVE (정확도 {acc_a}/{n} 동일, ON 과교정 {over}/{n})")


def test_field_aggregate_schema_replay():
    f = json.loads((ROOT / "gate/fixtures/targeting_reach_field_20260828.json").read_text())
    assert f["verification_level"] == "recorded_aggregate_replay_not_independent_recomputation"
    assert (f["guard_index_before"], f["guard_index_after"]) == (0, 137024)
    p = f["production_ab"]
    assert p["recall_at_10_before"] == p["recall_at_10_after"] == .110
    assert p["precision_at_3_before"] == p["precision_at_3_after"] == .051
    assert p["hit_at_3_before"] == p["hit_at_3_after"] == .154
    assert p["all_rank_changes"] == 0

    t = f["targeted_ab"]
    # 필드 원자료는 비공개라 query-level 재계산이 아니라 기록 집계의 정합성 replay다.
    # 전체 순서변동 13건은 대상 전용 이동과 구분하며, MOVED 판정은 노출 36→21에만 근거한다.
    r = ReachReport(t["n_queries"], t["reach"], t["target_exposure_before"],
                    t["target_exposure_after"], 0)
    assert (r.n_queries, r.reach, r.exposure_before, r.exposure_after) == (20, 17, 36, 21)
    assert t["all_rank_changes"] == 13
    assert r.verdict == "MOVED", r
    assert f["adjudication"] == {
        "regression": "not_observed",
        "relevance_improvement": "not_demonstrated",
        "safety_proxy": "recovered",
    }
    print("field aggregate replay → RECORDED_MOVED (도달 17/20, 대상노출 36→21, 전체 순서변동 13; query-level 독립검증 아님)")


def test_input_boundaries():
    with pytest.raises(ValueError):
        judge(Point(1, 1), Point(1, 1), reach=True)
    with pytest.raises(ValueError):
        point({"quality": 1, "cost": 1, "extra": 1}, "off")
    with pytest.raises(ValueError):
        parse_pair("quality=1,quality=2,cost=1")
    with pytest.raises(ValueError):
        safe_label("quality\x1b[2J", "quality")
    with pytest.raises(ValueError):
        safe_label("quality\u202eabc", "quality")
    with pytest.raises(ValueError):
        point({"quality": True, "cost": 1}, "off")
    with pytest.raises(ValueError):
        json.loads('{"off": 1, "off": 2}', object_pairs_hook=strict_measurement_object)
    with pytest.raises(SystemExit):
        harness_main(["--json", "x.json", "--off", "quality=1,cost=1", "--on", "quality=1,cost=1"])
    for bad in (True, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            Point(bad, 1)
    # 숨은 허용오차 없음: 작은 실제 개선도 KEEP이다.
    assert judge(Point(1, 1), Point(1 + 1e-13, 1)).verdict == "KEEP"


def test_skill_runtime_recommendation_contract():
    text = (ROOT / "skill-pareto/SKILL.md").read_text()
    required = [
        "도메인 독립 계약", "validator", "retry loop", "safety filter",
        "실행 전 중첩 점검", "그래도 추가하시겠습니까?",
        "사용자 승인 후", "자동 삭제하지",
    ]
    assert all(token in text for token in required)


def test_reach_boundaries():
    with pytest.raises(ValueError):
        ReachReport(1, 2, 0, 0, 0)
    with pytest.raises(ValueError):
        ReachReport(1, 1, 0, 0, 0)
    with pytest.raises(ValueError):
        reach_report({"q": ["t", "t"]}, {"q": ["t"]}, {"t"})
    with pytest.raises(ValueError):
        reach_report({"q1": ["t"]}, {"q2": ["t"]}, {"t"})
    # ON이 새로 target을 주입해도 baseline 도달 0이면 자기 유효화하지 못한다.
    injected = reach_report({"q": ["x"]}, {"q": ["t"]}, {"t"})
    assert injected.reach == 0 and injected.verdict == "TARGETING_FAILURE"
    mixed = reach_report({"hit": ["t"], "miss": ["x"]},
                         {"hit": ["t"], "miss": ["t"]}, {"t"})
    assert (mixed.reach, mixed.exposure_before, mixed.exposure_after,
            mixed.target_rank_changes, mixed.verdict) == (1, 1, 1, 0, "NO_EFFECT")
    with pytest.raises(ValueError):
        reach_report({"q": ["t"]}, {"q": ["t"]}, {"t"}, top_k=0)
    # 비대상 문서만 재정렬된 것은 대상 효과가 아니다.
    r = reach_report({"q": ["t", "x", "y"]}, {"q": ["t", "y", "x"]}, {"t"})
    assert r.verdict == "NO_EFFECT" and r.target_rank_changes == 0


if __name__ == "__main__":
    test_public_ab()
    test_field_aggregate_schema_replay()
    print("public validation + field aggregate replay PASS")
