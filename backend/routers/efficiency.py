from fastapi import APIRouter, Query
from backend.services.efficiency_query_service import EfficiencyQueryService
from backend.cache import cached_execute

router = APIRouter(prefix="/api/v1/efficiency", tags=["efficiency"])

_svc = EfficiencyQueryService()


@router.get("/aey")
async def get_aey_overview(days: int = Query(30, ge=1, le=365)):
    query = _svc.build_aey_overview(days=days)
    rows = await cached_execute(f"efficiency_aey:{days}", query)
    return rows[0] if rows else {
        "total_cost_usd": 0,
        "accepted_decisions": 0,
        "cost_per_accepted_decision": None,
    }


@router.get("/cognitive-load")
async def get_cognitive_load(days: int = Query(30, ge=1, le=365)):
    query = _svc.build_cognitive_load_index(days=days)
    rows = await cached_execute(f"efficiency_cognitive_load:{days}", query)
    return rows[0] if rows else {
        "avg_tools_per_prompt": 0,
        "avg_context_thrash": 0,
        "avg_reject_rate": 0,
        "cognitive_load_index": None,
    }


@router.get("/feedback-latency")
async def get_feedback_latency(days: int = Query(30, ge=1, le=365)):
    query = _svc.build_feedback_latency(days=days)
    rows = await cached_execute(f"efficiency_feedback_latency:{days}", query)
    return {"tools": rows, "days": days}


@router.get("/harness-convergence")
async def get_harness_convergence(days: int = Query(30, ge=1, le=365)):
    query = _svc.build_harness_convergence(days=days)
    rows = await cached_execute(f"efficiency_harness_convergence:{days}", query)
    return {"trend": rows, "days": days}


@router.get("/rework-ratio")
async def get_rework_ratio(days: int = Query(30, ge=1, le=365)):
    query = _svc.build_rework_ratio(days=days)
    rows = await cached_execute(f"efficiency_rework_ratio:{days}", query)
    return rows[0] if rows else {
        "avg_rework_ratio": 0,
        "overall_rework_ratio": 0,
        "total_rework_writes": 0,
        "total_writes": 0,
        "sessions_with_writes": 0,
    }
