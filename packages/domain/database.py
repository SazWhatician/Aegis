"""Database engine, connection pooling, and async session management."""

import os
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from packages.domain.models import Base

DEFAULT_DB_URL = "sqlite+aiosqlite:///./aegis.db"

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_database_url() -> str:
    """Resolve database URL from environment or fallback to local SQLite."""
    return os.environ.get("AEGIS_DATABASE_URL") or os.environ.get("DATABASE_URL") or DEFAULT_DB_URL


def get_engine(db_url: str | None = None, echo: bool = False) -> AsyncEngine:
    """Get or create singleton async SQLAlchemy engine."""
    global _engine, _session_factory
    if _engine is None or (db_url is not None and str(_engine.url) != db_url):
        url = db_url or get_database_url()
        is_sqlite = url.startswith("sqlite")

        engine_kwargs = {"echo": echo}
        if is_sqlite:
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url or url.endswith("://"):
                from sqlalchemy.pool import StaticPool
                engine_kwargs["poolclass"] = StaticPool

        _engine = create_async_engine(url, **engine_kwargs)
        _session_factory = None
    return _engine


def get_session_factory(target_engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Get or create async session factory."""
    global _session_factory
    if _session_factory is None or target_engine is not None:
        eng = target_engine or get_engine()
        factory = async_sessionmaker(
            bind=eng,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        if target_engine is None:
            _session_factory = factory
        return factory
    return _session_factory


async def close_engine() -> None:
    """Properly dispose engine connection pools."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def init_db(target_engine: AsyncEngine | None = None) -> None:
    """Create all domain tables if they do not exist."""
    eng = target_engine or get_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for yielding transactional database sessions."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
