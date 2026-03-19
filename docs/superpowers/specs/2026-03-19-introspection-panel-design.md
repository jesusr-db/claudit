# Introspection Panel — Design Spec

**Date:** 2026-03-19
**Branch:** introspection
**Status:** Approved

---

## Overview

A new "Introspection" feature for the Claudit app that analyzes Claude Code session logs to surface recurring failure patterns, identify root causes, and recommend best practices. Analysis is on-demand per session, with cross-session pattern frequency as additional context.

---

## Goals

- Detect recurring failure patterns within a session (skill forgetting, tool retry loops, context drift, inefficiency)
- Identify root causes using LLM synthesis over structured session data
- Provide actionable best practices to avoid recurrence
- Surface cross-session frequency ("seen in 5 of your last 8 sessions")
- Integrate at two entry points: top-level nav page and Session Detail tab

---

## Non-Goals

- Automated/scheduled analysis (analysis is always user-initiated via button click)
- Persisting analysis results to the database
- Two-stage LLM pipelines (single SOTA model call is sufficient)
- Streaming responses (synchronous response with timeout handling)

---

## Architecture

### Pipeline

```
User clicks "Analyze"
  → POST /api/v1/introspection/analyze
    → SQL pre-extraction (otel_logs_mat)     # reduces context ~80%
    → SQL cross-session aggregation           # adds frequency context
    → FMAPI call (SOTA LLM, 60s timeout)     # detection + synthesis
    → JSON parse + validation                 # with fallback on failure
    → InsightCard[] returned
  ← Card feed rendered in frontend
```

### Data Flow

1. **SQL pre-extraction** queries `otel_logs_mat` for the target session, pulling only signal fields (see confirmed columns below). Truncated to the most recent 200 events if session exceeds that threshold to stay within token budget.

2. **Cross-session SQL** aggregates sessions from the last `cross_session_days` (default 30) for the same `user_id` (derived from the target session record), counting sessions with ≥1 tool failure, ≥1 api_error, or a skill-reminder keyword in prompt_text.

3. **FMAPI call** uses `mlflow.deployments.get_deploy_client("databricks")` with `databricks-meta-llama/Meta-Llama-3.3-70B-Instruct`. Returns a JSON array of InsightCard objects. On parse failure or timeout, returns an empty card list with an `analysis_error` field (no 500).

---

## Data Schema Reference

### `otel_logs_mat` columns used (confirmed from materialized view definition)

| Column | Type | Source |
|---|---|---|
| `session_id` | text | `attributes->>'session.id'` |
| `user_id` | text | `attributes->>'user.id'` |
| `prompt_id` | text | `attributes->>'prompt.id'` |
| `event_name` | text | `attributes->>'event.name'` |
| `event_seq` | int | `attributes->>'event.sequence'` |
| `event_ts` | timestamp | `attributes->>'event.timestamp'` |
| `prompt_text` | text | `attributes->>'prompt'` |
| `tool_name` | text | `attributes->>'tool_name'` |
| `success` | text | `attributes->>'success'` ('true'/'false') |
| `duration_ms` | double | `attributes->>'duration_ms'` |
| `error` | text | `attributes->>'error'` |
| `status_code` | text | `attributes->>'status_code'` |

### SQL pre-extraction query

```sql
SELECT
  event_name,
  event_seq,
  prompt_id,
  prompt_text,
  tool_name,
  success,
  duration_ms,
  error,
  status_code,
  user_id         -- needed for cross-session aggregation lookup
FROM zerobus_sdp.otel_logs_mat
WHERE session_id = :session_id
  AND event_name IN ('user_prompt', 'tool_result', 'api_error', 'tool_decision')
ORDER BY event_seq ASC
LIMIT 200
```

### Cross-session aggregation query (skeletal)

```sql
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
  FROM zerobus_sdp.otel_logs_mat
  WHERE user_id = :user_id
    AND event_ts >= NOW() - INTERVAL ':cross_session_days days'
  GROUP BY session_id
) s
```

The backend maps each row's counts to the `CrossSessionContext.count` and `CrossSessionContext.total` fields per pattern type.

---

## Backend

### New File: `backend/routers/introspection.py`

**Endpoints:**

```
POST /api/v1/introspection/analyze
  Body: {
    session_id: str,
    cross_session_days: int = 30   # lookback window for cross-session frequency
  }
  Returns: {
    session_id: str,
    analyzed_at: str,              # ISO timestamp
    cards: InsightCard[],
    analysis_error: str | null     # non-null if LLM call failed; cards will be []
  }
```

The existing `GET /api/v1/sessions` endpoint is reused for the session dropdown in IntrospectionPage — no new sessions endpoint is needed.

### `user_id` sourcing

The `user_id` is derived from the session record itself: the pre-extraction query reads `user_id` from the first event of the target session. This value is then used in the cross-session aggregation query. No auth context required.

### InsightCard schema

Defined as a Pydantic model in `backend/routers/introspection.py` and as a TypeScript interface in `frontend/src/types/api.ts` (alongside existing API types).

```python
class InsightCardOccurrence(BaseModel):
    label: str        # e.g. "prompt 4"
    event_seq: int    # for deep-linking into session timeline

class CrossSessionContext(BaseModel):
    count: int        # sessions where this pattern appeared
    total: int        # total sessions in the lookback window

class InsightCard(BaseModel):
    type: Literal["skill_forgetting", "tool_retry", "context_drift", "inefficiency"]
    severity: Literal["high", "medium", "low"]
    title: str
    description: str
    occurrences: list[InsightCardOccurrence]
    root_cause: str
    best_practices: list[str]
    cross_session: CrossSessionContext | None
```

### FMAPI System Prompt (template)

```
You are a Claude Code session analyzer. You will receive a structured log of events from a Claude Code session.

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
<EVENTS>
```

**Note on `occurrences.label`:** The LLM is expected to populate the `label` field (e.g. `"prompt 4"`) based on the `prompt_id` or sequence context visible in the events. The backend does not post-process this field — it validates that `event_seq` is an integer and `label` is a non-empty string, then passes through as-is.

### Error handling

| Scenario | Behavior |
|---|---|
| FMAPI timeout (>60s) | Return `{ cards: [], analysis_error: "Analysis timed out. Try again." }` |
| LLM returns malformed JSON | Attempt `json.loads` on extracted JSON block; if still fails, return `analysis_error` |
| Session has 0 relevant events | Return `{ cards: [], analysis_error: null }` (empty state, not an error) |
| Lakebase query fails | Return HTTP 503 (consistent with other routers) |
| LLM returns empty array | Return `{ cards: [], analysis_error: null }` (valid result, no patterns found) |

### Token budget

The pre-extraction query is `LIMIT 200` events. Typical sessions are 20–80 events; 200 is a safe ceiling. At ~150 tokens per event (prompt_text can be long), this is ~30k tokens of session data, well within Llama-3.3-70B's context window. If a session exceeds 200 events, the most recent 200 are used (ORDER BY event_seq ASC with LIMIT applied — this gives the full session start, which is where most patterns emerge; a future enhancement could make this configurable).

### Registration

Router mounted in `backend/main.py` at prefix `/api/v1/introspection`.

---

## Frontend

### TypeScript Types

Add to `frontend/src/types/api.ts`:

```typescript
export interface InsightCardOccurrence {
  label: string;
  event_seq: number;
}

export interface CrossSessionContext {
  count: number;
  total: number;
}

export interface InsightCard {
  type: 'skill_forgetting' | 'tool_retry' | 'context_drift' | 'inefficiency';
  severity: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  occurrences: InsightCardOccurrence[];
  root_cause: string;
  best_practices: string[];
  cross_session: CrossSessionContext | null;
}

export interface IntrospectionResult {
  session_id: string;
  analyzed_at: string;
  cards: InsightCard[];
  analysis_error: string | null;
}
```

### New Files

**`frontend/src/views/introspection/IntrospectionPage.tsx`**
- Route: `/introspection`
- Session dropdown populated from `GET /api/v1/sessions?days=30` (existing endpoint, filtered to `days` from global TimeRangeContext)
- "Cross-session window" selector: 7 / 30 / 90 days (controls `cross_session_days` param)
- "Analyze Session" button — disabled until session selected
- On click: triggers `useIntrospectionAnalyze` mutation, shows spinner
- On success: renders `InsightCardFeed`
- On `analysis_error`: shows inline error banner (not a crash)

**`frontend/src/views/introspection/components/InsightCard.tsx`**
- Severity badge: high=red, medium=amber, low=purple
- Pattern type icon: ⚠ skill_forgetting, ✗ tool_retry, ⟳ context_drift, ⚡ inefficiency
- Title + description always visible
- Click to expand: root_cause paragraph + best_practices bullet list
- Cross-session badge: `↻ Seen in N of M sessions` (only if `cross_session` non-null)
- `occurrences` rendered as text references (e.g. "prompt 4"); deep-linking to session timeline by `event_seq` is a stub — the Session Timeline does not currently support anchor navigation by sequence number. The `event_seq` is stored for future use when that feature is added.

**`frontend/src/views/introspection/components/InsightCardFeed.tsx`**
- Sorted list: high → medium → low
- Empty state: "No patterns detected — great session! 🎉"
- Error state: shows `analysis_error` text with retry option

### Modified Files

**`frontend/src/views/sessions/SessionDetailPage.tsx`**
- Add "Insights" tab alongside existing tabs
- Tab renders `InsightCardFeed` + an "Analyze" button
- Analysis is always user-initiated (button click) — no auto-trigger on tab visit
- React Query caches result for 5 minutes; subsequent tab visits show cached result
- "Re-analyze" button always visible to force refresh

**`frontend/src/shared/hooks/useApi.ts`**
- Add `useIntrospectionAnalyze`: mutation hook for `POST /api/v1/introspection/analyze`

**`frontend/src/app/`** (sidebar nav + router)
- Add "Introspection" nav item (magnifying glass or brain icon)
- Add `/introspection` route → `IntrospectionPage`

---

## UX Details

### `days` parameter semantics

- `GET /api/v1/sessions?days=N` (existing): returns sessions *started* in the last N days
- `POST /api/v1/introspection/analyze` body `cross_session_days=N`: looks back N days for cross-session frequency counting

These are independent — the session picker's window does not have to match the cross-session window.

### IntrospectionPage flow
1. Dropdown: select session from the last N days (uses global time range)
2. "Analyze Session" button activates once session is selected
3. Click → spinner "Analyzing session…" (synchronous, up to 60s)
4. Cards render sorted by severity
5. Each card collapsed by default; click to expand

### Session Detail "Insights" tab flow
1. Tab shows "Insights" alongside Timeline and other tabs
2. On first visit: shows empty state with "Analyze" button — user must click
3. After analysis: cards render (React Query 5min cache)
4. "Re-analyze" button available at any time

---

## Decisions Table

| Decision | Choice | Reason |
|---|---|---|
| LLM pipeline | Single SOTA call | Sessions are bounded; two-stage adds latency without quality gain |
| Model | Meta-Llama-3.3-70B via FMAPI | Available in all Databricks workspaces; no separate API key |
| Output format | JSON only | Reliable parsing; frontend owns rendering |
| Caching | React Query 5min TTL | On-demand feel with repeat-visit speedup; no DB persistence |
| Cross-session window | 30 days default | Covers typical work patterns |
| Data source | Lakebase otel_logs_mat | Already indexed and tuned |
| Event limit | 200 events (LIMIT in SQL) | Safe token budget ceiling; covers all typical sessions |
| Auto-trigger | Never — always button-initiated | Consistent with "on-demand" framing; avoids surprise FMAPI calls |
| Sessions endpoint | Reuse existing GET /sessions | No new endpoint needed; avoids duplication |
| user_id | Derived from first session event | No auth context needed; already in the data |
| occurrences type | `{ label, event_seq }` structured | Enables deep-linking to session timeline |
| FMAPI failure | Graceful `analysis_error` field | Never 500; always usable UI state |
