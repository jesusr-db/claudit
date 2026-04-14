from backend.config import settings


class KpiQueryService:
    """Builds SQL queries for KPI Hub: cost intelligence, agent effectiveness, flow correlation.

    Uses kpi_logs_mat materialized view with pre-extracted columns for fast queries.
    Falls back to JSONB views only for spans (flow) queries.
    """

    def __init__(self):
        pass

    SERVICE_NAME = "claude-code"

    PG_METHODS = {
        'build_cost_overview', 'build_cost_trend', 'build_cost_by_session',
        'build_model_cost_comparison', 'build_token_waste_signals',
        'build_effectiveness_overview', 'build_tool_retry_analysis',
        'build_orphan_decisions', 'build_error_recovery_patterns',
        'build_prompt_complexity_distribution',
        'build_e2e_flow_summary',
        'build_model_performance_matrix', 'build_rightsizing_opportunities',
        'build_rightsizing_details', 'build_model_recommendation',
        'build_savings_calculator',
        'build_kpi_badges',
        'build_activity_classification',
    }

    SQL_METHODS = {
        'build_uc_connection_audit',
    }

    @property
    def mat(self) -> str:
        """Materialized view with pre-extracted columns (no JSONB overhead)."""
        return settings.kpi_logs_mat_table

    @property
    def spans_table(self) -> str:
        return settings.mcp_otel_spans_table

    @property
    def service_filter(self) -> str:
        return f"service_name = '{self.SERVICE_NAME}'"

    # ── Phase 1: Cost Intelligence ──

    def build_cost_overview(self, days: int = 30) -> str:
        return f"""
            SELECT
                ROUND(SUM(cost_usd)::numeric, 4) as total_cost,
                ROUND((SUM(cost_usd) / NULLIF(COUNT(DISTINCT session_id), 0))::numeric, 4) as avg_cost_per_session,
                ROUND((SUM(cost_usd) / NULLIF(COUNT(*), 0))::numeric, 6) as avg_cost_per_prompt,
                ROUND(
                    (100.0 * SUM(cache_read_tokens) /
                    NULLIF(SUM(input_tokens) + SUM(cache_read_tokens), 0))::numeric,
                    1
                ) as cache_hit_pct
            FROM {self.mat}
            WHERE {self.service_filter}
              AND event_name = 'api_request'
              AND event_ts >= current_date - interval '{days} days'
        """.strip()

    def build_cost_trend(self, days: float = 30) -> str:
        if days < 1:
            minutes = max(int(days * 24 * 60), 5)
            return f"""
                SELECT
                    to_char(
                        date_trunc('hour', event_ts)
                        + (floor(extract(minute from event_ts) / 5) * interval '5 minutes'),
                        'YYYY-MM-DD HH24:MI'
                    ) as date,
                    ROUND(SUM(cost_usd)::numeric, 4) as daily_cost,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(cache_read_tokens) as cache_read_tokens,
                    COUNT(*) as request_count
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_request'
                  AND event_ts >= CURRENT_TIMESTAMP - interval '{minutes} minutes'
                GROUP BY 1
                ORDER BY date ASC
            """.strip()
        elif days <= 1:
            return f"""
                SELECT
                    to_char(event_ts, 'YYYY-MM-DD HH24:00') as date,
                    ROUND(SUM(cost_usd)::numeric, 4) as daily_cost,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(cache_read_tokens) as cache_read_tokens,
                    COUNT(*) as request_count
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_request'
                  AND event_ts >= CURRENT_TIMESTAMP - interval '24 hours'
                GROUP BY to_char(event_ts, 'YYYY-MM-DD HH24:00')
                ORDER BY date ASC
            """.strip()
        else:
            int_days = int(days)
            return f"""
                SELECT
                    DATE(event_ts) as date,
                    ROUND(SUM(cost_usd)::numeric, 4) as daily_cost,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(cache_read_tokens) as cache_read_tokens,
                    COUNT(*) as request_count
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_request'
                  AND event_ts >= current_date - interval '{int_days} days'
                GROUP BY DATE(event_ts)
                ORDER BY date ASC
            """.strip()

    def build_cost_by_session(self, days: int = 30, limit: int = 20) -> str:
        return f"""
            WITH session_costs AS (
                SELECT
                    session_id,
                    SUM(cost_usd) as total_cost,
                    COUNT(*) as prompt_count,
                    ROUND(
                        (100.0 * SUM(cache_read_tokens) /
                        NULLIF(SUM(input_tokens) + SUM(cache_read_tokens), 0))::numeric,
                        1
                    ) as cache_hit_pct,
                    SUM(input_tokens) + SUM(output_tokens) + SUM(cache_read_tokens) as total_tokens
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_request'
                  AND event_ts >= current_date - interval '{days} days'
                GROUP BY session_id
            ),
            first_prompts AS (
                SELECT
                    session_id,
                    MIN(prompt_text) as first_prompt
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'user_prompt'
                GROUP BY session_id
            )
            SELECT
                sc.session_id,
                ROUND(sc.total_cost::numeric, 4) as total_cost,
                sc.prompt_count,
                sc.cache_hit_pct,
                ROUND((sc.total_cost / NULLIF(sc.prompt_count, 0))::numeric, 6) as cost_per_prompt,
                LEFT(fp.first_prompt, 80) as first_prompt,
                sc.total_tokens
            FROM session_costs sc
            LEFT JOIN first_prompts fp ON sc.session_id = fp.session_id
            ORDER BY sc.total_cost DESC
            LIMIT {limit}
        """.strip()

    def build_model_cost_comparison(self, days: int = 30) -> str:
        return f"""
            SELECT
                model,
                ROUND(SUM(cost_usd)::numeric, 4) as total_cost,
                COUNT(*) as request_count,
                ROUND((SUM(cost_usd) / COUNT(*))::numeric, 6) as avg_cost_per_call,
                ROUND(AVG(duration_ms)::numeric, 0) as avg_latency_ms,
                ROUND(
                    (100.0 * SUM(cache_read_tokens) /
                    NULLIF(SUM(input_tokens) + SUM(cache_read_tokens), 0))::numeric,
                    1
                ) as cache_hit_pct,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens
            FROM {self.mat}
            WHERE {self.service_filter}
              AND event_name = 'api_request'
              AND event_ts >= current_date - interval '{days} days'
            GROUP BY model
            ORDER BY total_cost DESC
        """.strip()

    def build_token_waste_signals(self, days: int = 30) -> str:
        return f"""
            SELECT
                session_id,
                prompt_id,
                input_tokens,
                output_tokens,
                cost_usd,
                model
            FROM {self.mat}
            WHERE {self.service_filter}
              AND event_name = 'api_request'
              AND event_ts >= current_date - interval '{days} days'
              AND input_tokens > 50000
              AND output_tokens < 500
            ORDER BY cost_usd DESC
            LIMIT 50
        """.strip()

    # ── Phase 2: Agent Effectiveness ──

    def build_effectiveness_overview(self, days: int = 30) -> str:
        return f"""
            WITH tool_results AS (
                SELECT success
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'tool_result'
                  AND event_ts >= current_date - interval '{days} days'
            ),
            api_errors AS (
                SELECT COUNT(*) as error_count
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_error'
                  AND event_ts >= current_date - interval '{days} days'
            ),
            prompt_stats AS (
                SELECT
                    COUNT(DISTINCT prompt_id) as total_prompts,
                    COUNT(CASE WHEN event_name = 'tool_result' THEN 1 END) as total_tool_calls,
                    COUNT(CASE WHEN event_name = 'api_request' THEN 1 END) as total_api_calls
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_ts >= current_date - interval '{days} days'
            )
            SELECT
                ROUND((100.0 * SUM(CASE WHEN tr.success = 'true' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0))::numeric, 1) as tool_success_rate,
                ROUND((ps.total_tool_calls::double precision / NULLIF(ps.total_prompts, 0))::numeric, 1) as avg_tools_per_prompt,
                ROUND((ps.total_api_calls::double precision / NULLIF(ps.total_prompts, 0))::numeric, 1) as avg_api_calls_per_prompt,
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
                    session_id,
                    prompt_id,
                    tool_name,
                    event_name,
                    event_seq,
                    LAG(tool_name) OVER (
                        PARTITION BY session_id, prompt_id
                        ORDER BY event_seq
                    ) as prev_tool,
                    LAG(event_name) OVER (
                        PARTITION BY session_id, prompt_id
                        ORDER BY event_seq
                    ) as prev_event
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name IN ('tool_decision', 'tool_result')
                  AND event_ts >= current_date - interval '{days} days'
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
                SELECT session_id, prompt_id, tool_name
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'tool_decision'
                  AND event_ts >= current_date - interval '{days} days'
            ),
            results AS (
                SELECT session_id, prompt_id, tool_name
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'tool_result'
                  AND event_ts >= current_date - interval '{days} days'
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
                    session_id,
                    prompt_id,
                    event_name,
                    model,
                    event_seq,
                    LEAD(event_name) OVER (
                        PARTITION BY session_id, prompt_id
                        ORDER BY event_seq
                    ) as next_event
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name IN ('api_error', 'api_request')
                  AND event_ts >= current_date - interval '{days} days'
            )
            SELECT
                model,
                SUM(CASE WHEN event_name = 'api_error' AND next_event = 'api_request' THEN 1 ELSE 0 END) as recovery_count,
                SUM(CASE WHEN event_name = 'api_error' THEN 1 ELSE 0 END) as total_errors,
                ROUND(
                    (100.0 * SUM(CASE WHEN event_name = 'api_error' AND next_event = 'api_request' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN event_name = 'api_error' THEN 1 ELSE 0 END), 0))::numeric,
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
                    session_id,
                    prompt_id,
                    COUNT(*) as event_count,
                    COUNT(CASE WHEN event_name = 'tool_result' THEN 1 END) as tool_calls,
                    COUNT(CASE WHEN event_name = 'api_request' THEN 1 END) as api_calls,
                    MIN(event_ts) as first_event,
                    MAX(event_ts) as last_event
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_ts >= current_date - interval '{days} days'
                GROUP BY session_id, prompt_id
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
                    EXTRACT(EPOCH FROM last_event) - EXTRACT(EPOCH FROM first_event)
                )::numeric, 1) as avg_agent_work_sec,
                ROUND(AVG(tool_calls)::numeric, 1) as avg_tool_calls,
                ROUND(AVG(api_calls)::numeric, 1) as avg_api_calls
            FROM prompt_stats
            GROUP BY
                CASE
                    WHEN event_count BETWEEN 1 AND 5 THEN '1-5'
                    WHEN event_count BETWEEN 6 AND 15 THEN '6-15'
                    WHEN event_count BETWEEN 16 AND 50 THEN '16-50'
                    ELSE '50+'
                END
            ORDER BY MIN(event_count)
        """.strip()

    # ── Phase 3: Flow Correlation ──

    def build_e2e_flow_summary(self, days: int = 30) -> str:
        """Spans query — still uses JSONB view (spans table has 0 rows currently)."""
        return f"""
            WITH tool_spans AS (
                SELECT
                    resource_attributes->>'service.name' as server_name,
                    name as tool_name,
                    COUNT(*) as tool_calls,
                    ROUND(AVG((end_time_unix_nano - start_time_unix_nano) / 1e6)::numeric, 1) as avg_duration_ms,
                    SUM(CASE WHEN status->>'code' IS NULL OR status->>'code' != 'ERROR' THEN 1 ELSE 0 END) as success_count,
                    SUM(CASE WHEN status->>'code' = 'ERROR' THEN 1 ELSE 0 END) as error_count
                FROM {self.spans_table}
                WHERE kind = 'SPAN_KIND_INTERNAL'
                  AND name LIKE 'mcp.tool.%'
                GROUP BY resource_attributes->>'service.name', name
            ),
            http_connections AS (
                SELECT
                    resource_attributes->>'service.name' as server_name,
                    (regexp_match(attributes->>'http.url', '/mcp/external/([^/?]+)'))[1] as connection_name,
                    COUNT(*) as http_calls,
                    ROUND(AVG((end_time_unix_nano - start_time_unix_nano) / 1e6)::numeric, 1) as avg_http_duration_ms,
                    SUM(CASE WHEN (attributes->>'http.status_code')::int >= 400 THEN 1 ELSE 0 END) as http_errors
                FROM {self.spans_table}
                WHERE kind = 'SPAN_KIND_CLIENT'
                  AND attributes->>'http.url' LIKE '%/mcp/external/%'
                GROUP BY resource_attributes->>'service.name',
                         (regexp_match(attributes->>'http.url', '/mcp/external/([^/?]+)'))[1]
            ),
            other_http AS (
                SELECT
                    resource_attributes->>'service.name' as server_name,
                    (regexp_match(attributes->>'http.url', '^(https?://[^/]+)'))[1] as domain,
                    COUNT(*) as http_calls,
                    ROUND(AVG((end_time_unix_nano - start_time_unix_nano) / 1e6)::numeric, 1) as avg_http_duration_ms
                FROM {self.spans_table}
                WHERE kind = 'SPAN_KIND_CLIENT'
                  AND attributes->>'http.url' NOT LIKE '%/mcp/external/%'
                  AND attributes->>'http.url' IS NOT NULL
                GROUP BY resource_attributes->>'service.name',
                         (regexp_match(attributes->>'http.url', '^(https?://[^/]+)'))[1]
            )
            SELECT
                'tool' as section, ts.server_name, ts.tool_name as name,
                ts.tool_calls::text as calls, ts.avg_duration_ms::text as avg_duration_ms,
                ts.success_count::text as success, ts.error_count::text as errors,
                NULL::text as extra
            FROM tool_spans ts
            UNION ALL
            SELECT
                'connection' as section, hc.server_name, hc.connection_name as name,
                hc.http_calls::text as calls, hc.avg_http_duration_ms::text as avg_duration_ms,
                NULL::text as success, hc.http_errors::text as errors,
                NULL::text as extra
            FROM http_connections hc
            UNION ALL
            SELECT
                'external_api' as section, oh.server_name, oh.domain as name,
                oh.http_calls::text as calls, oh.avg_http_duration_ms::text as avg_duration_ms,
                NULL::text as success, NULL::text as errors,
                NULL::text as extra
            FROM other_http oh
            ORDER BY server_name, section, calls DESC
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

    def _prompt_complexity_cte(self, days: int) -> str:
        """Shared CTE used by all Phase 4 queries — computed once per query."""
        return f"""
            prompt_events AS (
                SELECT session_id, prompt_id, COUNT(*) as event_count
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_ts >= current_date - interval '{days} days'
                GROUP BY session_id, prompt_id
            ),
            prompt_complexity AS (
                SELECT session_id, prompt_id,
                    {self._complexity_case()} as complexity
                FROM prompt_events
            )"""

    def build_model_performance_matrix(self, days: int = 30) -> str:
        return f"""
            WITH {self._prompt_complexity_cte(days)},
            api_calls AS (
                SELECT session_id, prompt_id, model, cost_usd, duration_ms, output_tokens
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_request'
                  AND event_ts >= current_date - interval '{days} days'
            ),
            tool_results AS (
                SELECT session_id, prompt_id, success
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'tool_result'
                  AND event_ts >= current_date - interval '{days} days'
            ),
            api_errors AS (
                SELECT session_id, prompt_id
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_error'
                  AND event_ts >= current_date - interval '{days} days'
            ),
            joined AS (
                SELECT ac.model, pc.complexity, ac.cost_usd, ac.duration_ms, ac.output_tokens
                FROM api_calls ac
                JOIN prompt_complexity pc ON ac.session_id = pc.session_id AND ac.prompt_id = pc.prompt_id
            ),
            tool_joined AS (
                SELECT pc.complexity, tr.success
                FROM tool_results tr
                JOIN prompt_complexity pc ON tr.session_id = pc.session_id AND tr.prompt_id = pc.prompt_id
            ),
            error_joined AS (
                SELECT pc.complexity, ae.session_id
                FROM api_errors ae
                JOIN prompt_complexity pc ON ae.session_id = pc.session_id AND ae.prompt_id = pc.prompt_id
            ),
            tool_rates AS (
                SELECT complexity,
                    ROUND((100.0 * SUM(CASE WHEN success = 'true' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0))::numeric, 1) as tool_success_rate
                FROM tool_joined
                GROUP BY complexity
            ),
            error_rates AS (
                SELECT complexity, COUNT(*) as error_count
                FROM error_joined
                GROUP BY complexity
            )
            SELECT
                j.model, j.complexity,
                COUNT(*) as call_count,
                ROUND(AVG(j.cost_usd)::numeric, 6) as avg_cost_per_call,
                ROUND(SUM(j.cost_usd)::numeric, 4) as total_cost,
                ROUND(AVG(j.duration_ms)::numeric, 0) as avg_latency_ms,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY j.duration_ms)::numeric, 0) as p50_latency_ms,
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY j.duration_ms)::numeric, 0) as p95_latency_ms,
                ROUND(AVG(j.output_tokens)::numeric, 0) as avg_output_tokens,
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
            WITH {self._prompt_complexity_cte(days)},
            api_calls AS (
                SELECT session_id, prompt_id, model, cost_usd
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_request'
                  AND event_ts >= current_date - interval '{days} days'
            ),
            joined AS (
                SELECT
                    ac.model, pc.complexity, ac.cost_usd,
                    CASE
                        WHEN LOWER(ac.model) LIKE '%opus%' THEN 3
                        WHEN LOWER(ac.model) LIKE '%sonnet%' THEN 2
                        WHEN LOWER(ac.model) LIKE '%haiku%' THEN 1
                        ELSE 2
                    END as model_tier,
                    CASE pc.complexity
                        WHEN 'simple' THEN 1 WHEN 'moderate' THEN 2
                        WHEN 'complex' THEN 3 ELSE 4
                    END as complexity_tier
                FROM api_calls ac
                JOIN prompt_complexity pc ON ac.session_id = pc.session_id AND ac.prompt_id = pc.prompt_id
            )
            SELECT
                model, complexity,
                COUNT(*) as call_count,
                ROUND(SUM(cost_usd)::numeric, 4) as total_cost,
                ROUND(AVG(cost_usd)::numeric, 6) as avg_cost,
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
            WITH {self._prompt_complexity_cte(days)},
            api_calls AS (
                SELECT session_id, prompt_id, model, cost_usd, duration_ms, output_tokens
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_request'
                  AND event_ts >= current_date - interval '{days} days'
            ),
            first_prompts AS (
                SELECT session_id, prompt_id, MIN(prompt_text) as prompt_text
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'user_prompt'
                  AND event_ts >= current_date - interval '{days} days'
                GROUP BY session_id, prompt_id
            ),
            joined AS (
                SELECT
                    ac.session_id, ac.prompt_id, ac.model, pc.complexity,
                    SUM(ac.cost_usd) as prompt_cost,
                    COUNT(*) as api_calls,
                    ROUND(AVG(ac.duration_ms)::numeric, 0) as avg_latency_ms,
                    SUM(ac.output_tokens) as total_output_tokens,
                    CASE
                        WHEN LOWER(ac.model) LIKE '%opus%' THEN 3
                        WHEN LOWER(ac.model) LIKE '%sonnet%' THEN 2
                        WHEN LOWER(ac.model) LIKE '%haiku%' THEN 1
                        ELSE 2
                    END as model_tier,
                    CASE pc.complexity
                        WHEN 'simple' THEN 1 WHEN 'moderate' THEN 2
                        WHEN 'complex' THEN 3 ELSE 4
                    END as complexity_tier
                FROM api_calls ac
                JOIN prompt_complexity pc ON ac.session_id = pc.session_id AND ac.prompt_id = pc.prompt_id
                WHERE 1=1 {model_filter} {complexity_filter}
                GROUP BY ac.session_id, ac.prompt_id, ac.model, pc.complexity
            )
            SELECT
                j.session_id, j.prompt_id, j.model, j.complexity,
                ROUND(j.prompt_cost::numeric, 4) as prompt_cost,
                j.api_calls, j.avg_latency_ms, j.total_output_tokens,
                CASE
                    WHEN j.model_tier - j.complexity_tier >= 2 THEN 'high'
                    WHEN j.model_tier - j.complexity_tier = 1 THEN 'medium'
                    ELSE 'low'
                END as downgrade_opportunity,
                LEFT(COALESCE(fp.prompt_text, ''), 120) as prompt_preview
            FROM joined j
            LEFT JOIN first_prompts fp ON j.session_id = fp.session_id AND j.prompt_id = fp.prompt_id
            WHERE j.model_tier > j.complexity_tier
            ORDER BY j.prompt_cost DESC
            LIMIT {limit}
        """.strip()

    def build_model_recommendation(self, days: int = 30) -> str:
        return f"""
            WITH {self._prompt_complexity_cte(days)},
            api_calls AS (
                SELECT session_id, prompt_id, model, cost_usd, duration_ms
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_request'
                  AND event_ts >= current_date - interval '{days} days'
            ),
            joined AS (
                SELECT ac.model, pc.complexity, ac.cost_usd, ac.duration_ms
                FROM api_calls ac
                JOIN prompt_complexity pc ON ac.session_id = pc.session_id AND ac.prompt_id = pc.prompt_id
            ),
            model_stats AS (
                SELECT
                    model, complexity,
                    COUNT(*) as call_count,
                    ROUND(AVG(cost_usd)::numeric, 6) as avg_cost,
                    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms)::numeric, 0) as p50_latency,
                    ROUND(AVG(cost_usd)::numeric, 6) as cost_per_call
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
                model, complexity, call_count, avg_cost, p50_latency,
                cost_rank, speed_rank,
                CASE WHEN cost_rank = 1 THEN true ELSE false END as is_cost_winner,
                CASE WHEN speed_rank = 1 THEN true ELSE false END as is_speed_winner
            FROM ranked
            ORDER BY {self._complexity_order()}, cost_rank
        """.strip()

    def build_savings_calculator(self, days: int = 30) -> str:
        return f"""
            WITH {self._prompt_complexity_cte(days)},
            api_calls AS (
                SELECT session_id, prompt_id, model, cost_usd
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_request'
                  AND event_ts >= current_date - interval '{days} days'
            ),
            joined AS (
                SELECT ac.model, pc.complexity, ac.cost_usd
                FROM api_calls ac
                JOIN prompt_complexity pc ON ac.session_id = pc.session_id AND ac.prompt_id = pc.prompt_id
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
                ) subq
                GROUP BY complexity, model, avg_cost
            ),
            cheapest_deduped AS (
                SELECT complexity,
                    MIN(cheapest_avg_cost) as cheapest_avg_cost,
                    MIN(cheapest_model) as cheapest_model
                FROM cheapest
                GROUP BY complexity
            ),
            actual AS (
                SELECT complexity, COUNT(*) as call_count, ROUND(SUM(cost_usd)::numeric, 4) as actual_cost
                FROM joined
                GROUP BY complexity
            )
            SELECT
                a.complexity, a.call_count, a.actual_cost,
                ROUND((a.call_count * cd.cheapest_avg_cost)::numeric, 4) as hypothetical_cost,
                ROUND((a.actual_cost - (a.call_count * cd.cheapest_avg_cost))::numeric, 4) as potential_savings,
                ROUND(
                    (100.0 * (a.actual_cost - (a.call_count * cd.cheapest_avg_cost))
                    / NULLIF(a.actual_cost, 0))::numeric, 1
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
                        (100.0 * SUM(cache_read_tokens) /
                        NULLIF(SUM(input_tokens) + SUM(cache_read_tokens), 0))::numeric, 1
                    ) as cache_hit_pct,
                    ROUND(SUM(cost_usd)::numeric, 4) as total_cost
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_request'
                  AND event_ts >= current_date - interval '{days} days'
            ),
            prev_cost AS (
                SELECT ROUND(SUM(cost_usd)::numeric, 4) as prev_total_cost
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'api_request'
                  AND event_ts >= current_date - interval '{days * 2} days'
                  AND event_ts < current_date - interval '{days} days'
            ),
            tool_data AS (
                SELECT
                    ROUND((100.0 * SUM(CASE WHEN success = 'true' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0))::numeric, 1)
                        as tool_success_rate
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_name = 'tool_result'
                  AND event_ts >= current_date - interval '{days} days'
            ),
            prompt_durations AS (
                SELECT
                    EXTRACT(EPOCH FROM MAX(event_ts)) - EXTRACT(EPOCH FROM MIN(event_ts))
                    as duration_sec
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND event_ts >= current_date - interval '{days} days'
                GROUP BY session_id, prompt_id
            ),
            turnaround AS (
                SELECT ROUND(AVG(duration_sec)::numeric, 1) as avg_turnaround_sec
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

    # ── Activity Classification (CodeBurn-inspired) ──

    def build_activity_classification(self, days: int = 30) -> str:
        return f"""
            WITH prompt_tools AS (
                SELECT
                    prompt_id,
                    string_agg(DISTINCT tool_name, ',') AS tools,
                    MAX(CASE WHEN event_name = 'user_prompt' THEN prompt_text END) AS prompt_text,
                    SUM(CASE WHEN event_name = 'api_request' THEN cost_usd ELSE 0 END) AS cost,
                    SUM(CASE WHEN event_name = 'api_request' THEN input_tokens + output_tokens ELSE 0 END) AS tokens,
                    COUNT(CASE WHEN event_name = 'api_request' THEN 1 END) AS api_calls
                FROM {self.mat}
                WHERE {self.service_filter}
                  AND prompt_id IS NOT NULL
                  AND event_ts >= current_date - interval '{days} days'
                GROUP BY prompt_id
            )
            SELECT
                activity,
                COUNT(*) AS prompt_count,
                ROUND(SUM(cost)::numeric, 4) AS total_cost,
                SUM(tokens) AS total_tokens
            FROM (
                SELECT *,
                    CASE
                        WHEN tools LIKE '%mcp_tool%' THEN 'Delegation'
                        WHEN prompt_text ~* 'test|pytest|jest|spec|coverage' THEN 'Testing'
                        WHEN prompt_text ~* 'git |commit|branch|merge|rebase|cherry.pick' THEN 'Git Ops'
                        WHEN prompt_text ~* 'build|deploy|docker|npm run|yarn |make |webpack|vite' THEN 'Build/Deploy'
                        WHEN prompt_text ~* 'debug|error|fix |bug|stacktrace|traceback|exception' THEN 'Debugging'
                        WHEN prompt_text ~* 'plan|design|architect|approach|strategy' THEN 'Planning'
                        WHEN prompt_text ~* 'find|search|explore|where is|how does' AND tools ~ 'Read|Glob|Grep' THEN 'Exploration'
                        WHEN tools ~ 'Edit|Write' THEN 'Coding'
                        WHEN tools IS NULL OR tools = '' THEN 'Conversation'
                        ELSE 'General'
                    END AS activity
                FROM prompt_tools
            ) classified
            GROUP BY activity
            ORDER BY total_cost DESC
        """.strip()
