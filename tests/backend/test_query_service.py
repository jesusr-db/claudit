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
