import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.routers import metrics_router, sessions_router, mcp_tools_router, platform_router, mcp_servers_router, kpis_router
from backend.executors import get_pg_executor

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Claudit Observability",
    description="Claude Code Observability Dashboard API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router)
app.include_router(sessions_router)
app.include_router(mcp_tools_router)
app.include_router(platform_router)
app.include_router(mcp_servers_router)
app.include_router(kpis_router)


@app.get("/health")
async def health_check():
    pg = get_pg_executor()
    if pg is None:
        pg_status = "not_configured"
    else:
        try:
            pg.execute("SELECT 1")
            pg_status = "connected"
        except Exception as e:
            pg_status = f"error: {e}"
    return {"status": "healthy", "lakebase": pg_status}


MATVIEW_REFRESH_INTERVAL = int(os.environ.get("MATVIEW_REFRESH_INTERVAL", "900"))  # seconds, default 15min

MATVIEW_DEFINITIONS = {
    "kpi_logs_mat": {
        "ddl": """
CREATE MATERIALIZED VIEW IF NOT EXISTS zerobus_sdp.kpi_logs_mat AS
SELECT
    row_id,
    (attributes::jsonb->>'session.id') as session_id,
    (attributes::jsonb->>'prompt.id') as prompt_id,
    (attributes::jsonb->>'event.name') as event_name,
    (attributes::jsonb->>'event.timestamp')::timestamp as event_ts,
    (attributes::jsonb->>'event.sequence')::int as event_seq,
    (attributes::jsonb->>'model') as model,
    (attributes::jsonb->>'cost_usd')::double precision as cost_usd,
    (attributes::jsonb->>'input_tokens')::bigint as input_tokens,
    (attributes::jsonb->>'output_tokens')::bigint as output_tokens,
    (attributes::jsonb->>'cache_read_tokens')::bigint as cache_read_tokens,
    (attributes::jsonb->>'duration_ms')::double precision as duration_ms,
    (attributes::jsonb->>'tool_name') as tool_name,
    (attributes::jsonb->>'success') as success,
    (attributes::jsonb->>'prompt') as prompt_text,
    (resource_attributes::jsonb->>'service.name') as service_name
FROM zerobus_sdp.otel_logs_pg_synced
""",
        "indexes": [
            "CREATE INDEX IF NOT EXISTS idx_mat_service_event_ts ON zerobus_sdp.kpi_logs_mat (service_name, event_name, event_ts)",
            "CREATE INDEX IF NOT EXISTS idx_mat_session_prompt ON zerobus_sdp.kpi_logs_mat (session_id, prompt_id)",
            "CREATE INDEX IF NOT EXISTS idx_mat_event_ts ON zerobus_sdp.kpi_logs_mat (event_ts)",
            "CREATE INDEX IF NOT EXISTS idx_mat_session_prompt_seq ON zerobus_sdp.kpi_logs_mat (session_id, prompt_id, event_seq)",
        ],
    },
    "otel_logs_mat": {
        "ddl": """
CREATE MATERIALIZED VIEW IF NOT EXISTS zerobus_sdp.otel_logs_mat AS
SELECT
    row_id,
    (attributes::jsonb->>'session.id') as session_id,
    (attributes::jsonb->>'user.id') as user_id,
    (attributes::jsonb->>'prompt.id') as prompt_id,
    (attributes::jsonb->>'event.name') as event_name,
    (attributes::jsonb->>'event.timestamp')::timestamp as event_ts,
    (attributes::jsonb->>'event.sequence')::int as event_seq,
    (resource_attributes::jsonb->>'service.name') as service_name,
    (attributes::jsonb->>'model') as model,
    (attributes::jsonb->>'cost_usd')::double precision as cost_usd,
    (attributes::jsonb->>'input_tokens')::bigint as input_tokens,
    (attributes::jsonb->>'output_tokens')::bigint as output_tokens,
    (attributes::jsonb->>'cache_read_tokens')::bigint as cache_read_tokens,
    (attributes::jsonb->>'cache_creation_tokens')::bigint as cache_creation_tokens,
    (attributes::jsonb->>'duration_ms')::double precision as duration_ms,
    (attributes::jsonb->>'tool_name') as tool_name,
    (attributes::jsonb->>'success') as success,
    (attributes::jsonb->>'prompt') as prompt_text,
    (attributes::jsonb->>'prompt_length') as prompt_length,
    (attributes::jsonb->>'error') as error,
    (attributes::jsonb->>'status_code') as status_code,
    (attributes::jsonb->>'decision') as decision,
    (attributes::jsonb->>'source') as source,
    (attributes::jsonb->>'speed') as speed,
    (attributes::jsonb->>'tool_result_size_bytes')::bigint as tool_result_size_bytes,
    (attributes::jsonb->>'tool_parameters') as tool_parameters
FROM zerobus_sdp.otel_logs_pg_synced
""",
        "indexes": [
            "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_svc_evt_ts ON zerobus_sdp.otel_logs_mat (service_name, event_name, event_ts)",
            "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_session ON zerobus_sdp.otel_logs_mat (session_id)",
            "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_session_prompt ON zerobus_sdp.otel_logs_mat (session_id, prompt_id)",
            "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_session_prompt_seq ON zerobus_sdp.otel_logs_mat (session_id, prompt_id, event_seq)",
            "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_event_ts ON zerobus_sdp.otel_logs_mat (event_ts)",
            "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_tool ON zerobus_sdp.otel_logs_mat (tool_name) WHERE event_name = 'tool_result'",
            "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_user ON zerobus_sdp.otel_logs_mat (user_id)",
        ],
    },
    "otel_spans_mat": {
        "ddl": """
CREATE MATERIALIZED VIEW IF NOT EXISTS zerobus_sdp.otel_spans_mat AS
SELECT
    row_id,
    name,
    kind,
    trace_id,
    span_id,
    parent_span_id,
    (resource_attributes::jsonb->>'service.name') as service_name,
    to_timestamp(start_time_unix_nano::bigint / 1000000000.0) as start_ts,
    ROUND(((end_time_unix_nano::bigint - start_time_unix_nano::bigint) / 1e6)::numeric, 1) as duration_ms,
    (status::jsonb->>'code') as status_code,
    (status::jsonb->>'message') as status_message,
    (attributes::jsonb->>'http.method') as http_method,
    (attributes::jsonb->>'http.url') as http_url,
    (attributes::jsonb->>'http.status_code')::int as http_status_code,
    (regexp_match(attributes::jsonb->>'http.url', '^(https?://[^/]+)'))[1] as http_domain
FROM zerobus_sdp.otel_spans_pg_synced
""",
        "indexes": [
            "CREATE INDEX IF NOT EXISTS idx_otel_spans_mat_kind_name ON zerobus_sdp.otel_spans_mat (kind, name)",
            "CREATE INDEX IF NOT EXISTS idx_otel_spans_mat_service ON zerobus_sdp.otel_spans_mat (service_name)",
            "CREATE INDEX IF NOT EXISTS idx_otel_spans_mat_start_ts ON zerobus_sdp.otel_spans_mat (start_ts)",
            "CREATE INDEX IF NOT EXISTS idx_otel_spans_mat_trace_span ON zerobus_sdp.otel_spans_mat (trace_id, span_id)",
        ],
    },
}

REFRESH_QUERIES = [
    "REFRESH MATERIALIZED VIEW zerobus_sdp.kpi_logs_mat",
    "REFRESH MATERIALIZED VIEW zerobus_sdp.otel_logs_mat",
    "REFRESH MATERIALIZED VIEW zerobus_sdp.otel_spans_mat",
]


async def _ensure_matviews(pg):
    """Create materialized views and indexes if they don't exist (app SP becomes owner)."""
    for name, spec in MATVIEW_DEFINITIONS.items():
        try:
            await asyncio.to_thread(pg.execute, spec["ddl"], 120000)
            logger.info("Ensured mat view zerobus_sdp.%s exists", name)
            for idx in spec["indexes"]:
                await asyncio.to_thread(pg.execute, idx, 30000)
        except Exception as e:
            logger.warning("Failed to ensure mat view %s: %s", name, e)


async def _refresh_matviews(pg) -> int:
    """Refresh all materialized views, return count of successes."""
    results = await asyncio.gather(
        *[asyncio.to_thread(pg.execute, q, 60000) for q in REFRESH_QUERIES],
        return_exceptions=True,
    )
    ok = sum(1 for r in results if not isinstance(r, Exception))
    for q, r in zip(REFRESH_QUERIES, results):
        if isinstance(r, Exception):
            logger.warning("Failed to refresh %s: %s", q.split()[-1], r)
    return ok


async def _periodic_refresh():
    """Background loop that refreshes materialized views on a fixed interval."""
    while True:
        await asyncio.sleep(MATVIEW_REFRESH_INTERVAL)
        pg = get_pg_executor()
        if pg is None:
            continue
        try:
            ok = await _refresh_matviews(pg)
            logger.info("Periodic mat view refresh: %d/%d views refreshed", ok, len(REFRESH_QUERIES))
            if ok > 0:
                from backend.cache import clear_cache
                clear_cache()
        except Exception as exc:
            logger.warning("Periodic mat view refresh failed: %s", exc)


@app.on_event("startup")
async def warm_cache():
    """Refresh materialized views, pre-fetch common queries, and start periodic refresh."""
    pg = get_pg_executor()
    if pg is None:
        return

    # Ensure mat views exist (app SP becomes owner), then refresh
    await _ensure_matviews(pg)
    ok = await _refresh_matviews(pg)
    logger.info("Mat view refresh: %d/%d views refreshed", ok, len(REFRESH_QUERIES))

    # Pre-fetch common KPI queries
    try:
        from backend.cache import cached_execute
        from backend.services.kpi_query_service import KpiQueryService
        kpi_service = KpiQueryService()
        warmup_queries = {
            "badges:30": kpi_service.build_kpi_badges(days=30),
            "cost_overview:30": kpi_service.build_cost_overview(days=30),
            "effectiveness_overview:30": kpi_service.build_effectiveness_overview(days=30),
            "cost_trend:30": kpi_service.build_cost_trend(days=30),
        }
        results = await asyncio.gather(
            *[cached_execute(k, q) for k, q in warmup_queries.items()],
            return_exceptions=True,
        )
        ok = sum(1 for r in results if not isinstance(r, Exception))
        logger.info("Cache warmup: %d/%d queries pre-fetched", ok, len(warmup_queries))
    except Exception as exc:
        logger.warning("Cache warmup failed: %s", exc)

    # Start periodic materialized view refresh
    asyncio.create_task(_periodic_refresh())


@app.on_event("shutdown")
async def shutdown():
    try:
        from backend.executors import _pg_executor
        if _pg_executor is not None:
            _pg_executor.close()
    except Exception:
        pass


# Serve frontend static files in production
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
