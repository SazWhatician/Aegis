"""Financial crime intake routes: transactions, KYC, and cryptographic audit verification."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_db_session, get_idempotency_key, get_tenant_id
from packages.audit.hash_chain import (
    AuditEntryInput,
    build_next_audit_event,
    verify_chain_integrity,
)
from packages.contracts import (
    CustomerProfileIn,
    EventTypeEnum,
    TransactionIn,
)
from packages.domain.models import (
    Account,
    AuditEvent,
    Customer,
    CustomerParty,
    OutboxEvent,
    Party,
    Transaction,
    generate_uuid7,
    utc_now,
)

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion & Intake"])


@router.post(
    "/transaction",
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a financial transaction with transactional outbox & audit hashing",
)
async def post_transaction(
    payload: TransactionIn,
    response: Response,
    tenant_id: str = Depends(get_tenant_id),
    idempotency_key_header: str | None = Depends(get_idempotency_key),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Ingest financial transaction adhering to strict idempotency and cryptographic audit trail."""
    idempotency_key = idempotency_key_header or f"txn:{payload.transaction_id}"

    # 1. Idempotency verification: Check if event was already accepted
    stmt = select(OutboxEvent).where(
        OutboxEvent.tenant_id == tenant_id,
        OutboxEvent.idempotency_key == idempotency_key,
    )
    result = await session.execute(stmt)
    existing_outbox = result.scalar_one_or_none()

    if existing_outbox:
        response.status_code = status.HTTP_200_OK
        return {
            "status": "duplicate_idempotent",
            "message": "Transaction already accepted and processed.",
            "transaction_id": payload.transaction_id,
            "event_id": existing_outbox.event_id,
            "outbox_status": existing_outbox.status,
        }

    # 2. Account verification / auto-provisioning for demo / ingestion flows
    acct_stmt = select(Account).where(
        Account.tenant_id == tenant_id,
        Account.id == payload.account_id,
    )
    acct_result = await session.execute(acct_stmt)
    account = acct_result.scalar_one_or_none()

    if not account:
        # Auto-provision system default customer and account if not existing yet
        cust_stmt = select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.id == f"cust_{payload.account_id}",
        )
        cust_res = await session.execute(cust_stmt)
        customer = cust_res.scalar_one_or_none()
        if not customer:
            customer = Customer(
                id=f"cust_{payload.account_id}",
                tenant_id=tenant_id,
                customer_type="business",
                legal_name=f"Entity {payload.account_id}",
                jurisdiction=payload.country_code or "US",
            )
            session.add(customer)
            await session.flush()

        account = Account(
            id=payload.account_id,
            tenant_id=tenant_id,
            customer_id=customer.id,
            currency=payload.currency,
        )
        session.add(account)
        await session.flush()

    # 3. Create Transaction Record
    txn_data = payload.model_dump(mode="json")
    txn_record = Transaction(
        id=payload.transaction_id,
        tenant_id=tenant_id,
        account_id=payload.account_id,
        direction=payload.direction.value,
        amount=payload.amount,
        currency=payload.currency,
        channel=payload.channel.value,
        counterparty_id=payload.counterparty_id,
        counterparty_account=payload.counterparty_account,
        country_code=payload.country_code,
        occurred_at=payload.occurred_at,
        description=payload.description,
        raw_payload=txn_data,
    )
    session.add(txn_record)

    # 4. Fetch latest audit event to continue SHA-256 hash chain
    audit_stmt = (
        select(AuditEvent)
        .where(AuditEvent.tenant_id == tenant_id)
        .order_by(desc(AuditEvent.chain_index))
        .limit(1)
    )
    latest_audit_res = await session.execute(audit_stmt)
    latest_audit = latest_audit_res.scalar_one_or_none()

    latest_hash = latest_audit.payload_hash if latest_audit else None
    latest_index = latest_audit.chain_index if latest_audit else -1

    audit_dict = build_next_audit_event(
        entry=AuditEntryInput(
            tenant_id=tenant_id,
            aggregate_type="transaction",
            aggregate_id=payload.transaction_id,
            event_type=EventTypeEnum.TRANSACTION_POSTED.value,
            actor_type="system",
            actor_id="ingestion_api",
            payload=txn_data,
            occurred_at=payload.occurred_at,
        ),
        latest_event_hash=latest_hash,
        latest_chain_index=latest_index,
    )

    audit_entry = AuditEvent(
        tenant_id=tenant_id,
        aggregate_type=audit_dict["aggregate_type"],
        aggregate_id=audit_dict["aggregate_id"],
        event_type=audit_dict["event_type"],
        actor_type=audit_dict["actor_type"],
        actor_id=audit_dict["actor_id"],
        occurred_at=audit_dict["occurred_at"],
        payload_hash=audit_dict["payload_hash"],
        previous_hash=audit_dict["previous_hash"],
        chain_index=audit_dict["chain_index"],
        payload=audit_dict["payload"],
    )
    session.add(audit_entry)

    # 5. Create Transactional Outbox Event
    event_id = generate_uuid7()
    outbox_entry = OutboxEvent(
        tenant_id=tenant_id,
        event_id=event_id,
        event_type=EventTypeEnum.TRANSACTION_POSTED.value,
        correlation_id=payload.transaction_id,
        idempotency_key=idempotency_key,
        payload=txn_data,
        status="PENDING",
    )
    session.add(outbox_entry)

    # All three committed in single atomic transaction via session dependency
    return {
        "status": "accepted",
        "transaction_id": payload.transaction_id,
        "event_id": event_id,
        "chain_index": audit_dict["chain_index"],
        "payload_hash": audit_dict["payload_hash"],
    }


@router.post(
    "/kyc",
    status_code=status.HTTP_201_CREATED,
    summary="Ingest KYC customer profile, related parties, and beneficial owners",
)
async def post_kyc_profile(
    payload: CustomerProfileIn,
    tenant_id: str = Depends(get_tenant_id),
    idempotency_key_header: str | None = Depends(get_idempotency_key),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Ingest corporate/individual KYC profile with ownership graph."""
    idempotency_key = idempotency_key_header or f"kyc:{payload.customer_id}"

    # Check idempotency
    stmt = select(OutboxEvent).where(
        OutboxEvent.tenant_id == tenant_id,
        OutboxEvent.idempotency_key == idempotency_key,
    )
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        return {
            "status": "duplicate_idempotent",
            "message": "KYC profile already accepted and processed.",
            "customer_id": payload.customer_id,
        }

    # Upsert customer
    cust_stmt = select(Customer).where(
        Customer.tenant_id == tenant_id,
        Customer.id == payload.customer_id,
    )
    cust_res = await session.execute(cust_stmt)
    customer = cust_res.scalar_one_or_none()

    kyc_data = payload.model_dump(mode="json")

    if not customer:
        customer = Customer(
            id=payload.customer_id,
            tenant_id=tenant_id,
            customer_type=payload.customer_type.value,
            legal_name=payload.legal_name,
            jurisdiction=payload.jurisdiction,
            risk_tier=payload.risk_tier.value,
            declared_monthly_turnover=payload.declared_monthly_turnover,
            device_tokens=payload.device_tokens,
            ip_addresses=payload.ip_addresses,
        )
        session.add(customer)
    else:
        customer.legal_name = payload.legal_name
        customer.jurisdiction = payload.jurisdiction
        customer.risk_tier = payload.risk_tier.value
        customer.declared_monthly_turnover = payload.declared_monthly_turnover
        customer.device_tokens = payload.device_tokens
        customer.ip_addresses = payload.ip_addresses

    await session.flush()

    # Process Parties and Beneficial Owners
    for party_in in payload.parties:
        p_stmt = select(Party).where(Party.tenant_id == tenant_id, Party.id == party_in.party_id)
        p_res = await session.execute(p_stmt)
        party = p_res.scalar_one_or_none()
        if not party:
            party = Party(
                id=party_in.party_id,
                tenant_id=tenant_id,
                kind=party_in.kind.value,
                canonical_name=party_in.canonical_name,
                tax_id_token=party_in.tax_id_token,
                jurisdiction=party_in.jurisdiction,
                date_of_birth_or_inc=party_in.date_of_birth_or_inc,
                risk_tier=party_in.risk_tier.value,
            )
            session.add(party)

    await session.flush()

    # Beneficial owners associations
    for bo in payload.beneficial_owners:
        cp_stmt = select(CustomerParty).where(
            CustomerParty.tenant_id == tenant_id,
            CustomerParty.customer_id == payload.customer_id,
            CustomerParty.party_id == bo.party_id,
        )
        cp_res = await session.execute(cp_stmt)
        cp = cp_res.scalar_one_or_none()
        if not cp:
            cp = CustomerParty(
                tenant_id=tenant_id,
                customer_id=payload.customer_id,
                party_id=bo.party_id,
                role=bo.role.value,
                ownership_pct=bo.ownership_pct,
                is_pep=bo.is_pep,
                valid_from=bo.valid_from,
                valid_to=bo.valid_to,
            )
            session.add(cp)

    # Append to cryptographic audit chain
    audit_stmt = (
        select(AuditEvent)
        .where(AuditEvent.tenant_id == tenant_id)
        .order_by(desc(AuditEvent.chain_index))
        .limit(1)
    )
    latest_audit = (await session.execute(audit_stmt)).scalar_one_or_none()
    latest_hash = latest_audit.payload_hash if latest_audit else None
    latest_index = latest_audit.chain_index if latest_audit else -1

    audit_dict = build_next_audit_event(
        entry=AuditEntryInput(
            tenant_id=tenant_id,
            aggregate_type="customer",
            aggregate_id=payload.customer_id,
            event_type=EventTypeEnum.CUSTOMER_CREATED.value,
            actor_type="system",
            actor_id="kyc_intake",
            payload=kyc_data,
        ),
        latest_event_hash=latest_hash,
        latest_chain_index=latest_index,
    )

    session.add(
        AuditEvent(
            tenant_id=tenant_id,
            aggregate_type=audit_dict["aggregate_type"],
            aggregate_id=audit_dict["aggregate_id"],
            event_type=audit_dict["event_type"],
            actor_type=audit_dict["actor_type"],
            actor_id=audit_dict["actor_id"],
            occurred_at=audit_dict["occurred_at"],
            payload_hash=audit_dict["payload_hash"],
            previous_hash=audit_dict["previous_hash"],
            chain_index=audit_dict["chain_index"],
            payload=audit_dict["payload"],
        )
    )

    event_id = generate_uuid7()
    session.add(
        OutboxEvent(
            tenant_id=tenant_id,
            event_id=event_id,
            event_type=EventTypeEnum.CUSTOMER_CREATED.value,
            correlation_id=payload.customer_id,
            idempotency_key=idempotency_key,
            payload=kyc_data,
            status="PENDING",
        )
    )

    return {
        "status": "accepted",
        "customer_id": payload.customer_id,
        "event_id": event_id,
        "chain_index": audit_dict["chain_index"],
    }


@router.get(
    "/audit/verify",
    summary="Cryptographically verify unbroken audit trail continuity for a tenant",
)
async def verify_tenant_audit_trail(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Audit verification endpoint providing mathematical proof of audit log integrity."""
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.chain_index.asc())
    )
    result = await session.execute(stmt)
    records = result.scalars().all()

    events_dicts = [
        {
            "chain_index": r.chain_index,
            "payload_hash": r.payload_hash,
            "previous_hash": r.previous_hash,
            "payload": r.payload,
        }
        for r in records
    ]

    is_valid, reason = verify_chain_integrity(events_dicts)

    return {
        "tenant_id": tenant_id,
        "total_audit_events": len(records),
        "is_tamper_free": is_valid,
        "verification_error": reason,
    }
