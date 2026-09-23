from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pareto_custody_gate.py"
SPEC = importlib.util.spec_from_file_location("pareto_custody_gate", MODULE_PATH)
assert SPEC and SPEC.loader
pareto = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pareto)
custody = pareto.custody


class CustodyGatedParetoTests(unittest.TestCase):
    def contract(self, metric_name: str, direction: str, unit: str) -> dict:
        return {
            "cohort_id": "synthetic-cohort-v1",
            "cohort_sha256": "a" * 64,
            "n_units": 20,
            "metric": {"name": metric_name, "direction": direction, "unit": unit},
            "code_revision": "synthetic-evaluator-r1",
            "adapter": "rules-engine",
            "provider": "rules-engine",
            "model": "synthetic-judge-v1",
            "runtime": "fixture",
        }

    def make_side(
        self,
        base: Path,
        name: str,
        quality: float,
        cost: float,
        mutate_contract=None,
        reached_units: int = 20,
    ):
        root = base / name
        (root / "artifacts").mkdir(parents=True)
        artifact_id = f"{name}-result"
        artifact_path = root / "artifacts" / "result.json"
        artifact_path.write_text(json.dumps({"fixture": name}), encoding="utf-8")
        reference = custody.artifact_reference(root, "artifacts/result.json", artifact_id)
        ledger = root / "custody" / "events.jsonl"
        receipt = root / "custody" / "receipt.json"
        metrics = (
            ("quality", "maximize", "ratio", quality),
            ("cost", "minimize", "milliseconds", cost),
        )
        for index, (metric_name, direction, unit, value) in enumerate(metrics):
            contract = self.contract(metric_name, direction, unit)
            if mutate_contract is not None:
                mutate_contract(contract, metric_name)
            custody.append_event(
                ledger,
                receipt,
                root,
                {
                    "event_type": "judgment",
                    "timestamp": f"2026-01-01T00:00:0{index}Z",
                    "actor": {
                        "adapter": "rules-engine",
                        "provider": "rules-engine",
                        "principal_type": "rules",
                        "runtime": "fixture",
                    },
                    "artifacts": [reference],
                    "comparison": contract,
                    "metadata": {
                        "measurement_value": value,
                        "reached_units": reached_units,
                        "fixture": True,
                    },
                },
            )
        return pareto.CustodyInput(ledger, receipt, root, artifact_id)

    def test_normal_keep_flow_reaches_pareto_only_after_custody_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            baseline = self.make_side(base, "baseline", quality=0.80, cost=100.0)
            candidate = self.make_side(base, "candidate", quality=0.85, cost=90.0)
            result = pareto.decide(baseline, candidate)
        self.assertEqual("KEEP", result["status"])
        self.assertEqual("PASS", result["custody"]["baseline"]["status"])
        self.assertEqual("PASS", result["custody"]["candidate"]["status"])
        self.assertEqual("judgment -> custody evidence -> Pareto decision", result["pipeline"])
        self.assertEqual(2, len(result["metrics"]))

    def test_tradeoff_and_dominated_regression_labels(self) -> None:
        cases = (
            (0.85, 110.0, "TEST_THIN"),
            (0.75, 110.0, "REMOVE"),
            (0.80, 100.0, "KEEP"),
        )
        for quality, cost, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                baseline = self.make_side(base, "baseline", 0.80, 100.0)
                candidate = self.make_side(base, "candidate", quality, cost)
                self.assertEqual(expected, pareto.decide(baseline, candidate)["status"])

    def test_zero_reach_is_not_measured(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            baseline = self.make_side(base, "baseline", 0.80, 100.0)
            candidate = self.make_side(base, "candidate", 0.85, 90.0, reached_units=0)
            result = pareto.decide(baseline, candidate)
        self.assertEqual("NOT_MEASURED", result["status"])
        self.assertIn("zero target units", result["reason"])

    def test_every_contract_mismatch_is_incomparable(self) -> None:
        def set_field(field, value):
            return lambda contract, metric: contract.__setitem__(field, value)

        def metric_field(field, value):
            return lambda contract, metric: contract["metric"].__setitem__(field, value)

        cases = {
            "cohort": set_field("cohort_sha256", "b" * 64),
            "code": set_field("code_revision", "synthetic-evaluator-r2"),
            "model": set_field("model", "synthetic-judge-v2"),
            "provider": lambda contract, metric: contract.update(
                {"adapter": "openai", "provider": "openai"}
            ),
            "metric_name": lambda contract, metric: contract["metric"].__setitem__(
                "name", "latency" if metric == "cost" else metric
            ),
            "direction": metric_field("direction", "maximize"),
            "unit": metric_field("unit", "seconds"),
        }
        for label, mutation in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                baseline = self.make_side(base, "baseline", 0.80, 100.0)
                candidate = self.make_side(base, "candidate", 0.85, 90.0, mutation)
                result = pareto.decide(baseline, candidate)
                self.assertEqual("INCOMPARABLE", result["status"])
                self.assertIn("INCOMPARABLE", result["reason"])

    def test_tampered_ledger_halts_before_pareto(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            baseline = self.make_side(base, "baseline", 0.80, 100.0)
            candidate = self.make_side(base, "candidate", 0.85, 90.0)
            candidate.ledger.write_text(
                candidate.ledger.read_text(encoding="utf-8").replace("90.0", "91.0", 1),
                encoding="utf-8",
            )
            result = pareto.decide(baseline, candidate)
        self.assertEqual("HALT", result["status"])
        self.assertIn("custody verification failed", result["reason"])

    def test_unverified_artifact_id_halts_before_pareto(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            baseline = self.make_side(base, "baseline", 0.80, 100.0)
            candidate = self.make_side(base, "candidate", 0.85, 90.0)
            candidate = pareto.CustodyInput(
                candidate.ledger,
                candidate.receipt,
                candidate.root,
                "not-indexed",
            )
            result = pareto.decide(baseline, candidate)
        self.assertEqual("HALT", result["status"])
        self.assertIn("no custody-verified", result["reason"])

    def test_artifact_tamper_halts_before_pareto(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            baseline = self.make_side(base, "baseline", 0.80, 100.0)
            candidate = self.make_side(base, "candidate", 0.85, 90.0)
            artifact = candidate.root / "artifacts" / "result.json"
            artifact.write_bytes(artifact.read_bytes() + b"x")
            result = pareto.decide(baseline, candidate)
        self.assertEqual("HALT", result["status"])
        self.assertIn("artifact digest mismatch", result["reason"])


if __name__ == "__main__":
    unittest.main()
