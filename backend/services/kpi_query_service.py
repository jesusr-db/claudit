from typing import Optional


class KpiQueryService:
    """Builds SQL queries for KPI Hub: cost intelligence, agent effectiveness, flow correlation."""

    def __init__(self, catalog: str, schema: str, mcp_schema: str = "default"):
        self.catalog = catalog
        self.schema = schema
        self.mcp_schema = mcp_schema

    SERVICE_NAME = "claude-code"

    @property
    def logs_table(self) -> str:
        return f"{self.catalog}.{self.schema}.otel_logs"

    @property
    def metrics_table(self) -> str:
        return f"{self.catalog}.{self.schema}.otel_metrics"

    @property
    def spans_table(self) -> str:
        return f"{self.catalog}.{self.mcp_schema}.otel_spans"

    @property
    def mcp_metrics_table(self) -> str:
        return f"{self.catalog}.{self.mcp_schema}.otel_metrics"

    @property
    def service_filter(self) -> str:
        return f"resource.attributes['service.name'] = '{self.SERVICE_NAME}'"

    # ── Phase 1: Cost Intelligence ──

    def build_cost_overview(self, days: int = 30) -> str:
        return f"""
            WITH api_calls AS (
                SELECT
                    attributes['session.id'] as session_id,
                    CAST(attributes['cost_usd'] AS DOUBLE) as cost_usd,
                    CAST(attributes['input_tokens'] AS BIGINT) as input_tokens,
                    CAST(attributes['cache_read_tokens'] AS BIGINT) as cache_read_tokens
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_request'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            )
            SELECT
                ROUND(SUM(cost_usd), 4) as total_cost,
                ROUND(SUM(cost_usd) / NULLIF(COUNT(DISTINCT session_id), 0), 4) as avg_cost_per_session,
                ROUND(SUM(cost_usd) / NULLIF(COUNT(*), 0), 6) as avg_cost_per_prompt,
                ROUND(
                    100.0 * SUM(cache_read_tokens) /
                    NULLIF(SUM(input_tokens) + SUM(cache_read_tokens), 0),
                    1
                ) as cache_hit_pct
            FROM api_calls
        """.strip()

    def build_cost_trend(self, days: float = 30) -> str:
        if days < 1:
            # Sub-day (1h): bucket by 5-minute intervals
            minutes = max(int(days * 24 * 60), 5)
            return f"""
                SELECT
                    CONCAT(
                        DATE_FORMAT(CAST(attributes['event.timestamp'] AS TIMESTAMP), 'yyyy-MM-dd HH:'),
                        LPAD(CAST(FLOOR(MINUTE(CAST(attributes['event.timestamp'] AS TIMESTAMP)) / 5) * 5 AS STRING), 2, '0')
                    ) as date,
                    ROUND(SUM(CAST(attributes['cost_usd'] AS DOUBLE)), 4) as daily_cost,
                    SUM(CAST(attributes['input_tokens'] AS BIGINT)) as input_tokens,
                    SUM(CAST(attributes['output_tokens'] AS BIGINT)) as output_tokens,
                    SUM(CAST(attributes['cache_read_tokens'] AS BIGINT)) as cache_read_tokens,
                    COUNT(*) as request_count
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_request'
                  AND CAST(attributes['event.timestamp'] AS TIMESTAMP) >= CURRENT_TIMESTAMP() - INTERVAL {minutes} MINUTES
                GROUP BY 1
                ORDER BY date ASC
            """.strip()
        elif days <= 1:
            # 1 day: bucket by hour
            return f"""
                SELECT
                    DATE_FORMAT(CAST(attributes['event.timestamp'] AS TIMESTAMP), 'yyyy-MM-dd HH:00') as date,
                    ROUND(SUM(CAST(attributes['cost_usd'] AS DOUBLE)), 4) as daily_cost,
                    SUM(CAST(attributes['input_tokens'] AS BIGINT)) as input_tokens,
                    SUM(CAST(attributes['output_tokens'] AS BIGINT)) as output_tokens,
                    SUM(CAST(attributes['cache_read_tokens'] AS BIGINT)) as cache_read_tokens,
                    COUNT(*) as request_count
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_request'
                  AND CAST(attributes['event.timestamp'] AS TIMESTAMP) >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
                GROUP BY DATE_FORMAT(CAST(attributes['event.timestamp'] AS TIMESTAMP), 'yyyy-MM-dd HH:00')
                ORDER BY date ASC
            """.strip()
        else:
            # Multi-day (7d+): bucket by day
            int_days = int(days)
            return f"""
                SELECT
                    DATE(attributes['event.timestamp']) as date,
                    ROUND(SUM(CAST(attributes['cost_usd'] AS DOUBLE)), 4) as daily_cost,
                    SUM(CAST(attributes['input_tokens'] AS BIGINT)) as input_tokens,
                    SUM(CAST(attributes['output_tokens'] AS BIGINT)) as output_tokens,
                    SUM(CAST(attributes['cache_read_tokens'] AS BIGINT)) as cache_read_tokens,
                    COUNT(*) as request_count
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_request'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {int_days})
                GROUP BY DATE(attributes['event.timestamp'])
                ORDER BY date ASC
            """.strip()

    def build_cost_by_session(self, days: int = 30, limit: int = 20) -> str:
        return f"""
            WITH session_costs AS (
                SELECT
                    attributes['session.id'] as session_id,
                    SUM(CAST(attributes['cost_usd'] AS DOUBLE)) as total_cost,
                    COUNT(*) as prompt_count,
                    ROUND(
                        100.0 * SUM(CAST(attributes['cache_read_tokens'] AS BIGINT)) /
                        NULLIF(SUM(CAST(attributes['input_tokens'] AS BIGINT))
                             + SUM(CAST(attributes['cache_read_tokens'] AS BIGINT)), 0),
                        1
                    ) as cache_hit_pct,
                    SUM(CAST(attributes['input_tokens'] AS BIGINT))
                      + SUM(CAST(attributes['output_tokens'] AS BIGINT))
                      + SUM(CAST(attributes['cache_read_tokens'] AS BIGINT)) as total_tokens
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_request'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
                GROUP BY attributes['session.id']
            ),
            first_prompts AS (
                SELECT
                    attributes['session.id'] as session_id,
                    MIN(attributes['prompt']) as first_prompt
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'user_prompt'
                GROUP BY attributes['session.id']
            )
            SELECT
                sc.session_id,
                ROUND(sc.total_cost, 4) as total_cost,
                sc.prompt_count,
                sc.cache_hit_pct,
                ROUND(sc.total_cost / NULLIF(sc.prompt_count, 0), 6) as cost_per_prompt,
                SUBSTRING(fp.first_prompt, 1, 80) as first_prompt,
                sc.total_tokens
            FROM session_costs sc
            LEFT JOIN first_prompts fp ON sc.session_id = fp.session_id
            ORDER BY sc.total_cost DESC
            LIMIT {limit}
        """.strip()

    def build_model_cost_comparison(self, days: int = 30) -> str:
        return f"""
            SELECT
                attributes['model'] as model,
                ROUND(SUM(CAST(attributes['cost_usd'] AS DOUBLE)), 4) as total_cost,
                COUNT(*) as request_count,
                ROUND(SUM(CAST(attributes['cost_usd'] AS DOUBLE)) / COUNT(*), 6) as avg_cost_per_call,
                ROUND(AVG(CAST(attributes['duration_ms'] AS DOUBLE)), 0) as avg_latency_ms,
                ROUND(
                    100.0 * SUM(CAST(attributes['cache_read_tokens'] AS BIGINT)) /
                    NULLIF(SUM(CAST(attributes['input_tokens'] AS BIGINT))
                         + SUM(CAST(attributes['cache_read_tokens'] AS BIGINT)), 0),
                    1
                ) as cache_hit_pct,
                SUM(CAST(attributes['input_tokens'] AS BIGINT)) as total_input_tokens,
                SUM(CAST(attributes['output_tokens'] AS BIGINT)) as total_output_tokens
            FROM {self.logs_table}
            WHERE {self.service_filter}
              AND attributes['event.name'] = 'api_request'
              AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            GROUP BY attributes['model']
            ORDER BY total_cost DESC
        """.strip()

    def build_token_waste_signals(self, days: int = 30) -> str:
        return f"""
            SELECT
                attributes['session.id'] as session_id,
                attributes['prompt.id'] as prompt_id,
                CAST(attributes['input_tokens'] AS BIGINT) as input_tokens,
                CAST(attributes['output_tokens'] AS BIGINT) as output_tokens,
                CAST(attributes['cost_usd'] AS DOUBLE) as cost_usd,
                attributes['model'] as model
            FROM {self.logs_table}
            WHERE {self.service_filter}
              AND attributes['event.name'] = 'api_request'
              AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
              AND CAST(attributes['input_tokens'] AS BIGINT) > 50000
              AND CAST(attributes['output_tokens'] AS BIGINT) < 500
            ORDER BY CAST(attributes['cost_usd'] AS DOUBLE) DESC
            LIMIT 50
        """.strip()

    # ── Phase 2: Agent Effectiveness ──

    def build_effectiveness_overview(self, days: int = 30) -> str:
        return f"""
            WITH tool_results AS (
                SELECT
                    attributes['success'] as success
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'tool_result'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            api_errors AS (
                SELECT COUNT(*) as error_count
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_error'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            prompt_stats AS (
                SELECT
                    COUNT(DISTINCT attributes['prompt.id']) as total_prompts,
                    COUNT(CASE WHEN attributes['event.name'] = 'tool_result' THEN 1 END) as total_tool_calls,
                    COUNT(CASE WHEN attributes['event.name'] = 'api_request' THEN 1 END) as total_api_calls
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            )
            SELECT
                ROUND(100.0 * SUM(CASE WHEN tr.success = 'true' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as tool_success_rate,
                ROUND(CAST(ps.total_tool_calls AS DOUBLE) / NULLIF(ps.total_prompts, 0), 1) as avg_tools_per_prompt,
                ROUND(CAST(ps.total_api_calls AS DOUBLE) / NULLIF(ps.total_prompts, 0), 1) as avg_api_calls_per_prompt,
                ae.error_count as total_errors,
                ps.total_prompts,
                ps.total_tool_calls
            FROM tool_results tr
            CROSS JOIN api_errors ae
            CROSS JOIN prompt_stats ps
            GROUP BY ae.error_count, ps.total_prompts, ps.total_tool_calls, ps.total_api_calls
        """.strip()

    def build_tool_retry_analysis(self, days: int = 30) -> str:
        return f"""
            WITH ordered_events AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    attributes['tool_name'] as tool_name,
                    attributes['event.name'] as event_name,
                    CAST(attributes['event.sequence'] AS INT) as seq,
                    LAG(attributes['tool_name']) OVER (
                        PARTITION BY attributes['session.id'], attributes['prompt.id']
                        ORDER BY CAST(attributes['event.sequence'] AS INT)
                    ) as prev_tool,
                    LAG(attributes['event.name']) OVER (
                        PARTITION BY attributes['session.id'], attributes['prompt.id']
                        ORDER BY CAST(attributes['event.sequence'] AS INT)
                    ) as prev_event
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] IN ('tool_decision', 'tool_result')
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            )
            SELECT
                tool_name,
                COUNT(*) as retry_count,
                COUNT(DISTINCT session_id) as sessions_affected
            FROM ordered_events
            WHERE event_name = 'tool_decision'
              AND prev_event = 'tool_result'
              AND prev_tool = tool_name
            GROUP BY tool_name
            ORDER BY retry_count DESC
        """.strip()

    def build_orphan_decisions(self, days: int = 30) -> str:
        return f"""
            WITH decisions AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    attributes['tool_name'] as tool_name
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'tool_decision'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            results AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    attributes['tool_name'] as tool_name
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'tool_result'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            )
            SELECT
                d.tool_name,
                COUNT(*) as orphan_count,
                COUNT(DISTINCT d.session_id) as sessions_affected
            FROM decisions d
            LEFT JOIN results r
                ON d.session_id = r.session_id
                AND d.prompt_id = r.prompt_id
                AND d.tool_name = r.tool_name
            WHERE r.tool_name IS NULL
            GROUP BY d.tool_name
            ORDER BY orphan_count DESC
        """.strip()

    def build_error_recovery_patterns(self, days: int = 30) -> str:
        return f"""
            WITH sequenced AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    attributes['event.name'] as event_name,
                    attributes['model'] as model,
                    CAST(attributes['event.sequence'] AS INT) as seq,
                    LEAD(attributes['event.name']) OVER (
                        PARTITION BY attributes['session.id'], attributes['prompt.id']
                        ORDER BY CAST(attributes['event.sequence'] AS INT)
                    ) as next_event
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] IN ('api_error', 'api_request')
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            )
            SELECT
                model,
                SUM(CASE WHEN event_name = 'api_error' AND next_event = 'api_request' THEN 1 ELSE 0 END) as recovery_count,
                SUM(CASE WHEN event_name = 'api_error' THEN 1 ELSE 0 END) as total_errors,
                ROUND(
                    100.0 * SUM(CASE WHEN event_name = 'api_error' AND next_event = 'api_request' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN event_name = 'api_error' THEN 1 ELSE 0 END), 0),
                    1
                ) as recovery_rate
            FROM sequenced
            WHERE event_name = 'api_error'
            GROUP BY model
            ORDER BY total_errors DESC
        """.strip()

    def build_prompt_complexity_distribution(self, days: int = 30) -> str:
        return f"""
            WITH prompt_stats AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    COUNT(*) as event_count,
                    COUNT(CASE WHEN attributes['event.name'] = 'tool_result' THEN 1 END) as tool_calls,
                    COUNT(CASE WHEN attributes['event.name'] = 'api_request' THEN 1 END) as api_calls,
                    MIN(attributes['event.timestamp']) as first_event,
                    MAX(attributes['event.timestamp']) as last_event
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
                GROUP BY attributes['session.id'], attributes['prompt.id']
            )
            SELECT
                CASE
                    WHEN event_count BETWEEN 1 AND 5 THEN '1-5'
                    WHEN event_count BETWEEN 6 AND 15 THEN '6-15'
                    WHEN event_count BETWEEN 16 AND 50 THEN '16-50'
                    ELSE '50+'
                END as bucket,
                COUNT(*) as prompt_count,
                ROUND(AVG(
                    UNIX_TIMESTAMP(CAST(last_event AS TIMESTAMP))
                    - UNIX_TIMESTAMP(CAST(first_event AS TIMESTAMP))
                ), 1) as avg_agent_work_sec,
                ROUND(AVG(tool_calls), 1) as avg_tool_calls,
                ROUND(AVG(api_calls), 1) as avg_api_calls
            FROM prompt_stats
            GROUP BY
                CASE
                    WHEN event_count BETWEEN 1 AND 5 THEN '1-5'
                    WHEN event_count BETWEEN 6 AND 15 THEN '6-15'
                    WHEN event_count BETWEEN 16 AND 50 THEN '16-50'
                    ELSE '50+'
                END
            ORDER BY
                CASE bucket
                    WHEN '1-5' THEN 1
                    WHEN '6-15' THEN 2
                    WHEN '16-50' THEN 3
                    ELSE 4
                END
        """.strip()

    # ── Phase 3: Flow Correlation ──

    def build_e2e_flow_summary(self, days: int = 30) -> str:
        """Two-section result: server-level connection summary + per-tool details.

        Tool spans and HTTP/connection spans are in separate traces (no shared trace_id),
        so we correlate at the server level: a server uses connections, and has tools.
        """
        return f"""
            WITH tool_spans AS (
                SELECT
                    resource.attributes['service.name'] as server_name,
                    name as tool_name,
                    COUNT(*) as tool_calls,
                    ROUND(AVG((end_time_unix_nano - start_time_unix_nano) / 1e6), 1) as avg_duration_ms,
                    SUM(CASE WHEN status.code IS NULL OR status.code != 'ERROR' THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN status.code = 'ERROR' THEN 1 ELSE 0 END) as error_count
                FROM {self.spans_table}
                WHERE kind = 'SPAN_KIND_INTERNAL'
                  AND name LIKE 'mcp.tool.%'
                GROUP BY resource.attributes['service.name'], name
            ),
            http_connections AS (
                SELECT
                    resource.attributes['service.name'] as server_name,
                    REGEXP_EXTRACT(attributes['http.url'], '/mcp/external/([^/?]+)', 1) as connection_name,
                    COUNT(*) as http_calls,
                    ROUND(AVG((end_time_unix_nano - start_time_unix_nano) / 1e6), 1) as avg_http_duration_ms,
                    SUM(CASE WHEN CAST(attributes['http.status_code'] AS INT) >= 400 THEN 1 ELSE 0 END) as http_errors
                FROM {self.spans_table}
                WHERE kind = 'SPAN_KIND_CLIENT'
                  AND attributes['http.url'] LIKE '%/mcp/external/%'
                GROUP BY resource.attributes['service.name'],
                         REGEXP_EXTRACT(attributes['http.url'], '/mcp/external/([^/?]+)', 1)
            ),
            other_http AS (
                SELECT
                    resource.attributes['service.name'] as server_name,
                    REGEXP_EXTRACT(attributes['http.url'], '^(https?://[^/]+)') as domain,
                    COUNT(*) as http_calls,
                    ROUND(AVG((end_time_unix_nano - start_time_unix_nano) / 1e6), 1) as avg_http_duration_ms
                FROM {self.spans_table}
                WHERE kind = 'SPAN_KIND_CLIENT'
                  AND attributes['http.url'] NOT LIKE '%/mcp/external/%'
                  AND attributes['http.url'] IS NOT NULL
                GROUP BY resource.attributes['service.name'],
                         REGEXP_EXTRACT(attributes['http.url'], '^(https?://[^/]+)')
            ),
            uc_audit AS (
                SELECT
                    COALESCE(request_params.name_arg, '(unknown)') as connection_name,
                    COUNT(*) as audit_events
                FROM system.access.audit
                WHERE service_name = 'unityCatalog'
                  AND action_name = 'getConnection'
                  AND event_time >= current_date() - {days}
                GROUP BY COALESCE(request_params.name_arg, '(unknown)')
            )
            -- Tools
            SELECT
                'tool' as section,
                ts.server_name,
                ts.tool_name as name,
                CAST(ts.tool_calls AS STRING) as calls,
                CAST(ts.avg_duration_ms AS STRING) as avg_duration_ms,
                CAST(ts.success_count AS STRING) as success,
                CAST(ts.error_count AS STRING) as errors,
                NULL as extra
            FROM tool_spans ts
            UNION ALL
            -- UC Connections
            SELECT
                'connection' as section,
                hc.server_name,
                hc.connection_name as name,
                CAST(hc.http_calls AS STRING) as calls,
                CAST(hc.avg_http_duration_ms AS STRING) as avg_duration_ms,
                NULL as success,
                CAST(hc.http_errors AS STRING) as errors,
                CAST(COALESCE(ua.audit_events, 0) AS STRING) as extra
            FROM http_connections hc
            LEFT JOIN uc_audit ua ON hc.connection_name = ua.connection_name
            UNION ALL
            -- External APIs
            SELECT
                'external_api' as section,
                oh.server_name,
                oh.domain as name,
                CAST(oh.http_calls AS STRING) as calls,
                CAST(oh.avg_http_duration_ms AS STRING) as avg_duration_ms,
                NULL as success,
                NULL as errors,
                NULL as extra
            FROM other_http oh
            ORDER BY server_name, section, CAST(calls AS INT) DESC
        """.strip()

    def build_uc_connection_audit(self, days: int = 7) -> str:
        return f"""
            SELECT
                COALESCE(request_params.name_arg, '(all connections)') as connection_name,
                action_name,
                COUNT(*) as call_count,
                COUNT(DISTINCT DATE(event_time)) as active_days,
                MIN(event_time) as first_seen,
                MAX(event_time) as last_seen,
                COUNT(DISTINCT user_identity.email) as distinct_users
            FROM system.access.audit
            WHERE service_name = 'unityCatalog'
              AND action_name LIKE '%Connection%'
              AND event_time >= current_date() - {days}
            GROUP BY COALESCE(request_params.name_arg, '(all connections)'), action_name
            ORDER BY call_count DESC
        """.strip()

    # ── Phase 4: Model Efficiency ──

    def _complexity_case(self) -> str:
        """Shared CASE expression for prompt complexity bucketing."""
        return """
            CASE
                WHEN event_count BETWEEN 1 AND 5 THEN 'simple'
                WHEN event_count BETWEEN 6 AND 15 THEN 'moderate'
                WHEN event_count BETWEEN 16 AND 50 THEN 'complex'
                ELSE 'very_complex'
            END
        """

    def _complexity_order(self, col: str = "complexity") -> str:
        return f"""
            CASE {col}
                WHEN 'simple' THEN 1
                WHEN 'moderate' THEN 2
                WHEN 'complex' THEN 3
                ELSE 4
            END
        """

    def build_model_performance_matrix(self, days: int = 30) -> str:
        return f"""
            WITH prompt_events AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    COUNT(*) as event_count
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
                GROUP BY attributes['session.id'], attributes['prompt.id']
            ),
            prompt_complexity AS (
                SELECT session_id, prompt_id,
                    {self._complexity_case()} as complexity
                FROM prompt_events
            ),
            api_calls AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    attributes['model'] as model,
                    CAST(attributes['cost_usd'] AS DOUBLE) as cost_usd,
                    CAST(attributes['duration_ms'] AS DOUBLE) as duration_ms,
                    CAST(attributes['output_tokens'] AS BIGINT) as output_tokens
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_request'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            tool_results AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    attributes['success'] as success
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'tool_result'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            api_errors AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_error'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            joined AS (
                SELECT
                    ac.model,
                    pc.complexity,
                    ac.cost_usd,
                    ac.duration_ms,
                    ac.output_tokens
                FROM api_calls ac
                JOIN prompt_complexity pc
                  ON ac.session_id = pc.session_id AND ac.prompt_id = pc.prompt_id
            ),
            tool_joined AS (
                SELECT pc.complexity, tr.success
                FROM tool_results tr
                JOIN prompt_complexity pc
                  ON tr.session_id = pc.session_id AND tr.prompt_id = pc.prompt_id
            ),
            error_joined AS (
                SELECT pc.complexity, ae.session_id
                FROM api_errors ae
                JOIN prompt_complexity pc
                  ON ae.session_id = pc.session_id AND ae.prompt_id = pc.prompt_id
            ),
            tool_rates AS (
                SELECT complexity,
                    ROUND(100.0 * SUM(CASE WHEN success = 'true' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) as tool_success_rate
                FROM tool_joined
                GROUP BY complexity
            ),
            error_rates AS (
                SELECT complexity, COUNT(*) as error_count
                FROM error_joined
                GROUP BY complexity
            )
            SELECT
                j.model,
                j.complexity,
                COUNT(*) as call_count,
                ROUND(AVG(j.cost_usd), 6) as avg_cost_per_call,
                ROUND(SUM(j.cost_usd), 4) as total_cost,
                ROUND(AVG(j.duration_ms), 0) as avg_latency_ms,
                ROUND(PERCENTILE_APPROX(j.duration_ms, 0.5), 0) as p50_latency_ms,
                ROUND(PERCENTILE_APPROX(j.duration_ms, 0.95), 0) as p95_latency_ms,
                ROUND(AVG(j.output_tokens), 0) as avg_output_tokens,
                COALESCE(tr.tool_success_rate, 0) as tool_success_rate,
                COALESCE(er.error_count, 0) as error_count
            FROM joined j
            LEFT JOIN tool_rates tr ON j.complexity = tr.complexity
            LEFT JOIN error_rates er ON j.complexity = er.complexity
            GROUP BY j.model, j.complexity, tr.tool_success_rate, er.error_count
            ORDER BY j.model, {self._complexity_order('j.complexity')}
        """.strip()

    def build_rightsizing_opportunities(self, days: int = 30) -> str:
        return f"""
            WITH prompt_events AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    COUNT(*) as event_count
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
                GROUP BY attributes['session.id'], attributes['prompt.id']
            ),
            prompt_complexity AS (
                SELECT session_id, prompt_id,
                    {self._complexity_case()} as complexity
                FROM prompt_events
            ),
            api_calls AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    attributes['model'] as model,
                    CAST(attributes['cost_usd'] AS DOUBLE) as cost_usd
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_request'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            joined AS (
                SELECT
                    ac.model,
                    pc.complexity,
                    ac.cost_usd,
                    CASE
                        WHEN LOWER(ac.model) LIKE '%opus%' THEN 3
                        WHEN LOWER(ac.model) LIKE '%sonnet%' THEN 2
                        WHEN LOWER(ac.model) LIKE '%haiku%' THEN 1
                        ELSE 2
                    END as model_tier,
                    CASE pc.complexity
                        WHEN 'simple' THEN 1
                        WHEN 'moderate' THEN 2
                        WHEN 'complex' THEN 3
                        ELSE 4
                    END as complexity_tier
                FROM api_calls ac
                JOIN prompt_complexity pc
                  ON ac.session_id = pc.session_id AND ac.prompt_id = pc.prompt_id
            )
            SELECT
                model,
                complexity,
                COUNT(*) as call_count,
                ROUND(SUM(cost_usd), 4) as total_cost,
                ROUND(AVG(cost_usd), 6) as avg_cost,
                CASE
                    WHEN model_tier - complexity_tier >= 2 THEN 'high'
                    WHEN model_tier - complexity_tier = 1 THEN 'medium'
                    WHEN model_tier - complexity_tier = 0 THEN 'low'
                    ELSE 'none'
                END as downgrade_opportunity
            FROM joined
            GROUP BY model, complexity, model_tier, complexity_tier
            ORDER BY
                CASE
                    WHEN model_tier - complexity_tier >= 2 THEN 1
                    WHEN model_tier - complexity_tier = 1 THEN 2
                    WHEN model_tier - complexity_tier = 0 THEN 3
                    ELSE 4
                END,
                SUM(cost_usd) DESC
        """.strip()

    def build_rightsizing_details(self, days: int = 30, model: str = "", complexity: str = "", limit: int = 50) -> str:
        model_filter = f"AND ac.model = '{model}'" if model else ""
        complexity_filter = f"AND pc.complexity = '{complexity}'" if complexity else ""
        return f"""
            WITH prompt_events AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    COUNT(*) as event_count
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
                GROUP BY attributes['session.id'], attributes['prompt.id']
            ),
            prompt_complexity AS (
                SELECT session_id, prompt_id,
                    {self._complexity_case()} as complexity
                FROM prompt_events
            ),
            api_calls AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    attributes['model'] as model,
                    CAST(attributes['cost_usd'] AS DOUBLE) as cost_usd,
                    CAST(attributes['duration_ms'] AS DOUBLE) as duration_ms,
                    CAST(attributes['output_tokens'] AS BIGINT) as output_tokens
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_request'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            first_prompts AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    MIN(attributes['prompt']) as prompt_text
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'user_prompt'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
                GROUP BY attributes['session.id'], attributes['prompt.id']
            ),
            joined AS (
                SELECT
                    ac.session_id,
                    ac.prompt_id,
                    ac.model,
                    pc.complexity,
                    SUM(ac.cost_usd) as prompt_cost,
                    COUNT(*) as api_calls,
                    ROUND(AVG(ac.duration_ms), 0) as avg_latency_ms,
                    SUM(ac.output_tokens) as total_output_tokens,
                    CASE
                        WHEN LOWER(ac.model) LIKE '%opus%' THEN 3
                        WHEN LOWER(ac.model) LIKE '%sonnet%' THEN 2
                        WHEN LOWER(ac.model) LIKE '%haiku%' THEN 1
                        ELSE 2
                    END as model_tier,
                    CASE pc.complexity
                        WHEN 'simple' THEN 1
                        WHEN 'moderate' THEN 2
                        WHEN 'complex' THEN 3
                        ELSE 4
                    END as complexity_tier
                FROM api_calls ac
                JOIN prompt_complexity pc
                  ON ac.session_id = pc.session_id AND ac.prompt_id = pc.prompt_id
                WHERE 1=1 {model_filter} {complexity_filter}
                GROUP BY ac.session_id, ac.prompt_id, ac.model, pc.complexity
            )
            SELECT
                j.session_id,
                j.prompt_id,
                j.model,
                j.complexity,
                ROUND(j.prompt_cost, 4) as prompt_cost,
                j.api_calls,
                j.avg_latency_ms,
                j.total_output_tokens,
                CASE
                    WHEN j.model_tier - j.complexity_tier >= 2 THEN 'high'
                    WHEN j.model_tier - j.complexity_tier = 1 THEN 'medium'
                    ELSE 'low'
                END as downgrade_opportunity,
                SUBSTRING(COALESCE(fp.prompt_text, ''), 1, 120) as prompt_preview
            FROM joined j
            LEFT JOIN first_prompts fp
              ON j.session_id = fp.session_id AND j.prompt_id = fp.prompt_id
            WHERE j.model_tier > j.complexity_tier
            ORDER BY j.prompt_cost DESC
            LIMIT {limit}
        """.strip()

    def build_model_recommendation(self, days: int = 30) -> str:
        return f"""
            WITH prompt_events AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    COUNT(*) as event_count
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
                GROUP BY attributes['session.id'], attributes['prompt.id']
            ),
            prompt_complexity AS (
                SELECT session_id, prompt_id,
                    {self._complexity_case()} as complexity
                FROM prompt_events
            ),
            api_calls AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    attributes['model'] as model,
                    CAST(attributes['cost_usd'] AS DOUBLE) as cost_usd,
                    CAST(attributes['duration_ms'] AS DOUBLE) as duration_ms
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_request'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            tool_results AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    CASE WHEN attributes['success'] = 'true' THEN 1 ELSE 0 END as is_success
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'tool_result'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            joined AS (
                SELECT
                    ac.model,
                    pc.complexity,
                    ac.cost_usd,
                    ac.duration_ms
                FROM api_calls ac
                JOIN prompt_complexity pc
                  ON ac.session_id = pc.session_id AND ac.prompt_id = pc.prompt_id
            ),
            model_stats AS (
                SELECT
                    model,
                    complexity,
                    COUNT(*) as call_count,
                    ROUND(AVG(cost_usd), 6) as avg_cost,
                    ROUND(PERCENTILE_APPROX(duration_ms, 0.5), 0) as p50_latency,
                    ROUND(AVG(cost_usd) / NULLIF(1, 0), 6) as cost_per_call
                FROM joined
                GROUP BY model, complexity
                HAVING COUNT(*) >= 5
            ),
            ranked AS (
                SELECT *,
                    ROW_NUMBER() OVER (PARTITION BY complexity ORDER BY avg_cost ASC) as cost_rank,
                    ROW_NUMBER() OVER (PARTITION BY complexity ORDER BY p50_latency ASC) as speed_rank
                FROM model_stats
            )
            SELECT
                model,
                complexity,
                call_count,
                avg_cost,
                p50_latency,
                cost_rank,
                speed_rank,
                CASE WHEN cost_rank = 1 THEN true ELSE false END as is_cost_winner,
                CASE WHEN speed_rank = 1 THEN true ELSE false END as is_speed_winner
            FROM ranked
            ORDER BY {self._complexity_order()}, cost_rank
        """.strip()

    def build_savings_calculator(self, days: int = 30) -> str:
        return f"""
            WITH prompt_events AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    COUNT(*) as event_count
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
                GROUP BY attributes['session.id'], attributes['prompt.id']
            ),
            prompt_complexity AS (
                SELECT session_id, prompt_id,
                    {self._complexity_case()} as complexity
                FROM prompt_events
            ),
            api_calls AS (
                SELECT
                    attributes['session.id'] as session_id,
                    attributes['prompt.id'] as prompt_id,
                    attributes['model'] as model,
                    CAST(attributes['cost_usd'] AS DOUBLE) as cost_usd
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_request'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            joined AS (
                SELECT
                    ac.model,
                    pc.complexity,
                    ac.cost_usd
                FROM api_calls ac
                JOIN prompt_complexity pc
                  ON ac.session_id = pc.session_id AND ac.prompt_id = pc.prompt_id
            ),
            cheapest AS (
                SELECT complexity,
                    MIN(avg_cost) as cheapest_avg_cost,
                    FIRST_VALUE(model) OVER (PARTITION BY complexity ORDER BY avg_cost) as cheapest_model
                FROM (
                    SELECT model, complexity, AVG(cost_usd) as avg_cost
                    FROM joined
                    GROUP BY model, complexity
                    HAVING COUNT(*) >= 5
                )
                GROUP BY complexity, model, avg_cost
            ),
            cheapest_deduped AS (
                SELECT complexity,
                    MIN(cheapest_avg_cost) as cheapest_avg_cost,
                    FIRST(cheapest_model) as cheapest_model
                FROM cheapest
                GROUP BY complexity
            ),
            actual AS (
                SELECT
                    complexity,
                    COUNT(*) as call_count,
                    ROUND(SUM(cost_usd), 4) as actual_cost
                FROM joined
                GROUP BY complexity
            )
            SELECT
                a.complexity,
                a.call_count,
                a.actual_cost,
                ROUND(a.call_count * cd.cheapest_avg_cost, 4) as hypothetical_cost,
                ROUND(a.actual_cost - (a.call_count * cd.cheapest_avg_cost), 4) as potential_savings,
                ROUND(
                    100.0 * (a.actual_cost - (a.call_count * cd.cheapest_avg_cost))
                    / NULLIF(a.actual_cost, 0),
                    1
                ) as savings_pct,
                cd.cheapest_model
            FROM actual a
            LEFT JOIN cheapest_deduped cd ON a.complexity = cd.complexity
            ORDER BY {self._complexity_order('a.complexity')}
        """.strip()

    # ── Badges ──

    def build_kpi_badges(self, days: int = 30) -> str:
        return f"""
            WITH cost_data AS (
                SELECT
                    ROUND(
                        100.0 * SUM(CAST(attributes['cache_read_tokens'] AS BIGINT)) /
                        NULLIF(SUM(CAST(attributes['input_tokens'] AS BIGINT))
                             + SUM(CAST(attributes['cache_read_tokens'] AS BIGINT)), 0),
                        1
                    ) as cache_hit_pct,
                    ROUND(SUM(CAST(attributes['cost_usd'] AS DOUBLE)), 4) as total_cost
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_request'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            prev_cost AS (
                SELECT
                    ROUND(SUM(CAST(attributes['cost_usd'] AS DOUBLE)), 4) as prev_total_cost
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'api_request'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days * 2})
                  AND attributes['event.timestamp'] < DATE_SUB(current_date(), {days})
            ),
            tool_data AS (
                SELECT
                    ROUND(100.0 * SUM(CASE WHEN attributes['success'] = 'true' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1)
                        as tool_success_rate
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.name'] = 'tool_result'
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
            ),
            prompt_durations AS (
                SELECT
                    UNIX_TIMESTAMP(CAST(MAX(attributes['event.timestamp']) AS TIMESTAMP))
                    - UNIX_TIMESTAMP(CAST(MIN(attributes['event.timestamp']) AS TIMESTAMP))
                    as duration_sec
                FROM {self.logs_table}
                WHERE {self.service_filter}
                  AND attributes['event.timestamp'] >= DATE_SUB(current_date(), {days})
                GROUP BY attributes['session.id'], attributes['prompt.id']
            ),
            turnaround AS (
                SELECT ROUND(AVG(duration_sec), 1) as avg_turnaround_sec
                FROM prompt_durations
            )
            SELECT
                cd.cache_hit_pct,
                CASE
                    WHEN cd.total_cost > COALESCE(pc.prev_total_cost, 0) * 1.1 THEN 'up'
                    WHEN cd.total_cost < COALESCE(pc.prev_total_cost, 0) * 0.9 THEN 'down'
                    ELSE 'flat'
                END as cost_trend_direction,
                td.tool_success_rate,
                ta.avg_turnaround_sec
            FROM cost_data cd
            CROSS JOIN prev_cost pc
            CROSS JOIN tool_data td
            CROSS JOIN turnaround ta
        """.strip()
