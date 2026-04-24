import pytest
from backend.services.efficiency_query_service import EfficiencyQueryService


@pytest.fixture
def svc():
    return EfficiencyQueryService()


def test_aey_overview_returns_nonempty_string(svc):
    sql = svc.build_aey_overview(days=30)
    assert isinstance(sql, str) and len(sql) > 0
    assert "cost_per_accepted_decision" in sql
    assert "tool_decision" in sql
    assert "api_request" in sql
    assert "30 days" in sql


def test_cognitive_load_index_contains_key_clauses(svc):
    sql = svc.build_cognitive_load_index(days=7)
    assert isinstance(sql, str) and len(sql) > 0
    assert "cognitive_load_index" in sql
    # prompt-level aggregation present
    assert "prompt_id" in sql
    # context thrash sub-select present
    assert "Read" in sql
    assert "7 days" in sql


def test_feedback_latency_returns_percentile_query(svc):
    sql = svc.build_feedback_latency(days=30)
    assert isinstance(sql, str) and len(sql) > 0
    assert "PERCENTILE_CONT(0.5)" in sql
    assert "PERCENTILE_CONT(0.95)" in sql
    assert "p50_ms" in sql
    assert "p95_ms" in sql
    assert "30 days" in sql


def test_harness_convergence_returns_dated_rows(svc):
    sql = svc.build_harness_convergence(days=30)
    assert isinstance(sql, str) and len(sql) > 0
    assert "avg_convergence_score" in sql
    # must have a date/day grouping column
    assert "session_date" in sql or "AS date" in sql
    assert "30 days" in sql


def test_rework_ratio_extracts_file_path(svc):
    sql = svc.build_rework_ratio(days=30)
    assert isinstance(sql, str) and len(sql) > 0
    assert "rework_ratio" in sql
    assert "file_path" in sql
    # edit/write events expected
    assert "Edit" in sql
    assert "Write" in sql
    assert "MultiEdit" in sql


def test_all_queries_use_correct_table(svc):
    table = svc.mat
    assert table  # non-empty
    queries = [
        svc.build_aey_overview(),
        svc.build_cognitive_load_index(),
        svc.build_feedback_latency(),
        svc.build_harness_convergence(),
        svc.build_rework_ratio(),
    ]
    for q in queries:
        assert table in q, f"Expected table '{table}' in query:\n{q}"
