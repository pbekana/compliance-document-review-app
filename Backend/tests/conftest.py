import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

TEST_DB_PATH = Path("/tmp/compliance_document_review_test.sqlite3")
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-internal-token")
os.environ.setdefault("AI_SERVICE_URL", "http://ai:8001")
os.environ.setdefault("DATA_ENGINEERING_URL", "http://data-engineering:8002")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault(
    "CORS_ORIGIN",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,https://compliance-document-review-frontend.vercel.app",
)

from app.db.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

Base.metadata.create_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(text(f'DELETE FROM "{table.name}"'))
    session.commit()
    try:
        yield session
    finally:
        session.close()
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(text(f'DELETE FROM "{table.name}"'))
        session.commit()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
