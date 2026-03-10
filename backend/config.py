from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_prefix="", case_sensitive=False)

    catalog: str = "jmr_demo"
    schema_name: str = "zerobus"  # 'schema' is reserved in Pydantic
    sql_warehouse_id: str = ""
    mcp_schema_name: str = "default"  # Schema for MCP server OTEL data

    # Lakebase connection settings
    lakebase_project_id: str = "claudit-otel"
    lakebase_branch: str = "production"
    lakebase_endpoint: str = "primary"
    lakebase_database: str = "claudit"

    # PG table names (no catalog prefix — used by PgExecutor)
    @property
    def otel_logs_table(self) -> str:
        return "zerobus_otel_logs"

    @property
    def otel_metrics_table(self) -> str:
        return "zerobus_otel_metrics"

    @property
    def mcp_otel_spans_table(self) -> str:
        return "mcp_otel_spans"

    @property
    def mcp_otel_logs_table(self) -> str:
        return "mcp_otel_logs"

    @property
    def mcp_otel_metrics_table(self) -> str:
        return "mcp_otel_metrics"

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
