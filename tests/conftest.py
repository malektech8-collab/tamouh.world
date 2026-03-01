"""
Pytest configuration and shared fixtures.

Sets DATABASE_URL to SQLite before any app imports, creates required
directories, and provides test_client / test_db / sample_pdf_file fixtures.
"""

import os
import tempfile

# Must be set BEFORE any app module is imported so pydantic-settings picks it up.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-32chars!!")

# StaticFiles(directory=...) raises RuntimeError if the directory doesn't exist.
# Create them here so importing app.main doesn't crash during collection.
os.makedirs("static", exist_ok=True)
os.makedirs("outputs", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite + threads
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def mock_celery_task():
    """Prevent all tests from hitting Redis by mocking the Celery task."""
    with patch("app.main.process_resume_job") as mock_task:
        mock_task.delay.return_value = MagicMock(id="mock-task-id")
        yield mock_task


@pytest.fixture
def test_db():
    """
    Provide a fresh SQLite session for each test.

    Tables are created before the test and dropped afterwards so every test
    runs against an empty database.
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_client(test_db):
    """
    Provide a FastAPI TestClient whose database dependency is overridden to use
    the same session as the test (test_db), enabling direct DB inspection.
    """
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_pdf_file():
    """
    Create a minimal but magic-byte-valid PDF file in a temp location.
    The file is deleted after the test completes.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False, mode="wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF")
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)
