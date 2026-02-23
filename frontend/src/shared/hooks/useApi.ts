import { useQuery } from "@tanstack/react-query";
import type { MetricsSummary, ToolStat, ErrorStat, SessionSummary, TimelineEvent } from "@/types/api";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
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
