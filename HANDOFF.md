# Developer Efficiency Panel — Deploy & Validate Handoff

**Date:** 2026-04-24 (updated)
**Branch:** `feat/developer-efficiency-panel`  
**Status:** Bundle deployed ✅. Lakebase instance provisioned ✅. `cc_logs_synced` + `cc_spans_synced` ONLINE ✅. **`otel_logs_pg_synced`, `otel_metrics_pg_synced`, `otel_spans_pg_synced` NOT created — setup job is blocked on these. App will return 503 until resolved.**

---

## Lakebase Setup — Blocked State (2026-04-24 session)

### What's working
- `claudit-db` instance: AVAILABLE
- DLT pipeline `f6eb3fee-6a2b-40c0-85d8-99716e645e45` (`[dev jesus_rodriguez] claudit-lakebase-sync`): completed successfully
- `cc_logs_synced` → `SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE` ✅
- `cc_spans_synced` → `SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE` ✅

### What's broken
Three synced tables fail to appear after setup job runs:
- `vdm_classic_rikfy0_catalog.zerobus_sdp.otel_logs_pg_synced`
- `vdm_classic_rikfy0_catalog.zerobus_sdp.otel_metrics_pg_synced`
- `vdm_classic_rikfy0_catalog.zerobus_sdp.otel_spans_pg_synced`

### Root cause chain

1. **Duplicate `row_id` PK violations** — original `otel_logs_pg.sql` and `otel_spans_pg.sql` hash too few fields, causing MD5 collisions in the source MVs. The synced table internal DLT pipeline fails with `PRIMARY_KEY_CONSTRAINT_VIOLATION`, putting the tables into a failed/invisible state.

2. **Orphaned UC metadata** — after destroying the Lakebase instance, the UC synced table metadata for the failed otel_* tables persists. `get_synced_database_table()` throws an unexpected exception (not "does not exist") and `create_synced_database_table()` throws `AlreadyExists`. The setup notebook now handles this, but the tables still don't appear — possibly because their internal DLT sync pipelines are failing silently.

3. **Pipeline refresh timing** — the DLT pipeline update `18c04109` that completed was already in-progress when the hash fix was deployed. The MVs may still have old hashes with duplicates.

### Fixes already applied to source files (committed on branch)

| File | Fix |
|---|---|
| `src/pipelines/lakebase_sync/otel_logs_pg.sql` | Added `observed_time_unix_nano`, `trace_id`, `span_id` to MD5 hash |
| `src/pipelines/lakebase_sync/otel_spans_pg.sql` | Added `end_time_unix_nano`, `name` to MD5 hash |
| `src/pipelines/lakebase_sync/cc_logs.sql` | Added 30-day filter on `time_unix_nano` |
| `src/pipelines/lakebase_sync/cc_spans.sql` | Added 30-day filter on `start_time_unix_nano` |
| `src/pipelines/lakebase_sync/otel_logs_pg.sql` | Added 30-day filter on `time_unix_nano` |
| `src/pipelines/lakebase_sync/otel_spans_pg.sql` | Added 30-day filter on `start_time_unix_nano` |
| `src/pipelines/lakebase_sync/otel_metrics_pg.sql` | Added 30-day filter on `coalesce(sum/histogram/gauge time_unix_nano)` |
| `src/notebooks/lakebase_setup.py` | Removed `SYNC_TIMEOUT` (no timeout — wait indefinitely); handles orphaned UC metadata with delete + recreate logic |

### What to try next

**Option A — Verify the pipeline actually picked up the hash fixes:**
```bash
# Check if otel_logs_pg MV has any duplicate row_ids
databricks sql execute --statement "SELECT row_id, COUNT(*) c FROM vdm_classic_rikfy0_catalog.zerobus_sdp.otel_logs_pg GROUP BY row_id HAVING c > 1 LIMIT 5" --warehouse-id <warehouse_id>
```
If duplicates still exist → run a new full pipeline refresh THEN setup.

**Option B — Manually delete the orphaned synced table UC metadata and recreate:**
```bash
# Check if orphaned tables exist (they may throw on get but exist in UC)
databricks database get-synced-database-table vdm_classic_rikfy0_catalog.zerobus_sdp.otel_logs_pg_synced
# If exists in bad state, delete:
databricks database delete-synced-database-table vdm_classic_rikfy0_catalog.zerobus_sdp.otel_logs_pg_synced
databricks database delete-synced-database-table vdm_classic_rikfy0_catalog.zerobus_sdp.otel_metrics_pg_synced
databricks database delete-synced-database-table vdm_classic_rikfy0_catalog.zerobus_sdp.otel_spans_pg_synced
# Then run a fresh pipeline refresh
databricks pipelines start-update f6eb3fee-6a2b-40c0-85d8-99716e645e45 --full-refresh
# Wait for pipeline to complete, then run setup
databricks jobs run-now 319699144072002
```

**Option C — Remove otel_* synced tables entirely (if not needed for efficiency page):**
The efficiency router only uses `cc_logs_synced` (via `kpi_logs_mat` PG mat view). If the goal is just to validate the Efficiency page, the otel_* tables are only needed for Sessions, MCP Tools, Introspection, and Platform tabs. Consider temporarily removing the 3 otel_* entries from `SYNCED_TABLE_DEFS` in `lakebase_setup.py`, running setup, validating the Efficiency page, then restoring.

### Current DAB resource IDs (post-redeploy)
| Resource | ID |
|---|---|
| Lakebase instance | `claudit-db` |
| Setup job | `319699144072002` |
| Sync job (scheduled) | `238354091206212` |
| Teardown job | `545091098297706` |
| DLT pipeline | `f6eb3fee-6a2b-40c0-85d8-99716e645e45` |
| App | `claudit-observability` |

### App URL
`https://claudit-observability-1351565862180944.aws.databricksapps.com`

---

---

## What Was Built

A **Developer Efficiency Panel** (new "Efficiency" nav tab) implementing the SPACE + DevEx hybrid framework with 5 AI-native metrics. See `research/developer-efficiency-beyond-dora_2026-04-24.md` for the full framework rationale.

### Metrics
| Metric | Endpoint | Description |
|---|---|---|
| AI-Effective Yield (AEY) | `/api/v1/efficiency/aey` | $ cost per accepted in-session edit |
| Cognitive Load Index (CLi) | `/api/v1/efficiency/cognitive-load` | Composite: tools/prompt × context thrash × orphan decisions |
| Feedback Loop Latency | `/api/v1/efficiency/feedback-latency` | p50/p95 seconds per tool type |
| Harness Convergence Score | `/api/v1/efficiency/harness-convergence` | (prompts/session ÷ tools/prompt) × success rate, trended |
| Rework Ratio | `/api/v1/efficiency/rework-ratio` | Repeated Edit/Write to same file within session |

### Commits (newest → oldest)
```
2e77d75 fix(frontend): wire unused interface fields into UI; remove avg_ms from v1
12cbe5c feat(frontend): register Efficiency route and nav icon
fd570a9 feat(frontend): add EfficiencyPage with SPACE+DevEx framework card and charts
4f25d38 fix(frontend): null-safe convergence direction; format rework sub-text
c940311 feat(frontend): add EfficiencyKpiCards, FeedbackLatencyChart, HarnessConvergenceChart
31f66b1 feat(frontend): add efficiency TypeScript types and React Query hooks
7e07cee feat(backend): wire efficiency router into FastAPI app
1b83153 fix(backend): use colon-namespaced cache keys in efficiency router
4429ca2 feat(backend): add efficiency router — AEY, CLi, latency, convergence, rework
166673b fix(tests): move efficiency tests to correct path; fix assertions
5f35591 test: add smoke tests for EfficiencyQueryService SQL builders
b84e48f fix(backend): correct overall_rework_ratio cast binding
1d7064e feat(backend): add EfficiencyQueryService with SPACE+DevEx SQL builders
```

### New Files
| File | Purpose |
|---|---|
| `backend/services/efficiency_query_service.py` | SQL builders for all 5 metrics (PostgreSQL CTEs) |
| `backend/routers/efficiency.py` | FastAPI router, 5 GET endpoints under `/api/v1/efficiency/` |
| `frontend/src/views/efficiency/EfficiencyPage.tsx` | Main page: framework card + KPI cards + charts |
| `frontend/src/views/efficiency/components/EfficiencyKpiCards.tsx` | 5 KPI stat cards |
| `frontend/src/views/efficiency/components/FeedbackLatencyChart.tsx` | Horizontal bar chart: p50/p95 by tool |
| `frontend/src/views/efficiency/components/HarnessConvergenceChart.tsx` | Line chart: convergence score trend |
| `tests/backend/test_efficiency_query_service.py` | 6 smoke tests (all pass, no DB required) |

### Modified Files
| File | Change |
|---|---|
| `backend/routers/__init__.py` | Added `efficiency_router` export |
| `backend/main.py` | Mounted `efficiency_router` |
| `frontend/src/types/api.ts` | Added 7 efficiency interfaces |
| `frontend/src/shared/hooks/useApi.ts` | Added 5 React Query hooks |
| `frontend/src/app/router/viewRegistry.ts` | Registered `/efficiency` route with lazy load |
| `frontend/src/app/Layout.tsx` | Added `FiActivity` icon for Efficiency nav item |

---

## Current Deploy State

`databricks bundle deploy` completed successfully on 2026-04-24. The `claudit-db` lakebase instance was re-provisioned by the bundle (it had been destroyed previously).

Bundle resources (from `databricks bundle summary`):
- **App:** `claudit-observability` — URL not yet active
- **Lakebase instance:** `claudit-db` — provisioned
- **Job: setup** — `[dev jesus_rodriguez] claudit-lakebase-setup` (job_id: `642924768522254`)
- **Job: sync** — `[dev jesus_rodriguez] claudit-lakebase-sync-scheduled` (job_id: `121600141412476`)
- **Job: teardown** — `[dev jesus_rodriguez] claudit-lakebase-teardown` (job_id: `603756289960034`)
- **Pipeline:** `[dev jesus_rodriguez] claudit-lakebase-sync` (pipeline_id: `41d1e42e-301d-41bf-948a-e65d9e7d91ee`)

---

## What Needs to Happen Next

### Step 1: Run the Lakebase setup job

Creates the database schema, views, and materialized view in the provisioned Lakebase instance.

```bash
databricks jobs run-now 642924768522254
# Wait for TERMINATED state (typically 3-5 min)
```

Or via Databricks MCP:
```
manage_job_runs action=run_now job_id=642924768522254
# then manage_job_runs action=wait run_id=<returned run_id>
```

### Step 2: Run the sync pipeline

Syncs `cc_logs` / `cc_spans` from Unity Catalog into Lakebase. Without this, all efficiency queries will return empty results.

```bash
# Option A: trigger the scheduled sync job
databricks jobs run-now 121600141412476

# Option B: trigger the DLT pipeline directly
databricks pipelines start-update --pipeline-id 41d1e42e-301d-41bf-948a-e65d9e7d91ee --full-refresh
```

### Step 3: Deploy the app code

The bundle deploy uploads files but the App itself needs to be deployed/started:

```bash
databricks apps deploy claudit-observability \
  --source-code-path "/Workspace/Users/jesus.rodriguez@databricks.com/.bundle/claudit-observability/dev/files"
```

Then check the app URL from `databricks bundle summary`.

### Step 4: Validate the Efficiency page in browser

Navigate to the app URL → click "Efficiency" in the left nav. Verify:
- [ ] Efficiency tab visible with activity icon
- [ ] `/efficiency` route loads without JS errors
- [ ] Framework card renders (SPACE / DevEx / AI-Native badges visible)
- [ ] 5 KPI cards show non-zero values
- [ ] Feedback Latency chart renders horizontal bars grouped by tool
- [ ] Harness Convergence chart renders a trend line with data points
- [ ] Days selector (7/30/90) updates all cards and charts

### Step 5: Check for backend errors if cards are empty

```bash
databricks apps logs claudit-observability
```

Common failure modes:
- `503 Lakebase not configured` → setup job didn't complete or failed; re-run it
- `relation "zerobus_sdp.cc_logs_synced" does not exist` → sync pipeline hasn't run yet
- SQL errors in efficiency queries → check `backend/services/efficiency_query_service.py`

---

## Data Flow

```
Unity Catalog (jmr_demo.zerobus.cc_logs / cc_spans)
    ↓  [lakebase_sync DLT pipeline]
Lakebase PostgreSQL (claudit-db / databricks_postgres)
    ↓  table: zerobus_sdp.cc_logs_synced
EfficiencyQueryService  →  /api/v1/efficiency/*
    ↓
React hooks (useEfficiencyAey, etc.)  →  EfficiencyPage.tsx
```

The property `settings.kpi_logs_mat_table` in `backend/config.py` is reused by the efficiency service for the source table name.

---

## Important Caveats / Design Decisions

1. **AEY is "In-session" only** — the UI explicitly labels it "In-session AEY" because there's no git/PR correlation yet. This is intentional. Do not remove the label.

2. **No `@chakra-ui/icons`** — this project does NOT have it installed. All icons use `react-icons/fi` or Unicode characters.

3. **Cache keys are colon-namespaced** — efficiency router uses `efficiency:aey:30` (not `efficiency_aey_30`) to avoid collision with the `kpis:` namespace in `backend/routers/kpis.py`.

4. **`frontend/dist/` has new untracked build artifacts** — `EfficiencyPage-B-hRAD5M.js` and related chunks exist in dist but are not committed (dist is gitignored). The bundle deploy sends whatever is in dist. If the efficiency page shows 404, rebuild: `cd frontend && npm run build && cd .. && databricks bundle deploy`.

5. **Tests location** — efficiency tests live at `tests/backend/test_efficiency_query_service.py` (not `backend/tests/`). Run with: `python -m pytest tests/backend/test_efficiency_query_service.py -v`

---

## Reference Files

- **Research / framework spec:** `research/developer-efficiency-beyond-dora_2026-04-24.md`
- **Implementation plan:** `docs/superpowers/plans/2026-04-24-developer-efficiency-panel.md`
- **Previous performance handoff** (KPI mat view, connection pool, etc.): see git history or the section below

---

<!-- ===== PRESERVED FROM PREVIOUS HANDOFF (2026-03-11) ===== -->

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
