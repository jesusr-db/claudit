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

    def __init__(self):
        pass  # Uses settings directly

    @property
    def logs_mat(self) -> str:
        return settings.otel_logs_mat_table

    @property
    def metrics_table(self) -> str:
        return settings.otel_metrics_table  # "zerobus_otel_metrics"

    @property
    def service_filter(self) -> str:
        """Filter otel_logs rows to only the claude-code service."""
        return f"service_name = '{self.SERVICE_NAME}'"

    @staticmethod
    def _days_filter(days: Optional[float]) -> str:
        """Return a SQL AND clause for time filtering, or empty string."""
        if days is None:
            return ""
        if days < 1:
            hours = max(int(days * 24), 1)
            return f"AND event_ts >= CURRENT_TIMESTAMP - interval '{hours} hours'"
        return f"AND event_ts::date >= current_date - interval '{int(days)} days'"

    def build_sessions_list_query(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
        days: Optional[float] = None,
    ) -> str:
        conditions = [self.service_filter]
        if user_id:
            conditions.append(f"user_id = '{user_id}'")
        if days is not None:
            if days < 1:
                hours = max(int(days * 24), 1)
                conditions.append(
                    f"event_ts >= CURRENT_TIMESTAMP - interval '{hours} hours'"
                )
            else:
                int_days = int(days)
                conditions.append(
                    f"event_ts::date >= current_date - interval '{int_days} days'"
                )

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            WITH session_stats AS (
                SELECT
                    session_id,
                    user_id,
                    MIN(event_ts) as start_time,
                    MAX(event_ts) as end_time,
                    COUNT(*) as event_count,
                    COUNT(DISTINCT prompt_id) as prompt_count,
                    COUNT(CASE WHEN event_name IN ('tool_decision', 'tool_result') THEN 1 END) as tool_calls,
                    COUNT(CASE WHEN event_name = 'api_error' THEN 1 END) as errors,
                    SUM(CASE WHEN event_name = 'api_request'
                        THEN cost_usd ELSE 0 END) as total_cost_usd,
                    SUM(CASE WHEN event_name = 'api_request'
                        THEN input_tokens ELSE 0 END) as total_input_tokens,
                    SUM(CASE WHEN event_name = 'api_request'
                        THEN output_tokens ELSE 0 END) as total_output_tokens,
                    SUM(CASE WHEN event_name = 'api_request'
                        THEN cache_read_tokens ELSE 0 END) as total_cache_read_tokens,
                    MIN(CASE WHEN event_name = 'user_prompt'
                        THEN prompt_text END) as first_prompt
                FROM {self.logs_mat}
                {where}
                GROUP BY session_id, user_id
            )
            SELECT * FROM session_stats
            ORDER BY start_time DESC
            LIMIT {limit}
            OFFSET {offset}
        """.strip()

    def build_session_detail_query(self, session_id: str) -> str:
        return f"""
            SELECT
                session_id,
                user_id,
                MIN(event_ts) as start_time,
                MAX(event_ts) as end_time,
                COUNT(*) as event_count,
                COUNT(DISTINCT prompt_id) as prompt_count,
                COUNT(CASE WHEN event_name IN ('tool_decision', 'tool_result') THEN 1 END) as tool_calls,
                COUNT(CASE WHEN event_name = 'api_error' THEN 1 END) as errors,
                SUM(CASE WHEN event_name = 'api_request'
                    THEN cost_usd ELSE 0 END) as total_cost_usd
            FROM {self.logs_mat}
            WHERE {self.service_filter}
              AND session_id = '{session_id}'
            GROUP BY session_id, user_id
        """.strip()

    def build_session_timeline_query(
        self,
        session_id: str,
        event_names: Optional[List[str]] = None,
    ) -> str:
        conditions = [self.service_filter, f"session_id = '{session_id}'"]

        if event_names:
            names_str = ", ".join(f"'{n}'" for n in event_names)
            conditions.append(f"event_name IN ({names_str})")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                event_name,
                event_ts as timestamp,
                event_seq as sequence,
                session_id,
                prompt_id,
                user_id,
                tool_name,
                model,
                duration_ms,
                cost_usd,
                input_tokens,
                output_tokens,
                cache_read_tokens,
                cache_creation_tokens,
                error,
                status_code,
                success,
                decision,
                source,
                prompt_text as prompt,
                prompt_length,
                tool_result_size_bytes,
                speed
            FROM {self.logs_mat}
            {where}
            ORDER BY event_seq ASC
        """.strip()

    def build_prompt_events_query(self, session_id: str, prompt_id: str) -> str:
        return f"""
            SELECT
                event_name,
                event_ts as timestamp,
                event_seq as sequence,
                session_id,
                prompt_id,
                tool_name,
                model,
                duration_ms,
                cost_usd,
                input_tokens,
                output_tokens,
                cache_read_tokens,
                cache_creation_tokens,
                error,
                status_code,
                success,
                decision,
                source,
                prompt_text as prompt,
                tool_result_size_bytes,
                tool_parameters
            FROM {self.logs_mat}
            WHERE {self.service_filter}
              AND session_id = '{session_id}'
              AND prompt_id = '{prompt_id}'
            ORDER BY event_seq ASC
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
        conditions = [self.service_filter, "event_name = 'tool_result'"]
        if session_id:
            conditions.append(f"session_id = '{session_id}'")
        if mcp_only:
            conditions.append("tool_name LIKE 'mcp\\_%'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                tool_name,
                COUNT(*) as call_count,
                AVG(duration_ms) as avg_duration_ms,
                SUM(CASE WHEN success = 'true' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN success = 'false' THEN 1 ELSE 0 END) as failure_count,
                SUM(tool_result_size_bytes) as total_result_bytes
            FROM {self.logs_mat}
            {where}
            GROUP BY tool_name
            ORDER BY call_count DESC
        """.strip()

    def build_error_stats_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = [self.service_filter, "event_name = 'api_error'"]
        if session_id:
            conditions.append(f"session_id = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                model,
                status_code,
                error,
                COUNT(*) as error_count,
                AVG(duration_ms) as avg_duration_ms
            FROM {self.logs_mat}
            {where}
            GROUP BY model, status_code, error
            ORDER BY error_count DESC
        """.strip()

    def build_api_performance_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = [self.service_filter, "event_name = 'api_request'"]
        if session_id:
            conditions.append(f"session_id = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                model,
                COUNT(*) as request_count,
                AVG(duration_ms) as avg_duration_ms,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms) as p50_duration_ms,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(cache_read_tokens) as total_cache_read_tokens,
                SUM(cost_usd) as total_cost_usd
            FROM {self.logs_mat}
            {where}
            GROUP BY model
        """.strip()

    def build_tool_performance_query(self, days: Optional[float] = None) -> str:
        """All tools with latency percentiles and success rates."""
        return f"""
            SELECT
                tool_name,
                COUNT(*) as call_count,
                SUM(CASE WHEN success = 'true' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN success = 'false' THEN 1 ELSE 0 END) as failure_count,
                ROUND((100.0 * SUM(CASE WHEN success = 'true' THEN 1 ELSE 0 END) / COUNT(*))::numeric, 1) as success_rate,
                ROUND(AVG(duration_ms)::numeric, 0) as avg_duration_ms,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms)::numeric, 0) as p50_duration_ms,
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 0) as p95_duration_ms,
                ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms)::numeric, 0) as p99_duration_ms,
                SUM(tool_result_size_bytes) as total_result_bytes
            FROM {self.logs_mat}
            WHERE {self.service_filter}
              AND event_name = 'tool_result'
              {self._days_filter(days)}
            GROUP BY tool_name
            ORDER BY call_count DESC
        """.strip()

    def build_tool_recent_calls_query(self, tool_name: str, limit: int = 50) -> str:
        """Recent individual calls for a specific tool."""
        return f"""
            SELECT
                event_ts as timestamp,
                tool_name,
                session_id,
                prompt_id,
                duration_ms,
                success,
                tool_result_size_bytes as result_size_bytes
            FROM {self.logs_mat}
            WHERE {self.service_filter}
              AND event_name = 'tool_result'
              AND tool_name = '{tool_name}'
            ORDER BY event_ts DESC
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

    @staticmethod
    def _ai_gw_agent_classification() -> str:
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

    def _ai_gw_endpoint_filter(self, endpoint: str | None) -> str:
        if endpoint:
            safe = endpoint.replace("'", "''")
            return f"AND endpoint_name = '{safe}'"
        return ""

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

    # ── AI Gateway Dashboard Queries ──

    def build_ai_gateway_endpoints_query(self, days: float = 7) -> str:
        """List distinct AI Gateway endpoints."""
        time_filter = self._ai_gw_time_filter(days)
        return f"""
            SELECT DISTINCT endpoint_name
            FROM system.ai_gateway.usage
            WHERE {time_filter}
            ORDER BY endpoint_name
        """.strip()

    # -- Overview Tab --

    def build_ai_gateway_overview_kpis_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                COUNT(*) as total_requests,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COUNT(DISTINCT requester) as total_unique_users
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
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
            WHERE {time_filter}
              {ep_filter}
            GROUP BY DATE(event_time)
            ORDER BY date ASC
        """.strip()

    def build_ai_gateway_overview_top_endpoints_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                endpoint_name,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COUNT(*) as requests
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
            GROUP BY endpoint_name
            ORDER BY total_tokens DESC
            LIMIT 10
        """.strip()

    def build_ai_gateway_overview_top_models_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                destination_model as model,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COUNT(*) as requests
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
            GROUP BY destination_model
            ORDER BY total_tokens DESC
            LIMIT 10
        """.strip()

    def build_ai_gateway_overview_top_users_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                requester,
                COUNT(*) as requests,
                COALESCE(SUM(total_tokens), 0) as total_tokens
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
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
                WHERE {time_filter}
                  {ep_filter}
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
            WHERE {time_filter}
              {ep_filter}
            GROUP BY DATE(u.event_time), u.endpoint_name
            ORDER BY date ASC, u.endpoint_name
        """.strip()

    # -- Performance Tab --

    def build_ai_gateway_performance_kpis_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                ROUND(PERCENTILE(CAST(latency_ms AS DOUBLE), 0.5), 0) as median_latency_ms,
                ROUND(PERCENTILE(CAST(time_to_first_byte_ms AS DOUBLE), 0.5), 0) as median_ttfb_ms,
                SUM(CASE WHEN status_code != 200 THEN 1 ELSE 0 END) as error_count
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
        """.strip()

    def build_ai_gateway_performance_latency_by_endpoint_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            WITH top_eps AS (
                SELECT endpoint_name
                FROM system.ai_gateway.usage
                WHERE {time_filter}
                  {ep_filter}
                GROUP BY endpoint_name
                ORDER BY COUNT(*) DESC
                LIMIT 5
            )
            SELECT
                DATE(u.event_time) as date,
                u.endpoint_name,
                ROUND(PERCENTILE(CAST(u.latency_ms AS DOUBLE), 0.5), 0) as median_latency_ms
            FROM system.ai_gateway.usage u
            JOIN top_eps t ON u.endpoint_name = t.endpoint_name
            WHERE {time_filter}
              {ep_filter}
            GROUP BY DATE(u.event_time), u.endpoint_name
            ORDER BY date ASC, u.endpoint_name
        """.strip()

    def build_ai_gateway_performance_status_codes_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                status_code,
                COUNT(*) as count
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
            GROUP BY status_code
            ORDER BY count DESC
        """.strip()

    def build_ai_gateway_performance_tpm_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            WITH top_eps AS (
                SELECT endpoint_name
                FROM system.ai_gateway.usage
                WHERE {time_filter}
                  {ep_filter}
                GROUP BY endpoint_name
                ORDER BY COUNT(*) DESC
                LIMIT 5
            )
            SELECT
                DATE(u.event_time) as date,
                u.endpoint_name,
                ROUND(SUM(u.total_tokens) / GREATEST(COUNT(DISTINCT HOUR(u.event_time)), 1) / 60.0, 0) as tpm
            FROM system.ai_gateway.usage u
            JOIN top_eps t ON u.endpoint_name = t.endpoint_name
            WHERE {time_filter}
              {ep_filter}
            GROUP BY DATE(u.event_time), u.endpoint_name
            ORDER BY date ASC, u.endpoint_name
        """.strip()

    def build_ai_gateway_performance_ttfb_by_endpoint_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            WITH top_eps AS (
                SELECT endpoint_name
                FROM system.ai_gateway.usage
                WHERE {time_filter}
                  {ep_filter}
                GROUP BY endpoint_name
                ORDER BY COUNT(*) DESC
                LIMIT 5
            )
            SELECT
                DATE(u.event_time) as date,
                u.endpoint_name,
                ROUND(PERCENTILE(CAST(u.time_to_first_byte_ms AS DOUBLE), 0.5), 0) as median_ttfb_ms
            FROM system.ai_gateway.usage u
            JOIN top_eps t ON u.endpoint_name = t.endpoint_name
            WHERE {time_filter}
              {ep_filter}
            GROUP BY DATE(u.event_time), u.endpoint_name
            ORDER BY date ASC, u.endpoint_name
        """.strip()

    def build_ai_gateway_performance_ttft_loss_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            WITH top_eps AS (
                SELECT endpoint_name
                FROM system.ai_gateway.usage
                WHERE {time_filter}
                  {ep_filter}
                GROUP BY endpoint_name
                ORDER BY COUNT(*) DESC
                LIMIT 5
            )
            SELECT
                u.endpoint_name,
                ROUND(AVG(u.time_to_first_byte_ms), 0) as avg_ttfb_ms,
                ROUND(AVG(u.latency_ms - u.time_to_first_byte_ms), 0) as avg_generation_ms
            FROM system.ai_gateway.usage u
            JOIN top_eps t ON u.endpoint_name = t.endpoint_name
            WHERE {time_filter}
              {ep_filter}
            GROUP BY u.endpoint_name
            ORDER BY u.endpoint_name
        """.strip()

    def build_ai_gateway_performance_errors_by_endpoint_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                endpoint_name,
                COUNT(*) as error_count
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              AND status_code != 200
              {ep_filter}
            GROUP BY endpoint_name
            ORDER BY error_count DESC
            LIMIT 10
        """.strip()

    # -- Usage Tab --

    def build_ai_gateway_usage_kpis_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                COUNT(DISTINCT endpoint_name) as total_endpoints,
                COUNT(DISTINCT requester) as active_users
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
        """.strip()

    def build_ai_gateway_usage_tokens_by_endpoint_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            WITH top_eps AS (
                SELECT endpoint_name
                FROM system.ai_gateway.usage
                WHERE {time_filter}
                  {ep_filter}
                GROUP BY endpoint_name
                ORDER BY COALESCE(SUM(total_tokens), 0) DESC
                LIMIT 7
            )
            SELECT
                DATE(u.event_time) as date,
                u.endpoint_name,
                COALESCE(SUM(u.total_tokens), 0) as tokens
            FROM system.ai_gateway.usage u
            JOIN top_eps t ON u.endpoint_name = t.endpoint_name
            WHERE {time_filter}
              {ep_filter}
            GROUP BY DATE(u.event_time), u.endpoint_name
            ORDER BY date ASC, u.endpoint_name
        """.strip()

    def build_ai_gateway_usage_tokens_by_model_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            WITH top_models AS (
                SELECT destination_model
                FROM system.ai_gateway.usage
                WHERE {time_filter}
                  {ep_filter}
                GROUP BY destination_model
                ORDER BY COALESCE(SUM(total_tokens), 0) DESC
                LIMIT 7
            )
            SELECT
                DATE(u.event_time) as date,
                u.destination_model as model,
                COALESCE(SUM(u.total_tokens), 0) as tokens
            FROM system.ai_gateway.usage u
            JOIN top_models t ON u.destination_model = t.destination_model
            WHERE {time_filter}
              {ep_filter}
            GROUP BY DATE(u.event_time), u.destination_model
            ORDER BY date ASC, model
        """.strip()

    def build_ai_gateway_usage_tokens_by_user_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            WITH top_users AS (
                SELECT requester
                FROM system.ai_gateway.usage
                WHERE {time_filter}
                  {ep_filter}
                GROUP BY requester
                ORDER BY COALESCE(SUM(total_tokens), 0) DESC
                LIMIT 5
            )
            SELECT
                DATE(u.event_time) as date,
                u.requester,
                COALESCE(SUM(u.total_tokens), 0) as tokens
            FROM system.ai_gateway.usage u
            JOIN top_users t ON u.requester = t.requester
            WHERE {time_filter}
              {ep_filter}
            GROUP BY DATE(u.event_time), u.requester
            ORDER BY date ASC, u.requester
        """.strip()

    def build_ai_gateway_usage_input_output_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                DATE(event_time) as date,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
            GROUP BY DATE(event_time)
            ORDER BY date ASC
        """.strip()

    def build_ai_gateway_usage_cache_hit_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                endpoint_name,
                COALESCE(SUM(token_details.cache_read_input_tokens), 0) as cache_read_tokens,
                COALESCE(SUM(input_tokens), 0) as total_input_tokens,
                ROUND(COALESCE(SUM(token_details.cache_read_input_tokens), 0) * 100.0 / SUM(input_tokens), 1) as cache_hit_pct
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
            GROUP BY endpoint_name
            HAVING SUM(input_tokens) > 0
            ORDER BY cache_hit_pct DESC
            LIMIT 10
        """.strip()

    # -- Coding Agents Tab --

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
            WHERE {time_filter}
              {ep_filter}
              {agent_filter}
            GROUP BY coding_agent
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
                WHERE {time_filter}
                  {ep_filter}
                  {agent_filter}
                GROUP BY coding_agent
                ORDER BY COUNT(*) DESC
                LIMIT 7
            )
            SELECT
                DATE(u.event_time) as date,
                {agent_cls} as coding_agent,
                COUNT(*) as requests,
                COALESCE(SUM(u.total_tokens), 0) as tokens,
                ROUND(AVG(u.latency_ms), 0) as avg_latency_ms
            FROM system.ai_gateway.usage u
            WHERE {time_filter}
              {ep_filter}
              {agent_filter}
              AND {agent_cls} IN (SELECT coding_agent FROM top_agents)
            GROUP BY DATE(u.event_time), coding_agent
            ORDER BY date ASC, coding_agent
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
            SELECT
                endpoint_name,
                COUNT(*) as requests
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
              {agent_filter}
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
            SELECT
                {agent_cls} as coding_agent,
                destination_model as model,
                COALESCE(SUM(total_tokens), 0) as tokens
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
              {agent_filter}
            GROUP BY coding_agent, destination_model
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
            SELECT
                requester,
                {agent_cls} as coding_agent,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COUNT(*) as requests,
                ROUND(AVG(latency_ms), 0) as avg_latency_ms
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
              {agent_filter}
            GROUP BY requester, coding_agent
            ORDER BY total_tokens DESC
            LIMIT 25
        """.strip()

    # -- Token Consumption Tab --

    def build_ai_gateway_token_consumption_kpis_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COUNT(*) as total_requests,
                ROUND(COALESCE(SUM(total_tokens), 0) * 1.0 / GREATEST(COUNT(*), 1), 0) as avg_tokens_per_request
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
        """.strip()

    def build_ai_gateway_token_consumption_daily_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                DATE(event_time) as date,
                COALESCE(SUM(total_tokens), 0) as tokens
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
            GROUP BY DATE(event_time)
            ORDER BY date ASC
        """.strip()

    def build_ai_gateway_token_consumption_by_dest_type_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                destination_type,
                COALESCE(SUM(total_tokens), 0) as tokens
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
            GROUP BY destination_type
            ORDER BY tokens DESC
        """.strip()

    def build_ai_gateway_token_consumption_weekly_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            WITH top_eps AS (
                SELECT endpoint_name
                FROM system.ai_gateway.usage
                WHERE {time_filter}
                  {ep_filter}
                GROUP BY endpoint_name
                ORDER BY COALESCE(SUM(total_tokens), 0) DESC
                LIMIT 7
            )
            SELECT
                DATE_TRUNC('WEEK', u.event_time) as week,
                u.endpoint_name,
                COALESCE(SUM(u.total_tokens), 0) as tokens
            FROM system.ai_gateway.usage u
            JOIN top_eps t ON u.endpoint_name = t.endpoint_name
            WHERE {time_filter}
              {ep_filter}
            GROUP BY DATE_TRUNC('WEEK', u.event_time), u.endpoint_name
            ORDER BY week ASC, u.endpoint_name
        """.strip()

    def build_ai_gateway_token_consumption_top_endpoints_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                endpoint_name,
                COALESCE(SUM(total_tokens), 0) as tokens
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
            GROUP BY endpoint_name
            ORDER BY tokens DESC
            LIMIT 10
        """.strip()

    def build_ai_gateway_token_consumption_top_models_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                destination_model as model,
                COALESCE(SUM(total_tokens), 0) as tokens
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
            GROUP BY destination_model
            ORDER BY tokens DESC
            LIMIT 10
        """.strip()

    def build_ai_gateway_token_consumption_top_users_query(self, days: float = 7, endpoint: str | None = None) -> str:
        time_filter = self._ai_gw_time_filter(days)
        ep_filter = self._ai_gw_endpoint_filter(endpoint)
        return f"""
            SELECT
                requester,
                COALESCE(SUM(total_tokens), 0) as tokens
            FROM system.ai_gateway.usage
            WHERE {time_filter}
              {ep_filter}
            GROUP BY requester
            ORDER BY tokens DESC
            LIMIT 10
        """.strip()

    # ── OTEL Queries ──

    def build_turnaround_summary(self) -> str:
        """Aggregate turnaround stats across all sessions."""
        return f"""
            WITH prompts AS (
                SELECT
                    session_id,
                    prompt_id,
                    event_ts as prompt_ts
                FROM {self.logs_mat}
                WHERE {self.service_filter}
                  AND event_name = 'user_prompt'
            ),
            prompt_events AS (
                SELECT
                    p.session_id,
                    p.prompt_id,
                    p.prompt_ts,
                    COUNT(*) as events_in_prompt,
                    COUNT(CASE WHEN l.event_name = 'api_request' THEN 1 END) as api_calls,
                    COUNT(CASE WHEN l.event_name = 'tool_result' THEN 1 END) as tool_calls,
                    MAX(l.event_ts) as last_agent_event
                FROM prompts p
                LEFT JOIN {self.logs_mat} l
                    ON p.session_id = l.session_id
                    AND p.prompt_id = l.prompt_id
                    AND l.event_name != 'user_prompt'
                    AND l.service_name = '{self.SERVICE_NAME}'
                GROUP BY p.session_id, p.prompt_id, p.prompt_ts
            ),
            with_durations AS (
                SELECT *,
                    ROUND(EXTRACT(EPOCH FROM last_agent_event)
                         - EXTRACT(EPOCH FROM prompt_ts), 0) as agent_work_sec
                FROM prompt_events
                WHERE last_agent_event IS NOT NULL
            )
            SELECT
                COUNT(DISTINCT session_id) as total_sessions,
                COUNT(*) as total_prompts,
                ROUND(AVG(agent_work_sec)::numeric, 1) as avg_turnaround_sec,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY agent_work_sec)::numeric, 1) as p50_turnaround_sec,
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY agent_work_sec)::numeric, 1) as p95_turnaround_sec,
                ROUND(MAX(agent_work_sec)::numeric, 0) as max_turnaround_sec,
                ROUND(AVG(api_calls)::numeric, 1) as avg_api_calls,
                ROUND(AVG(tool_calls)::numeric, 1) as avg_tool_calls,
                ROUND(AVG(events_in_prompt)::numeric, 1) as avg_events_per_prompt
            FROM with_durations
        """.strip()

    def build_turnaround_by_session(
        self,
        session_id: Optional[str] = None,
        limit: int = 500,
    ) -> str:
        """Per-prompt turnaround data. Optional session_id filter."""
        session_filter = (
            f"AND session_id = '{session_id}'" if session_id else ""
        )
        return f"""
            WITH prompts AS (
                SELECT
                    session_id,
                    prompt_id,
                    event_ts as prompt_ts,
                    LEFT(prompt_text, 80) as prompt_preview
                FROM {self.logs_mat}
                WHERE {self.service_filter}
                  AND event_name = 'user_prompt'
                  {session_filter}
            ),
            prompt_events AS (
                SELECT
                    p.session_id,
                    p.prompt_id,
                    p.prompt_ts,
                    p.prompt_preview,
                    COUNT(*) as events_in_prompt,
                    COUNT(CASE WHEN l.event_name = 'api_request' THEN 1 END) as api_calls,
                    COUNT(CASE WHEN l.event_name = 'tool_result' THEN 1 END) as tool_calls,
                    MAX(l.event_ts) as last_agent_event,
                    MAX(CASE WHEN l.tool_name = 'AskUserQuestion' THEN 1 ELSE 0 END) as has_question,
                    MAX(CASE WHEN l.tool_name = 'ExitPlanMode' THEN 1 ELSE 0 END) as has_plan_exit
                FROM prompts p
                LEFT JOIN {self.logs_mat} l
                    ON p.session_id = l.session_id
                    AND p.prompt_id = l.prompt_id
                    AND l.event_name != 'user_prompt'
                    AND l.service_name = '{self.SERVICE_NAME}'
                GROUP BY p.session_id, p.prompt_id, p.prompt_ts, p.prompt_preview
            )
            SELECT *,
                ROUND(EXTRACT(EPOCH FROM last_agent_event)
                     - EXTRACT(EPOCH FROM prompt_ts), 0) as agent_work_sec
            FROM prompt_events
            ORDER BY prompt_ts DESC
            LIMIT {limit}
        """.strip()

    def build_summary_query(self, days: Optional[float] = None) -> str:
        return f"""
            SELECT
                COUNT(DISTINCT session_id) as total_sessions,
                COUNT(DISTINCT user_id) as total_users,
                COUNT(*) as total_events,
                COUNT(CASE WHEN event_name = 'user_prompt' THEN 1 END) as total_prompts,
                COUNT(CASE WHEN event_name = 'api_request' THEN 1 END) as total_api_calls,
                COUNT(CASE WHEN event_name = 'api_error' THEN 1 END) as total_errors,
                SUM(CASE WHEN event_name = 'api_request'
                    THEN cost_usd ELSE 0 END) as total_cost_usd
            FROM {self.logs_mat}
            WHERE {self.service_filter}
              {self._days_filter(days)}
        """.strip()
