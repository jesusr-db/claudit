from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_prefix="", case_sensitive=False)

    catalog: str = "jmr_demo"
    schema_name: str = "zerobus"  # 'schema' is reserved in Pydantic
    sql_warehouse_id: str = ""
    mcp_schema_name: str = "default"  # Schema for MCP server OTEL data

    # Lakebase Provisioned connection settings
    lakebase_instance_name: str = "claudit-db"
    lakebase_database: str = "claudit"

    # PG table names (schema-qualified — used by PgExecutor against Lakebase Provisioned)
    # These are views over synced tables that cast TEXT→JSONB for ->>'key' operator support
    @property
    def otel_logs_table(self) -> str:
        return "zerobus_sdp.otel_logs"

    @property
    def kpi_logs_mat_table(self) -> str:
        """Pre-shaped Claude Code logs from SDP pipeline (synced table)."""
        return "zerobus_sdp.cc_logs_synced"

    @property
    def otel_logs_mat_table(self) -> str:
        """Pre-shaped Claude Code logs from SDP pipeline (same source as kpi_logs_mat)."""
        return "zerobus_sdp.cc_logs_synced"

    @property
    def otel_spans_mat_table(self) -> str:
        """Pre-shaped Claude Code spans from SDP pipeline (synced table)."""
        return "zerobus_sdp.cc_spans_synced"

    @property
    def otel_metrics_table(self) -> str:
        return "zerobus_sdp.otel_metrics"

    @property
    def mcp_otel_spans_table(self) -> str:
        return "zerobus_sdp.otel_spans"

    @property
    def mcp_otel_logs_table(self) -> str:
        return "zerobus_sdp.otel_logs"  # Same source — MCP data is in same logs table

    @property
    def mcp_otel_metrics_table(self) -> str:
        return "zerobus_sdp.otel_metrics"  # Same source — MCP data is in same metrics table

    # System table properties (catalog-qualified, used by SqlExecutor via SQL Warehouse)
    @property
    def billing_usage_table(self) -> str:
        return "system.billing.usage"

    @property
    def query_history_table(self) -> str:
        return "system.query.history"

    @property
    def ai_gateway_usage_table(self) -> str:
        return "system.ai_gateway.usage"

    @property
    def access_audit_table(self) -> str:
        return "system.access.audit"


settings = Settings()
