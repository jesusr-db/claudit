# Module 2: MCP Tool Deep Dive - Design

**Date:** 2026-02-24
**Status:** Approved

## Overview

New top-level nav page at `/mcp-tools` providing per-MCP-server analytics with drill-down to individual tool stats and recent call history.

## Backend

### New Queries (QueryService)

1. **`build_mcp_server_summary_query()`** - Aggregates tool_result events by MCP server (extracted via `SPLIT(tool_name, '__')[1]`). Returns: server name, call count, success rate, avg/p50/p95/p99 latency, total result bytes.

2. **`build_mcp_tool_detail_query(server)`** - Per-tool stats for a specific MCP server. Returns: tool name, call count, success/failure counts, avg/p50/p95/p99 latency, avg result size.

3. **`build_mcp_recent_calls_query(server, limit)`** - Recent individual tool_result events for a server. Returns: timestamp, tool name, session_id, duration_ms, success, result size bytes.

### New Router (`/api/v1/mcp-tools`)

- `GET /servers` - Server-level summary
- `GET /servers/{server}` - Tool-level detail for one server
- `GET /servers/{server}/calls` - Recent individual calls (default limit 50)

## Frontend

### Pages

- **McpToolsPage** (`/mcp-tools`) - Server summary cards grid + server table
- **McpServerDetailPage** (`/mcp-tools/:server`) - Tool breakdown table with percentile latencies, recent calls list

### Hooks

- `useMcpServers()` - Fetches server summary
- `useMcpServerDetail(server)` - Fetches tool-level detail
- `useMcpRecentCalls(server)` - Fetches recent calls

### Types

- `McpServerSummary` - server, call_count, success_rate, avg/p50/p95/p99 latency
- `McpToolDetail` - tool_name, call_count, success/failure counts, latency percentiles
- `McpCall` - timestamp, tool_name, session_id, duration_ms, success, result_size_bytes

## Data Extraction

MCP server name from tool_name: `mcp__glean__search` -> `glean` via `SPLIT(attributes['tool_name'], '__')[1]`.

Only `tool_result` events with `tool_name LIKE 'mcp__%'` are included.
