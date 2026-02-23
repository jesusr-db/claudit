# Claudit Observability App - Design Document

**Date:** 2026-02-20
**Updated:** 2026-02-23 (aligned with actual Claude Code OTEL telemetry)
**Status:** Approved
**Author:** Design session with Claude

## Overview

Claudit is an observability application for tracking Claude Code client usage via OTEL telemetry. It queries OTEL logs and metrics tables directly to provide analytics dashboards and session-level visibility. The architecture is modular, with MCP server logs, Databricks system tables, and inference tables as pluggable backlog extensions.

## Verified Data Model (from live telemetry)

Claude Code emits telemetry via two OTEL signal types:

### otel_logs - Event Stream

All Claude Code events are emitted as OTEL log records. The `body` field contains the event type name; all structured data lives in the `attributes` map.

| event.name | Key Attributes | Description |
|---|---|---|
| `user_prompt` | `prompt`, `prompt_length`, `prompt.id`, `session.id` | User sends a message |
| `api_request` | `model`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`, `cost_usd`, `duration_ms`, `speed` | LLM API call completed |
| `api_error` | `model`, `error`, `status_code`, `duration_ms`, `attempt` | LLM API call failed |
| `tool_decision` | `tool_name`, `decision`, `source` | Tool permission evaluated |
| `tool_result` | `tool_name`, `duration_ms`, `success`, `tool_parameters`, `tool_result_size_bytes`, `decision_source`, `decision_type` | Tool execution completed |

**Common attributes on all events:** `session.id`, `prompt.id`, `event.sequence`, `event.timestamp`, `user.id` (SHA256 hash), `terminal.type`

**Note:** `severity_text`, `severity_number`, `trace_id`, and `span_id` are always null. Claude Code does not emit OTEL spans.

### otel_metrics - Aggregated Counters

Metrics are emitted as OTEL `sum` type with cumulative values per export interval.

| Metric Name | Unit | Breakdown Attributes |
|---|---|---|
| `claude_code.token.usage` | tokens | `type` (input/output/cacheRead/cacheCreation), `model`, `session.id` |
| `claude_code.cost.usage` | USD | `model`, `session.id` |
| `claude_code.active_time.total` | s | `session.id` |
| `claude_code.session.count` | (count) | `session.id` |

**Metric attributes location:** `sum.attributes` (map), values in `sum.value`
**Timestamps:** `sum.start_time_unix_nano`, `sum.time_unix_nano`

### Resource Attributes (both tables)

```json
{
  "service.name": "claude-code",
  "service.version": "2.1.50",
  "os.type": "darwin",
  "host.arch": "arm64",
  "os.version": "25.2.0"
}
```

### Key Identifiers

| Identifier | Source | Format | Notes |
|---|---|---|---|
| `session.id` | attributes | UUID | Groups all events in one Claude Code session |
| `prompt.id` | attributes | UUID | Groups events within one user turn |
| `event.sequence` | attributes | integer | Ordering within a session |
| `user.id` | attributes | SHA256 hex | Anonymized user identity (no email) |

## Requirements

| Requirement | Decision |
|-------------|----------|
| Target users | Platform teams (MVP), Multi-persona (backlog) |
| Data source (MVP) | Direct query on OTEL logs + metrics tables |
| Data source (Backlog) | + MCP server logs, inference tables, system tables |
| Data freshness | Near real-time (OTEL export interval: 5-10s) |
| Scale | Small (1-10 users) |
| Auth | Databricks native OAuth |
| Priority view | Analytics dashboard (MVP), Session timeline (MVP) |

## MVP vs Backlog

### MVP Scope (Direct Query on OTEL Tables)
- **No ETL/materialization required** - query OTEL tables directly
- Token usage over time (from `otel_metrics` or aggregated `api_request` events)
- Cost breakdown by model and session (from `api_request.cost_usd` or `cost.usage` metric)
- Tool usage statistics (from `tool_decision` + `tool_result` events)
- MCP tool patterns (filter `tool_name LIKE 'mcp__%'` on tool events)
- API latency distributions (from `api_request.duration_ms`)
- Error rates and patterns (from `api_error` events)
- Session list and timeline view (from `otel_logs` grouped by `session.id`)

### Backlog - Module 1: Materialized Tables (Scale)
When data volume grows beyond direct-query performance:
- Batch ETL job to pre-compute daily rollups
- Session summary table
- Aggregated daily metrics table

### Backlog - Module 2: MCP Server Logs
- Separate Unity Catalog table for MCP server-side logs
- Correlate with OTEL tool events via timestamp + tool name
- MCP-specific latency and error analysis
- Server-side vs client-side duration comparison

### Backlog - Module 3: Inference Tables
- `{endpoint}_payload_logs` from Databricks Model Serving
- Full request/response payloads for LLM calls
- Token-level cost verification against OTEL-reported costs
- Prompt/response content analysis

### Backlog - Module 4: System Tables
- `system.billing.usage` for infrastructure cost correlation
- `system.serving.served_entities` / `endpoint_usage` for serving metrics
- `system.query.history` for SQL warehouse usage by the app itself

### Backlog - Module 5: User Correlation
- Map `user.id` (SHA256) to user emails via lookup table
- Per-user session tracking and comparison
- Manager dashboards
- User onboarding and adoption metrics

## Architecture

### High-Level Architecture (MVP)

```
+------------------------------------------------------------------+
|                     claudit-observability                         |
|                    (Databricks App - APX)                         |
+------------------------------------------------------------------+
|  React Frontend <--> FastAPI Backend                              |
|  - Dashboard         - /api/v1/metrics/*                         |
|  - Session List      - /api/v1/sessions                          |
|  - Session Timeline  - /api/v1/sessions/{id}/timeline            |
+------------------------------------------------------------------+
                              |
                              | SQL via Databricks SDK
                              v
+------------------------------------------------------------------+
|                 OTEL Source Tables (Unity Catalog)                |
+------------------------------------------------------------------+
| {catalog}.{schema}.otel_logs     - Claude Code event stream      |
| {catalog}.{schema}.otel_metrics  - Aggregated usage counters     |
+------------------------------------------------------------------+
```

### Backlog Architecture Extensions

```
+------------------------------------------------------------------+
|                    Additional Data Sources                        |
+------------------------------------------------------------------+
| {catalog}.{schema}.mcp_server_logs    - MCP server-side logs     |
| {endpoint}_payload_logs               - Inference request/resp   |
| system.billing.usage                  - Infrastructure costs     |
| system.serving.served_entities        - Serving endpoint metrics |
| system.query.history                  - SQL warehouse usage      |
+------------------------------------------------------------------+
                              ^
                              | (Backlog) Batch ETL
                              |
+------------------------------------------------------------------+
|              Materialized Observability Tables                    |
|              (Added when scale requires it)                       |
+------------------------------------------------------------------+
| obs.sessions          - Session summaries with aggregated metrics |
| obs.daily_metrics     - Daily rollups                             |
+------------------------------------------------------------------+
```

### Correlation Strategy (MVP)

All data correlation uses `session.id` from the `attributes` map. No cross-table joins needed for MVP since all events are in `otel_logs`.

**Session discovery:**
```sql
SELECT
  attributes['session.id'] as session_id,
  MIN(attributes['event.timestamp']) as start_time,
  MAX(attributes['event.timestamp']) as end_time,
  COUNT(*) as event_count,
  COUNT(DISTINCT attributes['prompt.id']) as prompt_count
FROM {catalog}.{schema}.otel_logs
GROUP BY attributes['session.id']
ORDER BY start_time DESC
```

**Session timeline:**
```sql
SELECT
  attributes['event.name'] as event_name,
  attributes['event.timestamp'] as ts,
  attributes['event.sequence'] as seq,
  attributes['tool_name'] as tool_name,
  attributes['duration_ms'] as duration_ms,
  attributes['model'] as model,
  attributes['cost_usd'] as cost_usd,
  attributes['input_tokens'] as input_tokens,
  attributes['output_tokens'] as output_tokens,
  attributes['error'] as error,
  attributes['success'] as success,
  attributes['prompt'] as prompt,
  attributes
FROM {catalog}.{schema}.otel_logs
WHERE attributes['session.id'] = :session_id
ORDER BY CAST(attributes['event.sequence'] AS INT) ASC
```

**Cost/token aggregation (from metrics):**
```sql
SELECT
  sum.attributes['session.id'] as session_id,
  sum.attributes['model'] as model,
  name,
  sum.value,
  sum.attributes['type'] as token_type
FROM {catalog}.{schema}.otel_metrics
WHERE name = 'claude_code.token.usage'
```

## API Design

### MVP Endpoints

```
GET  /api/v1/metrics/usage           # Token usage over time
GET  /api/v1/metrics/costs           # Cost breakdown by model/session
GET  /api/v1/metrics/tools           # Tool usage stats (includes MCP tools)
GET  /api/v1/metrics/errors          # Error rates and patterns
GET  /api/v1/metrics/performance     # API latency distributions
GET  /api/v1/metrics/summary         # Overall summary stats

GET  /api/v1/sessions                # List sessions with pagination
GET  /api/v1/sessions/{id}           # Session detail with aggregated stats
GET  /api/v1/sessions/{id}/timeline  # Chronological event stream
```

### Backlog Endpoints

```
GET  /api/v1/sessions/{id}/events/{seq}  # Event detail by sequence
GET  /api/v1/users                       # User list (requires user mapping)
GET  /api/v1/users/{id}/summary          # User summary
GET  /api/v1/mcp/servers                 # MCP server stats (Module 2)
GET  /api/v1/inference/{session_id}      # Inference payloads (Module 3)
```

### Response Examples

**GET /api/v1/sessions**
```json
{
  "sessions": [
    {
      "session_id": "996a6297-0787-454a-94b8-96191aa0a22c",
      "user_id": "c35b69e8...",
      "start_time": "2026-02-23T18:02:20Z",
      "end_time": "2026-02-23T19:30:00Z",
      "event_count": 111,
      "prompt_count": 5,
      "total_cost_usd": 0.44,
      "total_tokens": {"input": 4, "output": 545, "cache_read": 47356, "cache_creation": 68504},
      "tool_calls": 29,
      "errors": 22
    }
  ]
}
```

**GET /api/v1/sessions/{id}/timeline**
```json
{
  "session_id": "996a6297-0787-454a-94b8-96191aa0a22c",
  "events": [
    {
      "sequence": 1,
      "timestamp": "2026-02-23T18:02:20.757Z",
      "event_name": "user_prompt",
      "prompt": "can you review OTEL log configuration...",
      "prompt_length": 93,
      "prompt_id": "efeed64b-0cb7-44ca-9290-6ed36f416478"
    },
    {
      "sequence": 48,
      "timestamp": "2026-02-23T18:06:23.169Z",
      "event_name": "tool_decision",
      "tool_name": "Bash",
      "decision": "accept",
      "source": "config"
    },
    {
      "sequence": 49,
      "timestamp": "2026-02-23T18:06:24.971Z",
      "event_name": "api_request",
      "model": "claude-opus-4-6",
      "duration_ms": 7221,
      "cost_usd": 0.039,
      "input_tokens": 1,
      "output_tokens": 470,
      "cache_read_tokens": 47356,
      "cache_creation_tokens": 521
    },
    {
      "sequence": 50,
      "timestamp": "2026-02-23T18:06:25.499Z",
      "event_name": "tool_result",
      "tool_name": "Bash",
      "duration_ms": 2330,
      "success": true,
      "result_size_bytes": 1274
    }
  ]
}
```

## Frontend Design

### Modular Architecture

```
src/
├── app/                          # App shell
│   ├── App.tsx
│   ├── Layout.tsx
│   ├── providers/
│   └── router/
│       └── viewRegistry.ts       # Central view configuration
│
├── views/                        # Self-contained views
│   ├── landing/
│   ├── dashboard/                # MVP: Analytics dashboard
│   │   ├── DashboardPage.tsx
│   │   └── components/
│   │       ├── TokenUsageChart.tsx
│   │       ├── CostBreakdown.tsx
│   │       ├── ToolUsageTable.tsx
│   │       ├── ErrorRateChart.tsx
│   │       └── LatencyDistribution.tsx
│   ├── sessions/                 # MVP: Session browser
│   │   ├── SessionsPage.tsx
│   │   ├── SessionDetailPage.tsx
│   │   └── components/
│   │       ├── SessionTimeline.tsx
│   │       └── TimelineEvent.tsx
│   └── [future-views]/           # Backlog modules plug in here
│
├── shared/
│   ├── components/
│   ├── hooks/
│   └── utils/
│
└── types/
```

### View Registry

```typescript
const viewRegistry = [
  { id: 'landing', path: '/', component: LandingPage, nav: false },
  { id: 'dashboard', path: '/dashboard', component: DashboardPage,
    icon: ChartIcon, label: 'Dashboard', nav: true },
  { id: 'sessions', path: '/sessions', component: SessionsPage,
    icon: ListIcon, label: 'Sessions', nav: true },
  { id: 'session-detail', path: '/sessions/:id',
    component: SessionDetailPage, nav: false },
  // Backlog modules add entries here
]
```

### Session Timeline (MVP View)

```
Session: 996a6297-0787-454a-94b8-96191aa0a22c       Feb 23, 6:02 PM
User: c35b69e8... | Duration: 1h 28m | Tokens: 116K | Cost: $0.44

Filter: [All] [Prompts] [API Calls] [Tools] [Errors]

Timeline
=========

#1  18:02:20  >>> USER PROMPT
              "can you review OTEL log configuration..."
              └─ prompt_length: 93

#2  18:02:20  ⚠ API ERROR (claude-haiku-4-5-20251001)
              ├─ 404: endpoint does not exist
              └─ Duration: 344ms

#48 18:06:23  ◆ TOOL DECISION: Bash [accept via config]

#49 18:06:24  ○ API REQUEST (claude-opus-4-6)
              ├─ Duration: 7,221ms
              ├─ Tokens: 1 in / 470 out / 47,356 cache_read
              └─ Cost: $0.039

#50 18:06:25  ◆ TOOL RESULT: Bash
              ├─ Duration: 2,330ms
              ├─ Success: true
              └─ Result size: 1,274 bytes
```

### Event Type Color Coding

| Event Type | Icon | Color |
|------------|------|-------|
| user_prompt | >>> | Teal |
| api_request | ○ | Green |
| api_error | ⚠ | Red |
| tool_decision | ◆ | Blue |
| tool_result | ◆ | Blue (muted) |

### Key Libraries

- React 18
- Chakra UI
- Recharts
- TanStack Query (React Query)
- React Router v6
- date-fns

## Deployment

### Project Structure

```
claudit/
├── databricks.yml                # Main DAB bundle
├── app.yaml                      # App config
├── pyproject.toml
├── package.json
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── models/
│   ├── services/
│   └── routers/
├── frontend/
│   └── src/
│       ├── app/
│       ├── views/
│       ├── shared/
│       └── types/
├── resources/
│   ├── apps.yml
│   └── schemas.yml               # Only for backlog materialized tables
└── tests/
```

### DAB Bundle Configuration

**databricks.yml**
```yaml
bundle:
  name: claudit-observability

include:
  - resources/*.yml

variables:
  catalog:
    description: "Unity Catalog containing OTEL tables"
    default: jmr_demo
  schema:
    description: "Schema containing OTEL tables"
    default: zerobus
  warehouse_id:
    description: "SQL Warehouse ID for app queries"

targets:
  dev:
    mode: development
    default: true
    variables:
      catalog: jmr_demo
      schema: zerobus

  prod:
    mode: production
    variables:
      catalog: jmr_demo
      schema: zerobus
    run_as:
      service_principal_name: claudit-service-principal
```

**resources/apps.yml**
```yaml
resources:
  apps:
    claudit_app:
      name: claudit-observability
      description: "Claude Code Observability Dashboard"
      source_code_path: .
      config:
        command:
          - uvicorn
          - "backend.main:app"
          - "--host"
          - "0.0.0.0"
          - "--port"
          - "8000"
        env:
          - name: CATALOG
            value: ${var.catalog}
          - name: SCHEMA
            value: ${var.schema}
          - name: SQL_WAREHOUSE_ID
            value: ${var.warehouse_id}
      resources:
        - name: sql_warehouse
          sql_warehouse:
            id: ${var.warehouse_id}
            permission: CAN_USE
```

### Deployment Commands

```bash
# Validate
databricks bundle validate

# Deploy to dev
databricks bundle deploy -t dev

# Deploy to prod
databricks bundle deploy -t prod
```

## Error Handling

| Layer | Error Type | Handling |
|-------|-----------|----------|
| API | Query timeout | Return 504 with retry hint |
| API | Auth failure | Return 401, redirect to login |
| API | No data found | Return 200 with empty results |
| API | Table not found | Return 503 with setup instructions |
| Frontend | API error | Show toast notification, allow retry |
| Frontend | No results | Show empty state with suggestions |

## Testing Strategy

| Test Type | Coverage | Tool |
|-----------|----------|------|
| Unit (Backend) | Services, query builders | pytest |
| Unit (Frontend) | Components, hooks | Vitest + React Testing Library |
| Integration | API endpoints with test data | pytest + httpx |

## Backlog Roadmap

| Module | Views | Data Source | Dependency |
|--------|-------|-------------|------------|
| 1. Materialized Tables | (performance optimization) | ETL job | Scale > 10K events |
| 2. MCP Server Logs | `/mcp` deep dive | Separate UC table | MCP log ingestion pipeline |
| 3. Inference Tables | `/inference` payloads | `{endpoint}_payload_logs` | Inference table enablement |
| 4. System Tables | `/costs` infrastructure | `system.billing.*`, `system.serving.*` | System table access grants |
| 5. User Correlation | `/users` dashboards | User mapping table | user.id -> email mapping |
| 6. Alerts | `/alerts` configuration | Threshold rules | Modules 1-4 |

## References

- [Claude Code OTEL Setup](https://docs.google.com/document/d/1qK2e14A6hc-wC-vfr1tVfreHoc0qHYpGlP4_GI0quBM/)
- [Claude Code Monitoring Docs](https://docs.claude.com/en/docs/claude-code/monitoring-usage)
