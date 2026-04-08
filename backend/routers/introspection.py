"""Introspection router — analyzes Claude Code session logs to surface
recurring failure patterns, identify root causes, and recommend best practices."""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.cache import cached_execute
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/introspection", tags=["introspection"])

# ── Pydantic Models ──────────────────────────────────────────────────────────


class InsightCardOccurrence(BaseModel):
    label: str
    event_seq: int


class CrossSessionContext(BaseModel):
    count: int
    total: int


class InsightCard(BaseModel):
    type: Literal["skill_forgetting", "tool_retry", "context_drift", "inefficiency"]
    severity: Literal["high", "medium", "low"]
    title: str
    description: str
    occurrences: list[InsightCardOccurrence]
    root_cause: str
    best_practices: list[str]
    cross_session: Optional[CrossSessionContext] = None


class IntrospectionRequest(BaseModel):
    session_id: str
    cross_session_days: int = 30


class IntrospectionResponse(BaseModel):
    session_id: str
    analyzed_at: str
    cards: list[InsightCard]
    analysis_error: Optional[str] = None


# ── System Prompt Template ───────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Claude Code session analyzer. You will receive a structured log of events from a Claude Code session.

Analyze the events and identify failure patterns from these categories:
- skill_forgetting: The user had to remind Claude about a skill, tool, or instruction it already had access to
- tool_retry: Claude retried the same failing tool call without diagnosing the root cause first
- context_drift: Claude contradicted an earlier decision or re-asked a question already answered
- inefficiency: Claude took an unnecessarily long path (many tool calls) to accomplish a simple task

For each pattern found, return a JSON object matching this exact schema:
{
  "type": "<pattern type>",
  "severity": "<high|medium|low>",
  "title": "<short label, max 60 chars>",
  "description": "<what happened, 1-2 sentences>",
  "occurrences": [{"label": "prompt N", "event_seq": <int>}],
  "root_cause": "<why this happened, 2-3 sentences>",
  "best_practices": ["<actionable tip>", ...]
}

Return ONLY a JSON array of these objects. No markdown. No prose. No explanation outside the JSON.
If no patterns are found, return an empty array: []

Session events:
<EVENTS>"""

# ── Helpers ──────────────────────────────────────────────────────────────────

FMAPI_MODEL = "databricks-meta-llama-3-3-70b-instruct"
FMAPI_TIMEOUT = 60  # seconds


def _build_event_extraction_query(session_id: str) -> str:
    safe_id = session_id.replace("'", "''")
    return f"""
SELECT event_name, event_seq, prompt_id, prompt_text, tool_name,
       success, duration_ms, error, status_code, user_id
FROM {settings.otel_logs_mat_table}
WHERE session_id = '{safe_id}'
  AND event_name IN ('user_prompt', 'tool_result', 'api_error', 'tool_decision')
ORDER BY event_seq ASC
LIMIT 200
"""


def _build_cross_session_query(user_id: str, cross_session_days: int) -> str:
    safe_uid = user_id.replace("'", "''")
    return f"""
SELECT
  COUNT(DISTINCT session_id)                                           AS total_sessions,
  COUNT(DISTINCT CASE WHEN has_tool_failure THEN session_id END)      AS tool_failure_sessions,
  COUNT(DISTINCT CASE WHEN has_api_error    THEN session_id END)      AS api_error_sessions,
  COUNT(DISTINCT CASE WHEN has_skill_remind THEN session_id END)      AS skill_remind_sessions
FROM (
  SELECT
    session_id,
    BOOL_OR(event_name = 'tool_result' AND success = 'false')        AS has_tool_failure,
    BOOL_OR(event_name = 'api_error')                                 AS has_api_error,
    BOOL_OR(event_name = 'user_prompt'
      AND prompt_text ILIKE ANY(ARRAY['%remember to use%','%don''t forget%','%use the skill%','%invoke the%']))
                                                                      AS has_skill_remind
  FROM {settings.otel_logs_mat_table}
  WHERE user_id = '{safe_uid}'
    AND event_ts >= NOW() - INTERVAL '{int(cross_session_days)} days'
  GROUP BY session_id
) s
"""


def _map_cross_session(card_type: str, cross_session_row: dict) -> Optional[CrossSessionContext]:
    """Map cross-session aggregation counts to the correct InsightCard type."""
    total = int(cross_session_row.get("total_sessions", 0))
    if total == 0:
        return None

    type_to_field = {
        "skill_forgetting": "skill_remind_sessions",
        "tool_retry": "tool_failure_sessions",
        "context_drift": None,  # no direct cross-session signal
        "inefficiency": "tool_failure_sessions",  # proxy: sessions with tool failures
    }

    field = type_to_field.get(card_type)
    if field is None:
        return None

    count = int(cross_session_row.get(field, 0))
    if count == 0:
        return None

    return CrossSessionContext(count=count, total=total)


def _call_fmapi(events_json: str) -> str:
    """Call FMAPI with the session events. Returns the raw LLM response text."""
    import mlflow.deployments

    client = mlflow.deployments.get_deploy_client("databricks")
    prompt_text = SYSTEM_PROMPT.replace("<EVENTS>", events_json)

    response = client.predict(
        endpoint=FMAPI_MODEL,
        inputs={
            "messages": [
                {"role": "system", "content": prompt_text},
                {"role": "user", "content": "Analyze the session events above and return the JSON array of insight cards."},
            ],
            "max_tokens": 4096,
            "temperature": 0.1,
        },
    )

    # Extract text from response
    if isinstance(response, dict):
        choices = response.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
    return str(response)


def _parse_llm_response(raw_text: str) -> list[dict]:
    """Parse JSON array from LLM response, with fallback extraction."""
    text = raw_text.strip()

    # Direct parse attempt
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try extracting JSON block from markdown code fences
    import re
    json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    # Try finding array brackets
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON array from LLM response: {text[:200]}")


# ── Endpoint ─────────────────────────────────────────────────────────────────


@router.post("/analyze", response_model=IntrospectionResponse)
async def analyze_session(request: IntrospectionRequest):
    """Analyze a Claude Code session for failure patterns using LLM synthesis."""
    session_id = request.session_id
    cross_session_days = request.cross_session_days
    now = datetime.now(timezone.utc).isoformat()

    # Step 1: Extract session events
    event_query = _build_event_extraction_query(session_id)
    events = await cached_execute(f"introspection:events:{session_id}", event_query)

    # Step 2: Handle empty session
    if not events:
        return IntrospectionResponse(
            session_id=session_id,
            analyzed_at=now,
            cards=[],
            analysis_error=None,
        )

    # Step 3: Extract user_id from first event
    user_id = events[0].get("user_id")

    # Step 4: Cross-session aggregation
    cross_session_row = {}
    if user_id:
        cross_query = _build_cross_session_query(user_id, cross_session_days)
        cross_rows = await cached_execute(
            f"introspection:cross:{user_id}:{cross_session_days}",
            cross_query,
        )
        if cross_rows:
            cross_session_row = cross_rows[0]

    # Step 5: Prepare events for LLM
    # Serialize events to compact JSON for the prompt
    events_for_llm = []
    for e in events:
        event_dict = {
            "event_name": e.get("event_name"),
            "event_seq": e.get("event_seq"),
            "prompt_id": e.get("prompt_id"),
        }
        # Only include non-null fields to save tokens
        if e.get("prompt_text"):
            # Truncate long prompts
            pt = str(e["prompt_text"])
            event_dict["prompt_text"] = pt[:500] if len(pt) > 500 else pt
        if e.get("tool_name"):
            event_dict["tool_name"] = e["tool_name"]
        if e.get("success") is not None:
            event_dict["success"] = e["success"]
        if e.get("duration_ms") is not None:
            event_dict["duration_ms"] = e["duration_ms"]
        if e.get("error"):
            err = str(e["error"])
            event_dict["error"] = err[:300] if len(err) > 300 else err
        if e.get("status_code"):
            event_dict["status_code"] = e["status_code"]
        events_for_llm.append(event_dict)

    events_json = json.dumps(events_for_llm, default=str)

    # Step 6: Call FMAPI
    try:
        t0 = time.monotonic()
        raw_response = await _run_fmapi_in_thread(events_json)
        elapsed = time.monotonic() - t0
        logger.info("FMAPI call for session %s took %.1fs", session_id, elapsed)
    except (TimeoutError, asyncio.TimeoutError):
        logger.warning("FMAPI timeout for session %s", session_id)
        return IntrospectionResponse(
            session_id=session_id,
            analyzed_at=now,
            cards=[],
            analysis_error="Analysis timed out. Try again.",
        )
    except Exception as e:
        logger.error("FMAPI error for session %s: %s", session_id, e)
        return IntrospectionResponse(
            session_id=session_id,
            analyzed_at=now,
            cards=[],
            analysis_error=f"Analysis failed: {str(e)[:200]}",
        )

    # Step 7: Parse LLM response
    try:
        raw_cards = _parse_llm_response(raw_response)
    except ValueError as e:
        logger.warning("LLM response parse error for session %s: %s", session_id, e)
        return IntrospectionResponse(
            session_id=session_id,
            analyzed_at=now,
            cards=[],
            analysis_error=f"Could not parse analysis results. Try again.",
        )

    # Step 8: Validate and build InsightCard objects
    cards: list[InsightCard] = []
    for raw_card in raw_cards:
        try:
            card = InsightCard(**raw_card)
            # Attach cross-session context
            card.cross_session = _map_cross_session(card.type, cross_session_row)
            cards.append(card)
        except Exception as e:
            logger.warning("Skipping invalid card: %s — %s", raw_card, e)
            continue

    return IntrospectionResponse(
        session_id=session_id,
        analyzed_at=now,
        cards=cards,
        analysis_error=None,
    )


async def _run_fmapi_in_thread(events_json: str) -> str:
    """Run the blocking FMAPI call off the event loop with a hard timeout."""
    return await asyncio.wait_for(
        asyncio.to_thread(_call_fmapi, events_json),
        timeout=FMAPI_TIMEOUT,
    )
