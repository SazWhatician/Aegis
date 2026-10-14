"""Pytest configuration and shared async fixtures for AEGIS test suite."""

import asyncio
import os
from collections.abc import AsyncGenerator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Set test environment database
os.environ["AEGIS_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from apps.api.main import app
from packages.domain.database import close_engine, get_engine, get_session_factory, init_db


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_test_database():
    """Create fresh database tables before each test and dispose afterwards."""
    engine = get_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    yield
    await close_engine()


@pytest.fixture
def client():
    """Synchronous test client with active lifespan context."""
    with TestClient(app) as test_client:
        yield test_client
