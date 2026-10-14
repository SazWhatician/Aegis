"""Unified event envelope contract for outbox and asynchronous messaging."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class EventTypeEnum(str, Enum):
    """Standardized event taxonomy across the AEGIS ecosystem."""
    TRANSACTION_POSTED = "transaction.posted.v1"
    CUSTOMER_CREATED = "customer.created.v1"
    CUSTOMER_UPDATED = "customer.updated.v1"
    ALERT_GENERATED = "alert.generated.v1"
    CASE_OPENED = "case.opened.v1"
    CASE_TRANSITIONED = "case.transitioned.v1"
    AUDIT_ENTRY = "audit.entry.v1"


class EventEnvelope(BaseModel):
    """Immutable event envelope matching enterprise transactional outbox contracts."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(..., min_length=1, description="Globally unique event identifier (UUIDv7 or ULID)")
    event_type: EventTypeEnum = Field(..., description="Canonical taxonomy type of the event")
    tenant_id: str = Field(..., min_length=1, max_length=64, description="Tenant partition identifier for multi-tenancy isolation")
    occurred_at: datetime = Field(..., description="Timestamp when event occurred at source")
    producer: str = Field(..., min_length=1, max_length=128, description="Originating service or subsystem")
    correlation_id: str = Field(..., min_length=1, max_length=128, description="Distributed tracing correlation key")
    idempotency_key: str = Field(..., min_length=1, max_length=255, description="Client or producer idempotency deduplication key")
    data_classification: Literal["public", "internal", "confidential", "restricted"] = Field(
        default="restricted", description="Data sensitivity classification"
    )
    payload: dict[str, Any] = Field(..., description="Validated event payload body")
