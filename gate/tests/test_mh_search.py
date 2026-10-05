"""Pareto meta-harness search runner — 0 LLM calls (ADDENDUM3 §4, design §13.3 D-3/D-4)."""
import json
import pathlib
import subprocess
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import instrument_check_run as icr  # noqa: E402
import mh_front as mf  # noqa: E402
import mh_judge_sets as mjs  # noqa: E402
import mh_propose as mp  # noqa: E402
import mh_search as ms  # noqa: E402
import phase3_build_prompts as p3  # noqa: E402


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Any real LLM path raises. MODEL_FIXED aligned in memory (IMPL_NOTES B1)."""
    def boom(*a, **k):
        raise AssertionError("LLM call attempted")
    monkeypatch.setattr(icr, "call", boom)
    monkeypatch.setattr(mp, "claude_cli_caller", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(mf, "MODEL_FIXED", p3.CLAUDE_MODEL)


def dry(cond, root, caller=mp.stub_caller):
    return ms.run(cond, root=root, caller=caller, measure=ms.stub_measure, dry=True,
                  log=lambda *_: None)


def test_dry_run_uses_only_stubs_and_counts_calls(tmp_path):
    seen = []

    def counting_stub(prompt):
        seen.append(prompt)
        return mp.stub_caller(prompt)
    counting_stub.is_stub = True
    res = dry("C2", tmp_path, counting_stub)
    assert getattr(mp.stub_caller, "is_stub", False) and getattr(ms.stub_measure, "is_stub")
    plans = ms._jsonl(tmp_path / "mh_search_C2/plans.jsonl")
    assert len(seen) == sum(p["proposer_calls"] for p in plans) > 0
    assert res["spent_calls"] == 165 * sum(
        1 for p in plans for s in p["slots"] if s.get("cid") and not s["invalid"])


def test_dry_run_refuses_non_stub_caller(tmp_path):
    with pytest.raises(SystemExit):
        dry("C1", tmp_path, caller=lambda p: mp.stub_caller(p))
    assert not (tmp_path / "mh_archive_C1.jsonl").exists()


def test_c1_parent_selection_deterministic_D3(tmp_path):
    assert ms.c1_parents(["c000", "c201", "c202"], 2) == ms.c1_parents(["c202", "c000", "c201"], 2)
    a, b = tmp_path / "a", tmp_path / "b"
    dry("C1", a), dry("C1", b)
    for rel in ("mh_archive_C1.jsonl", "mh_search_C1/plans.jsonl", "mh_search_C1/rounds.jsonl"):
        assert (a / rel).read_bytes() == (b / rel).read_bytes(), rel


def test_archive_restore_same_front_D4(tmp_path):
    dry("C2", tmp_path)
    saved = json.loads((tmp_path / "mh_front_C2.json").read_text())
    _, latest = mf.load_archive(tmp_path / "mh_archive_C2.jsonl")
    res = mf.compute_front(latest, "ci_qid")
    keep, _, _ = mf.prune_front(res["front"], res["pool"], "ci_qid")
    assert keep == saved["front"]
    assert mf.endpoints(keep, res["pool"], "ci_qid") == saved["endpoints"]


def test_resume_is_idempotent(tmp_path):
    dry("C1", tmp_path)
    arch = (tmp_path / "mh_archive_C1.jsonl").read_bytes()
    rounds = tmp_path / "mh_search_C1/rounds.jsonl"
    lines = rounds.read_text().splitlines(keepends=True)
    rounds.write_text("".join(lines[:-1]))            # crash after adds, before round log
    dry("C1", tmp_path)
    assert (tmp_path / "mh_archive_C1.jsonl").read_bytes() == arch
    assert rounds.read_text().splitlines(keepends=True) == lines


def test_budget_stop_T2(tmp_path, monkeypatch):
    monkeypatch.setattr(ms, "BUDGET", 330)
    res = dry("C0", tmp_path)
    plan = ms._jsonl(tmp_path / "mh_search_C0/plans.jsonl")[0]
    assert res["spent_calls"] == 330 and "T2" in res["stops"]
    assert [s.get("empty", "").split(" ")[0] for s in plan["slots"]][-1] == "budget"


def test_c0_reject_status_and_stall(tmp_path):
    res = dry("C0", tmp_path)
    _, latest = mf.load_archive(tmp_path / "mh_archive_C0.jsonl")
    kids = [r for i, r in latest.items() if i != "c000"]
    assert all(r["status"] in (mf.STATUS_REJECTED_C0, mf.STATUS_ON_FRONT, mf.STATUS_DOMINATED,
                               mf.STATUS_INVALID, mf.STATUS_UNJUDGED) for r in kids)
    if all(r["status"] == mf.STATUS_REJECTED_C0 for r in kids):
        assert res["stops"] == ["T1"] and ms.c0_stall(latest, res["rounds"]) == 3


def test_c2_round2_has_s3_with_forbidden_surfaces(tmp_path):
    dry("C2", tmp_path)
    p = ms.P("C2", tmp_path)
    lat = ms.latest(p)
    doc = json.loads(p.front.read_text())
    slots = ms.c2_slots(doc, lat, p, ms.mo.load_labels(ms.LABELS))
    assert [s["slot"] for s in slots] == ["FS", "S1", "S2", "S3"]
    ep = doc["endpoints"]
    if ep["recall"] != ep["precision"] and "empty" not in slots[3]:
        edited = set()
        for c in (ep["recall"], ep["precision"]):
            edited |= set(lat[c]["harness"].get("edited_surface") or [])
        assert set(slots[3]["forbidden"]) == edited


def test_proposer_rejects_bad_edits():
    base = {"candidate_id": "c000", "harness": ms.baseline_harness(), "objectives": None}
    old = mp.DEFAULT_PARTS["def_insufficient"]

    def reply(surface, new):
        return lambda _p: json.dumps({"surface": surface, "new_value": new,
                                      "diff_from_parent": "d", "origin_reason": "r"})
    assert mp.propose([base], context={}, mode="edit", forbidden=set(),
                      caller=reply("JUDGE.def_insufficient", old))[0] is None        # no-op
    assert mp.propose([base], context={}, mode="edit", forbidden={"JUDGE.task"},
                      caller=reply("JUDGE.task", "x"))[0] is None                     # forbidden
    assert mp.propose([base], context={}, mode="delete_only", forbidden=set(),
                      caller=reply("JUDGE.def_insufficient", old + "more"))[0] is None
    child, _ = mp.propose([base], context={}, mode="delete_only", forbidden=set(),
                          caller=reply("JUDGE.def_insufficient", ""))
    assert child["harness"]["edited_surface"] == ["JUDGE.def_insufficient"]
    assert mp.propose([base], context={}, mode="edit", forbidden=set(),
                      caller=lambda _p: "not json")[0] is None


def test_auto_judge_selftest_covers_V1_to_V7():
    assert mjs.selftest(verbose=False)


def test_auto_judge_on_dry_run_fronts(tmp_path):
    for c in ("C2", "C0", "C1"):
        dry(c, tmp_path / c)
    fronts, stops = {}, {}
    for c in ("C0", "C1", "C2"):
        fronts[c], stops[c] = mjs.load_front(tmp_path / c / f"mh_archive_{c}.jsonl",
                                             tmp_path / c / f"mh_front_{c}.json")
    out = mjs.judge(fronts, stops)
    assert out["verdict"] in {f"V{i}" for i in range(1, 8)}
    if any("T4" in stops[c] for c in ("C1", "C2")):
        assert out["verdict"] == "V5"
