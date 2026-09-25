import io
import os
import socket
import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

_tmp = Path(tempfile.mkdtemp(prefix="pricecious-tests-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_tmp / 'test.db'}"
os.environ["SCREENSHOT_DIR"] = str(_tmp / "screenshots")
os.environ["STATIC_DIR"] = str(_tmp / "static")
os.environ["CORS_ORIGINS"] = "https://trusted.example"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db():
    async with SessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def public_dns(monkeypatch):
    """Resolve IP literals and localhost normally and every other hostname to a public IP, without real DNS."""
    real_getaddrinfo = socket.getaddrinfo

    def getaddrinfo(host, port, *args, **kwargs):
        try:
            return real_getaddrinfo(host, port, type=socket.SOCK_STREAM, flags=socket.AI_NUMERICHOST)
        except socket.gaierror:
            address = "127.0.0.1" if host == "localhost" else "93.184.216.34"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port or 0))]

    monkeypatch.setattr("app.urls.socket.getaddrinfo", getaddrinfo)


@pytest.fixture
def png() -> bytes:
    """A screenshot with enough detail to pass the blank-page checks."""
    image = Image.effect_noise((400, 300), 80).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
