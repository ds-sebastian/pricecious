import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop tables
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    
    # Mock scheduler to prevent event loop issues
    from unittest.mock import patch, MagicMock
    
    # Mock SessionLocal to return the test session
    # We need a factory that returns the session, but SessionLocal() creates a new session.
    # So we mock SessionLocal to return a mock that acts like a session but is actually our test session.
    # However, our test session is scoped to the function.
    # A better approach is to use a separate engine for the background task or share the connection.
    # Since we use SQLite in-memory, sharing connection is key.
    # But process_item_check creates a NEW session.
    
    # Let's mock SessionLocal to return a session bound to the SAME engine.
    # But we are using StaticPool, so all sessions share the same connection.
    # So we just need SessionLocal to return a session from TestingSessionLocal.
    
    with patch("app.main.scheduler.start"), \
         patch("app.main.scheduler.shutdown"), \
         patch("app.database.SessionLocal", side_effect=TestingSessionLocal):
        with TestClient(app) as c:
            yield c
            
    app.dependency_overrides.clear()
