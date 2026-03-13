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


@app.on_event("startup")
async def warm_cache():
    """Refresh materialized views and pre-fetch common queries to warm the cache on startup."""
    pg = get_pg_executor()
    if pg is None:
        return

    # Refresh all materialized views first
    refresh_queries = [
        "REFRESH MATERIALIZED VIEW zerobus_sdp.kpi_logs_mat",
        "REFRESH MATERIALIZED VIEW zerobus_sdp.otel_logs_mat",
        "REFRESH MATERIALIZED VIEW zerobus_sdp.otel_spans_mat",
    ]
    refresh_results = await asyncio.gather(
        *[asyncio.to_thread(pg.execute, q, 60000) for q in refresh_queries],
        return_exceptions=True,
    )
    ok = sum(1 for r in refresh_results if not isinstance(r, Exception))
    logger.info("Mat view refresh: %d/%d views refreshed", ok, len(refresh_queries))

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
