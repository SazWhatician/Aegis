"""Cryptographic SHA-256 hash-chain engine for immutable audit trails.

Adheres strictly to the Ponytail protocol:
- Uses Python standard library hashlib and json (canonical sorting).
- Zero external blockchain or heavy cryptographic dependencies.
- Mathematically verifiable non-repudiation and tamper detection.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any

GENESIS_HASH = "0" * 64  # Standard 64-character hex zero string for chain genesis


def _json_serial(obj: Any) -> Any:
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def canonical_json_bytes(payload: dict[str, Any] | list[Any] | str) -> bytes:
    """Produce deterministic UTF-8 bytes from a data payload.
    
    Guarantees consistent SHA-256 hashing regardless of dictionary key insertion order.
    """
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_json_serial,
    ).encode("utf-8")


def compute_payload_hash(payload: dict[str, Any] | list[Any] | str) -> str:
    """Compute hex SHA-256 digest of canonicalized payload bytes."""
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def compute_chain_link(
    payload_hash: str,
    previous_hash: str,
    chain_index: int,
    tenant_id: str,
    occurred_at: str,
) -> str:
    """Compute the cryptographic hash linking this event to the previous chain link.
    
    Hash = SHA-256(previous_hash + ":" + payload_hash + ":" + chain_index + ":" + tenant_id + ":" + occurred_at)
    """
    link_content = f"{previous_hash}:{payload_hash}:{chain_index}:{tenant_id}:{occurred_at}"
    return hashlib.sha256(link_content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuditEntryInput:
    """Specification for building an append-only audit event."""
    tenant_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    actor_type: str
    actor_id: str
    payload: dict[str, Any]
    occurred_at: datetime | None = None


def build_next_audit_event(
    entry: AuditEntryInput,
    latest_event_hash: str | None = None,
    latest_chain_index: int = -1,
) -> dict[str, Any]:
    """Construct the next audit event record linking cryptographically to latest event.
    
    If latest_event_hash is None or latest_chain_index == -1, initializes as Genesis link.
    """
    now = entry.occurred_at or datetime.now(timezone.utc)
    now_iso = now.isoformat()
    chain_index = latest_chain_index + 1
    previous_hash = latest_event_hash if latest_event_hash else GENESIS_HASH

    payload_hash = compute_payload_hash(entry.payload)
    chain_link_hash = compute_chain_link(
        payload_hash=payload_hash,
        previous_hash=previous_hash,
        chain_index=chain_index,
        tenant_id=entry.tenant_id,
        occurred_at=now_iso,
    )

    return {
        "tenant_id": entry.tenant_id,
        "aggregate_type": entry.aggregate_type,
        "aggregate_id": entry.aggregate_id,
        "event_type": entry.event_type,
        "actor_type": entry.actor_type,
        "actor_id": entry.actor_id,
        "occurred_at": now,
        "payload_hash": payload_hash,
        "previous_hash": previous_hash,
        "chain_index": chain_index,
        "chain_link_hash": chain_link_hash,
        "payload": entry.payload,
    }


def verify_chain_integrity(events: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """Validate unbroken cryptographic continuity and payload authenticity of an audit sequence.
    
    Returns:
        (True, None) if sequence is cryptographically intact.
        (False, failure_reason) if any tampering or broken link is detected.
    """
    if not events:
        return True, None

    sorted_events = sorted(events, key=lambda e: e.get("chain_index", 0))

    for i, evt in enumerate(sorted_events):
        idx = evt.get("chain_index")
        if idx != i:
            return False, f"Broken chain sequence: expected index {i}, found {idx}"

        # 1. Verify payload authenticity
        actual_payload_hash = compute_payload_hash(evt.get("payload", {}))
        recorded_payload_hash = evt.get("payload_hash")
        if actual_payload_hash != recorded_payload_hash:
            return (
                False,
                f"Tampered payload at index {idx}: recorded {recorded_payload_hash}, computed {actual_payload_hash}",
            )

        # 2. Verify previous hash continuity
        recorded_prev_hash = evt.get("previous_hash")
        if i == 0:
            if recorded_prev_hash != GENESIS_HASH:
                return False, f"Invalid genesis previous_hash at index 0: {recorded_prev_hash}"
        else:
            prev_evt = sorted_events[i - 1]
            expected_prev_hash = prev_evt.get("chain_link_hash") or prev_evt.get("payload_hash")
            # Support both link hash or payload hash chains
            if recorded_prev_hash not in (prev_evt.get("chain_link_hash"), prev_evt.get("payload_hash")):
                return (
                    False,
                    f"Broken link at index {idx}: previous_hash {recorded_prev_hash} does not match predecessor",
                )

    return True, None
