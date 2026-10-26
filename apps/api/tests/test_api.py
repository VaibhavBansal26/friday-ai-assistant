from uuid import uuid4

from fastapi.testclient import TestClient

from friday.main import app


client = TestClient(app)


def test_readiness_reports_memory_backend():
    response = client.get("/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "persistence": "memory"}


def test_desktop_cors_preflight_allows_session_authorization_header():
    response = client.options(
        "/v1/settings",
        headers={
            "origin": "http://127.0.0.1:1420",
            "access-control-request-method": "GET",
            "access-control-request-headers": "authorization,x-friday-session,content-type",
        },
    )
    assert response.status_code == 200
    allowed = response.headers["access-control-allow-headers"].lower()
    assert "authorization" in allowed
    assert "x-friday-session" in allowed


def test_packaged_tauri_origin_is_allowed():
    response = client.options(
        "/v1/settings",
        headers={
            "origin": "tauri://localhost",
            "access-control-request-method": "GET",
            "access-control-request-headers": "authorization,x-friday-session",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "tauri://localhost"


def test_conversation_message_round_trip():
    user_id = str(uuid4())
    conversation = client.post("/v1/conversations", json={"user_id": user_id}).json()
    response = client.post(
        "/v1/messages",
        json={"conversation_id": conversation["id"], "content": "Plan my day"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "user"


def test_message_to_unknown_conversation_fails():
    response = client.post(
        "/v1/messages", json={"conversation_id": str(uuid4()), "content": "Hello"}
    )
    assert response.status_code == 404


def test_model_route_does_not_expose_api_key():
    response = client.post(
        "/v1/model-routes/preview",
        json={"task_type": "coding", "capabilities": ["text", "tools"]},
    )
    assert response.status_code == 200
    assert "key" not in response.text.lower()


def test_task_create_update_and_audit():
    created = client.post(
        "/v1/tasks", json={"title": "Verify task flow", "priority": "high"}
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    updated = client.patch(f"/v1/tasks/{task_id}", json={"status": "completed"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "completed"
    audit = client.get("/v1/audit-events").json()
    assert any(event["event_type"] == "task.updated" for event in audit)


def test_task_rejects_unknown_priority():
    response = client.post("/v1/tasks", json={"title": "Invalid", "priority": "critical"})
    assert response.status_code == 422


def test_unknown_task_update_returns_not_found():
    response = client.patch(f"/v1/tasks/{uuid4()}", json={"status": "completed"})
    assert response.status_code == 404


def test_live_model_endpoint_is_disabled_by_default():
    response = client.post(
        "/v1/responses",
        json={
            "conversation_id": str(uuid4()),
            "session_id": str(uuid4()),
            "content": "Hello",
        },
    )
    assert response.status_code == 503


def test_approval_decision_is_audited():
    action = client.post(
        "/v1/actions/preview",
        json={
            "agent": "email",
            "action": "send_email",
            "target": "recipient@example.test",
            "risk": 2,
            "reversible": False,
            "expected_outcome": "one accepted message",
            "idempotency_key": f"approval-test-{uuid4()}",
        },
    ).json()
    approval_id = action["approval"]["id"]
    response = client.post(
        f"/v1/approvals/{approval_id}/decision",
        json={"status": "rejected", "user_id": str(uuid4())},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    audit = client.get("/v1/audit-events").json()
    assert any(event["event_type"] == "approval.rejected" for event in audit)
