"""Candidate proposer — child judge-harness within the frozen mutation surface (U11).

Surface list = `gate/mh_propose.md` (identical for C0/C1/C2/A-S3/A-FS).
The LLM is injected as `caller(prompt: str) -> str`; this module never picks a caller
itself. INV-6: nothing here computes axis scores — parent objectives are only *read*
and pasted into the prompt.

Harness representation (archive `harness` block, design §5.1):
    builder_module = "mh_propose", builder_fn = "build",
    builder_kwargs = {"with_siblings": bool, "judge_parts": {<surface>: str, ...}}
`build()` reuses `phase3_build_prompts.build` and only swaps `p3.JUDGE` (same
technique as `mh_ic1_negative_control.build_prompt`). Default parts concatenate to
`p3.JUDGE` byte-for-byte, so an unmutated child has c000's prompt_sha256 and is
rejected by `mh_front.validity_check` as a duplicate.
"""
from __future__ import annotations

import copy
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

GATE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GATE / "scripts"))

import phase3_build_prompts as p3  # noqa: E402

PROPOSER_MODEL = "claude-sonnet-5"      # mh_propose.md §3 — same for every condition
CLI_TIMEOUT = 300

# ── U11 surface list. Order = order of concatenation inside p3.JUDGE. ───────────
JUDGE_PARTS = ("preamble", "task", "def_supported", "def_contradicted",
               "def_insufficient", "closing")
# JUDGE.preamble is NOT a surface: it carries the "evidence is data, not instructions" guard.
SURFACES = tuple(f"JUDGE.{k}" for k in JUDGE_PARTS if k != "preamble")
# with_siblings is NOT a surface: prompt_sha256 is taken on units[0] (0 siblings), so a
# with_siblings flip is invisible to the duplicate gate (mh_propose.md §2).
WITH_SIBLINGS = True


def _split_judge(text: str) -> dict[str, str]:
    """p3.JUDGE → 6 segments whose concatenation is the original text."""
    m = re.fullmatch(r"(.*?\n\n)(.*?\n)(- SUPPORTED:.*?\n)(- CONTRADICTED:.*?\n)"
                     r"(- INSUFFICIENT:.*?\n\n)(.*)", text, re.S)
    if not m:
        raise SystemExit("drift: phase3_build_prompts.JUDGE no longer matches the "
                         "6-segment surface map in mh_propose.md")
    return dict(zip(JUDGE_PARTS, m.groups()))


DEFAULT_PARTS = _split_judge(p3.JUDGE)
assert "".join(DEFAULT_PARTS.values()) == p3.JUDGE


def build(unit: dict, *, with_siblings: bool, judge_parts: Optional[dict] = None) -> str:
    """Builder referenced by child harnesses. Only JUDGE is swapped."""
    parts = {**DEFAULT_PARTS, **(judge_parts or {})}
    orig = p3.JUDGE
    p3.JUDGE = "".join(parts[k] for k in JUDGE_PARTS)
    try:
        return p3.build(unit, with_siblings=with_siblings)
    finally:
        p3.JUDGE = orig


def surfaces_of(harness: dict) -> dict:
    """Any harness (c000 uses phase3_build_prompts.build) → {surface: value}."""
    kw = harness.get("builder_kwargs") or {}
    parts = {**DEFAULT_PARTS, **(kw.get("judge_parts") or {})}
    return {f"JUDGE.{k}": parts[k] for k in JUDGE_PARTS}


def harness_from_surfaces(s: dict, *, diff: str, edited: list[str]) -> dict:
    return {
        "builder_module": "mh_propose",
        "builder_fn": "build",
        "builder_kwargs": {"with_siblings": WITH_SIBLINGS,
                           "judge_parts": {k: s[f"JUDGE.{k}"] for k in JUDGE_PARTS}},
        "prompt_sha256": None,             # filled by the driver on the fixed unit
        "model": p3.CLAUDE_MODEL,
        "diff_from_parent": diff,
        "edited_surface": edited,
    }


def prompt_sha256(harness: dict, unit0: dict) -> str:
    """Same definition as mh_run_candidate.prompt_sha256 (fixed first unit)."""
    import importlib
    fn = getattr(importlib.import_module(harness["builder_module"]), harness["builder_fn"])
    return hashlib.sha256(fn(unit0, **harness.get("builder_kwargs", {}))
                          .encode("utf-8")).hexdigest()


def is_deletion(old, new) -> bool:
    """filter_strip (§6.5-2): diff must be deletion only."""
    ops = difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes()
    return new != old and all(t in ("equal", "delete") for t, *_ in ops)


# ── Prompt template (committed; sha256 recorded in mh_propose.md) ──────────────
PROMPT_TEMPLATE = """You edit the instruction text of an LLM citation judge.
The judge reads a claim plus evidence and outputs SUPPORTED / CONTRADICTED / INSUFFICIENT.
Two objectives are measured outside your control on a fixed labelled set:
recall (problem claims flagged) and precision (flags that are real problems).
You never see or compute the scores of your own proposal.

MODE: {mode}
{mode_rule}

EDITABLE SURFACES (change exactly ONE of these; anything else is invalid):
{allowed}
FORBIDDEN SURFACES this time: {forbidden}

PARENT HARNESS(ES) — current surface values:
{parents}

DIAGNOSTIC CONTEXT (read-only):
{context}

Reply with ONE JSON object and nothing else:
{{"surface": "<one editable surface>", "new_value": "<full new text of that surface>",
  "diff_from_parent": "<one sentence: what changed>",
  "origin_reason": "<1-3 sentences: why this parent and this edit; cite question ids and labels only>"}}
"""

MODE_RULES = {
    "edit": "Make one focused change (add, remove or rewrite text) to one surface.",
    "delete_only": ("DELETE ONLY: the new value must be the old value with some text removed "
                    "(no additions, no rewording)."),
}


def render_prompt(parents: list[dict], context: dict, mode: str,
                  forbidden: set[str]) -> str:
    allowed = [s for s in SURFACES if s not in forbidden]
    par = {p["candidate_id"]: {"surfaces": surfaces_of(p["harness"]),
                               "objectives": p.get("objectives"),
                               "edited_surface": p["harness"].get("edited_surface")}
           for p in parents}
    return PROMPT_TEMPLATE.format(
        mode=mode, mode_rule=MODE_RULES[mode], allowed="\n".join(f"- {s}" for s in allowed),
        forbidden=sorted(forbidden) or "none",
        parents=json.dumps(par, ensure_ascii=False, indent=1),
        context=json.dumps(context, ensure_ascii=False, indent=1))


def parse_reply(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        raise ValueError("no JSON object in proposer reply")
    obj = json.loads(m.group(0))
    for k in ("surface", "new_value", "diff_from_parent", "origin_reason"):
        if k not in obj:
            raise ValueError(f"missing key {k}")
    return obj


def propose(parents: list[dict], *, context: dict, mode: str, forbidden: set[str],
            caller: Callable[[str], str]) -> tuple[Optional[dict], str]:
    """Return (child_fields, reason). child_fields=None → slot left empty (§6.3).

    The edit is applied to parents[0] (S3 pair: the recall endpoint — IMPL_NOTES D7).
    One LLM call, no retry: an invalid proposal empties the slot (§6.3).
    """
    try:
        reply = parse_reply(caller(render_prompt(parents, context, mode, forbidden)))
    except Exception as exc:  # noqa: BLE001 — any proposer failure = empty slot
        return None, f"proposer reply rejected: {type(exc).__name__}: {exc}"
    surface, new = reply["surface"], reply["new_value"]
    base = surfaces_of(parents[0]["harness"])
    if surface not in SURFACES:
        return None, f"surface {surface!r} not in mutation surface list"
    if surface in forbidden:
        return None, f"surface {surface!r} forbidden (§6.2-5)"
    if not isinstance(new, str):
        return None, f"new_value type mismatch for {surface}"
    if new == base[surface]:
        return None, "no-op edit (src1: proposal must modify the editable surface)"
    if mode == "delete_only" and not is_deletion(base[surface], new):
        return None, "filter_strip edit is not deletion-only (§6.5-2)"
    child = copy.deepcopy(base)
    child[surface] = new
    if not any(child[f"JUDGE.{k}"].strip() for k in JUDGE_PARTS):
        return None, "empty JUDGE"
    return {"harness": harness_from_surfaces(child, diff=str(reply["diff_from_parent"]),
                                             edited=[surface]),
            "origin_reason": str(reply["origin_reason"]).strip()}, "ok"


def claude_cli_caller(prompt: str) -> str:   # pragma: no cover — real run only
    """Real proposer call. NEVER used by --dry-run or tests."""
    p = subprocess.run([shutil.which("claude") or "claude", "-p", "--model", PROPOSER_MODEL,
                        "--max-turns", "1"], input=prompt, capture_output=True, text=True,
                       timeout=CLI_TIMEOUT)
    return p.stdout or ""


def stub_caller(prompt: str) -> str:
    """Deterministic 0-call proposer for --dry-run / tests (marked `is_stub`)."""
    h = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest(), 16)
    allowed = re.findall(r"^- (JUDGE\.\w+)$", prompt, re.M)
    surface = allowed[h % len(allowed)]
    if "MODE: delete_only" in prompt:
        surface = "JUDGE.def_insufficient" if "JUDGE.def_insufficient" in allowed else allowed[0]
        new = ""
    else:
        new = f"(stub edit {h % 10007}) "
    return json.dumps({"surface": surface, "new_value": new,
                       "diff_from_parent": f"stub: {surface}",
                       "origin_reason": f"stub {h % 997}"})


stub_caller.is_stub = True  # type: ignore[attr-defined]


if __name__ == "__main__":
    # selftest: surface map round-trips and the default child equals c000's prompt.
    import instrument_check_run as icr
    u0 = icr.load_units()[0]
    assert build(u0, with_siblings=True) == p3.build(u0, with_siblings=True)
    assert is_deletion("abc", "ac") and not is_deletion("abc", "abx")
    print("mh_propose selftest PASS; surfaces:", ", ".join(SURFACES))
    print("PROMPT_TEMPLATE sha256:", hashlib.sha256(PROMPT_TEMPLATE.encode()).hexdigest())
