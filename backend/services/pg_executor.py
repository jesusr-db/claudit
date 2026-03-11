import logging
import threading
import time
import uuid
from typing import List, Dict, Any, Optional

from databricks.sdk import WorkspaceClient
from psycopg_pool import ConnectionPool

from backend.config import settings

logger = logging.getLogger(__name__)

_TOKEN_REFRESH_INTERVAL_SECONDS = 50 * 60  # 50 minutes (tokens expire at 1 hour)
_STARTUP_MAX_RETRIES = 5
_STARTUP_BACKOFF_BASE = 2  # seconds


class PgExecutor:
    """Executes SQL against Lakebase Provisioned (PostgreSQL) via psycopg v3 connection pool.

    Same interface as SqlExecutor: execute(query) -> List[Dict[str, Any]].
    Uses OAuth tokens from Databricks SDK, refreshed every 50 minutes in the background.
    """

    def __init__(self):
        self._client: Optional[WorkspaceClient] = None
        self._token: Optional[str] = None
        self._conninfo: Optional[str] = None
        self._pool: Optional[ConnectionPool] = None
        self._refresh_timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._initialize()

    @property
    def client(self) -> WorkspaceClient:
        if self._client is None:
            self._client = WorkspaceClient()
        return self._client

    def _get_endpoint_conninfo(self) -> str:
        """Retrieve instance hostname from Databricks SDK and build conninfo string."""
        instance = self.client.database.get_database_instance(settings.lakebase_instance_name)
        host = instance.read_write_dns
        dbname = settings.lakebase_database
        user = self.client.current_user.me().user_name
        return f"host={host} port=5432 dbname={dbname} user={user} sslmode=require"

    def _generate_token(self) -> str:
        """Generate a new OAuth token via Databricks SDK."""
        credential = self.client.database.generate_database_credential(
            request_id=str(uuid.uuid4()),
            instance_names=[settings.lakebase_instance_name],
        )
        return credential.token

    def _create_pool(self, conninfo: str, token: str) -> ConnectionPool:
        """Create a psycopg ConnectionPool with the OAuth token as password."""
        full_conninfo = f"{conninfo} password={token}"
        pool = ConnectionPool(
            conninfo=full_conninfo,
            min_size=2,
            max_size=10,
            open=True,
            reconnect_failed=self._on_reconnect_failed,
        )
        return pool

    def _on_reconnect_failed(self, pool) -> None:
        logger.error("PgExecutor: connection pool failed to reconnect — will retry on next request")

    def _initialize(self) -> None:
        """Fetch endpoint info, generate token, create pool, schedule token refresh."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, _STARTUP_MAX_RETRIES + 1):
            try:
                logger.info("PgExecutor: initializing (attempt %d/%d)", attempt, _STARTUP_MAX_RETRIES)
                self._conninfo = self._get_endpoint_conninfo()
                self._token = self._generate_token()
                self._pool = self._create_pool(self._conninfo, self._token)
                logger.info("PgExecutor: initialized successfully")
                self._schedule_refresh()
                return
            except Exception as exc:
                last_exc = exc
                wait = _STARTUP_BACKOFF_BASE ** attempt
                logger.warning(
                    "PgExecutor: initialization attempt %d failed: %s — retrying in %ds",
                    attempt,
                    exc,
                    wait,
                )
                time.sleep(wait)

        logger.error(
            "PgExecutor: all %d initialization attempts failed: %s",
            _STARTUP_MAX_RETRIES,
            last_exc,
        )
        raise RuntimeError(f"PgExecutor failed to initialize after {_STARTUP_MAX_RETRIES} attempts") from last_exc

    def _schedule_refresh(self) -> None:
        """Schedule the next token refresh in 50 minutes."""
        self._refresh_timer = threading.Timer(
            _TOKEN_REFRESH_INTERVAL_SECONDS,
            self._refresh_token,
        )
        self._refresh_timer.daemon = True
        self._refresh_timer.start()

    def _refresh_token(self) -> None:
        """Refresh OAuth token and recreate pool with new credentials."""
        max_retries = 3
        backoff = 5  # seconds
        for attempt in range(1, max_retries + 1):
            try:
                logger.info("PgExecutor: refreshing OAuth token (attempt %d/%d)", attempt, max_retries)
                new_token = self._generate_token()

                old_pool = self._pool
                new_pool = self._create_pool(self._conninfo, new_token)

                with self._lock:
                    self._token = new_token
                    self._pool = new_pool

                # Close old pool gracefully after swapping
                if old_pool is not None:
                    try:
                        old_pool.close()
                    except Exception as close_exc:
                        logger.warning("PgExecutor: error closing old pool: %s", close_exc)

                logger.info("PgExecutor: OAuth token refreshed successfully")
                self._schedule_refresh()
                return
            except Exception as exc:
                logger.error(
                    "PgExecutor: token refresh attempt %d/%d failed: %s",
                    attempt,
                    max_retries,
                    exc,
                )
                if attempt < max_retries:
                    time.sleep(backoff * attempt)

        logger.error("PgExecutor: all token refresh attempts failed — pool will use expired token until next retry")
        # Schedule another refresh sooner (5 minutes) to retry
        self._refresh_timer = threading.Timer(5 * 60, self._refresh_token)
        self._refresh_timer.daemon = True
        self._refresh_timer.start()

    def execute(self, query: str, timeout_ms: int = 25000) -> List[Dict[str, Any]]:
        """Execute a SQL query and return rows as a list of dicts.

        Args:
            timeout_ms: Statement timeout in milliseconds (default 25s).
                        Prevents queries from running until proxy timeout (30s).
        """
        with self._lock:
            pool = self._pool

        if pool is None:
            raise RuntimeError("PgExecutor: connection pool is not initialized")

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = {timeout_ms}")
                cur.execute(query)
                if cur.description is None:
                    return []
                columns = [desc.name for desc in cur.description]
                rows = cur.fetchall()
                return [dict(zip(columns, row)) for row in rows]

    def close(self) -> None:
        """Shut down the pool and cancel the refresh timer."""
        if self._refresh_timer is not None:
            self._refresh_timer.cancel()
            self._refresh_timer = None

        if self._pool is not None:
            try:
                self._pool.close()
            except Exception as exc:
                logger.warning("PgExecutor: error closing pool on shutdown: %s", exc)
            self._pool = None

        logger.info("PgExecutor: shut down cleanly")
