from typing import Optional


class McpQueryService:
    """Builds SQL queries against MCP server OTEL tables (jmr_demo.default.*).

    Actual schema notes (discovered from live data):
    - Span kind values: SPAN_KIND_INTERNAL (tool spans), SPAN_KIND_CLIENT (HTTP)
    - HTTP attributes (old OTEL conventions): http.method, http.url, http.status_code
    - status struct: {code, message} — code is typically null for success
    - Metric tool attributes: sum.attributes['tool'], sum.attributes['status']
    """

    def __init__(self, catalog: str, schema: str):
        self.catalog = catalog
        self.schema = schema

    @property
    def spans_table(self) -> str:
        return f"{self.catalog}.{self.schema}.otel_spans"

    @property
    def metrics_table(self) -> str:
        return f"{self.catalog}.{self.schema}.otel_metrics"

    @property
    def logs_table(self) -> str:
        return f"{self.catalog}.{self.schema}.otel_logs"

    def _server_filter(self, server: Optional[str]) -> str:
        if server:
            return f"AND resource.attributes['service.name'] = '{server}'"
        return ""

    @staticmethod
    def _time_filter_spans(days: Optional[float]) -> str:
        """Time filter for spans tables (using start_time_unix_nano)."""
        if days is None:
            return ""
        if days < 1:
            minutes = max(int(days * 24 * 60), 5)
            return f"AND TIMESTAMP_MICROS(CAST(start_time_unix_nano / 1000 AS BIGINT)) >= CURRENT_TIMESTAMP() - INTERVAL {minutes} MINUTES"
        return f"AND TIMESTAMP_MICROS(CAST(start_time_unix_nano / 1000 AS BIGINT)) >= CURRENT_TIMESTAMP() - INTERVAL {int(days)} DAYS"

    @staticmethod
    def _time_filter_logs(days: Optional[float]) -> str:
        """Time filter for logs tables (using time_unix_nano)."""
        if days is None:
            return ""
        if days < 1:
            minutes = max(int(days * 24 * 60), 5)
            return f"AND TIMESTAMP_MICROS(CAST(time_unix_nano / 1000 AS BIGINT)) >= CURRENT_TIMESTAMP() - INTERVAL {minutes} MINUTES"
        return f"AND TIMESTAMP_MICROS(CAST(time_unix_nano / 1000 AS BIGINT)) >= CURRENT_TIMESTAMP() - INTERVAL {int(days)} DAYS"

    @staticmethod
    def _time_filter_metrics(days: Optional[float]) -> str:
        """Time filter for metrics tables (using time_unix_nano)."""
        if days is None:
            return ""
        if days < 1:
            minutes = max(int(days * 24 * 60), 5)
            return f"AND TIMESTAMP_MICROS(CAST(time_unix_nano / 1000 AS BIGINT)) >= CURRENT_TIMESTAMP() - INTERVAL {minutes} MINUTES"
        return f"AND TIMESTAMP_MICROS(CAST(time_unix_nano / 1000 AS BIGINT)) >= CURRENT_TIMESTAMP() - INTERVAL {int(days)} DAYS"

    # ── Operations Queries ──

    def build_server_summary(self, server: Optional[str] = None, days: Optional[float] = None) -> str:
        """Distinct service names with tool count, span counts, HTTP call count, log entries."""
        tf_spans = self._time_filter_spans(days)
        tf_logs = self._time_filter_logs(days)
        return f"""
            WITH tool_counts AS (
                SELECT
                    resource.attributes['service.name'] as service_name,
                    COUNT(DISTINCT name) as tool_count,
                    COUNT(*) as tool_spans
                FROM {self.spans_table}
                WHERE kind = 'SPAN_KIND_INTERNAL'
                  AND name LIKE 'mcp.tool.%'
                  {self._server_filter(server)}
                  {tf_spans}
                GROUP BY resource.attributes['service.name']
            ),
            http_counts AS (
                SELECT
                    resource.attributes['service.name'] as service_name,
                    COUNT(*) as http_spans
                FROM {self.spans_table}
                WHERE kind = 'SPAN_KIND_CLIENT'
                  {self._server_filter(server)}
                  {tf_spans}
                GROUP BY resource.attributes['service.name']
            ),
            all_spans AS (
                SELECT
                    resource.attributes['service.name'] as service_name,
                    COUNT(*) as total_spans
                FROM {self.spans_table}
                WHERE 1=1 {self._server_filter(server)} {tf_spans}
                GROUP BY resource.attributes['service.name']
            ),
            log_counts AS (
                SELECT
                    resource.attributes['service.name'] as service_name,
                    COUNT(*) as total_log_entries
                FROM {self.logs_table}
                WHERE 1=1 {self._server_filter(server)} {tf_logs}
                GROUP BY resource.attributes['service.name']
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
                SUM(CASE WHEN status.code IS NULL OR status.code != 'ERROR' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN status.code = 'ERROR' THEN 1 ELSE 0 END) as failure_count,
                ROUND(AVG(
                    (end_time_unix_nano - start_time_unix_nano) / 1e6
                ), 1) as avg_duration_ms,
                ROUND(PERCENTILE(
                    (end_time_unix_nano - start_time_unix_nano) / 1e6, 0.5
                ), 1) as p50_duration_ms,
                ROUND(PERCENTILE(
                    (end_time_unix_nano - start_time_unix_nano) / 1e6, 0.95
                ), 1) as p95_duration_ms
            FROM {self.spans_table}
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
                DATE_TRUNC('hour', TIMESTAMP_MICROS(CAST(start_time_unix_nano / 1000 AS BIGINT))) as time_bucket,
                name as tool_name,
                COUNT(*) as call_count,
                ROUND(AVG(
                    (end_time_unix_nano - start_time_unix_nano) / 1e6
                ), 1) as avg_duration_ms,
                ROUND(PERCENTILE(
                    (end_time_unix_nano - start_time_unix_nano) / 1e6, 0.95
                ), 1) as p95_duration_ms
            FROM {self.spans_table}
            WHERE kind = 'SPAN_KIND_INTERNAL'
              AND name LIKE 'mcp.tool.%'
              {self._server_filter(server)}
              {self._time_filter_spans(days)}
            GROUP BY
                DATE_TRUNC('hour', TIMESTAMP_MICROS(CAST(start_time_unix_nano / 1000 AS BIGINT))),
                name
            ORDER BY time_bucket DESC
        """.strip()

    def build_http_outbound_summary(self, server: Optional[str] = None, days: Optional[float] = None) -> str:
        """Outbound HTTP calls grouped by URL domain + method + status code."""
        return f"""
            SELECT
                REGEXP_EXTRACT(attributes['http.url'], '^(https?://[^/]+)') as domain,
                attributes['http.method'] as method,
                attributes['http.status_code'] as status_code,
                COUNT(*) as call_count,
                ROUND(AVG(
                    (end_time_unix_nano - start_time_unix_nano) / 1e6
                ), 1) as avg_duration_ms,
                ROUND(PERCENTILE(
                    (end_time_unix_nano - start_time_unix_nano) / 1e6, 0.95
                ), 1) as p95_duration_ms
            FROM {self.spans_table}
            WHERE kind = 'SPAN_KIND_CLIENT'
              AND attributes['http.method'] IS NOT NULL
              {self._server_filter(server)}
              {self._time_filter_spans(days)}
            GROUP BY
                REGEXP_EXTRACT(attributes['http.url'], '^(https?://[^/]+)'),
                attributes['http.method'],
                attributes['http.status_code']
            ORDER BY call_count DESC
        """.strip()

    # ── Server Detail (expandable) ──

    def build_server_detail(self, server: Optional[str] = None, days: Optional[float] = None) -> str:
        """Per-tool metrics from mcp.tool.calls counter and mcp.tool.latency histogram."""
        return f"""
            WITH tool_calls AS (
                SELECT
                    sum.attributes['tool'] as tool_name,
                    sum.attributes['status'] as call_status,
                    SUM(CAST(sum.value AS DOUBLE)) as total_calls
                FROM {self.metrics_table}
                WHERE name = 'mcp.tool.calls'
                  {self._server_filter(server)}
                  {self._time_filter_metrics(days)}
                GROUP BY sum.attributes['tool'], sum.attributes['status']
            ),
            tool_latency AS (
                SELECT
                    histogram.attributes['tool'] as tool_name,
                    SUM(histogram.count) as latency_samples,
                    ROUND(SUM(histogram.sum) / NULLIF(SUM(histogram.count), 0), 1) as avg_latency_ms,
                    ROUND(MIN(histogram.min), 1) as min_latency_ms,
                    ROUND(MAX(histogram.max), 1) as max_latency_ms
                FROM {self.metrics_table}
                WHERE name = 'mcp.tool.latency'
                  {self._server_filter(server)}
                  {self._time_filter_metrics(days)}
                GROUP BY histogram.attributes['tool']
            ),
            http_duration AS (
                SELECT
                    histogram.attributes['http.method'] as method,
                    histogram.attributes['http.status_code'] as status_code,
                    SUM(histogram.count) as http_samples,
                    ROUND(SUM(histogram.sum) / NULLIF(SUM(histogram.count), 0), 1) as avg_http_ms,
                    ROUND(MIN(histogram.min), 1) as min_http_ms,
                    ROUND(MAX(histogram.max), 1) as max_http_ms
                FROM {self.metrics_table}
                WHERE name = 'http.client.duration'
                  {self._server_filter(server)}
                  {self._time_filter_metrics(days)}
                GROUP BY histogram.attributes['http.method'], histogram.attributes['http.status_code']
            )
            SELECT 'tool_calls' as section, tc.tool_name, tc.call_status,
                   CAST(tc.total_calls AS STRING) as value1,
                   NULL as value2, NULL as value3, NULL as value4, NULL as value5
            FROM tool_calls tc
            UNION ALL
            SELECT 'tool_latency' as section, tl.tool_name, NULL as call_status,
                   CAST(tl.latency_samples AS STRING) as value1,
                   CAST(tl.avg_latency_ms AS STRING) as value2,
                   CAST(tl.min_latency_ms AS STRING) as value3,
                   CAST(tl.max_latency_ms AS STRING) as value4,
                   NULL as value5
            FROM tool_latency tl
            UNION ALL
            SELECT 'http_duration' as section, hd.method as tool_name, hd.status_code as call_status,
                   CAST(hd.http_samples AS STRING) as value1,
                   CAST(hd.avg_http_ms AS STRING) as value2,
                   CAST(hd.min_http_ms AS STRING) as value3,
                   CAST(hd.max_http_ms AS STRING) as value4,
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
                TIMESTAMP_MICROS(CAST(start_time_unix_nano / 1000 AS BIGINT)) as timestamp,
                attributes['http.method'] as method,
                attributes['http.url'] as url,
                attributes['http.status_code'] as status_code,
                ROUND((end_time_unix_nano - start_time_unix_nano) / 1e6, 1) as duration_ms
            FROM {self.spans_table}
            WHERE kind = 'SPAN_KIND_CLIENT'
              AND attributes['http.method'] IS NOT NULL
              {self._server_filter(server)}
              {self._time_filter_spans(days)}
            ORDER BY start_time_unix_nano DESC
            LIMIT {limit}
        """.strip()

    def build_tool_invocations(
        self, server: Optional[str] = None, limit: int = 200, days: Optional[float] = None
    ) -> str:
        """Every tool span: timestamp, tool name, status, duration, trace_id."""
        return f"""
            SELECT
                TIMESTAMP_MICROS(CAST(start_time_unix_nano / 1000 AS BIGINT)) as timestamp,
                name as tool_name,
                COALESCE(status.code, 'OK') as status,
                ROUND((end_time_unix_nano - start_time_unix_nano) / 1e6, 1) as duration_ms,
                trace_id
            FROM {self.spans_table}
            WHERE kind = 'SPAN_KIND_INTERNAL'
              AND name LIKE 'mcp.tool.%'
              {self._server_filter(server)}
              {self._time_filter_spans(days)}
            ORDER BY start_time_unix_nano DESC
            LIMIT {limit}
        """.strip()

    def build_error_events(
        self, server: Optional[str] = None, limit: int = 200, days: Optional[float] = None
    ) -> str:
        """Spans with non-success status or HTTP 4xx/5xx."""
        return f"""
            SELECT
                TIMESTAMP_MICROS(CAST(start_time_unix_nano / 1000 AS BIGINT)) as timestamp,
                name as span_name,
                kind,
                COALESCE(status.code, 'OK') as status,
                status.message as status_message,
                attributes['http.status_code'] as http_status,
                ROUND((end_time_unix_nano - start_time_unix_nano) / 1e6, 1) as duration_ms,
                trace_id
            FROM {self.spans_table}
            WHERE (
                status.code = 'ERROR'
                OR CAST(attributes['http.status_code'] AS INT) >= 400
            )
            {self._server_filter(server)}
            {self._time_filter_spans(days)}
            ORDER BY start_time_unix_nano DESC
            LIMIT {limit}
        """.strip()

    # ── Logs Queries ──

    def build_server_logs(
        self, server: Optional[str] = None, limit: int = 200, days: Optional[float] = None
    ) -> str:
        """All log records: timestamp, severity, body, attributes, and tool_name from nearest span."""
        return f"""
            WITH raw_logs AS (
                SELECT
                    CAST(DATE_FORMAT(TIMESTAMP_MICROS(CAST(time_unix_nano / 1000 AS BIGINT)), 'yyyy-MM-dd HH:mm:ss') AS STRING) as timestamp,
                    severity_text as severity,
                    body as body,
                    TO_JSON(attributes) as attributes,
                    trace_id,
                    span_id
                FROM {self.logs_table}
                WHERE 1=1 {self._server_filter(server)} {self._time_filter_logs(days)}
                ORDER BY time_unix_nano DESC
                LIMIT {limit}
            ),
            span_tools AS (
                SELECT DISTINCT
                    trace_id,
                    span_id,
                    name as tool_name
                FROM {self.spans_table}
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
