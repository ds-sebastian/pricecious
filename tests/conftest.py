import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Set env var before importing app.database
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.database import Base, get_db
from app.main import app

# Use in-memory SQLite for testing
# Note: sqlite+aiosqlite is needed for async sqlite
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(scope="function")
async def db() -> AsyncGenerator[AsyncSession, None]:
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Mock scheduler and ScraperService to prevent real browser startup
    with (
        patch("app.main.scheduler.start"),
        patch("app.main.scheduler.shutdown"),
        patch("app.services.scraper_service.ScraperService.initialize", new_callable=AsyncMock),
        patch("app.services.scraper_service.ScraperService.shutdown", new_callable=AsyncMock),
        patch(
            "app.database.get_db", override_get_db
        ),  # Direct patch if needed, but dependency_override is usually enough
        patch(
            "app.database.AsyncSessionLocal", return_value=db
        ),  # Mock the session local used in services/background tasks
    ):
        # We need to mock AsyncSessionLocal to act as a context manager that returns OUR session
        # But AsyncSessionLocal() returns an AsyncSession
        # In code: async with AsyncSessionLocal() as session:
        # We want that session to be `db`.

        class MockSessionContext:
            def __init__(self, session):
                self.session = session

            async def __aenter__(self):
                return self.session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        with patch("app.database.AsyncSessionLocal", side_effect=lambda: MockSessionContext(db)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                yield c

    app.dependency_overrides.clear()
