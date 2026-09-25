"""Shared pytest fixtures: isolated SQLite database + TestClient.

The environment is configured before any ``app.*`` import so the engine binds to
a temporary SQLite file instead of the development database.
"""

import os
import tempfile
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="azuma-tests-")
os.environ["DB_DRIVER"] = "sqlite"
os.environ["DB_PATH"] = str(Path(_TMP_DIR) / "test.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    """Recreate the schema and clear middleware state before every test."""
    from app import database, models, security

    models.Base.metadata.drop_all(bind=database.engine)
    models.Base.metadata.create_all(bind=database.engine)
    security.reset_rate_limiter()
    yield


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def fake_analyzer(monkeypatch):
    """Replace the network analyzer with canned forms/OAuth/cookies."""
    from app import analyzer

    async def fake_analyze(target: str) -> dict:
        return {
            "final_url": "https://example.com/",
            "title": "Example Domain",
            "forms": [
                analyzer.FormData(
                    page_url="https://example.com/",
                    action="/login",
                    method="POST",
                    enctype="application/x-www-form-urlencoded",
                    is_secure=False,
                    fields=[
                        analyzer.FormFieldData(
                            name="username",
                            input_type="text",
                            value=None,
                            required=True,
                            autocomplete="username",
                            placeholder=None,
                        ),
                        analyzer.FormFieldData(
                            name="authenticity_token",
                            input_type="hidden",
                            value="aB3xY9qW7eR2tU5iO8pL1kM4nJ6hG0vC",
                            required=False,
                            autocomplete=None,
                            placeholder=None,
                            is_csrf=True,
                        ),
                    ],
                    redirect_chain=[{"url": "https://example.com/login", "status": 302}],
                )
            ],
            "oauth_flows": [
                analyzer.OAuthFlowData(
                    endpoint="https://accounts.example.com/oauth/authorize",
                    flow_type="authorization_code",
                    client_id="app-123",
                    redirect_uri="https://example.com/cb",
                    scope="openid",
                    uses_state=True,
                    weakness=[],
                )
            ],
            "session_cookies": [
                analyzer.SessionCookieData(
                    name="sessionid",
                    value_preview="abc123",
                    domain=None,
                    path="/",
                    http_only=True,
                    secure=True,
                    same_site="Lax",
                    max_age="3600",
                )
            ],
            "session_findings": [
                analyzer.SessionFindingData(
                    kind="logout",
                    severity="low",
                    title="Logout uses state-changing GET",
                    description="Logout endpoint https://example.com/logout is reachable via GET (link).",
                    target_url="https://example.com/logout",
                    method="GET",
                    csrf_present=None,
                    evidence={"source": "link", "method": "GET"},
                )
            ],
        }

    monkeypatch.setattr(analyzer, "analyze_target", fake_analyze)
    return fake_analyze


@pytest.fixture()
def create_analysis(client):
    """POST a valid discovery run and return the parsed response."""

    def _create(target: str = "https://example.com") -> dict:
        response = client.post("/api/forms/discover", json={"target": target})
        assert response.status_code == 200, response.text
        return response.json()

    return _create
