"""Strict Pydantic v2 contracts for KYC, customers, and corporate ownership."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


class CustomerTypeEnum(str, Enum):
    """Classification of customer entity."""
    INDIVIDUAL = "individual"
    BUSINESS = "business"


class RiskTierEnum(str, Enum):
    """Initial compliance risk classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PROHIBITED = "prohibited"


class PartyRoleEnum(str, Enum):
    """Relationship of a related party to the principal customer."""
    BENEFICIAL_OWNER = "beneficial_owner"
    DIRECTOR = "director"
    SIGNATORY = "signatory"
    PARENT_COMPANY = "parent_company"
    SUBSIDIARY = "subsidiary"
    TRUSTEE = "trustee"


class BeneficialOwner(BaseModel):
    """Ultimate Beneficial Owner (UBO) declaration for legal entities."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    party_id: str = Field(..., min_length=1, description="Unique identifier for the beneficial party")
    ownership_pct: Decimal = Field(..., ge=0, le=100, max_digits=5, decimal_places=2, description="Percentage of direct/indirect equity ownership (0-100%)")
    role: PartyRoleEnum = Field(default=PartyRoleEnum.BENEFICIAL_OWNER, description="Specific role or title held")
    is_pep: bool = Field(default=False, description="Flag indicating Politically Exposed Person status")
    valid_from: datetime = Field(..., description="Timestamp when beneficial ownership relationship commenced")
    valid_to: datetime | None = Field(default=None, description="Timestamp when ownership ceased (if applicable)")


class PartyIn(BaseModel):
    """Related legal or natural party connected to an account or customer."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    party_id: str = Field(..., min_length=1, description="Identifier for this related party")
    kind: CustomerTypeEnum = Field(..., description="Natural person vs corporate entity")
    canonical_name: str = Field(..., min_length=1, max_length=255, description="Official legal name or full individual name")
    tax_id_token: str | None = Field(default=None, description="Hashed or tokenized tax identification (SSN/EIN/TIN)")
    jurisdiction: str = Field(..., pattern=r"^[A-Z]{2}$", description="2-letter ISO-3166-1 alpha-2 jurisdiction of registration or citizenship")
    date_of_birth_or_inc: str | None = Field(default=None, description="ISO-8601 date string of birth or incorporation")
    risk_tier: RiskTierEnum = Field(default=RiskTierEnum.LOW, description="Screening risk classification")


class CustomerProfileIn(BaseModel):
    """Customer profile intake contract for onboarding and refresh."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: str = Field(..., min_length=1, description="Unique primary customer identifier")
    customer_type: CustomerTypeEnum = Field(..., description="Individual retail vs legal corporate entity")
    legal_name: str = Field(..., min_length=1, max_length=255, description="Full registered legal name")
    jurisdiction: str = Field(..., pattern=r"^[A-Z]{2}$", description="2-letter ISO-3166-1 alpha-2 country of incorporation or residence")
    risk_tier: RiskTierEnum = Field(default=RiskTierEnum.LOW, description="Initial risk tier assignment")
    declared_monthly_turnover: Decimal = Field(
        ..., ge=0, max_digits=18, decimal_places=2, description="Expected monthly inflow/outflow volume in base currency"
    )
    parties: list[PartyIn] = Field(default_factory=list, description="Related corporate officers, signatories, or directors")
    beneficial_owners: list[BeneficialOwner] = Field(default_factory=list, description="Declared beneficial ownership graph")
    device_tokens: list[str] = Field(default_factory=list, description="Associated device fingerprint tokens for entity resolution")
    ip_addresses: list[str] = Field(default_factory=list, description="Observed IP addresses for network clustering")
