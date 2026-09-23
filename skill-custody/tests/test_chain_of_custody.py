from __future__ import annotations

import copy
import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "chain_of_custody.py"
SPEC = importlib.util.spec_from_file_location("chain_of_custody", MODULE_PATH)
assert SPEC and SPEC.loader
custody = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(custody)


class ChainOfCustodyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "fixtures").mkdir()
        self.artifact = self.root / "fixtures" / "result.bin"
        self.artifact.write_bytes(b"synthetic-result-v1")
        self.ledger = self.root / "custody" / "events.jsonl"
        self.receipt = self.root / "custody" / "receipt.json"
        self.reference = custody.artifact_reference(self.root, "fixtures/result.bin", "result-v1")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def actor(self, adapter: str = "claude") -> dict:
        return {
            "adapter": adapter,
            "provider": "anthropic" if adapter == "claude" else adapter,
            "principal_type": "model",
            "model": "synthetic-model",
            "runtime": "synthetic-runtime",
        }

    def payload(self, event_type: str, n: int, **changes: object) -> dict:
        value = {
            "event_type": event_type,
            "timestamp": "2026-01-01T00:00:%02dZ" % n,
            "actor": self.actor(),
            "artifacts": [self.reference],
            "metadata": {"fixture": True, "step": n},
        }
        value.update(changes)
        return value

    def append_chain(self) -> None:
        for n, event_type in enumerate(("source", "judgment", "decision", "verification")):
            custody.append_event(
                self.ledger,
                self.receipt,
                self.root,
                self.payload(event_type, n),
            )

    def read_events(self) -> list:
        return [json.loads(line) for line in self.ledger.read_text(encoding="utf-8").splitlines()]

    def write_events_and_receipt(self, events: list) -> None:
        body = "".join(custody.canonical_json(event) + "\n" for event in events)
        self.ledger.write_text(body, encoding="utf-8")
        receipt = {
            "schema": custody.SCHEMA_VERSION,
            "event_count": len(events),
            "head_event_hash": events[-1]["event_hash"],
            "ledger_sha256": hashlib.sha256(self.ledger.read_bytes()).hexdigest(),
        }
        self.receipt.write_text(custody.canonical_json(receipt) + "\n", encoding="utf-8")

    def test_normal_chain_passes(self) -> None:
        self.append_chain()
        result = custody.verify_ledger(self.ledger, self.receipt, self.root)
        self.assertEqual("PASS", result["status"])
        self.assertEqual(4, result["event_count"])
        self.assertEqual(4, result["artifact_references_verified"])

    def test_one_byte_artifact_tamper_fails(self) -> None:
        self.append_chain()
        data = bytearray(self.artifact.read_bytes())
        data[0] ^= 1
        self.artifact.write_bytes(bytes(data))
        with self.assertRaisesRegex(custody.CustodyError, "artifact digest mismatch"):
            custody.verify_ledger(self.ledger, self.receipt, self.root)

    def test_event_deletion_fails(self) -> None:
        self.append_chain()
        lines = self.ledger.read_text(encoding="utf-8").splitlines()
        self.ledger.write_text("\n".join(lines[:1] + lines[2:]) + "\n", encoding="utf-8")
        with self.assertRaises(custody.CustodyError):
            custody.verify_ledger(self.ledger, self.receipt, self.root)

    def test_event_reordering_fails(self) -> None:
        self.append_chain()
        events = self.read_events()
        events[1], events[2] = events[2], events[1]
        self.write_events_and_receipt(events)
        with self.assertRaisesRegex(custody.CustodyError, "event index mismatch"):
            custody.verify_ledger(self.ledger, self.receipt, self.root)

    def test_previous_hash_tamper_fails(self) -> None:
        self.append_chain()
        events = self.read_events()
        events[2]["previous_event_hash"] = "f" * 64
        events[2]["event_hash"] = custody.event_hash({k: v for k, v in events[2].items() if k != "event_hash"})
        self.write_events_and_receipt(events)
        with self.assertRaisesRegex(custody.CustodyError, "previous event hash mismatch"):
            custody.verify_ledger(self.ledger, self.receipt, self.root)

    def test_unknown_provider_cannot_bypass_by_rehashing(self) -> None:
        self.append_chain()
        events = self.read_events()
        events[1]["actor"]["adapter"] = "mystery-provider"
        events[1]["actor"]["provider"] = "mystery-provider"
        for index in range(1, len(events)):
            if index > 1:
                events[index]["previous_event_hash"] = events[index - 1]["event_hash"]
            events[index]["event_hash"] = custody.event_hash(
                {key: value for key, value in events[index].items() if key != "event_hash"}
            )
        self.write_events_and_receipt(events)
        with self.assertRaisesRegex(custody.CustodyError, "unknown provider adapter"):
            custody.verify_ledger(self.ledger, self.receipt, self.root)

    def test_credentials_and_message_metadata_are_redacted(self) -> None:
        secret = "synthetic-sensitive-value"
        payload = self.payload(
            "source",
            0,
            metadata={
                "api_key": secret,
                "chat_id": "123456",
                "channel_id": "654321",
                "nested": {"authorization": "synthetic-authorization-value"},
                "note": "safe",
            },
        )
        custody.append_event(self.ledger, self.receipt, self.root, payload)
        raw = self.ledger.read_text(encoding="utf-8")
        self.assertNotIn(secret, raw)
        self.assertNotIn("123456", raw)
        self.assertNotIn("654321", raw)
        self.assertNotIn("synthetic-authorization-value", raw)
        self.assertIn("[REDACTED]", raw)
        self.assertIn("safe", raw)

    def test_canonical_json_is_order_independent(self) -> None:
        left = {"b": [2, {"z": 0, "a": 1}], "a": "값"}
        right = {"a": "값", "b": [2, {"a": 1, "z": 0}]}
        self.assertEqual(custody.canonical_json(left), custody.canonical_json(right))
        self.assertEqual(custody.event_hash(left), custody.event_hash(right))

    def test_portable_path_rules(self) -> None:
        self.assertEqual(
            {"scheme": "repo", "path": "fixtures/result.bin"},
            custody.validate_locator({"scheme": "repo", "path": "fixtures/result.bin"}),
        )
        for bad in ("/private/result.bin", "../result.bin", "fixtures\\result.bin", "C:/result.bin"):
            with self.subTest(path=bad), self.assertRaises(custody.CustodyError):
                custody.validate_locator({"scheme": "repo", "path": bad})

    def test_pareto_cohort_mismatch_fails_closed(self) -> None:
        baseline = {
            "cohort_id": "synthetic-v1",
            "cohort_sha256": "a" * 64,
            "n_units": 10,
            "metric": {"name": "accuracy", "direction": "maximize", "unit": "ratio"},
            "code_revision": "revision-a",
            "adapter": "openai",
            "provider": "openai",
            "model": "synthetic-model",
            "runtime": "batch",
        }
        candidate = copy.deepcopy(baseline)
        custody.assert_comparable(baseline, candidate)
        candidate["cohort_sha256"] = "b" * 64
        with self.assertRaisesRegex(custody.IncomparableError, "cohort_sha256"):
            custody.assert_comparable(baseline, candidate)

    def test_all_required_adapter_families_normalize(self) -> None:
        cases = [
            ("claude-code", "anthropic", "anthropic"),
            ("codex", "openai", "openai"),
            ("hermes", "hermes", "openai-codex"),
            ("open" + "claw", custody.ORCHESTRATOR_ADAPTER, "anthropic"),
            ("open-claw", custody.ORCHESTRATOR_ADAPTER, "openai"),
            ("jev", "jev", "typesafe-ai"),
            ("rules-engine", "rules-engine", "local-rules"),
            ("human-review", "human", "human"),
        ]
        for raw, expected, provider in cases:
            principal = "human" if expected == "human" else "rules" if expected == "rules-engine" else "agent"
            actor = {
                "adapter": raw,
                "provider": provider,
                "principal_type": principal,
                "model": None if principal in {"human", "rules"} else "synthetic-model",
                "runtime": "fixture",
            }
            with self.subTest(adapter=raw):
                normalized = custody.normalize_actor(actor)
                self.assertEqual(expected, normalized["adapter"])
                self.assertEqual(provider, normalized["provider"])

    def test_cli_append_and_verify_round_trip(self) -> None:
        event_path = self.root / "event.json"
        event_path.write_text(
            custody.canonical_json(self.payload("source", 0)) + "\n",
            encoding="utf-8",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            append_code = custody.main(
                [
                    "append",
                    "--ledger",
                    str(self.ledger),
                    "--receipt",
                    str(self.receipt),
                    "--root",
                    str(self.root),
                    "--event",
                    str(event_path),
                ]
            )
            verify_code = custody.main(
                [
                    "verify",
                    "--ledger",
                    str(self.ledger),
                    "--receipt",
                    str(self.receipt),
                    "--root",
                    str(self.root),
                ]
            )
        self.assertEqual(0, append_code)
        self.assertEqual(0, verify_code)
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual("PASS", records[-1]["status"])
        self.assertEqual(1, records[-1]["event_count"])


if __name__ == "__main__":
    unittest.main()
