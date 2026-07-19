from __future__ import annotations

# ruff: noqa: E402, I001

import os
import tempfile
from pathlib import Path

os.environ["AERORAMP_ENVIRONMENT"] = "test"
TEST_ROOT = Path(tempfile.gettempdir()) / f"aeroramp-tests-{os.getpid()}"
TEST_DB = TEST_ROOT / "test-aeroramp.db"
os.environ["AERORAMP_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["AERORAMP_JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256"
os.environ["AERORAMP_UPLOAD_DIR"] = (TEST_ROOT / "storage/uploads").as_posix()
os.environ["AERORAMP_EVIDENCE_DIR"] = (TEST_ROOT / "storage/evidence").as_posix()
os.environ["AERORAMP_OBSERVATION_DIR"] = (TEST_ROOT / "storage/observations").as_posix()

import pytest
from aeroramp.main import app
from aeroramp.db.session import engine
from fastapi.testclient import TestClient

from scripts.seed import seed


@pytest.fixture(scope="session", autouse=True)
def clean_files() -> None:
    TEST_ROOT.mkdir(parents=True, exist_ok=True)
    TEST_DB.unlink(missing_ok=True)
    yield
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture()
def seeded() -> dict[str, str]:
    return seed(reset=True)


@pytest.fixture()
def client(seeded: dict[str, str]) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": "admin@aeroramp.local", "password": "AeroRamp-Dev-2026!"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
