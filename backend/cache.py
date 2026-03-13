"""Shared TTL cache for expensive PG queries across all routers."""

import asyncio
import logging
import time

from cachetools import TTLCache

from backend.executors import require_pg_executor

logger = logging.getLogger(__name__)

_cache: TTLCache = TTLCache(maxsize=256, ttl=60)


def _execute_sync(cache_key: str, query: str) -> list:
    """Execute query with TTL cache (synchronous, called from thread)."""
    if cache_key in _cache:
        return _cache[cache_key]

    t0 = time.monotonic()
    rows = require_pg_executor().execute(query)
    elapsed = (time.monotonic() - t0) * 1000
    logger.info("PG query %s: %.0fms (%d rows)", cache_key, elapsed, len(rows))
    _cache[cache_key] = rows
    return rows


async def cached_execute(cache_key: str, query: str) -> list:
    """Execute query off the event loop via thread pool, with TTL cache."""
    return await asyncio.to_thread(_execute_sync, cache_key, query)


def clear_cache():
    """Clear the entire cache (used by refresh endpoints)."""
    _cache.clear()
