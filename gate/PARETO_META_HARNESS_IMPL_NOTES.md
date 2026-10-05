# Pareto meta-harness — implementation notes

Scope: ADDENDUM3 §4 "must exist before the first search call". Written 2026-10-06 while the
IC-1 rerun (ADDENDUM2) was still measuring; **0 search calls, 0 LLM calls** were made to build
or test any of this. Nothing in prereg §7's frozen list was changed (`mh_front.py`,
`mh_objectives.py` untouched).

| file | role |
|---|---|
| `scripts/mh_propose.py` + `mh_propose.md` | proposer (injectable LLM caller) + U11 surface list |
| `scripts/mh_pair_diagnose.py` | C2 S3 pair diagnosis (§6.2), 0 calls |
| `scripts/mh_filter_candidates.py` | C2 filter_strip material (§6.5-1), 0 calls |
| `scripts/mh_search.py` | driver `--condition C0|C1|C2 [--dry-run]`, parent selection for all conditions, C0 accept rule, budget, resume, lock |
| `scripts/mh_judge_sets.py` | U9 set-dominance auto-judge V1–V7 + ADDENDUM3 C13 |
| `tests/test_mh_search.py` | D-3, D-4, resume, budget, 0-LLM, V1–V7 |

## Decisions made before any search call

Where the design was ambiguous the conservative option was taken.

**Open items**

- **U3 `REJECTED_C0`**: the constant already exists in `mh_front.py` and is excluded by
  `judgeable()`. The driver appends a `REJECTED_C0` status transition (new line, nothing deleted)
  for every measured C0 child that fails the acceptance rule.
- **U4 per-condition ledgers**: `mh_archive_<COND>.jsonl` / `mh_front_<COND>.json` /
  `mh_search_<COND>/` (plans, rounds, objectives). Passed to `mh_front` through `--archive`;
  `mh_front.py` is not changed. See D1 for the id ranges.
- **U5 R4 denominator**: the current fail-closed convention stays as is (larger of the
  unit-based and the raw run-based UNRESOLVED ratio). Stricter of the two, so it is the conservative choice.
- **U6 zero-denominator bootstrap resamples**: the current convention stays as is (excluded on
  that axis only, `n_valid_resamples` recorded per axis). U5/U6 are adopted unchanged, so no
  `mh_objectives.py` change is needed. ⚠️ The operator should ratify this in the
  first-measurement commit, as ADDENDUM3 §4 requires.
- **U9**: `mh_judge_sets.py`. covers/dominates reuse `mh_front.dominates`/`cmp_axis` with
  `ci_qid`. Precedence V6 > V5 > V4 > V1 > V2 > V7 > V3. V5 only looks at T4 in C1/C2, because C0
  has no T4 (§12.1). Outcomes the §14.2 table does not name (for example C2 neither covers nor is
  covered) map to V3 with `table_gap=true`, which means the claim is not supported. C13
  (ADDENDUM3 §2) is computed from C2 vs C1 only: supported / rejected / opposite direction /
  undecidable (T3/T4) / not run (IC-1 FAIL).
- **U11**: `mh_propose.md`. Five JUDGE segments are editable. `JUDGE.preamble`, `SYSTEM_GUARD`
  and `CONTRACT` are not (security / measurement boundary). `with_siblings` is not either, because
  the identity hash cannot see it.
- **U12 C0 stall**: `c0_stall()` is computed only from `status_history`: the number of rounds
  since the last "C0 accept" that activated a harness. T1 for C0 means stall ≥ 3. T4 is not
  applied to C0.

**Driver decisions**

- **D1 candidate ids**: `mh_run_candidate.run_one` writes `scripts/mh_<cid>_<run>.jsonl` for every
  condition, so ids are split by condition to avoid raw-file collisions: C0 `c101…`,
  C1 `c201…`, C2 `c301…` (`c%03d` keeps `validate_record` happy). Each budget allows at most 10.
- **D2 budget**: 1,650 judge calls per condition, **c000 excluded**, because c000 is the IC-0
  cost and is measured once and shared (§12.1, ADDENDUM2). A slot is planned only if
  `spent + 165 ≤ 1650`. INVALID children cost 0 because they are rejected before measurement.
  Proposer calls are **not** in the 1,650. They are recorded per round in `plans.jsonl`
  (`proposer_calls`). `mh_front`'s own T2 counts c000 too and therefore fires at the same point.
- **D3 baseline**: `cmd_add` refuses an existing id, and c000 is pre-registered as UNJUDGED by
  `mh_register_c000.py`. The measured c000 is therefore attached as a status-transition
  snapshot built from `mh_c000_objectives.json` (C2), using the same structural and axis
  validators as `cmd_add`. C0 and C1 copy that row from `mh_archive_C2.jsonl` (C2 runs first,
  prereg §5 order), so baseline values are identical across conditions.
- **D4 resume / single writer**: `ledger_lock(<archive>)` (O_EXCL, the same helper as IC-1)
  allows one writer per condition. A round's proposals, including `origin_reason` and
  `prompt_sha256`, are appended to `plans.jsonl` **before** any measurement. A restart re-measures
  missing raw rows (the `run_one` done-set), skips already-added ids, and re-finalizes the round
  idempotently (front recompute is skipped when `archive_sha256` already matches). Tested.
- **D5 candidates per round**: C2 runs FS + S1 + S2 + S3 (≤ 4, §6.5-3). C0 and C1 run **3**,
  the same as C2's S1/S2/S3, so round counts and therefore T1 timing stay comparable.
- **D6 C0 several accepted in one round**: there is no merge (§12.1). The new active harness is
  the accepted child with the largest (Δn_detected, Δprecision), then the lowest id. The other
  accepted children are logged "C0 accept … not activated" with status DOMINATED.
  Acceptance compares against the active harness at round start, uses point estimates only and
  no CI: `Δn_det ≥ 0 ∧ Δprec ≥ −EPS ∧ (Δn_det > 0 ∨ Δprec > EPS)`. UNJUDGED and INVALID are never accepted.
- **D7 F_C0** (for the set judge): `mh_front.cmd_front --no-status-write` over the C0 archive at
  stop. That is the non-dominated set of c000 plus the accepted lineage (rejected children are
  excluded by `judgeable`). It is a superset of {h_T}, which makes it harder for C2 to dominate
  (conservative).
- **D8 S2/S3 → filter_strip** (§6.1, §6.2-4): filter_strip already runs at the start of every
  C2 round, so a replacement means the slot is empty and the reason is logged. No second
  filter_strip child is made in the same round.
- **D9 origins**: C0 `active_harness`, C1 `random_parent`. `mh_front add`'s argparse `choices`
  list only C2 origins, so the driver calls `mh_front.cmd_add` with a Namespace. This reuses the
  same gates and avoids editing a frozen file.
- **D10 termination**: C1/C2 use `mh_front.termination` (T1/T3/T4). The driver adds T2 (D2) and
  T3 for a round in which no child is valid, including a round with 0 proposals that
  `mh_front` cannot see.
- **D11 S3 edit target**: the edit is applied to A (the recall endpoint). B is only context.
- **D12 "agrees with human"** (S3 quadrants): majority ∉ {SPLIT, UNRESOLVED} and
  (human ∈ {C,I}) == (majority ∈ PROBLEM). This is the same binary the axes use.
- **D13 filter_strip material**: priority is a (SPLIT) > b (false alarms) > c (a child whose JUDGE
  text grew vs its single parent without improving any axis, measured with `cmp_axis` under
  ci_qid). JUDGE length stands in for `prompt_chars`, because that field is not recorded by the
  runner. Inside a level the candidate with the most items wins, then the lowest id.
- **D14 C1 draws**: uniform, with replacement, 3 per round from the sorted front.
  `random.Random(f"{PARENT_SEED}:{round}")` is used, so the result is reproducible and
  resume-safe without stored RNG state (D-3).

## Known blockers / limits (not fixed here)

- **B1 `mh_front.MODEL_FIXED = "claude-sonnet-4-6"`** while ADDENDUM2 switched the judge to
  `claude-sonnet-5`. `validity_check` would mark **every** search candidate INVALID. The real
  run refuses to start (`preflight_real`), and dry-run/tests patch it **in memory only**. Fix: a
  one-line constant update that ADDENDUM2 already declares (INV-3 explicit amendment). It was
  deliberately not done here because a live IC-1 process imports `mh_front` and §7 freezes it.
  Commit it after IC-1 finishes.
- **B2** design §6.5-4 asks for the "nothing to strip" fact to be written into `mh_front.json`.
  Only `mh_front` writes that file, so the fact is recorded in `plans.jsonl` (slot FS `empty`).
- **B3** A-S3 / A-FS are flags of `c2_slots(s3=, fs=)`, but `mh_run_candidate.CONDITIONS` has only
  C0/C1/C2, so the ablations are not runnable from the CLI yet. They are P5/P6, after the cutline.
- **B4** `real_measure`/`claude_cli_caller` are untested by design (0 LLM calls). The real path
  also requires `mh_ic1_verdict.json` = PASS and `mh_guard` to pass.
- ponytail: one global lock per condition archive. Concurrent conditions use separate files.
