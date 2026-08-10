from fastapi.testclient import TestClient

from app.main import app


def test_agent_zero_review_routes_require_api_token() -> None:
    client = TestClient(app)

    response = client.get("/v1/agent-zero/reviews/missing/status")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API token"}


def test_dashboard_task_actions_require_api_token() -> None:
    client = TestClient(app)

    decline = client.post(
        "/v1/agent-zero/reviews/job-1/decline",
        json={"reason": "The proposed change is wrong."},
    )
    archive = client.post(
        "/v1/flow/model/jobs/job-1/archive",
        json={"reason": "Remove it from the workspace."},
    )

    assert decline.status_code == 401
    assert archive.status_code == 401
