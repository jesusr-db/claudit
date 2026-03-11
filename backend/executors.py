"""Shared executor instances for the app."""
import logging
from backend.config import settings
from backend.services.pg_executor import PgExecutor
from backend.services.sql_executor import SqlExecutor

logger = logging.getLogger(__name__)

# Singleton PgExecutor — initialized on first import
_pg_executor = None


def get_pg_executor() -> PgExecutor:
    global _pg_executor
    if _pg_executor is None:
        _pg_executor = PgExecutor()
    return _pg_executor


def get_sql_executor() -> SqlExecutor:
    return SqlExecutor(warehouse_id=settings.sql_warehouse_id)
