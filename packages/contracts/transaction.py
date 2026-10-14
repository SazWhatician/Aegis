"""Strict Pydantic v2 contracts for financial transactions in AEGIS."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class DirectionEnum(str, Enum):
    """Transaction flow direction relative to the subject account."""
    CREDIT = "credit"
    DEBIT = "debit"


class ChannelEnum(str, Enum):
    """Payment transfer channel."""
    WIRE = "wire"
    ACH = "ach"
    CARD = "card"
    SECURITIES = "securities"
    CASH = "cash"
    CRYPTO = "crypto"


class TransactionStatusEnum(str, Enum):
    """Lifecycle settlement status of a transaction."""
    SETTLED = "settled"
    PENDING = "pending"
    DECLINED = "declined"
    REVERSED = "reversed"


class TransactionIn(BaseModel):
    """Inbound transaction contract with strict validation.
    
    Adheres to the Ponytail protocol:
    - extra="forbid" rejects unexpected properties and payload pollution
    - Decimal ensures exact currency math without IEEE-754 floating-point inaccuracies
    - Regex patterns enforce ISO-4217 (currencies) and ISO-3166-1 alpha-2 (country codes)
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str = Field(..., min_length=1, description="Unique transaction identifier from source system")
    account_id: str = Field(..., min_length=1, description="Account identifier subject to this transaction")
    occurred_at: datetime = Field(..., description="Timestamp of transaction execution in ISO-8601 format")
    direction: DirectionEnum = Field(..., description="Direction of funds relative to account")
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2, description="Monetary value, must be strictly positive")
    currency: str = Field(..., pattern=r"^[A-Z]{3}$", description="3-letter ISO-4217 currency code")
    channel: ChannelEnum = Field(..., description="Payment execution rail or channel")
    counterparty_id: str | None = Field(default=None, description="Known internal/external counterparty entity ID")
    counterparty_account: str | None = Field(default=None, description="External counterparty account or routing number")
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$", description="2-letter ISO-3166-1 alpha-2 country code")
    description: str | None = Field(default=None, max_length=500, description="Payment narrative or memo")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary sanitized key-value attributes")
