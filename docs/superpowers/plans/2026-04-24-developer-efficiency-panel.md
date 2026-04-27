# Developer Efficiency Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Developer Efficiency" page to Claudit that surfaces five AI-native efficiency metrics derived from existing `cc_logs_synced` data — no new instrumentation or SDP tables required for v1.

**Architecture:** New `EfficiencyQueryService` builds parameterized PostgreSQL queries against `zerobus_sdp.cc_logs_synced`. A new FastAPI router at `/api/v1/efficiency/*` calls `cached_execute`. The frontend adds a lazy-loaded `EfficiencyPage` with four visual sections: KPI header cards (AEY, CLi, Rework), Feedback Loop Latency bar chart, Harness Convergence trend line, and a SPACE+DevEx framework context card.

**Tech Stack:** FastAPI + Pydantic (backend), React + TypeScript + Chakra UI + Recharts (frontend), React Query (`@tanstack/react-query`), PostgreSQL CTE queries via Lakebase Provisioned, react-icons/fi for nav icon.

**Framework:** SPACE + DevEx hybrid. Metrics map to framework dimensions:
- Performance (SPACE-P): AI-Effective Yield, Rework Ratio
- Efficiency/Flow (SPACE-E + DevEx): Feedback Loop Latency, Harness Convergence Score
- Cognitive Load (DevEx): Cognitive Load Index

**Scope:** v1 only — all data from existing `cc_logs_synced`. No git/CI integration, no new SDP pipelines, no new Lakebase tables.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `backend/services/efficiency_query_service.py` | SQL builders for all 5 efficiency metrics |
| Create | `backend/routers/efficiency.py` | FastAPI router, 5 GET endpoints + prefix `/api/v1/efficiency` |
| Modify | `backend/routers/__init__.py` | Export `efficiency_router` |
| Modify | `backend/main.py` | Import + `app.include_router(efficiency_router)` |
| Create | `backend/tests/test_efficiency_query_service.py` | Smoke tests: queries are non-empty strings with expected clauses |
| Modify | `frontend/src/shared/hooks/useApi.ts` | Add 5 TypeScript types + 5 `useEfficiency*` hooks |
| Create | `frontend/src/views/efficiency/EfficiencyPage.tsx` | Page shell, layout, framework context card |
| Create | `frontend/src/views/efficiency/components/EfficiencyKpiCards.tsx` | AEY + CLi + Rework ratio stat cards |
| Create | `frontend/src/views/efficiency/components/FeedbackLatencyChart.tsx` | Recharts BarChart, p50/p95 by tool name |
| Create | `frontend/src/views/efficiency/components/HarnessConvergenceChart.tsx` | Recharts LineChart, daily convergence score |
| Modify | `frontend/src/app/router/viewRegistry.ts` | Register `EfficiencyPage` lazy component + route entry |
| Modify | `frontend/src/app/Layout.tsx` | Add `FiActivity` nav icon mapping for `efficiency` |

---

## Task 1: EfficiencyQueryService — SQL builders

**Files:**
- Create: `backend/services/efficiency_query_service.py`

- [ ] **Step 1: Write the service**

```python
from backend.config import settings


class EfficiencyQueryService:
    """SQL builders for the Developer Efficiency Panel (SPACE + DevEx hybrid).

    All queries run against the Lakebase Provisioned PG instance via cached_execute.
    Source table: zerobus_sdp.cc_logs_synced (alias: self.mat)

    Metrics implemented:
      - AI-Effective Yield (AEY): $ cost per in-session accepted decision
      - Cognitive Load Index (CLi): composite of tools/prompt × thrash × reject rate
      - Feedback Loop Latency: p50/p95 duration_ms by tool_name on tool_result events
      - Harness Convergence Score: daily trend of tool efficiency × completion rate
      - Rework Ratio: fraction of file writes that are re-writes to the same file
    """

    @property
    def mat(self) -> str:
        return settings.kpi_logs_mat_table  # zerobus_sdp.cc_logs_synced

    def build_aey_overview(self, days: int = 30) -> str:
        return f"""
            SELECT
                ROUND(SUM(cost_usd) FILTER (WHERE event_name = 'api_request')::numeric, 4)
                    AS total_cost_usd,
                COUNT(*) FILTER (WHERE event_name = 'tool_decision' AND decision = 'accept')
                    AS accepted_decisions,
                ROUND(
                    (SUM(cost_usd) FILTER (WHERE event_name = 'api_request') /
                     NULLIF(COUNT(*) FILTER (WHERE event_name = 'tool_decision' AND decision = 'accept'), 0))::numeric,
                    6
                ) AS cost_per_accepted_decision
            FROM {self.mat}
            WHERE event_ts >= current_date - interval '{days} days'
        """.strip()

    def build_cognitive_load_index(self, days: int = 30) -> str:
        return f"""
            WITH per_session AS (
                SELECT
                    session_id,
                    ROUND(
                        COUNT(*) FILTER (WHERE event_name = 'tool_result')::float /
                        NULLIF(COUNT(DISTINCT prompt_id) FILTER (WHERE event_name = 'user_prompt'), 0),
                        2
                    ) AS tools_per_prompt,
                    ROUND(
                        COUNT(*) FILTER (WHERE event_name = 'tool_decision' AND decision != 'accept')::float /
                        NULLIF(COUNT(*) FILTER (WHERE event_name = 'tool_decision'), 0),
                        3
                    ) AS reject_rate
                FROM {self.mat}
                WHERE event_ts >= current_date - interval '{days} days'
                GROUP BY session_id
            ),
            thrash AS (
                SELECT session_id, COUNT(*) AS repeated_reads
                FROM (
                    SELECT session_id, tool_parameters, COUNT(*) AS reads
                    FROM {self.mat}
                    WHERE event_name = 'tool_result'
                      AND tool_name = 'Read'
                      AND tool_parameters IS NOT NULL
                      AND event_ts >= current_date - interval '{days} days'
                    GROUP BY session_id, tool_parameters
                    HAVING COUNT(*) > 1
                ) r
                GROUP BY session_id
            )
            SELECT
                ROUND(AVG(ps.tools_per_prompt)::numeric, 2)          AS avg_tools_per_prompt,
                ROUND(AVG(COALESCE(t.repeated_reads, 0))::numeric, 2) AS avg_context_thrash,
                ROUND(AVG(COALESCE(ps.reject_rate, 0))::numeric, 3)  AS avg_reject_rate,
                ROUND(
                    (AVG(ps.tools_per_prompt) *
                     (1 + AVG(COALESCE(t.repeated_reads, 0)) / 5.0) *
                     (1 + AVG(COALESCE(ps.reject_rate, 0))))::numeric,
                    3
                ) AS cognitive_load_index
            FROM per_session ps
            LEFT JOIN thrash t ON ps.session_id = t.session_id
        """.strip()

    def build_feedback_latency(self, days: int = 30) -> str:
        return f"""
            SELECT
                tool_name,
                COUNT(*)                                                                          AS call_count,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms)::numeric, 0)      AS p50_ms,
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 0)     AS p95_ms,
                ROUND(AVG(duration_ms)::numeric, 0)                                               AS avg_ms
            FROM {self.mat}
            WHERE event_name = 'tool_result'
              AND duration_ms IS NOT NULL
              AND duration_ms > 0
              AND event_ts >= current_date - interval '{days} days'
            GROUP BY tool_name
            ORDER BY p95_ms DESC NULLS LAST
            LIMIT 20
        """.strip()

    def build_harness_convergence(self, days: int = 30) -> str:
        return f"""
            WITH per_session AS (
                SELECT
                    session_id,
                    date_trunc('day', MIN(event_ts))::date AS session_date,
                    COUNT(DISTINCT prompt_id) FILTER (WHERE event_name = 'user_prompt')          AS prompts,
                    COUNT(*) FILTER (WHERE event_name = 'tool_result')                           AS tool_calls,
                    COUNT(*) FILTER (WHERE event_name = 'api_error')                             AS api_errors,
                    COUNT(*) FILTER (WHERE event_name IN ('api_request', 'api_error'))           AS api_total
                FROM {self.mat}
                WHERE event_ts >= current_date - interval '{days} days'
                GROUP BY session_id
                HAVING COUNT(DISTINCT prompt_id) FILTER (WHERE event_name = 'user_prompt') > 0
                   AND COUNT(*) FILTER (WHERE event_name = 'tool_result') > 0
                   AND COUNT(*) FILTER (WHERE event_name IN ('api_request', 'api_error')) > 0
            ),
            scored AS (
                SELECT
                    session_date,
                    (1.0 - api_errors::float / NULLIF(api_total, 0)) /
                    (1.0 + tool_calls::float / NULLIF(prompts, 0) / 10.0) AS convergence_score
                FROM per_session
            )
            SELECT
                session_date                                         AS date,
                ROUND(AVG(convergence_score)::numeric, 3)           AS avg_convergence_score,
                COUNT(*)                                             AS session_count
            FROM scored
            GROUP BY session_date
            ORDER BY date ASC
        """.strip()

    def build_rework_ratio(self, days: int = 30) -> str:
        return f"""
            WITH file_writes AS (
                SELECT
                    session_id,
                    COALESCE(
                        substring(tool_parameters FROM '"file_path"\\s*:\\s*"([^"]+)"'),
                        substring(tool_parameters FROM '"path"\\s*:\\s*"([^"]+)"'),
                        tool_parameters
                    ) AS file_path,
                    event_ts
                FROM {self.mat}
                WHERE event_name = 'tool_result'
                  AND tool_name IN ('Edit', 'Write', 'MultiEdit')
                  AND tool_parameters IS NOT NULL
                  AND event_ts >= current_date - interval '{days} days'
            ),
            write_counts AS (
                SELECT session_id, file_path, COUNT(*) AS writes
                FROM file_writes
                GROUP BY session_id, file_path
            ),
            rework_per_session AS (
                SELECT
                    session_id,
                    SUM(writes)                      AS total_writes,
                    SUM(GREATEST(writes - 1, 0))     AS rework_writes
                FROM write_counts
                GROUP BY session_id
            )
            SELECT
                ROUND(AVG(rework_writes::float / NULLIF(total_writes, 0))::numeric, 3)    AS avg_rework_ratio,
                ROUND(SUM(rework_writes)::float / NULLIF(SUM(total_writes), 0)::numeric, 3) AS overall_rework_ratio,
                SUM(rework_writes)::int                                                    AS total_rework_writes,
                SUM(total_writes)::int                                                     AS total_writes,
                COUNT(*)                                                                   AS sessions_with_writes
            FROM rework_per_session
            WHERE total_writes > 0
        """.strip()
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/efficiency_query_service.py
git commit -m "feat(backend): add EfficiencyQueryService with SPACE+DevEx SQL builders"
```

---

## Task 2: Write tests for EfficiencyQueryService

**Files:**
- Create: `backend/tests/test_efficiency_query_service.py`

- [ ] **Step 1: Write smoke tests**

```python
import pytest
from backend.services.efficiency_query_service import EfficiencyQueryService


@pytest.fixture
def svc():
    return EfficiencyQueryService()


def test_aey_overview_returns_nonempty_string(svc):
    q = svc.build_aey_overview(days=30)
    assert isinstance(q, str)
    assert len(q) > 0
    assert "cost_per_accepted_decision" in q
    assert "tool_decision" in q
    assert "api_request" in q


def test_cognitive_load_index_contains_key_clauses(svc):
    q = svc.build_cognitive_load_index(days=7)
    assert "cognitive_load_index" in q
    assert "per_session" in q
    assert "thrash" in q
    assert "interval '7 days'" in q


def test_feedback_latency_returns_percentile_query(svc):
    q = svc.build_feedback_latency(days=30)
    assert "PERCENTILE_CONT(0.5)" in q
    assert "PERCENTILE_CONT(0.95)" in q
    assert "p50_ms" in q
    assert "p95_ms" in q
    assert "tool_name" in q


def test_harness_convergence_returns_dated_rows(svc):
    q = svc.build_harness_convergence(days=14)
    assert "avg_convergence_score" in q
    assert "session_date" in q or "date" in q
    assert "interval '14 days'" in q


def test_rework_ratio_extracts_file_path(svc):
    q = svc.build_rework_ratio(days=30)
    assert "rework_ratio" in q
    assert "file_path" in q
    assert "Edit" in q
    assert "Write" in q


def test_all_queries_use_correct_table(svc):
    builders = [
        svc.build_aey_overview,
        svc.build_cognitive_load_index,
        svc.build_feedback_latency,
        svc.build_harness_convergence,
        svc.build_rework_ratio,
    ]
    for build_fn in builders:
        q = build_fn(days=30)
        assert svc.mat in q, f"{build_fn.__name__} missing table reference"
```

- [ ] **Step 2: Run tests**

Run: `cd /path/to/claudit && python -m pytest backend/tests/test_efficiency_query_service.py -v`

Expected: 6 tests PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_efficiency_query_service.py
git commit -m "test(backend): smoke tests for EfficiencyQueryService"
```

---

## Task 3: Efficiency Router

**Files:**
- Create: `backend/routers/efficiency.py`

- [ ] **Step 1: Write the router**

```python
from fastapi import APIRouter, Query
from backend.services.efficiency_query_service import EfficiencyQueryService
from backend.cache import cached_execute

router = APIRouter(prefix="/api/v1/efficiency", tags=["efficiency"])

_svc = EfficiencyQueryService()


@router.get("/aey")
async def get_aey_overview(days: int = Query(30, ge=1, le=365)):
    query = _svc.build_aey_overview(days=days)
    rows = await cached_execute(f"efficiency_aey:{days}", query)
    return rows[0] if rows else {
        "total_cost_usd": 0,
        "accepted_decisions": 0,
        "cost_per_accepted_decision": None,
    }


@router.get("/cognitive-load")
async def get_cognitive_load(days: int = Query(30, ge=1, le=365)):
    query = _svc.build_cognitive_load_index(days=days)
    rows = await cached_execute(f"efficiency_cognitive_load:{days}", query)
    return rows[0] if rows else {
        "avg_tools_per_prompt": 0,
        "avg_context_thrash": 0,
        "avg_reject_rate": 0,
        "cognitive_load_index": None,
    }


@router.get("/feedback-latency")
async def get_feedback_latency(days: int = Query(30, ge=1, le=365)):
    query = _svc.build_feedback_latency(days=days)
    rows = await cached_execute(f"efficiency_feedback_latency:{days}", query)
    return {"tools": rows, "days": days}


@router.get("/harness-convergence")
async def get_harness_convergence(days: int = Query(30, ge=1, le=365)):
    query = _svc.build_harness_convergence(days=days)
    rows = await cached_execute(f"efficiency_harness_convergence:{days}", query)
    return {"trend": rows, "days": days}


@router.get("/rework-ratio")
async def get_rework_ratio(days: int = Query(30, ge=1, le=365)):
    query = _svc.build_rework_ratio(days=days)
    rows = await cached_execute(f"efficiency_rework_ratio:{days}", query)
    return rows[0] if rows else {
        "avg_rework_ratio": 0,
        "overall_rework_ratio": 0,
        "total_rework_writes": 0,
        "total_writes": 0,
        "sessions_with_writes": 0,
    }
```

- [ ] **Step 2: Commit**

```bash
git add backend/routers/efficiency.py
git commit -m "feat(backend): add efficiency router — AEY, CLi, latency, convergence, rework"
```

---

## Task 4: Wire router into the app

**Files:**
- Modify: `backend/routers/__init__.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Export from `__init__.py`**

In `backend/routers/__init__.py`, add at end of imports and `__all__`:

```python
# Add to imports:
from backend.routers.efficiency import router as efficiency_router

# Update __all__:
__all__ = ["metrics_router", "sessions_router", "mcp_tools_router", "platform_router",
           "mcp_servers_router", "kpis_router", "introspection_router", "efficiency_router"]
```

- [ ] **Step 2: Register in `main.py`**

In `backend/main.py`, change the import line:

```python
# Before:
from backend.routers import metrics_router, sessions_router, mcp_tools_router, platform_router, mcp_servers_router, kpis_router, introspection_router

# After:
from backend.routers import metrics_router, sessions_router, mcp_tools_router, platform_router, mcp_servers_router, kpis_router, introspection_router, efficiency_router
```

Then add after `app.include_router(introspection_router)`:

```python
app.include_router(efficiency_router)
```

- [ ] **Step 3: Verify the app starts**

Run: `cd /path/to/claudit && python -m uvicorn backend.main:app --port 8001 --reload`

Expected: Server starts with no import errors. Visit `http://localhost:8001/docs` and confirm `/api/v1/efficiency/aey` appears in the OpenAPI spec.

Stop the server (Ctrl-C).

- [ ] **Step 4: Commit**

```bash
git add backend/routers/__init__.py backend/main.py
git commit -m "feat(backend): wire efficiency router into FastAPI app"
```

---

## Task 5: TypeScript types and hooks

**Files:**
- Modify: `frontend/src/shared/hooks/useApi.ts`

- [ ] **Step 1: Add type definitions**

In `useApi.ts`, add these interfaces after the existing type imports (find the block of `interface` definitions):

```typescript
// ── Developer Efficiency types ──

export interface EfficiencyAey {
  total_cost_usd: string | null;
  accepted_decisions: string | null;
  cost_per_accepted_decision: string | null;
}

export interface EfficiencyCognitiveLoad {
  avg_tools_per_prompt: string | null;
  avg_context_thrash: string | null;
  avg_reject_rate: string | null;
  cognitive_load_index: string | null;
}

export interface EfficiencyFeedbackTool {
  tool_name: string;
  call_count: string;
  p50_ms: string | null;
  p95_ms: string | null;
  avg_ms: string | null;
}

export interface EfficiencyFeedbackLatency {
  tools: EfficiencyFeedbackTool[];
  days: number;
}

export interface EfficiencyConvergencePoint {
  date: string;
  avg_convergence_score: string | null;
  session_count: string;
}

export interface EfficiencyHarnessConvergence {
  trend: EfficiencyConvergencePoint[];
  days: number;
}

export interface EfficiencyReworkRatio {
  avg_rework_ratio: string | null;
  overall_rework_ratio: string | null;
  total_rework_writes: string | null;
  total_writes: string | null;
  sessions_with_writes: string | null;
}
```

- [ ] **Step 2: Add hooks**

In `useApi.ts`, add the following hooks after the last existing hook (find the end of the file, before any closing braces):

```typescript
// ── Developer Efficiency hooks ──

export function useEfficiencyAey(days: number) {
  return useQuery<EfficiencyAey>({
    queryKey: ["efficiency", "aey", { days }],
    queryFn: () => fetchJson(`/api/v1/efficiency/aey?days=${days}`),
  });
}

export function useEfficiencyCognitiveLoad(days: number) {
  return useQuery<EfficiencyCognitiveLoad>({
    queryKey: ["efficiency", "cognitive-load", { days }],
    queryFn: () => fetchJson(`/api/v1/efficiency/cognitive-load?days=${days}`),
  });
}

export function useEfficiencyFeedbackLatency(days: number) {
  return useQuery<EfficiencyFeedbackLatency>({
    queryKey: ["efficiency", "feedback-latency", { days }],
    queryFn: () => fetchJson(`/api/v1/efficiency/feedback-latency?days=${days}`),
  });
}

export function useEfficiencyHarnessConvergence(days: number) {
  return useQuery<EfficiencyHarnessConvergence>({
    queryKey: ["efficiency", "harness-convergence", { days }],
    queryFn: () => fetchJson(`/api/v1/efficiency/harness-convergence?days=${days}`),
  });
}

export function useEfficiencyReworkRatio(days: number) {
  return useQuery<EfficiencyReworkRatio>({
    queryKey: ["efficiency", "rework-ratio", { days }],
    queryFn: () => fetchJson(`/api/v1/efficiency/rework-ratio?days=${days}`),
  });
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npm run build 2>&1 | head -30`

Expected: No new TypeScript errors. (Pre-existing warnings in `ModelEfficiencyTab.tsx`, `SessionsPage.tsx`, and `TurnaroundPage.tsx` are not regressions.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/shared/hooks/useApi.ts
git commit -m "feat(frontend): add efficiency TypeScript types and React Query hooks"
```

---

## Task 6: KPI overview cards (AEY + CLi + Rework)

**Files:**
- Create: `frontend/src/views/efficiency/components/EfficiencyKpiCards.tsx`

- [ ] **Step 1: Write the component**

```tsx
import { Box, HStack, Text, Spinner, Center, Tooltip } from "@chakra-ui/react";
import {
  useEfficiencyAey,
  useEfficiencyCognitiveLoad,
  useEfficiencyReworkRatio,
} from "@/shared/hooks/useApi";

function StatCard({
  label,
  value,
  sub,
  tooltip,
  valueColor,
}: {
  label: string;
  value: string;
  sub?: string;
  tooltip?: string;
  valueColor?: string;
}) {
  return (
    <Box
      bg="surface.card"
      borderRadius="soft-lg"
      boxShadow="soft"
      border="1px solid"
      borderColor="soft.border"
      p={5}
      flex={1}
      minW="200px"
    >
      <Tooltip label={tooltip} isDisabled={!tooltip} placement="top" hasArrow>
        <Text fontSize="xs" color="gray.500" fontWeight="500" cursor={tooltip ? "help" : "default"}>
          {label} {tooltip && <span style={{ opacity: 0.5 }}>ⓘ</span>}
        </Text>
      </Tooltip>
      <Text
        fontSize="2xl"
        fontWeight="700"
        color={valueColor ?? "gray.800"}
        fontFamily="mono"
        mt={1}
      >
        {value}
      </Text>
      {sub && (
        <Text fontSize="xs" color="gray.400" mt={1}>
          {sub}
        </Text>
      )}
    </Box>
  );
}

function fmt(val: string | null | undefined, decimals = 2): string {
  if (val == null || val === "null") return "—";
  const n = parseFloat(val);
  return isNaN(n) ? "—" : n.toFixed(decimals);
}

function fmtCost(val: string | null | undefined): string {
  if (val == null || val === "null") return "—";
  const n = parseFloat(val);
  if (isNaN(n)) return "—";
  if (n < 0.001) return `$${(n * 1000).toFixed(3)}m`;
  return `$${n.toFixed(4)}`;
}

function cliColor(cli: string | null | undefined): string {
  if (cli == null || cli === "null") return "gray.800";
  const n = parseFloat(cli);
  if (isNaN(n)) return "gray.800";
  if (n < 1.5) return "green.600";
  if (n < 3.0) return "orange.500";
  return "red.500";
}

interface Props {
  days: number;
}

export default function EfficiencyKpiCards({ days }: Props) {
  const { data: aey, isLoading: aeyLoading } = useEfficiencyAey(days);
  const { data: cli, isLoading: cliLoading } = useEfficiencyCognitiveLoad(days);
  const { data: rework, isLoading: reworkLoading } = useEfficiencyReworkRatio(days);

  if (aeyLoading || cliLoading || reworkLoading) {
    return (
      <Center py={6}>
        <Spinner color="brand.500" />
      </Center>
    );
  }

  const reworkPct = rework?.avg_rework_ratio != null
    ? `${(parseFloat(rework.avg_rework_ratio) * 100).toFixed(1)}%`
    : "—";

  return (
    <HStack spacing={4} flexWrap="wrap" mb={6}>
      <StatCard
        label="AI-Effective Yield"
        value={fmtCost(aey?.cost_per_accepted_decision)}
        sub={`per accepted decision · ${parseInt(aey?.accepted_decisions ?? "0", 10).toLocaleString()} accepted`}
        tooltip="In-session cost (USD) per tool decision the developer accepted. Lower = AI producing more accepted output per dollar spent. Labeled 'in-session' until git linkage is available."
      />
      <StatCard
        label="Cognitive Load Index"
        value={fmt(cli?.cognitive_load_index, 2)}
        sub={`${fmt(cli?.avg_tools_per_prompt)} tools/prompt · ${fmt(cli?.avg_context_thrash)} re-reads · ${(parseFloat(cli?.avg_reject_rate ?? "0") * 100).toFixed(1)}% reject`}
        tooltip="Composite: (tools/prompt) × (1 + context thrash/5) × (1 + reject rate). Lower is better. Green < 1.5, Orange < 3.0, Red ≥ 3.0."
        valueColor={cliColor(cli?.cognitive_load_index)}
      />
      <StatCard
        label="Rework Ratio"
        value={reworkPct}
        sub={`${rework?.total_rework_writes ?? 0} re-writes of ${rework?.total_writes ?? 0} total across ${rework?.sessions_with_writes ?? 0} sessions`}
        tooltip="Fraction of file edit/write operations that target a file already edited in the same session. High rework = AI produced output that needed correction."
      />
    </HStack>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/efficiency/components/EfficiencyKpiCards.tsx
git commit -m "feat(frontend): add EfficiencyKpiCards — AEY, CLi, Rework Ratio"
```

---

## Task 7: Feedback Loop Latency chart

**Files:**
- Create: `frontend/src/views/efficiency/components/FeedbackLatencyChart.tsx`

- [ ] **Step 1: Write the component**

```tsx
import { Box, Text, Spinner, Center } from "@chakra-ui/react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useEfficiencyFeedbackLatency } from "@/shared/hooks/useApi";

interface Props {
  days: number;
}

export default function FeedbackLatencyChart({ days }: Props) {
  const { data, isLoading, error } = useEfficiencyFeedbackLatency(days);

  return (
    <Box
      bg="surface.card"
      borderRadius="soft-lg"
      boxShadow="soft"
      border="1px solid"
      borderColor="soft.border"
      p={5}
      mb={6}
    >
      <Text fontSize="sm" fontWeight="600" color="gray.700" mb={1}>
        Feedback Loop Latency by Tool
      </Text>
      <Text fontSize="xs" color="gray.400" mb={4}>
        p50 / p95 duration (ms) per tool_result event — lower = tighter feedback loop
      </Text>

      {isLoading && (
        <Center py={8}>
          <Spinner color="brand.500" />
        </Center>
      )}
      {error && (
        <Text color="red.500" fontSize="sm">
          Failed to load latency data
        </Text>
      )}

      {data && data.tools.length > 0 && (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart
            data={data.tools.map((t) => ({
              name: t.tool_name,
              p50: t.p50_ms != null ? parseFloat(t.p50_ms) : 0,
              p95: t.p95_ms != null ? parseFloat(t.p95_ms) : 0,
            }))}
            layout="vertical"
            margin={{ top: 0, right: 24, bottom: 0, left: 80 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" unit="ms" tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={80} />
            <Tooltip
              formatter={(value: number, name: string) => [`${value.toLocaleString()}ms`, name]}
            />
            <Legend />
            <Bar dataKey="p50" name="p50" fill="#4A90D9" radius={[0, 3, 3, 0]} />
            <Bar dataKey="p95" name="p95" fill="#E07B54" radius={[0, 3, 3, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}

      {data && data.tools.length === 0 && !isLoading && (
        <Text color="gray.400" fontSize="sm">
          No tool latency data for this period
        </Text>
      )}
    </Box>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/efficiency/components/FeedbackLatencyChart.tsx
git commit -m "feat(frontend): add FeedbackLatencyChart — p50/p95 by tool"
```

---

## Task 8: Harness Convergence trend chart

**Files:**
- Create: `frontend/src/views/efficiency/components/HarnessConvergenceChart.tsx`

- [ ] **Step 1: Write the component**

```tsx
import { Box, Text, Spinner, Center, HStack, Badge } from "@chakra-ui/react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { useEfficiencyHarnessConvergence } from "@/shared/hooks/useApi";

interface Props {
  days: number;
}

export default function HarnessConvergenceChart({ days }: Props) {
  const { data, isLoading, error } = useEfficiencyHarnessConvergence(days);

  const trend = data?.trend ?? [];
  const latest = trend.length > 0
    ? parseFloat(trend[trend.length - 1].avg_convergence_score ?? "0")
    : null;
  const earliest = trend.length > 1
    ? parseFloat(trend[0].avg_convergence_score ?? "0")
    : null;
  const direction =
    latest != null && earliest != null
      ? latest > earliest + 0.01
        ? "↑ improving"
        : latest < earliest - 0.01
        ? "↓ declining"
        : "→ stable"
      : null;

  return (
    <Box
      bg="surface.card"
      borderRadius="soft-lg"
      boxShadow="soft"
      border="1px solid"
      borderColor="soft.border"
      p={5}
      mb={6}
    >
      <HStack mb={1} justify="space-between">
        <Text fontSize="sm" fontWeight="600" color="gray.700">
          Harness Convergence Score
        </Text>
        {direction && (
          <Badge
            colorScheme={
              direction.startsWith("↑") ? "green" : direction.startsWith("↓") ? "red" : "gray"
            }
            fontSize="xs"
          >
            {direction}
          </Badge>
        )}
      </HStack>
      <Text fontSize="xs" color="gray.400" mb={4}>
        Daily average: (1 − error rate) ÷ (1 + tools/prompt/10). Rising = harness more efficient.
        Formula tooltip: higher score means fewer errors AND fewer tool calls per prompt.
      </Text>

      {isLoading && (
        <Center py={8}>
          <Spinner color="brand.500" />
        </Center>
      )}
      {error && (
        <Text color="red.500" fontSize="sm">
          Failed to load convergence data
        </Text>
      )}

      {trend.length > 0 && (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart
            data={trend.map((p) => ({
              date: p.date,
              score: p.avg_convergence_score != null ? parseFloat(p.avg_convergence_score) : null,
              sessions: parseInt(p.session_count, 10),
            }))}
            margin={{ top: 4, right: 16, bottom: 0, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10 }}
              tickFormatter={(d: string) => d.slice(5)}
            />
            <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} tickFormatter={(v) => v.toFixed(2)} />
            <Tooltip
              formatter={(v: number) => [v.toFixed(3), "Convergence Score"]}
              labelFormatter={(l: string) => `Date: ${l}`}
            />
            <ReferenceLine y={0.5} stroke="#ccc" strokeDasharray="4 2" label={{ value: "0.5", fontSize: 10 }} />
            <Line
              type="monotone"
              dataKey="score"
              stroke="#4A90D9"
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {trend.length === 0 && !isLoading && (
        <Text color="gray.400" fontSize="sm">
          No convergence data for this period
        </Text>
      )}
    </Box>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/efficiency/components/HarnessConvergenceChart.tsx
git commit -m "feat(frontend): add HarnessConvergenceChart — daily convergence trend"
```

---

## Task 9: EfficiencyPage — main page shell

**Files:**
- Create: `frontend/src/views/efficiency/EfficiencyPage.tsx`

- [ ] **Step 1: Write the page**

```tsx
import { Box, Heading, Text, VStack, HStack, Badge, Divider } from "@chakra-ui/react";
import { useTimeRange } from "@/shared/context/TimeRangeContext";
import EfficiencyKpiCards from "./components/EfficiencyKpiCards";
import FeedbackLatencyChart from "./components/FeedbackLatencyChart";
import HarnessConvergenceChart from "./components/HarnessConvergenceChart";

function FrameworkCard() {
  return (
    <Box
      bg="surface.card"
      borderRadius="soft-lg"
      boxShadow="soft"
      border="1px solid"
      borderColor="soft.border"
      p={5}
      mb={6}
    >
      <HStack mb={2} spacing={2} flexWrap="wrap">
        <Badge colorScheme="purple" fontSize="xs">SPACE Framework</Badge>
        <Badge colorScheme="blue" fontSize="xs">DevEx</Badge>
        <Badge colorScheme="orange" fontSize="xs">AI-Native · v1</Badge>
      </HStack>
      <Text fontSize="xs" color="gray.500" lineHeight="1.7">
        This panel uses the <strong>SPACE</strong> (Satisfaction, Performance, Activity,
        Communication, Efficiency) framework augmented with <strong>DevEx</strong>'s three
        AI-native dimensions (Feedback Loops, Cognitive Load, Flow State). Metrics are derived
        from Claude Code session telemetry — no git or CI integration required.{" "}
        <strong>AI-Effective Yield</strong> measures in-session accepted decisions per dollar;
        it will gain a merged-PR denominator once git correlation is wired (phase 2).
      </Text>
    </Box>
  );
}

export default function EfficiencyPage() {
  const { days } = useTimeRange();

  return (
    <Box p={8}>
      <Box mb={6}>
        <Heading size="lg" mb={1}>
          Developer Efficiency
        </Heading>
        <Text fontSize="sm" color="gray.500">
          SPACE + DevEx metrics for AI-assisted coding — beyond tokenmaxxing
        </Text>
      </Box>

      <FrameworkCard />

      <EfficiencyKpiCards days={days} />

      <HarnessConvergenceChart days={days} />

      <FeedbackLatencyChart days={days} />
    </Box>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npm run build 2>&1 | grep -E "error|Error" | grep -v "node_modules" | head -20`

Expected: No new errors from `efficiency/` files.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/efficiency/
git commit -m "feat(frontend): add EfficiencyPage with SPACE+DevEx framework card and charts"
```

---

## Task 10: Register route and navigation

**Files:**
- Modify: `frontend/src/app/router/viewRegistry.ts`
- Modify: `frontend/src/app/Layout.tsx`

- [ ] **Step 1: Add lazy import and route to `viewRegistry.ts`**

In `viewRegistry.ts`, add the lazy import after the last existing lazy import:

```typescript
const EfficiencyPage = lazy(
  () => import("@/views/efficiency/EfficiencyPage")
);
```

Then add to the `viewRegistry` array (after the `introspection` entry):

```typescript
{
  id: "efficiency",
  path: "/efficiency",
  component: EfficiencyPage,
  label: "Efficiency",
  nav: true,
},
```

- [ ] **Step 2: Add nav icon to `Layout.tsx`**

In `Layout.tsx`, add `FiActivity` to the import from `react-icons/fi`:

```typescript
// Before:
import {
  FiGrid,
  FiMessageSquare,
  FiCpu,
  FiBarChart2,
  FiServer,
  FiTrendingUp,
  FiSearch,
} from "react-icons/fi";

// After:
import {
  FiGrid,
  FiMessageSquare,
  FiCpu,
  FiBarChart2,
  FiServer,
  FiTrendingUp,
  FiSearch,
  FiActivity,
} from "react-icons/fi";
```

Then add `efficiency` to the `NAV_ICONS` record:

```typescript
const NAV_ICONS: Record<string, React.ElementType> = {
  "mcp-servers": FiServer,
  dashboard: FiGrid,
  sessions: FiMessageSquare,
  "mcp-tools": FiCpu,
  kpis: FiTrendingUp,
  platform: FiBarChart2,
  introspection: FiSearch,
  efficiency: FiActivity,   // ← add this line
};
```

- [ ] **Step 3: Final build check**

Run: `cd frontend && npm run build 2>&1 | tail -5`

Expected: `✓ built in X.Xs` with no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/router/viewRegistry.ts frontend/src/app/Layout.tsx
git commit -m "feat(frontend): register Efficiency route and nav icon"
```

---

## Self-Review

### Spec coverage check

| Requirement | Covered by |
|---|---|
| AI-Effective Yield (AEY) | Task 1 `build_aey_overview`, Task 3 `/efficiency/aey`, Task 6 `EfficiencyKpiCards` |
| Cognitive Load Index (CLi) | Task 1 `build_cognitive_load_index`, Task 3 `/efficiency/cognitive-load`, Task 6 |
| Feedback Loop Latency p50/p95 | Task 1 `build_feedback_latency`, Task 3 `/efficiency/feedback-latency`, Task 7 `FeedbackLatencyChart` |
| Harness Convergence Score (trend) | Task 1 `build_harness_convergence`, Task 3 `/efficiency/harness-convergence`, Task 8 `HarnessConvergenceChart` |
| Rework Ratio | Task 1 `build_rework_ratio`, Task 3 `/efficiency/rework-ratio`, Task 6 `EfficiencyKpiCards` |
| SPACE+DevEx framework context | Task 9 `FrameworkCard` |
| AEY labeled "in-session" with phase-2 callout | Task 6 tooltip text + Task 9 FrameworkCard |
| Composite tooltips showing formula inputs | Task 6 tooltips for CLi and Rework Ratio |
| Nav registration | Task 10 |
| DAB-compliant (no bespoke API artifacts) | All — no new pipelines, tables, or direct API calls in this v1 scope |
| No `@chakra-ui/icons` | All components use Chakra `Tooltip`, react-icons/fi, no icon imports from `@chakra-ui/icons` |

### Placeholder scan

No TBD, TODO, or "implement later" present. All steps have complete code blocks.

### Type consistency

- `EfficiencyFeedbackTool.tool_name` matches `tool_name` in SQL `GROUP BY tool_name`
- `EfficiencyConvergencePoint.date` matches SQL alias `session_date AS date`
- `EfficiencyConvergencePoint.avg_convergence_score` matches SQL alias exactly
- `EfficiencyAey.cost_per_accepted_decision` matches SQL alias exactly
- `EfficiencyCognitiveLoad.cognitive_load_index` matches SQL alias exactly
- `EfficiencyReworkRatio.avg_rework_ratio` matches SQL alias exactly
- All hooks use `useQuery<T>` where `T` matches the exact return shape of their router endpoint
