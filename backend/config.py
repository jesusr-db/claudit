from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_prefix="", case_sensitive=False)

    catalog: str = "jmr_demo"
    schema_name: str = "zerobus"  # 'schema' is reserved in Pydantic
    sql_warehouse_id: str = ""
    mcp_schema_name: str = "default"  # Schema for MCP server OTEL data

    @property
    def otel_logs_table(self) -> str:
        return f"{self.catalog}.{self.schema_name}.otel_logs"

    @property
    def otel_metrics_table(self) -> str:
        return f"{self.catalog}.{self.schema_name}.otel_metrics"


settings = Settings()
