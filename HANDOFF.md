# KPI Performance Optimization Handoff

**Date:** 2026-03-11
**Branch:** `lakebase`
**Status:** KPI panel load times reduced from 30s+ timeouts (504) to sub-5ms queries. All 4 KPI tabs render data.

## Problem

Most KPI endpoints were returning **504 Gateway Timeout** errors on the deployed Databricks App. 12 of 17 KPI endpoints timed out, making the KPI Hub unusable.

**Root cause:** Every query cast `TEXT → JSONB` on every row of every CTE. With 4086 rows and queries containing 6-8 chained CTEs, each CTE re-parsed the JSON. The Lakebase Provisioned instance (CU_1) couldn't complete these within the 30s proxy timeout.

## What Was Done

### 1. Materialized View with Pre-Extracted Columns

Created `zerobus_sdp.kpi_logs_mat` — a PostgreSQL materialized view that extracts 16 JSONB attributes into typed columns once, at refresh time:

```
otel_logs_pg_synced (TEXT attributes)
  → kpi_logs_mat (session_id TEXT, event_name TEXT, event_ts TIMESTAMP,
                  cost_usd DOUBLE, input_tokens BIGINT, model TEXT, ...)
```

**Query performance before/after:**
| Query | Before | After |
|-------|--------|-------|
| cost_overview | 504 timeout | 1.4ms |
| model_performance_matrix (8 CTEs) | 504 timeout | 3.9ms |
| kpi_badges (5 CTEs) | 504 timeout | 4.3ms |
| All other KPI queries | 504 timeout | 1-5ms |

### 2. Four Indexes on the Materialized View

```sql
idx_mat_service_event_ts   (service_name, event_name, event_ts)  -- main filter pattern
idx_mat_session_prompt     (session_id, prompt_id)               -- GROUP BY pattern
idx_mat_event_ts           (event_ts)                            -- time range scans
idx_mat_session_prompt_seq (session_id, prompt_id, event_seq)    -- window functions
```

### 3. Rewrote All KPI Queries

**File:** `backend/services/kpi_query_service.py`

All 16 KPI query methods now use `kpi_logs_mat` with direct column access:
- `attributes->>'session.id'` → `session_id`
- `(attributes->>'cost_usd')::double precision` → `cost_usd`
- `(attributes->>'event.timestamp')::timestamp` → `event_ts`

Added `_prompt_complexity_cte()` helper to DRY the repeated prompt-events → complexity bucketing pattern used by all 5 Phase 4 queries.

The `build_e2e_flow_summary()` query still uses the JSONB spans view since `otel_spans` has 0 rows (no MCP span data yet).

Added `build_refresh_mat_view()` method for on-demand refresh.

### 4. Backend Caching & Timeout Protection

**File:** `backend/routers/kpis.py`
- Added 60-second TTL in-memory cache (`_cached_execute`) — identical queries within 60s return cached results
- Added `POST /api/v1/kpis/refresh` endpoint to refresh the materialized view and clear cache
- Added request-level logging: `KPI query cost_overview:7: 3ms (1 rows)`

**File:** `backend/services/pg_executor.py`
- Added `SET statement_timeout = 25000` before each query — prevents queries from running until the proxy kills them at 30s, giving a clear error instead

### 5. DAB Automation

**File:** `src/notebooks/lakebase_setup.py`
- Added **Step 4b** between view creation and SP grants
- Creates the materialized view and all 4 indexes after synced tables come online
- Idempotent: uses `DROP MATERIALIZED VIEW IF EXISTS ... CASCADE` then recreates
- Added `ALTER DEFAULT PRIVILEGES IN SCHEMA zerobus_sdp GRANT SELECT ON TABLES TO "{sp_role}"` to cover future objects

### 6. Instance Reference Fix

All code now references `claudit-db` instead of `zerobus-dev`:
- `app.yaml` — `LAKEBASE_INSTANCE_NAME: claudit-db`
- `backend/config.py` — default `lakebase_instance_name: "claudit-db"`
- `src/notebooks/lakebase_setup.py` — widget default
- `src/notebooks/lakebase_teardown.py` — widget default

## Architecture

```
Delta Tables (Unity Catalog)
  │
  ├── SDP Pipeline (lakebase_sync) → MVs with synthetic row_id PK
  │
  ├── Synced Database Tables → Lakebase Provisioned (claudit-db)
  │     └── otel_logs_pg_synced     ✅ ONLINE
  │     └── otel_metrics_pg_synced  ✅ ONLINE
  │     └── otel_spans_pg_synced    ✅ ONLINE
  │
  ├── PG Views (cast text→jsonb for ->>'key' support)
  │     └── zerobus_sdp.otel_logs
  │     └── zerobus_sdp.otel_metrics
  │     └── zerobus_sdp.otel_spans
  │
  ├── KPI Materialized View (pre-extracted columns + indexes)  ← NEW
  │     └── zerobus_sdp.kpi_logs_mat  (4086 rows, 4 indexes)
  │
  └── System Tables → SQL Warehouse → SqlExecutor → platform/flow audit
```

**Lakebase Instance:** `claudit-db` (Provisioned, CU_1, AVAILABLE)
**PG Host:** `instance-0e8c1546-218c-4d07-a73d-c08d9fbdf375.database.cloud.databricks.com`
**PG Database:** `claudit`
**App URL:** `https://claudit-observability-1351565862180944.aws.databricksapps.com`

## Files Changed

| File | Change |
|---|---|
| `backend/services/kpi_query_service.py` | Rewrote all 16 queries to use `kpi_logs_mat`, added `_prompt_complexity_cte()` helper, added `build_refresh_mat_view()` |
| `backend/routers/kpis.py` | Added TTL cache, logging, `POST /refresh` endpoint |
| `backend/services/pg_executor.py` | Added `statement_timeout` parameter |
| `backend/config.py` | Added `kpi_logs_mat_table` property, updated instance default to `claudit-db` |
| `app.yaml` | Updated `LAKEBASE_INSTANCE_NAME` to `claudit-db` |
| `src/notebooks/lakebase_setup.py` | Added Step 4b (mat view + indexes), `ALTER DEFAULT PRIVILEGES`, updated instance default |
| `src/notebooks/lakebase_teardown.py` | Updated instance default |

## Next Steps to Improve Performance

### Priority 1: Automate Mat View Refresh

The materialized view is a snapshot — it doesn't update automatically when new OTEL data syncs. Options:

**Option A: Periodic refresh via DAB job**
Add a scheduled job in `resources/` that runs `REFRESH MATERIALIZED VIEW CONCURRENTLY zerobus_sdp.kpi_logs_mat` every 15-30 minutes. This is the simplest approach and keeps data reasonably fresh.

**Option B: Refresh on sync completion**
Chain the mat view refresh to the lakebase_sync pipeline completion. Add a task to the `lakebase_setup.yml` job or create a new job triggered by pipeline success.

**Option C: App-level background refresh**
Add a background thread in the FastAPI app that calls `REFRESH MATERIALIZED VIEW CONCURRENTLY` every N minutes. This avoids a separate job but ties the refresh lifecycle to the app.

The `POST /api/v1/kpis/refresh` endpoint already exists for manual/ad-hoc refresh.

### Priority 2: Connection Pool Optimization

Currently: max 5 connections, all KPI queries are synchronous (`require_pg_executor().execute()`). When the frontend fires 15+ queries in parallel across tabs, they queue.

**Fix:** Make router endpoints truly async using `asyncio.to_thread()`:
```python
@router.get("/cost/overview")
async def get_cost_overview(days: int = Query(30)):
    query = kpi_service.build_cost_overview(days=days)
    rows = await asyncio.to_thread(_cached_execute, f"cost_overview:{days}", query)
    return rows[0] if rows else {...}
```

And increase pool size to 10 (`max_size=10` in `PgExecutor._create_pool`).

### Priority 3: Warm Cache on Startup

The first request after deploy always hits the database cold. Add an `@app.on_event("startup")` handler that pre-fetches the most common queries (badges, cost_overview, effectiveness_overview) to warm the cache.

### Priority 4: Replace In-Memory Cache with Proper Solution

The current `dict`-based cache doesn't survive app restarts and has no size limits. For a single-instance app this is fine, but consider:
- `cachetools.TTLCache` with max size
- Redis if scaling to multiple app instances

### Priority 5: Reduce Frontend Parallel Query Burst

The frontend fires all queries for a tab simultaneously. For tabs with 5 queries, this means 5 concurrent DB connections consumed instantly. Consider:
- Staggering queries (load hero stats first, then charts, then tables)
- Combining related queries into single endpoints (e.g., `/cost/all` returns overview + trend + models)

### Priority 6: Scale Lakebase Instance

If data volume grows beyond ~50K rows, the CU_1 instance may become a bottleneck again. Options:
- Upgrade to CU_2 or CU_4 for more compute
- Add a read replica using `read_only_dns` for query traffic

## Deploy & Verify

```bash
# Deploy all resources
databricks bundle deploy -t dev

# Deploy app code
databricks apps deploy claudit-observability \
  --source-code-path "/Workspace/Users/jesus.rodriguez@databricks.com/.bundle/claudit-observability/dev/files"

# Verify health
curl -s https://claudit-observability-1351565862180944.aws.databricksapps.com/health
# Expected: {"status":"healthy","lakebase":"connected"}

# Refresh mat view (after new data syncs)
curl -X POST https://claudit-observability-1351565862180944.aws.databricksapps.com/api/v1/kpis/refresh
```

## Connection Details

```bash
# Generate PG credential
TOKEN=$(databricks database generate-database-credential \
  --json '{"request_id": "'$(uuidgen)'", "instance_names": ["claudit-db"]}' \
  --output json | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Connect to claudit database
EMAIL=$(databricks current-user me --output json | python3 -c "import sys,json; print(json.load(sys.stdin)['userName'])")
PGPASSWORD="$TOKEN" psql "host=instance-0e8c1546-218c-4d07-a73d-c08d9fbdf375.database.cloud.databricks.com port=5432 dbname=claudit user=$EMAIL sslmode=require"

# Check mat view freshness
SELECT COUNT(*), MAX(event_ts) as latest FROM zerobus_sdp.kpi_logs_mat;

# Manual refresh
REFRESH MATERIALIZED VIEW zerobus_sdp.kpi_logs_mat;
```
