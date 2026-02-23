import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_executor():
    with patch("backend.routers.metrics.get_executor") as mock:
        executor = MagicMock()
        mock.return_value = executor
        yield executor


@pytest.fixture
def client(mock_executor):
    from backend.main import app
    return TestClient(app)


def test_get_summary(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "total_sessions": "3",
            "total_users": "1",
            "total_events": "111",
            "total_prompts": "8",
            "total_api_calls": "24",
            "total_errors": "22",
            "total_cost_usd": "0.44",
        }
    ]
    response = client.get("/api/v1/metrics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_sessions" in data


def test_get_tool_stats(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "tool_name": "Bash",
            "call_count": "15",
            "avg_duration_ms": "2100.5",
            "success_count": "14",
            "failure_count": "1",
            "total_result_bytes": "15000",
        }
    ]
    response = client.get("/api/v1/metrics/tools")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tools"]) == 1
    assert data["tools"][0]["tool_name"] == "Bash"


def test_health_check(client, mock_executor):
    response = client.get("/health")
    assert response.status_code == 200
