"""FastAPI dependency injection utilities for authentication and tenancy."""

from typing import Annotated
from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession
from packages.domain.database import get_db_session

# Standard tenant header with safe fallback for dev/demo
DEFAULT_TENANT_ID = "demo-bank"


async def get_tenant_id(
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-ID")] = None,
) -> str:
    """Extract and validate tenant ID from request headers."""
    return x_tenant_id.strip() if x_tenant_id and x_tenant_id.strip() else DEFAULT_TENANT_ID


async def get_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    """Extract client idempotency key if supplied."""
    return idempotency_key.strip() if idempotency_key and idempotency_key.strip() else None
