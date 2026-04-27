-- Materialized view of OTEL logs with synthetic PK and pre-extracted typed columns.
-- The Delta MV is shaped so the synced PG table is consumed directly by the app — no
-- PG views, no JSONB casting. Mirrors the cc_logs.sql pattern but for ALL services
-- (claude-code + MCP servers).
-- Adds row_id (md5 hash) for Lakebase sync PK requirement.
-- Deduplicates by row_id to guard against duplicate source events.
CREATE OR REFRESH MATERIALIZED VIEW otel_logs_pg
AS
WITH hashed AS (
  SELECT
    md5(concat(
      coalesce(cast(time_unix_nano AS string), ''),
      coalesce(cast(observed_time_unix_nano AS string), ''),
      coalesce(trace_id, ''),
      coalesce(span_id, ''),
      coalesce(body, ''),
      coalesce(cast(attributes AS string), '')
    )) AS row_id,
    -- Resource fields (typed)
    resource.attributes['service.name'] AS service_name,
    -- Core OTEL fields
    event_name,
    trace_id,
    span_id,
    time_unix_nano,
    observed_time_unix_nano,
    severity_number,
    severity_text,
    body,
    -- Pre-extracted attribute keys (drives every query the app issues against this table)
    attributes['session.id'] AS session_id,
    attributes['model'] AS model,
    attributes['tool'] AS tool_name,
    attributes['type'] AS attr_type,
    attributes['status'] AS attr_status,
    attributes['http.method'] AS http_method,
    CAST(attributes['http.status_code'] AS INT) AS http_status_code,
    attributes['http.url'] AS http_url,
    -- Schema URLs (small TEXT, kept for completeness)
    resource_schema_url,
    log_schema_url
  FROM ${source_catalog}.${source_schema}.otel_logs
  WHERE time_unix_nano >= (unix_timestamp(current_timestamp() - INTERVAL 30 DAYS) * 1000000000)
)
SELECT * EXCEPT (_rn) FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY row_id ORDER BY time_unix_nano) AS _rn
  FROM hashed
) WHERE _rn = 1
