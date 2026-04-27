-- Pre-shaped Claude Code spans with extracted attributes and computed fields.
-- Replaces PG materialized view otel_spans_mat.
-- Filtered to service.name = 'claude-code' at the pipeline level.
-- Deduplicates by row_id to guard against duplicate source events.
CREATE OR REFRESH MATERIALIZED VIEW cc_spans
AS
WITH hashed AS (
  SELECT
    md5(concat(
      coalesce(trace_id, ''),
      coalesce(span_id, ''),
      coalesce(cast(start_time_unix_nano AS string), '')
    )) AS row_id,
    name,
    kind,
    trace_id,
    span_id,
    parent_span_id,
    resource.attributes['service.name'] AS service_name,
    CAST(start_time_unix_nano / 1000000000.0 AS TIMESTAMP) AS start_ts,
    ROUND(CAST((end_time_unix_nano - start_time_unix_nano) / 1e6 AS DOUBLE), 1) AS duration_ms,
    status.code AS status_code,
    status.message AS status_message,
    attributes['http.method'] AS http_method,
    attributes['http.url'] AS http_url,
    CAST(attributes['http.status_code'] AS INT) AS http_status_code,
    regexp_extract(attributes['http.url'], '^(https?://[^/]+)', 1) AS http_domain,
    start_time_unix_nano
  FROM ${source_catalog}.${source_schema}.otel_spans
  WHERE resource.attributes['service.name'] = 'claude-code'
    AND start_time_unix_nano >= (unix_timestamp(current_timestamp() - INTERVAL 30 DAYS) * 1000000000)
)
SELECT * EXCEPT (_rn, start_time_unix_nano) FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY row_id ORDER BY start_time_unix_nano) AS _rn
  FROM hashed
) WHERE _rn = 1
