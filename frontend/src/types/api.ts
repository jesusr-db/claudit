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
  tool_calls: string;
  errors: string;
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
