"""Comprehensive unit tests for Phase 0 Foundation:

- Strict Pydantic v2 Contracts (Transactions, KYC, Events)
- Transactional Outbox Pattern & Idempotent Ingestion API
- Cryptographic SHA-256 Hash Chain Non-Repudiation & Tamper Detection
- Asynchronous Outbox Worker & Event Dispatcher
- Algorithmic Realism of 'Project Sandglass' Mule Scenario
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from apps.worker.outbox import EventDispatcher, OutboxWorker
from ml.synthetic.generator import seed_sandglass_mule_scenario, seed_scenario_to_database
from packages.audit.hash_chain import (
    GENESIS_HASH,
    AuditEntryInput,
    build_next_audit_event,
    compute_payload_hash,
    verify_chain_integrity,
)
from packages.contracts import (
    BeneficialOwner,
    ChannelEnum,
    CustomerProfileIn,
    CustomerTypeEnum,
    DirectionEnum,
    EventEnvelope,
    EventTypeEnum,
    PartyIn,
    PartyRoleEnum,
    RiskTierEnum,
    TransactionIn,
)
from packages.domain.database import get_session_factory
from packages.domain.models import AuditEvent, OutboxEvent, Transaction


def test_transaction_contract_strict_validation():
    """Verify strict validation and rejection of extra fields and invalid financial types."""
    # 1. Valid transaction
    valid_txn = TransactionIn(
        transaction_id="txn-test-01",
        account_id="acct-test-01",
        occurred_at=datetime.now(timezone.utc),
        direction=DirectionEnum.CREDIT,
        amount=Decimal("1250.50"),
        currency="USD",
        channel=ChannelEnum.WIRE,
        country_code="US",
    )
    assert valid_txn.amount == Decimal("1250.50")

    # 2. Rejection of unknown properties (extra="forbid")
    with pytest.raises(ValidationError) as exc:
        TransactionIn(
            transaction_id="txn-test-02",
            account_id="acct-test-01",
            occurred_at=datetime.now(timezone.utc),
            direction=DirectionEnum.CREDIT,
            amount=Decimal("100.00"),
            currency="USD",
            channel=ChannelEnum.WIRE,
            malicious_field="injection_attempt",  # type: ignore[call-arg]
        )
    assert "extra_forbidden" in str(exc.value)

    # 3. Rejection of negative / zero monetary amount
    with pytest.raises(ValidationError):
        TransactionIn(
            transaction_id="txn-test-03",
            account_id="acct-test-01",
            occurred_at=datetime.now(timezone.utc),
            direction=DirectionEnum.DEBIT,
            amount=Decimal("-50.00"),
            currency="USD",
            channel=ChannelEnum.ACH,
        )

    # 4. Rejection of non-ISO-4217 currency
    with pytest.raises(ValidationError):
        TransactionIn(
            transaction_id="txn-test-04",
            account_id="acct-test-01",
            occurred_at=datetime.now(timezone.utc),
            direction=DirectionEnum.DEBIT,
            amount=Decimal("50.00"),
            currency="INVALID_CURRENCY",
            channel=ChannelEnum.ACH,
        )


def test_kyc_contract_validation():
    """Verify KYC profile hierarchy and beneficial ownership validation."""
    valid_kyc = CustomerProfileIn(
        customer_id="cust-corp-01",
        customer_type=CustomerTypeEnum.BUSINESS,
        legal_name="Acme Holdings Ltd",
        jurisdiction="GB",
        risk_tier=RiskTierEnum.MEDIUM,
        declared_monthly_turnover=Decimal("75000.00"),
        parties=[
            PartyIn(
                party_id="party-01",
                kind=CustomerTypeEnum.INDIVIDUAL,
                canonical_name="Jane Doe",
                jurisdiction="GB",
            )
        ],
        beneficial_owners=[
            BeneficialOwner(
                party_id="party-01",
                ownership_pct=Decimal("51.00"),
                role=PartyRoleEnum.BENEFICIAL_OWNER,
                is_pep=False,
                valid_from=datetime.now(timezone.utc),
            )
        ],
    )
    assert len(valid_kyc.parties) == 1
    assert valid_kyc.beneficial_owners[0].ownership_pct == Decimal("51.00")

    # Invalid ownership percent (>100%)
    with pytest.raises(ValidationError):
        BeneficialOwner(
            party_id="party-01",
            ownership_pct=Decimal("150.00"),
            valid_from=datetime.now(timezone.utc),
        )


def test_cryptographic_audit_hash_chain_tamper_detection():
    """Verify SHA-256 Merkle-style hash chaining and mathematical tamper detection."""
    tenant = "audit-test-tenant"
    e0 = build_next_audit_event(
        AuditEntryInput(
            tenant_id=tenant,
            aggregate_type="transaction",
            aggregate_id="txn-1",
            event_type="transaction.posted.v1",
            actor_type="system",
            actor_id="test",
            payload={"amount": "100.00", "currency": "USD"},
        )
    )
    e1 = build_next_audit_event(
        AuditEntryInput(
            tenant_id=tenant,
            aggregate_type="transaction",
            aggregate_id="txn-2",
            event_type="transaction.posted.v1",
            actor_type="system",
            actor_id="test",
            payload={"amount": "250.00", "currency": "USD"},
        ),
        latest_event_hash=e0["payload_hash"],
        latest_chain_index=e0["chain_index"],
    )

    # 1. Valid unbroken chain
    is_valid, err = verify_chain_integrity([e0, e1])
    assert is_valid is True
    assert err is None

    # 2. Tampered event payload
    tampered_e0 = dict(e0)
    tampered_e0["payload"] = {"amount": "999999.00", "currency": "USD"}  # altered payload
    is_valid, err = verify_chain_integrity([tampered_e0, e1])
    assert is_valid is False
    assert "Tampered payload at index 0" in err


def test_intake_api_idempotency_and_outbox(client):
    """Verify FastAPI intake route with idempotency and transactional outbox."""
    payload = {
        "transaction_id": "txn-api-99",
        "account_id": "acct-api-99",
        "occurred_at": "2026-10-14T10:00:00Z",
        "direction": "credit",
        "amount": "18500.00",
        "currency": "USD",
        "channel": "wire",
        "country_code": "US",
        "description": "Commercial wire settlement",
    }
    headers = {"X-Tenant-ID": "test-bank", "Idempotency-Key": "client-key-99"}

    # First POST -> Accepted (201)
    res1 = client.post("/api/v1/ingest/transaction", json=payload, headers=headers)
    assert res1.status_code == 201
    data1 = res1.json()
    assert data1["status"] == "accepted"
    assert data1["transaction_id"] == "txn-api-99"

    # Duplicate POST with same Idempotency-Key -> Idempotent replay (200)
    res2 = client.post("/api/v1/ingest/transaction", json=payload, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "duplicate_idempotent"
    assert data2["event_id"] == data1["event_id"]

    # Verify audit trail endpoint reports zero tampering
    audit_res = client.get("/api/v1/ingest/audit/verify", headers=headers)
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["is_tamper_free"] is True
    assert audit_data["total_audit_events"] >= 1


@pytest.mark.asyncio
async def test_outbox_worker_polling_and_dispatch():
    """Verify asynchronous OutboxWorker polls pending events and dispatches to subscribers."""
    session_factory = get_session_factory()
    dispatcher = EventDispatcher()
    received_events: list[EventEnvelope] = []

    async def sample_handler(envelope: EventEnvelope):
        received_events.append(envelope)

    dispatcher.subscribe(EventTypeEnum.TRANSACTION_POSTED, sample_handler)

    # Insert pending event into outbox
    async with session_factory() as session:
        evt = OutboxEvent(
            tenant_id="worker-test-bank",
            event_id="test-evt-001",
            event_type=EventTypeEnum.TRANSACTION_POSTED.value,
            correlation_id="corr-001",
            idempotency_key="worker-key-001",
            payload={"amount": "5000.00"},
            status="PENDING",
        )
        session.add(evt)
        await session.commit()

    # Run worker batch
    worker = OutboxWorker(session_maker=session_factory, dispatcher=dispatcher)
    processed_count = await worker.process_pending_batch()

    assert processed_count == 1
    assert len(received_events) == 1
    assert received_events[0].event_id == "test-evt-001"

    # Check status transitioned to PUBLISHED
    async with session_factory() as session:
        stmt = select(OutboxEvent).where(OutboxEvent.event_id == "test-evt-001")
        res = await session.execute(stmt)
        record = res.scalar_one()
        assert record.status == "PUBLISHED"
        assert record.processed_at is not None


@pytest.mark.asyncio
async def test_project_sandglass_algorithmic_invariants():
    """Verify authentic AML typology invariants in the generated Project Sandglass scenario."""
    scenario = seed_sandglass_mule_scenario(tenant_id="demo-bank", seed=42)

    # 1. Structural requirements
    assert len(scenario["inbound_transactions"]) == 18, "Must generate exactly 18 inbound transfers over 48 hours"
    assert len(scenario["outbound_transactions"]) == 16, "Must generate exactly 16 rapid outbound transfers"

    # 2. Structuring below CTR threshold ($4,500 - $9,800 < $10,000)
    for in_txn in scenario["inbound_transactions"]:
        assert Decimal("4000.00") <= in_txn["amount"] < Decimal("10000.00"), (
            f"Inflow amount {in_txn['amount']} violates smurfing criteria"
        )

    # 3. Rapid pass-through ratio (>90%)
    summary = scenario["summary"]
    assert summary["pass_through_ratio"] >= 0.90, (
        f"Pass-through ratio {summary['pass_through_ratio']} is below 90%"
    )

    # 4. Shared device token between Viktor Vance and mules
    customer = scenario["customer_profile"]
    assert "dev_shared_mule_7f90c" in customer.device_tokens
    first_mule = scenario["mule_accounts"][0]
    assert first_mule["device_token"] == "dev_shared_mule_7f90c"

    # 5. Database Persistence with live audit hashing
    session_factory = get_session_factory()
    async with session_factory() as session:
        counts = await seed_scenario_to_database(session, scenario)
        assert counts["customers"] == 1
        assert counts["transactions"] == 34  # 18 in + 16 out
        assert counts["audit_events"] == 34
        assert counts["outbox_events"] == 34

        # Validate audit chain continuity of seeded scenario
        audit_stmt = (
            select(AuditEvent)
            .where(AuditEvent.tenant_id == "demo-bank")
            .order_by(AuditEvent.chain_index.asc())
        )
        audit_records = (await session.execute(audit_stmt)).scalars().all()
        dicts = [
            {
                "chain_index": a.chain_index,
                "payload_hash": a.payload_hash,
                "previous_hash": a.previous_hash,
                "payload": a.payload,
            }
            for a in audit_records
        ]
        is_intact, reason = verify_chain_integrity(dicts)
        assert is_intact is True, f"Audit chain broke: {reason}"
