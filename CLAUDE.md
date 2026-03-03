# Claudit - Claude Code Observability Dashboard

## Architecture
- **Databricks App**: FastAPI backend + React frontend
- **Backend**: FastAPI with routers for metrics, sessions, mcp_tools, platform, mcp_servers, kpis
- **Frontend**: React + Vite + TypeScript, views/shared/app structure
- **Data**: Unity Catalog tables in `jmr_demo.zerobus`, queried via SQL Warehouse
- **Deployment**: `app.yaml` -> Databricks Apps, uvicorn on port 8000

## Key Files
- `backend/main.py` — FastAPI entry, mounts routers + serves static files
- `backend/routers/` — API routes: metrics, sessions, mcp_tools, platform, mcp_servers, kpis
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

## Context Management
- Use subagents for exploratory reads (3+ files), test runs, and search operations
- Keep edits and decision-making in the main conversation
- After compaction, check TaskList to recover progress state
- Update .claude/context-anchor.md with decisions as you go

## Current Focus
<!-- Update this when starting each session or major phase -->
- Active feature: TBD
- Key decisions: TBD
