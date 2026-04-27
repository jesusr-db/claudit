# Claudit - Claude Code Observability Dashboard

## Architecture
- **Databricks App**: FastAPI backend + React frontend
- **Backend**: FastAPI with routers for metrics, sessions, mcp_tools, platform, mcp_servers, kpis, introspection
- **Frontend**: React + Vite + TypeScript, views/shared/app structure
- **Data**: Unity Catalog tables in `jmr_demo.zerobus`, queried via SQL Warehouse
- **Deployment**: `app.yaml` -> Databricks Apps, uvicorn on port 8000

## Key Files
- `backend/main.py` — FastAPI entry, mounts routers + serves static files
- `backend/routers/` — API routes: metrics, sessions, mcp_tools, platform, mcp_servers, kpis, introspection
- `backend/config.py` — Environment config (CATALOG, SCHEMA_NAME, SQL_WAREHOUSE_ID)
- `frontend/src/views/` — React page components
- `frontend/src/shared/` — Shared components, hooks, utilities
- `frontend/src/app/` — App shell, routing, layout
- `app.yaml` — Databricks App config with env vars
- `databricks.yml` — Asset bundle config
- `design-system/` — Soft UI Evolution design tokens and guidelines

## Conventions
- Commits: conventional commits (feat:, fix:, docs:, refactor:)
- CSS: Soft UI Evolution design system
- Charts: Recharts library
- Backend: FastAPI routers pattern, one router per domain
- Frontend: TypeScript strict, functional components

## Deployment Rules
- **All assets supporting the Claudit app MUST be deployable through Databricks Asset Bundles (DAB).** Do not create bespoke artifacts directly via the API — unless it's strictly for testing purposes.

## Data Architecture Rules
- **Shape data in the Delta MV, never in Lakebase.** All transformations (attribute extraction, type casts, filters, dedup, JSON-to-typed-column conversion) happen in the SDP pipeline (`src/pipelines/lakebase_sync/*.sql`). The synced PG table is consumed directly by the app.
- **No PG materialized views.** Do not `CREATE MATERIALIZED VIEW` in Lakebase. Refresh cycles, staleness, and ownership become hard to reason about; the SDP pipeline already gives us a refresh cadence.
- **No PG views over synced tables for JSONB casting.** If the app needs to read a JSON field as JSONB or as a typed column, extract it in the Delta MV (e.g., `attributes['session.id'] AS session_id`, `CAST(attributes['cost_usd'] AS DOUBLE)`). The synced table should already be in the shape the app reads.
- **App reads typed columns, not `attributes->>'key'` syntax.** If you find yourself writing `->>'something'` in a query, the right fix is to add `something` as a typed column to the source MV in `src/pipelines/lakebase_sync/`, redeploy, and refresh — not to add a PG view that does the cast.
- **Pipeline change → recreate the synced table.** When a Delta MV's schema changes, the existing synced table will fail (schema mismatch). Drop it via `databricks database delete-synced-database-table` AND drop the orphaned PG table (`DROP TABLE zerobus_sdp.<name>`) before re-running setup, or the next create will fail with "Destination table already exists."

## Context Management
- Use subagents for exploratory reads (3+ files), test runs, and search operations
- Keep edits and decision-making in the main conversation
- After compaction, check TaskList to recover progress state
- Update .claude/context-anchor.md with decisions as you go

## Current Focus
- Active feature: Introspection Panel (completed)
- Key decisions: Single FMAPI call with Llama-3.3-70B, user-initiated only, graceful degradation

## Introspection

### Feature "Introspection Panel" -- Phase 1: Implementation (2026-03-19)

#### What worked
- app-developer: Backend router followed existing `cached_execute` + `require_pg_executor` patterns cleanly. The established router pattern (prefix, tags, Pydantic models) made the new endpoint consistent with the rest of the codebase.
- app-developer: Frontend component structure (IntrospectionPage, InsightCard, InsightCardFeed) integrated naturally with existing Chakra UI theme tokens (surface.card, soft-lg, soft.border).
- app-developer: SessionDetailPage tab integration using Chakra Tabs preserved all existing timeline functionality while adding Insights tab.

#### What failed or needed fixing
- app-developer: Initial InsightCard.tsx imported from `@chakra-ui/icons` which is not installed in this project.
  - Error: `TS2307: Cannot find module '@chakra-ui/icons'`
  - Fix: Replaced ChevronDownIcon/ChevronRightIcon with Unicode characters, removed ListIcon and Icon imports.
- app-developer: InsightCardFeed.tsx had unused `Box` and `Icon` imports after the icons fix.
  - Error: `TS6133: 'Box' is declared but its value is never read`
  - Fix: Removed unused imports.

#### Patterns to watch for
- This project does NOT have `@chakra-ui/icons` installed. Use Unicode characters or inline SVG for icons instead of Chakra icon imports.
- Pre-existing TS unused-import warnings exist in `ModelEfficiencyTab.tsx`, `SessionsPage.tsx`, and `TurnaroundPage.tsx` -- these are not regressions.

#### QA iterations
- Attempt 1: PASS -- all 30+ checklist items validated on first attempt.

### Feature "Introspection Panel" -- Phase 2: QA (2026-03-19)

#### What worked
- qa-engineer: All backend Pydantic models, SQL queries, FMAPI integration, and error handling matched spec exactly.
- qa-engineer: All frontend types, hooks, components, and navigation matched spec. No `any` types, no auto-triggers.

#### What failed or needed fixing
- Nothing -- QA passed on first attempt after TypeScript compilation fixes in Phase 1.

#### Patterns to watch for
- The `cached_execute` function in `backend/cache.py` always calls `require_pg_executor()` which raises HTTP 503 if Lakebase is not configured. This is the standard pattern for all data queries and should be relied upon for graceful degradation.
