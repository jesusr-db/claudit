-- Materialized view of OTEL metrics with synthetic PK and pre-extracted typed columns.
-- The Delta MV is shaped so the synced PG table is consumed directly by the app — no
-- PG views, no JSONB casting.
-- Adds row_id (md5 hash) for Lakebase sync PK requirement.
-- Deduplicates by row_id to guard against duplicate source events.
--
-- IMPORTANT: filtered to only the metric names the app actually queries. The full source
-- contains 26M+ rows of infrastructure noise (process.cpu, system.disk, etc.) that we
-- never read. Restricting here drops the synced PG table from 26.5M rows to ~94K.
CREATE OR REFRESH MATERIALIZED VIEW otel_metrics_pg
AS
WITH hashed AS (
  SELECT
    md5(concat(
      coalesce(name, ''),
      coalesce(metric_type, ''),
      coalesce(cast(sum AS string), ''),
      coalesce(cast(gauge AS string), ''),
      coalesce(cast(histogram AS string), ''),
      coalesce(cast(resource AS string), '')
    )) AS row_id,
    -- Resource (typed)
    resource.attributes['service.name'] AS service_name,
    -- Core metric fields
    name,
    description,
    unit,
    metric_type,
    -- Sum branch (counters: token usage, cost usage, mcp.tool.calls)
    sum.start_time_unix_nano AS sum_start_time_unix_nano,
    sum.time_unix_nano AS sum_time_unix_nano,
    sum.value AS sum_value,
    sum.attributes['session.id'] AS sum_session_id,
    sum.attributes['model'] AS sum_model,
    sum.attributes['type'] AS sum_type,
    sum.attributes['tool'] AS sum_tool,
    sum.attributes['status'] AS sum_status,
    -- Histogram branch (latency: mcp.tool.latency, http.client.duration)
    histogram.start_time_unix_nano AS histogram_start_time_unix_nano,
    histogram.time_unix_nano AS histogram_time_unix_nano,
    histogram.count AS histogram_count,
    histogram.sum AS histogram_sum,
    histogram.min AS histogram_min,
    histogram.max AS histogram_max,
    histogram.attributes['tool'] AS hist_tool,
    histogram.attributes['http.method'] AS hist_http_method,
    histogram.attributes['http.status_code'] AS hist_http_status_code,
    -- Gauge branch (kept structurally even if unused today)
    gauge.value AS gauge_value,
    gauge.time_unix_nano AS gauge_time_unix_nano,
    -- Schema URLs
    resource_schema_url,
    metric_schema_url
  FROM ${source_catalog}.${source_schema}.otel_metrics
  WHERE name IN (
      'claude_code.token.usage',
      'claude_code.cost.usage',
      'mcp.tool.calls',
      'mcp.tool.latency',
      'http.client.duration'
    )
    AND coalesce(sum.time_unix_nano, histogram.time_unix_nano, gauge.time_unix_nano) >=
        (unix_timestamp(current_timestamp() - INTERVAL 30 DAYS) * 1000000000)
)
SELECT * EXCEPT (_rn) FROM (
  SELECT *, ROW_NUMBER() OVER (
    PARTITION BY row_id
    ORDER BY coalesce(sum_time_unix_nano, histogram_time_unix_nano, 0)
  ) AS _rn
  FROM hashed
) WHERE _rn = 1
