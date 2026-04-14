export type EventName =
  | "user_prompt"
  | "api_request"
  | "api_error"
  | "tool_decision"
  | "tool_result";

export interface SessionSummary {
  session_id: string;
  user_id: string;
  start_time: string;
  end_time: string | null;
  event_count: string;
  prompt_count: string;
  total_cost_usd: string;
  total_input_tokens: string;
  total_output_tokens: string;
  total_cache_read_tokens: string;
  tool_calls: string;
  errors: string;
  first_prompt: string | null;
}

export interface TimelineEvent {
  event_name: EventName;
  timestamp: string;
  sequence: number;
  session_id: string;
  prompt_id: string | null;
  user_id: string | null;
  tool_name: string | null;
  model: string | null;
  duration_ms: string | null;
  cost_usd: string | null;
  input_tokens: string | null;
  output_tokens: string | null;
  cache_read_tokens: string | null;
  cache_creation_tokens: string | null;
  error: string | null;
  status_code: string | null;
  success: string | null;
  decision: string | null;
  source: string | null;
  prompt: string | null;
  prompt_length: string | null;
  tool_result_size_bytes: string | null;
  speed: string | null;
}

export interface PromptEvent extends TimelineEvent {
  tool_parameters: string | null;
}

export interface ToolStat {
  tool_name: string;
  call_count: string;
  avg_duration_ms: string;
  success_count: string;
  failure_count: string;
  total_result_bytes: string;
}

export interface MetricsSummary {
  total_sessions: string;
  total_users: string;
  total_events: string;
  total_prompts: string;
  total_api_calls: string;
  total_errors: string;
  total_cost_usd: string;
}

export interface ErrorStat {
  model: string;
  status_code: string;
  error: string;
  error_count: string;
  avg_duration_ms: string;
}

export interface ToolPerformance {
  tool_name: string;
  call_count: string;
  success_count: string;
  failure_count: string;
  success_rate: string;
  avg_duration_ms: string;
  p50_duration_ms: string;
  p95_duration_ms: string;
  p99_duration_ms: string;
  total_result_bytes: string;
}

export interface BillingProduct {
  product: string;
  usage_unit: string;
  total_usage: string;
  record_count: string;
  active_days: string;
}

export interface BillingDaily {
  usage_date: string;
  product: string;
  sku_name: string;
  usage_unit: string;
  total_usage: string;
}

export interface QueryStats {
  client_application: string;
  execution_status: string;
  query_count: string;
  avg_total_ms: string;
  avg_exec_ms: string;
  avg_compile_ms: string;
  avg_queue_ms: string;
  total_rows_read: string;
  total_bytes_read: string;
}

export interface QueryDaily {
  query_date: string;
  total_queries: string;
  succeeded: string;
  failed: string;
  avg_duration_ms: string;
  p95_duration_ms: string;
  total_bytes_read: string;
}

export interface ToolCall {
  timestamp: string;
  tool_name: string;
  session_id: string;
  prompt_id: string | null;
  duration_ms: string;
  success: string;
  result_size_bytes: string;
}

// ── Turnaround Types ──

export interface TurnaroundSummary {
  total_sessions: string;
  total_prompts: string;
  avg_turnaround_sec: string;
  p50_turnaround_sec: string;
  p95_turnaround_sec: string;
  max_turnaround_sec: string;
  avg_api_calls: string;
  avg_tool_calls: string;
  avg_events_per_prompt: string;
}

export interface TurnaroundPrompt {
  session_id: string;
  prompt_id: string;
  prompt_ts: string;
  prompt_preview: string | null;
  events_in_prompt: string;
  api_calls: string;
  tool_calls: string;
  last_agent_event: string;
  has_question: string;
  has_plan_exit: string;
  agent_work_sec: string;
}

// ── MCP Server Types ──

export interface McpServerOverview {
  service_name: string;
  tool_count: string;
  total_spans: string;
  tool_spans: string;
  http_spans: string;
  total_log_entries: string;
}

export interface McpDetailToolCall {
  tool_name: string;
  status: string;
  total_calls: string;
}

export interface McpDetailToolLatency {
  tool_name: string;
  samples: string;
  avg_latency_ms: string;
  min_latency_ms: string;
  max_latency_ms: string;
}

export interface McpDetailHttpDuration {
  method: string;
  status_code: string;
  samples: string;
  avg_duration_ms: string;
  min_duration_ms: string;
  max_duration_ms: string;
}

export interface McpServerDetail {
  tool_calls: McpDetailToolCall[];
  tool_latency: McpDetailToolLatency[];
  http_duration: McpDetailHttpDuration[];
}

export interface McpToolStat {
  tool_name: string;
  call_count: string;
  success_count: string;
  failure_count: string;
  avg_duration_ms: string;
  p50_duration_ms: string;
  p95_duration_ms: string;
}

export interface McpToolTimeline {
  time_bucket: string;
  tool_name: string;
  call_count: string;
  avg_duration_ms: string;
  p95_duration_ms: string;
}

export interface McpHttpSummary {
  domain: string;
  method: string;
  status_code: string;
  call_count: string;
  avg_duration_ms: string;
  p95_duration_ms: string;
}

export interface McpHttpCall {
  timestamp: string;
  method: string;
  url: string;
  status_code: string;
  duration_ms: string;
}

export interface McpAuditEntry {
  timestamp: string;
  tool_name: string;
  status: string;
  duration_ms: string;
  trace_id: string;
}

export interface McpErrorEvent {
  timestamp: string;
  span_name: string;
  kind: string;
  status: string;
  status_message: string | null;
  http_status: string | null;
  duration_ms: string;
  trace_id: string;
}

export interface McpServerLog {
  timestamp: string;
  severity: string;
  body: string;
  attributes: string;
  tool_name?: string;
}

// ── KPI Types ──

export interface KpiCostOverview {
  total_cost: string;
  avg_cost_per_session: string;
  avg_cost_per_prompt: string;
  cache_hit_pct: string;
}

export interface KpiCostTrend {
  date: string;
  daily_cost: string;
  input_tokens: string;
  output_tokens: string;
  cache_read_tokens: string;
  request_count: string;
}

export interface KpiCostSession {
  session_id: string;
  total_cost: string;
  prompt_count: string;
  cache_hit_pct: string;
  cost_per_prompt: string;
  first_prompt: string | null;
  total_tokens: string;
}

export interface KpiModelCost {
  model: string;
  total_cost: string;
  request_count: string;
  avg_cost_per_call: string;
  avg_latency_ms: string;
  cache_hit_pct: string;
  total_input_tokens: string;
  total_output_tokens: string;
}

export interface KpiTokenWaste {
  session_id: string;
  prompt_id: string;
  input_tokens: string;
  output_tokens: string;
  cost_usd: string;
  model: string;
}

export interface KpiEffectivenessOverview {
  tool_success_rate: string;
  avg_tools_per_prompt: string;
  avg_api_calls_per_prompt: string;
  total_errors: string;
  total_prompts: string;
  total_tool_calls: string;
}

export interface KpiToolRetry {
  tool_name: string;
  retry_count: string;
  sessions_affected: string;
}

export interface KpiOrphanDecision {
  tool_name: string;
  orphan_count: string;
  sessions_affected: string;
}

export interface KpiErrorRecovery {
  model: string;
  recovery_count: string;
  total_errors: string;
  recovery_rate: string;
}

export interface KpiPromptComplexity {
  bucket: string;
  prompt_count: string;
  avg_agent_work_sec: string;
  avg_tool_calls: string;
  avg_api_calls: string;
}

export interface KpiFlowRow {
  section: "tool" | "connection" | "external_api";
  server_name: string;
  name: string;
  calls: string;
  avg_duration_ms: string;
  success: string | null;
  errors: string | null;
  extra: string | null; // UC audit events for connections
}

export interface KpiAuditEntry {
  connection_name: string;
  action_name: string;
  call_count: string;
  active_days: string;
  first_seen: string;
  last_seen: string;
  distinct_users: string;
}

// ── KPI Model Efficiency Types ──

export interface KpiModelMatrix {
  model: string;
  complexity: string;
  call_count: string;
  avg_cost_per_call: string;
  total_cost: string;
  avg_latency_ms: string;
  p50_latency_ms: string;
  p95_latency_ms: string;
  avg_output_tokens: string;
  tool_success_rate: string;
  error_count: string;
}

export interface KpiRightsizing {
  model: string;
  complexity: string;
  call_count: string;
  total_cost: string;
  avg_cost: string;
  downgrade_opportunity: string;
}

export interface KpiModelRecommendation {
  model: string;
  complexity: string;
  call_count: string;
  avg_cost: string;
  p50_latency: string;
  cost_rank: string;
  speed_rank: string;
  is_cost_winner: string;
  is_speed_winner: string;
}

export interface KpiRightsizingDetail {
  session_id: string;
  prompt_id: string;
  model: string;
  complexity: string;
  prompt_cost: string;
  api_calls: string;
  avg_latency_ms: string;
  total_output_tokens: string;
  downgrade_opportunity: string;
  prompt_preview: string | null;
}

export interface KpiSavingsRow {
  complexity: string;
  call_count: string;
  actual_cost: string;
  hypothetical_cost: string;
  potential_savings: string;
  savings_pct: string;
  cheapest_model: string;
}

export interface KpiBadges {
  cache_hit_pct: string;
  cost_trend_direction: string;
  tool_success_rate: string;
  avg_turnaround_sec: string;
}

// ── Introspection Types ──

export interface InsightCardOccurrence {
  label: string;
  event_seq: number;
}

export interface CrossSessionContext {
  count: number;
  total: number;
}

export interface InsightCard {
  type: 'skill_forgetting' | 'tool_retry' | 'context_drift' | 'inefficiency';
  severity: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  occurrences: InsightCardOccurrence[];
  root_cause: string;
  best_practices: string[];
  cross_session: CrossSessionContext | null;
}

export interface IntrospectionResult {
  session_id: string;
  analyzed_at: string;
  cards: InsightCard[];
  analysis_error: string | null;
}

export interface ActivityClassification {
  activity: string;
  prompt_count: string;
  total_cost: string;
  total_tokens: string;
}

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
