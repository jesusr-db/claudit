from typing import Optional
from fastapi import APIRouter, Query
from backend.config import settings
from backend.services.query_service import QueryService
from backend.services.sql_executor import SqlExecutor

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])

query_service = QueryService(
    catalog=settings.catalog,
    schema=settings.schema_name,
)


def get_executor() -> SqlExecutor:
    return SqlExecutor(warehouse_id=settings.sql_warehouse_id)


@router.get("/performance")
async def get_tool_performance(days: Optional[float] = Query(None, ge=0.01, le=365)):
    query = query_service.build_tool_performance_query(days=days)
    rows = get_executor().execute(query)
    return {"tools": rows}


@router.get("/{tool_name}/calls")
async def get_tool_recent_calls(
    tool_name: str,
    limit: int = Query(50, ge=1, le=200),
):
    query = query_service.build_tool_recent_calls_query(tool_name=tool_name, limit=limit)
    rows = get_executor().execute(query)
    return {"tool_name": tool_name, "calls": rows}
