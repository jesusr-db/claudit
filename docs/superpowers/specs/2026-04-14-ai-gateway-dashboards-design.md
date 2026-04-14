# AI Gateway Dashboards — Design Spec

**Date:** 2026-04-14
**Status:** Approved
**Scope:** Replace the existing Platform page with a 5-tab AI Gateway analytics dashboard

## Overview

Replace the current Platform page (single chart + two tables) with a comprehensive 5-tab dashboard providing deep visibility into AI Gateway usage. All data sourced from `system.ai_gateway.usage`. Tabs load lazily — only the active tab fetches data.

### Tabs

1. **Overview** — high-level gateway health at a glance
2. **Performance** — latency, TTFB, errors, throughput
3. **Usage** — token consumption, active endpoints/users, model distribution
4. **Coding Agents** — auto-discovered agent traffic breakdown
5. **Token Consumption** — token volume analysis (replaces Cost Insights; no dollar estimates)

### Key Decisions

- **Replace entirely**: current Platform page content is removed; the 5 tabs supersede it
- **Lazy tabs**: Chakra `<Tabs isLazy>` — same pattern as KPI Hub; only active tab renders/fetches
- **Endpoint filter**: single dropdown at the top, populated from distinct `endpoint_name` values, shared across all tabs
- **Time range**: uses the existing global sidebar `TimeRangeContext` (1h / 1d / 7d)
- **Coding agent detection**: auto-discover from `user_agent` field; group by prefix pattern
- **No cost estimates**: Token Consumption tab shows raw token volumes only
- **Dark aesthetic**: dashboard cards use the dark palette from the screenshots (implemented via Chakra theme tokens and inline styles on the dashboard container)

---

## Data Source

**Table:** `system.ai_gateway.usage`

**Key columns used:**

| Column | Type | Used In |
|--------|------|---------|
| `event_time` | timestamp | All tabs (time bucketing) |
| `endpoint_name` | string | All tabs (grouping, filtering) |
| `destination_model` | string | Overview, Usage, Token Consumption |
| `destination_type` | string | Token Consumption |
| `requester` | string | Overview, Usage, Coding Agents, Token Consumption |
| `user_agent` | string | Coding Agents (agent classification) |
| `status_code` | int | Overview, Performance |
| `latency_ms` | bigint | Overview, Performance |
| `time_to_first_byte_ms` | bigint | Overview, Performance |
| `input_tokens` | bigint | Usage, Token Consumption |
| `output_tokens` | bigint | Usage, Token Consumption |
| `total_tokens` | bigint | All tabs |
| `token_details.cache_read_input_tokens` | bigint | Usage (cache hit rate) |
| `token_details.cache_creation_input_tokens` | bigint | Usage |
| `api_type` | string | Performance |

**Data validation (last 30 days):**
- 89,756 rows, 80 endpoints, 36 models, 259 users, 98 user agents
- 3.7B total tokens (3.6B input, 67M output)
- Latency/TTFB populated on 99.9% of rows
- Cache token data on ~46% of rows
- Status codes: 200 (80.7K), 429 (7.8K), 400 (1K), 500 (120)

---

## Architecture

### Frontend Structure

```
frontend/src/views/platform/
├── PlatformPage.tsx              # Shell: endpoint filter + Chakra Tabs isLazy
├── components/
│   ├── EndpointFilter.tsx        # Dropdown populated from /api/v1/platform/ai-gateway/endpoints
│   ├── OverviewTab.tsx           # Tab 1
│   ├── PerformanceTab.tsx        # Tab 2
│   ├── UsageTab.tsx              # Tab 3
│   ├── CodingAgentsTab.tsx       # Tab 4
│   └── TokenConsumptionTab.tsx   # Tab 5
```

**PlatformPage.tsx** manages:
- `selectedEndpoint` state (string | null, null = "All Endpoints")
- Passes `days` from `useTimeRange()` and `selectedEndpoint` to each tab component
- Chakra `<Tabs isLazy variant="soft-rounded" colorScheme="brand">`

Each tab component:
- Accepts `days: number` and `endpoint: string | null` props
- Uses `useQuery` hooks to fetch its own data
- Renders its own chart grid

### Backend Structure

**Router:** `backend/routers/platform.py` — extend with new endpoints

New endpoints (all accept `days: float` and optional `endpoint: str` query params):

| Endpoint | Returns | Used By |
|----------|---------|---------|
| `GET /api/v1/platform/ai-gateway/endpoints` | Distinct endpoint names | EndpointFilter |
| `GET /api/v1/platform/ai-gateway/overview` | KPIs + daily trends + top-N tables | OverviewTab |
| `GET /api/v1/platform/ai-gateway/performance` | Latency/TTFB/errors + status codes + TPM | PerformanceTab |
| `GET /api/v1/platform/ai-gateway/usage` | Token breakdowns + active counts + cache rates | UsageTab |
| `GET /api/v1/platform/ai-gateway/coding-agents` | Agent-grouped metrics + user analytics | CodingAgentsTab |
| `GET /api/v1/platform/ai-gateway/token-consumption` | Token volumes + weekly breakdown + top-N | TokenConsumptionTab |

**Query building:** New methods on `QueryService` in `backend/services/query_service.py`.

**Caching:** All endpoints use `cached_execute()` with 60s TTL (existing pattern).

**Execution:** Queries run against the SQL Warehouse via `get_sql_executor()` (not Lakebase — system tables are Databricks-only).

---

## Tab Specifications

### Tab 1: Overview

**KPI Cards (3):**
- Total Requests: `COUNT(*)`
- Total Tokens: `SUM(total_tokens)` formatted as X.XXB/M/K
- Total Unique Users: `COUNT(DISTINCT requester)`

**Charts (3):**
- Daily Requests — bar chart (Recharts `<BarChart>`), bucketed by date
- Daily Token Usage — bar chart, `SUM(total_tokens)` per day
- Daily Unique Users — line chart (Recharts `<LineChart>`), `COUNT(DISTINCT requester)` per day

**Tables (3):**
- Top Endpoints — `GROUP BY endpoint_name`, sorted by `SUM(total_tokens)` DESC, LIMIT 10
- Top Models — `GROUP BY destination_model`, sorted by `SUM(total_tokens)` DESC, LIMIT 10
- Top Users — `GROUP BY requester`, sorted by `COUNT(*)` DESC, LIMIT 10

**Multi-line Charts (2):**
- TTFB by Endpoint — `AVG(time_to_first_byte_ms)` per day, one line per top-5 endpoint
- Latency by Endpoint — `AVG(latency_ms)` per day, one line per top-5 endpoint

**SQL approach:** Single large query with all aggregations, or separate queries per section. Recommend separate queries to keep each cacheable and parallelizable on the frontend (multiple `useQuery` hooks).

### Tab 2: Performance

**KPI Cards (3):**
- Median Latency: `PERCENTILE(CAST(latency_ms AS DOUBLE), 0.5)`
- Median TTFB: `PERCENTILE(CAST(time_to_first_byte_ms AS DOUBLE), 0.5)`
- Error Count: `COUNT(CASE WHEN status_code != 200 THEN 1 END)`

**Charts (6):**
- Median Latency by Endpoint — multi-line, daily `PERCENTILE(..., 0.5)` per top-5 endpoint
- Status Code Distribution — pie/donut chart (Recharts `<PieChart>`), `GROUP BY status_code`
- Tokens per Minute by Endpoint — multi-line, `SUM(total_tokens) / (time_window_minutes)` per endpoint per day
- Median TTFB by Endpoint — multi-line, daily median per top-5 endpoint
- TTFT Loss — stacked bar per endpoint: TTFB portion vs generation portion (`latency_ms - time_to_first_byte_ms`)
- Error Rate by Endpoint — bar chart, `COUNT(CASE WHEN status_code != 200)` per endpoint

### Tab 3: Usage

**KPI Cards (3):**
- Total Endpoints: `COUNT(DISTINCT endpoint_name)`
- Active Endpoints: `COUNT(DISTINCT endpoint_name)` (same, but labeled as "with traffic in window")
- Active Users: `COUNT(DISTINCT requester)`

**Charts (6):**
- Token Usage by Endpoint — daily stacked bar, one color per top-N endpoint
- Token Usage by Model — daily stacked bar, one color per top-N model
- Token Usage by User — multi-line, one line per top-N requester
- Daily Input vs Output — stacked bar (`SUM(input_tokens)` vs `SUM(output_tokens)` per day)
- Token Volume Distribution — histogram of per-request `total_tokens` (bucket into ranges)
- Cache Hit Rate by Endpoint — horizontal bar, `SUM(cache_read_input_tokens) / SUM(input_tokens)` per endpoint

### Tab 4: Coding Agents

**Agent Classification Logic:**

Parse `user_agent` field into agent groups:

```
claude-cli/* (cli)         → "Claude Code (CLI)"
claude-cli/* (claude-vscode) → "Claude Code (VS Code)"  
claude-cli/* (sdk-py)      → "Claude Code (SDK)"
OpenAI/Python *            → "OpenAI SDK"
AsyncOpenAI/Python *       → "OpenAI SDK (Async)"
Anthropic/Python *         → "Anthropic SDK"
AsyncAnthropic/Python *    → "Anthropic SDK (Async)"
python-requests/*          → "Python Requests"
Mozilla/*                  → "Browser"
*                          → raw user_agent value (truncated)
```

Classification done in SQL via `CASE WHEN user_agent LIKE 'claude-cli%' AND user_agent LIKE '%cli%' THEN 'Claude Code (CLI)' ...` expressions.

**Additional filter:** Coding Agent dropdown (in addition to endpoint filter), populated from distinct classified agent names.

**KPI Cards (3):**
- Total Requests: `COUNT(*)`
- Total Tokens Used: `SUM(total_tokens)`
- Unique Users: `COUNT(DISTINCT requester)`

**Charts (6):**
- Requests by Coding Agent — daily multi-line, one line per agent
- Token Distribution by Agent — horizontal 100% stacked bar
- Latency by Agent — daily multi-line, `AVG(latency_ms)` per agent
- Agent Usage by Endpoint — donut chart, request count per endpoint filtered by agents
- Agent Usage by Model — horizontal 100% stacked bars per agent
- Agent Usage by User — horizontal 100% stacked bars per agent

**Table (1):**
- User Analytics — per-user: user, agent badge, total tokens, requests, avg latency. Sortable.

### Tab 5: Token Consumption

**KPI Cards (3):**
- Total Tokens: `SUM(total_tokens)`
- Total Requests: `COUNT(*)`
- Avg Tokens per Request: `ROUND(SUM(total_tokens) / COUNT(*), 0)`

**Charts (3):**
- Token Consumption over Time — area chart, daily `SUM(total_tokens)`
- Tokens by Destination Type — horizontal bars, `GROUP BY destination_type`
- Weekly Token Consumption by Endpoint — full-width stacked bar, `DATE_TRUNC('week', event_time)` buckets, top-N endpoints

**Tables (3):**
- Top Endpoints by Tokens — `GROUP BY endpoint_name ORDER BY SUM(total_tokens) DESC LIMIT 10`
- Top Models by Tokens — `GROUP BY destination_model ORDER BY SUM(total_tokens) DESC LIMIT 10`
- Top Users by Tokens — `GROUP BY requester ORDER BY SUM(total_tokens) DESC LIMIT 10`

---

## Shared Components

### EndpointFilter

- Fetches distinct endpoint names from `/api/v1/platform/ai-gateway/endpoints`
- Renders a Chakra `<Select>` with "All Endpoints" default
- Lifts `selectedEndpoint` state to `PlatformPage`

### Chart Container Pattern

All chart cards follow the existing Soft UI pattern:
```tsx
<Box bg="surface.card" borderRadius="soft-lg" boxShadow="soft" border="1px solid" borderColor="soft.border" p={4}>
  <Text fontSize="sm" color="gray.500" mb={3}>{title}</Text>
  <ResponsiveContainer width="100%" height={chartHeight}>
    {/* Recharts component */}
  </ResponsiveContainer>
</Box>
```

### Dark Dashboard Container

The dashboard body uses a dark container wrapping all tab content:
```tsx
<Box bg="#0f1724" borderRadius="soft-lg" p={6} minH="80vh">
  {/* Dark-themed cards with bg="#1a2332" */}
</Box>
```

Card tokens inside the dark container:
- Card background: `#1a2332`
- Card border: `1px solid #2d3748`
- Label text: `#94a3b8`
- Value text: `#f8fafc`
- Muted text: `#64748b`
- Table header: `#64748b`
- Table row border: `#1e293b`

### Number Formatting

Reuse existing `formatNumber` pattern:
```ts
function formatNumber(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(2)}K`;
  return n.toLocaleString();
}
```

### Chart Color Palette

Consistent across all tabs:
```ts
const CHART_COLORS = [
  '#06b6d4', // cyan
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#22c55e', // green
  '#ec4899', // pink
  '#ef4444', // red
  '#6366f1', // indigo
  '#14b8a6', // teal
];
```

---

## API Hooks

New hooks in `frontend/src/shared/hooks/useApi.ts`:

```ts
useAiGatewayEndpoints()                          // GET /endpoints
useAiGatewayOverview(days, endpoint)              // GET /overview
useAiGatewayPerformance(days, endpoint)           // GET /performance
useAiGatewayUsage(days, endpoint)                 // GET /usage
useAiGatewayCodingAgents(days, endpoint, agent)   // GET /coding-agents
useAiGatewayTokenConsumption(days, endpoint)      // GET /token-consumption
```

Each returns `useQuery` with appropriate `queryKey` arrays including all filter params.

---

## Backend SQL Queries

### Endpoint Filter Query
```sql
SELECT DISTINCT endpoint_name
FROM system.ai_gateway.usage
WHERE event_time >= current_date() - INTERVAL {days} DAY
ORDER BY endpoint_name
```

### Agent Classification SQL Expression
```sql
CASE
  WHEN user_agent LIKE 'claude-cli%' AND user_agent LIKE '%cli)' THEN 'Claude Code (CLI)'
  WHEN user_agent LIKE 'claude-cli%' AND user_agent LIKE '%claude-vscode%' THEN 'Claude Code (VS Code)'
  WHEN user_agent LIKE 'claude-cli%' AND user_agent LIKE '%sdk-py%' THEN 'Claude Code (SDK)'
  WHEN user_agent LIKE 'OpenAI/Python%' OR user_agent LIKE 'AsyncOpenAI/Python%' THEN 'OpenAI SDK'
  WHEN user_agent LIKE 'Anthropic/Python%' OR user_agent LIKE 'AsyncAnthropic/Python%' THEN 'Anthropic SDK'
  WHEN user_agent LIKE 'python-requests%' THEN 'Python Requests'
  WHEN user_agent LIKE 'Mozilla%' THEN 'Browser'
  ELSE COALESCE(SUBSTRING(user_agent, 1, 30), 'Unknown')
END AS coding_agent
```

### Time Bucketing
Reuse existing pattern from `QueryService._ai_gw_time_filter()`:
- `days <= 0.1` → 5-minute buckets
- `days <= 2` → hourly buckets
- `days > 2` → daily buckets

For Token Consumption weekly chart: `DATE_TRUNC('WEEK', event_time)`.

---

## Files to Create/Modify

### New Files
- `frontend/src/views/platform/components/EndpointFilter.tsx`
- `frontend/src/views/platform/components/OverviewTab.tsx`
- `frontend/src/views/platform/components/PerformanceTab.tsx`
- `frontend/src/views/platform/components/UsageTab.tsx`
- `frontend/src/views/platform/components/CodingAgentsTab.tsx`
- `frontend/src/views/platform/components/TokenConsumptionTab.tsx`

### Modified Files
- `frontend/src/views/platform/PlatformPage.tsx` — rewrite with Tabs shell
- `frontend/src/shared/hooks/useApi.ts` — add 6 new hooks
- `frontend/src/types/api.ts` — add response types for new endpoints
- `backend/routers/platform.py` — add 6 new endpoints (can remove old 3)
- `backend/services/query_service.py` — add query builder methods per endpoint

### Unchanged
- `backend/config.py` — already has `ai_gateway_usage_table` property
- `frontend/src/app/router/viewRegistry.ts` — Platform route stays the same
- `frontend/src/app/Layout.tsx` — sidebar entry stays the same

---

## Error Handling

- If SQL Warehouse is unavailable: `get_sql_executor()` returns None and endpoints raise HTTP 503
- If endpoint filter returns empty: show "No data for selected time range" empty state
- If a tab query fails: show per-tab error state with retry button (don't break other tabs)
- If `user_agent` is NULL: classify as "Unknown" in Coding Agents tab
- Cache token columns can be NULL: use `COALESCE(..., 0)` in SQL

## Testing

- Verify all 6 new backend endpoints return valid JSON with real data
- Verify endpoint filter populates with distinct endpoints
- Verify tab switching only triggers data fetch on first activation
- Verify time range changes re-fetch data for the active tab
- Verify endpoint filter changes re-fetch data for the active tab
- TypeScript strict: no `any` types in new code
