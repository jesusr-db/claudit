import { useQuery, useMutation } from "@tanstack/react-query";
import type {
  MetricsSummary,
  ToolStat,
  ErrorStat,
  SessionSummary,
  TimelineEvent,
  ToolPerformance,
  ToolCall,
  PromptEvent,
  BillingProduct,
  BillingDaily,
  QueryStats,
  QueryDaily,
  AiGatewayModelStat,
  AiGatewayDaily,
  AiGatewayError,
  TurnaroundSummary,
  TurnaroundPrompt,
  McpServerOverview,
  McpToolStat,
  McpToolTimeline,
  McpHttpSummary,
  McpHttpCall,
  McpAuditEntry,
  McpErrorEvent,
  McpServerLog,
  McpServerDetail,
  KpiCostOverview,
  KpiCostTrend,
  KpiCostSession,
  KpiModelCost,
  KpiTokenWaste,
  KpiEffectivenessOverview,
  KpiToolRetry,
  KpiOrphanDecision,
  KpiErrorRecovery,
  KpiPromptComplexity,
  KpiFlowRow,
  KpiAuditEntry as KpiAuditEntryType,
  KpiBadges,
  KpiModelMatrix,
  KpiRightsizing,
  KpiModelRecommendation,
  KpiSavingsRow,
  KpiRightsizingDetail,
  IntrospectionResult,
} from "@/types/api";

async function fetchJson<T>(url: string): Promise<T> {
  console.log(`[API] Fetching: ${url}`);
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    console.error(`[API] Error ${res.status} for ${url}:`, body);
    throw new Error(`API error: ${res.status}`);
  }
  const data = await res.json();
  console.log(`[API] Success: ${url}`, data);
  return data;
}

export function useSummary(days?: number) {
  const qs = days !== undefined ? `?days=${days}` : "";
  return useQuery<MetricsSummary>({
    queryKey: ["metrics", "summary", { days }],
    queryFn: () => fetchJson(`/api/v1/metrics/summary${qs}`),
  });
}

export function useToolStats(mcp_only = false) {
  return useQuery<{ tools: ToolStat[] }>({
    queryKey: ["metrics", "tools", { mcp_only }],
    queryFn: () =>
      fetchJson(`/api/v1/metrics/tools?mcp_only=${mcp_only}`),
  });
}

export function useErrorStats() {
  return useQuery<{ errors: ErrorStat[] }>({
    queryKey: ["metrics", "errors"],
    queryFn: () => fetchJson("/api/v1/metrics/errors"),
  });
}

export function useSessions(limit = 50, offset = 0, days?: number) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (days !== undefined) params.set("days", String(days));
  return useQuery<{ sessions: SessionSummary[] }>({
    queryKey: ["sessions", { limit, offset, days }],
    queryFn: () =>
      fetchJson(`/api/v1/sessions?${params.toString()}`),
  });
}

export function useSessionTimeline(
  sessionId: string,
  eventNames?: string[]
) {
  const params = new URLSearchParams();
  if (eventNames) {
    eventNames.forEach((n) => params.append("event_names", n));
  }
  const qs = params.toString() ? `?${params.toString()}` : "";
  return useQuery<{
    session_id: string;
    events: TimelineEvent[];
  }>({
    queryKey: ["sessions", sessionId, "timeline", eventNames],
    queryFn: () =>
      fetchJson(`/api/v1/sessions/${sessionId}/timeline${qs}`),
    enabled: !!sessionId,
  });
}

export function usePromptEvents(sessionId: string, promptId: string) {
  return useQuery<{
    session_id: string;
    prompt_id: string;
    events: PromptEvent[];
  }>({
    queryKey: ["sessions", sessionId, "prompts", promptId],
    queryFn: () =>
      fetchJson(`/api/v1/sessions/${sessionId}/prompts/${promptId}`),
    enabled: !!sessionId && !!promptId,
  });
}

export function useToolPerformance(days?: number) {
  const qs = days !== undefined ? `?days=${days}` : "";
  return useQuery<{ tools: ToolPerformance[] }>({
    queryKey: ["tools", "performance", { days }],
    queryFn: () => fetchJson(`/api/v1/tools/performance${qs}`),
  });
}

export function useToolRecentCalls(toolName: string, limit = 50) {
  return useQuery<{ tool_name: string; calls: ToolCall[] }>({
    queryKey: ["tools", toolName, "calls", { limit }],
    queryFn: () =>
      fetchJson(`/api/v1/tools/${encodeURIComponent(toolName)}/calls?limit=${limit}`),
    enabled: !!toolName,
  });
}

export function useBillingSummary(days = 30) {
  return useQuery<{ products: BillingProduct[]; days: number }>({
    queryKey: ["platform", "billing", "summary", { days }],
    queryFn: () => fetchJson(`/api/v1/platform/billing/summary?days=${days}`),
  });
}

export function useBillingDaily(days = 30) {
  return useQuery<{ daily: BillingDaily[]; days: number }>({
    queryKey: ["platform", "billing", "daily", { days }],
    queryFn: () => fetchJson(`/api/v1/platform/billing/daily?days=${days}`),
  });
}

export function useQueryStats(days = 7) {
  return useQuery<{ stats: QueryStats[]; days: number }>({
    queryKey: ["platform", "queries", "stats", { days }],
    queryFn: () => fetchJson(`/api/v1/platform/queries/stats?days=${days}`),
  });
}

export function useQueryDaily(days = 7) {
  return useQuery<{ daily: QueryDaily[]; days: number }>({
    queryKey: ["platform", "queries", "daily", { days }],
    queryFn: () => fetchJson(`/api/v1/platform/queries/daily?days=${days}`),
  });
}

export function useAiGatewayModels(days = 7) {
  return useQuery<{ models: AiGatewayModelStat[]; days: number }>({
    queryKey: ["platform", "ai-gateway", "models", { days }],
    queryFn: () => fetchJson(`/api/v1/platform/ai-gateway/models?days=${days}`),
  });
}

export function useAiGatewayDaily(days = 7) {
  return useQuery<{ daily: AiGatewayDaily[]; days: number }>({
    queryKey: ["platform", "ai-gateway", "daily", { days }],
    queryFn: () => fetchJson(`/api/v1/platform/ai-gateway/daily?days=${days}`),
  });
}

export function useAiGatewayErrors(days = 7) {
  return useQuery<{ errors: AiGatewayError[]; days: number }>({
    queryKey: ["platform", "ai-gateway", "errors", { days }],
    queryFn: () => fetchJson(`/api/v1/platform/ai-gateway/errors?days=${days}`),
  });
}

// ── Turnaround Hooks ──

export function useTurnaroundSummary() {
  return useQuery<TurnaroundSummary>({
    queryKey: ["sessions", "turnaround", "summary"],
    queryFn: () => fetchJson("/api/v1/sessions/turnaround/summary"),
  });
}

export function useTurnaroundDetail(sessionId?: string) {
  const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  return useQuery<{ prompts: TurnaroundPrompt[] }>({
    queryKey: ["sessions", "turnaround", "detail", { sessionId }],
    queryFn: () => fetchJson(`/api/v1/sessions/turnaround/detail${qs}`),
  });
}

// ── MCP Server Hooks ──

function mcpServerParams(server?: string, days?: number): URLSearchParams {
  const qs = new URLSearchParams();
  if (server) qs.set("server", server);
  if (days !== undefined) qs.set("days", String(days));
  return qs;
}

export function useMcpServerSummary(server?: string, days?: number) {
  const qs = mcpServerParams(server, days);
  return useQuery<{ servers: McpServerOverview[] }>({
    queryKey: ["mcp-servers", "summary", { server, days }],
    queryFn: () => fetchJson(`/api/v1/mcp-servers/summary?${qs.toString()}`),
  });
}

export function useMcpServerDetail(server?: string, days?: number) {
  const qs = mcpServerParams(server, days);
  return useQuery<McpServerDetail>({
    queryKey: ["mcp-servers", "detail", { server, days }],
    queryFn: () => fetchJson(`/api/v1/mcp-servers/detail?${qs.toString()}`),
  });
}

export function useMcpToolStats(server?: string, days?: number) {
  const qs = mcpServerParams(server, days);
  return useQuery<{ tools: McpToolStat[] }>({
    queryKey: ["mcp-servers", "tools", { server, days }],
    queryFn: () => fetchJson(`/api/v1/mcp-servers/tools?${qs.toString()}`),
  });
}

export function useMcpToolTimeline(server?: string, days?: number) {
  const qs = mcpServerParams(server, days);
  return useQuery<{ timeline: McpToolTimeline[] }>({
    queryKey: ["mcp-servers", "tools", "timeline", { server, days }],
    queryFn: () => fetchJson(`/api/v1/mcp-servers/tools/timeline?${qs.toString()}`),
  });
}

export function useMcpHttpSummary(server?: string, days?: number) {
  const qs = mcpServerParams(server, days);
  return useQuery<{ http: McpHttpSummary[] }>({
    queryKey: ["mcp-servers", "http", { server, days }],
    queryFn: () => fetchJson(`/api/v1/mcp-servers/http?${qs.toString()}`),
  });
}

export function useMcpHttpDetail(server?: string, limit = 200, days?: number) {
  const qs = mcpServerParams(server, days);
  qs.set("limit", String(limit));
  return useQuery<{ calls: McpHttpCall[] }>({
    queryKey: ["mcp-servers", "http", "detail", { server, limit, days }],
    queryFn: () => fetchJson(`/api/v1/mcp-servers/http/detail?${qs.toString()}`),
  });
}

export function useMcpAudit(server?: string, limit = 200, days?: number) {
  const qs = mcpServerParams(server, days);
  qs.set("limit", String(limit));
  return useQuery<{ invocations: McpAuditEntry[] }>({
    queryKey: ["mcp-servers", "audit", { server, limit, days }],
    queryFn: () => fetchJson(`/api/v1/mcp-servers/audit?${qs.toString()}`),
  });
}

export function useMcpErrors(server?: string, limit = 200, days?: number) {
  const qs = mcpServerParams(server, days);
  qs.set("limit", String(limit));
  return useQuery<{ errors: McpErrorEvent[] }>({
    queryKey: ["mcp-servers", "errors", { server, limit, days }],
    queryFn: () => fetchJson(`/api/v1/mcp-servers/errors?${qs.toString()}`),
  });
}

export function useMcpServerLogs(server?: string, limit = 200, days?: number) {
  const qs = mcpServerParams(server, days);
  qs.set("limit", String(limit));
  return useQuery<{ logs: McpServerLog[] }>({
    queryKey: ["mcp-servers", "logs", { server, limit, days }],
    queryFn: () => fetchJson(`/api/v1/mcp-servers/logs?${qs.toString()}`),
  });
}

// ── KPI Hooks ──

export function useKpiCostOverview(days = 30) {
  return useQuery<KpiCostOverview>({
    queryKey: ["kpis", "cost", "overview", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/cost/overview?days=${days}`),
  });
}

export function useKpiCostTrend(days = 30) {
  return useQuery<{ trend: KpiCostTrend[]; days: number }>({
    queryKey: ["kpis", "cost", "trend", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/cost/trend?days=${days}`),
  });
}

export function useKpiCostSessions(days = 30) {
  return useQuery<{ sessions: KpiCostSession[]; days: number }>({
    queryKey: ["kpis", "cost", "sessions", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/cost/sessions?days=${days}`),
  });
}

export function useKpiModelComparison(days = 30) {
  return useQuery<{ models: KpiModelCost[]; days: number }>({
    queryKey: ["kpis", "cost", "models", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/cost/models?days=${days}`),
  });
}

export function useKpiTokenWaste(days = 30) {
  return useQuery<{ waste: KpiTokenWaste[]; days: number }>({
    queryKey: ["kpis", "cost", "waste", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/cost/waste?days=${days}`),
  });
}

export function useKpiEffectivenessOverview(days = 30) {
  return useQuery<KpiEffectivenessOverview>({
    queryKey: ["kpis", "effectiveness", "overview", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/effectiveness/overview?days=${days}`),
  });
}

export function useKpiToolRetries(days = 30) {
  return useQuery<{ retries: KpiToolRetry[]; days: number }>({
    queryKey: ["kpis", "effectiveness", "retries", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/effectiveness/retries?days=${days}`),
  });
}

export function useKpiOrphanDecisions(days = 30) {
  return useQuery<{ orphans: KpiOrphanDecision[]; days: number }>({
    queryKey: ["kpis", "effectiveness", "orphans", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/effectiveness/orphans?days=${days}`),
  });
}

export function useKpiErrorRecovery(days = 30) {
  return useQuery<{ recovery: KpiErrorRecovery[]; days: number }>({
    queryKey: ["kpis", "effectiveness", "recovery", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/effectiveness/recovery?days=${days}`),
  });
}

export function useKpiPromptComplexity(days = 30) {
  return useQuery<{ complexity: KpiPromptComplexity[]; days: number }>({
    queryKey: ["kpis", "effectiveness", "complexity", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/effectiveness/complexity?days=${days}`),
  });
}

export function useKpiFlowSummary(days = 30) {
  return useQuery<{ flows: KpiFlowRow[]; days: number }>({
    queryKey: ["kpis", "flow", "summary", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/flow/summary?days=${days}`),
  });
}

export function useKpiAuditCorrelation(days = 7) {
  return useQuery<{ audit: KpiAuditEntryType[]; days: number }>({
    queryKey: ["kpis", "flow", "audit", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/flow/audit?days=${days}`),
  });
}

// ── KPI Efficiency Hooks ──

export function useKpiEfficiencyMatrix(days = 30) {
  return useQuery<{ matrix: KpiModelMatrix[]; days: number }>({
    queryKey: ["kpis", "efficiency", "matrix", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/efficiency/matrix?days=${days}`),
  });
}

export function useKpiRightsizing(days = 30) {
  return useQuery<{ opportunities: KpiRightsizing[]; days: number }>({
    queryKey: ["kpis", "efficiency", "rightsizing", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/efficiency/rightsizing?days=${days}`),
  });
}

export function useKpiRightsizingDetails(days = 30, model?: string, complexity?: string) {
  const params = new URLSearchParams();
  params.set("days", String(days));
  if (model) params.set("model", model);
  if (complexity) params.set("complexity", complexity);
  return useQuery<{ details: KpiRightsizingDetail[]; days: number; model: string | null; complexity: string | null }>({
    queryKey: ["kpis", "efficiency", "rightsizing", "details", { days, model, complexity }],
    queryFn: () => fetchJson(`/api/v1/kpis/efficiency/rightsizing/details?${params.toString()}`),
    enabled: !!model || !!complexity,
  });
}

export function useKpiModelRecommendations(days = 30) {
  return useQuery<{ recommendations: KpiModelRecommendation[]; days: number }>({
    queryKey: ["kpis", "efficiency", "recommendations", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/efficiency/recommendations?days=${days}`),
  });
}

export function useKpiSavingsCalculator(days = 30) {
  return useQuery<{ savings: KpiSavingsRow[]; days: number }>({
    queryKey: ["kpis", "efficiency", "savings", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/efficiency/savings?days=${days}`),
  });
}

export function useKpiBadges(days = 30) {
  return useQuery<KpiBadges>({
    queryKey: ["kpis", "badges", { days }],
    queryFn: () => fetchJson(`/api/v1/kpis/badges?days=${days}`),
  });
}

// ── Introspection Hooks ──

export function useIntrospectionAnalyze() {
  return useMutation<
    IntrospectionResult,
    Error,
    { session_id: string; cross_session_days?: number }
  >({
    mutationFn: async (params) => {
      const res = await fetch("/api/v1/introspection/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`API error: ${res.status} ${body}`);
      }
      return res.json();
    },
  });
}
