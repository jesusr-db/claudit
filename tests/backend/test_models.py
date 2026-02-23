import pytest
from datetime import datetime
from backend.models.events import OtelLogEvent, EventName
from backend.models.sessions import SessionSummary
from backend.models.metrics import TokenUsage, CostUsage


def test_event_name_enum():
    assert EventName.USER_PROMPT.value == "user_prompt"
    assert EventName.API_REQUEST.value == "api_request"
    assert EventName.API_ERROR.value == "api_error"
    assert EventName.TOOL_DECISION.value == "tool_decision"
    assert EventName.TOOL_RESULT.value == "tool_result"


def test_otel_log_event_from_row():
    """Test parsing a raw otel_logs row into structured event."""
    row = {
        "body": "claude_code.tool_result",
        "attributes": {
            "event.name": "tool_result",
            "event.timestamp": "2026-02-23T18:06:25.499Z",
            "event.sequence": "50",
            "session.id": "996a6297-0787-454a-94b8-96191aa0a22c",
            "prompt.id": "70c91395-e300-4989-ac61-b2a97091f944",
            "user.id": "c35b69e8d2d591e01edc4cee16bda6467c047ca6d44038c0eb87fc779a4fcc2f",
            "terminal.type": "iTerm.app",
            "tool_name": "Bash",
            "duration_ms": "2330",
            "success": "true",
            "tool_result_size_bytes": "1274",
        },
    }
    event = OtelLogEvent.from_row(row)
    assert event.event_name == EventName.TOOL_RESULT
    assert event.session_id == "996a6297-0787-454a-94b8-96191aa0a22c"
    assert event.sequence == 50
    assert event.tool_name == "Bash"
    assert event.duration_ms == 2330


def test_session_summary():
    summary = SessionSummary(
        session_id="996a6297-0787-454a-94b8-96191aa0a22c",
        user_id="c35b69e8...",
        start_time=datetime(2026, 2, 23, 18, 2, 20),
        end_time=datetime(2026, 2, 23, 19, 30, 0),
        event_count=111,
        prompt_count=5,
        total_cost_usd=0.44,
        tool_calls=29,
        errors=22,
    )
    assert summary.session_id == "996a6297-0787-454a-94b8-96191aa0a22c"
    assert summary.event_count == 111


def test_token_usage():
    usage = TokenUsage(
        session_id="996a...",
        model="databricks-claude-opus-4-6",
        input_tokens=4,
        output_tokens=545,
        cache_read_tokens=47356,
        cache_creation_tokens=68504,
    )
    assert usage.total_tokens == 4 + 545 + 47356 + 68504
