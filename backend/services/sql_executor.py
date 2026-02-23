from typing import List, Dict, Any, Optional
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState


class SqlExecutor:
    """Executes SQL against Databricks SQL Warehouse."""

    def __init__(self, warehouse_id: str):
        self.warehouse_id = warehouse_id
        self._client: Optional[WorkspaceClient] = None

    @property
    def client(self) -> WorkspaceClient:
        if self._client is None:
            self._client = WorkspaceClient()
        return self._client

    def execute(self, query: str, timeout_seconds: int = 50) -> List[Dict[str, Any]]:
        """Execute SQL and return rows as list of dicts."""
        response = self.client.statement_execution.execute_statement(
            statement=query,
            warehouse_id=self.warehouse_id,
            wait_timeout=f"{timeout_seconds}s",
        )

        if response.status and response.status.state == StatementState.FAILED:
            error = response.status.error
            raise RuntimeError(f"SQL execution failed: {error}")

        if not response.result or not response.result.data_array:
            return []

        columns = [col.name for col in response.manifest.schema.columns]
        return [dict(zip(columns, row)) for row in response.result.data_array]
