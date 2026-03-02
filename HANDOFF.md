# Claudit Project Handoff

**Date:** 2026-03-02
**Status:** MVP deployed and running on Databricks Apps
**Branch:** `main` (feature branch merged)

---

## Current State

**App is LIVE:** https://claudit-observability-1351565862180944.aws.databricksapps.com

The MVP is deployed and functional. Dashboard, sessions list, session timeline, MCP servers, and KPI hub views are all working. Backend has routers for sessions, metrics, KPIs, and MCP servers. Frontend uses React + Mantine + Recharts.

---

## PRIORITY 1: Verify databricks-mcp Tools Load

The `databricks-mcp` MCP server config was updated (session 4) to use a **hardcoded OAuth token** in `~/.claude.json` — same pattern as the working `weather-server`. This should fix the connection issue that persisted across 4 sessions.

### First thing to do: verify tools loaded
```
ToolSearch: "databricks-mcp"
```
If tools appear → the fix worked. Proceed to use them (e.g., `mcp__databricks-mcp__execute_sql` with param `sql_query`).

### If tools still don't appear
The hardcoded token may have expired (1-hour TTL). Refresh it:
```bash
# Get fresh token and update ~/.claude.json
FRESH_TOKEN=$(databricks auth token --host "https://fe-vm-vdm-classic-rikfy0.cloud.databricks.com" 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
python3 -c "
import json
with open('$HOME/.claude.json', 'r') as f:
    d = json.load(f)
d['mcpServers']['databricks-mcp']['headers']['Authorization'] = 'Bearer ' + '$FRESH_TOKEN'
with open('$HOME/.claude.json', 'w') as f:
    json.dump(d, f, indent=2)
print('Token refreshed')
"
```
Then restart Claude Code.

### Long-term fix needed
The `CLAUDE_ENV_FILE` env var is never set in the session, so the `SessionStart` hook that writes `DATABRICKS_MCP_TOKEN` to it is a no-op. The `${DATABRICKS_MCP_TOKEN}` env var interpolation in headers never resolves. The hardcoded token is a workaround; the real fix requires understanding why `CLAUDE_ENV_FILE` isn't populated.

---

## PRIORITY 2: Fix Frontend Tests

**Backend tests: 42/42 passing.**

**Frontend tests: FAILING** — test mocks are out of date after recent UI changes.

### What's broken
The `vi.mock("@/shared/hooks/useApi")` blocks in test files don't include hooks added in recent commits:

| Test file | Missing mock(s) |
|---|---|
| `frontend/src/views/dashboard/__tests__/DashboardPage.test.tsx` | `useKpiBadges` |
| `frontend/src/views/sessions/__tests__/SessionsPage.test.tsx` | `useSessionTimeline`, `useTurnaroundSummary`, `useTurnaroundDetail` |

### How to fix
Add the missing hooks to each test's `vi.mock` block. Each mock should return `{ data: <minimal valid data>, isLoading: false, error: null }`. Check the actual hook signatures in `frontend/src/shared/hooks/useApi.ts` and what the components destructure.

### Run tests
```bash
python -m pytest tests/ -v                    # Backend (should be 42/42)
cd frontend && npx vitest run                  # Frontend (currently failing)
```

---

## Databricks MCP Server Config

**`~/.claude.json`** (MCP server definition — user scope):
```json
"databricks-mcp": {
  "type": "http",
  "url": "https://databricks-mcp-server-dev-1351565862180944.aws.databricksapps.com/mcp",
  "headers": {
    "Authorization": "Bearer <hardcoded-oauth-jwt>"
  }
}
```
**Note:** As of session 4, the token is hardcoded (not env var interpolation). It expires after 1 hour.

**`~/.claude/settings.json`** (hooks):
- `SessionStart` hook: runs `~/.claude/hooks/refresh-databricks-oauth.sh` → tries to write `DATABRICKS_MCP_TOKEN` to `CLAUDE_ENV_FILE` (currently a no-op because `CLAUDE_ENV_FILE` is empty)
- `PreToolUse` hook (matcher: `mcp__databricks-mcp`): runs same refresh script before each databricks-mcp tool call

### Why env var interpolation failed (root cause)
- `CLAUDE_ENV_FILE` is **not set** in the session environment
- The hook script checks `if [ -n "$CLAUDE_ENV_FILE" ]` before writing — so it silently skips
- The `${DATABRICKS_MCP_TOKEN}` in headers resolves to empty → MCP client sends `Authorization: Bearer ` → 401
- **PAT (`$DATABRICKS_TOKEN`, 36 chars) does NOT work** — the MCP server requires OAuth JWT, returns 401 on PAT

### Tool parameter gotcha
- `execute_sql` requires `sql_query` (NOT `sql`) as the parameter name
- Optional params: `warehouse_id`, `catalog`, `schema`, `timeout`

---

## Critical Architecture Notes

**Claude Code MCP config files:**
- `~/.claude.json` — where Claude Code reads MCP server definitions (added via `claude mcp add -s user`)
- `~/.claude/settings.json` — hooks, permissions, env vars, but `mcpServers` block here is **NOT read** by the MCP client
- The `mcpServers` block in `settings.json` is effectively dead config

**Data location:**
- Catalog: `jmr_demo`
- Schema: `zerobus`
- Tables: `otel_logs` (13,985 rows), `otel_metrics`
- Warehouse: `5067b513037fbf07` (Serverless Starter Warehouse)

---

## Known Issues

### OTEL telemetry limitations
- **`tool_parameters` is always null** — cannot identify which specific Skill was invoked or which Task subagent type was used
- **MCP tools are generic** — all logged as `tool_name: "mcp_tool"`, not the specific MCP tool name
- **No skill/subagent identity** in telemetry at all

### Deployment lessons learned
1. **Workspace host** — `databricks.yml` cannot use `${DATABRICKS_HOST}` variable interpolation for `workspace.host`. Use `profile: DEFAULT` instead.
2. **Env vars** — DAB `resources/apps.yml` `config.env` block does NOT set runtime env vars. Must use `app.yaml` `env` section.
3. **Frontend dist** — `.gitignore` patterns are respected by `databricks bundle deploy` sync. Had to remove `dist/` and `frontend/dist/` from `.gitignore` and force-add built files.
4. **Root package.json** — Databricks Apps build system picks up root `package.json` before `frontend/package.json`. Removed root copy.
5. **tsc in Apps** — TypeScript 5.9.x in the Apps build environment requires `tsc -b` for projects with `references`. Simplified build to just `vite build`.

---

## Completed Modules

| # | Module | Status | What shipped |
|---|--------|--------|-------------|
| 2 | **MCP Tool Deep Dive** | ✅ Done | 9 backend endpoints, 3 frontend pages (McpToolsPage, McpServerDetailPage, McpServersPage with Ops/Security/Logs tabs), 9 hooks, 11 types. Exceeded original design spec. |
| 3 | **Prompt Execution Graph** | ✅ Done | Swim-lane component (`PromptExecutionGraph.tsx`) with per-prompt drill-down via `/sessions/:id/prompts/:promptId` endpoint. Integrated into SessionDetailPage. |
| 5 | **System Tables** (partial) | ✅ Done | Platform page (`/platform`) with 3 tabs: Billing (DBU by product), Query History (by client), AI Gateway (model performance). Uses Databricks system tables. |
| — | **KPI Hub** | ✅ Done | 13 endpoints across 3 phases: Cost Intelligence (overview, trend, sessions, models, waste), Agent Effectiveness (retries, orphans, recovery, complexity), Flow Correlation (MCP→UC→API flow, audit). |
| — | **Turnaround Analysis** | ✅ Done | Turnaround summary/detail endpoints + TurnaroundPage. Per-prompt agent work time, API/tool call counts. |

## Backlog Roadmap

| # | Module | Dependency | Notes |
|---|--------|-----------|-------|
| 1 | Materialized Tables | Scale > 10K events | ETL job for daily rollups |
| 4 | Inference Tables | Table enablement | LLM request/response payloads |
| 5b | System Tables (remaining) | Access grants | Serving metrics, deeper billing drill-downs |
| 6 | User Correlation | Mapping table | user.id hash → email |
| 7 | Alerts | Modules 1-6 | Threshold rules |
| 8 | Optimization Chatbot | Model Efficiency tab | Contextual recommendations for model right-sizing — see details below |

**Module 1 (Materialized Tables) is the next scalability unlock.** Modules 4 and 5b depend on table/access enablement.

### Module 8: Optimization Chatbot (Model Right-Sizing Advisor)

The Model Efficiency tab shows *what* to optimize but not *how*. A chatbot/advisor feature would provide contextual, actionable guidance. Scope:

**Preferred optimization methods to recommend:**
- **Claude Code `--model` flag** — route simple tasks to Haiku/Sonnet via CLI args
- **CLAUDE.md model directives** — per-project model preferences (e.g., "use Sonnet for this repo")
- **`/model` mid-session switching** — switch to cheaper model for simple follow-ups within a session
- **MCP server model config** — configure which model handles tool-heavy vs reasoning-heavy calls
- **API gateway routing rules** — complexity-based automatic routing at the proxy level
- **Prompt optimization** — reduce input tokens via better context management, system prompt tuning

**UX options (pick one):**
1. **Inline recommendations panel** in the Model Efficiency tab — static advice based on current data patterns
2. **Chat sidebar** — conversational advisor that can answer "how do I downsize this workflow?" with context from the drill-down data
3. **Action cards** — each rightsizing opportunity gets a "How to fix" expandable section with specific commands/config changes

**Dependencies:** Model Efficiency tab (done), drill-down details (done). No backend infra needed for option 1 or 3.

---

## Project Structure

```
claudit/
├── databricks.yml              # DAB bundle (profile: DEFAULT, warehouse: 5067b513037fbf07)
├── app.yaml                    # Runtime config with env vars (CATALOG, SCHEMA_NAME, SQL_WAREHOUSE_ID)
├── requirements.txt            # Python deps for Databricks Apps
├── pyproject.toml              # Python project config
├── backend/
│   ├── main.py                 # FastAPI app + static file serving
│   ├── config.py               # Settings (pydantic-settings, reads env vars)
│   ├── models/                 # events.py, sessions.py, metrics.py
│   ├── services/               # query_service.py, kpi_query_service.py, mcp_query_service.py, sql_executor.py
│   └── routers/                # metrics.py, sessions.py, kpis.py, mcp_servers.py
├── frontend/
│   ├── dist/                   # Built production bundle (committed, served by FastAPI)
│   └── src/
│       ├── app/                # App.tsx, Layout.tsx, router/viewRegistry.ts
│       ├── views/              # dashboard/, sessions/, kpis/, mcp-servers/
│       ├── shared/hooks/       # useApi.ts (TanStack Query hooks)
│       └── types/              # api.ts (TypeScript interfaces)
├── resources/apps.yml          # DAB app resource definition
└── tests/backend/              # pytest tests
```

## Key Commands

```bash
# Run tests
python -m pytest tests/ -v                              # Backend tests (42/42 passing)
cd frontend && npx vitest run                            # Frontend tests (FAILING — mock updates needed)

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

---

## Session Log

### 2026-03-02 (session 4) — MCP Auth Root Cause Found
**Problem:** databricks-mcp tools still not appearing (4th session in a row).
**Root cause confirmed:** `CLAUDE_ENV_FILE` is not set in the session environment. The SessionStart hook checks for it before writing the token, so it silently does nothing. The `${DATABRICKS_MCP_TOKEN}` env var in the MCP config header resolves to empty → 401.
**Investigation:**
- Compared with working `weather-server` MCP — it uses a **hardcoded token** in `~/.claude.json`, no env var interpolation
- Tested PAT (`$DATABRICKS_TOKEN`, 36 chars) against databricks-mcp → **401** (server requires OAuth JWT, not PAT)
- Backend tests: 42/42 passing
- Frontend tests: failing due to stale mocks (missing `useKpiBadges`, `useTurnaroundSummary`, `useTurnaroundDetail`)
**Fix applied:** Updated `~/.claude.json` to hardcode a fresh OAuth JWT in the `databricks-mcp` headers (same pattern as working weather-server). Requires Claude Code restart to take effect.

### 2026-03-02 (session 3) — MCP Connection Debugging
**Problem:** databricks-mcp tools still not appearing despite config being correct and token being valid.
**Investigation:** Token present (865 chars), not expired, server responds HTTP 200 with 48 tools. Successfully queried `jmr_demo.zerobus.otel_logs` (13,985 rows) and `list_warehouses` via direct curl.
**Finding:** `CLAUDE_ENV_FILE` not set in bash tool context — suggests possible race condition where MCP client connects before hook writes the token.
**Action:** Re-added server via `claude mcp add -s user` to ensure clean config. Next session should connect.

### 2026-03-02 (session 2) — Databricks MCP Config Fix
**Problem:** `databricks-mcp` tools never appeared in Claude Code despite server being healthy.
**Root cause:** MCP server was defined in `~/.claude/settings.json` `mcpServers` block, but Claude Code reads MCP configs from `~/.claude.json`.
**Fix:** Added server to `~/.claude.json` with `${DATABRICKS_MCP_TOKEN}` env var interpolation.

### 2026-03-02 (session 1) — Databricks MCP Auth Fix
**Problem:** OAuth token (1-hour TTL) expired mid-session causing 401 errors.
**Fix:** Added `PreToolUse` hook in `~/.claude/settings.json` with matcher `mcp__databricks-mcp` to refresh token before each call.
