import logging
import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

# Remove hardcoded credentials - require environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. Example: postgresql+asyncpg://user:password@localhost:5432/pricewatch"
    )

# Ensure usage of async driver
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

# Connection pool configuration
#  pool_size: number of connections to maintain
#  max_overflow: max number of connections above pool_size
#  pool_pre_ping: verify connections before using (prevents stale connections)
#  pool_recycle: recycle connections after N seconds (prevents timeout issues)

engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 3600,  # 1 hour
    "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
}

# SQLite (especially :memory: or with StaticPool) does not support pool_size/max_overflow
if "sqlite" not in DATABASE_URL:
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 10

engine = create_async_engine(DATABASE_URL, **engine_kwargs)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        # Session is closed automatically by the context manager
