import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_executor():
    with patch("backend.routers.platform.get_sql_executor") as mock_plat, \
         patch("backend.routers.sessions.require_pg_executor") as mock_sess, \
         patch("backend.routers.metrics.require_pg_executor") as mock_met, \
         patch("backend.main.get_pg_executor") as mock_health:
        executor = MagicMock()
        mock_plat.return_value = executor
        mock_sess.return_value = executor
        mock_met.return_value = executor
        mock_health.return_value = executor
        yield executor


@pytest.fixture
def client(mock_executor):
    from backend.main import app
    return TestClient(app)


def test_billing_summary(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "product": "MODEL_SERVING",
            "usage_unit": "DBU",
            "total_usage": "5521.45",
            "record_count": "1200",
            "active_days": "30",
        },
        {
            "product": "SQL",
            "usage_unit": "DBU",
            "total_usage": "1074.20",
            "record_count": "800",
            "active_days": "28",
        },
    ]
    response = client.get("/api/v1/platform/billing/summary?days=30")
    assert response.status_code == 200
    data = response.json()
    assert len(data["products"]) == 2
    assert data["products"][0]["product"] == "MODEL_SERVING"
    assert data["days"] == 30


def test_billing_daily(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "usage_date": "2026-02-25",
            "product": "SQL",
            "sku_name": "ENTERPRISE_SERVERLESS_SQL",
            "usage_unit": "DBU",
            "total_usage": "35.20",
        }
    ]
    response = client.get("/api/v1/platform/billing/daily?days=7")
    assert response.status_code == 200
    data = response.json()
    assert len(data["daily"]) == 1
    assert data["daily"][0]["usage_date"] == "2026-02-25"


def test_query_stats(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "client_application": "Databricks CLI",
            "execution_status": "FINISHED",
            "query_count": "250",
            "avg_total_ms": "1394",
            "avg_exec_ms": "800",
            "avg_compile_ms": "304",
            "avg_queue_ms": "0",
            "total_rows_read": "89900",
            "total_bytes_read": "87200000",
        }
    ]
    response = client.get("/api/v1/platform/queries/stats?days=7")
    assert response.status_code == 200
    data = response.json()
    assert len(data["stats"]) == 1
    assert data["stats"][0]["client_application"] == "Databricks CLI"


def test_query_daily(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "query_date": "2026-02-25",
            "total_queries": "1500",
            "succeeded": "1480",
            "failed": "20",
            "avg_duration_ms": "2100",
            "p95_duration_ms": "8500",
            "total_bytes_read": "500000000",
        }
    ]
    response = client.get("/api/v1/platform/queries/daily?days=7")
    assert response.status_code == 200
    data = response.json()
    assert len(data["daily"]) == 1
    assert data["daily"][0]["total_queries"] == "1500"


def test_ai_gateway_models(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "model": "Claude 3.5 Sonnet",
            "endpoint_name": "databricks-claude-3-5-sonnet",
            "api_type": "anthropic",
            "call_count": "260",
            "success_count": "255",
            "error_count": "5",
            "avg_latency_ms": "6200",
            "p50_latency_ms": "4500",
            "p95_latency_ms": "15000",
            "avg_ttfb_ms": "1200",
            "total_input_tokens": "850000",
            "total_output_tokens": "120000",
            "total_tokens": "970000",
            "total_cache_read_tokens": "650000",
            "total_cache_creation_tokens": "45000",
        }
    ]
    response = client.get("/api/v1/platform/ai-gateway/models?days=7")
    assert response.status_code == 200
    data = response.json()
    assert len(data["models"]) == 1
    assert data["models"][0]["model"] == "Claude 3.5 Sonnet"
    assert data["days"] == 7


def test_ai_gateway_daily(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "request_date": "2026-02-25",
            "total_requests": "120",
            "succeeded": "115",
            "failed": "5",
            "avg_latency_ms": "5500",
            "avg_ttfb_ms": "1100",
            "p95_latency_ms": "14000",
            "total_tokens": "180000",
        }
    ]
    response = client.get("/api/v1/platform/ai-gateway/daily?days=7")
    assert response.status_code == 200
    data = response.json()
    assert len(data["daily"]) == 1
    assert data["daily"][0]["total_requests"] == "120"


def test_ai_gateway_errors(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "model": "Claude 3.5 Sonnet",
            "endpoint_name": "databricks-claude-3-5-sonnet",
            "status_code": "500",
            "error_count": "3",
            "avg_latency_ms": "200",
        }
    ]
    response = client.get("/api/v1/platform/ai-gateway/errors?days=7")
    assert response.status_code == 200
    data = response.json()
    assert len(data["errors"]) == 1
    assert data["errors"][0]["status_code"] == "500"
