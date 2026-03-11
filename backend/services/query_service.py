from typing import Optional, List

from backend.config import settings


class QueryService:
    """Builds SQL queries against OTEL source tables directly."""

    SERVICE_NAME = "claude-code"

    # Methods that return PostgreSQL queries (for PgExecutor)
    PG_METHODS = {
        'build_sessions_list_query', 'build_session_detail_query',
        'build_session_timeline_query', 'build_prompt_events_query',
        'build_token_usage_query', 'build_cost_usage_query',
        'build_tool_stats_query', 'build_error_stats_query',
        'build_api_performance_query', 'build_tool_performance_query',
        'build_tool_recent_calls_query', 'build_turnaround_summary',
        'build_turnaround_by_session', 'build_summary_query',
    }

    # Methods that return Databricks SQL queries (for SqlExecutor)
    SQL_METHODS = {
        'build_billing_daily_query', 'build_billing_summary_query',
        'build_query_history_stats_query', 'build_query_history_daily_query',
        'build_ai_gateway_model_stats_query', 'build_ai_gateway_daily_query',
        'build_ai_gateway_errors_query',
    }

    def __init__(self):
        pass  # Uses settings directly

    @property
    def logs_table(self) -> str:
        return settings.otel_logs_table  # "zerobus_otel_logs"

    @property
    def metrics_table(self) -> str:
        return settings.otel_metrics_table  # "zerobus_otel_metrics"

    @property
    def service_filter(self) -> str:
        """Filter otel_logs rows to only the claude-code service."""
        return f"resource_attributes->>'service.name' = '{self.SERVICE_NAME}'"

    @staticmethod
    def _days_filter(days: Optional[float]) -> str:
        """Return a SQL AND clause for time filtering, or empty string."""
        if days is None:
            return ""
        if days < 1:
            hours = max(int(days * 24), 1)
            return f"AND (attributes->>'event.timestamp')::timestamp >= CURRENT_TIMESTAMP - interval '{hours} hours'"
        return f"AND (attributes->>'event.timestamp')::date >= current_date - interval '{int(days)} days'"

    def build_sessions_list_query(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
        days: Optional[float] = None,
    ) -> str:
        conditions = [self.service_filter]
        if user_id:
            conditions.append(f"attributes->>'user.id' = '{user_id}'")
        if days is not None:
            if days < 1:
                hours = max(int(days * 24), 1)
                conditions.append(
                    f"(attributes->>'event.timestamp')::timestamp >= CURRENT_TIMESTAMP - interval '{hours} hours'"
                )
            else:
                int_days = int(days)
                conditions.append(
                    f"(attributes->>'event.timestamp')::date >= current_date - interval '{int_days} days'"
                )

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            WITH session_stats AS (
                SELECT
                    attributes->>'session.id' as session_id,
                    attributes->>'user.id' as user_id,
                    MIN(attributes->>'event.timestamp') as start_time,
                    MAX(attributes->>'event.timestamp') as end_time,
                    COUNT(*) as event_count,
                    COUNT(DISTINCT attributes->>'prompt.id') as prompt_count,
                    COUNT(CASE WHEN attributes->>'event.name' IN ('tool_decision', 'tool_result') THEN 1 END) as tool_calls,
                    COUNT(CASE WHEN attributes->>'event.name' = 'api_error' THEN 1 END) as errors,
                    SUM(CASE WHEN attributes->>'event.name' = 'api_request'
                        THEN (attributes->>'cost_usd')::double precision ELSE 0 END) as total_cost_usd,
                    SUM(CASE WHEN attributes->>'event.name' = 'api_request'
                        THEN (attributes->>'input_tokens')::bigint ELSE 0 END) as total_input_tokens,
                    SUM(CASE WHEN attributes->>'event.name' = 'api_request'
                        THEN (attributes->>'output_tokens')::bigint ELSE 0 END) as total_output_tokens,
                    SUM(CASE WHEN attributes->>'event.name' = 'api_request'
                        THEN (attributes->>'cache_read_tokens')::bigint ELSE 0 END) as total_cache_read_tokens,
                    MIN(CASE WHEN attributes->>'event.name' = 'user_prompt'
                        THEN attributes->>'prompt' END) as first_prompt
                FROM {self.logs_table}
                {where}
                GROUP BY attributes->>'session.id', attributes->>'user.id'
            )
            SELECT * FROM session_stats
            ORDER BY start_time DESC
            LIMIT {limit}
            OFFSET {offset}
        """.strip()

    def build_session_detail_query(self, session_id: str) -> str:
        return f"""
            SELECT
                attributes->>'session.id' as session_id,
                attributes->>'user.id' as user_id,
                MIN(attributes->>'event.timestamp') as start_time,
                MAX(attributes->>'event.timestamp') as end_time,
                COUNT(*) as event_count,
                COUNT(DISTINCT attributes->>'prompt.id') as prompt_count,
                COUNT(CASE WHEN attributes->>'event.name' IN ('tool_decision', 'tool_result') THEN 1 END) as tool_calls,
                COUNT(CASE WHEN attributes->>'event.name' = 'api_error' THEN 1 END) as errors,
                SUM(CASE WHEN attributes->>'event.name' = 'api_request'
                    THEN (attributes->>'cost_usd')::double precision ELSE 0 END) as total_cost_usd
            FROM {self.logs_table}
            WHERE {self.service_filter}
              AND attributes->>'session.id' = '{session_id}'
            GROUP BY attributes->>'session.id', attributes->>'user.id'
        """.strip()

    def build_session_timeline_query(
        self,
        session_id: str,
        event_names: Optional[List[str]] = None,
    ) -> str:
        conditions = [self.service_filter, f"attributes->>'session.id' = '{session_id}'"]

        if event_names:
            names_str = ", ".join(f"'{n}'" for n in event_names)
            conditions.append(f"attributes->>'event.name' IN ({names_str})")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes->>'event.name' as event_name,
                attributes->>'event.timestamp' as timestamp,
                (attributes->>'event.sequence')::int as sequence,
                attributes->>'session.id' as session_id,
                attributes->>'prompt.id' as prompt_id,
                attributes->>'user.id' as user_id,
                attributes->>'tool_name' as tool_name,
                attributes->>'model' as model,
                attributes->>'duration_ms' as duration_ms,
                attributes->>'cost_usd' as cost_usd,
                attributes->>'input_tokens' as input_tokens,
                attributes->>'output_tokens' as output_tokens,
                attributes->>'cache_read_tokens' as cache_read_tokens,
                attributes->>'cache_creation_tokens' as cache_creation_tokens,
                attributes->>'error' as error,
                attributes->>'status_code' as status_code,
                attributes->>'success' as success,
                attributes->>'decision' as decision,
                attributes->>'source' as source,
                attributes->>'prompt' as prompt,
                attributes->>'prompt_length' as prompt_length,
                attributes->>'tool_result_size_bytes' as tool_result_size_bytes,
                attributes->>'speed' as speed
            FROM {self.logs_table}
            {where}
            ORDER BY (attributes->>'event.sequence')::int ASC
        """.strip()

    def build_prompt_events_query(self, session_id: str, prompt_id: str) -> str:
        return f"""
            SELECT
                attributes->>'event.name' as event_name,
                attributes->>'event.timestamp' as timestamp,
                (attributes->>'event.sequence')::int as sequence,
                attributes->>'session.id' as session_id,
                attributes->>'prompt.id' as prompt_id,
                attributes->>'tool_name' as tool_name,
                attributes->>'model' as model,
                attributes->>'duration_ms' as duration_ms,
                attributes->>'cost_usd' as cost_usd,
                attributes->>'input_tokens' as input_tokens,
                attributes->>'output_tokens' as output_tokens,
                attributes->>'cache_read_tokens' as cache_read_tokens,
                attributes->>'cache_creation_tokens' as cache_creation_tokens,
                attributes->>'error' as error,
                attributes->>'status_code' as status_code,
                attributes->>'success' as success,
                attributes->>'decision' as decision,
                attributes->>'source' as source,
                attributes->>'prompt' as prompt,
                attributes->>'tool_result_size_bytes' as tool_result_size_bytes,
                attributes->>'tool_parameters' as tool_parameters
            FROM {self.logs_table}
            WHERE {self.service_filter}
              AND attributes->>'session.id' = '{session_id}'
              AND attributes->>'prompt.id' = '{prompt_id}'
            ORDER BY (attributes->>'event.sequence')::int ASC
        """.strip()

    def build_token_usage_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = ["name = 'claude_code.token.usage'"]
        if session_id:
            conditions.append(f"sum_attributes->>'session.id' = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                sum_attributes->>'session.id' as session_id,
                sum_attributes->>'model' as model,
                sum_attributes->>'type' as token_type,
                sum_value as value,
                sum_start_time_unix_nano,
                sum_time_unix_nano
            FROM {self.metrics_table}
            {where}
            ORDER BY sum_time_unix_nano DESC
        """.strip()

    def build_cost_usage_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = ["name = 'claude_code.cost.usage'"]
        if session_id:
            conditions.append(f"sum_attributes->>'session.id' = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                sum_attributes->>'session.id' as session_id,
                sum_attributes->>'model' as model,
                sum_value as cost_usd,
                sum_start_time_unix_nano,
                sum_time_unix_nano
            FROM {self.metrics_table}
            {where}
            ORDER BY sum_time_unix_nano DESC
        """.strip()

    def build_tool_stats_query(
        self,
        session_id: Optional[str] = None,
        mcp_only: bool = False,
    ) -> str:
        conditions = [self.service_filter, "attributes->>'event.name' = 'tool_result'"]
        if session_id:
            conditions.append(f"attributes->>'session.id' = '{session_id}'")
        if mcp_only:
            conditions.append("attributes->>'tool_name' LIKE 'mcp\\_%'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes->>'tool_name' as tool_name,
                COUNT(*) as call_count,
                AVG((attributes->>'duration_ms')::double precision) as avg_duration_ms,
                SUM(CASE WHEN attributes->>'success' = 'true' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN attributes->>'success' = 'false' THEN 1 ELSE 0 END) as failure_count,
                SUM((attributes->>'tool_result_size_bytes')::bigint) as total_result_bytes
            FROM {self.logs_table}
            {where}
            GROUP BY attributes->>'tool_name'
            ORDER BY call_count DESC
        """.strip()

    def build_error_stats_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = [self.service_filter, "attributes->>'event.name' = 'api_error'"]
        if session_id:
            conditions.append(f"attributes->>'session.id' = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes->>'model' as model,
                attributes->>'status_code' as status_code,
                attributes->>'error' as error,
                COUNT(*) as error_count,
                AVG((attributes->>'duration_ms')::double precision) as avg_duration_ms
            FROM {self.logs_table}
            {where}
            GROUP BY attributes->>'model', attributes->>'status_code', attributes->>'error'
            ORDER BY error_count DESC
        """.strip()

    def build_api_performance_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = [self.service_filter, "attributes->>'event.name' = 'api_request'"]
        if session_id:
            conditions.append(f"attributes->>'session.id' = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes->>'model' as model,
                COUNT(*) as request_count,
                AVG((attributes->>'duration_ms')::double precision) as avg_duration_ms,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (attributes->>'duration_ms')::double precision) as p50_duration_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY (attributes->>'duration_ms')::double precision) as p95_duration_ms,
                SUM((attributes->>'input_tokens')::bigint) as total_input_tokens,
                SUM((attributes->>'output_tokens')::bigint) as total_output_tokens,
                SUM((attributes->>'cache_read_tokens')::bigint) as total_cache_read_tokens,
                SUM((attributes->>'cost_usd')::double precision) as total_cost_usd
            FROM {self.logs_table}
            {where}
            GROUP BY attributes->>'model'
        """.strip()

    def build_tool_performance_query(self, days: Optional[float] = None) -> str:
        """All tools with latency percentiles and success rates."""
        return f"""
            SELECT
                attributes->>'tool_name' as tool_name,
                COUNT(*) as call_count,
                SUM(CASE WHEN attributes->>'success' = 'true' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN attributes->>'success' = 'false' THEN 1 ELSE 0 END) as failure_count,
                ROUND(100.0 * SUM(CASE WHEN attributes->>'success' = 'true' THEN 1 ELSE 0 END) / COUNT(*), 1) as success_rate,
                ROUND(AVG((attributes->>'duration_ms')::double precision), 0) as avg_duration_ms,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY (attributes->>'duration_ms')::double precision), 0) as p50_duration_ms,
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY (attributes->>'duration_ms')::double precision), 0) as p95_duration_ms,
                ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY (attributes->>'duration_ms')::double precision), 0) as p99_duration_ms,
                SUM((attributes->>'tool_result_size_bytes')::bigint) as total_result_bytes
            FROM {self.logs_table}
            WHERE {self.service_filter}
              AND attributes->>'event.name' = 'tool_result'
              {self._days_filter(days)}
            GROUP BY attributes->>'tool_name'
            ORDER BY call_count DESC
        """.strip()

    def build_tool_recent_calls_query(self, tool_name: str, limit: int = 50) -> str:
        """Recent individual calls for a specific tool."""
        return f"""
            SELECT
                attributes->>'event.timestamp' as timestamp,
                attributes->>'tool_name' as tool_name,
                attributes->>'session.id' as session_id,
                attributes->>'prompt.id' as prompt_id,
                attributes->>'duration_ms' as duration_ms,
                attributes->>'success' as success,
                attributes->>'tool_result_size_bytes' as result_size_bytes
            FROM {self.logs_table}
            WHERE {self.service_filter}
              AND attributes->>'event.name' = 'tool_result'
              AND attributes->>'tool_name' = '{tool_name}'
            ORDER BY attributes->>'event.timestamp' DESC
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

    @staticmethod
    def _ai_gw_time_filter(days: float) -> str:
        """Time filter for system.ai_gateway.usage queries."""
        if days < 1:
            minutes = max(int(days * 24 * 60), 5)
            return f"event_time >= CURRENT_TIMESTAMP() - INTERVAL {minutes} MINUTES"
        return f"event_time >= current_date() - {int(days)}"

    def build_ai_gateway_model_stats_query(self, days: float = 7) -> str:
        """Per-model performance from system.ai_gateway.usage."""
        time_filter = self._ai_gw_time_filter(days)
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
            WHERE {time_filter}
            GROUP BY destination_model, endpoint_name, api_type
            ORDER BY call_count DESC
        """.strip()

    def build_ai_gateway_daily_query(self, days: float = 7) -> str:
        """Time-bucketed AI Gateway volume and latency."""
        time_filter = self._ai_gw_time_filter(days)
        if days < 1:
            # 5-minute buckets
            return f"""
                SELECT
                    CONCAT(
                        DATE_FORMAT(event_time, 'yyyy-MM-dd HH:'),
                        LPAD(CAST(FLOOR(MINUTE(event_time) / 5) * 5 AS STRING), 2, '0')
                    ) as request_date,
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) as succeeded,
                    SUM(CASE WHEN status_code != 200 THEN 1 ELSE 0 END) as failed,
                    ROUND(AVG(latency_ms), 0) as avg_latency_ms,
                    ROUND(AVG(time_to_first_byte_ms), 0) as avg_ttfb_ms,
                    ROUND(PERCENTILE(CAST(latency_ms AS DOUBLE), 0.95), 0) as p95_latency_ms,
                    SUM(total_tokens) as total_tokens
                FROM system.ai_gateway.usage
                WHERE {time_filter}
                GROUP BY 1
                ORDER BY request_date ASC
            """.strip()
        elif days <= 1:
            # Hourly buckets
            return f"""
                SELECT
                    DATE_FORMAT(event_time, 'yyyy-MM-dd HH:00') as request_date,
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN status_code = 200 THEN 1 ELSE 0 END) as succeeded,
                    SUM(CASE WHEN status_code != 200 THEN 1 ELSE 0 END) as failed,
                    ROUND(AVG(latency_ms), 0) as avg_latency_ms,
                    ROUND(AVG(time_to_first_byte_ms), 0) as avg_ttfb_ms,
                    ROUND(PERCENTILE(CAST(latency_ms AS DOUBLE), 0.95), 0) as p95_latency_ms,
                    SUM(total_tokens) as total_tokens
                FROM system.ai_gateway.usage
                WHERE {time_filter}
                GROUP BY DATE_FORMAT(event_time, 'yyyy-MM-dd HH:00')
                ORDER BY request_date ASC
            """.strip()
        else:
            # Daily buckets
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
                WHERE {time_filter}
                GROUP BY DATE(event_time)
                ORDER BY request_date DESC
            """.strip()

    def build_ai_gateway_errors_query(self, days: float = 7) -> str:
        """AI Gateway errors by model and status code."""
        time_filter = self._ai_gw_time_filter(days)
        return f"""
            SELECT
                destination_model as model,
                endpoint_name,
                status_code,
                COUNT(*) as error_count,
                ROUND(AVG(latency_ms), 0) as avg_latency_ms
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              AND status_code != 200
            GROUP BY destination_model, endpoint_name, status_code
            ORDER BY error_count DESC
        """.strip()

    # ── OTEL Queries ──

    def build_turnaround_summary(self) -> str:
        """Aggregate turnaround stats across all sessions."""
        return f"""
            WITH prompts AS (
                SELECT
                    attributes->>'session.id' as session_id,
                    attributes->>'prompt.id' as prompt_id,
                    attributes->>'event.timestamp' as prompt_ts
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes->>'event.name' = 'user_prompt'
            ),
            prompt_events AS (
                SELECT
                    p.session_id,
                    p.prompt_id,
                    p.prompt_ts,
                    COUNT(*) as events_in_prompt,
                    COUNT(CASE WHEN l.attributes->>'event.name' = 'api_request' THEN 1 END) as api_calls,
                    COUNT(CASE WHEN l.attributes->>'event.name' = 'tool_result' THEN 1 END) as tool_calls,
                    MAX(l.attributes->>'event.timestamp') as last_agent_event
                FROM prompts p
                LEFT JOIN {self.logs_table} l
                    ON p.session_id = l.attributes->>'session.id'
                    AND p.prompt_id = l.attributes->>'prompt.id'
                    AND l.attributes->>'event.name' != 'user_prompt'
                    AND l.resource_attributes->>'service.name' = '{self.SERVICE_NAME}'
                GROUP BY p.session_id, p.prompt_id, p.prompt_ts
            ),
            with_durations AS (
                SELECT *,
                    ROUND(EXTRACT(EPOCH FROM last_agent_event::timestamp)
                         - EXTRACT(EPOCH FROM prompt_ts::timestamp), 0) as agent_work_sec
                FROM prompt_events
                WHERE last_agent_event IS NOT NULL
            )
            SELECT
                COUNT(DISTINCT session_id) as total_sessions,
                COUNT(*) as total_prompts,
                ROUND(AVG(agent_work_sec), 1) as avg_turnaround_sec,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY agent_work_sec), 1) as p50_turnaround_sec,
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY agent_work_sec), 1) as p95_turnaround_sec,
                ROUND(MAX(agent_work_sec), 0) as max_turnaround_sec,
                ROUND(AVG(api_calls), 1) as avg_api_calls,
                ROUND(AVG(tool_calls), 1) as avg_tool_calls,
                ROUND(AVG(events_in_prompt), 1) as avg_events_per_prompt
            FROM with_durations
        """.strip()

    def build_turnaround_by_session(
        self,
        session_id: Optional[str] = None,
        limit: int = 500,
    ) -> str:
        """Per-prompt turnaround data. Optional session_id filter."""
        session_filter = (
            f"AND attributes->>'session.id' = '{session_id}'" if session_id else ""
        )
        return f"""
            WITH prompts AS (
                SELECT
                    attributes->>'session.id' as session_id,
                    attributes->>'prompt.id' as prompt_id,
                    attributes->>'event.timestamp' as prompt_ts,
                    LEFT(attributes->>'prompt', 80) as prompt_preview
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes->>'event.name' = 'user_prompt'
                  {session_filter}
            ),
            prompt_events AS (
                SELECT
                    p.session_id,
                    p.prompt_id,
                    p.prompt_ts,
                    p.prompt_preview,
                    COUNT(*) as events_in_prompt,
                    COUNT(CASE WHEN l.attributes->>'event.name' = 'api_request' THEN 1 END) as api_calls,
                    COUNT(CASE WHEN l.attributes->>'event.name' = 'tool_result' THEN 1 END) as tool_calls,
                    MAX(l.attributes->>'event.timestamp') as last_agent_event,
                    MAX(CASE WHEN l.attributes->>'tool_name' = 'AskUserQuestion' THEN 1 ELSE 0 END) as has_question,
                    MAX(CASE WHEN l.attributes->>'tool_name' = 'ExitPlanMode' THEN 1 ELSE 0 END) as has_plan_exit
                FROM prompts p
                LEFT JOIN {self.logs_table} l
                    ON p.session_id = l.attributes->>'session.id'
                    AND p.prompt_id = l.attributes->>'prompt.id'
                    AND l.attributes->>'event.name' != 'user_prompt'
                    AND l.resource_attributes->>'service.name' = '{self.SERVICE_NAME}'
                GROUP BY p.session_id, p.prompt_id, p.prompt_ts, p.prompt_preview
            )
            SELECT *,
                ROUND(EXTRACT(EPOCH FROM last_agent_event::timestamp)
                     - EXTRACT(EPOCH FROM prompt_ts::timestamp), 0) as agent_work_sec
            FROM prompt_events
            ORDER BY prompt_ts DESC
            LIMIT {limit}
        """.strip()

    def build_summary_query(self, days: Optional[float] = None) -> str:
        return f"""
            SELECT
                COUNT(DISTINCT attributes->>'session.id') as total_sessions,
                COUNT(DISTINCT attributes->>'user.id') as total_users,
                COUNT(*) as total_events,
                COUNT(CASE WHEN attributes->>'event.name' = 'user_prompt' THEN 1 END) as total_prompts,
                COUNT(CASE WHEN attributes->>'event.name' = 'api_request' THEN 1 END) as total_api_calls,
                COUNT(CASE WHEN attributes->>'event.name' = 'api_error' THEN 1 END) as total_errors,
                SUM(CASE WHEN attributes->>'event.name' = 'api_request'
                    THEN (attributes->>'cost_usd')::double precision ELSE 0 END) as total_cost_usd
            FROM {self.logs_table}
            WHERE {self.service_filter}
              {self._days_filter(days)}
        """.strip()
