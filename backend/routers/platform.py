from typing import Optional
from fastapi import APIRouter, Query
from backend.services.query_service import QueryService
from backend.executors import get_sql_executor

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])

query_service = QueryService()


@router.get("/billing/summary")
async def get_billing_summary(days: int = Query(30, ge=1, le=365)):
    query = query_service.build_billing_summary_query(days=days)
    rows = get_sql_executor().execute(query)
    return {"products": rows, "days": days}


@router.get("/billing/daily")
async def get_billing_daily(days: int = Query(30, ge=1, le=365)):
    query = query_service.build_billing_daily_query(days=days)
    rows = get_sql_executor().execute(query)
    return {"daily": rows, "days": days}


@router.get("/queries/stats")
async def get_query_stats(days: int = Query(7, ge=1, le=90)):
    query = query_service.build_query_history_stats_query(days=days)
    rows = get_sql_executor().execute(query)
    return {"stats": rows, "days": days}


@router.get("/queries/daily")
async def get_query_daily(days: int = Query(7, ge=1, le=90)):
    query = query_service.build_query_history_daily_query(days=days)
    rows = get_sql_executor().execute(query)
    return {"daily": rows, "days": days}


# ── AI Gateway endpoints ─────────────────────────────────────────────


@router.get("/ai-gateway/endpoints")
async def get_ai_gateway_endpoints(
    days: float = Query(7, ge=0.01, le=365),
):
    executor = get_sql_executor()
    query = query_service.build_ai_gateway_endpoints_query(days=days)
    rows = executor.execute(query)
    return {"endpoints": [r["endpoint_name"] for r in rows]}


@router.get("/ai-gateway/overview")
async def get_ai_gateway_overview(
    days: float = Query(7, ge=0.01, le=365),
    endpoint: Optional[str] = Query(None),
):
    executor = get_sql_executor()
    params = {"days": days, "endpoint": endpoint}

    kpis = executor.execute(query_service.build_ai_gateway_overview_kpis_query(**params))
    daily = executor.execute(query_service.build_ai_gateway_overview_daily_query(**params))
    top_endpoints = executor.execute(query_service.build_ai_gateway_overview_top_endpoints_query(**params))
    top_models = executor.execute(query_service.build_ai_gateway_overview_top_models_query(**params))
    top_users = executor.execute(query_service.build_ai_gateway_overview_top_users_query(**params))
    latency_by_endpoint = executor.execute(query_service.build_ai_gateway_overview_latency_by_endpoint_query(**params))

    return {
        "kpis": kpis[0] if kpis else {},
        "daily": daily,
        "top_endpoints": top_endpoints,
        "top_models": top_models,
        "top_users": top_users,
        "latency_by_endpoint": latency_by_endpoint,
    }


@router.get("/ai-gateway/performance")
async def get_ai_gateway_performance(
    days: float = Query(7, ge=0.01, le=365),
    endpoint: Optional[str] = Query(None),
):
    executor = get_sql_executor()
    params = {"days": days, "endpoint": endpoint}

    kpis = executor.execute(query_service.build_ai_gateway_performance_kpis_query(**params))
    latency_by_endpoint = executor.execute(query_service.build_ai_gateway_performance_latency_by_endpoint_query(**params))
    status_codes = executor.execute(query_service.build_ai_gateway_performance_status_codes_query(**params))
    tpm_by_endpoint = executor.execute(query_service.build_ai_gateway_performance_tpm_query(**params))
    ttfb_by_endpoint = executor.execute(query_service.build_ai_gateway_performance_ttfb_by_endpoint_query(**params))
    ttft_loss = executor.execute(query_service.build_ai_gateway_performance_ttft_loss_query(**params))
    errors_by_endpoint = executor.execute(query_service.build_ai_gateway_performance_errors_by_endpoint_query(**params))

    return {
        "kpis": kpis[0] if kpis else {},
        "latency_by_endpoint": latency_by_endpoint,
        "status_codes": status_codes,
        "tpm_by_endpoint": tpm_by_endpoint,
        "ttfb_by_endpoint": ttfb_by_endpoint,
        "ttft_loss": ttft_loss,
        "errors_by_endpoint": errors_by_endpoint,
    }


@router.get("/ai-gateway/usage")
async def get_ai_gateway_usage(
    days: float = Query(7, ge=0.01, le=365),
    endpoint: Optional[str] = Query(None),
):
    executor = get_sql_executor()
    params = {"days": days, "endpoint": endpoint}

    kpis = executor.execute(query_service.build_ai_gateway_usage_kpis_query(**params))
    tokens_by_endpoint = executor.execute(query_service.build_ai_gateway_usage_tokens_by_endpoint_query(**params))
    tokens_by_model = executor.execute(query_service.build_ai_gateway_usage_tokens_by_model_query(**params))
    tokens_by_user = executor.execute(query_service.build_ai_gateway_usage_tokens_by_user_query(**params))
    input_output = executor.execute(query_service.build_ai_gateway_usage_input_output_query(**params))
    cache_hit_by_endpoint = executor.execute(query_service.build_ai_gateway_usage_cache_hit_query(**params))

    return {
        "kpis": kpis[0] if kpis else {},
        "tokens_by_endpoint": tokens_by_endpoint,
        "tokens_by_model": tokens_by_model,
        "tokens_by_user": tokens_by_user,
        "input_output": input_output,
        "cache_hit_by_endpoint": cache_hit_by_endpoint,
    }


@router.get("/ai-gateway/coding-agents")
async def get_ai_gateway_coding_agents(
    days: float = Query(7, ge=0.01, le=365),
    endpoint: Optional[str] = Query(None),
    agent: Optional[str] = Query(None),
):
    executor = get_sql_executor()
    params = {"days": days, "endpoint": endpoint, "agent": agent}

    summary = executor.execute(query_service.build_ai_gateway_coding_agents_summary_query(**params))
    daily = executor.execute(query_service.build_ai_gateway_coding_agents_daily_query(**params))
    by_endpoint = executor.execute(query_service.build_ai_gateway_coding_agents_by_endpoint_query(**params))
    by_model = executor.execute(query_service.build_ai_gateway_coding_agents_by_model_query(**params))
    user_analytics = executor.execute(query_service.build_ai_gateway_coding_agents_user_analytics_query(**params))

    total_requests = sum(int(r.get("requests", 0)) for r in summary)
    total_tokens = sum(int(r.get("total_tokens", 0)) for r in summary)
    unique_users = len({r.get("requester") for r in user_analytics if r.get("requester")})

    return {
        "kpis": {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "unique_users": unique_users,
        },
        "summary": summary,
        "daily": daily,
        "by_endpoint": by_endpoint,
        "by_model": by_model,
        "user_analytics": user_analytics,
    }


@router.get("/ai-gateway/token-consumption")
async def get_ai_gateway_token_consumption(
    days: float = Query(7, ge=0.01, le=365),
    endpoint: Optional[str] = Query(None),
):
    executor = get_sql_executor()
    params = {"days": days, "endpoint": endpoint}

    kpis = executor.execute(query_service.build_ai_gateway_token_consumption_kpis_query(**params))
    daily = executor.execute(query_service.build_ai_gateway_token_consumption_daily_query(**params))
    by_dest_type = executor.execute(query_service.build_ai_gateway_token_consumption_by_dest_type_query(**params))
    weekly_by_endpoint = executor.execute(query_service.build_ai_gateway_token_consumption_weekly_query(**params))
    top_endpoints = executor.execute(query_service.build_ai_gateway_token_consumption_top_endpoints_query(**params))
    top_models = executor.execute(query_service.build_ai_gateway_token_consumption_top_models_query(**params))
    top_users = executor.execute(query_service.build_ai_gateway_token_consumption_top_users_query(**params))

    return {
        "kpis": kpis[0] if kpis else {},
        "daily": daily,
        "by_destination_type": by_dest_type,
        "weekly_by_endpoint": weekly_by_endpoint,
        "top_endpoints": top_endpoints,
        "top_models": top_models,
        "top_users": top_users,
    }
