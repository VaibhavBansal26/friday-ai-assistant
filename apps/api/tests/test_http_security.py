from fastapi.testclient import TestClient

from friday.main import app


client = TestClient(app)


def test_security_headers_and_correlation_id_are_present():
    response = client.get("/v1/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-correlation-id"]


def test_caller_correlation_id_is_preserved():
    response = client.get("/v1/health", headers={"x-correlation-id": "test-correlation"})
    assert response.headers["x-correlation-id"] == "test-correlation"


def test_oversized_request_is_rejected_before_parsing():
    response = client.post(
        "/v1/tasks",
        content=b"{}",
        headers={"content-length": "3000000", "content-type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["code"] == "request_too_large"
    assert "correlation_id" in response.json()


def test_invalid_content_length_is_rejected_safely():
    response = client.get("/v1/health", headers={"content-length": "invalid"})
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_content_length"
