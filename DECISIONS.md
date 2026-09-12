# Decisions

- [2026-09-12] Issue #1: do not auto-deduplicate the IC-1 strict ledger. Four duplicate keys have conflicting labels, so row selection would invent a result. Preserve raw rows, invalidate the verdict, and require a clean rerun.
- [2026-09-12] Issue #1: do not add a deterministic free-form answer-to-claims substring check. Substring matching rejects valid paraphrases and still cannot prove completeness. Expose `submitted_claims_only` / `not_checked` scope and keep `fully_verified=false`; require a structured producer contract before claiming full answer completeness.
- [2026-09-12] Issue #1: defer locator revision/URI fields while evidence is a repository-pinned frozen snapshot with a whole-file hash. Require revision identity when mutable or multi-revision evidence adapters are introduced.
