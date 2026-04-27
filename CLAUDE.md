# Claudit - Claude Code Observability Dashboard

## Architecture

```
                                              ┌──────────────────────┐
Unity Catalog                                 │  Lakebase            │
(source OTEL tables)                          │  (Postgres / OLTP)   │
─────────────────────                         │  instance: claudit-db│
catalog.zerobus.otel_logs        ─┐           │                      │
catalog.zerobus.otel_metrics      │           │  zerobus_sdp.        │
catalog.zerobus.otel_spans        │           │    cc_logs_synced    │
                                  │           │    cc_spans_synced   │
                                  ▼           │    otel_logs_pg_     │
              ┌───────────────────────┐       │      synced          │
              │  SDP Pipeline         │       │    otel_spans_pg_    │
              │  (lakebase_sync)      │──────▶│      synced          │
              │  5 Delta MVs:         │       │    otel_metrics_pg_  │
              │   - cc_logs           │       │      synced          │
              │   - cc_spans          │       │                      │
              │   - otel_logs_pg      │       │  (typed columns,     │
              │   - otel_spans_pg     │       │   no views, no MVs)  │
              │   - otel_metrics_pg   │       └──────────┬───────────┘
              └───────────────────────┘                  │
                                                         ▼
                                              ┌──────────────────────┐
                                              │  FastAPI App         │
                                              │  (uvicorn, Apps)     │
                                              │  + React frontend    │
                                              └──────────────────────┘
                                                         │
                                                         ▼
                                              ┌──────────────────────┐
                                              │  Databricks SQL      │
                                              │  Warehouse           │
                                              │  (system.* tables    │
                                              │   for billing,       │
                                              │   query history,     │
                                              │   AI Gateway)        │
                                              └──────────────────────┘
```

- **Databricks App**: FastAPI backend + React frontend served by uvicorn on port 8000
- **Two data sources**:
  - **Lakebase Postgres** (`claudit-db`) — primary store for OTEL telemetry. Synced tables in `zerobus_sdp.*` are queried via `PgExecutor` with OAuth tokens.
  - **SQL Warehouse** — system tables (`system.billing`, `system.query`, `system.ai_gateway`, etc.) queried via `SqlExecutor`.
- **Source OTEL tables** live in Unity Catalog: `${catalog}.zerobus.otel_{logs,metrics,spans}` (`vdm_classic_rikfy0_catalog` in dev, `jmr_demo` in prod).

## Key Files
- `backend/main.py` — FastAPI entry, mounts routers + serves static frontend
- `backend/routers/` — one router per domain: `metrics`, `sessions`, `kpis`, `efficiency`, `introspection`, `mcp_servers`, `mcp_tools`, `platform`
- `backend/services/` — query builders: `query_service`, `kpi_query_service`, `mcp_query_service`, `efficiency_query_service`
- `backend/services/pg_executor.py` — Lakebase Postgres connection pool with OAuth token refresh
- `backend/cache.py` — `cached_execute` (60s TTL) + `require_pg_executor` (raises 503 if Lakebase not configured)
- `backend/config.py` — env-driven config; `*_table` properties resolve to synced-table names in `zerobus_sdp`
- `frontend/src/views/` — page components: `dashboard`, `sessions`, `kpis`, `efficiency`, `introspection`, `mcp-servers`, `mcp-tools`, `platform`
- `frontend/src/shared/` — shared components, hooks, utilities
- `frontend/src/app/` — app shell, routing, layout
- `src/pipelines/lakebase_sync/*.sql` — 5 Delta MVs that pre-shape data for direct PG consumption
- `src/notebooks/lakebase_setup.py` — DAB job that creates synced tables, indexes, and grants
- `app.yaml` / `databricks.yml` / `resources/*.yml` — Databricks Asset Bundle config
- `design-system/claudit/MASTER.md` — Soft UI Evolution design tokens

## Conventions
- Commits: conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)
- CSS: Soft UI Evolution design system tokens (`surface.card`, `soft-lg`, `soft.border`)
- Charts: Recharts library
- Backend: FastAPI routers pattern, one router per domain
- Frontend: TypeScript strict, functional components, Chakra UI
- Icons: this project does **NOT** have `@chakra-ui/icons` installed. Use `react-icons/fi` or Unicode characters.

## Deployment Rules
- **All assets supporting the Claudit app MUST be deployable through Databricks Asset Bundles (DAB).** Do not create bespoke artifacts directly via the API — unless it's strictly for testing purposes.

## Data Architecture Rules
- **Shape data in the Delta MV, never in Lakebase.** All transformations (attribute extraction, type casts, filters, dedup, JSON-to-typed-column conversion) happen in the SDP pipeline (`src/pipelines/lakebase_sync/*.sql`). The synced PG table is consumed directly by the app.
- **No PG materialized views.** Do not `CREATE MATERIALIZED VIEW` in Lakebase. Refresh cycles, staleness, and ownership become hard to reason about; the SDP pipeline already gives us a refresh cadence.
- **No PG views over synced tables for JSONB casting.** If the app needs to read a JSON field as JSONB or as a typed column, extract it in the Delta MV (e.g., `attributes['session.id'] AS session_id`, `CAST(attributes['cost_usd'] AS DOUBLE)`). The synced table should already be in the shape the app reads.
- **App reads typed columns, not `attributes->>'key'` syntax.** If you find yourself writing `->>'something'` in a query, the right fix is to add `something` as a typed column to the source MV in `src/pipelines/lakebase_sync/`, redeploy, and refresh — not to add a PG view that does the cast.
- **Pipeline change → recreate the synced table.** When a Delta MV's schema changes, the existing synced table will fail (schema mismatch). Drop it via `databricks database delete-synced-database-table` AND drop the orphaned PG table (`DROP TABLE zerobus_sdp.<name>`) before re-running setup, or the next create will fail with "Destination table already exists."
- **Profile source data before designing a metric.** Before writing any SQL for a new panel, run `SELECT event_name, COUNT(*), COUNT(col1), COUNT(col2)... FROM source GROUP BY event_name` to confirm every column the metric depends on is actually populated. Several of the original Efficiency-panel metrics shipped against fields that are 0% populated (e.g., `tool_parameters`) and silently returned empty.

## Context Management
- Use subagents for exploratory reads (3+ files), test runs, and search operations
- Keep edits and decision-making in the main conversation
- After compaction, check TaskList to recover progress state

## Patterns to know
- `cached_execute(key, query)` always calls `require_pg_executor()` which raises HTTP 503 if Lakebase isn't configured. This is the standard graceful-degradation point for all PG-backed endpoints.
- App-SP-vs-Lakebase race: the very first deploy of an app with a `lakebase` resource on a brand-new instance fails with `Role X not found in instance claudit-db` because the PG role is provisioned async by the grant attempt. Workaround: deploy the app once without the `lakebase` resource block, then add it back and redeploy.
