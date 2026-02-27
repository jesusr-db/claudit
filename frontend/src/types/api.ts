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

export interface AiGatewayModelStat {
  model: string;
  endpoint_name: string;
  api_type: string;
  call_count: string;
  success_count: string;
  error_count: string;
  avg_latency_ms: string;
  p50_latency_ms: string;
  p95_latency_ms: string;
  avg_ttfb_ms: string;
  total_input_tokens: string;
  total_output_tokens: string;
  total_tokens: string;
  total_cache_read_tokens: string | null;
  total_cache_creation_tokens: string | null;
}

export interface AiGatewayDaily {
  request_date: string;
  total_requests: string;
  succeeded: string;
  failed: string;
  avg_latency_ms: string;
  avg_ttfb_ms: string;
  p95_latency_ms: string;
  total_tokens: string;
}

export interface AiGatewayError {
  model: string;
  endpoint_name: string;
  status_code: string;
  error_count: string;
  avg_latency_ms: string;
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
