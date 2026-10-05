"""Search driver — one condition (C0 | C1 | C2), resume-safe, single writer.

Loop per round g (generation = g):
    plan (parent selection + proposer) → [validity pre-check → measure (165 calls)
    → mh_objectives.build_result → mh_front.cmd_add] → finalize (front / C0 accept)
    → termination.
Everything that decides is reused: dominance/CI/front/prune/T1–T4 = mh_front,
axes/CI = mh_objectives, measurement = mh_run_candidate.run_one, S3 = mh_pair_diagnose,
filter_strip material = mh_filter_candidates, edit = mh_propose.
Decisions not fixed by the design are in PARETO_META_HARNESS_IMPL_NOTES.md (D1…).

State (all append-only, all derivable again from the archive + these two logs):
    <archive>                       mh_archive_<COND>.jsonl    (U4: one file per condition)
    <front>                         mh_front_<COND>.json       (mh_front.cmd_front output)
    <state>/plans.jsonl             one line per round = the round's proposals, written
                                    BEFORE any measurement (origin_reason pre-committed)
    <state>/rounds.jsonl            one line per finished round (+ termination)
    <state>/<cid>_objectives.json, <cid>_harness.json

usage:
    python mh_search.py --condition C1 --dry-run [--root DIR]     # 0 LLM calls, temp archive
    python mh_search.py --condition C2                            # REAL — needs IC-1 PASS
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import random
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE / "scripts"))

import instrument_check_run as icr  # noqa: E402
import mh_filter_candidates as mfc  # noqa: E402
import mh_front as mf  # noqa: E402
import mh_objectives as mo  # noqa: E402
import mh_pair_diagnose as mpd  # noqa: E402
import mh_propose as mp  # noqa: E402
import phase3_build_prompts as p3  # noqa: E402
from mh_guard import ledger_lock  # noqa: E402

PARENT_SEED = 20260731          # F5 — C1 only (design §12.1)
CALLS_PER_CANDIDATE = 165       # 55 units × 3 runs (§6.4)
BUDGET = mf.CALL_BUDGET         # 1,650 per condition, c000 excluded (D2)
SLOTS_C0_C1 = 3                 # D5 — same count as C2's S1/S2/S3
ID_BASE = {"C0": 100, "C1": 200, "C2": 300}   # D1 — raw files mh_c<NNN>_run*.jsonl are global
LABELS = mpd.LABELS
CI_KEY = mf.CI_KEYS[mf.DEFAULT_CI]
DRY_AT = "dry-run"              # fixed timestamp → byte-identical dry-run archives (D-3)


# ── paths ───────────────────────────────────────────────────────────────────────
class P:
    def __init__(self, cond: str, root: Optional[Path]):
        self.cond = cond
        if root is None:                          # real run
            self.archive = GATE / f"scripts/mh_archive_{cond}.jsonl"
            self.front = GATE / f"scripts/mh_front_{cond}.json"
            self.state = GATE / f"scripts/mh_search_{cond}"
            self.raw = GATE / "scripts"
        else:
            self.archive = root / f"mh_archive_{cond}.jsonl"
            self.front = root / f"mh_front_{cond}.json"
            self.state = root / f"mh_search_{cond}"
            self.raw = root / "raw"
        self.plans = self.state / "plans.jsonl"
        self.rounds = self.state / "rounds.jsonl"
        self.state.mkdir(parents=True, exist_ok=True)
        self.raw.mkdir(parents=True, exist_ok=True)


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if p.exists() else []


def _append(p: Path, obj: dict) -> None:
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def _quiet(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a)
    return rc, buf.getvalue()


# ── measurement (injectable) ────────────────────────────────────────────────────
def real_measure(cid: str, harness: dict, cond: str, paths: P) -> list[str]:  # pragma: no cover
    import mh_run_candidate as mrc
    fn, kw, model = mrc.resolve_builder(harness)
    files = []
    for run in mrc.RUNS:
        mrc.run_one(cid, cond, run, fn, kw, model, harness["prompt_sha256"])
        f = GATE / f"scripts/mh_{cid}_{run}.jsonl"
        bad = sum(r.get("label") == "UNRESOLVED" for r in _jsonl(f))
        if bad > len(icr.load_units()) * mo.R4_MAX_UNRESOLVED:
            # ponytail: can't tell CLI/quota outage from model format failure here → stop, human decides
            raise SystemExit(f"HALT {cid}/{run}: {bad} UNRESOLVED rows — possible CLI/quota "
                             "outage; not scored. Inspect before resuming.")
        files.append(str(f))
    return files


def stub_measure(cid: str, harness: dict, cond: str, paths: P) -> list[str]:
    """Synthetic 3-run ledger, deterministic in (prompt_sha256, unit). 0 LLM calls.
    Same row schema as mh_run_candidate.run_one; resumes like it (done-set)."""
    sha = harness["prompt_sha256"]
    sp, ss = int(sha[:2], 16) % 61 - 30, int(sha[2:4], 16) % 31 - 15
    files = []
    for run in ("run1", "run2", "run3"):
        out = paths.raw / f"mh_{cid}_{run}.jsonl"
        done = {r["id"] for r in _jsonl(out)}
        with open(out, "a", encoding="utf-8") as fh:
            for u in icr.load_units():
                if u["id"] in done:
                    continue
                h = int(hashlib.sha256(f"{sha}:{u['id']}".encode()).hexdigest(), 16)
                flag = (h % 100) < (70 + sp if u["human"] in mo.HUMAN_PROBLEM else 18 + ss)
                if run == "run3" and h % 41 == 0:
                    flag = not flag                     # rare run disagreement
                fh.write(json.dumps({
                    "id": u["id"], "run": run,
                    "label": ("CONTRADICTED" if h % 2 else "INSUFFICIENT") if flag
                    else "SUPPORTED",
                    "rationale": f"stub {h % 9973}", "human": u["human"],
                    "candidate_id": cid, "condition": cond, "model": harness["model"],
                    "prompt_sha256": sha}, ensure_ascii=False) + "\n")
        files.append(str(out))
    return files


stub_measure.is_stub = True  # type: ignore[attr-defined]


def score(cid: str, files: list[str], paths: P) -> Path:
    labels = mo.load_labels(LABELS)
    per, names = mo.load_runs(files)
    mo.validate_run_ledger(per, labels, cid)
    res = mo.build_result(cid, mo.build_units(per, labels), per, names, mo.sha256_file(LABELS))
    out = paths.state / f"{cid}_objectives.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


# ── archive helpers (all writes go through mh_front) ────────────────────────────
def latest(paths: P) -> dict[str, dict]:
    return mf.load_archive(paths.archive)[1]


def spent(lat: dict[str, dict]) -> int:
    """Search calls used by this condition. c000 = IC-0 cost, shared → excluded (D2)."""
    return sum((r.get("reference_fields") or {}).get("search_cost_calls", 0)
               for i, r in lat.items() if i != mf.BASELINE_ID
               and r.get("status") != mf.STATUS_INVALID)


def baseline_harness() -> dict:
    u0 = icr.load_units()[0]
    return {"builder_module": "phase3_build_prompts", "builder_fn": "build",
            "builder_kwargs": {"with_siblings": True},
            "prompt_sha256": hashlib.sha256(p3.build(u0, with_siblings=True).encode()).hexdigest(),
            "model": p3.CLAUDE_MODEL, "diff_from_parent": "없음 (baseline)", "edited_surface": []}


def attach_baseline(paths: P, obj: dict, at: str, how: str) -> None:
    """c000 pre-registered UNJUDGED (mh_register_c000) → append measured snapshot.
    cmd_add refuses an existing id, so this is a status transition, not an add (D3)."""
    lat = latest(paths)
    rec = copy.deepcopy(lat[mf.BASELINE_ID])
    if rec.get("objectives"):
        return
    for k in ("measurement", "objectives", "reference_fields", "sample_gate", "bootstrap"):
        rec[k] = obj.get(k)
    mf.validate_add_structure(rec)
    mf.validate_axes(rec, CI_KEY)
    st = mf.STATUS_ON_FRONT if rec["sample_gate"]["passed"] else mf.STATUS_UNJUDGED
    mf.append_archive(mf._transition(rec, st, f"c000 측정 반영 — {how}", at), paths.archive)


def init_baseline(paths: P, measure: Callable, at: str, dry: bool) -> None:
    lat = latest(paths)
    if lat.get(mf.BASELINE_ID, {}).get("objectives"):
        return
    if dry:
        if mf.BASELINE_ID not in lat:
            h = baseline_harness()
            mf.append_archive({"candidate_id": "c000", "created_at": at, "parent_ids": [],
                               "generation": 0, "origin": "baseline",
                               "origin_reason": "dry-run baseline (stub-measured)",
                               "harness": h, "measurement": None, "objectives": None,
                               "reference_fields": {}, "sample_gate":
                               {"passed": False, "violations": ["미측정"]},
                               "status": mf.STATUS_UNJUDGED, "status_history": []},
                              paths.archive)
        obj = json.loads(score("c000", measure("c000", baseline_harness(), paths.cond, paths),
                               paths).read_text(encoding="utf-8"))
        attach_baseline(paths, obj, at, "dry-run stub")
        return
    # real: c000 measured once (IC-0 rerun, ADDENDUM2) in mh_archive_C2.jsonl; shared (§12.1)
    c2 = GATE / "scripts/mh_archive_C2.jsonl"
    if paths.cond == "C2":
        obj = json.loads((GATE / "scripts/mh_c000_objectives.json").read_text(encoding="utf-8"))
        attach_baseline(paths, obj, at, "mh_c000_objectives.json (IC-0 재실행, 부속서1 U8)")
    else:
        src = mf.load_archive(c2)[1].get(mf.BASELINE_ID)
        if not (src and src.get("objectives")):
            raise SystemExit("C2 must run first (prereg §5 order) — c000 not measured in C2 archive")
        # status reset: c000 may be DOMINATED/PRUNED in C2; in a fresh condition it is the front
        mf.append_archive(mf._transition(src, mf.STATUS_ON_FRONT, "copied from "
                                         "mh_archive_C2.jsonl (shared baseline, §12.1)", at),
                          paths.archive)


def add_candidate(paths: P, c: dict, objpath: Optional[Path], at: str) -> str:
    """Register via mh_front.cmd_add (all §5.2 gates). INVALID pre-check before any call."""
    if c["cid"] in latest(paths):
        return latest(paths)[c["cid"]]["status"]
    if objpath is None:
        rec = {"candidate_id": c["cid"], "created_at": at, "parent_ids": c["parents"],
               "generation": c["round"], "origin": c["origin"],
               "origin_reason": c["origin_reason"], "harness": c["harness"],
               "measurement": None, "objectives": None,
               "reference_fields": {"search_cost_calls": 0},
               "sample_gate": {"passed": False, "violations": ["미측정"]},
               "status": None, "status_history": []}
        _quiet(mf._reject_add, rec, paths.archive, at, "; ".join(c["invalid"]))
        return mf.STATUS_INVALID
    hp = paths.state / f"{c['cid']}_harness.json"
    hp.write_text(json.dumps(c["harness"], ensure_ascii=False, indent=1), encoding="utf-8")
    ns = argparse.Namespace(archive=str(paths.archive), ci=mf.DEFAULT_CI, computed_at=at,
                            objectives=str(objpath), harness=str(hp), candidate_id=c["cid"],
                            parents=c["parents"], generation=c["round"], origin=c["origin"],
                            origin_reason=c["origin_reason"], no_verify_builder=False)
    _quiet(mf.cmd_add, ns)
    return latest(paths)[c["cid"]]["status"]


def recompute_front(paths: P, at: str, status_write: bool = True) -> dict:
    if paths.front.exists():
        doc = json.loads(paths.front.read_text(encoding="utf-8"))
        if doc.get("archive_sha256") == mf.sha256_file(paths.archive):
            return doc                                    # idempotent on resume
    ns = argparse.Namespace(archive=str(paths.archive), out=str(paths.front), ci=mf.DEFAULT_CI,
                            computed_at=at, cap=mf.FRONT_CAP, dry_run=False,
                            no_status_write=not status_write)
    rc, out = _quiet(mf.cmd_front, ns)
    if rc != 0:
        raise SystemExit(f"mh_front front failed rc={rc}: {out}")
    return json.loads(paths.front.read_text(encoding="utf-8"))


# ── parent selection ────────────────────────────────────────────────────────────
def diag(rec: dict, paths: P, labels: dict) -> dict:
    t = mpd.unit_table(rec, paths.raw, labels)
    return {"misses": [u for u in sorted(t) if t[u]["human"] in mo.HUMAN_PROBLEM
                       and t[u]["maj"] not in mo.PROBLEM],
            "false_alarms": [u for u in sorted(t) if t[u]["human"] == "S"
                             and t[u]["maj"] in mo.PROBLEM],
            "splits": [u for u in sorted(t) if t[u]["maj"] == mo.SPLIT]}


def c0_active(lat: dict[str, dict]) -> dict:
    act = [r for r in lat.values() if r.get("status") == mf.STATUS_ON_FRONT]
    return sorted(act, key=lambda r: (r.get("generation", 0), r["candidate_id"]))[-1]


def c1_parents(front: list[str], rnd: int, k: int = SLOTS_C0_C1) -> list[str]:
    """Uniform draw with replacement; seeded per round → resume-safe & reproducible (D-3)."""
    rng = random.Random(f"{PARENT_SEED}:{rnd}")
    pool = sorted(front)
    return [rng.choice(pool) for _ in range(k)]


def c2_slots(front_doc: dict, lat: dict, paths: P, labels: dict,
             s3: bool = True, fs: bool = True) -> list[dict]:
    """Design §6.1/§6.2/§6.5. Priority order filter_strip > S1 > S2 > S3 (§6.5-3).
    s3/fs flags = ablations A-S3 / A-FS (driver CLI runs C0/C1/C2 only)."""
    front, ep = front_doc["front"], front_doc["endpoints"]
    a, b = ep["recall"], ep["precision"]
    slots: list[dict] = []
    if fs:
        tables = {c: mpd.unit_table(lat[c], paths.raw, labels) for c in front}
        m = mfc.material(front, lat, tables, CI_KEY)
        slots.append({"slot": "FS", "origin": "filter_strip", "mode": "delete_only",
                      "parents": [m["candidate"]], "context": m, "forbidden": []} if m else
                     {"slot": "FS", "empty": "§6.5-4 nothing to strip (recorded here; "
                                             "mh_front.json is written only by mh_front)"})
    slots.append({"slot": "S1", "origin": "front_endpoint", "mode": "edit", "parents": [a],
                  "context": {"slot": "S1", "goal": "keep recall, gain precision",
                              **diag(lat[a], paths, labels)}, "forbidden": []})
    if a == b:
        slots.append({"slot": "S2", "empty": "§6.1 A == B (front size 1): S2 → filter_strip, "
                                             "already run this round"})
    else:
        slots.append({"slot": "S2", "origin": "front_endpoint", "mode": "edit", "parents": [b],
                      "context": {"slot": "S2", "goal": "keep precision, gain recall",
                                  **diag(lat[b], paths, labels)}, "forbidden": []})
    if not s3:
        slots.append({"slot": "S3", "empty": "ablation A-S3"})
    elif a == b:
        slots.append({"slot": "S3", "empty": "A == B"})
    else:
        d = mpd.diagnose(lat[a], lat[b], mpd.unit_table(lat[a], paths.raw, labels),
                         mpd.unit_table(lat[b], paths.raw, labels))
        slots.append({"slot": "S3", "origin": "front_pair", "mode": "edit", "parents": [a, b],
                      "context": {"slot": "S3", **d}, "forbidden": d["forbidden_surfaces"]}
                     if d["target"] else
                     {"slot": "S3", "empty": "§6.2-4 BOTH_FAIL = 0 → filter_strip already run"})
    return slots


def plan_round(paths: P, rnd: int, caller: Callable, at: str) -> dict:
    lat = latest(paths)
    labels = mo.load_labels(LABELS)
    if paths.cond == "C2":
        slots = c2_slots(recompute_front(paths, at), lat, paths, labels)
    elif paths.cond == "C1":
        front = recompute_front(paths, at)["front"]
        slots = [{"slot": f"R{k + 1}", "origin": "random_parent", "mode": "edit", "parents": [p],
                  "context": {"slot": "random", "draw": k + 1, **diag(lat[p], paths, labels)}, "forbidden": []}
                 for k, p in enumerate(c1_parents(front, rnd))]
    else:
        act = c0_active(lat)
        slots = [{"slot": f"A{k + 1}", "origin": "active_harness", "mode": "edit",
                  "parents": [act["candidate_id"]],
                  "context": {"slot": "active", "variant": k + 1,
                              **diag(act, paths, labels)}, "forbidden": []}
                 for k in range(SLOTS_C0_C1)]
    room = (BUDGET - spent(lat)) // CALLS_PER_CANDIDATE
    n_ids = sum(1 for pl in _jsonl(paths.plans) for s in pl["slots"] if s.get("cid"))
    u0 = icr.load_units()[0]
    calls = 0
    for s in slots:
        if "empty" in s:
            continue
        if room <= 0:
            s["empty"] = "budget (§6.5-3 priority filter_strip > S1 > S2 > S3)"
            continue
        child, why = mp.propose([lat[p] for p in s["parents"]], context=s["context"],
                                mode=s["mode"], forbidden=set(s["forbidden"]), caller=caller)
        calls += 1
        if child is None:
            s["empty"] = why
            continue
        n_ids += 1
        s["cid"] = f"c{ID_BASE[paths.cond] + n_ids:03d}"
        s["harness"] = child["harness"]
        s["harness"]["prompt_sha256"] = mp.prompt_sha256(s["harness"], u0)
        s["origin_reason"] = child["origin_reason"]
        s["invalid"] = mf.validity_check(s["harness"], lat)
        if not s["invalid"]:
            room -= 1
        lat = {**lat, s["cid"]: {"harness": s["harness"], "status": mf.STATUS_ON_FRONT,
                                 "sample_gate": {"passed": True, "violations": []}}}
    plan = {"round": rnd, "condition": paths.cond, "proposer_calls": calls,
            "slots": [{k: v for k, v in s.items() if k != "context"} |
                      {"context_sha256": hashlib.sha256(json.dumps(
                          s.get("context"), sort_keys=True).encode()).hexdigest()}
                      for s in slots]}
    _append(paths.plans, plan)
    return plan


# ── round finalize + termination ────────────────────────────────────────────────
def c0_finalize(paths: P, rnd: int, at: str) -> None:
    """C0 acceptance (design §12.1, D13; no CI). Rejected → REJECTED_C0 (U3)."""
    lat = latest(paths)
    act = c0_active({i: r for i, r in lat.items() if r.get("generation", 0) < rnd})
    kids = [r for r in lat.values() if r.get("generation") == rnd
            and r["status"] not in (mf.STATUS_INVALID, mf.STATUS_UNJUDGED)
            and not any(h["by"].startswith("C0 ") for h in r["status_history"])]
    ok = []
    for r in sorted(kids, key=lambda r: r["candidate_id"]):
        dr = r["measurement"]["n_detected"] - act["measurement"]["n_detected"]
        dp = r["objectives"]["precision"]["value"] - act["objectives"]["precision"]["value"]
        acc = dr >= 0 and dp >= -mf.EPS and (dr > 0 or dp > mf.EPS)
        (ok if acc else []).append((dr, dp, r))
        if not acc:
            mf.append_archive(mf._transition(r, mf.STATUS_REJECTED_C0,
                                             f"C0 reject vs {act['candidate_id']}: "
                                             f"Δrecall_n={dr} Δprecision={dp:+.4f}", at),
                              paths.archive)
    if ok:   # D6 — no merge; several accepted → largest (Δn_detected, Δprecision), then id
        win = sorted(ok, key=lambda t: (-t[0], -t[1], t[2]["candidate_id"]))[0][2]
        for dr, dp, r in ok:
            st = mf.STATUS_ON_FRONT if r is win else mf.STATUS_DOMINATED
            mf.append_archive(mf._transition(
                r, st, f"C0 accept vs {act['candidate_id']}: Δrecall_n={dr} "
                       f"Δprecision={dp:+.4f}" + ("" if r is win else
                                                  f" — not activated ({win['candidate_id']})"),
                at), paths.archive)
        mf.append_archive(mf._transition(act, mf.STATUS_DOMINATED,
                                         f"C0 superseded by {win['candidate_id']}", at),
                          paths.archive)


def c0_stall(lat: dict[str, dict], rnd: int) -> int:
    """U12 — rounds since the active harness last changed, from status_history only."""
    acc = [r.get("generation", 0) for r in lat.values()
           if any(h["by"].startswith("C0 accept") and "not activated" not in h["by"]
                  for h in r.get("status_history") or [])]
    return rnd - max(acc, default=0)


def finalize(paths: P, plan: dict, at: str) -> dict:
    rnd = plan["round"]
    lat = latest(paths)
    kids = [lat[s["cid"]] for s in plan["slots"] if s.get("cid")]
    valid = [r for r in kids if r["status"] not in (mf.STATUS_INVALID, mf.STATUS_UNJUDGED)]
    stops: list[str] = []
    if paths.cond == "C0":
        c0_finalize(paths, rnd, at)
        lat = latest(paths)
        if c0_stall(lat, rnd) >= mf.STALL_LIMIT:
            stops.append("T1")
        term = {"stall_rounds": c0_stall(lat, rnd), "active": c0_active(lat)["candidate_id"]}
    else:
        doc = recompute_front(paths, at)
        term = doc["termination"]
        stops += [t for t in term["triggered"] if t != "T2"]
    if not valid and "T3" not in stops:
        stops.append("T3")           # also catches a round with 0 proposals (mh_front can't)
    if BUDGET - spent(latest(paths)) < CALLS_PER_CANDIDATE:
        stops.append("T2")
    row = {"round": rnd, "candidates": [r["candidate_id"] for r in kids],
           "statuses": {r["candidate_id"]: latest(paths)[r["candidate_id"]]["status"]
                        for r in kids},
           "spent_calls": spent(latest(paths)), "stops": sorted(set(stops)), "detail": term}
    _append(paths.rounds, row)
    return row


def run(cond: str, *, root: Optional[Path], caller: Callable, measure: Callable,
        dry: bool, log=print) -> dict:
    if dry and not (getattr(caller, "is_stub", False) and getattr(measure, "is_stub", False)):
        raise SystemExit("--dry-run requires stub caller AND stub measure (0 LLM calls)")
    paths = P(cond, root)
    at_fn = (lambda: DRY_AT) if dry else (
        lambda: datetime.now(mf.KST).isoformat(timespec="seconds"))
    with ledger_lock(paths.archive):
        init_baseline(paths, measure, at_fn(), dry)
        if cond != "C0":
            recompute_front(paths, at_fn())
        while True:
            rounds = _jsonl(paths.rounds)
            if rounds and rounds[-1]["stops"]:
                break
            rnd = len(rounds) + 1
            plan = next((p for p in _jsonl(paths.plans) if p["round"] == rnd), None)
            if plan is None:
                plan = plan_round(paths, rnd, caller, at_fn())
                if not dry:      # prereg §5: origin_reason committed BEFORE measurement
                    commit_plan(paths, rnd)
            for s in plan["slots"]:
                if not s.get("cid"):
                    continue
                if s["cid"] not in latest(paths):
                    objp = None if s["invalid"] else score(
                        s["cid"], measure(s["cid"], s["harness"], cond, paths), paths)
                    add_candidate(paths, {**s, "round": rnd}, objp, at_fn())
            row = finalize(paths, plan, at_fn())
            log(f"[{cond}] round {rnd}: {row['statuses']} spent={row['spent_calls']} "
                f"stops={row['stops']}")
        if cond == "C0":   # F_C0 = non-dominated set of c000 + accepted lineage (D7)
            doc = recompute_front(paths, at_fn(), status_write=False)
            doc["termination"]["triggered"] = _jsonl(paths.rounds)[-1]["stops"]
            paths.front.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
    final = json.loads(paths.front.read_text(encoding="utf-8"))
    return {"condition": cond, "rounds": len(_jsonl(paths.rounds)), "front": final["front"],
            "stops": _jsonl(paths.rounds)[-1]["stops"], "spent_calls": spent(latest(paths)),
            "archive": str(paths.archive), "front_json": str(paths.front)}


def commit_plan(paths: P, rnd: int) -> None:  # pragma: no cover — real run only
    import subprocess
    subprocess.run(["git", "add", str(paths.plans)], cwd=GATE, check=True)
    subprocess.run(["git", "commit", "-q", "-m", f"mh_search {paths.cond} round {rnd}: "
                    "proposals + origin_reason pre-committed before measurement",
                    "--", str(paths.plans)], cwd=GATE, check=True)


def preflight_real() -> None:  # pragma: no cover — real run only
    v = GATE / "scripts/mh_ic1_verdict.json"
    if not v.exists() or json.loads(v.read_text(encoding="utf-8")).get("verdict") != "PASS":
        raise SystemExit("ADDENDUM3: search runs only after IC-1 PASS (mh_ic1_verdict.json)")
    if mf.MODEL_FIXED != p3.CLAUDE_MODEL:
        raise SystemExit(f"mh_front.MODEL_FIXED={mf.MODEL_FIXED!r} != CLAUDE_MODEL="
                         f"{p3.CLAUDE_MODEL!r}: every candidate would be INVALID. Apply the "
                         "ADDENDUM2 one-line constant update first (IMPL_NOTES B1).")
    import mh_run_candidate as mrc
    mrc.guard()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", required=True, choices=sorted(ID_BASE))
    ap.add_argument("--dry-run", action="store_true", help="stub proposer + stub measure, "
                    "temp archive, 0 LLM calls")
    ap.add_argument("--root", default=None, help="dry-run directory (default: new temp dir)")
    a = ap.parse_args(argv)
    if a.dry_run:
        root = Path(a.root) if a.root else Path(tempfile.mkdtemp(prefix="mh_search_"))
        if mf.MODEL_FIXED != p3.CLAUDE_MODEL:
            print(f"WARNING (IMPL_NOTES B1): mh_front.MODEL_FIXED={mf.MODEL_FIXED!r} != "
                  f"{p3.CLAUDE_MODEL!r}; patched IN MEMORY for this dry-run only")
            mf.MODEL_FIXED = p3.CLAUDE_MODEL
        res = run(a.condition, root=root, caller=mp.stub_caller, measure=stub_measure, dry=True)
    else:  # pragma: no cover
        preflight_real()
        res = run(a.condition, root=None, caller=mp.claude_cli_caller, measure=real_measure,
                  dry=False)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
