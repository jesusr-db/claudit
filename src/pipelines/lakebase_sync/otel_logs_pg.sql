-- Materialized view of OTEL logs with synthetic PK and flattened resource struct.
-- Adds row_id (md5 hash) for Lakebase sync PK requirement.
-- Converts MAP<string,string> columns to JSON strings for JSONB in PG.
CREATE OR REFRESH MATERIALIZED VIEW otel_logs_pg
AS
SELECT
  md5(concat(
    cast(time_unix_nano AS string),
    coalesce(body, ''),
    coalesce(cast(attributes AS string), '')
  )) AS row_id,
  event_name,
  trace_id,
  span_id,
  time_unix_nano,
  observed_time_unix_nano,
  severity_number,
  severity_text,
  body,
  to_json(attributes) AS attributes,
  dropped_attributes_count,
  flags,
  to_json(resource.attributes) AS resource_attributes,
  resource_schema_url,
  log_schema_url
FROM ${source_catalog}.${source_schema}.otel_logs
