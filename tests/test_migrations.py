"""Migrations must produce exactly the schema the models describe. Needs a disposable Postgres database."""

import os
import subprocess
import sys

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import Base

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="set TEST_POSTGRES_URL to run migration tests")


def alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args], env=os.environ | {"DATABASE_URL": POSTGRES_URL}, check=True
    )


async def test_migrations_match_models():
    engine = create_async_engine(POSTGRES_URL.replace("postgresql://", "postgresql+asyncpg://", 1))
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

    alembic("upgrade", "head")
    alembic("downgrade", "-1")
    alembic("upgrade", "head")

    async with engine.connect() as conn:
        diff = await conn.run_sync(lambda sync: compare_metadata(MigrationContext.configure(sync), Base.metadata))
    await engine.dispose()
    assert diff == []
