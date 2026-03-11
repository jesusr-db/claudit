import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_executor():
    with patch("backend.routers.mcp_tools.get_pg_executor") as mock, \
         patch("backend.main.get_pg_executor") as mock_health:
        executor = MagicMock()
        mock.return_value = executor
        mock_health.return_value = executor
        yield executor


@pytest.fixture
def client(mock_executor):
    from backend.main import app
    return TestClient(app)


def test_get_tool_performance(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "tool_name": "Bash",
            "call_count": "274",
            "success_count": "249",
            "failure_count": "25",
            "success_rate": "90.9",
            "avg_duration_ms": "9582",
            "p50_duration_ms": "3200",
            "p95_duration_ms": "54823",
            "p99_duration_ms": "60000",
            "total_result_bytes": "500000",
        },
        {
            "tool_name": "mcp_tool",
            "call_count": "46",
            "success_count": "45",
            "failure_count": "1",
            "success_rate": "97.8",
            "avg_duration_ms": "1122",
            "p50_duration_ms": "800",
            "p95_duration_ms": "3160",
            "p99_duration_ms": "4000",
            "total_result_bytes": "125000",
        },
    ]
    response = client.get("/api/v1/tools/performance")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tools"]) == 2
    assert data["tools"][0]["tool_name"] == "Bash"
    assert data["tools"][1]["tool_name"] == "mcp_tool"


def test_get_tool_recent_calls(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "timestamp": "2026-02-24T10:00:00Z",
            "tool_name": "mcp_tool",
            "session_id": "abc-123",
            "prompt_id": "p-456",
            "duration_ms": "320",
            "success": "true",
            "result_size_bytes": "4500",
        }
    ]
    response = client.get("/api/v1/tools/mcp_tool/calls?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["tool_name"] == "mcp_tool"
    assert len(data["calls"]) == 1
    assert data["calls"][0]["success"] == "true"


def test_get_tool_recent_calls_empty(client, mock_executor):
    mock_executor.execute.return_value = []
    response = client.get("/api/v1/tools/Read/calls")
    assert response.status_code == 200
    data = response.json()
    assert data["tool_name"] == "Read"
    assert data["calls"] == []
