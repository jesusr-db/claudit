import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_executor():
    with patch("backend.routers.sessions.get_pg_executor") as mock_sess, \
         patch("backend.routers.metrics.get_pg_executor") as mock_met, \
         patch("backend.routers.platform.get_sql_executor") as mock_plat, \
         patch("backend.main.get_pg_executor") as mock_health:
        executor = MagicMock()
        mock_sess.return_value = executor
        mock_met.return_value = executor
        mock_plat.return_value = executor
        mock_health.return_value = executor
        yield executor


@pytest.fixture
def client(mock_executor):
    from backend.main import app
    return TestClient(app)


def test_list_sessions(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "session_id": "996a6297-0787-454a-94b8-96191aa0a22c",
            "user_id": "c35b69e8...",
            "start_time": "2026-02-23T18:02:20Z",
            "end_time": "2026-02-23T19:30:00Z",
            "event_count": "111",
            "prompt_count": "5",
            "tool_calls": "29",
            "errors": "22",
            "total_cost_usd": "0.44",
            "total_input_tokens": "85000",
            "total_output_tokens": "12000",
            "total_cache_read_tokens": "45000",
            "first_prompt": "can you review the OTEL log config",
        }
    ]
    response = client.get("/api/v1/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "996a6297-0787-454a-94b8-96191aa0a22c"
    assert data["sessions"][0]["first_prompt"] == "can you review the OTEL log config"


def test_get_session_detail(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "session_id": "996a6297",
            "user_id": "c35b69e8...",
            "start_time": "2026-02-23T18:02:20Z",
            "end_time": "2026-02-23T19:30:00Z",
            "event_count": "111",
            "prompt_count": "5",
            "tool_calls": "29",
            "errors": "22",
            "total_cost_usd": "0.44",
        }
    ]
    response = client.get("/api/v1/sessions/996a6297")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "996a6297"


def test_get_session_detail_not_found(client, mock_executor):
    mock_executor.execute.return_value = []
    response = client.get("/api/v1/sessions/nonexistent")
    assert response.status_code == 404


def test_get_session_timeline(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "event_name": "user_prompt",
            "timestamp": "2026-02-23T18:02:20.757Z",
            "sequence": 1,
            "session_id": "996a6297",
            "prompt_id": "efeed64b",
            "user_id": "c35b69e8",
            "tool_name": None,
            "model": None,
            "duration_ms": None,
            "prompt": "can you review OTEL log configuration...",
        }
    ]
    response = client.get("/api/v1/sessions/996a6297/timeline")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "996a6297"
    assert len(data["events"]) == 1
    assert data["events"][0]["event_name"] == "user_prompt"


def test_get_prompt_events(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "event_name": "user_prompt",
            "timestamp": "2026-02-23T18:02:20.757Z",
            "sequence": 1,
            "session_id": "996a6297",
            "prompt_id": "efeed64b",
            "tool_name": None,
            "model": None,
            "duration_ms": None,
            "tool_parameters": None,
        },
        {
            "event_name": "tool_result",
            "timestamp": "2026-02-23T18:02:21.757Z",
            "sequence": 4,
            "session_id": "996a6297",
            "prompt_id": "efeed64b",
            "tool_name": "Bash",
            "model": None,
            "duration_ms": "1017",
            "tool_parameters": '{"bash_command":"git","full_command":"git status"}',
        },
    ]
    response = client.get("/api/v1/sessions/996a6297/prompts/efeed64b")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "996a6297"
    assert data["prompt_id"] == "efeed64b"
    assert len(data["events"]) == 2
    assert data["events"][1]["tool_parameters"] is not None
