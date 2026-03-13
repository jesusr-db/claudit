-- Materialized view of OTEL metrics with synthetic PK and flattened sum/histogram/gauge structs.
-- Adds row_id (md5 hash) for Lakebase sync PK requirement.
CREATE OR REFRESH MATERIALIZED VIEW otel_metrics_pg
AS
SELECT
  md5(concat(
    name,
    coalesce(metric_type, ''),
    coalesce(cast(sum AS string), ''),
    coalesce(cast(gauge AS string), ''),
    coalesce(cast(histogram AS string), ''),
    coalesce(cast(resource AS string), '')
  )) AS row_id,
  name,
  description,
  unit,
  metric_type,
  -- Sum fields (token usage, cost metrics)
  sum.start_time_unix_nano AS sum_start_time_unix_nano,
  sum.time_unix_nano AS sum_time_unix_nano,
  sum.value AS sum_value,
  to_json(sum.attributes) AS sum_attributes,
  -- Histogram fields (latency metrics)
  histogram.start_time_unix_nano AS histogram_start_time_unix_nano,
  histogram.time_unix_nano AS histogram_time_unix_nano,
  histogram.count AS histogram_count,
  histogram.sum AS histogram_sum,
  histogram.min AS histogram_min,
  histogram.max AS histogram_max,
  to_json(histogram.attributes) AS histogram_attributes,
  -- Gauge fields
  gauge.value AS gauge_value,
  to_json(gauge.attributes) AS gauge_attributes,
  -- Resource
  to_json(resource.attributes) AS resource_attributes,
  resource_schema_url,
  metric_schema_url
FROM ${source_catalog}.${source_schema}.otel_metrics
