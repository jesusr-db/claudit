import { useQuery } from "@tanstack/react-query";
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

export function useSummary() {
  return useQuery<MetricsSummary>({
    queryKey: ["metrics", "summary"],
    queryFn: () => fetchJson("/api/v1/metrics/summary"),
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

export function useSessions(limit = 50, offset = 0) {
  return useQuery<{ sessions: SessionSummary[] }>({
    queryKey: ["sessions", { limit, offset }],
    queryFn: () =>
      fetchJson(`/api/v1/sessions?limit=${limit}&offset=${offset}`),
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

export function useToolPerformance() {
  return useQuery<{ tools: ToolPerformance[] }>({
    queryKey: ["tools", "performance"],
    queryFn: () => fetchJson("/api/v1/tools/performance"),
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
