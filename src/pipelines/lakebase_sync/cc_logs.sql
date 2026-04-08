-- Pre-shaped Claude Code logs with extracted attributes and type casts.
-- Replaces PG materialized views kpi_logs_mat and otel_logs_mat.
-- Filtered to service.name = 'claude-code' at the pipeline level.
CREATE OR REFRESH MATERIALIZED VIEW cc_logs
AS
SELECT
  md5(concat(
    cast(time_unix_nano AS string),
    coalesce(body, ''),
    coalesce(cast(attributes AS string), '')
  )) AS row_id,
  attributes['session.id'] AS session_id,
  attributes['user.id'] AS user_id,
  attributes['prompt.id'] AS prompt_id,
  attributes['event.name'] AS event_name,
  CAST(attributes['event.timestamp'] AS TIMESTAMP) AS event_ts,
  CAST(attributes['event.sequence'] AS INT) AS event_seq,
  resource.attributes['service.name'] AS service_name,
  attributes['model'] AS model,
  CAST(attributes['cost_usd'] AS DOUBLE) AS cost_usd,
  CAST(attributes['input_tokens'] AS BIGINT) AS input_tokens,
  CAST(attributes['output_tokens'] AS BIGINT) AS output_tokens,
  CAST(attributes['cache_read_tokens'] AS BIGINT) AS cache_read_tokens,
  CAST(attributes['cache_creation_tokens'] AS BIGINT) AS cache_creation_tokens,
  CAST(attributes['duration_ms'] AS DOUBLE) AS duration_ms,
  attributes['tool_name'] AS tool_name,
  attributes['success'] AS success,
  attributes['prompt'] AS prompt_text,
  attributes['prompt_length'] AS prompt_length,
  attributes['error'] AS error,
  attributes['status_code'] AS status_code,
  attributes['decision'] AS decision,
  attributes['source'] AS source,
  attributes['speed'] AS speed,
  CAST(attributes['tool_result_size_bytes'] AS BIGINT) AS tool_result_size_bytes,
  attributes['tool_parameters'] AS tool_parameters
FROM ${source_catalog}.${source_schema}.otel_logs
WHERE resource.attributes['service.name'] = 'claude-code'
