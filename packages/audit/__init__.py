"""AEGIS Audit Engine Package."""

from packages.audit.hash_chain import (
    GENESIS_HASH,
    AuditEntryInput,
    build_next_audit_event,
    canonical_json_bytes,
    compute_chain_link,
    compute_payload_hash,
    verify_chain_integrity,
)

__all__ = [
    "GENESIS_HASH",
    "AuditEntryInput",
    "build_next_audit_event",
    "canonical_json_bytes",
    "compute_chain_link",
    "compute_payload_hash",
    "verify_chain_integrity",
]
