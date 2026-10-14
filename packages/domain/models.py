"""SQLAlchemy declarative models for AEGIS financial crime intelligence domain."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import uuid_utils
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# JSON type compatible across SQLite and PostgreSQL
JSONType = SQLiteJSON().with_variant(SQLiteJSON, "sqlite")


def generate_uuid7() -> str:
    """Generate time-ordered UUIDv7 as string."""
    return str(uuid_utils.uuid7())


def utc_now() -> datetime:
    """Standard UTC timestamp factory."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for all AEGIS domain models."""
    pass


class Customer(Base):
    """Customer identity profile (natural person or legal business entity)."""
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    customer_type: Mapped[str] = mapped_column(String(32), nullable=False)  # individual, business
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO-3166-1 alpha-2
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(32), default="low", nullable=False)
    declared_monthly_turnover: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    device_tokens: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    ip_addresses: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="customer", cascade="all, delete-orphan")
    party_associations: Mapped[list["CustomerParty"]] = relationship("CustomerParty", back_populates="customer", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_customers_tenant_type", "tenant_id", "customer_type"),
        Index("ix_customers_tenant_name", "tenant_id", "legal_name"),
    )


class Party(Base):
    """Related party entity (director, beneficial owner, corporate officer)."""
    __tablename__ = "parties"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # individual, business
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tax_id_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    jurisdiction: Mapped[str] = mapped_column(String(2), nullable=False)
    date_of_birth_or_inc: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_tier: Mapped[str] = mapped_column(String(32), default="low", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    customer_associations: Mapped[list["CustomerParty"]] = relationship("CustomerParty", back_populates="party")

    __table_args__ = (
        Index("ix_parties_tenant_canonical", "tenant_id", "canonical_name"),
    )


class CustomerParty(Base):
    """Association table mapping beneficial ownership and corporate roles."""
    __tablename__ = "customer_parties"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    party_id: Mapped[str] = mapped_column(String(64), ForeignKey("parties.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    ownership_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    is_pep: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="party_associations")
    party: Mapped["Party"] = relationship("Party", back_populates="customer_associations")

    __table_args__ = (
        Index("ix_custparty_tenant_pair", "tenant_id", "customer_id", "party_id"),
    )


class Account(Base):
    """Financial account owned by a customer."""
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), default="demand_deposit", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="account")

    __table_args__ = (
        Index("ix_accounts_tenant_cust", "tenant_id", "customer_id"),
    )


class Transaction(Base):
    """Ledger transaction record subject to monitoring and graph projection."""
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    account_id: Mapped[str] = mapped_column(String(64), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # credit, debit
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)  # wire, ach, card, etc.
    counterparty_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    counterparty_account: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="settled", nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="transactions")

    __table_args__ = (
        # Critical composite index for point-in-time temporal queries without lookahead leakage
        Index("ix_txns_tenant_acct_time", "tenant_id", "account_id", "occurred_at"),
        Index("ix_txns_tenant_time", "tenant_id", "occurred_at"),
    )


class Alert(Base):
    """Detection alert emitted by deterministic rules or ML models."""
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)  # account, customer, transaction
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    detector_version: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # low, medium, high, critical
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_alerts_tenant_idempotency", "tenant_id", "idempotency_key", unique=True),
        Index("ix_alerts_tenant_subject", "tenant_id", "subject_type", "subject_id"),
    )


class Case(Base):
    """Investigation case container governed by state machine and CAS versioning."""
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    external_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="NEW", nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # CAS expected_version
    policy_bundle_version: Mapped[str] = mapped_column(String(64), default="v1.0.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_cases_tenant_status", "tenant_id", "status"),
        Index("ix_cases_tenant_ref", "tenant_id", "external_ref", unique=True),
    )


class AuditEvent(Base):
    """Append-only cryptographic audit ledger entry with SHA-256 hash chaining."""
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), default="system", nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chain_index: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_audit_tenant_chain", "tenant_id", "chain_index", unique=True),
        Index("ix_audit_tenant_aggregate", "tenant_id", "aggregate_type", "aggregate_id"),
    )


class OutboxEvent(Base):
    """Transactional outbox table for atomic event emission without dual-write hazards."""
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=generate_uuid7)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True, nullable=False)  # PENDING, PROCESSING, PUBLISHED, FAILED
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_outbox_tenant_idempotency", "tenant_id", "idempotency_key", unique=True),
        Index("ix_outbox_status_created", "status", "created_at"),
    )
