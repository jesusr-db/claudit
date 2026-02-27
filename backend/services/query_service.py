from typing import Optional, List


class QueryService:
    """Builds SQL queries against OTEL source tables directly."""

    def __init__(self, catalog: str, schema: str):
        self.catalog = catalog
        self.schema = schema

    SERVICE_NAME = "claude-code"

    @property
    def logs_table(self) -> str:
        return f"{self.catalog}.{self.schema}.otel_logs"

    @property
    def metrics_table(self) -> str:
        return f"{self.catalog}.{self.schema}.otel_metrics"

    @property
    def service_filter(self) -> str:
        """Filter otel_logs rows to only the claude-code service."""
        return f"resource.attributes['service.name'] = '{self.SERVICE_NAME}'"

    def build_sessions_list_query(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
    ) -> str:
        conditions = [self.service_filter]
        if user_id:
            conditions.append(f"attributes['user.id'] = '{user_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            WITH session_stats AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['user.id'] as user_id,
                    MIN(attributes['event.timestamp']) as start_time,
                    MAX(attributes['event.timestamp']) as end_time,
                    COUNT(*) as event_count,
                    COUNT(DISTINCT attributes['prompt.id']) as prompt_count,
                    COUNT(CASE WHEN attributes['event.name'] IN ('tool_decision', 'tool_result') THEN 1 END) as tool_calls,
                    COUNT(CASE WHEN attributes['event.name'] = 'api_error' THEN 1 END) as errors,
                    SUM(CASE WHEN attributes['event.name'] = 'api_request'
                        THEN CAST(attributes['cost_usd'] AS DOUBLE) ELSE 0 END) as total_cost_usd,
                    SUM(CASE WHEN attributes['event.name'] = 'api_request'
                        THEN CAST(attributes['input_tokens'] AS BIGINT) ELSE 0 END) as total_input_tokens,
                    SUM(CASE WHEN attributes['event.name'] = 'api_request'
                        THEN CAST(attributes['output_tokens'] AS BIGINT) ELSE 0 END) as total_output_tokens,
                    SUM(CASE WHEN attributes['event.name'] = 'api_request'
                        THEN CAST(attributes['cache_read_tokens'] AS BIGINT) ELSE 0 END) as total_cache_read_tokens,
                    MIN(CASE WHEN attributes['event.name'] = 'user_prompt'
                        THEN attributes['prompt'] END) as first_prompt
                FROM {self.logs_table}
                {where}
                GROUP BY attributes['session.id'], attributes['user.id']
            )
            SELECT * FROM session_stats
            ORDER BY start_time DESC
            LIMIT {limit}
            OFFSET {offset}
        """.strip()

    def build_session_detail_query(self, session_id: str) -> str:
        return f"""
            SELECT
                attributes['session.id'] as session_id,
                attributes['user.id'] as user_id,
                MIN(attributes['event.timestamp']) as start_time,
                MAX(attributes['event.timestamp']) as end_time,
                COUNT(*) as event_count,
                COUNT(DISTINCT attributes['prompt.id']) as prompt_count,
                COUNT(CASE WHEN attributes['event.name'] IN ('tool_decision', 'tool_result') THEN 1 END) as tool_calls,
                COUNT(CASE WHEN attributes['event.name'] = 'api_error' THEN 1 END) as errors,
                SUM(CASE WHEN attributes['event.name'] = 'api_request'
                    THEN CAST(attributes['cost_usd'] AS DOUBLE) ELSE 0 END) as total_cost_usd
            FROM {self.logs_table}
            WHERE {self.service_filter}
              AND attributes['session.id'] = '{session_id}'
            GROUP BY attributes['session.id'], attributes['user.id']
        """.strip()

    def build_session_timeline_query(
        self,
        session_id: str,
        event_names: Optional[List[str]] = None,
    ) -> str:
        conditions = [self.service_filter, f"attributes['session.id'] = '{session_id}'"]

        if event_names:
            names_str = ", ".join(f"'{n}'" for n in event_names)
            conditions.append(f"attributes['event.name'] IN ({names_str})")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes['event.name'] as event_name,
                attributes['event.timestamp'] as timestamp,
                CAST(attributes['event.sequence'] AS INT) as sequence,
                attributes['session.id'] as session_id,
                attributes['prompt.id'] as prompt_id,
                attributes['user.id'] as user_id,
                attributes['tool_name'] as tool_name,
                attributes['model'] as model,
                attributes['duration_ms'] as duration_ms,
                attributes['cost_usd'] as cost_usd,
                attributes['input_tokens'] as input_tokens,
                attributes['output_tokens'] as output_tokens,
                attributes['cache_read_tokens'] as cache_read_tokens,
                attributes['cache_creation_tokens'] as cache_creation_tokens,
                attributes['error'] as error,
                attributes['status_code'] as status_code,
                attributes['success'] as success,
                attributes['decision'] as decision,
                attributes['source'] as source,
                attributes['prompt'] as prompt,
                attributes['prompt_length'] as prompt_length,
                attributes['tool_result_size_bytes'] as tool_result_size_bytes,
                attributes['speed'] as speed
            FROM {self.logs_table}
            {where}
            ORDER BY CAST(attributes['event.sequence'] AS INT) ASC
        """.strip()

    def build_prompt_events_query(self, session_id: str, prompt_id: str) -> str:
        return f"""
            SELECT
                attributes['event.name'] as event_name,
                attributes['event.timestamp'] as timestamp,
                CAST(attributes['event.sequence'] AS INT) as sequence,
                attributes['session.id'] as session_id,
                attributes['prompt.id'] as prompt_id,
                attributes['tool_name'] as tool_name,
                attributes['model'] as model,
                attributes['duration_ms'] as duration_ms,
                attributes['cost_usd'] as cost_usd,
                attributes['input_tokens'] as input_tokens,
                attributes['output_tokens'] as output_tokens,
                attributes['cache_read_tokens'] as cache_read_tokens,
                attributes['cache_creation_tokens'] as cache_creation_tokens,
                attributes['error'] as error,
                attributes['status_code'] as status_code,
                attributes['success'] as success,
                attributes['decision'] as decision,
                attributes['source'] as source,
                attributes['prompt'] as prompt,
                attributes['tool_result_size_bytes'] as tool_result_size_bytes,
                attributes['tool_parameters'] as tool_parameters
            FROM {self.logs_table}
            WHERE {self.service_filter}
              AND attributes['session.id'] = '{session_id}'
              AND attributes['prompt.id'] = '{prompt_id}'
            ORDER BY CAST(attributes['event.sequence'] AS INT) ASC
        """.strip()

    def build_token_usage_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = ["name = 'claude_code.token.usage'"]
        if session_id:
            conditions.append(f"sum.attributes['session.id'] = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                sum.attributes['session.id'] as session_id,
                sum.attributes['model'] as model,
                sum.attributes['type'] as token_type,
                sum.value as value,
                sum.start_time_unix_nano,
                sum.time_unix_nano
            FROM {self.metrics_table}
            {where}
            ORDER BY sum.time_unix_nano DESC
        """.strip()

    def build_cost_usage_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = ["name = 'claude_code.cost.usage'"]
        if session_id:
            conditions.append(f"sum.attributes['session.id'] = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                sum.attributes['session.id'] as session_id,
                sum.attributes['model'] as model,
                sum.value as cost_usd,
                sum.start_time_unix_nano,
                sum.time_unix_nano
            FROM {self.metrics_table}
            {where}
            ORDER BY sum.time_unix_nano DESC
        """.strip()

    def build_tool_stats_query(
        self,
        session_id: Optional[str] = None,
        mcp_only: bool = False,
    ) -> str:
        conditions = [self.service_filter, "attributes['event.name'] = 'tool_result'"]
        if session_id:
            conditions.append(f"attributes['session.id'] = '{session_id}'")
        if mcp_only:
            conditions.append("attributes['tool_name'] LIKE 'mcp!_!_%' ESCAPE '!'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes['tool_name'] as tool_name,
                COUNT(*) as call_count,
                AVG(CAST(attributes['duration_ms'] AS DOUBLE)) as avg_duration_ms,
                SUM(CASE WHEN attributes['success'] = 'true' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN attributes['success'] = 'false' THEN 1 ELSE 0 END) as failure_count,
                SUM(CAST(attributes['tool_result_size_bytes'] AS BIGINT)) as total_result_bytes
            FROM {self.logs_table}
            {where}
            GROUP BY attributes['tool_name']
            ORDER BY call_count DESC
        """.strip()

    def build_error_stats_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = [self.service_filter, "attributes['event.name'] = 'api_error'"]
        if session_id:
            conditions.append(f"attributes['session.id'] = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes['model'] as model,
                attributes['status_code'] as status_code,
                attributes['error'] as error,
                COUNT(*) as error_count,
                AVG(CAST(attributes['duration_ms'] AS DOUBLE)) as avg_duration_ms
            FROM {self.logs_table}
            {where}
            GROUP BY attributes['model'], attributes['status_code'], attributes['error']
            ORDER BY error_count DESC
        """.strip()

    def build_api_performance_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = [self.service_filter, "attributes['event.name'] = 'api_request'"]
        if session_id:
            conditions.append(f"attributes['session.id'] = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes['model'] as model,
                COUNT(*) as request_count,
                AVG(CAST(attributes['duration_ms'] AS DOUBLE)) as avg_duration_ms,
                PERCENTILE(CAST(attributes['duration_ms'] AS DOUBLE), 0.5) as p50_duration_ms,
                PERCENTILE(CAST(attributes['duration_ms'] AS DOUBLE), 0.95) as p95_duration_ms,
                SUM(CAST(attributes['input_tokens'] AS BIGINT)) as total_input_tokens,
                SUM(CAST(attributes['output_tokens'] AS BIGINT)) as total_output_tokens,
                SUM(CAST(attributes['cache_read_tokens'] AS BIGINT)) as total_cache_read_tokens,
                SUM(CAST(attributes['cost_usd'] AS DOUBLE)) as total_cost_usd
            FROM {self.logs_table}
            {where}
            GROUP BY attributes['model']
        """.strip()

    def build_tool_performance_query(self) -> str:
        """All tools with latency percentiles and success rates."""
        return f"""
            SELECT
                attributes['tool_name'] as tool_name,
                COUNT(*) as call_count,
                SUM(CASE WHEN attributes['success'] = 'true' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN attributes['success'] = 'false' THEN 1 ELSE 0 END) as failure_count,
                ROUND(100.0 * SUM(CASE WHEN attributes['success'] = 'true' THEN 1 ELSE 0 END) / COUNT(*), 1) as success_rate,
                ROUND(AVG(CAST(attributes['duration_ms'] AS DOUBLE)), 0) as avg_duration_ms,
                ROUND(PERCENTILE(CAST(attributes['duration_ms'] AS DOUBLE), 0.5), 0) as p50_duration_ms,
                ROUND(PERCENTILE(CAST(attributes['duration_ms'] AS DOUBLE), 0.95), 0) as p95_duration_ms,
                ROUND(PERCENTILE(CAST(attributes['duration_ms'] AS DOUBLE), 0.99), 0) as p99_duration_ms,
                SUM(CAST(attributes['tool_result_size_bytes'] AS BIGINT)) as total_result_bytes
            FROM {self.logs_table}
            WHERE {self.service_filter}
              AND attributes['event.name'] = 'tool_result'
            GROUP BY attributes['tool_name']
            ORDER BY call_count DESC
        """.strip()

    def build_tool_recent_calls_query(self, tool_name: str, limit: int = 50) -> str:
        """Recent individual calls for a specific tool."""
        return f"""
            SELECT
                attributes['event.timestamp'] as timestamp,
                attributes['tool_name'] as tool_name,
                attributes['session.id'] as session_id,
                attributes['prompt.id'] as prompt_id,
                attributes['duration_ms'] as duration_ms,
                attributes['success'] as success,
                attributes['tool_result_size_bytes'] as result_size_bytes
            FROM {self.logs_table}
            WHERE {self.service_filter}
              AND attributes['event.name'] = 'tool_result'
              AND attributes['tool_name'] = '{tool_name}'
            ORDER BY attributes['event.timestamp'] DESC
            LIMIT {limit}
        """.strip()

    # ── System Tables ──

    def build_billing_daily_query(self, days: int = 30) -> str:
        """Daily DBU consumption by product, from system.billing.usage."""
        return f"""
            SELECT
                usage_date,
                billing_origin_product as product,
                sku_name,
                usage_unit,
                ROUND(SUM(usage_quantity), 2) as total_usage
            FROM system.billing.usage
            WHERE usage_date >= current_date() - {days}
              AND usage_unit = 'DBU'
            GROUP BY usage_date, billing_origin_product, sku_name, usage_unit
            ORDER BY usage_date DESC, total_usage DESC
        """.strip()

    def build_billing_summary_query(self, days: int = 30) -> str:
        """Aggregate billing by product for the period."""
        return f"""
            SELECT
                billing_origin_product as product,
                usage_unit,
                ROUND(SUM(usage_quantity), 2) as total_usage,
                COUNT(*) as record_count,
                COUNT(DISTINCT usage_date) as active_days
            FROM system.billing.usage
            WHERE usage_date >= current_date() - {days}
              AND usage_unit = 'DBU'
            GROUP BY billing_origin_product, usage_unit
            ORDER BY total_usage DESC
        """.strip()

    def build_query_history_stats_query(self, days: int = 7) -> str:
        """Query performance by client application from system.query.history."""
        return f"""
            SELECT
                COALESCE(NULLIF(client_application, ''), 'unknown') as client_application,
                execution_status,
                COUNT(*) as query_count,
                ROUND(AVG(total_duration_ms), 0) as avg_total_ms,
                ROUND(AVG(execution_duration_ms), 0) as avg_exec_ms,
                ROUND(AVG(compilation_duration_ms), 0) as avg_compile_ms,
                ROUND(AVG(waiting_at_capacity_duration_ms), 0) as avg_queue_ms,
                SUM(read_rows) as total_rows_read,
                SUM(read_bytes) as total_bytes_read
            FROM system.query.history
            WHERE start_time >= current_date() - {days}
            GROUP BY COALESCE(NULLIF(client_application, ''), 'unknown'), execution_status
            ORDER BY query_count DESC
            LIMIT 25
        """.strip()

    def build_query_history_daily_query(self, days: int = 7) -> str:
        """Daily query volume and performance from system.query.history."""
        return f"""
            SELECT
                DATE(start_time) as query_date,
                COUNT(*) as total_queries,
                SUM(CASE WHEN execution_status = 'FINISHED' THEN 1 ELSE 0 END) as succeeded,
                SUM(CASE WHEN execution_status = 'FAILED' THEN 1 ELSE 0 END) as failed,
                ROUND(AVG(total_duration_ms), 0) as avg_duration_ms,
                ROUND(PERCENTILE(CAST(total_duration_ms AS DOUBLE), 0.95), 0) as p95_duration_ms,
                SUM(read_bytes) as total_bytes_read
            FROM system.query.history
            WHERE start_time >= current_date() - {days}
            GROUP BY DATE(start_time)
            ORDER BY query_date DESC
        """.strip()

    def build_ai_gateway_model_stats_query(self, days: int = 7) -> str:
        """Per-model performance from system.ai_gateway.usage."""
        return f"""
            SELECT
                destination_model as model,
                endpoint_name,
                api_type,
                COUNT(*) as call_count,
                SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN status_code != 200 THEN 1 ELSE 0 END) as error_count,
                ROUND(AVG(latency_ms), 0) as avg_latency_ms,
                ROUND(PERCENTILE(CAST(latency_ms AS DOUBLE), 0.5), 0) as p50_latency_ms,
                ROUND(PERCENTILE(CAST(latency_ms AS DOUBLE), 0.95), 0) as p95_latency_ms,
                ROUND(AVG(time_to_first_byte_ms), 0) as avg_ttfb_ms,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(token_details.cache_read_input_tokens) as total_cache_read_tokens,
                SUM(token_details.cache_creation_input_tokens) as total_cache_creation_tokens
            FROM system.ai_gateway.usage
            WHERE event_time >= current_date() - {days}
            GROUP BY destination_model, endpoint_name, api_type
            ORDER BY call_count DESC
        """.strip()

    def build_ai_gateway_daily_query(self, days: int = 7) -> str:
        """Daily AI Gateway volume and latency."""
        return f"""
            SELECT
                DATE(event_time) as request_date,
                COUNT(*) as total_requests,
                SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) as succeeded,
                SUM(CASE WHEN status_code != 200 THEN 1 ELSE 0 END) as failed,
                ROUND(AVG(latency_ms), 0) as avg_latency_ms,
                ROUND(AVG(time_to_first_byte_ms), 0) as avg_ttfb_ms,
                ROUND(PERCENTILE(CAST(latency_ms AS DOUBLE), 0.95), 0) as p95_latency_ms,
                SUM(total_tokens) as total_tokens
            FROM system.ai_gateway.usage
            WHERE event_time >= current_date() - {days}
            GROUP BY DATE(event_time)
            ORDER BY request_date DESC
        """.strip()

    def build_ai_gateway_errors_query(self, days: int = 7) -> str:
        """AI Gateway errors by model and status code."""
        return f"""
            SELECT
                destination_model as model,
                endpoint_name,
                status_code,
                COUNT(*) as error_count,
                ROUND(AVG(latency_ms), 0) as avg_latency_ms
            FROM system.ai_gateway.usage
            WHERE event_time >= current_date() - {days}
              AND status_code != 200
            GROUP BY destination_model, endpoint_name, status_code
            ORDER BY error_count DESC
        """.strip()

    # ── OTEL Queries ──

    def build_summary_query(self) -> str:
        return f"""
            SELECT
                COUNT(DISTINCT attributes['session.id']) as total_sessions,
                COUNT(DISTINCT attributes['user.id']) as total_users,
                COUNT(*) as total_events,
                COUNT(CASE WHEN attributes['event.name'] = 'user_prompt' THEN 1 END) as total_prompts,
                COUNT(CASE WHEN attributes['event.name'] = 'api_request' THEN 1 END) as total_api_calls,
                COUNT(CASE WHEN attributes['event.name'] = 'api_error' THEN 1 END) as total_errors,
                SUM(CASE WHEN attributes['event.name'] = 'api_request'
                    THEN CAST(attributes['cost_usd'] AS DOUBLE) ELSE 0 END) as total_cost_usd
            FROM {self.logs_table}
            WHERE {self.service_filter}
        """.strip()
