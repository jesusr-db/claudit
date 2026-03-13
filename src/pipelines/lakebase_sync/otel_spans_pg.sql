-- Materialized view of OTEL spans with synthetic PK and flattened resource/status structs.
-- Adds row_id (md5 hash) for Lakebase sync PK requirement.
CREATE OR REFRESH MATERIALIZED VIEW otel_spans_pg
AS
SELECT
  md5(concat(
    coalesce(trace_id, ''),
    coalesce(span_id, ''),
    coalesce(cast(start_time_unix_nano AS string), '')
  )) AS row_id,
  trace_id,
  span_id,
  trace_state,
  parent_span_id,
  flags,
  name,
  kind,
  start_time_unix_nano,
  end_time_unix_nano,
  to_json(attributes) AS attributes,
  dropped_attributes_count,
  to_json(events) AS events,
  dropped_events_count,
  to_json(links) AS links,
  dropped_links_count,
  to_json(status) AS status,
  to_json(resource.attributes) AS resource_attributes,
  resource_schema_url,
  span_schema_url
FROM ${source_catalog}.${source_schema}.otel_spans
