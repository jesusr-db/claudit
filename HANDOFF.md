# Claudit Project Handoff

**Date:** 2026-02-20
**Status:** Design complete, ready for implementation

---

## Project Overview

**Claudit** is an end-to-end observability app for Claude Code clients. It tracks OTEL metrics/logs, MCP server logs, Databricks system tables, and inference table artifacts, presenting them in a unified session timeline view.

## What Was Completed

### 1. Design Phase (Approved)
- Brainstormed requirements with user
- Evaluated 3 architectural approaches
- Selected: Batch materialization + Direct query architecture
- Design document: `docs/plans/2026-02-20-claudit-observability-design.md`

### 2. Implementation Plan (Ready)
- 18 bite-sized TDD tasks across 5 phases
- Full code snippets for each task
- Plan document: `docs/plans/2026-02-20-claudit-implementation.md`

## Key Design Decisions

| Decision | Choice |
|----------|--------|
| Architecture | Batch ETL materializes unified tables, FastAPI queries them |
| Data correlation | User + Time hybrid (5-min window) |
| Data freshness | Batch (15-min ETL job) |
| Auth | Databricks native OAuth via Apps |
| Frontend | React 18 + Chakra UI + TanStack Query |
| Deployment | Full DAB bundle (app + ETL jobs) |
| Primary view | Session timeline with event filtering |

## Project Structure (Planned)

```
claudit/
├── databricks.yml          # DAB bundle config
├── app.yaml                # App config
├── pyproject.toml          # Python deps
├── package.json            # Frontend deps
├── backend/                # FastAPI backend
│   ├── main.py
│   ├── config.py
│   ├── models/
│   ├── services/
│   └── routers/
├── frontend/               # React frontend
│   └── src/
│       ├── app/
│       ├── views/
│       ├── shared/
│       └── types/
├── etl/                    # Spark ETL jobs
│   ├── obs_materialization.py
│   ├── config.py
│   ├── models.py
│   └── extractors/
├── resources/              # DAB resource definitions
│   ├── apps.yml
│   ├── jobs.yml
│   └── schemas.yml
└── tests/
```

## Data Sources

| Source | Table | Purpose |
|--------|-------|---------|
| OTEL Metrics | `{catalog}.{schema}.mlflow_experiment_trace_otel_metrics` | Usage metrics |
| OTEL Logs | `{catalog}.{schema}.mlflow_experiment_trace_otel_logs` | Application logs |
| MCP Logs | User's separate Unity Catalog table | MCP server interactions |
| System | `system.billing.usage`, `system.serving.*`, `system.query.history` | Costs & infra |
| Inference | `{endpoint}_payload_logs` | LLM request/response data |

## Materialized Tables (Created by ETL)

| Table | Purpose |
|-------|---------|
| `obs.session_events` | Unified event stream with normalized schema |
| `obs.sessions` | Session summaries with aggregated metrics |
| `obs.daily_metrics` | Daily rollups by user |

## To Start Implementation

### Option 1: Subagent-Driven (Interactive)
```bash
# In this project directory
claude

# Then run:
/superpowers:subagent-driven-development
# Point it to: docs/plans/2026-02-20-claudit-implementation.md
```

### Option 2: Executing Plans (Batch)
```bash
claude

# Then run:
/superpowers:executing-plans docs/plans/2026-02-20-claudit-implementation.md
```

### Option 3: Manual Task-by-Task
Open `docs/plans/2026-02-20-claudit-implementation.md` and follow each task sequentially.

## Prerequisites for Implementation

1. **Databricks workspace** with Unity Catalog enabled
2. **SQL Warehouse ID** for app queries
3. **OTEL tables** already ingesting Claude Code telemetry
4. **Environment variables:**
   - `DATABRICKS_HOST`
   - `SQL_WAREHOUSE_ID`
   - `CATALOG`, `SCHEMA`

## Git State

```
Branch: main
Commits:
  1. df3b941 - Add claudit observability app design document
  2. 8d04ff5 - docs: add claudit implementation plan
```

## Session Stats

- **Cost:** $6.76
- **Duration:** 39 min (wall time)
- **Output:** 3,651 lines of documentation

---

## Questions for Next Session

If picking this up, consider asking the user:

1. Do they have the OTEL tables set up and ingesting data?
2. What's their SQL Warehouse ID?
3. What catalog/schema should we use for materialized tables?
4. Any changes to the design since this session?
