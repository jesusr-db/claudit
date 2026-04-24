from backend.config import settings


class EfficiencyQueryService:
    """SQL builders for the Developer Efficiency Panel (SPACE + DevEx hybrid).

    All queries run against the Lakebase Provisioned PG instance via cached_execute.
    Source table: zerobus_sdp.cc_logs_synced (alias: self.mat)

    Metrics implemented:
      - AI-Effective Yield (AEY): $ cost per in-session accepted decision
      - Cognitive Load Index (CLi): composite of tools/prompt × thrash × reject rate
      - Feedback Loop Latency: p50/p95 duration_ms by tool_name on tool_result events
      - Harness Convergence Score: daily trend of tool efficiency × completion rate
      - Rework Ratio: fraction of file writes that are re-writes to the same file

    Note: No service_name filter needed — cc_logs_synced is pre-filtered to
    service.name='claude-code' at the SDP pipeline level (cc_logs.sql).
    """

    @property
    def mat(self) -> str:
        return settings.kpi_logs_mat_table  # zerobus_sdp.cc_logs_synced

    def build_aey_overview(self, days: int = 30) -> str:
        return f"""
            SELECT
                ROUND(SUM(cost_usd) FILTER (WHERE event_name = 'api_request')::numeric, 4)
                    AS total_cost_usd,
                COUNT(*) FILTER (WHERE event_name = 'tool_decision' AND decision = 'accept')
                    AS accepted_decisions,
                ROUND(
                    (SUM(cost_usd) FILTER (WHERE event_name = 'api_request') /
                     NULLIF(COUNT(*) FILTER (WHERE event_name = 'tool_decision' AND decision = 'accept'), 0))::numeric,
                    6
                ) AS cost_per_accepted_decision
            FROM {self.mat}
            WHERE event_ts >= current_date - interval '{days} days'
        """.strip()

    def build_cognitive_load_index(self, days: int = 30) -> str:
        return f"""
            WITH per_session AS (
                SELECT
                    session_id,
                    ROUND(
                        COUNT(*) FILTER (WHERE event_name = 'tool_result')::float /
                        NULLIF(COUNT(DISTINCT prompt_id) FILTER (WHERE event_name = 'user_prompt'), 0),
                        2
                    ) AS tools_per_prompt,
                    ROUND(
                        COUNT(*) FILTER (WHERE event_name = 'tool_decision' AND decision != 'accept')::float /
                        NULLIF(COUNT(*) FILTER (WHERE event_name = 'tool_decision'), 0),
                        3
                    ) AS reject_rate
                FROM {self.mat}
                WHERE event_ts >= current_date - interval '{days} days'
                GROUP BY session_id
            ),
            thrash AS (
                SELECT session_id, COUNT(*) AS repeated_reads
                FROM (
                    SELECT session_id, tool_parameters, COUNT(*) AS reads
                    FROM {self.mat}
                    WHERE event_name = 'tool_result'
                      AND tool_name = 'Read'
                      AND tool_parameters IS NOT NULL
                      AND event_ts >= current_date - interval '{days} days'
                    GROUP BY session_id, tool_parameters
                    HAVING COUNT(*) > 1
                ) r
                GROUP BY session_id
            )
            SELECT
                ROUND(AVG(ps.tools_per_prompt)::numeric, 2)          AS avg_tools_per_prompt,
                ROUND(AVG(COALESCE(t.repeated_reads, 0))::numeric, 2) AS avg_context_thrash,
                ROUND(AVG(COALESCE(ps.reject_rate, 0))::numeric, 3)  AS avg_reject_rate,
                ROUND(
                    (AVG(ps.tools_per_prompt) *
                     (1 + AVG(COALESCE(t.repeated_reads, 0)) / 5.0) *
                     (1 + AVG(COALESCE(ps.reject_rate, 0))))::numeric,
                    3
                ) AS cognitive_load_index
            FROM per_session ps
            LEFT JOIN thrash t ON ps.session_id = t.session_id
        """.strip()

    def build_feedback_latency(self, days: int = 30) -> str:
        return f"""
            SELECT
                tool_name,
                COUNT(*)                                                                          AS call_count,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms)::numeric, 0)      AS p50_ms,
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 0)     AS p95_ms,
                ROUND(AVG(duration_ms)::numeric, 0)                                               AS avg_ms
            FROM {self.mat}
            WHERE event_name = 'tool_result'
              AND duration_ms IS NOT NULL
              AND duration_ms > 0
              AND event_ts >= current_date - interval '{days} days'
            GROUP BY tool_name
            ORDER BY p95_ms DESC NULLS LAST
            LIMIT 20
        """.strip()

    def build_harness_convergence(self, days: int = 30) -> str:
        return f"""
            WITH per_session AS (
                SELECT
                    session_id,
                    date_trunc('day', MIN(event_ts))::date AS session_date,
                    COUNT(DISTINCT prompt_id) FILTER (WHERE event_name = 'user_prompt')          AS prompts,
                    COUNT(*) FILTER (WHERE event_name = 'tool_result')                           AS tool_calls,
                    COUNT(*) FILTER (WHERE event_name = 'api_error')                             AS api_errors,
                    COUNT(*) FILTER (WHERE event_name IN ('api_request', 'api_error'))           AS api_total
                FROM {self.mat}
                WHERE event_ts >= current_date - interval '{days} days'
                GROUP BY session_id
                HAVING COUNT(DISTINCT prompt_id) FILTER (WHERE event_name = 'user_prompt') > 0
                   AND COUNT(*) FILTER (WHERE event_name = 'tool_result') > 0
                   AND COUNT(*) FILTER (WHERE event_name IN ('api_request', 'api_error')) > 0
            ),
            scored AS (
                SELECT
                    session_date,
                    (1.0 - api_errors::float / NULLIF(api_total, 0)) /
                    (1.0 + tool_calls::float / NULLIF(prompts, 0) / 10.0) AS convergence_score
                FROM per_session
            )
            SELECT
                session_date                                         AS date,
                ROUND(AVG(convergence_score)::numeric, 3)           AS avg_convergence_score,
                COUNT(*)                                             AS session_count
            FROM scored
            GROUP BY session_date
            ORDER BY date ASC
        """.strip()

    def build_rework_ratio(self, days: int = 30) -> str:
        return f"""
            WITH file_writes AS (
                SELECT
                    session_id,
                    COALESCE(
                        substring(tool_parameters FROM '"file_path"\\s*:\\s*"([^"]+)"'),
                        substring(tool_parameters FROM '"path"\\s*:\\s*"([^"]+)"'),
                        tool_parameters
                    ) AS file_path,
                    event_ts
                FROM {self.mat}
                WHERE event_name = 'tool_result'
                  AND tool_name IN ('Edit', 'Write', 'MultiEdit')
                  AND tool_parameters IS NOT NULL
                  AND event_ts >= current_date - interval '{days} days'
            ),
            write_counts AS (
                SELECT session_id, file_path, COUNT(*) AS writes
                FROM file_writes
                GROUP BY session_id, file_path
            ),
            rework_per_session AS (
                SELECT
                    session_id,
                    SUM(writes)                      AS total_writes,
                    SUM(GREATEST(writes - 1, 0))     AS rework_writes
                FROM write_counts
                GROUP BY session_id
            )
            SELECT
                ROUND(AVG(rework_writes::float / NULLIF(total_writes, 0))::numeric, 3)    AS avg_rework_ratio,
                ROUND((SUM(rework_writes)::float / NULLIF(SUM(total_writes), 0))::numeric, 3) AS overall_rework_ratio,
                SUM(rework_writes)::int                                                    AS total_rework_writes,
                SUM(total_writes)::int                                                     AS total_writes,
                COUNT(*)                                                                   AS sessions_with_writes
            FROM rework_per_session
            WHERE total_writes > 0
        """.strip()
