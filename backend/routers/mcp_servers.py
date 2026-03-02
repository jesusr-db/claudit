from fastapi import APIRouter, Query
from typing import Optional
from backend.config import settings
from backend.services.mcp_query_service import McpQueryService
from backend.services.sql_executor import SqlExecutor

router = APIRouter(prefix="/api/v1/mcp-servers", tags=["mcp-servers"])

query_service = McpQueryService(
    catalog=settings.catalog,
    schema=settings.mcp_schema_name,
)


def get_executor() -> SqlExecutor:
    return SqlExecutor(warehouse_id=settings.sql_warehouse_id)


@router.get("/summary")
async def get_server_summary(
    server: Optional[str] = Query(None),
    days: Optional[float] = Query(None, ge=0.01, le=365),
):
    query = query_service.build_server_summary(server=server, days=days)
    rows = get_executor().execute(query)
    return {"servers": rows}


@router.get("/detail")
async def get_server_detail(
    server: Optional[str] = Query(None),
    days: Optional[float] = Query(None, ge=0.01, le=365),
):
    query = query_service.build_server_detail(server=server, days=days)
    rows = get_executor().execute(query)
    # Reshape flat UNION ALL rows into structured sections
    tool_calls = []
    tool_latency = []
    http_duration = []
    for row in rows:
        section = row.get("section")
        if section == "tool_calls":
            tool_calls.append({
                "tool_name": row["tool_name"],
                "status": row["call_status"],
                "total_calls": row["value1"],
            })
        elif section == "tool_latency":
            tool_latency.append({
                "tool_name": row["tool_name"],
                "samples": row["value1"],
                "avg_latency_ms": row["value2"],
                "min_latency_ms": row["value3"],
                "max_latency_ms": row["value4"],
            })
        elif section == "http_duration":
            http_duration.append({
                "method": row["tool_name"],
                "status_code": row["call_status"],
                "samples": row["value1"],
                "avg_duration_ms": row["value2"],
                "min_duration_ms": row["value3"],
                "max_duration_ms": row["value4"],
            })
    return {
        "tool_calls": tool_calls,
        "tool_latency": tool_latency,
        "http_duration": http_duration,
    }


@router.get("/tools")
async def get_tool_stats(
    server: Optional[str] = Query(None),
    days: Optional[float] = Query(None, ge=0.01, le=365),
):
    query = query_service.build_tool_stats(server=server, days=days)
    rows = get_executor().execute(query)
    return {"tools": rows}


@router.get("/tools/timeline")
async def get_tool_latency_timeline(
    server: Optional[str] = Query(None),
    days: Optional[float] = Query(None, ge=0.01, le=365),
):
    query = query_service.build_tool_latency_over_time(server=server, days=days)
    rows = get_executor().execute(query)
    return {"timeline": rows}


@router.get("/http")
async def get_http_outbound_summary(
    server: Optional[str] = Query(None),
    days: Optional[float] = Query(None, ge=0.01, le=365),
):
    query = query_service.build_http_outbound_summary(server=server, days=days)
    rows = get_executor().execute(query)
    return {"http": rows}


@router.get("/http/detail")
async def get_http_outbound_detail(
    server: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    days: Optional[float] = Query(None, ge=0.01, le=365),
):
    query = query_service.build_http_outbound_detail(server=server, limit=limit, days=days)
    rows = get_executor().execute(query)
    return {"calls": rows}


@router.get("/audit")
async def get_tool_audit(
    server: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    days: Optional[float] = Query(None, ge=0.01, le=365),
):
    query = query_service.build_tool_invocations(server=server, limit=limit, days=days)
    rows = get_executor().execute(query)
    return {"invocations": rows}


@router.get("/errors")
async def get_error_events(
    server: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    days: Optional[float] = Query(None, ge=0.01, le=365),
):
    query = query_service.build_error_events(server=server, limit=limit, days=days)
    rows = get_executor().execute(query)
    return {"errors": rows}


@router.get("/logs")
async def get_server_logs(
    server: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    days: Optional[float] = Query(None, ge=0.01, le=365),
):
    query = query_service.build_server_logs(server=server, limit=limit, days=days)
    rows = get_executor().execute(query)
    return {"logs": rows}
