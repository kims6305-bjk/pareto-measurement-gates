# Issue #1 external-review adjudication

Date: 2026-09-12
Source: GitHub issue #1 in this repository

External findings are treated as hypotheses. Each item below was reproduced against the current branch before modification.

## Accepted

### IC-1 raw-ledger integrity

- Expected key: `(candidate, run, id)`, exactly once for 55 IDs × 3 runs.
- `c_neg_loose`: 165 rows / 165 unique keys / 0 excess rows.
- `c_neg_strict`: 278 rows / 165 unique keys / **113 excess rows**.
  - run1: 63 rows / 8 excess / 0 conflicting keys
  - run2: 109 rows / 54 excess / 2 conflicting keys
  - run3: 106 rows / 51 excess / 2 conflicting keys
- The interleaved duplicate sequence is consistent with overlapping append/resume writers. The historical files do not contain process timestamps, so the exact launch event cannot be reconstructed.
- Fix: an atomic, cross-platform lock now excludes concurrent writers; the scorer rejects missing, unexpected, duplicate, conflicting, wrong-candidate, wrong-run, and invalid-label rows before computing an objective.
- Historical IC-1 scores are **invalidated, not deduplicated**. Four duplicate keys disagree on labels, so choosing a row would manufacture a result. A clean rerun is required.
- Actual historical row/call count was 608 (`c000` 165 + loose 165 + strict 278), not the planned 495.

### Evidence identity and integrity

- `EvidenceRecord` now rejects a `source_id` that differs from its locator and rejects a supplied `content_sha256` that differs from the excerpt.
- `EvidenceBundle` now rejects duplicate `source_id` values instead of silently keeping the last row in a dictionary.

### Verification-mode disclosure

- `GateResult` now exposes `checks_run`, `checks_skipped`, `verification_scope`, `answer_claim_completeness`, and `fully_verified`.
- Optional quote/semantic bypasses remain supported, but their result can no longer be mistaken for a full verification when the new scope fields are consumed.

### Derived hash and frozen metadata

- The stale `mh_front_C2.json.archive_sha256` was corrected and is now checked against the committed archive in CI.
- The writer-order bug had already been fixed in commit `61d37d2`; the new regression test also covers the committed artifact.
- `ab_questions_FROZEN.json` metadata now reports K-IFRS 1007 as 9, so the standards total is 119. Question content is unchanged. CI recomputes the distribution.

### Cross-platform byte stability

- `.gitattributes` pins `*.json` and `*.jsonl` to LF so byte-level SHA-256 assertions are stable on Windows checkouts.

## Deferred with explicit limits

### Free-form answer ↔ claims completeness

A deterministic `claim.text in answer` rule was not added. Existing claim decomposition intentionally permits paraphrase, so substring matching would create false failures while still missing paraphrased omissions. Instead, results explicitly report `verification_scope=submitted_claims_only` and `answer_claim_completeness=not_checked`; `fully_verified` remains false. Full completeness remains an upstream answer-generation/extraction contract limitation.

### Locator revision namespace

The current bundled evidence is a repository-pinned frozen snapshot whose whole-file SHA is asserted. A separate revision/URI field would not add independent integrity for this source. It becomes required when evidence can come from mutable external adapters or multiple standard revisions.

## Reproduction gates

```bash
python -m pytest gate/tests -q -o addopts=''
python gate/scripts/mh_ic1_negative_control.py --score  # exits 2 on the retained corrupt strict ledger
```

The retained corrupt ledger is intentional audit evidence. It must not be used for an objective or verdict.
