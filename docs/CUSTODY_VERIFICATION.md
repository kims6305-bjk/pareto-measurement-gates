# Chain of Custody candidate verification

This record covers the integrated public-repository candidate: the chain-of-custody reference implementation, the custody-gated Pareto bridge, and the multilingual skill index.

## Reproduction commands

Run from the repository root:

```sh
python3 -m pytest gate/tests -q -o addopts=""
python3 -m unittest discover -s skill-custody/tests -v
python3 -m unittest discover -s skill-pareto/tests -v
python3 gate/scripts/anonymize_check.py --selftest
python3 gate/scripts/anonymize_check.py
python3 -m py_compile skill-custody/scripts/chain_of_custody.py skill-pareto/scripts/pareto_custody_gate.py
git diff --check
```

The GitHub Actions workflow runs the same three test suites and the repository security gate on Ubuntu and Windows with Python 3.11 and 3.12. Changes under either new skill, the skill index, localized READMEs, docs, the existing gate, or the workflow trigger CI.

## Verified result

- Reflection-gate regression: 135 passed.
- Chain-of-custody unit/negative controls: 12 passed.
- Pareto/custody integration: 7 passed.
- Total executed tests: 154; failures: 0. This is an executed non-zero test set.
- Anonymize negative control: injected leak was blocked with exit 1.
- Full anonymize scan: 0 findings.
- Candidate path/content audit: 0 personal absolute paths, credential-shaped values, private-key material, or numeric messaging metadata in tracked and candidate text files or added diff lines.
- Root skill-index/README relative links: 84 checked, 0 missing.
- Python compilation and `git diff --check`: passed.

The negative controls independently cover normal PASS, canonical key-order equivalence, portable locator acceptance/rejection, credential and messaging-metadata redaction, event deletion, event reordering, previous-hash modification, one-byte artifact modification, and unknown-provider rehash bypass. The integration suite additionally verifies custody HALT before Pareto, unindexed-artifact HALT, all seven comparison-contract mismatch classes as INCOMPARABLE, and KEEP/TEST_THIN/REMOVE/NOT_MEASURED outcomes.

## Publication gate

This file records local candidate verification only. The downstream publication task must still verify the exact PR head across the complete GitHub Actions matrix before merge, and must verify the merged commit again before creating a tag or release.

## Known limitations

- The SHA-256 ledger is tamper-evident, not independently signed. If an attacker can rewrite both ledger and receipt, use an independently signed or WORM receipt.
- The repository anonymizer scans its declared public text extensions and intentionally excludes its own pattern dictionary. Binary semantic review remains a release-owner responsibility; the integrated candidate adds no non-text fixture or binary artifact.
- The Pareto bridge requires exactly two distinct metric judgment events per comparison and fails closed outside that contract.
