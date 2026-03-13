from typing import Optional
from fastapi import APIRouter, Query
from backend.services.query_service import QueryService
from backend.cache import cached_execute

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])

query_service = QueryService()


@router.get("/performance")
async def get_tool_performance(days: Optional[float] = Query(None, ge=0.01, le=365)):
    query = query_service.build_tool_performance_query(days=days)
    rows = await cached_execute(f"tool_performance:{days}", query)
    return {"tools": rows}


@router.get("/{tool_name}/calls")
async def get_tool_recent_calls(
    tool_name: str,
    limit: int = Query(50, ge=1, le=200),
):
    query = query_service.build_tool_recent_calls_query(tool_name=tool_name, limit=limit)
    rows = await cached_execute(f"tool_calls:{tool_name}:{limit}", query)
    return {"tool_name": tool_name, "calls": rows}
