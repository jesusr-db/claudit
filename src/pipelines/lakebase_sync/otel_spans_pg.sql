-- Materialized view of OTEL spans with synthetic PK and pre-extracted typed columns.
-- The Delta MV is shaped so the synced PG table is consumed directly by the app — no
-- PG views, no JSONB casting. Mirrors the cc_spans.sql pattern but for ALL services
-- (claude-code + MCP servers).
-- Adds row_id (md5 hash) for Lakebase sync PK requirement.
-- Deduplicates by row_id to guard against duplicate source events.
CREATE OR REFRESH MATERIALIZED VIEW otel_spans_pg
AS
WITH hashed AS (
  SELECT
    md5(concat(
      coalesce(trace_id, ''),
      coalesce(span_id, ''),
      coalesce(cast(start_time_unix_nano AS string), ''),
      coalesce(cast(end_time_unix_nano AS string), ''),
      coalesce(name, '')
    )) AS row_id,
    -- Resource (typed)
    resource.attributes['service.name'] AS service_name,
    -- Core span fields
    trace_id,
    span_id,
    trace_state,
    parent_span_id,
    flags,
    name,
    kind,
    start_time_unix_nano,
    end_time_unix_nano,
    -- Status struct flattened
    status.code AS status_code,
    status.message AS status_message,
    -- Pre-extracted attribute keys
    attributes['http.method'] AS http_method,
    CAST(attributes['http.status_code'] AS INT) AS http_status_code,
    attributes['http.url'] AS http_url,
    regexp_extract(attributes['http.url'], '^(https?://[^/]+)', 1) AS http_domain,
    -- Counters
    dropped_attributes_count,
    dropped_events_count,
    dropped_links_count,
    -- Schema URLs
    resource_schema_url,
    span_schema_url
  FROM ${source_catalog}.${source_schema}.otel_spans
  WHERE start_time_unix_nano >= (unix_timestamp(current_timestamp() - INTERVAL 30 DAYS) * 1000000000)
)
SELECT * EXCEPT (_rn) FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY row_id ORDER BY start_time_unix_nano) AS _rn
  FROM hashed
) WHERE _rn = 1
