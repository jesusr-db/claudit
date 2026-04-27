from typing import Optional

from backend.config import settings


class McpQueryService:
    """Builds SQL queries against MCP server OTEL tables (PostgreSQL / Lakebase).

    Uses otel_spans_mat materialized view with pre-extracted columns for fast span queries.
    Falls back to the JSONB view only for logs (body/severity aren't in any mat view).
    """

    def __init__(self):
        pass  # Uses settings directly

    @property
    def spans_mat(self) -> str:
        return settings.otel_spans_mat_table

    @property
    def metrics_table(self) -> str:
        return settings.mcp_otel_metrics_table

    @property
    def logs_table(self) -> str:
        return settings.mcp_otel_logs_table

    def _server_filter(self, server: Optional[str]) -> str:
        if server:
            return f"AND service_name = '{server}'"
        return ""

    def _server_filter_logs(self, server: Optional[str]) -> str:
        """Server filter for logs synced table (typed `service_name` column from MV).
        Always filters to claude-code when no specific server is given."""
        if server:
            return f"AND service_name = '{server}'"
        return "AND service_name = 'claude-code'"

    @staticmethod
    def _time_filter_spans(days: Optional[float]) -> str:
        """Time filter for spans mat view (using start_ts timestamp column)."""
        if days is None:
            return ""
        if days < 1:
            minutes = max(int(days * 24 * 60), 5)
            return f"AND start_ts >= CURRENT_TIMESTAMP - interval '{minutes} minutes'"
        return f"AND start_ts >= CURRENT_TIMESTAMP - interval '{int(days)} days'"

    @staticmethod
    def _time_filter_logs(days: Optional[float]) -> str:
        """Time filter for logs tables (using time_unix_nano)."""
        if days is None:
            return ""
        if days < 1:
            minutes = max(int(days * 24 * 60), 5)
            return f"AND to_timestamp(time_unix_nano::bigint / 1000000000.0) >= CURRENT_TIMESTAMP - interval '{minutes} minutes'"
        return f"AND to_timestamp(time_unix_nano::bigint / 1000000000.0) >= CURRENT_TIMESTAMP - interval '{int(days)} days'"

    @staticmethod
    def _time_filter_metrics(days: Optional[float]) -> str:
        """Time filter for metrics tables (flattened: sum_time_unix_nano, histogram_time_unix_nano)."""
        if days is None:
            return ""
        ts_expr = "COALESCE(sum_time_unix_nano, histogram_time_unix_nano)"
        if days < 1:
            minutes = max(int(days * 24 * 60), 5)
            return f"AND to_timestamp({ts_expr}::bigint / 1000000000.0) >= CURRENT_TIMESTAMP - interval '{minutes} minutes'"
        return f"AND to_timestamp({ts_expr}::bigint / 1000000000.0) >= CURRENT_TIMESTAMP - interval '{int(days)} days'"

    # ── Operations Queries ──

    def build_server_summary(self, server: Optional[str] = None, days: Optional[float] = None) -> str:
        """Distinct service names with tool count, span counts, HTTP call count, log entries."""
        tf_spans = self._time_filter_spans(days)
        tf_logs = self._time_filter_logs(days)
        sf_logs = self._server_filter_logs(server)
        return f"""
            WITH tool_counts AS (
                SELECT
                    service_name,
                    COUNT(DISTINCT name) as tool_count,
                    COUNT(*) as tool_spans
                FROM {self.spans_mat}
                WHERE kind = 'SPAN_KIND_INTERNAL'
                  AND name LIKE 'mcp.tool.%'
                  {self._server_filter(server)}
                  {tf_spans}
                GROUP BY service_name
            ),
            http_counts AS (
                SELECT
                    service_name,
                    COUNT(*) as http_spans
                FROM {self.spans_mat}
                WHERE kind = 'SPAN_KIND_CLIENT'
                  {self._server_filter(server)}
                  {tf_spans}
                GROUP BY service_name
            ),
            all_spans AS (
                SELECT
                    service_name,
                    COUNT(*) as total_spans
                FROM {self.spans_mat}
                WHERE 1=1 {self._server_filter(server)} {tf_spans}
                GROUP BY service_name
            ),
            log_counts AS (
                SELECT
                    service_name,
                    COUNT(*) as total_log_entries
                FROM {self.logs_table}
                WHERE 1=1 {sf_logs} {tf_logs}
                GROUP BY service_name
            )
            SELECT
                a.service_name,
                COALESCE(t.tool_count, 0) as tool_count,
                a.total_spans,
                COALESCE(t.tool_spans, 0) as tool_spans,
                COALESCE(h.http_spans, 0) as http_spans,
                COALESCE(l.total_log_entries, 0) as total_log_entries
            FROM all_spans a
            LEFT JOIN tool_counts t ON a.service_name = t.service_name
            LEFT JOIN http_counts h ON a.service_name = h.service_name
            LEFT JOIN log_counts l ON a.service_name = l.service_name
            ORDER BY a.total_spans DESC
        """.strip()

    def build_tool_stats(self, server: Optional[str] = None, days: Optional[float] = None) -> str:
        """Per-tool aggregates from spans: call count, success rate, latency percentiles."""
        return f"""
            SELECT
                name as tool_name,
                COUNT(*) as call_count,
                SUM(CASE WHEN status_code IS NULL OR status_code != 'ERROR' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN status_code = 'ERROR' THEN 1 ELSE 0 END) as failure_count,
                ROUND(AVG(duration_ms)::numeric, 1) as avg_duration_ms,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms)::numeric, 1) as p50_duration_ms,
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 1) as p95_duration_ms
            FROM {self.spans_mat}
            WHERE kind = 'SPAN_KIND_INTERNAL'
              AND name LIKE 'mcp.tool.%'
              {self._server_filter(server)}
              {self._time_filter_spans(days)}
            GROUP BY name
            ORDER BY call_count DESC
        """.strip()

    def build_tool_latency_over_time(self, server: Optional[str] = None, days: Optional[float] = None) -> str:
        """Time-bucketed tool latency from spans."""
        return f"""
            SELECT
                DATE_TRUNC('hour', start_ts) as time_bucket,
                name as tool_name,
                COUNT(*) as call_count,
                ROUND(AVG(duration_ms)::numeric, 1) as avg_duration_ms,
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 1) as p95_duration_ms
            FROM {self.spans_mat}
            WHERE kind = 'SPAN_KIND_INTERNAL'
              AND name LIKE 'mcp.tool.%'
              {self._server_filter(server)}
              {self._time_filter_spans(days)}
            GROUP BY
                DATE_TRUNC('hour', start_ts),
                name
            ORDER BY time_bucket DESC
        """.strip()

    def build_http_outbound_summary(self, server: Optional[str] = None, days: Optional[float] = None) -> str:
        """Outbound HTTP calls grouped by URL domain + method + status code."""
        return f"""
            SELECT
                http_domain as domain,
                http_method as method,
                http_status_code::text as status_code,
                COUNT(*) as call_count,
                ROUND(AVG(duration_ms)::numeric, 1) as avg_duration_ms,
                ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 1) as p95_duration_ms
            FROM {self.spans_mat}
            WHERE kind = 'SPAN_KIND_CLIENT'
              AND http_method IS NOT NULL
              {self._server_filter(server)}
              {self._time_filter_spans(days)}
            GROUP BY http_domain, http_method, http_status_code
            ORDER BY call_count DESC
        """.strip()

    # ── Server Detail (expandable) ──

    def build_server_detail(self, server: Optional[str] = None, days: Optional[float] = None) -> str:
        """Per-tool metrics from mcp.tool.calls counter and mcp.tool.latency histogram.
        Uses typed columns directly from the synced metrics table — no JSONB casting."""
        if server:
            server_filter_metrics = f"AND service_name = '{server}'"
        else:
            server_filter_metrics = "AND service_name = 'claude-code'"
        return f"""
            WITH tool_calls AS (
                SELECT
                    sum_tool as tool_name,
                    sum_status as call_status,
                    SUM((sum_value)::double precision) as total_calls
                FROM {self.metrics_table}
                WHERE name = 'mcp.tool.calls'
                  {server_filter_metrics}
                  {self._time_filter_metrics(days)}
                GROUP BY sum_tool, sum_status
            ),
            tool_latency AS (
                SELECT
                    hist_tool as tool_name,
                    SUM(histogram_count) as latency_samples,
                    ROUND((SUM(histogram_sum) / NULLIF(SUM(histogram_count), 0))::numeric, 1) as avg_latency_ms,
                    ROUND(MIN(histogram_min)::numeric, 1) as min_latency_ms,
                    ROUND(MAX(histogram_max)::numeric, 1) as max_latency_ms
                FROM {self.metrics_table}
                WHERE name = 'mcp.tool.latency'
                  {server_filter_metrics}
                  {self._time_filter_metrics(days)}
                GROUP BY hist_tool
            ),
            http_duration AS (
                SELECT
                    hist_http_method as method,
                    hist_http_status_code as status_code,
                    SUM(histogram_count) as http_samples,
                    ROUND((SUM(histogram_sum) / NULLIF(SUM(histogram_count), 0))::numeric, 1) as avg_http_ms,
                    ROUND(MIN(histogram_min)::numeric, 1) as min_http_ms,
                    ROUND(MAX(histogram_max)::numeric, 1) as max_http_ms
                FROM {self.metrics_table}
                WHERE name = 'http.client.duration'
                  {server_filter_metrics}
                  {self._time_filter_metrics(days)}
                GROUP BY hist_http_method, hist_http_status_code
            )
            SELECT 'tool_calls' as section, tc.tool_name, tc.call_status,
                   (tc.total_calls)::text as value1,
                   NULL as value2, NULL as value3, NULL as value4, NULL as value5
            FROM tool_calls tc
            UNION ALL
            SELECT 'tool_latency' as section, tl.tool_name, NULL as call_status,
                   (tl.latency_samples)::text as value1,
                   (tl.avg_latency_ms)::text as value2,
                   (tl.min_latency_ms)::text as value3,
                   (tl.max_latency_ms)::text as value4,
                   NULL as value5
            FROM tool_latency tl
            UNION ALL
            SELECT 'http_duration' as section, hd.method as tool_name, hd.status_code as call_status,
                   (hd.http_samples)::text as value1,
                   (hd.avg_http_ms)::text as value2,
                   (hd.min_http_ms)::text as value3,
                   (hd.max_http_ms)::text as value4,
                   NULL as value5
            FROM http_duration hd
        """.strip()

    # ── Security & Audit Queries ──

    def build_http_outbound_detail(
        self, server: Optional[str] = None, limit: int = 200, days: Optional[float] = None
    ) -> str:
        """Every outbound HTTP span: timestamp, method, full URL, status, duration."""
        return f"""
            SELECT
                start_ts as timestamp,
                http_method as method,
                http_url as url,
                http_status_code::text as status_code,
                duration_ms
            FROM {self.spans_mat}
            WHERE kind = 'SPAN_KIND_CLIENT'
              AND http_method IS NOT NULL
              {self._server_filter(server)}
              {self._time_filter_spans(days)}
            ORDER BY start_ts DESC
            LIMIT {limit}
        """.strip()

    def build_tool_invocations(
        self, server: Optional[str] = None, limit: int = 200, days: Optional[float] = None
    ) -> str:
        """Every tool span: timestamp, tool name, status, duration, trace_id."""
        return f"""
            SELECT
                start_ts as timestamp,
                name as tool_name,
                COALESCE(status_code, 'OK') as status,
                duration_ms,
                trace_id
            FROM {self.spans_mat}
            WHERE kind = 'SPAN_KIND_INTERNAL'
              AND name LIKE 'mcp.tool.%'
              {self._server_filter(server)}
              {self._time_filter_spans(days)}
            ORDER BY start_ts DESC
            LIMIT {limit}
        """.strip()

    def build_error_events(
        self, server: Optional[str] = None, limit: int = 200, days: Optional[float] = None
    ) -> str:
        """Spans with non-success status or HTTP 4xx/5xx."""
        return f"""
            SELECT
                start_ts as timestamp,
                name as span_name,
                kind,
                COALESCE(status_code, 'OK') as status,
                status_message,
                http_status_code::text as http_status,
                duration_ms,
                trace_id
            FROM {self.spans_mat}
            WHERE (
                status_code = 'ERROR'
                OR http_status_code >= 400
            )
            {self._server_filter(server)}
            {self._time_filter_spans(days)}
            ORDER BY start_ts DESC
            LIMIT {limit}
        """.strip()

    # ── Logs Queries ──

    def build_server_logs(
        self, server: Optional[str] = None, limit: int = 200, days: Optional[float] = None
    ) -> str:
        """All log records with tool_name from nearest span. Reads typed columns directly."""
        sf_logs = self._server_filter_logs(server)
        return f"""
            WITH raw_logs AS (
                SELECT
                    to_char(to_timestamp(time_unix_nano::bigint / 1000000000.0), 'YYYY-MM-DD HH24:MI:SS') as timestamp,
                    severity_text as severity,
                    body as body,
                    -- Surface the per-row extracted attribute keys we have available.
                    -- Raw `attributes` map was dropped from the MV; assemble a small JSON
                    -- object so the existing UI cell still renders something useful.
                    json_strip_nulls(json_build_object(
                        'session.id', session_id,
                        'model', model,
                        'tool', tool_name,
                        'type', attr_type,
                        'status', attr_status,
                        'http.method', http_method,
                        'http.status_code', http_status_code,
                        'http.url', http_url
                    ))::text as attributes,
                    trace_id,
                    span_id
                FROM {self.logs_table}
                WHERE 1=1 {sf_logs} {self._time_filter_logs(days)}
                ORDER BY time_unix_nano DESC
                LIMIT {limit}
            ),
            span_tools AS (
                SELECT DISTINCT
                    trace_id,
                    span_id,
                    name as tool_name
                FROM {self.spans_mat}
                WHERE kind = 'SPAN_KIND_INTERNAL'
                  AND name LIKE 'mcp.tool.%'
                  {self._server_filter(server)}
                  {self._time_filter_spans(days)}
            )
            SELECT
                l.timestamp,
                l.severity,
                l.body,
                l.attributes,
                COALESCE(s.tool_name, NULL) as tool_name
            FROM raw_logs l
            LEFT JOIN span_tools s ON l.trace_id = s.trace_id AND l.span_id = s.span_id
            ORDER BY l.timestamp DESC
        """.strip()
