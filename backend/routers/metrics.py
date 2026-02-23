from fastapi import APIRouter, Query
from typing import Optional
from backend.config import settings
from backend.services.query_service import QueryService
from backend.services.sql_executor import SqlExecutor

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])

query_service = QueryService(
    catalog=settings.catalog,
    schema=settings.schema_name,
)


def get_executor() -> SqlExecutor:
    return SqlExecutor(warehouse_id=settings.sql_warehouse_id)


@router.get("/summary")
async def get_summary():
    query = query_service.build_summary_query()
    rows = get_executor().execute(query)
    return rows[0] if rows else {}


@router.get("/usage")
async def get_token_usage(session_id: Optional[str] = Query(None)):
    query = query_service.build_token_usage_query(session_id=session_id)
    rows = get_executor().execute(query)
    return {"usage": rows}


@router.get("/costs")
async def get_cost_usage(session_id: Optional[str] = Query(None)):
    query = query_service.build_cost_usage_query(session_id=session_id)
    rows = get_executor().execute(query)
    return {"costs": rows}


@router.get("/tools")
async def get_tool_stats(
    session_id: Optional[str] = Query(None),
    mcp_only: bool = Query(False),
):
    query = query_service.build_tool_stats_query(
        session_id=session_id, mcp_only=mcp_only
    )
    rows = get_executor().execute(query)
    return {"tools": rows}


@router.get("/errors")
async def get_error_stats(session_id: Optional[str] = Query(None)):
    query = query_service.build_error_stats_query(session_id=session_id)
    rows = get_executor().execute(query)
    return {"errors": rows}


@router.get("/performance")
async def get_api_performance(session_id: Optional[str] = Query(None)):
    query = query_service.build_api_performance_query(session_id=session_id)
    rows = get_executor().execute(query)
    return {"performance": rows}
