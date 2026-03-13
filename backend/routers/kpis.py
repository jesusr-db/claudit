import asyncio
import logging
import time
from typing import Optional

from fastapi import APIRouter, Query
from backend.services.kpi_query_service import KpiQueryService
from backend.cache import cached_execute, clear_cache
from backend.executors import require_pg_executor, get_sql_executor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/kpis", tags=["kpis"])

kpi_service = KpiQueryService()


# ── Materialized view refresh ──


@router.post("/refresh")
async def refresh_mat_view():
    """Refresh all materialized views and clear the shared cache."""
    t0 = time.monotonic()
    pg = require_pg_executor()

    refresh_queries = [
        kpi_service.build_refresh_mat_view(),
        "REFRESH MATERIALIZED VIEW zerobus_sdp.otel_logs_mat",
        "REFRESH MATERIALIZED VIEW zerobus_sdp.otel_spans_mat",
    ]

    async def _refresh(q):
        await asyncio.to_thread(pg.execute, q, 60000)

    results = await asyncio.gather(
        *[_refresh(q) for q in refresh_queries],
        return_exceptions=True,
    )

    ok = sum(1 for r in results if not isinstance(r, Exception))
    errors = [str(r) for r in results if isinstance(r, Exception)]
    elapsed = (time.monotonic() - t0) * 1000

    clear_cache()

    resp = {"status": "refreshed", "views_refreshed": ok, "total_views": len(refresh_queries), "elapsed_ms": round(elapsed)}
    if errors:
        resp["errors"] = errors
    return resp


# ── Phase 1: Cost Intelligence ──


@router.get("/cost/overview")
async def get_cost_overview(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_cost_overview(days=days)
    rows = await cached_execute(f"cost_overview:{days}", query)
    return rows[0] if rows else {
        "total_cost": 0, "avg_cost_per_session": 0,
        "avg_cost_per_prompt": 0, "cache_hit_pct": 0,
    }


@router.get("/cost/trend")
async def get_cost_trend(days: float = Query(30, ge=0.01, le=365)):
    query = kpi_service.build_cost_trend(days=days)
    rows = await cached_execute(f"cost_trend:{days}", query)
    return {"trend": rows, "days": days}


@router.get("/cost/sessions")
async def get_cost_sessions(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
):
    query = kpi_service.build_cost_by_session(days=days, limit=limit)
    rows = await cached_execute(f"cost_sessions:{days}:{limit}", query)
    return {"sessions": rows, "days": days}


@router.get("/cost/models")
async def get_cost_models(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_model_cost_comparison(days=days)
    rows = await cached_execute(f"cost_models:{days}", query)
    return {"models": rows, "days": days}


@router.get("/cost/waste")
async def get_cost_waste(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_token_waste_signals(days=days)
    rows = await cached_execute(f"cost_waste:{days}", query)
    return {"waste": rows, "days": days}


# ── Phase 2: Agent Effectiveness ──


@router.get("/effectiveness/overview")
async def get_effectiveness_overview(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_effectiveness_overview(days=days)
    rows = await cached_execute(f"effectiveness_overview:{days}", query)
    return rows[0] if rows else {
        "tool_success_rate": 0, "avg_tools_per_prompt": 0,
        "avg_api_calls_per_prompt": 0, "total_errors": 0,
        "total_prompts": 0, "total_tool_calls": 0,
    }


@router.get("/effectiveness/retries")
async def get_effectiveness_retries(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_tool_retry_analysis(days=days)
    rows = await cached_execute(f"effectiveness_retries:{days}", query)
    return {"retries": rows, "days": days}


@router.get("/effectiveness/orphans")
async def get_effectiveness_orphans(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_orphan_decisions(days=days)
    rows = await cached_execute(f"effectiveness_orphans:{days}", query)
    return {"orphans": rows, "days": days}


@router.get("/effectiveness/recovery")
async def get_effectiveness_recovery(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_error_recovery_patterns(days=days)
    rows = await cached_execute(f"effectiveness_recovery:{days}", query)
    return {"recovery": rows, "days": days}


@router.get("/effectiveness/complexity")
async def get_effectiveness_complexity(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_prompt_complexity_distribution(days=days)
    rows = await cached_execute(f"effectiveness_complexity:{days}", query)
    return {"complexity": rows, "days": days}


# ── Phase 3: Flow Correlation ──


@router.get("/flow/summary")
async def get_flow_summary(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_e2e_flow_summary(days=days)
    rows = await cached_execute(f"flow_summary:{days}", query)
    return {"flows": rows, "days": days}


@router.get("/flow/audit")
async def get_flow_audit(days: int = Query(7, ge=1, le=90)):
    query = kpi_service.build_uc_connection_audit(days=days)
    rows = await asyncio.to_thread(get_sql_executor().execute, query)
    return {"audit": rows, "days": days}


# ── Phase 4: Model Efficiency ──


@router.get("/efficiency/matrix")
async def get_efficiency_matrix(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_model_performance_matrix(days=days)
    rows = await cached_execute(f"efficiency_matrix:{days}", query)
    return {"matrix": rows, "days": days}


@router.get("/efficiency/rightsizing")
async def get_efficiency_rightsizing(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_rightsizing_opportunities(days=days)
    rows = await cached_execute(f"efficiency_rightsizing:{days}", query)
    return {"opportunities": rows, "days": days}


@router.get("/efficiency/rightsizing/details")
async def get_efficiency_rightsizing_details(
    days: int = Query(30, ge=1, le=365),
    model: Optional[str] = Query(None),
    complexity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    query = kpi_service.build_rightsizing_details(
        days=days, model=model or "", complexity=complexity or "", limit=limit
    )
    rows = await cached_execute(f"efficiency_rightsizing_details:{days}:{model}:{complexity}:{limit}", query)
    return {"details": rows, "days": days, "model": model, "complexity": complexity}


@router.get("/efficiency/recommendations")
async def get_efficiency_recommendations(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_model_recommendation(days=days)
    rows = await cached_execute(f"efficiency_recommendations:{days}", query)
    return {"recommendations": rows, "days": days}


@router.get("/efficiency/savings")
async def get_efficiency_savings(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_savings_calculator(days=days)
    rows = await cached_execute(f"efficiency_savings:{days}", query)
    return {"savings": rows, "days": days}


# ── Badges ──


@router.get("/badges")
async def get_kpi_badges(days: int = Query(30, ge=1, le=365)):
    query = kpi_service.build_kpi_badges(days=days)
    rows = await cached_execute(f"badges:{days}", query)
    return rows[0] if rows else {
        "cache_hit_pct": 0, "cost_trend_direction": "flat",
        "tool_success_rate": 0, "avg_turnaround_sec": 0,
    }
