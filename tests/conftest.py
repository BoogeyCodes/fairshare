from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from fairshare.app import create_app
from fairshare.config import Settings
from fairshare.db import Database


@pytest.fixture
def app():
    # A fresh shared in-memory database per test.
    db = Database("sqlite://")
    return create_app(Settings(database_url="sqlite://", secret_key="test-secret"), database=db)


@pytest.fixture
def make_client(app):
    """Factory for independent clients (separate cookie jars) against the same app/db."""
    return lambda: TestClient(app)


@pytest.fixture
def client(make_client):
    return make_client()


def register(client: TestClient, email: str, name: str = "User", password: str = "password123") -> dict:
    resp = client.post(
        "/api/auth/register", json={"email": email, "display_name": name, "password": password}
    )
    resp.raise_for_status()
    return resp.json()
