from fastapi.testclient import TestClient

from app.main import app


def test_agent_zero_review_routes_require_api_token() -> None:
    client = TestClient(app)

    response = client.get("/v1/agent-zero/reviews/missing/status")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API token"}
