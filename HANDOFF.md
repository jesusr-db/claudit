# Claudit Project Handoff

**Date:** 2026-02-20
**Updated:** 2026-02-23 (aligned plans with actual OTEL telemetry data)
**Status:** Design complete, ready for implementation

---

## Project Overview

**Claudit** is an observability app for Claude Code clients. It queries OTEL logs and metrics tables directly to provide analytics dashboards and session-level visibility. Modular backlog extensions add MCP server logs, inference tables, and system table integration.

## What Was Completed

### 1. Design Phase (Approved)
- Brainstormed requirements with user
- Evaluated architectural approaches
- Selected: Direct query on OTEL tables (MVP), materialization when scale requires it
- Design document: `docs/plans/2026-02-20-claudit-observability-design.md`

### 2. Data Validation (2026-02-23)
- Verified actual Claude Code OTEL telemetry against planned schema
- Identified 6 major misalignments between plan and actual data
- Updated design and implementation plans to match real data

### 3. Implementation Plan (Ready)
- Simplified from 18 tasks to ~12 focused tasks across 4 MVP phases + backlog
- Removed ETL/materialization from MVP scope
- All SQL queries validated against actual table structure
- Plan document: `docs/plans/2026-02-20-claudit-implementation.md`

## Key Design Decisions

| Decision | Choice |
|----------|--------|
| Architecture | Direct query on OTEL tables (MVP), materialization in backlog |
| Source tables | `{catalog}.{schema}.otel_logs` + `otel_metrics` (NOT mlflow-prefixed) |
| Data freshness | Near real-time (OTEL export: 5-10s) |
| Session correlation | `attributes['session.id']` in logs (NOT spans) |
| User identity | `user.id` is SHA256 hash (no email without mapping) |
| Auth | Databricks native OAuth via Apps |
| Frontend | React 18 + Chakra UI + TanStack Query |
| Deployment | DAB bundle (app only for MVP, + ETL job in backlog) |
| Primary views | Analytics dashboard + Session timeline (both MVP) |

## Verified Data Model

### otel_logs events (5 types)
| event.name | Key fields |
|---|---|
| `user_prompt` | prompt, prompt_length, prompt.id |
| `api_request` | model, duration_ms, cost_usd, input/output/cache tokens |
| `api_error` | model, error, status_code, duration_ms |
| `tool_decision` | tool_name, decision, source |
| `tool_result` | tool_name, duration_ms, success, tool_result_size_bytes |

Common: `session.id`, `prompt.id`, `event.sequence`, `event.timestamp`, `user.id`

### otel_metrics (4 counters)
| Metric | Unit | Breakdown |
|---|---|---|
| `claude_code.token.usage` | tokens | type (input/output/cacheRead/cacheCreation), model |
| `claude_code.cost.usage` | USD | model |
| `claude_code.active_time.total` | s | - |
| `claude_code.session.count` | count | - |

### What does NOT exist
- **otel_spans**: Table exists but is always empty. Claude Code does not emit spans.
- **trace_id / span_id**: Always null in logs.
- **severity_text / severity_number**: Always null.
- **user email**: Only hashed `user.id` available.

## MVP Scope

- Analytics dashboard (summary, tools, errors, performance, costs)
- Session list with aggregated stats
- Session timeline with event-level detail
- MCP tool filtering (via `tool_name LIKE 'mcp__%'`)
- No ETL, no materialized tables, no cross-table joins

## Backlog Modules

| Module | Description | Trigger |
|--------|-------------|---------|
| 1. Materialized Tables | ETL job for pre-computed rollups | Scale > 10K events |
| 2. MCP Server Logs | Server-side MCP log correlation | MCP log ingestion pipeline |
| 3. Inference Tables | LLM request/response payloads | Inference table enablement |
| 4. System Tables | Billing and serving infrastructure metrics | System table access |
| 5. User Correlation | Map user.id hash to emails | User mapping table |

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
├── resources/              # DAB resource definitions
│   └── apps.yml
└── tests/
```

## To Start Implementation

```bash
# In this project directory
claude

# Then run:
/superpowers:executing-plans docs/plans/2026-02-20-claudit-implementation.md
```

## Prerequisites

1. **Databricks workspace** with Unity Catalog enabled
2. **SQL Warehouse ID**: `5067b513037fbf07` (Serverless Starter Warehouse)
3. **OTEL tables**: `jmr_demo.zerobus.otel_logs`, `jmr_demo.zerobus.otel_metrics` (verified with data)
4. **Databricks profile**: `DEFAULT` pointing to `fe-vm-vdm-classic-rikfy0.cloud.databricks.com`

## Git State

```
Branch: main
Commits:
  1. df3b941 - Add claudit observability app design document
  2. 8d04ff5 - docs: add claudit implementation plan
  3. cbfb24d - docs: add handoff document for next session
```
