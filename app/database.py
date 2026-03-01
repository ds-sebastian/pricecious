import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

# Lazy engine initialization — don't crash at import time if DATABASE_URL is missing
_state: dict = {"engine": None, "session_factory": None}


def _get_database_url() -> str:
    """Resolve and normalize the DATABASE_URL."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is required. " "Set it before making any database calls.")

    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    return url


def _init_engine():
    """Initialize engine and session factory lazily on first use."""
    if _state["engine"] is not None:
        return

    database_url = _get_database_url()

    engine_kwargs = {
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
    }

    if "sqlite" not in database_url:
        engine_kwargs.update({"pool_size": 5, "max_overflow": 10})

    _state["engine"] = create_async_engine(database_url, **engine_kwargs)

    _state["session_factory"] = async_sessionmaker(
        bind=_state["engine"],
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


class _AsyncSessionLocalProxy:
    """Proxy that lazily initializes the engine on first session creation."""

    def __call__(self):
        _init_engine()
        return _state["session_factory"]()


AsyncSessionLocal = _AsyncSessionLocalProxy()


class Base(AsyncAttrs, DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    _init_engine()
    async with _state["session_factory"]() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
