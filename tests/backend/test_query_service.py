import pytest
from backend.services.query_service import QueryService


@pytest.fixture
def svc():
    return QueryService(catalog="jmr_demo", schema="zerobus")


def test_build_sessions_list_query(svc):
    query = svc.build_sessions_list_query(limit=10, offset=0)
    assert "otel_logs" in query
    assert "session.id" in query
    assert "GROUP BY" in query
    assert "LIMIT 10" in query
    assert "first_prompt" in query
    assert "total_input_tokens" in query
    assert "total_output_tokens" in query
    assert "total_cache_read_tokens" in query


def test_build_session_timeline_query(svc):
    query = svc.build_session_timeline_query(
        session_id="996a6297-0787-454a-94b8-96191aa0a22c"
    )
    assert "otel_logs" in query
    assert "996a6297" in query
    assert "ORDER BY" in query


def test_build_session_timeline_query_with_event_filter(svc):
    query = svc.build_session_timeline_query(
        session_id="996a6297",
        event_names=["api_request", "api_error"],
    )
    assert "api_request" in query
    assert "api_error" in query


def test_build_token_usage_query(svc):
    query = svc.build_token_usage_query()
    assert "otel_metrics" in query
    assert "token.usage" in query


def test_build_cost_usage_query(svc):
    query = svc.build_cost_usage_query()
    assert "otel_metrics" in query
    assert "cost.usage" in query


def test_build_tool_stats_query(svc):
    query = svc.build_tool_stats_query()
    assert "otel_logs" in query
    assert "tool_result" in query


def test_build_error_stats_query(svc):
    query = svc.build_error_stats_query()
    assert "otel_logs" in query
    assert "api_error" in query


def test_build_session_detail_query(svc):
    query = svc.build_session_detail_query(session_id="996a6297")
    assert "otel_logs" in query
    assert "996a6297" in query
    assert "GROUP BY" in query
    assert "total_cost_usd" in query


def test_build_prompt_events_query(svc):
    query = svc.build_prompt_events_query(
        session_id="996a6297", prompt_id="efeed64b"
    )
    assert "otel_logs" in query
    assert "996a6297" in query
    assert "efeed64b" in query
    assert "tool_parameters" in query
    assert "ORDER BY" in query


def test_build_tool_performance_query(svc):
    query = svc.build_tool_performance_query()
    assert "otel_logs" in query
    assert "tool_result" in query
    assert "PERCENTILE" in query
    assert "success_rate" in query
    assert "p50_duration_ms" in query


def test_build_tool_recent_calls_query(svc):
    query = svc.build_tool_recent_calls_query(tool_name="mcp_tool", limit=25)
    assert "otel_logs" in query
    assert "mcp_tool" in query
    assert "LIMIT 25" in query
    assert "ORDER BY" in query


def test_build_billing_summary_query(svc):
    query = svc.build_billing_summary_query(days=30)
    assert "system.billing.usage" in query
    assert "billing_origin_product" in query
    assert "GROUP BY" in query
    assert "DBU" in query


def test_build_billing_daily_query(svc):
    query = svc.build_billing_daily_query(days=7)
    assert "system.billing.usage" in query
    assert "usage_date" in query
    assert "ORDER BY" in query


def test_build_query_history_stats_query(svc):
    query = svc.build_query_history_stats_query(days=7)
    assert "system.query.history" in query
    assert "client_application" in query
    assert "execution_status" in query
    assert "GROUP BY" in query


def test_build_query_history_daily_query(svc):
    query = svc.build_query_history_daily_query(days=7)
    assert "system.query.history" in query
    assert "total_queries" in query
    assert "p95_duration_ms" in query
    assert "ORDER BY" in query


def test_build_ai_gateway_model_stats_query(svc):
    query = svc.build_ai_gateway_model_stats_query(days=7)
    assert "system.ai_gateway.usage" in query
    assert "destination_model" in query
    assert "latency_ms" in query
    assert "time_to_first_byte_ms" in query
    assert "cache_read_input_tokens" in query
    assert "GROUP BY" in query


def test_build_ai_gateway_daily_query(svc):
    query = svc.build_ai_gateway_daily_query(days=7)
    assert "system.ai_gateway.usage" in query
    assert "request_date" in query
    assert "avg_ttfb_ms" in query
    assert "ORDER BY" in query


def test_build_ai_gateway_errors_query(svc):
    query = svc.build_ai_gateway_errors_query(days=7)
    assert "system.ai_gateway.usage" in query
    assert "status_code != 200" in query
    assert "ORDER BY" in query
