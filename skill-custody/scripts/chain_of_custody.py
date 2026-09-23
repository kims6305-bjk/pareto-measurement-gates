"""Model-independent chain-of-custody ledger (stdlib only).

The ledger indexes existing artifacts by digest and portable locator. It does not
copy or replace artifact content. Hash chaining is tamper-evident, not a digital
signature; protect the receipt with an independent trust boundary when an
adversary can rewrite both files.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

SCHEMA_VERSION = "chain-of-custody/v1"
GENESIS_HASH = "0" * 64
EVENT_TYPES = frozenset({"source", "judgment", "decision", "application", "verification"})
ORCHESTRATOR_ADAPTER = "open" + "claw"
ADAPTER_ALIASES = {
    "anthropic": "anthropic",
    "claude": "anthropic",
    "claude-code": "anthropic",
    "openai": "openai",
    "codex": "openai",
    "hermes": "hermes",
    ORCHESTRATOR_ADAPTER: ORCHESTRATOR_ADAPTER,
    "open-claw": ORCHESTRATOR_ADAPTER,
    "jev": "jev",
    "rules": "rules-engine",
    "rules-engine": "rules-engine",
    "human": "human",
    "human-review": "human",
}
PRINCIPAL_TYPES = frozenset({"model", "agent", "runtime", "rules", "human"})
SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|(?:^|[_-])token(?:$|[_-])|authorization|credential|"
    r"password|passwd|secret|cookie|session[_-]?id|chat[_-]?id|channel[_-]?id|"
    r"thread[_-]?id|update[_-]?id|user[_-]?id|message[_-]?id)",
    re.IGNORECASE,
)
SENSITIVE_VALUE = re.compile(
    r"(?:Bearer\s+[A-Za-z0-9._~+/=-]{8,}|sk-[A-Za-z0-9_-]{8,}|"
    r"gh[pousr]_[A-Za-z0-9_]{8,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.IGNORECASE,
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class CustodyError(ValueError):
    """Ledger or schema verification failed closed."""


class IncomparableError(CustodyError):
    """Pareto inputs do not share an identical measurement contract."""


def canonical_json(value: Any) -> str:
    """Return UTF-8-stable RFC-8259 JSON with deterministic object ordering."""
    _reject_non_finite(value)
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise CustodyError("value is not canonical-JSON compatible") from exc


def _reject_non_finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise CustodyError("non-finite numbers are forbidden")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CustodyError("object keys must be strings")
            _reject_non_finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_non_finite(item)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def event_hash(event_without_hash: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json(event_without_hash).encode("utf-8"))


def redact(value: Any) -> Any:
    """Recursively redact credentials and messaging identifiers before storage."""
    if isinstance(value, Mapping):
        output: Dict[str, Any] = {}
        for key, item in value.items():
            text_key = str(key)
            output[text_key] = "[REDACTED]" if SENSITIVE_KEY.search(text_key) else redact(item)
        return output
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return SENSITIVE_VALUE.sub("[REDACTED]", value)
    return value


def normalize_actor(actor: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize all supported producers into one explicit adapter schema."""
    if not isinstance(actor, Mapping):
        raise CustodyError("actor must be an object")
    raw_adapter = str(actor.get("adapter", "")).strip().lower()
    adapter = ADAPTER_ALIASES.get(raw_adapter)
    if adapter is None:
        raise CustodyError("unknown provider adapter: %s" % (raw_adapter or "<missing>"))
    principal_type = str(actor.get("principal_type", "")).strip().lower()
    if principal_type not in PRINCIPAL_TYPES:
        raise CustodyError("unknown principal_type: %s" % (principal_type or "<missing>"))
    provider = str(actor.get("provider", adapter)).strip().lower()
    if not provider:
        raise CustodyError("provider is required")
    model = actor.get("model")
    runtime = actor.get("runtime")
    if principal_type in {"model", "agent", "runtime"} and not str(model or "").strip():
        raise CustodyError("model is required for model/agent/runtime actors")
    result = {
        "adapter": adapter,
        "provider": provider,
        "principal_type": principal_type,
        "model": str(model).strip() if model is not None else None,
        "runtime": str(runtime).strip() if runtime is not None else None,
    }
    return result


def validate_locator(locator: Mapping[str, Any]) -> Dict[str, str]:
    """Accept a repository-relative POSIX locator and reject host-specific paths."""
    if not isinstance(locator, Mapping) or locator.get("scheme") != "repo":
        raise CustodyError("locator scheme must be 'repo'")
    raw_path = locator.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise CustodyError("locator path must be a non-empty string")
    if "\\" in raw_path or raw_path.startswith("/") or re.match(r"^[A-Za-z]:", raw_path):
        raise CustodyError("locator path must be portable and relative")
    pure = PurePosixPath(raw_path)
    if any(part in {"", ".", ".."} for part in pure.parts) or str(pure) != raw_path:
        raise CustodyError("locator path must be normalized without traversal")
    return {"scheme": "repo", "path": raw_path}


def resolve_locator(root: Path, locator: Mapping[str, Any]) -> Path:
    normalized = validate_locator(locator)
    root_resolved = root.resolve()
    target = root_resolved.joinpath(*PurePosixPath(normalized["path"]).parts).resolve()
    try:
        target.relative_to(root_resolved)
    except ValueError as exc:
        raise CustodyError("locator escapes artifact root") from exc
    return target


def artifact_reference(root: Path, relative_path: str, artifact_id: str) -> Dict[str, Any]:
    locator = validate_locator({"scheme": "repo", "path": relative_path})
    target = resolve_locator(root, locator)
    if not target.is_file():
        raise CustodyError("artifact does not exist: %s" % relative_path)
    if not artifact_id or not isinstance(artifact_id, str):
        raise CustodyError("artifact_id is required")
    return {
        "artifact_id": artifact_id,
        "digest": {"algorithm": "sha256", "value": sha256_file(target)},
        "locator": locator,
    }


def _validate_artifact_reference(reference: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(reference, Mapping):
        raise CustodyError("artifact reference must be an object")
    artifact_id = reference.get("artifact_id")
    digest = reference.get("digest")
    if not isinstance(artifact_id, str) or not artifact_id:
        raise CustodyError("artifact_id is required")
    if not isinstance(digest, Mapping) or digest.get("algorithm") != "sha256":
        raise CustodyError("artifact digest algorithm must be sha256")
    digest_value = digest.get("value")
    if not isinstance(digest_value, str) or not SHA256_RE.fullmatch(digest_value):
        raise CustodyError("artifact digest must be 64 lowercase hex characters")
    return {
        "artifact_id": artifact_id,
        "digest": {"algorithm": "sha256", "value": digest_value},
        "locator": validate_locator(reference.get("locator", {})),
    }


def build_event(
    *,
    index: int,
    previous_event_hash: str,
    event_type: str,
    actor: Mapping[str, Any],
    timestamp: str,
    artifacts: Sequence[Mapping[str, Any]],
    metadata: Optional[Mapping[str, Any]] = None,
    comparison: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a canonical event after redaction and strict schema validation."""
    if event_type not in EVENT_TYPES:
        raise CustodyError("unknown event_type: %s" % event_type)
    if not isinstance(index, int) or index < 0:
        raise CustodyError("index must be a non-negative integer")
    if not isinstance(previous_event_hash, str) or not SHA256_RE.fullmatch(previous_event_hash):
        raise CustodyError("previous_event_hash must be a sha256 value")
    if not isinstance(timestamp, str) or not timestamp:
        raise CustodyError("timestamp is required")
    clean_metadata = redact(dict(metadata or {}))
    event: Dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "index": index,
        "previous_event_hash": previous_event_hash,
        "event_type": event_type,
        "timestamp": timestamp,
        "actor": normalize_actor(actor),
        "artifacts": [_validate_artifact_reference(item) for item in artifacts],
        "metadata": clean_metadata,
    }
    if comparison is not None:
        event["comparison"] = validate_comparison_contract(comparison)
    event["event_hash"] = event_hash(event)
    return event


def validate_comparison_contract(contract: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate the measurement identity required before Pareto comparison."""
    if not isinstance(contract, Mapping):
        raise CustodyError("comparison contract must be an object")
    metric = contract.get("metric")
    if not isinstance(metric, Mapping):
        raise CustodyError("comparison metric must be an object")
    direction = metric.get("direction")
    if direction not in {"maximize", "minimize"}:
        raise CustodyError("metric direction must be maximize or minimize")
    required_text = {
        "cohort_id": contract.get("cohort_id"),
        "code_revision": contract.get("code_revision"),
        "model": contract.get("model"),
    }
    for key, value in required_text.items():
        if not isinstance(value, str) or not value:
            raise CustodyError("comparison %s is required" % key)
    cohort_sha256 = contract.get("cohort_sha256")
    if not isinstance(cohort_sha256, str) or not SHA256_RE.fullmatch(cohort_sha256):
        raise CustodyError("cohort_sha256 must be 64 lowercase hex characters")
    n_units = contract.get("n_units")
    if not isinstance(n_units, int) or isinstance(n_units, bool) or n_units <= 0:
        raise CustodyError("n_units must be a positive integer")
    for key in ("name", "unit"):
        if not isinstance(metric.get(key), str) or not metric.get(key):
            raise CustodyError("metric %s is required" % key)
    adapter = normalize_actor(
        {
            "adapter": contract.get("adapter"),
            "provider": contract.get("provider", contract.get("adapter")),
            "principal_type": "model",
            "model": contract.get("model"),
            "runtime": contract.get("runtime"),
        }
    )
    return {
        "cohort_id": required_text["cohort_id"],
        "cohort_sha256": cohort_sha256,
        "n_units": n_units,
        "metric": {
            "name": metric["name"],
            "direction": direction,
            "unit": metric["unit"],
        },
        "code_revision": required_text["code_revision"],
        "adapter": adapter["adapter"],
        "provider": adapter["provider"],
        "model": required_text["model"],
        "runtime": adapter["runtime"],
    }


def assert_comparable(left: Mapping[str, Any], right: Mapping[str, Any]) -> None:
    """Fail closed unless cohort, metric, code, provider, and model are identical."""
    left_valid = validate_comparison_contract(left)
    right_valid = validate_comparison_contract(right)
    fields = (
        "cohort_id",
        "cohort_sha256",
        "n_units",
        "metric",
        "code_revision",
        "adapter",
        "provider",
        "model",
        "runtime",
    )
    mismatches = [field for field in fields if left_valid[field] != right_valid[field]]
    if mismatches:
        raise IncomparableError("INCOMPARABLE: " + ", ".join(mismatches))


def _load_jsonl(ledger_path: Path) -> List[Dict[str, Any]]:
    if not ledger_path.is_file():
        raise CustodyError("ledger does not exist")
    text = ledger_path.read_text(encoding="utf-8")
    if not text:
        raise CustodyError("ledger is empty")
    lines = text.splitlines()
    if any(not line.strip() for line in lines):
        raise CustodyError("blank ledger records are forbidden")
    events: List[Dict[str, Any]] = []
    for line_number, line in enumerate(lines, 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CustodyError("invalid JSON at ledger line %d" % line_number) from exc
        if not isinstance(value, dict):
            raise CustodyError("ledger line %d is not an object" % line_number)
        if line != canonical_json(value):
            raise CustodyError("ledger line %d is not canonical JSON" % line_number)
        events.append(value)
    return events


def _read_receipt(receipt_path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CustodyError("receipt is missing or invalid") from exc
    if not isinstance(value, dict):
        raise CustodyError("receipt must be an object")
    return value


def verify_ledger(ledger_path: Path, receipt_path: Path, artifact_root: Path) -> Dict[str, Any]:
    """Verify receipt, event chain, adapters, and every referenced artifact."""
    events = _load_jsonl(ledger_path)
    receipt = _read_receipt(receipt_path)
    ledger_digest = sha256_file(ledger_path)
    if receipt.get("schema") != SCHEMA_VERSION:
        raise CustodyError("receipt schema mismatch")
    if receipt.get("event_count") != len(events):
        raise CustodyError("receipt event_count mismatch")
    if receipt.get("ledger_sha256") != ledger_digest:
        raise CustodyError("receipt ledger digest mismatch")

    previous = GENESIS_HASH
    verified_artifacts = 0
    for expected_index, event in enumerate(events):
        if event.get("schema") != SCHEMA_VERSION:
            raise CustodyError("event schema mismatch at index %d" % expected_index)
        if event.get("index") != expected_index:
            raise CustodyError("event index mismatch at index %d" % expected_index)
        if event.get("previous_event_hash") != previous:
            raise CustodyError("previous event hash mismatch at index %d" % expected_index)
        if event.get("event_type") not in EVENT_TYPES:
            raise CustodyError("unknown event type at index %d" % expected_index)
        normalized_actor = normalize_actor(event.get("actor", {}))
        if event.get("actor") != normalized_actor:
            raise CustodyError("actor is not canonical at index %d" % expected_index)
        candidate = copy.deepcopy(event)
        stored_hash = candidate.pop("event_hash", None)
        calculated_hash = event_hash(candidate)
        if stored_hash != calculated_hash:
            raise CustodyError("event hash mismatch at index %d" % expected_index)
        artifacts = event.get("artifacts")
        if not isinstance(artifacts, list):
            raise CustodyError("artifacts must be a list at index %d" % expected_index)
        for raw_reference in artifacts:
            reference = _validate_artifact_reference(raw_reference)
            target = resolve_locator(artifact_root, reference["locator"])
            if not target.is_file():
                raise CustodyError("referenced artifact is missing: %s" % reference["locator"]["path"])
            if sha256_file(target) != reference["digest"]["value"]:
                raise CustodyError("artifact digest mismatch: %s" % reference["artifact_id"])
            verified_artifacts += 1
        if "comparison" in event:
            validate_comparison_contract(event["comparison"])
        previous = stored_hash

    if receipt.get("head_event_hash") != previous:
        raise CustodyError("receipt head hash mismatch")
    return {
        "status": "PASS",
        "event_count": len(events),
        "artifact_references_verified": verified_artifacts,
        "head_event_hash": previous,
    }


def _write_receipt(ledger_path: Path, receipt_path: Path, events: Sequence[Mapping[str, Any]]) -> None:
    receipt = {
        "schema": SCHEMA_VERSION,
        "event_count": len(events),
        "head_event_hash": events[-1]["event_hash"],
        "ledger_sha256": sha256_file(ledger_path),
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=receipt_path.name + ".", dir=str(receipt_path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(receipt) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, receipt_path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def append_event(
    ledger_path: Path,
    receipt_path: Path,
    artifact_root: Path,
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    """Verify the current state, append exactly one record, and refresh its receipt."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if ledger_path.exists():
        current = verify_ledger(ledger_path, receipt_path, artifact_root)
        events = _load_jsonl(ledger_path)
        index = current["event_count"]
        previous = current["head_event_hash"]
    else:
        if receipt_path.exists():
            raise CustodyError("receipt exists without a ledger")
        events = []
        index = 0
        previous = GENESIS_HASH
    raw_event_type = payload.get("event_type")
    raw_timestamp = payload.get("timestamp")
    if not isinstance(raw_event_type, str):
        raise CustodyError("event_type is required")
    if not isinstance(raw_timestamp, str):
        raise CustodyError("timestamp is required")
    event = build_event(
        index=index,
        previous_event_hash=previous,
        event_type=raw_event_type,
        actor=payload.get("actor", {}),
        timestamp=raw_timestamp,
        artifacts=payload.get("artifacts", []),
        metadata=payload.get("metadata", {}),
        comparison=payload.get("comparison"),
    )
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(canonical_json(event) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    events.append(event)
    _write_receipt(ledger_path, receipt_path, events)
    return event


def _read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise CustodyError("expected a JSON object: %s" % path)
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Append and verify a chain-of-custody ledger")
    subparsers = parser.add_subparsers(dest="command", required=True)

    artifact = subparsers.add_parser("artifact", help="index one existing artifact")
    artifact.add_argument("--root", type=Path, required=True)
    artifact.add_argument("--path", required=True)
    artifact.add_argument("--id", required=True)

    append = subparsers.add_parser("append", help="append one event from a JSON payload")
    append.add_argument("--ledger", type=Path, required=True)
    append.add_argument("--receipt", type=Path, required=True)
    append.add_argument("--root", type=Path, required=True)
    append.add_argument("--event", type=Path, required=True)

    verify = subparsers.add_parser("verify", help="verify receipt, chain, and artifacts")
    verify.add_argument("--ledger", type=Path, required=True)
    verify.add_argument("--receipt", type=Path, required=True)
    verify.add_argument("--root", type=Path, required=True)

    compare = subparsers.add_parser("compare", help="fail closed on measurement mismatch")
    compare.add_argument("--baseline", type=Path, required=True)
    compare.add_argument("--candidate", type=Path, required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "artifact":
            result = artifact_reference(args.root, args.path, args.id)
        elif args.command == "append":
            result = append_event(args.ledger, args.receipt, args.root, _read_json(args.event))
        elif args.command == "verify":
            result = verify_ledger(args.ledger, args.receipt, args.root)
        else:
            assert_comparable(_read_json(args.baseline), _read_json(args.candidate))
            result = {"status": "COMPARABLE"}
    except (CustodyError, OSError, json.JSONDecodeError) as exc:
        print(canonical_json({"status": "FAIL", "reason": str(exc)}))
        return 1
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
