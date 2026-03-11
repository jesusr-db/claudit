from typing import Optional
from fastapi import APIRouter, Query
from backend.config import settings
from backend.services.query_service import QueryService
from backend.services.sql_executor import SqlExecutor

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])

query_service = QueryService()


def get_executor() -> SqlExecutor:
    return SqlExecutor(warehouse_id=settings.sql_warehouse_id)


@router.get("/billing/summary")
async def get_billing_summary(days: int = Query(30, ge=1, le=365)):
    query = query_service.build_billing_summary_query(days=days)
    rows = get_executor().execute(query)
    return {"products": rows, "days": days}


@router.get("/billing/daily")
async def get_billing_daily(days: int = Query(30, ge=1, le=365)):
    query = query_service.build_billing_daily_query(days=days)
    rows = get_executor().execute(query)
    return {"daily": rows, "days": days}


@router.get("/queries/stats")
async def get_query_stats(days: int = Query(7, ge=1, le=90)):
    query = query_service.build_query_history_stats_query(days=days)
    rows = get_executor().execute(query)
    return {"stats": rows, "days": days}


@router.get("/queries/daily")
async def get_query_daily(days: int = Query(7, ge=1, le=90)):
    query = query_service.build_query_history_daily_query(days=days)
    rows = get_executor().execute(query)
    return {"daily": rows, "days": days}


@router.get("/ai-gateway/models")
async def get_ai_gateway_models(days: float = Query(7, ge=0.01, le=365)):
    query = query_service.build_ai_gateway_model_stats_query(days=days)
    rows = get_executor().execute(query)
    return {"models": rows, "days": days}


@router.get("/ai-gateway/daily")
async def get_ai_gateway_daily(days: float = Query(7, ge=0.01, le=365)):
    query = query_service.build_ai_gateway_daily_query(days=days)
    rows = get_executor().execute(query)
    return {"daily": rows, "days": days}


@router.get("/ai-gateway/errors")
async def get_ai_gateway_errors(days: float = Query(7, ge=0.01, le=365)):
    query = query_service.build_ai_gateway_errors_query(days=days)
    rows = get_executor().execute(query)
    return {"errors": rows, "days": days}
