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

- Automated/scheduled analysis (on-demand only)
- Persisting analysis results to the database
- Two-stage LLM pipelines (single SOTA model call is sufficient)

---

## Architecture

### Pipeline

```
User clicks "Analyze"
  → POST /api/v1/introspection/analyze
    → SQL pre-extraction (otel_logs_mat)     # reduces context ~80%
    → SQL cross-session aggregation           # adds frequency context
    → FMAPI call (SOTA LLM)                  # detection + synthesis
    → JSON insight cards returned
  ← Card feed rendered in frontend
```

### Data Flow

1. **SQL pre-extraction** queries `otel_logs_mat` for the target session, pulling only signal fields: `prompt_text` (from `user_prompt` events), `tool_name` + `success` + `duration_ms` (from `tool_result` events), and `error` + `status_code` (from `api_error` events). All ordered by `event_seq`.

2. **Cross-session SQL** aggregates the last `days` sessions (default 30) for the same `user_id`, counting occurrences of each pattern type to populate the `cross_session` field on cards.

3. **FMAPI call** uses `databricks-meta-llama/Meta-Llama-3.3-70B-Instruct` via `mlflow.deployments` client. The system prompt instructs the model to return a JSON array of `InsightCard` objects. No prose — structured output only.

---

## Backend

### New File: `backend/routers/introspection.py`

**Endpoints:**

```
POST /api/v1/introspection/analyze
  Body: { session_id: str, days: int = 30 }
  Returns: { session_id, analyzed_at, cards: InsightCard[] }

GET /api/v1/introspection/sessions
  Query: days: int = 30
  Returns: list of session summaries (reuses sessions router logic)
```

**InsightCard schema:**

```json
{
  "type": "skill_forgetting | tool_retry | context_drift | inefficiency",
  "severity": "high | medium | low",
  "title": "string",
  "description": "string",
  "occurrences": ["prompt 4", "prompt 11"],
  "root_cause": "string",
  "best_practices": ["string"],
  "cross_session": { "count": 5, "total": 8 } | null
}
```

**SQL pre-extraction** (runs against Lakebase `zerobus_sdp.otel_logs_mat`):

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
  status_code
FROM zerobus_sdp.otel_logs_mat
WHERE session_id = :session_id
  AND event_name IN ('user_prompt', 'tool_result', 'api_error', 'tool_decision')
ORDER BY event_seq ASC
```

**Cross-session aggregation** (counts sessions with ≥1 tool failure, ≥1 api_error, or skill-reminder keyword in prompt_text, over the last `days` days for the same user).

**FMAPI integration:** Uses `mlflow.deployments.get_deploy_client("databricks")` with model `databricks-meta-llama/Meta-Llama-3.3-70B-Instruct`. System prompt enforces JSON-only output matching the InsightCard schema.

**Registration:** Router mounted in `backend/main.py` at `/api/v1/introspection`.

---

## Frontend

### New Files

**`frontend/src/views/introspection/IntrospectionPage.tsx`**
- Top-level page at route `/introspection`
- Session dropdown (populated from `GET /api/v1/introspection/sessions`)
- Days slider for cross-session context window (7 / 30 / 90 days)
- "Analyze Session" button → `useIntrospectionAnalyze` mutation
- Spinner during analysis, card feed on success

**`frontend/src/views/introspection/components/InsightCard.tsx`**
- Severity badge (high=red, medium=amber, low=purple)
- Pattern type icon (⚠ skill, ✗ tool, ⟳ drift, ⚡ inefficiency)
- Title + description always visible
- Click to expand: root cause paragraph + best practices bullet list
- Cross-session badge (`↻ Seen in N of M sessions`) if `cross_session` is non-null
- `occurrences` rendered as clickable prompt references (links to session timeline)

**`frontend/src/views/introspection/components/InsightCardFeed.tsx`**
- Ordered list of `InsightCard` components
- Sorted: high → medium → low severity

### Modified Files

**`frontend/src/views/sessions/SessionDetailPage.tsx`**
- Add "Insights" tab alongside existing tabs
- Renders `InsightCardFeed` pre-scoped to current `session_id`
- "Analyze" button triggers on first visit; React Query caches result for 5 minutes

**`frontend/src/shared/hooks/useApi.ts`**
- Add `useIntrospectionAnalyze` mutation hook (`POST /api/v1/introspection/analyze`)
- Add `useIntrospectionSessions` query hook (`GET /api/v1/introspection/sessions`)

**`frontend/src/app/`** (sidebar nav + router)
- Add "Introspection" nav item with appropriate icon
- Add `/introspection` route pointing to `IntrospectionPage`

---

## UX Details

### IntrospectionPage flow
1. Dropdown shows sessions from last 30 days (adjustable)
2. User selects session → "Analyze Session" button activates
3. Click → spinner ("Analyzing session…", ~5–15s depending on session size)
4. Cards render sorted by severity
5. Each card collapsed by default; click to expand root cause + best practices

### Session Detail "Insights" tab flow
1. Tab visible alongside Timeline, etc.
2. First click → triggers analysis automatically (no separate button needed)
3. Subsequent visits within 5 min → cached result renders immediately
4. "Re-analyze" button available to force refresh

---

## Constraints & Decisions

| Decision | Choice | Reason |
|---|---|---|
| LLM pipeline | Single SOTA call | Sessions are bounded; two-stage adds latency/complexity without quality gain |
| Model | Meta-Llama-3.3-70B via FMAPI | Available in all Databricks workspaces; no separate API key needed |
| Output format | JSON only | Reliable parsing; frontend owns rendering |
| Caching | React Query 5min TTL | On-demand feel with some repeat-visit speedup; no DB persistence needed |
| Cross-session window | 30 days default | Covers typical work patterns without pulling excessive history |
| Data source | Lakebase `otel_logs_mat` | Already indexed and tuned; same connection used by other routers |
