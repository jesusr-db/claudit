# AI Gateway Dashboards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Platform page with a 5-tab AI Gateway analytics dashboard (Overview, Performance, Usage, Coding Agents, Token Consumption) sourced from `system.ai_gateway.usage`.

**Architecture:** Chakra `<Tabs isLazy>` shell with per-tab components, each fetching its own data via `useQuery` hooks. Backend adds 6 new endpoints to the existing platform router, with SQL query builders on `QueryService`. Dark-themed dashboard container wrapping all tabs, with a shared endpoint filter dropdown.

**Tech Stack:** FastAPI, Databricks SQL, React, TypeScript, Chakra UI, Recharts, TanStack Query

**Spec:** `docs/superpowers/specs/2026-04-14-ai-gateway-dashboards-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/services/query_service.py` | Modify | Add 6 query builder methods + agent classification SQL |
| `backend/routers/platform.py` | Modify | Add 6 new API endpoints, remove old 3 |
| `frontend/src/types/api.ts` | Modify | Add response types for all new endpoints |
| `frontend/src/shared/hooks/useApi.ts` | Modify | Add 6 new `useQuery` hooks + remove old 3 |
| `frontend/src/shared/utils/gatewayColors.ts` | Create | Shared chart color palette + number formatting |
| `frontend/src/views/platform/PlatformPage.tsx` | Rewrite | Tabs shell + endpoint filter + dark container |
| `frontend/src/views/platform/components/OverviewTab.tsx` | Create | Overview tab with KPIs, charts, tables |
| `frontend/src/views/platform/components/PerformanceTab.tsx` | Create | Performance tab with latency, errors, status codes |
| `frontend/src/views/platform/components/UsageTab.tsx` | Create | Usage tab with token breakdowns, cache rates |
| `frontend/src/views/platform/components/CodingAgentsTab.tsx` | Create | Coding agents tab with agent detection, user analytics |
| `frontend/src/views/platform/components/TokenConsumptionTab.tsx` | Create | Token consumption tab with volume analysis |

---

### Task 1: Backend — Query Builders for Overview and Endpoints

**Files:**
- Modify: `backend/services/query_service.py:22-28` (add to SQL_METHODS set)
- Modify: `backend/services/query_service.py` (add methods after line 544)

- [ ] **Step 1: Add new method names to SQL_METHODS set**

In `backend/services/query_service.py`, update the `SQL_METHODS` set at line 22-28 to include the new methods:

```python
SQL_METHODS = {
    'build_billing_daily_query', 'build_billing_summary_query',
    'build_query_history_stats_query', 'build_query_history_daily_query',
    'build_ai_gateway_model_stats_query', 'build_ai_gateway_daily_query',
    'build_ai_gateway_errors_query',
    'build_ai_gateway_endpoints_query',
    'build_ai_gateway_overview_kpis_query',
    'build_ai_gateway_overview_daily_query',
    'build_ai_gateway_overview_top_endpoints_query',
    'build_ai_gateway_overview_top_models_query',
    'build_ai_gateway_overview_top_users_query',
    'build_ai_gateway_overview_latency_by_endpoint_query',
    'build_ai_gateway_performance_kpis_query',
    'build_ai_gateway_performance_latency_by_endpoint_query',
    'build_ai_gateway_performance_status_codes_query',
    'build_ai_gateway_performance_tpm_query',
    'build_ai_gateway_performance_ttfb_by_endpoint_query',
    'build_ai_gateway_performance_ttft_loss_query',
    'build_ai_gateway_performance_errors_by_endpoint_query',
    'build_ai_gateway_usage_kpis_query',
    'build_ai_gateway_usage_tokens_by_endpoint_query',
    'build_ai_gateway_usage_tokens_by_model_query',
    'build_ai_gateway_usage_tokens_by_user_query',
    'build_ai_gateway_usage_input_output_query',
    'build_ai_gateway_usage_cache_hit_query',
    'build_ai_gateway_coding_agents_summary_query',
    'build_ai_gateway_coding_agents_daily_query',
    'build_ai_gateway_coding_agents_by_endpoint_query',
    'build_ai_gateway_coding_agents_by_model_query',
    'build_ai_gateway_coding_agents_user_analytics_query',
    'build_ai_gateway_token_consumption_kpis_query',
    'build_ai_gateway_token_consumption_daily_query',
    'build_ai_gateway_token_consumption_by_dest_type_query',
    'build_ai_gateway_token_consumption_weekly_query',
    'build_ai_gateway_token_consumption_top_endpoints_query',
    'build_ai_gateway_token_consumption_top_models_query',
    'build_ai_gateway_token_consumption_top_users_query',
}
```

- [ ] **Step 2: Add the agent classification SQL helper**

Add this helper method right after the existing `_ai_gw_time_filter` method (after line 443):

```python
@staticmethod
def _ai_gw_agent_classification() -> str:
    """CASE expression to classify user_agent into coding agent groups."""
    return """
        CASE
            WHEN user_agent LIKE 'claude-cli%' AND user_agent LIKE '%claude-vscode%' THEN 'Claude Code (VS Code)'
            WHEN user_agent LIKE 'claude-cli%' AND user_agent LIKE '%sdk-py%' THEN 'Claude Code (SDK)'
            WHEN user_agent LIKE 'claude-cli%' THEN 'Claude Code (CLI)'
            WHEN user_agent LIKE 'OpenAI/Python%' OR user_agent LIKE 'AsyncOpenAI/Python%' THEN 'OpenAI SDK'
            WHEN user_agent LIKE 'Anthropic/Python%' OR user_agent LIKE 'AsyncAnthropic/Python%' THEN 'Anthropic SDK'
            WHEN user_agent LIKE 'python-requests%' THEN 'Python Requests'
            WHEN user_agent LIKE 'Mozilla%' THEN 'Browser'
            ELSE COALESCE(SUBSTRING(user_agent, 1, 30), 'Unknown')
        END
    """.strip()
```

- [ ] **Step 3: Add endpoint filter query builder and optional endpoint WHERE clause helper**

Add after the agent classification helper:

```python
def _ai_gw_endpoint_filter(self, endpoint: str | None) -> str:
    """Returns an AND clause for endpoint filtering, or empty string."""
    if endpoint:
        safe = endpoint.replace("'", "''")
        return f"AND endpoint_name = '{safe}'"
    return ""

def build_ai_gateway_endpoints_query(self, days: float = 7) -> str:
    """Distinct endpoint names for the filter dropdown."""
    time_filter = self._ai_gw_time_filter(days)
    return f"""
        SELECT DISTINCT endpoint_name
        FROM system.ai_gateway.usage
        WHERE {time_filter}
        ORDER BY endpoint_name
    """.strip()
```

- [ ] **Step 4: Add Overview query builders**

```python
def build_ai_gateway_overview_kpis_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT
            COUNT(*) as total_requests,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COUNT(DISTINCT requester) as total_unique_users
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
    """.strip()

def build_ai_gateway_overview_daily_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT
            DATE(event_time) as date,
            COUNT(*) as requests,
            COALESCE(SUM(total_tokens), 0) as tokens,
            COUNT(DISTINCT requester) as unique_users
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
        GROUP BY DATE(event_time)
        ORDER BY date ASC
    """.strip()

def build_ai_gateway_overview_top_endpoints_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT endpoint_name, COALESCE(SUM(total_tokens), 0) as total_tokens, COUNT(*) as requests
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
        GROUP BY endpoint_name
        ORDER BY total_tokens DESC
        LIMIT 10
    """.strip()

def build_ai_gateway_overview_top_models_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT destination_model as model, COALESCE(SUM(total_tokens), 0) as total_tokens, COUNT(*) as requests
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
        GROUP BY destination_model
        ORDER BY total_tokens DESC
        LIMIT 10
    """.strip()

def build_ai_gateway_overview_top_users_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT requester, COUNT(*) as requests, COALESCE(SUM(total_tokens), 0) as total_tokens
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
        GROUP BY requester
        ORDER BY requests DESC
        LIMIT 10
    """.strip()

def build_ai_gateway_overview_latency_by_endpoint_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        WITH top_eps AS (
            SELECT endpoint_name
            FROM system.ai_gateway.usage
            WHERE {time_filter} {ep_filter}
            GROUP BY endpoint_name
            ORDER BY COUNT(*) DESC
            LIMIT 5
        )
        SELECT
            DATE(u.event_time) as date,
            u.endpoint_name,
            ROUND(AVG(u.latency_ms), 0) as avg_latency_ms,
            ROUND(AVG(u.time_to_first_byte_ms), 0) as avg_ttfb_ms
        FROM system.ai_gateway.usage u
        JOIN top_eps t ON u.endpoint_name = t.endpoint_name
        WHERE {time_filter} {ep_filter}
        GROUP BY DATE(u.event_time), u.endpoint_name
        ORDER BY date ASC, u.endpoint_name
    """.strip()
```

- [ ] **Step 5: Commit**

```bash
git add backend/services/query_service.py
git commit -m "feat(backend): add AI Gateway overview + endpoints query builders"
```

---

### Task 2: Backend — Query Builders for Performance Tab

**Files:**
- Modify: `backend/services/query_service.py` (append methods)

- [ ] **Step 1: Add Performance query builders**

Append to `QueryService` class:

```python
def build_ai_gateway_performance_kpis_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT
            ROUND(PERCENTILE(CAST(latency_ms AS DOUBLE), 0.5), 0) as median_latency_ms,
            ROUND(PERCENTILE(CAST(time_to_first_byte_ms AS DOUBLE), 0.5), 0) as median_ttfb_ms,
            SUM(CASE WHEN status_code != 200 THEN 1 ELSE 0 END) as error_count
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
    """.strip()

def build_ai_gateway_performance_latency_by_endpoint_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        WITH top_eps AS (
            SELECT endpoint_name FROM system.ai_gateway.usage
            WHERE {time_filter} {ep_filter}
            GROUP BY endpoint_name ORDER BY COUNT(*) DESC LIMIT 5
        )
        SELECT DATE(u.event_time) as date, u.endpoint_name,
            ROUND(PERCENTILE(CAST(u.latency_ms AS DOUBLE), 0.5), 0) as median_latency_ms
        FROM system.ai_gateway.usage u JOIN top_eps t ON u.endpoint_name = t.endpoint_name
        WHERE {time_filter} {ep_filter}
        GROUP BY DATE(u.event_time), u.endpoint_name
        ORDER BY date ASC
    """.strip()

def build_ai_gateway_performance_status_codes_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT status_code, COUNT(*) as count
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
        GROUP BY status_code
        ORDER BY count DESC
    """.strip()

def build_ai_gateway_performance_tpm_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        WITH top_eps AS (
            SELECT endpoint_name FROM system.ai_gateway.usage
            WHERE {time_filter} {ep_filter}
            GROUP BY endpoint_name ORDER BY COUNT(*) DESC LIMIT 5
        )
        SELECT DATE(u.event_time) as date, u.endpoint_name,
            ROUND(COALESCE(SUM(u.total_tokens), 0) / GREATEST(COUNT(DISTINCT HOUR(u.event_time)), 1) / 60.0, 0) as tpm
        FROM system.ai_gateway.usage u JOIN top_eps t ON u.endpoint_name = t.endpoint_name
        WHERE {time_filter} {ep_filter}
        GROUP BY DATE(u.event_time), u.endpoint_name
        ORDER BY date ASC
    """.strip()

def build_ai_gateway_performance_ttfb_by_endpoint_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        WITH top_eps AS (
            SELECT endpoint_name FROM system.ai_gateway.usage
            WHERE {time_filter} {ep_filter}
            GROUP BY endpoint_name ORDER BY COUNT(*) DESC LIMIT 5
        )
        SELECT DATE(u.event_time) as date, u.endpoint_name,
            ROUND(PERCENTILE(CAST(u.time_to_first_byte_ms AS DOUBLE), 0.5), 0) as median_ttfb_ms
        FROM system.ai_gateway.usage u JOIN top_eps t ON u.endpoint_name = t.endpoint_name
        WHERE {time_filter} {ep_filter}
        GROUP BY DATE(u.event_time), u.endpoint_name
        ORDER BY date ASC
    """.strip()

def build_ai_gateway_performance_ttft_loss_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        WITH top_eps AS (
            SELECT endpoint_name FROM system.ai_gateway.usage
            WHERE {time_filter} {ep_filter}
            GROUP BY endpoint_name ORDER BY COUNT(*) DESC LIMIT 5
        )
        SELECT u.endpoint_name,
            ROUND(AVG(u.time_to_first_byte_ms), 0) as avg_ttfb_ms,
            ROUND(AVG(u.latency_ms - u.time_to_first_byte_ms), 0) as avg_generation_ms
        FROM system.ai_gateway.usage u JOIN top_eps t ON u.endpoint_name = t.endpoint_name
        WHERE {time_filter} {ep_filter}
        GROUP BY u.endpoint_name
        ORDER BY avg_ttfb_ms + avg_generation_ms DESC
    """.strip()

def build_ai_gateway_performance_errors_by_endpoint_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT endpoint_name, COUNT(*) as error_count
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter} AND status_code != 200
        GROUP BY endpoint_name
        ORDER BY error_count DESC
        LIMIT 10
    """.strip()
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/query_service.py
git commit -m "feat(backend): add AI Gateway performance query builders"
```

---

### Task 3: Backend — Query Builders for Usage, Coding Agents, Token Consumption

**Files:**
- Modify: `backend/services/query_service.py` (append methods)

- [ ] **Step 1: Add Usage query builders**

```python
def build_ai_gateway_usage_kpis_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT
            COUNT(DISTINCT endpoint_name) as total_endpoints,
            COUNT(DISTINCT requester) as active_users
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
    """.strip()

def build_ai_gateway_usage_tokens_by_endpoint_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        WITH top_eps AS (
            SELECT endpoint_name FROM system.ai_gateway.usage
            WHERE {time_filter} {ep_filter}
            GROUP BY endpoint_name ORDER BY SUM(total_tokens) DESC LIMIT 7
        )
        SELECT DATE(u.event_time) as date, u.endpoint_name,
            COALESCE(SUM(u.total_tokens), 0) as tokens
        FROM system.ai_gateway.usage u JOIN top_eps t ON u.endpoint_name = t.endpoint_name
        WHERE {time_filter} {ep_filter}
        GROUP BY DATE(u.event_time), u.endpoint_name
        ORDER BY date ASC
    """.strip()

def build_ai_gateway_usage_tokens_by_model_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        WITH top_models AS (
            SELECT destination_model FROM system.ai_gateway.usage
            WHERE {time_filter} {ep_filter}
            GROUP BY destination_model ORDER BY SUM(total_tokens) DESC LIMIT 7
        )
        SELECT DATE(u.event_time) as date, u.destination_model as model,
            COALESCE(SUM(u.total_tokens), 0) as tokens
        FROM system.ai_gateway.usage u JOIN top_models t ON u.destination_model = t.destination_model
        WHERE {time_filter} {ep_filter}
        GROUP BY DATE(u.event_time), u.destination_model
        ORDER BY date ASC
    """.strip()

def build_ai_gateway_usage_tokens_by_user_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        WITH top_users AS (
            SELECT requester FROM system.ai_gateway.usage
            WHERE {time_filter} {ep_filter}
            GROUP BY requester ORDER BY SUM(total_tokens) DESC LIMIT 5
        )
        SELECT DATE(u.event_time) as date, u.requester,
            COALESCE(SUM(u.total_tokens), 0) as tokens
        FROM system.ai_gateway.usage u JOIN top_users t ON u.requester = t.requester
        WHERE {time_filter} {ep_filter}
        GROUP BY DATE(u.event_time), u.requester
        ORDER BY date ASC
    """.strip()

def build_ai_gateway_usage_input_output_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT DATE(event_time) as date,
            COALESCE(SUM(input_tokens), 0) as input_tokens,
            COALESCE(SUM(output_tokens), 0) as output_tokens
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
        GROUP BY DATE(event_time)
        ORDER BY date ASC
    """.strip()

def build_ai_gateway_usage_cache_hit_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT endpoint_name,
            COALESCE(SUM(token_details.cache_read_input_tokens), 0) as cache_read_tokens,
            COALESCE(SUM(input_tokens), 0) as total_input_tokens,
            CASE WHEN SUM(input_tokens) > 0
                THEN ROUND(SUM(token_details.cache_read_input_tokens) * 100.0 / SUM(input_tokens), 1)
                ELSE 0 END as cache_hit_pct
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
        GROUP BY endpoint_name
        HAVING SUM(input_tokens) > 0
        ORDER BY cache_hit_pct DESC
        LIMIT 10
    """.strip()
```

- [ ] **Step 2: Add Coding Agents query builders**

```python
def build_ai_gateway_coding_agents_summary_query(self, days: float = 7, endpoint: str | None = None, agent: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    agent_cls = self._ai_gw_agent_classification()
    agent_filter = ""
    if agent:
        safe_agent = agent.replace("'", "''")
        agent_filter = f"AND {agent_cls} = '{safe_agent}'"
    return f"""
        SELECT
            {agent_cls} as coding_agent,
            COUNT(*) as requests,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COUNT(DISTINCT requester) as unique_users,
            ROUND(AVG(latency_ms), 0) as avg_latency_ms
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter} {agent_filter}
        GROUP BY {agent_cls}
        ORDER BY requests DESC
    """.strip()

def build_ai_gateway_coding_agents_daily_query(self, days: float = 7, endpoint: str | None = None, agent: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    agent_cls = self._ai_gw_agent_classification()
    agent_filter = ""
    if agent:
        safe_agent = agent.replace("'", "''")
        agent_filter = f"AND {agent_cls} = '{safe_agent}'"
    return f"""
        WITH top_agents AS (
            SELECT {agent_cls} as coding_agent
            FROM system.ai_gateway.usage
            WHERE {time_filter} {ep_filter} {agent_filter}
            GROUP BY {agent_cls} ORDER BY COUNT(*) DESC LIMIT 7
        )
        SELECT DATE(u.event_time) as date,
            {agent_cls} as coding_agent,
            COUNT(*) as requests,
            COALESCE(SUM(u.total_tokens), 0) as tokens,
            ROUND(AVG(u.latency_ms), 0) as avg_latency_ms
        FROM system.ai_gateway.usage u
        WHERE {time_filter} {ep_filter} {agent_filter}
          AND {agent_cls} IN (SELECT coding_agent FROM top_agents)
        GROUP BY DATE(u.event_time), {agent_cls}
        ORDER BY date ASC
    """.strip()

def build_ai_gateway_coding_agents_by_endpoint_query(self, days: float = 7, endpoint: str | None = None, agent: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    agent_cls = self._ai_gw_agent_classification()
    agent_filter = ""
    if agent:
        safe_agent = agent.replace("'", "''")
        agent_filter = f"AND {agent_cls} = '{safe_agent}'"
    return f"""
        SELECT endpoint_name, COUNT(*) as requests
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter} {agent_filter}
        GROUP BY endpoint_name
        ORDER BY requests DESC
        LIMIT 10
    """.strip()

def build_ai_gateway_coding_agents_by_model_query(self, days: float = 7, endpoint: str | None = None, agent: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    agent_cls = self._ai_gw_agent_classification()
    agent_filter = ""
    if agent:
        safe_agent = agent.replace("'", "''")
        agent_filter = f"AND {agent_cls} = '{safe_agent}'"
    return f"""
        SELECT {agent_cls} as coding_agent, destination_model as model,
            COALESCE(SUM(total_tokens), 0) as tokens
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter} {agent_filter}
        GROUP BY {agent_cls}, destination_model
        ORDER BY tokens DESC
    """.strip()

def build_ai_gateway_coding_agents_user_analytics_query(self, days: float = 7, endpoint: str | None = None, agent: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    agent_cls = self._ai_gw_agent_classification()
    agent_filter = ""
    if agent:
        safe_agent = agent.replace("'", "''")
        agent_filter = f"AND {agent_cls} = '{safe_agent}'"
    return f"""
        SELECT requester, {agent_cls} as coding_agent,
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COUNT(*) as requests,
            ROUND(AVG(latency_ms), 0) as avg_latency_ms
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter} {agent_filter}
        GROUP BY requester, {agent_cls}
        ORDER BY total_tokens DESC
        LIMIT 25
    """.strip()
```

- [ ] **Step 3: Add Token Consumption query builders**

```python
def build_ai_gateway_token_consumption_kpis_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT
            COALESCE(SUM(total_tokens), 0) as total_tokens,
            COUNT(*) as total_requests,
            ROUND(COALESCE(SUM(total_tokens), 0) * 1.0 / GREATEST(COUNT(*), 1), 0) as avg_tokens_per_request
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
    """.strip()

def build_ai_gateway_token_consumption_daily_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT DATE(event_time) as date, COALESCE(SUM(total_tokens), 0) as tokens
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
        GROUP BY DATE(event_time)
        ORDER BY date ASC
    """.strip()

def build_ai_gateway_token_consumption_by_dest_type_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT destination_type, COALESCE(SUM(total_tokens), 0) as tokens
        FROM system.ai_gateway.usage
        WHERE {time_filter} {ep_filter}
        GROUP BY destination_type
        ORDER BY tokens DESC
    """.strip()

def build_ai_gateway_token_consumption_weekly_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        WITH top_eps AS (
            SELECT endpoint_name FROM system.ai_gateway.usage
            WHERE {time_filter} {ep_filter}
            GROUP BY endpoint_name ORDER BY SUM(total_tokens) DESC LIMIT 7
        )
        SELECT DATE_TRUNC('WEEK', u.event_time) as week, u.endpoint_name,
            COALESCE(SUM(u.total_tokens), 0) as tokens
        FROM system.ai_gateway.usage u JOIN top_eps t ON u.endpoint_name = t.endpoint_name
        WHERE {time_filter} {ep_filter}
        GROUP BY DATE_TRUNC('WEEK', u.event_time), u.endpoint_name
        ORDER BY week ASC
    """.strip()

def build_ai_gateway_token_consumption_top_endpoints_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT endpoint_name, COALESCE(SUM(total_tokens), 0) as tokens
        FROM system.ai_gateway.usage WHERE {time_filter} {ep_filter}
        GROUP BY endpoint_name ORDER BY tokens DESC LIMIT 10
    """.strip()

def build_ai_gateway_token_consumption_top_models_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT destination_model as model, COALESCE(SUM(total_tokens), 0) as tokens
        FROM system.ai_gateway.usage WHERE {time_filter} {ep_filter}
        GROUP BY destination_model ORDER BY tokens DESC LIMIT 10
    """.strip()

def build_ai_gateway_token_consumption_top_users_query(self, days: float = 7, endpoint: str | None = None) -> str:
    time_filter = self._ai_gw_time_filter(days)
    ep_filter = self._ai_gw_endpoint_filter(endpoint)
    return f"""
        SELECT requester, COALESCE(SUM(total_tokens), 0) as tokens
        FROM system.ai_gateway.usage WHERE {time_filter} {ep_filter}
        GROUP BY requester ORDER BY tokens DESC LIMIT 10
    """.strip()
```

- [ ] **Step 4: Commit**

```bash
git add backend/services/query_service.py
git commit -m "feat(backend): add usage, coding agents, token consumption query builders"
```

---

### Task 4: Backend — API Endpoints

**Files:**
- Modify: `backend/routers/platform.py`

- [ ] **Step 1: Rewrite platform.py with new endpoints**

Replace the entire content of `backend/routers/platform.py`:

```python
from typing import Optional
from fastapi import APIRouter, Query
from backend.services.query_service import QueryService
from backend.executors import get_sql_executor

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])

query_service = QueryService()


# ── Billing & Query History (unchanged) ──

@router.get("/billing/summary")
async def get_billing_summary(days: int = Query(30, ge=1, le=365)):
    query = query_service.build_billing_summary_query(days=days)
    rows = get_sql_executor().execute(query)
    return {"products": rows, "days": days}


@router.get("/billing/daily")
async def get_billing_daily(days: int = Query(30, ge=1, le=365)):
    query = query_service.build_billing_daily_query(days=days)
    rows = get_sql_executor().execute(query)
    return {"daily": rows, "days": days}


@router.get("/queries/stats")
async def get_query_stats(days: int = Query(7, ge=1, le=90)):
    query = query_service.build_query_history_stats_query(days=days)
    rows = get_sql_executor().execute(query)
    return {"stats": rows, "days": days}


@router.get("/queries/daily")
async def get_query_daily(days: int = Query(7, ge=1, le=90)):
    query = query_service.build_query_history_daily_query(days=days)
    rows = get_sql_executor().execute(query)
    return {"daily": rows, "days": days}


# ── AI Gateway Dashboard Endpoints ──

@router.get("/ai-gateway/endpoints")
async def get_ai_gateway_endpoints(days: float = Query(7, ge=0.01, le=365)):
    query = query_service.build_ai_gateway_endpoints_query(days=days)
    rows = get_sql_executor().execute(query)
    return {"endpoints": [r["endpoint_name"] for r in rows]}


@router.get("/ai-gateway/overview")
async def get_ai_gateway_overview(
    days: float = Query(7, ge=0.01, le=365),
    endpoint: Optional[str] = Query(None),
):
    executor = get_sql_executor()
    kpis = executor.execute(query_service.build_ai_gateway_overview_kpis_query(days, endpoint))
    daily = executor.execute(query_service.build_ai_gateway_overview_daily_query(days, endpoint))
    top_endpoints = executor.execute(query_service.build_ai_gateway_overview_top_endpoints_query(days, endpoint))
    top_models = executor.execute(query_service.build_ai_gateway_overview_top_models_query(days, endpoint))
    top_users = executor.execute(query_service.build_ai_gateway_overview_top_users_query(days, endpoint))
    latency = executor.execute(query_service.build_ai_gateway_overview_latency_by_endpoint_query(days, endpoint))
    return {
        "kpis": kpis[0] if kpis else {},
        "daily": daily,
        "top_endpoints": top_endpoints,
        "top_models": top_models,
        "top_users": top_users,
        "latency_by_endpoint": latency,
    }


@router.get("/ai-gateway/performance")
async def get_ai_gateway_performance(
    days: float = Query(7, ge=0.01, le=365),
    endpoint: Optional[str] = Query(None),
):
    executor = get_sql_executor()
    kpis = executor.execute(query_service.build_ai_gateway_performance_kpis_query(days, endpoint))
    latency = executor.execute(query_service.build_ai_gateway_performance_latency_by_endpoint_query(days, endpoint))
    status_codes = executor.execute(query_service.build_ai_gateway_performance_status_codes_query(days, endpoint))
    tpm = executor.execute(query_service.build_ai_gateway_performance_tpm_query(days, endpoint))
    ttfb = executor.execute(query_service.build_ai_gateway_performance_ttfb_by_endpoint_query(days, endpoint))
    ttft_loss = executor.execute(query_service.build_ai_gateway_performance_ttft_loss_query(days, endpoint))
    errors = executor.execute(query_service.build_ai_gateway_performance_errors_by_endpoint_query(days, endpoint))
    return {
        "kpis": kpis[0] if kpis else {},
        "latency_by_endpoint": latency,
        "status_codes": status_codes,
        "tpm_by_endpoint": tpm,
        "ttfb_by_endpoint": ttfb,
        "ttft_loss": ttft_loss,
        "errors_by_endpoint": errors,
    }


@router.get("/ai-gateway/usage")
async def get_ai_gateway_usage(
    days: float = Query(7, ge=0.01, le=365),
    endpoint: Optional[str] = Query(None),
):
    executor = get_sql_executor()
    kpis = executor.execute(query_service.build_ai_gateway_usage_kpis_query(days, endpoint))
    by_endpoint = executor.execute(query_service.build_ai_gateway_usage_tokens_by_endpoint_query(days, endpoint))
    by_model = executor.execute(query_service.build_ai_gateway_usage_tokens_by_model_query(days, endpoint))
    by_user = executor.execute(query_service.build_ai_gateway_usage_tokens_by_user_query(days, endpoint))
    input_output = executor.execute(query_service.build_ai_gateway_usage_input_output_query(days, endpoint))
    cache_hit = executor.execute(query_service.build_ai_gateway_usage_cache_hit_query(days, endpoint))
    return {
        "kpis": kpis[0] if kpis else {},
        "tokens_by_endpoint": by_endpoint,
        "tokens_by_model": by_model,
        "tokens_by_user": by_user,
        "input_output": input_output,
        "cache_hit_by_endpoint": cache_hit,
    }


@router.get("/ai-gateway/coding-agents")
async def get_ai_gateway_coding_agents(
    days: float = Query(7, ge=0.01, le=365),
    endpoint: Optional[str] = Query(None),
    agent: Optional[str] = Query(None),
):
    executor = get_sql_executor()
    summary = executor.execute(query_service.build_ai_gateway_coding_agents_summary_query(days, endpoint, agent))
    daily = executor.execute(query_service.build_ai_gateway_coding_agents_daily_query(days, endpoint, agent))
    by_endpoint = executor.execute(query_service.build_ai_gateway_coding_agents_by_endpoint_query(days, endpoint, agent))
    by_model = executor.execute(query_service.build_ai_gateway_coding_agents_by_model_query(days, endpoint, agent))
    user_analytics = executor.execute(query_service.build_ai_gateway_coding_agents_user_analytics_query(days, endpoint, agent))

    total_requests = sum(int(r.get("requests", 0)) for r in summary)
    total_tokens = sum(int(r.get("total_tokens", 0)) for r in summary)
    unique_users = len(set(r.get("requester", "") for r in user_analytics))

    return {
        "kpis": {
            "total_requests": str(total_requests),
            "total_tokens": str(total_tokens),
            "unique_users": str(unique_users),
        },
        "summary": summary,
        "daily": daily,
        "by_endpoint": by_endpoint,
        "by_model": by_model,
        "user_analytics": user_analytics,
    }


@router.get("/ai-gateway/token-consumption")
async def get_ai_gateway_token_consumption(
    days: float = Query(7, ge=0.01, le=365),
    endpoint: Optional[str] = Query(None),
):
    executor = get_sql_executor()
    kpis = executor.execute(query_service.build_ai_gateway_token_consumption_kpis_query(days, endpoint))
    daily = executor.execute(query_service.build_ai_gateway_token_consumption_daily_query(days, endpoint))
    by_dest_type = executor.execute(query_service.build_ai_gateway_token_consumption_by_dest_type_query(days, endpoint))
    weekly = executor.execute(query_service.build_ai_gateway_token_consumption_weekly_query(days, endpoint))
    top_endpoints = executor.execute(query_service.build_ai_gateway_token_consumption_top_endpoints_query(days, endpoint))
    top_models = executor.execute(query_service.build_ai_gateway_token_consumption_top_models_query(days, endpoint))
    top_users = executor.execute(query_service.build_ai_gateway_token_consumption_top_users_query(days, endpoint))
    return {
        "kpis": kpis[0] if kpis else {},
        "daily": daily,
        "by_destination_type": by_dest_type,
        "weekly_by_endpoint": weekly,
        "top_endpoints": top_endpoints,
        "top_models": top_models,
        "top_users": top_users,
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/routers/platform.py
git commit -m "feat(backend): add AI Gateway dashboard API endpoints"
```

---

### Task 5: Frontend — Types and Hooks

**Files:**
- Modify: `frontend/src/types/api.ts` (append new interfaces)
- Modify: `frontend/src/shared/hooks/useApi.ts` (add hooks, remove old 3)
- Create: `frontend/src/shared/utils/gatewayColors.ts`

- [ ] **Step 1: Add new types to api.ts**

Append to `frontend/src/types/api.ts` before the final blank line:

```typescript
// ── AI Gateway Dashboard Types ──

export interface GatewayOverviewData {
  kpis: { total_requests: string; total_tokens: string; total_unique_users: string };
  daily: { date: string; requests: string; tokens: string; unique_users: string }[];
  top_endpoints: { endpoint_name: string; total_tokens: string; requests: string }[];
  top_models: { model: string; total_tokens: string; requests: string }[];
  top_users: { requester: string; requests: string; total_tokens: string }[];
  latency_by_endpoint: { date: string; endpoint_name: string; avg_latency_ms: string; avg_ttfb_ms: string }[];
}

export interface GatewayPerformanceData {
  kpis: { median_latency_ms: string; median_ttfb_ms: string; error_count: string };
  latency_by_endpoint: { date: string; endpoint_name: string; median_latency_ms: string }[];
  status_codes: { status_code: string; count: string }[];
  tpm_by_endpoint: { date: string; endpoint_name: string; tpm: string }[];
  ttfb_by_endpoint: { date: string; endpoint_name: string; median_ttfb_ms: string }[];
  ttft_loss: { endpoint_name: string; avg_ttfb_ms: string; avg_generation_ms: string }[];
  errors_by_endpoint: { endpoint_name: string; error_count: string }[];
}

export interface GatewayUsageData {
  kpis: { total_endpoints: string; active_users: string };
  tokens_by_endpoint: { date: string; endpoint_name: string; tokens: string }[];
  tokens_by_model: { date: string; model: string; tokens: string }[];
  tokens_by_user: { date: string; requester: string; tokens: string }[];
  input_output: { date: string; input_tokens: string; output_tokens: string }[];
  cache_hit_by_endpoint: { endpoint_name: string; cache_read_tokens: string; total_input_tokens: string; cache_hit_pct: string }[];
}

export interface GatewayCodingAgentsData {
  kpis: { total_requests: string; total_tokens: string; unique_users: string };
  summary: { coding_agent: string; requests: string; total_tokens: string; unique_users: string; avg_latency_ms: string }[];
  daily: { date: string; coding_agent: string; requests: string; tokens: string; avg_latency_ms: string }[];
  by_endpoint: { endpoint_name: string; requests: string }[];
  by_model: { coding_agent: string; model: string; tokens: string }[];
  user_analytics: { requester: string; coding_agent: string; total_tokens: string; requests: string; avg_latency_ms: string }[];
}

export interface GatewayTokenConsumptionData {
  kpis: { total_tokens: string; total_requests: string; avg_tokens_per_request: string };
  daily: { date: string; tokens: string }[];
  by_destination_type: { destination_type: string; tokens: string }[];
  weekly_by_endpoint: { week: string; endpoint_name: string; tokens: string }[];
  top_endpoints: { endpoint_name: string; tokens: string }[];
  top_models: { model: string; tokens: string }[];
  top_users: { requester: string; tokens: string }[];
}
```

- [ ] **Step 2: Add new hooks and remove old ones in useApi.ts**

Remove the old 3 hooks (`useAiGatewayModels`, `useAiGatewayDaily`, `useAiGatewayErrors` at lines 177-196) and their type imports (`AiGatewayModelStat`, `AiGatewayDaily`, `AiGatewayError`).

Add new imports and hooks. Add these types to the import block:

```typescript
import type {
  // ... existing imports ...
  GatewayOverviewData,
  GatewayPerformanceData,
  GatewayUsageData,
  GatewayCodingAgentsData,
  GatewayTokenConsumptionData,
} from "@/types/api";
```

Add these hooks (replacing the removed ones, in the same location):

```typescript
// ── AI Gateway Dashboard Hooks ──

function gatewayParams(days: number, endpoint: string | null, agent?: string | null): string {
  const params = new URLSearchParams();
  params.set("days", String(days));
  if (endpoint) params.set("endpoint", endpoint);
  if (agent) params.set("agent", agent);
  return params.toString();
}

export function useAiGatewayEndpoints(days = 7) {
  return useQuery<{ endpoints: string[] }>({
    queryKey: ["platform", "ai-gateway", "endpoints", { days }],
    queryFn: () => fetchJson(`/api/v1/platform/ai-gateway/endpoints?days=${days}`),
  });
}

export function useAiGatewayOverview(days = 7, endpoint: string | null = null) {
  return useQuery<GatewayOverviewData>({
    queryKey: ["platform", "ai-gateway", "overview", { days, endpoint }],
    queryFn: () => fetchJson(`/api/v1/platform/ai-gateway/overview?${gatewayParams(days, endpoint)}`),
  });
}

export function useAiGatewayPerformance(days = 7, endpoint: string | null = null) {
  return useQuery<GatewayPerformanceData>({
    queryKey: ["platform", "ai-gateway", "performance", { days, endpoint }],
    queryFn: () => fetchJson(`/api/v1/platform/ai-gateway/performance?${gatewayParams(days, endpoint)}`),
  });
}

export function useAiGatewayUsage(days = 7, endpoint: string | null = null) {
  return useQuery<GatewayUsageData>({
    queryKey: ["platform", "ai-gateway", "usage", { days, endpoint }],
    queryFn: () => fetchJson(`/api/v1/platform/ai-gateway/usage?${gatewayParams(days, endpoint)}`),
  });
}

export function useAiGatewayCodingAgents(days = 7, endpoint: string | null = null, agent: string | null = null) {
  return useQuery<GatewayCodingAgentsData>({
    queryKey: ["platform", "ai-gateway", "coding-agents", { days, endpoint, agent }],
    queryFn: () => fetchJson(`/api/v1/platform/ai-gateway/coding-agents?${gatewayParams(days, endpoint, agent)}`),
  });
}

export function useAiGatewayTokenConsumption(days = 7, endpoint: string | null = null) {
  return useQuery<GatewayTokenConsumptionData>({
    queryKey: ["platform", "ai-gateway", "token-consumption", { days, endpoint }],
    queryFn: () => fetchJson(`/api/v1/platform/ai-gateway/token-consumption?${gatewayParams(days, endpoint)}`),
  });
}
```

- [ ] **Step 3: Create gatewayColors.ts**

Create `frontend/src/shared/utils/gatewayColors.ts`:

```typescript
export const CHART_COLORS = [
  '#06b6d4', // cyan
  '#f59e0b', // amber
  '#8b5cf6', // violet
  '#22c55e', // green
  '#ec4899', // pink
  '#ef4444', // red
  '#6366f1', // indigo
  '#14b8a6', // teal
];

export function formatNum(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(2)}K`;
  return n.toLocaleString();
}

export function fmtMs(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Dark theme tokens for AI Gateway dashboard cards */
export const DARK = {
  bg: '#0f1724',
  card: '#1a2332',
  border: '#2d3748',
  label: '#94a3b8',
  value: '#f8fafc',
  muted: '#64748b',
  rowBorder: '#1e293b',
} as const;
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/shared/hooks/useApi.ts frontend/src/shared/utils/gatewayColors.ts
git commit -m "feat(frontend): add AI Gateway types, hooks, and shared utilities"
```

---

### Task 6: Frontend — PlatformPage Shell with Tabs

**Files:**
- Rewrite: `frontend/src/views/platform/PlatformPage.tsx`

- [ ] **Step 1: Create the components directory**

```bash
mkdir -p frontend/src/views/platform/components
```

- [ ] **Step 2: Rewrite PlatformPage.tsx**

Replace `frontend/src/views/platform/PlatformPage.tsx` entirely:

```tsx
import { useState } from "react";
import {
  Box,
  Heading,
  VStack,
  Text,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Select,
  HStack,
  Spinner,
  Center,
} from "@chakra-ui/react";
import { useTimeRange } from "@/shared/context/TimeRangeContext";
import { useAiGatewayEndpoints } from "@/shared/hooks/useApi";
import { DARK } from "@/shared/utils/gatewayColors";
import OverviewTab from "./components/OverviewTab";
import PerformanceTab from "./components/PerformanceTab";
import UsageTab from "./components/UsageTab";
import CodingAgentsTab from "./components/CodingAgentsTab";
import TokenConsumptionTab from "./components/TokenConsumptionTab";

export default function PlatformPage() {
  const { days } = useTimeRange();
  const [selectedEndpoint, setSelectedEndpoint] = useState<string | null>(null);
  const { data: endpointData, isLoading: loadingEndpoints } = useAiGatewayEndpoints(days);

  const endpoints = endpointData?.endpoints ?? [];

  return (
    <Box p={8}>
      <VStack spacing={6} align="stretch">
        <Box>
          <Heading size="lg" mb={1}>AI Gateway Analytics</Heading>
          <Text color="gray.500" fontSize="sm">
            Comprehensive AI Gateway usage, performance, and token analytics
          </Text>
        </Box>

        <Box bg={DARK.bg} borderRadius="soft-lg" p={6} minH="80vh">
          {/* Endpoint filter */}
          <HStack mb={5} spacing={3}>
            <Text fontSize="xs" color={DARK.label} textTransform="uppercase" letterSpacing="0.5px" whiteSpace="nowrap">
              AI Gateway Endpoint
            </Text>
            {loadingEndpoints ? (
              <Spinner size="xs" color="cyan.400" />
            ) : (
              <Select
                size="sm"
                maxW="300px"
                bg={DARK.card}
                border="1px solid"
                borderColor={DARK.border}
                color={DARK.value}
                value={selectedEndpoint ?? ""}
                onChange={(e) => setSelectedEndpoint(e.target.value || null)}
                _focus={{ borderColor: "cyan.500" }}
              >
                <option value="" style={{ background: DARK.card }}>All Endpoints</option>
                {endpoints.map((ep) => (
                  <option key={ep} value={ep} style={{ background: DARK.card }}>{ep}</option>
                ))}
              </Select>
            )}
          </HStack>

          <Tabs isLazy variant="soft-rounded" colorScheme="cyan">
            <TabList
              mb={5}
              sx={{
                "& .chakra-tabs__tab": { color: DARK.label, fontSize: "sm" },
                "& .chakra-tabs__tab[aria-selected=true]": { color: DARK.bg, bg: "cyan.400" },
              }}
            >
              <Tab>Overview</Tab>
              <Tab>Performance</Tab>
              <Tab>Usage</Tab>
              <Tab>Coding Agents</Tab>
              <Tab>Token Consumption</Tab>
            </TabList>
            <TabPanels>
              <TabPanel px={0} pt={2}>
                <OverviewTab days={days} endpoint={selectedEndpoint} />
              </TabPanel>
              <TabPanel px={0} pt={2}>
                <PerformanceTab days={days} endpoint={selectedEndpoint} />
              </TabPanel>
              <TabPanel px={0} pt={2}>
                <UsageTab days={days} endpoint={selectedEndpoint} />
              </TabPanel>
              <TabPanel px={0} pt={2}>
                <CodingAgentsTab days={days} endpoint={selectedEndpoint} />
              </TabPanel>
              <TabPanel px={0} pt={2}>
                <TokenConsumptionTab days={days} endpoint={selectedEndpoint} />
              </TabPanel>
            </TabPanels>
          </Tabs>
        </Box>
      </VStack>
    </Box>
  );
}
```

- [ ] **Step 3: Create placeholder tab components**

Create placeholder files for all 5 tabs so TypeScript compiles. Each one follows this pattern (substitute the name):

`frontend/src/views/platform/components/OverviewTab.tsx`:
```tsx
import { Center, Spinner } from "@chakra-ui/react";

export default function OverviewTab({ days, endpoint }: { days: number; endpoint: string | null }) {
  return <Center py={20}><Spinner color="cyan.400" /></Center>;
}
```

Create the same for `PerformanceTab.tsx`, `UsageTab.tsx`, `CodingAgentsTab.tsx`, and `TokenConsumptionTab.tsx` — each with the matching component name.

- [ ] **Step 4: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors (or only pre-existing warnings)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/platform/
git commit -m "feat(frontend): add Platform page tabs shell with endpoint filter"
```

---

### Task 7: Frontend — Overview Tab

**Files:**
- Rewrite: `frontend/src/views/platform/components/OverviewTab.tsx`

- [ ] **Step 1: Implement OverviewTab**

Replace the placeholder with the full implementation. This component should:

1. Call `useAiGatewayOverview(days, endpoint)` 
2. Show 3 KPI stat cards (Total Requests, Total Tokens, Total Unique Users) in a `SimpleGrid columns={3}` with dark card styling using `DARK` tokens
3. Show 3 Recharts charts in a `SimpleGrid columns={3}`: Daily Requests (`<BarChart>`), Daily Token Usage (`<BarChart>`), Daily Unique Users (`<LineChart>`)
4. Show 3 top-N tables in a `SimpleGrid columns={3}`: Top Endpoints, Top Models, Top Users — each as a simple HTML `<table>` styled with DARK tokens
5. Show 2 multi-line charts in a `SimpleGrid columns={2}`: TTFB by Endpoint, Latency by Endpoint — using `<LineChart>` with one `<Line>` per endpoint, colored from `CHART_COLORS`
6. Use `formatNum` and `fmtMs` from `gatewayColors.ts`
7. Use `formatAxisLabel` from `@/shared/utils/dates` for X-axis labels
8. Pivot the `latency_by_endpoint` array from row-per-endpoint-per-day into chart-friendly format: `{ date, [endpoint1]: value, [endpoint2]: value, ... }`
9. Handle loading state with `<Spinner>` and empty state with a "No data" message

The chart card pattern for every chart:
```tsx
<Box bg={DARK.card} borderRadius="10px" border="1px solid" borderColor={DARK.border} p={4}>
  <Text fontSize="xs" color={DARK.label} mb={3}>{title}</Text>
  <ResponsiveContainer width="100%" height={chartHeight}>
    {/* chart */}
  </ResponsiveContainer>
</Box>
```

Recharts imports needed: `ResponsiveContainer, BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid`

Recharts axis styling:
```tsx
<XAxis dataKey="date" tick={{ fontSize: 10, fill: DARK.muted }} tickFormatter={formatAxisLabel} />
<YAxis tick={{ fontSize: 10, fill: DARK.muted }} tickFormatter={(v) => formatNum(v)} />
<CartesianGrid strokeDasharray="3 3" stroke={DARK.border} vertical={false} />
<Tooltip contentStyle={{ background: DARK.card, border: `1px solid ${DARK.border}`, fontSize: 12, color: DARK.value }} />
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/platform/components/OverviewTab.tsx
git commit -m "feat(frontend): implement Overview tab with KPIs, charts, tables"
```

---

### Task 8: Frontend — Performance Tab

**Files:**
- Rewrite: `frontend/src/views/platform/components/PerformanceTab.tsx`

- [ ] **Step 1: Implement PerformanceTab**

This component should:

1. Call `useAiGatewayPerformance(days, endpoint)`
2. Show 3 KPI cards: Median Latency (formatted with `fmtMs`), Median TTFB (formatted with `fmtMs`), Error Count (formatted with `formatNum`, red color)
3. Row 1 (3-column grid):
   - Median Latency by Endpoint: `<LineChart>` — pivot `latency_by_endpoint` by `endpoint_name`, one `<Line>` per endpoint
   - Status Code Distribution: `<PieChart>` with `<Pie>` and `<Cell>` per status code. Colors: 200=`#22c55e`, 429=`#f59e0b`, 400/500=`#ef4444`, other=`#64748b`
   - TPM by Endpoint: `<LineChart>` — pivot `tpm_by_endpoint` by `endpoint_name`
4. Row 2 (3-column grid):
   - Median TTFB by Endpoint: `<LineChart>` — pivot `ttfb_by_endpoint`
   - TTFT Loss: `<BarChart>` with two stacked `<Bar>` — `avg_ttfb_ms` and `avg_generation_ms` per endpoint
   - Error Rate by Endpoint: `<BarChart>` — single `<Bar>` for `error_count` per endpoint

Additional Recharts imports: `PieChart, Pie, Cell`

Use the same dark card and axis patterns from Task 7.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/platform/components/PerformanceTab.tsx
git commit -m "feat(frontend): implement Performance tab with latency, errors, status codes"
```

---

### Task 9: Frontend — Usage Tab

**Files:**
- Rewrite: `frontend/src/views/platform/components/UsageTab.tsx`

- [ ] **Step 1: Implement UsageTab**

This component should:

1. Call `useAiGatewayUsage(days, endpoint)`
2. Show 3 KPI cards: Total Endpoints, Active Endpoints (same value, labeled differently), Active Users
3. Row 1 (3-column grid):
   - Token Usage by Endpoint: `<BarChart>` stacked — pivot `tokens_by_endpoint` by day, one `<Bar>` per endpoint
   - Token Usage by Model: `<BarChart>` stacked — pivot `tokens_by_model` by day
   - Token Usage by User: `<LineChart>` — pivot `tokens_by_user` by day
4. Row 2 (3-column grid):
   - Daily Input vs Output: `<BarChart>` stacked — two `<Bar>` (input_tokens, output_tokens)
   - Token Volume Distribution: Skip histogram (complex to compute from API data) — replace with a simpler "Tokens by Endpoint" horizontal bar using cached data from kpis.  Actually, show "Input vs Output Ratio" as a simple stat or reuse existing data more meaningfully. Use a simple horizontal bar chart showing total tokens per endpoint from `tokens_by_endpoint` aggregated.
   - Cache Hit Rate by Endpoint: horizontal `<BarChart>` layout with `layout="vertical"` — `cache_hit_pct` per endpoint

For stacked bar charts, pivot the daily time-series data:
```typescript
// Input: [{date: "2026-04-01", endpoint_name: "ep-A", tokens: "100"}, {date: "2026-04-01", endpoint_name: "ep-B", tokens: "200"}, ...]
// Output: [{date: "2026-04-01", "ep-A": 100, "ep-B": 200}, ...]
function pivotByDay<T extends Record<string, string>>(rows: T[], dateKey: string, nameKey: string, valueKey: string): { data: Record<string, number>[]; keys: string[] }
```

This pivot function is reused across Overview, Performance, Usage, and Coding Agents tabs — define it inline or in `gatewayColors.ts`.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/platform/components/UsageTab.tsx
git commit -m "feat(frontend): implement Usage tab with token breakdowns and cache rates"
```

---

### Task 10: Frontend — Coding Agents Tab

**Files:**
- Rewrite: `frontend/src/views/platform/components/CodingAgentsTab.tsx`

- [ ] **Step 1: Implement CodingAgentsTab**

This component should:

1. Accept additional `agent` filter state (local to this tab): `const [selectedAgent, setSelectedAgent] = useState<string | null>(null)`
2. Call `useAiGatewayCodingAgents(days, endpoint, selectedAgent)`
3. Show coding agent filter dropdown at top (populated from `summary` array's `coding_agent` values)
4. Show 3 KPI cards: Total Requests, Total Tokens Used, Unique Users
5. Row 1 (3-column grid):
   - Requests by Agent: `<LineChart>` — pivot `daily` by `coding_agent`, dataKey=`requests`
   - Token Distribution by Agent: horizontal 100% stacked bar — compute percentages from `summary`
   - Latency by Agent: `<LineChart>` — pivot `daily` by `coding_agent`, dataKey=`avg_latency_ms`
6. Row 2 (3-column grid):
   - Agent Usage by Endpoint: `<PieChart>` donut — data from `by_endpoint`
   - Agent Usage by Model: horizontal 100% stacked bars — compute from `by_model` grouped by `coding_agent`
   - Agent Usage by User: similar to by_model but different grouping — can show top users as horizontal bars
7. User Analytics table — render `user_analytics` as a dark-themed table with columns: User, Agent (with colored badge), Total Tokens, Requests, Avg Latency

Agent badge color: assign from `CHART_COLORS` based on agent index in the summary array.

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/platform/components/CodingAgentsTab.tsx
git commit -m "feat(frontend): implement Coding Agents tab with auto-discovered agents"
```

---

### Task 11: Frontend — Token Consumption Tab

**Files:**
- Rewrite: `frontend/src/views/platform/components/TokenConsumptionTab.tsx`

- [ ] **Step 1: Implement TokenConsumptionTab**

This component should:

1. Call `useAiGatewayTokenConsumption(days, endpoint)`
2. Show 3 KPI cards: Total Tokens, Total Requests, Avg Tokens per Request
3. Section header "Token Overview" with divider line
4. 2-column grid:
   - Token Consumption over Time: `<AreaChart>` with `<Area>` — data from `daily`, fill with gradient
   - Tokens by Destination Type: horizontal bars — data from `by_destination_type`
5. Section header "Token Breakdown" with divider line
6. Full-width: Weekly Token Consumption by Endpoint — `<BarChart>` stacked, pivot `weekly_by_endpoint` by week
7. 3-column grid: Top Endpoints, Top Models, Top Users — ranked tables from `top_endpoints`, `top_models`, `top_users`

Additional Recharts imports: `AreaChart, Area`

Area chart gradient pattern:
```tsx
<defs>
  <linearGradient id="tokenGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
    <stop offset="95%" stopColor="#6366f1" stopOpacity={0.05} />
  </linearGradient>
</defs>
<Area type="monotone" dataKey="tokens" stroke="#6366f1" fill="url(#tokenGrad)" />
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/platform/components/TokenConsumptionTab.tsx
git commit -m "feat(frontend): implement Token Consumption tab with volume analysis"
```

---

### Task 12: Integration Test — Start Dev Server and Verify

**Files:** None new — testing existing work

- [ ] **Step 1: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TS errors

- [ ] **Step 2: Start backend**

Run the app locally or verify endpoints return data:
```bash
curl -s "http://localhost:8000/api/v1/platform/ai-gateway/endpoints?days=7" | python3 -m json.tool | head -20
curl -s "http://localhost:8000/api/v1/platform/ai-gateway/overview?days=7" | python3 -m json.tool | head -30
```
Expected: JSON with real data from the AI Gateway table

- [ ] **Step 3: Open browser and verify tabs**

Navigate to the Platform page. Verify:
- Endpoint filter dropdown loads with endpoint names
- Overview tab shows KPI cards, charts, and tables with real data
- Clicking other tabs loads their data (lazy — first click triggers fetch)
- Changing time range in sidebar re-fetches active tab
- Changing endpoint filter re-fetches active tab
- Dark theme renders correctly (dark background, light text)
- Charts render with colored lines/bars
- No console errors

- [ ] **Step 4: Commit any fixes**

If any fixes needed during testing, commit them:
```bash
git add -A
git commit -m "fix: address integration issues in AI Gateway dashboard"
```

---

### Task 13: Cleanup — Remove Old Types

**Files:**
- Modify: `frontend/src/types/api.ts` (remove old interfaces if no longer imported)

- [ ] **Step 1: Check if old types are still used**

Search for `AiGatewayModelStat`, `AiGatewayDaily`, `AiGatewayError` across the frontend. If they're only imported in the old hooks (which were removed in Task 5), remove the interfaces from `api.ts` (lines 132-167).

Run: `grep -r "AiGatewayModelStat\|AiGatewayDaily\|AiGatewayError" frontend/src/`

If no results (or only the type definitions themselves), remove the old interfaces.

- [ ] **Step 2: Remove old backend endpoints**

The old endpoints (`/ai-gateway/models`, `/ai-gateway/daily`, `/ai-gateway/errors`) were already removed in Task 4 when we rewrote `platform.py`. Verify they're gone.

- [ ] **Step 3: Final TypeScript check**

Run: `cd frontend && npx tsc --noEmit`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/api.ts
git commit -m "refactor: remove unused AI Gateway types"
```
