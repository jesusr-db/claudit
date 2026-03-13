# Lakebase Migration Design — Claudit Observability

**Date:** 2026-03-10
**Status:** Approved
**Scope:** Migrate Claudit from SQL Warehouse to Lakebase Autoscaling for all OTEL data queries

## Context

Claudit is a Databricks App (FastAPI + React) that queries OTEL telemetry tables via a SQL Warehouse. The app reads from 5 Delta tables across 2 schemas. This design migrates the data path to Lakebase Autoscaling (managed PostgreSQL), syncing Delta tables via Lakebase sync pipelines and replacing the SQL Warehouse executor with a PostgreSQL executor.

## Decisions

| Decision | Choice |
|---|---|
| Lakebase tier | Autoscaling (`databricks postgres` CLI) |
| SQL migration | Full cutover — no dual executor, no fallback |
| Environment model | Single project (`claudit-otel`), branch per DAB target |
| Sync scope | All 5 OTEL tables across both schemas |
| Pipeline model | Shared single pipeline via `existing_pipeline_id` |
| Scheduling policy | SNAPSHOT |
| SP access | Dynamic discovery from app resource |
| DAB approach | Single job + notebook, fully DAB-managed |

## Architecture

### Current State

```
Delta Tables (Unity Catalog)
  -> SQL Warehouse (statement_execution API)
    -> SqlExecutor
      -> Query Services (Databricks SQL syntax)
        -> FastAPI Routers -> React Frontend
```

### Target State

```
Delta Tables (Unity Catalog)
  -> Lakebase Sync Pipeline (SNAPSHOT, shared)
    -> Lakebase Autoscaling (PostgreSQL)
      -> PgExecutor (psycopg3 + OAuth token refresh)
        -> Query Services (PostgreSQL syntax)
          -> FastAPI Routers -> React Frontend
```

## Section 1: Lakebase Infrastructure

### Lakebase Project

- **Project ID:** `claudit-otel`
- **Branch model:** `production` branch (auto-created with project), used by both dev/prod targets
- **Endpoint:** `primary` (read-write, auto-created with project)
- **PostgreSQL database:** `claudit` (created inside the instance)

### Sync Pipeline

All 5 tables share a single pipeline. The first table creates the pipeline via `new_pipeline_spec`; tables 2-5 reference it via `existing_pipeline_id`.

| Source Delta Table | Lakebase PG Table | Sync Order |
|---|---|---|
| `{catalog}.zerobus.otel_logs` | `claudit.zerobus_otel_logs` | 1 (creates pipeline) |
| `{catalog}.zerobus.otel_metrics` | `claudit.zerobus_otel_metrics` | 2 |
| `{catalog}.default.otel_spans` | `claudit.mcp_otel_spans` | 3 |
| `{catalog}.default.otel_logs` | `claudit.mcp_otel_logs` | 4 |
| `{catalog}.default.otel_metrics` | `claudit.mcp_otel_metrics` | 5 |

### SP Grants

The setup notebook dynamically discovers the app's service principal via `w.apps.get("claudit-observability")`, then grants `SELECT` on all synced tables via PostgreSQL `GRANT` statements.

### DAB Resources

**New variable in `databricks.yml`:**

```yaml
lakebase_project:
  description: "Lakebase Autoscaling project ID"
  default: claudit-otel
lakebase_branch:
  description: "Lakebase branch name"
  default: production
lakebase_endpoint:
  description: "Lakebase endpoint name"
  default: primary
lakebase_database:
  description: "Lakebase PostgreSQL database name"
  default: claudit
```

The `warehouse_id` variable is removed.

**New resource `resources/lakebase_setup.yml`:**
- Job `lakebase_setup` with a single notebook task (`src/notebooks/lakebase_setup.py`)
- Parameterized with all Lakebase and catalog variables

**Updated `resources/apps.yml`:**
- Remove `sql_warehouse` resource
- Add `database` resource pointing to Lakebase instance
- Env vars change from `SQL_WAREHOUSE_ID` to `LAKEBASE_PROJECT_ID`, `LAKEBASE_BRANCH`, `LAKEBASE_ENDPOINT`, `LAKEBASE_DATABASE`

## Section 2: Backend Migration

### PgExecutor (replaces SqlExecutor)

New file `backend/services/pg_executor.py`:

- Same interface as `SqlExecutor`: `execute(query: str) -> List[Dict[str, Any]]`
- Uses `psycopg` (v3) with connection pooling
- OAuth token from `w.database.generate_database_credential()`
- Background token refresh every 50 minutes (tokens expire at 1 hour)
- Token injected into connections via psycopg's connection event

### Config Changes (`backend/config.py`)

Remove:
- `sql_warehouse_id`

Add:
- `lakebase_project_id: str`
- `lakebase_branch: str = "production"`
- `lakebase_endpoint: str = "primary"`
- `lakebase_database: str = "claudit"`

Table properties return PG table names (no catalog prefix):
- `otel_logs_table` -> `"zerobus_otel_logs"`
- `otel_metrics_table` -> `"zerobus_otel_metrics"`
- `mcp_otel_spans_table` -> `"mcp_otel_spans"`
- `mcp_otel_logs_table` -> `"mcp_otel_logs"`
- `mcp_otel_metrics_table` -> `"mcp_otel_metrics"`

### SQL Syntax Migration

All 4 query services are rewritten for PostgreSQL syntax:

| Pattern | Databricks SQL | PostgreSQL |
|---|---|---|
| Map access | `attributes['key']` | `attributes->>'key'` |
| Nested map | `resource.attributes['key']` | `resource_attributes->>'key'` |
| Cast timestamp | `CAST(x AS TIMESTAMP)` | `x::timestamp` |
| Nano conversion | `TIMESTAMP_MICROS(CAST(x / 1000 AS BIGINT))` | `to_timestamp(x::bigint / 1000000000.0)` |

**Note:** Delta columns with dots (e.g., `resource.attributes`) may map to underscores in PG (`resource_attributes`). Actual column names must be verified after first sync.

### Affected Query Services

- `backend/services/query_service.py` — main claude-code logs/metrics
- `backend/services/mcp_query_service.py` — MCP server spans/logs/metrics
- `backend/services/kpi_query_service.py` — composite KPI queries

All routers updated to instantiate `PgExecutor` instead of `SqlExecutor`.

### Dependencies

Add to `requirements.txt`:
- `psycopg[binary]>=3.0`

## Section 3: Deployment Flow

### DAB Configuration

**`databricks.yml` changes:**
- Remove `warehouse_id` variable
- Add `lakebase_project`, `lakebase_branch`, `lakebase_endpoint`, `lakebase_database` variables
- Both targets (`dev`, `prod`) use defaults (single Lakebase project, shared)

**`app.yaml` changes:**
- Remove `SQL_WAREHOUSE_ID` env var
- Add `LAKEBASE_PROJECT_ID`, `LAKEBASE_BRANCH`, `LAKEBASE_ENDPOINT`, `LAKEBASE_DATABASE` env vars

### Deployment Sequence

```bash
1. databricks bundle deploy -t dev        # Deploys app + setup job
2. databricks bundle run lakebase_setup   # Creates project, syncs tables, grants SP
3. databricks bundle run claudit_app      # Starts the app (now using Lakebase)
```

Step 2 is idempotent — safe to re-run after redeployments or SP changes.

### Setup Notebook Logic (`src/notebooks/lakebase_setup.py`)

1. Create Lakebase project `claudit-otel` (skip if exists)
2. Wait for `production` branch and `primary` endpoint to reach ACTIVE state
3. Create PostgreSQL database `claudit` (skip if exists)
4. Create first synced table with `new_pipeline_spec` (captures pipeline ID)
5. Create remaining 4 synced tables with `existing_pipeline_id`
6. Discover app SP via `w.apps.get("claudit-observability")`
7. Grant SP `SELECT` on all synced tables

## Section 4: Error Handling

### Token Refresh
- Background task refreshes OAuth token every 50 minutes
- On failure: log error, retry with exponential backoff (max 3 retries)
- Connection pool picks up fresh token via `do_connect` event

### Setup Notebook Idempotency
- Project creation: check existence via `get-project` before creating
- Synced tables: check existence before creating
- Grants: PostgreSQL `GRANT` is idempotent
- If one table sync fails, log error, continue with remaining tables
- Returns summary of success/failure per table

### Column Name Mapping
- Delta columns with dots may become underscores in PG
- Setup notebook verifies actual PG column names after first sync
- Query services use verified column names

### App Startup Resilience
- `PgExecutor` retries connection with backoff if Lakebase is temporarily unavailable
- `/health` endpoint verifies PG connectivity

## File Changes Summary

```
MODIFIED  databricks.yml                    — new vars, remove warehouse_id
MODIFIED  app.yaml                          — lakebase env vars
MODIFIED  requirements.txt                  — add psycopg
MODIFIED  resources/apps.yml                — database resource, new env vars
NEW       resources/lakebase_setup.yml      — setup job
NEW       src/notebooks/lakebase_setup.py   — provisioning notebook
NEW       backend/services/pg_executor.py   — PostgreSQL executor
DELETED   backend/services/sql_executor.py  — replaced by pg_executor
MODIFIED  backend/config.py                 — lakebase settings
MODIFIED  backend/services/query_service.py     — PG syntax
MODIFIED  backend/services/mcp_query_service.py — PG syntax
MODIFIED  backend/services/kpi_query_service.py — PG syntax
MODIFIED  backend/routers/*.py              — use PgExecutor
```
