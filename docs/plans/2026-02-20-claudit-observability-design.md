# Claudit Observability App - Design Document

**Date:** 2026-02-20
**Status:** Approved
**Author:** Design session with Claude

## Overview

Claudit is an end-to-end observability application for tracking Claude Code client metrics, traces, and logs. It provides unified visibility across OTEL tables, MCP server logs, Databricks system tables, and inference table artifacts.

## Requirements

| Requirement | Decision |
|-------------|----------|
| Target users | Multi-persona (developers, managers, platform teams) |
| Data correlation | User + Time hybrid |
| MCP logs source | Separate Unity Catalog table |
| System tables | Billing, serving, query history |
| Inference data | Full inference tables (requests, responses, tokens, latency) |
| Data freshness | Batch (5-15 min) |
| Scale | Small (1-10 users) |
| Auth | Databricks native OAuth |
| Priority view | Session timeline |

## Architecture

### High-Level Architecture

```
+------------------------------------------------------------------+
|                     claudit-observability                         |
|                    (Databricks App - APX)                         |
+------------------------------------------------------------------+
|  React Frontend <--> FastAPI Backend                              |
|  - Session List      - /api/sessions                              |
|  - Timeline View     - /api/sessions/{id}/timeline                |
|  - Dashboard         - /api/metrics/*                             |
+------------------------------------------------------------------+
                              |
                              | SQL via Databricks Connect
                              v
+------------------------------------------------------------------+
|              Materialized Observability Tables                    |
|              (Pre-computed by batch job)                          |
+------------------------------------------------------------------+
| obs.sessions          - Session summaries with aggregated metrics |
| obs.session_events    - All events with unified schema            |
| obs.daily_metrics     - Daily rollups by user                     |
+------------------------------------------------------------------+
                              ^
                              | Batch ETL (every 15 min)
                              |
+------------------------------------------------------------------+
|              Databricks Job: obs_materialization                  |
+------------------------------------------------------------------+
| Task 1: Extract & Correlate - Read sources, apply correlation     |
| Task 2: Aggregate Sessions  - Group events, compute metrics       |
| Task 3: Daily Rollups       - Aggregate by date + user            |
+------------------------------------------------------------------+
                              ^
                              | Reads from
                              |
+------------------------------------------------------------------+
|                    Source Tables (Unity Catalog)                  |
+------------------------------------------------------------------+
| - {catalog}.{schema}.mlflow_experiment_trace_otel_spans           |
| - {catalog}.{schema}.mlflow_experiment_trace_otel_metrics         |
| - {catalog}.{schema}.mlflow_experiment_trace_otel_logs            |
| - {catalog}.{schema}.mcp_server_logs                              |
| - system.billing.usage                                            |
| - system.serving.served_entities / endpoint_usage                 |
| - system.query.history                                            |
| - {endpoint}_payload_logs (inference tables)                      |
+------------------------------------------------------------------+
```

### Data Model

#### Unified Session Event Schema

```python
@dataclass
class SessionEvent:
    session_id: str           # Derived from OTEL resource attributes
    user_email: str           # From OAuth context + OTEL attributes
    timestamp: datetime
    event_type: Literal["metric", "log", "mcp_call", "tool_use", "inference"]
    source_table: str         # Origin table for drill-down
    payload: dict             # Event-specific data
    wall_time_ms: Optional[int]
    api_time_ms: Optional[int]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    tool_name: Optional[str]
    mcp_server: Optional[str]
```

#### Correlation Strategy

Join data sources by user + 5-minute time window:

```sql
WITH session_bounds AS (
  SELECT
    user_id, session_id,
    MIN(timestamp) as session_start,
    MAX(timestamp) as session_end
  FROM otel_metrics
  WHERE metric_name = 'session.start'
  GROUP BY user_id, session_id
)
SELECT s.session_id, m.*
FROM mcp_server_logs m
JOIN session_bounds s
  ON m.user_id = s.user_id
  AND m.timestamp BETWEEN s.session_start AND s.session_end + INTERVAL 5 MINUTES
```

## API Design

### Endpoints

```
GET  /api/v1/sessions                    # List sessions with pagination
GET  /api/v1/sessions/{id}               # Session details
GET  /api/v1/sessions/{id}/timeline      # Chronological events
GET  /api/v1/sessions/{id}/events/{eid}  # Event detail

GET  /api/v1/metrics/usage               # Token usage over time
GET  /api/v1/metrics/costs               # Cost breakdown
GET  /api/v1/metrics/performance         # Wall/API time distributions
GET  /api/v1/metrics/tools               # Tool usage stats
GET  /api/v1/metrics/mcp                  # MCP call patterns

GET  /api/v1/users                        # User list (managers)
GET  /api/v1/users/{email}/summary        # User summary
```

### Response Examples

**GET /sessions/{id}/timeline**
```json
{
  "session_id": "sess_abc123",
  "events": [
    {
      "event_id": "evt_001",
      "timestamp": "2026-02-20T10:30:05Z",
      "event_type": "metric",
      "source": "otel_metrics",
      "summary": "Session started"
    },
    {
      "event_id": "evt_002",
      "timestamp": "2026-02-20T10:30:12Z",
      "event_type": "tool_use",
      "source": "otel_logs",
      "summary": "Tool: Read file /src/main.py",
      "wall_time_ms": 250,
      "tokens": {"input": 1200, "output": 0}
    }
  ]
}
```

## Frontend Design

### Modular Architecture

The frontend uses a plugin-style view system for extensibility:

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
│   ├── sessions/
│   │   ├── SessionsPage.tsx
│   │   ├── SessionDetailPage.tsx
│   │   └── components/
│   │       ├── SessionTimeline.tsx
│   │       └── TimelineEvent.tsx
│   ├── dashboard/
│   └── [future-views]/
│
├── shared/                       # Reusable components
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
  { id: 'sessions', path: '/sessions', component: SessionsPage,
    icon: ListIcon, label: 'Sessions', nav: true },
  { id: 'session-detail', path: '/sessions/:id',
    component: SessionDetailPage, nav: false },
  { id: 'dashboard', path: '/dashboard', component: DashboardPage,
    icon: ChartIcon, label: 'Dashboard', nav: true },
  // Future views just add entries here
]
```

### Session Timeline (Primary View)

```
Session: sess_abc123                                    Feb 20, 10:30 AM
User: dev@company.com | Duration: 45m | Tokens: 57K | Cost: $0.85

Filter: [All] [Metrics] [Tools] [MCP] [Inference]

Timeline
=========

10:30:05  ● SESSION START

10:30:12  ◆ TOOL: Read /src/main.py
          ├─ Duration: 250ms
          └─ Tokens: 1,200 in

10:30:15  ◇ MCP: glean.search("auth patterns")
          ├─ Duration: 850ms (API: 720ms)
          └─ Server: glean

10:30:20  ○ INFERENCE: claude-opus completion
          ├─ Duration: 3,200ms (API: 2,850ms)
          ├─ Tokens: 8,500 in / 2,100 out
          └─ [View Request/Response]

11:15:00  ● SESSION END
```

### Event Type Color Coding

| Event Type | Icon | Color |
|------------|------|-------|
| Session start/end | ● | Gray |
| Tool call | ◆ | Blue |
| MCP call | ◇ | Purple |
| Inference | ○ | Green |
| Error/Warning | ⚠ | Red/Orange |

### Key Libraries

- React 18
- Chakra UI or Ant Design
- Recharts or Chart.js
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
├── frontend/
├── etl/
├── resources/
│   ├── apps.yml
│   ├── jobs.yml
│   └── schemas.yml
└── environments/
    ├── dev.yml
    ├── staging.yml
    └── prod.yml
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
    default: ml
  schema:
    default: claudit_obs
  otel_catalog:
    default: ml
  otel_schema:
    default: otel_ingest
  mcp_logs_table:
    default: ml.mcp_logs.server_logs
  warehouse_id:
    description: "SQL Warehouse ID"

targets:
  dev:
    mode: development
    default: true
    variables:
      catalog: ml_dev
      schema: claudit_obs_dev

  staging:
    mode: development
    variables:
      catalog: ml_staging
      schema: claudit_obs_staging

  prod:
    mode: production
    variables:
      catalog: ml
      schema: claudit_obs
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
          - name: OTEL_CATALOG
            value: ${var.otel_catalog}
          - name: OTEL_SCHEMA
            value: ${var.otel_schema}
          - name: MCP_LOGS_TABLE
            value: ${var.mcp_logs_table}
          - name: SQL_WAREHOUSE_ID
            value: ${var.warehouse_id}
      resources:
        - name: sql_warehouse
          sql_warehouse:
            id: ${var.warehouse_id}
            permission: CAN_USE
```

**resources/jobs.yml**
```yaml
resources:
  jobs:
    obs_materialization:
      name: "${bundle.target}-claudit-obs-materialization"
      schedule:
        quartz_cron_expression: "0 */15 * * * ?"
        timezone_id: "UTC"
      email_notifications:
        on_failure:
          - ${workspace.current_user.userName}
      tasks:
        - task_key: extract_and_correlate
          spark_python_task:
            python_file: etl/obs_materialization.py
            parameters:
              - "--step=extract"
          new_cluster:
            spark_version: "14.3.x-scala2.12"
            num_workers: 0
            spark_conf:
              spark.databricks.cluster.profile: serverless
        - task_key: aggregate_sessions
          depends_on:
            - task_key: extract_and_correlate
          spark_python_task:
            python_file: etl/obs_materialization.py
            parameters:
              - "--step=aggregate"
        - task_key: daily_rollups
          depends_on:
            - task_key: aggregate_sessions
          spark_python_task:
            python_file: etl/obs_materialization.py
            parameters:
              - "--step=rollup"
```

### Deployment Commands

```bash
# Validate
databricks bundle validate

# Deploy to dev
databricks bundle deploy -t dev

# Deploy to prod
databricks bundle deploy -t prod

# Run ETL manually
databricks bundle run obs_materialization -t dev
```

## Error Handling

| Layer | Error Type | Handling |
|-------|-----------|----------|
| API | Query timeout | Return 504 with retry hint |
| API | Auth failure | Return 401, redirect to login |
| API | No data found | Return 200 with empty results |
| ETL | Source table missing | Log warning, continue with available sources |
| ETL | Correlation failure | Write to error table, alert via job notification |
| Frontend | API error | Show toast notification, allow retry |
| Frontend | No results | Show empty state with suggestions |

## Testing Strategy

| Test Type | Coverage | Tool |
|-----------|----------|------|
| Unit (Backend) | Services, query builders | pytest |
| Unit (Frontend) | Components, hooks | Vitest + React Testing Library |
| Integration | API endpoints with test data | pytest + httpx |
| ETL | Transform logic with sample data | pytest + PySpark local |

## Future Roadmap

Placeholder views for future expansion:
- MCP Deep Dive (`/mcp`)
- Cost Analysis (`/costs`)
- Tool Analytics (`/tools`)
- User Comparison (`/users`)
- Alerts (`/alerts`)

## References

- [Claude Code OTEL Setup](https://docs.google.com/document/d/1qK2e14A6hc-wC-vfr1tVfreHoc0qHYpGlP4_GI0quBM/)
- [Claude Code Monitoring Docs](https://docs.claude.com/en/docs/claude-code/monitoring-usage)
- [MLflow OTEL Integration](https://mlflow.org/docs/latest/genai/tracing/integrations/listing/claude_code/)
