# Claudit Project Handoff

**Date:** 2026-02-23
**Status:** MVP deployed and running on Databricks Apps
**Branch:** `feature/claudit-mvp` (worktree at `.worktrees/claudit-mvp`)

---

## Current State

**App is LIVE:** https://claudit-observability-1351565862180944.aws.databricksapps.com

The MVP is deployed and functional. Dashboard, sessions list, and session timeline views are all working. 34 tests passing (21 backend, 13 frontend). All API endpoints returning 200.

## Critical Next Steps (Priority Order)

### 1. Clean up debug logging in backend/main.py
**Why:** `print()` statements for frontend dist path discovery are still in production code.
**What:** Remove the `_candidates` loop, `print(f"[CLAUDIT]...")` lines, and the fallback `root()` endpoint. Replace with the simple original pattern now that we know the correct path:
```python
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
```
**File:** `backend/main.py`

### 2. Remove unused imports and dead code
**Why:** `backend/main.py` has `HTMLResponse`, `logging` imports only used by debug code.
**File:** `backend/main.py`

### 3. Add Recharts visualizations to dashboard
**Why:** Design doc specifies charts (TokenUsageChart, CostBreakdown, ErrorRateChart, LatencyDistribution) but MVP only has tables and stat cards.
**What:** Add time-series charts using Recharts (already in package.json dependencies). Needs new API hooks for `/api/v1/metrics/usage`, `/api/v1/metrics/costs`, `/api/v1/metrics/performance`.
**Files:** `frontend/src/views/dashboard/components/` (new chart components)

### 4. Add proper error handling and loading states
**Why:** Current error handling is minimal (just `<Text color="red.500">Failed to load</Text>`). No retry buttons, no empty states with suggestions.
**What:** Add toast notifications on API errors, retry buttons, and meaningful empty states per the design doc error handling table.

### 5. Merge feature branch to main
**Why:** All work is on `feature/claudit-mvp`. Main branch only has design docs.
**What:** `git checkout main && git merge feature/claudit-mvp`

## Known Issues

### OTEL telemetry limitations discovered this session
- **`tool_parameters` is always null** - cannot identify which specific Skill was invoked (e.g., `"superpowers:executing-plans"`) or which Task subagent type was used (e.g., `"Explore"`)
- **MCP tools are generic** - all logged as `tool_name: "mcp_tool"`, not the specific MCP tool name like `mcp__slack__slack_read_api_call`
- **No skill/subagent identity** in telemetry at all

### Deployment lessons learned
These are documented in commits but worth knowing:
1. **Workspace host** - `databricks.yml` cannot use `${DATABRICKS_HOST}` variable interpolation for `workspace.host`. Use `profile: DEFAULT` instead.
2. **Env vars** - DAB `resources/apps.yml` `config.env` block does NOT set runtime env vars. Must use `app.yaml` `env` section.
3. **Frontend dist** - `.gitignore` patterns are respected by `databricks bundle deploy` sync. Had to remove `dist/` and `frontend/dist/` from `.gitignore` and force-add built files.
4. **Root package.json** - Databricks Apps build system picks up root `package.json` before `frontend/package.json`. Removed root copy to avoid stale build scripts.
5. **tsc in Apps** - TypeScript 5.9.x in the Apps build environment requires `tsc -b` for projects with `references`. Simplified build to just `vite build`.

## Backlog Roadmap (updated this session)

| # | Module | Dependency | Notes |
|---|--------|-----------|-------|
| 1 | Materialized Tables | Scale > 10K events | ETL job for daily rollups |
| 2 | **MCP Tool Deep Dive** | **None** | Per-server breakdown, latency p50/p95/p99, success rates, call chains. All from existing OTEL data |
| 3 | **Prompt Execution Graph** | **None** | Swim-lane timeline per `prompt.id`. Shows full execution tree: prompt -> API calls -> tool calls -> subagents. Uses existing OTEL data |
| 4 | Inference Tables | Table enablement | LLM request/response payloads |
| 5 | System Tables | Access grants | Billing, serving metrics |
| 6 | User Correlation | Mapping table | user.id hash -> email |
| 7 | Alerts | Modules 1-5 | Threshold rules |

**Modules 2 and 3 have zero dependencies** - best candidates for next sprint.

## Project Structure

```
claudit/.worktrees/claudit-mvp/
├── databricks.yml              # DAB bundle (profile: DEFAULT, warehouse: 5067b513037fbf07)
├── app.yaml                    # Runtime config with env vars (CATALOG, SCHEMA_NAME, SQL_WAREHOUSE_ID)
├── requirements.txt            # Python deps for Databricks Apps
├── pyproject.toml              # Python project config
├── backend/
│   ├── main.py                 # FastAPI app + static file serving
│   ├── config.py               # Settings (pydantic-settings, reads env vars)
│   ├── models/                 # events.py, sessions.py, metrics.py
│   ├── services/               # query_service.py (9 query builders), sql_executor.py
│   └── routers/                # metrics.py (6 endpoints), sessions.py (3 endpoints)
├── frontend/
│   ├── dist/                   # Built production bundle (committed, served by FastAPI)
│   └── src/
│       ├── app/                # App.tsx, Layout.tsx, router/viewRegistry.ts
│       ├── views/              # dashboard/, sessions/ (pages + components)
│       ├── shared/hooks/       # useApi.ts (TanStack Query hooks)
│       └── types/              # api.ts (TypeScript interfaces)
├── resources/apps.yml          # DAB app resource definition
└── tests/backend/              # 21 pytest tests
```

## Key Commands

```bash
# Work in the worktree
cd .worktrees/claudit-mvp

# Run tests
python -m pytest tests/ -v                              # 21 backend tests
cd frontend && npx vitest run                            # 13 frontend tests (must run from frontend/)

# Build and deploy
cd frontend && npx vite build && cd ..                   # Rebuild frontend
databricks bundle validate -t dev                        # Validate bundle
databricks bundle deploy -t dev                          # Upload to workspace
databricks apps deploy claudit-observability \
  --source-code-path /Workspace/Users/jesus.rodriguez@databricks.com/.bundle/claudit-observability/dev/files \
  --profile DEFAULT                                      # Deploy app

# Check app
databricks apps logs claudit-observability --tail-lines 50 --profile DEFAULT
```

## Git State

```
Branch: feature/claudit-mvp (24 commits ahead of main)
Latest: 617c085 docs: add prompt execution graph to backlog (Module 3)
All tests passing. App deployed and serving.
```
