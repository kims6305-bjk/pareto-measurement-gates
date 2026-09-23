"""Custody-gated Pareto and harness-diet decisions (stdlib only).

The judgment layer records measured values against existing artifact digests. The
custody layer verifies those records and artifacts. Only then may this module
make a Pareto decision. It fails closed on every unverifiable or incomparable
input.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple


class CustodyInput(NamedTuple):
    ledger: Path
    receipt: Path
    root: Path
    artifact_id: str


def _load_custody():
    module_path = Path(__file__).resolve().parents[2] / "skill-custody" / "scripts" / "chain_of_custody.py"
    spec = importlib.util.spec_from_file_location("pareto_chain_of_custody", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load chain-of-custody verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


custody = _load_custody()


class ParetoInputError(ValueError):
    """A custody-valid input still cannot safely enter Pareto judgment."""


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ParetoInputError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ParetoInputError(f"{field} must be finite")
    return result


def _measurement_events(spec: CustodyInput) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    verification = custody.verify_ledger(spec.ledger, spec.receipt, spec.root)
    events = custody._load_jsonl(spec.ledger)
    matches: Dict[str, Dict[str, Any]] = {}

    for event in events:
        references = event.get("artifacts", [])
        if not any(reference.get("artifact_id") == spec.artifact_id for reference in references):
            continue
        if event.get("event_type") != "judgment" or "comparison" not in event:
            continue
        contract = custody.validate_comparison_contract(event["comparison"])
        metadata = event.get("metadata")
        if not isinstance(metadata, Mapping):
            raise ParetoInputError("judgment metadata must be an object")
        metric_name = contract["metric"]["name"]
        record = {
            "contract": contract,
            "value": _finite_number(metadata.get("measurement_value"), "measurement_value"),
            "reached_units": metadata.get("reached_units"),
            "event_hash": event["event_hash"],
        }
        reached = record["reached_units"]
        if isinstance(reached, bool) or not isinstance(reached, int) or reached < 0:
            raise ParetoInputError("reached_units must be a non-negative integer")
        if reached > contract["n_units"]:
            raise ParetoInputError("reached_units cannot exceed n_units")
        previous = matches.get(metric_name)
        if previous is not None and previous != record:
            raise ParetoInputError(f"ambiguous judgment records for metric {metric_name}")
        matches[metric_name] = record

    if not matches:
        raise ParetoInputError(
            f"artifact {spec.artifact_id!r} has no custody-verified judgment measurements"
        )
    if len(matches) != 2:
        raise ParetoInputError("Pareto input must contain exactly two distinct metrics")
    return verification, matches


def _shared_contract_fields(records: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    fields = (
        "cohort_id",
        "cohort_sha256",
        "n_units",
        "code_revision",
        "adapter",
        "provider",
        "model",
        "runtime",
    )
    contracts = [record["contract"] for record in records.values()]
    first = contracts[0]
    mismatches = [field for field in fields if any(contract[field] != first[field] for contract in contracts[1:])]
    if mismatches:
        raise custody.IncomparableError("INCOMPARABLE: cross-metric " + ", ".join(mismatches))
    return {field: first[field] for field in fields}


def _pareto_label(metric_rows: Sequence[Mapping[str, Any]]) -> Tuple[str, str]:
    if any(row["baseline_reached_units"] == 0 or row["candidate_reached_units"] == 0 for row in metric_rows):
        return "NOT_MEASURED", "at least one judgment reached zero target units"

    comparisons = [row["comparison"] for row in metric_rows]
    if all(value >= 0 for value in comparisons) and any(value > 0 for value in comparisons):
        return "KEEP", "candidate Pareto-dominates baseline"
    if all(value <= 0 for value in comparisons) and any(value < 0 for value in comparisons):
        return "REMOVE", "baseline Pareto-dominates candidate; removal still requires user approval"
    if all(value == 0 for value in comparisons):
        return "KEEP", "candidate ties baseline on both preregistered metrics"
    return "TEST_THIN", "candidate trades one preregistered metric against the other"


def decide(baseline: CustodyInput, candidate: CustodyInput) -> Dict[str, Any]:
    """Return a decision or an explicit fail-closed result with its reason."""
    try:
        baseline_verification, baseline_records = _measurement_events(baseline)
        candidate_verification, candidate_records = _measurement_events(candidate)
        if set(baseline_records) != set(candidate_records):
            raise custody.IncomparableError("INCOMPARABLE: metric names")
        _shared_contract_fields(baseline_records)
        _shared_contract_fields(candidate_records)

        rows: List[Dict[str, Any]] = []
        for name in sorted(baseline_records):
            left = baseline_records[name]
            right = candidate_records[name]
            custody.assert_comparable(left["contract"], right["contract"])
            direction = left["contract"]["metric"]["direction"]
            raw_delta = right["value"] - left["value"]
            comparison = raw_delta if direction == "maximize" else -raw_delta
            rows.append(
                {
                    "name": name,
                    "direction": direction,
                    "unit": left["contract"]["metric"]["unit"],
                    "baseline": left["value"],
                    "candidate": right["value"],
                    "delta": raw_delta,
                    "comparison": comparison,
                    "baseline_reached_units": left["reached_units"],
                    "candidate_reached_units": right["reached_units"],
                }
            )
        status, reason = _pareto_label(rows)
        return {
            "status": status,
            "reason": reason,
            "pipeline": "judgment -> custody evidence -> Pareto decision",
            "custody": {
                "baseline": baseline_verification,
                "candidate": candidate_verification,
            },
            "metrics": rows,
        }
    except custody.IncomparableError as exc:
        return {"status": "INCOMPARABLE", "reason": str(exc)}
    except (custody.CustodyError, ParetoInputError, OSError, json.JSONDecodeError) as exc:
        return {"status": "HALT", "reason": f"custody verification failed: {exc}"}


def _input_from_args(prefix: str, args: argparse.Namespace) -> CustodyInput:
    return CustodyInput(
        ledger=getattr(args, prefix + "_ledger"),
        receipt=getattr(args, prefix + "_receipt"),
        root=getattr(args, prefix + "_root"),
        artifact_id=getattr(args, prefix + "_artifact_id"),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Make a custody-gated Pareto decision")
    for prefix in ("baseline", "candidate"):
        parser.add_argument(f"--{prefix}-ledger", type=Path, required=True)
        parser.add_argument(f"--{prefix}-receipt", type=Path, required=True)
        parser.add_argument(f"--{prefix}-root", type=Path, required=True)
        parser.add_argument(f"--{prefix}-artifact-id", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    result = decide(_input_from_args("baseline", args), _input_from_args("candidate", args))
    print(custody.canonical_json(result))
    return 0 if result["status"] in {"KEEP", "TEST_THIN", "REMOVE", "NOT_MEASURED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
