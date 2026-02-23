from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    catalog: str = "jmr_demo"
    schema_name: str = "zerobus"  # 'schema' is reserved in Pydantic

    sql_warehouse_id: str = ""

    @property
    def otel_logs_table(self) -> str:
        return f"{self.catalog}.{self.schema_name}.otel_logs"

    @property
    def otel_metrics_table(self) -> str:
        return f"{self.catalog}.{self.schema_name}.otel_metrics"

    class Config:
        env_prefix = ""
        case_sensitive = False


settings = Settings()
