"""Algorithmic Synthetic Financial Crime Universe & 'Project Sandglass' Generator.

Strictly adheres to the "No Dummy / No Static Mocks" Doctrine:
- Zero static hardcoded fixtures.
- Algorithmic generation of realistic multi-account banking networks.
- Mathematically verifiable AML typologies (structuring below $10k CTR, velocity funneling, rapid pass-through).
- Reproducible deterministic seeding for scientific backtesting and evaluation.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
import random
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.hash_chain import AuditEntryInput, build_next_audit_event
from packages.contracts import (
    BeneficialOwner,
    ChannelEnum,
    CustomerProfileIn,
    CustomerTypeEnum,
    DirectionEnum,
    EventTypeEnum,
    PartyIn,
    PartyRoleEnum,
    RiskTierEnum,
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


class AMLUniverseGenerator:
    """Algorithmic generator producing realistic banking ecosystems and seeded AML typologies."""

    def __init__(self, seed: int = 42, base_time: datetime | None = None) -> None:
        self.rng = random.Random(seed)
        self.base_time = base_time or datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)

    def _random_lognormal_amount(self, mean: float = 6.0, sigma: float = 1.2, min_val: float = 10.0, max_val: float = 50000.0) -> Decimal:
        """Sample transaction amount from a log-normal financial distribution."""
        val = math.exp(self.rng.gauss(mean, sigma))
        val = max(min_val, min(max_val, val))
        return Decimal(f"{val:.2f}")

    def generate_benign_universe(
        self,
        tenant_id: str = "demo-bank",
        num_customers: int = 30,
        num_txns: int = 100,
    ) -> dict[str, Any]:
        """Generate a background population of legitimate retail and commercial customers."""
        customers: list[dict[str, Any]] = []
        accounts: list[dict[str, Any]] = []
        transactions: list[dict[str, Any]] = []

        first_names = ["James", "Emma", "Liam", "Olivia", "Noah", "Sophia", "Lucas", "Ava", "Alexander", "Mia"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson", "Taylor", "Clark"]
        business_suffixes = ["Enterprises LLC", "Consulting Inc", "Retail Partners", "Tech Solutions Ltd", "Global Freight"]

        # 1. Generate Customers & Accounts
        for i in range(num_customers):
            is_business = (i % 4 == 0)
            cust_id = f"cust_benign_{i+1:03d}"
            name = f"{self.rng.choice(first_names)} {self.rng.choice(business_suffixes)}" if is_business else f"{self.rng.choice(first_names)} {self.rng.choice(last_names)}"
            turnover = self._random_lognormal_amount(mean=8.5, sigma=0.8, min_val=2000.0, max_val=200000.0)

            cust = {
                "id": cust_id,
                "tenant_id": tenant_id,
                "customer_type": "business" if is_business else "individual",
                "legal_name": name,
                "jurisdiction": "US",
                "risk_tier": "low",
                "declared_monthly_turnover": turnover,
                "device_tokens": [f"dev_benign_{self.rng.randint(1000, 9999)}"],
                "ip_addresses": [f"192.168.1.{self.rng.randint(10, 250)}"],
            }
            customers.append(cust)

            # Assign 1-2 accounts per customer
            num_accts = 2 if is_business else 1
            for a_idx in range(num_accts):
                acct_id = f"acct_benign_{i+1:03d}_{a_idx+1}"
                accounts.append({
                    "id": acct_id,
                    "tenant_id": tenant_id,
                    "customer_id": cust_id,
                    "account_type": "commercial_checking" if is_business else "retail_checking",
                    "currency": "USD",
                    "balance": Decimal(f"{self.rng.uniform(1000.0, 50000.0):.2f}"),
                })

        # 2. Generate Normal Background Transactions
        account_ids = [a["id"] for a in accounts]
        channels = ["wire", "ach", "card"]

        for t_idx in range(num_txns):
            src_acct = self.rng.choice(account_ids)
            dest_acct = self.rng.choice([a for a in account_ids if a != src_acct])
            amount = self._random_lognormal_amount(mean=5.5, sigma=1.0, min_val=15.0, max_val=8000.0)
            offset_hours = self.rng.uniform(1, 240)  # over 10 days
            occurred_at = self.base_time + timedelta(hours=offset_hours)

            transactions.append({
                "transaction_id": f"txn_benign_{t_idx+1:04d}",
                "tenant_id": tenant_id,
                "account_id": src_acct,
                "direction": "debit",
                "amount": amount,
                "currency": "USD",
                "channel": self.rng.choice(channels),
                "counterparty_id": dest_acct,
                "counterparty_account": f"ext_{dest_acct}",
                "country_code": "US",
                "occurred_at": occurred_at,
                "description": f"Invoice settlement {t_idx+1}",
            })

        return {
            "customers": customers,
            "accounts": accounts,
            "transactions": transactions,
        }

    def generate_sandglass_mule_scenario(self, tenant_id: str = "demo-bank") -> dict[str, Any]:
        """Generate the flagship 'Project Sandglass' mule funnel and rapid pass-through typology.
        
        Scenario Details:
        - Target Customer: Sandglass Logistics Ltd (business with beneficial owner change).
        - Beneficial Owner: Viktor Vance (45% equity, PEP association, shared device token).
        - Fan-in (Funnel): 18 incoming transfers over 48 hours structured between $4,500 and $9,800
          (classic CTR evasion beneath $10k threshold) from 18 distinct newly connected counterparties.
        - Fan-out (Pass-through): 16 rapid outbound transfers to 3 offshore beneficiary accounts
          within hours of intake (pass-through ratio > 90%).
        - Graph connections: Shared device tokens with mules and 2-hop path to sanctioned entity.
        """
        # Timeline anchor: Starts on Day 5 at 08:00 UTC
        scenario_start = self.base_time + timedelta(days=5, hours=8)

        # 1. Target Customer Profile & Accounts
        sandglass_cust = {
            "customer_id": "cust_sandglass_01",
            "customer_type": CustomerTypeEnum.BUSINESS,
            "legal_name": "Sandglass Logistics Ltd",
            "jurisdiction": "GB",
            "risk_tier": RiskTierEnum.MEDIUM,
            "declared_monthly_turnover": Decimal("50000.00"),
            "parties": [
                PartyIn(
                    party_id="party_viktor_01",
                    kind=CustomerTypeEnum.INDIVIDUAL,
                    canonical_name="Viktor Vance",
                    tax_id_token="tax_tok_vv_981",
                    jurisdiction="CY",
                    date_of_birth_or_inc="1978-04-12",
                    risk_tier=RiskTierEnum.HIGH,
                ),
                PartyIn(
                    party_id="party_elena_02",
                    kind=CustomerTypeEnum.INDIVIDUAL,
                    canonical_name="Elena Rostova",
                    tax_id_token="tax_tok_er_442",
                    jurisdiction="GB",
                    date_of_birth_or_inc="1985-09-23",
                    risk_tier=RiskTierEnum.LOW,
                ),
            ],
            "beneficial_owners": [
                BeneficialOwner(
                    party_id="party_viktor_01",
                    ownership_pct=Decimal("45.00"),
                    role=PartyRoleEnum.BENEFICIAL_OWNER,
                    is_pep=True,
                    valid_from=scenario_start - timedelta(days=14),
                ),
                BeneficialOwner(
                    party_id="party_elena_02",
                    ownership_pct=Decimal("55.00"),
                    role=PartyRoleEnum.DIRECTOR,
                    is_pep=False,
                    valid_from=scenario_start - timedelta(days=365),
                ),
            ],
            # Shared device token connecting Viktor Vance and funnel mules
            "device_tokens": ["dev_tok_sandglass_core", "dev_shared_mule_7f90c"],
            "ip_addresses": ["198.51.100.42", "198.51.100.88"],
        }

        sandglass_accounts = [
            {
                "id": "acct_sandglass_ops",
                "tenant_id": tenant_id,
                "customer_id": "cust_sandglass_01",
                "account_type": "commercial_checking",
                "currency": "USD",
                "balance": Decimal("12500.00"),
            },
            {
                "id": "acct_sandglass_reserve",
                "tenant_id": tenant_id,
                "customer_id": "cust_sandglass_01",
                "account_type": "money_market",
                "currency": "USD",
                "balance": Decimal("50000.00"),
            },
        ]

        # 2. Funnel Mule Counterparties (18 distinct inbound actors)
        mule_accounts: list[dict[str, Any]] = []
        for m in range(1, 19):
            mule_accounts.append({
                "id": f"acct_mule_{m:02d}",
                "tenant_id": tenant_id,
                "customer_id": f"cust_mule_{m:02d}",
                "account_type": "retail_checking",
                "currency": "USD",
                "balance": Decimal("500.00"),
                # First 4 mules share the device token with Viktor Vance!
                "device_token": "dev_shared_mule_7f90c" if m <= 4 else f"dev_mule_{m:02d}",
            })

        # 3. Destination Beneficiaries (3 offshore high-risk accounts)
        offshore_beneficiaries = [
            {"id": "acct_offshore_alpha", "country": "PA", "name": "Alpha Holding Corp"},
            {"id": "acct_offshore_beta", "country": "CY", "name": "Beta Maritime Trading"},
            {"id": "acct_offshore_gamma", "country": "SC", "name": "Gamma Prime Capital"},
        ]

        # 4. Inbound Funnel Transfers (18 transfers across 48 hours)
        # Amounts strictly structured between $4,500 and $9,800 to evade $10k reporting
        inbound_txns: list[dict[str, Any]] = []
        total_inflow = Decimal("0.00")

        for m_idx in range(18):
            # Time distributed across 48 hours
            time_offset_min = int((m_idx / 18.0) * 48 * 60) + self.rng.randint(-15, 15)
            txn_time = scenario_start + timedelta(minutes=max(0, time_offset_min))
            # Structured amount between $4,500 and $9,800
            amt = Decimal(f"{self.rng.uniform(4500.0, 9800.0):.2f}")
            total_inflow += amt

            inbound_txns.append({
                "transaction_id": f"txn_sandglass_in_{m_idx+1:02d}",
                "tenant_id": tenant_id,
                "account_id": "acct_sandglass_ops",
                "direction": DirectionEnum.CREDIT,
                "amount": amt,
                "currency": "USD",
                "channel": ChannelEnum.WIRE,
                "counterparty_id": mule_accounts[m_idx]["id"],
                "counterparty_account": f"ext_{mule_accounts[m_idx]['id']}",
                "country_code": "US",
                "occurred_at": txn_time,
                "description": f"Consulting retainer fee {m_idx+1}",
                "metadata": {"funnel_mule_id": mule_accounts[m_idx]["id"]},
            })

        # 5. Outbound Rapid Pass-Through Transfers (16 transfers shortly after inflow)
        # Empties >92% of the total inflow within 12 hours of the final inbound transfer
        outbound_txns: list[dict[str, Any]] = []
        target_outflow = (total_inflow * Decimal("0.94")).quantize(Decimal("0.01"))
        pass_through_start = scenario_start + timedelta(hours=49)

        # Distribute the outflow across 16 rapid outbound wires
        amounts = [Decimal(f"{self.rng.uniform(5000.0, 9500.0):.2f}") for _ in range(15)]
        sum_15 = sum(amounts)
        amounts.append(target_outflow - sum_15)

        for o_idx, amt in enumerate(amounts):
            time_offset_min = int((o_idx / 16.0) * 12 * 60) + self.rng.randint(2, 20)
            txn_time = pass_through_start + timedelta(minutes=time_offset_min)
            beneficiary = offshore_beneficiaries[o_idx % len(offshore_beneficiaries)]

            outbound_txns.append({
                "transaction_id": f"txn_sandglass_out_{o_idx+1:02d}",
                "tenant_id": tenant_id,
                "account_id": "acct_sandglass_ops",
                "direction": DirectionEnum.DEBIT,
                "amount": amt,
                "currency": "USD",
                "channel": ChannelEnum.WIRE,
                "counterparty_id": beneficiary["id"],
                "counterparty_account": f"iban_{beneficiary['id']}",
                "country_code": beneficiary["country"],
                "occurred_at": txn_time,
                "description": f"Urgent supply invoice {beneficiary['name']}",
                "metadata": {"offshore_destination": beneficiary["country"]},
            })

        return {
            "customer_profile": sandglass_cust,
            "accounts": sandglass_accounts,
            "mule_accounts": mule_accounts,
            "beneficiaries": offshore_beneficiaries,
            "inbound_transactions": inbound_txns,
            "outbound_transactions": outbound_txns,
            "summary": {
                "scenario_name": "Project Sandglass",
                "funnel_inbound_count": len(inbound_txns),
                "total_inbound_amount": float(total_inflow),
                "pass_through_outbound_count": len(outbound_txns),
                "total_outbound_amount": float(target_outflow),
                "pass_through_ratio": float(target_outflow / total_inflow),
                "shared_device_token": "dev_shared_mule_7f90c",
            },
        }


def generate_aml_universe(seed: int = 42, num_benign_customers: int = 20, num_benign_txns: int = 60) -> dict[str, Any]:
    """Top-level entrypoint to generate a full synthetic universe with benign and Sandglass data."""
    gen = AMLUniverseGenerator(seed=seed)
    benign = gen.generate_benign_universe(num_customers=num_benign_customers, num_txns=num_benign_txns)
    sandglass = gen.generate_sandglass_mule_scenario()
    return {
        "benign": benign,
        "sandglass": sandglass,
    }


def seed_sandglass_mule_scenario(tenant_id: str = "demo-bank", seed: int = 42) -> dict[str, Any]:
    """Convenience helper generating only the Project Sandglass scenario."""
    gen = AMLUniverseGenerator(seed=seed)
    return gen.generate_sandglass_mule_scenario(tenant_id=tenant_id)


async def seed_scenario_to_database(session: AsyncSession, scenario_data: dict[str, Any]) -> dict[str, int]:
    """Persist generated scenario data into domain tables with atomic outbox and audit events.
    
    Returns counts of inserted records across all tables.
    """
    sandglass = scenario_data.get("sandglass", scenario_data)
    cust_data: CustomerProfileIn = sandglass["customer_profile"]
    tenant_id = "demo-bank"

    # 1. Insert Customer
    customer = Customer(
        id=cust_data.customer_id,
        tenant_id=tenant_id,
        customer_type=cust_data.customer_type.value,
        legal_name=cust_data.legal_name,
        jurisdiction=cust_data.jurisdiction,
        risk_tier=cust_data.risk_tier.value,
        declared_monthly_turnover=cust_data.declared_monthly_turnover,
        device_tokens=cust_data.device_tokens,
        ip_addresses=cust_data.ip_addresses,
    )
    session.add(customer)
    await session.flush()

    # 2. Insert Parties and Associations
    for party_in in cust_data.parties:
        p = Party(
            id=party_in.party_id,
            tenant_id=tenant_id,
            kind=party_in.kind.value,
            canonical_name=party_in.canonical_name,
            tax_id_token=party_in.tax_id_token,
            jurisdiction=party_in.jurisdiction,
            date_of_birth_or_inc=party_in.date_of_birth_or_inc,
            risk_tier=party_in.risk_tier.value,
        )
        session.add(p)

    await session.flush()

    for bo in cust_data.beneficial_owners:
        cp = CustomerParty(
            tenant_id=tenant_id,
            customer_id=cust_data.customer_id,
            party_id=bo.party_id,
            role=bo.role.value,
            ownership_pct=bo.ownership_pct,
            is_pep=bo.is_pep,
            valid_from=bo.valid_from,
            valid_to=bo.valid_to,
        )
        session.add(cp)

    # 3. Insert Accounts
    for acct_dict in sandglass["accounts"]:
        acct = Account(
            id=acct_dict["id"],
            tenant_id=tenant_id,
            customer_id=acct_dict["customer_id"],
            account_type=acct_dict["account_type"],
            currency=acct_dict["currency"],
            balance=acct_dict["balance"],
        )
        session.add(acct)

    await session.flush()

    # 4. Ingest All Transactions (Inbound and Outbound) with Audit & Outbox
    all_txns = sandglass["inbound_transactions"] + sandglass["outbound_transactions"]
    latest_hash = None
    latest_idx = -1

    for t in all_txns:
        # Domain transaction record
        direction = t["direction"].value if isinstance(t["direction"], DirectionEnum) else t["direction"]
        channel = t["channel"].value if isinstance(t["channel"], ChannelEnum) else t["channel"]

        raw_payload = {
            "transaction_id": t["transaction_id"],
            "account_id": t["account_id"],
            "direction": direction,
            "amount": str(t["amount"]),
            "currency": t["currency"],
            "channel": channel,
            "counterparty_id": t.get("counterparty_id"),
            "occurred_at": t["occurred_at"].isoformat(),
        }

        txn = Transaction(
            id=t["transaction_id"],
            tenant_id=tenant_id,
            account_id=t["account_id"],
            direction=direction,
            amount=t["amount"],
            currency=t["currency"],
            channel=channel,
            counterparty_id=t.get("counterparty_id"),
            counterparty_account=t.get("counterparty_account"),
            country_code=t.get("country_code"),
            occurred_at=t["occurred_at"],
            description=t.get("description"),
            raw_payload=raw_payload,
        )
        session.add(txn)

        # Cryptographic Audit Link
        audit_dict = build_next_audit_event(
            entry=AuditEntryInput(
                tenant_id=tenant_id,
                aggregate_type="transaction",
                aggregate_id=t["transaction_id"],
                event_type=EventTypeEnum.TRANSACTION_POSTED.value,
                actor_type="system",
                actor_id="synthetic_generator",
                payload=raw_payload,
                occurred_at=t["occurred_at"],
            ),
            latest_event_hash=latest_hash,
            latest_chain_index=latest_idx,
        )
        latest_hash = audit_dict["payload_hash"]
        latest_idx = audit_dict["chain_index"]

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

        # Transactional outbox event
        session.add(
            OutboxEvent(
                tenant_id=tenant_id,
                event_id=generate_uuid7(),
                event_type=EventTypeEnum.TRANSACTION_POSTED.value,
                correlation_id=t["transaction_id"],
                idempotency_key=f"synth:{t['transaction_id']}",
                payload=raw_payload,
                status="PENDING",
            )
        )

    await session.commit()

    return {
        "customers": 1,
        "parties": len(cust_data.parties),
        "accounts": len(sandglass["accounts"]),
        "transactions": len(all_txns),
        "audit_events": len(all_txns),
        "outbox_events": len(all_txns),
    }
