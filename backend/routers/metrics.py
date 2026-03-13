from fastapi import APIRouter, Query
from typing import Optional
from backend.services.query_service import QueryService
from backend.cache import cached_execute

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])

query_service = QueryService()


@router.get("/summary")
async def get_summary(days: Optional[float] = Query(None, ge=0.01, le=365)):
    query = query_service.build_summary_query(days=days)
    rows = await cached_execute(f"summary:{days}", query)
    return rows[0] if rows else {}


@router.get("/usage")
async def get_token_usage(session_id: Optional[str] = Query(None)):
    query = query_service.build_token_usage_query(session_id=session_id)
    rows = await cached_execute(f"token_usage:{session_id}", query)
    return {"usage": rows}


@router.get("/costs")
async def get_cost_usage(session_id: Optional[str] = Query(None)):
    query = query_service.build_cost_usage_query(session_id=session_id)
    rows = await cached_execute(f"cost_usage:{session_id}", query)
    return {"costs": rows}


@router.get("/tools")
async def get_tool_stats(
    session_id: Optional[str] = Query(None),
    mcp_only: bool = Query(False),
):
    query = query_service.build_tool_stats_query(
        session_id=session_id, mcp_only=mcp_only
    )
    rows = await cached_execute(f"tool_stats:{session_id}:{mcp_only}", query)
    return {"tools": rows}


@router.get("/errors")
async def get_error_stats(session_id: Optional[str] = Query(None)):
    query = query_service.build_error_stats_query(session_id=session_id)
    rows = await cached_execute(f"error_stats:{session_id}", query)
    return {"errors": rows}


@router.get("/performance")
async def get_api_performance(session_id: Optional[str] = Query(None)):
    query = query_service.build_api_performance_query(session_id=session_id)
    rows = await cached_execute(f"api_performance:{session_id}", query)
    return {"performance": rows}
