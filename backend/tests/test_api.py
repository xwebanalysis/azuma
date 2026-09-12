"""API integration tests: health, persistence, history, export, delete, WS."""

from datetime import datetime, timedelta


def test_health_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["tool"] == "azuma"
    assert body["version"]


def test_health_reports_database_error(client, monkeypatch):
    from app import database

    monkeypatch.setattr(database, "ping", lambda: False)
    response = client.get("/api/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["database"] == "error"


def test_discover_persists_and_list(client, fake_analyzer, create_analysis):
    created = create_analysis()
    analysis = created["analysis"]

    assert analysis["status"] == "COMPLETED"
    assert created["form_count"] == 1
    assert created["oauth_flow_count"] == 1
    assert created["session_cookie_count"] == 1
    assert analysis["forms"][0]["fields"][1]["is_csrf"] is True

    listed = client.get("/api/analyses").json()
    assert len(listed) == 1
    assert listed[0]["id"] == analysis["id"]
    assert listed[0]["form_count"] == 1


def test_discover_upstream_error_envelope(client, monkeypatch):
    from app import analyzer

    async def failing(target: str):
        raise analyzer.TargetError("Failed to fetch target: connection refused")

    monkeypatch.setattr(analyzer, "analyze_target", failing)
    response = client.post("/api/forms/discover", json={"target": "https://bad.example"})
    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "UPSTREAM_ERROR"
    assert body["error"]["retryable"] is True

    listed = client.get("/api/analyses").json()
    assert listed[0]["status"] == "ERROR"


def test_validation_error_envelope(client):
    response = client.post("/api/forms/discover", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_detail_export_and_delete(client, fake_analyzer, create_analysis):
    created = create_analysis()
    analysis_id = created["analysis"]["id"]

    detail = client.get(f"/api/analyses/{analysis_id}")
    assert detail.status_code == 200
    assert len(detail.json()["forms"]) == 1

    export_json = client.get(f"/api/analyses/{analysis_id}/export?format=json")
    assert export_json.status_code == 200
    assert export_json.headers["content-disposition"] == (
        f'attachment; filename="azuma-analysis-{analysis_id}.json"'
    )
    assert export_json.json()["forms"][0]["action"] == "/login"

    export_csv = client.get(f"/api/analyses/{analysis_id}/export?format=csv")
    assert export_csv.status_code == 200
    assert export_csv.headers["content-type"].startswith("text/csv")
    assert "attachment" in export_csv.headers["content-disposition"]
    lines = export_csv.text.splitlines()
    assert lines[0].startswith("kind,analysis_id,target")
    assert any(line.startswith("form,") and "/login" in line for line in lines)
    assert any(line.startswith("session_cookie,") and "sessionid" in line for line in lines)

    bad_format = client.get(f"/api/analyses/{analysis_id}/export?format=xml")
    assert bad_format.status_code == 422

    deleted = client.delete(f"/api/analyses/{analysis_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/analyses/{analysis_id}").status_code == 404
    assert client.get("/api/analyses").json() == []


def test_delete_all(client, fake_analyzer, create_analysis):
    create_analysis("https://one.example")
    create_analysis("https://two.example")
    assert len(client.get("/api/analyses").json()) == 2

    assert client.delete("/api/analyses").status_code == 204
    assert client.get("/api/analyses").json() == []


def test_websocket_event_shape_and_analysis_id(client, fake_analyzer):
    with client.websocket_connect("/api/forms/live?target=https://example.com") as ws:
        events = [ws.receive_json() for _ in range(6)]

    assert [event["seq"] for event in events] == [1, 2, 3, 4, 5, 6]
    assert [event["type"] for event in events] == [
        "analysis_started",
        "analysis_progress",
        "item_found",
        "item_found",
        "item_found",
        "analysis_completed",
    ]
    assert all(event["tool"] == "azuma" for event in events)

    analysis_id = events[0]["analysis_id"]
    assert isinstance(analysis_id, str)
    assert analysis_id.isdigit()
    # analysis_id is the persisted row id (not the target)
    persisted = client.get("/api/analyses").json()
    assert persisted[0]["id"] == int(analysis_id)

    for event in events:
        parsed = datetime.fromisoformat(event["ts"])
        assert parsed.utcoffset() == timedelta(0)
        assert event["analysis_id"] == analysis_id

    assert events[5]["payload"]["form_count"] == 1
    assert events[5]["payload"]["session_cookie_count"] == 1


def test_rate_limit_envelope(client, monkeypatch):
    from app import security

    monkeypatch.setattr(security, "RATE_LIMIT_MAX", 2)
    security.reset_rate_limiter()

    assert client.get("/api/analyses").status_code == 200
    assert client.get("/api/analyses").status_code == 200
    blocked = client.get("/api/analyses")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"

    assert client.get("/api/health").status_code == 200


def test_optional_jwt_auth(client, monkeypatch):
    from app import security

    monkeypatch.setattr(security, "JWT_SECRET", "test-secret")
    monkeypatch.setattr(security, "AUTH_REQUIRED", True)
    monkeypatch.setattr(security, "AUTH_PASSWORD", "s3cret")

    assert client.get("/api/analyses").status_code == 401

    token_response = client.post("/api/auth/token", json={"password": "s3cret"})
    assert token_response.status_code == 200
    token = token_response.json()["token"]

    authorized = client.get("/api/analyses", headers={"Authorization": f"Bearer {token}"})
    assert authorized.status_code == 200

    wrong = client.post("/api/auth/token", json={"password": "nope"})
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "UNAUTHORIZED"

    assert security.validate_ws_token(None) is False
    assert security.validate_ws_token(token) is True
