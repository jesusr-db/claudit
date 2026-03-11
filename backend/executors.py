"""Shared executor instances for the app."""
import logging
from typing import Optional
from fastapi import HTTPException
from backend.config import settings
from backend.services.sql_executor import SqlExecutor

logger = logging.getLogger(__name__)

# Singleton PgExecutor — initialized on first call
_pg_executor = None
_pg_init_failed = False


def get_pg_executor():
    """Get the PgExecutor singleton. Returns None if Lakebase is not available."""
    global _pg_executor, _pg_init_failed
    if _pg_executor is not None:
        return _pg_executor
    if _pg_init_failed:
        return None
    try:
        from backend.services.pg_executor import PgExecutor
        _pg_executor = PgExecutor()
        return _pg_executor
    except Exception as e:
        logger.warning("PgExecutor not available (Lakebase may not be provisioned): %s", e)
        _pg_init_failed = True
        return None


def require_pg_executor():
    """Get PgExecutor or raise HTTP 503 if Lakebase not available."""
    pg = get_pg_executor()
    if pg is None:
        raise HTTPException(status_code=503, detail="Lakebase not configured — OTEL queries unavailable")
    return pg


def get_sql_executor() -> SqlExecutor:
    return SqlExecutor(warehouse_id=settings.sql_warehouse_id)
