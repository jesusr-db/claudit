import pytest
from unittest.mock import Mock, patch, MagicMock
from backend.services.sql_executor import SqlExecutor


def test_sql_executor_init():
    executor = SqlExecutor(warehouse_id="abc123")
    assert executor.warehouse_id == "abc123"


@patch("backend.services.sql_executor.WorkspaceClient")
def test_sql_executor_execute(mock_ws_class):
    mock_ws = MagicMock()
    mock_ws_class.return_value = mock_ws

    # Mock the statement execution API
    mock_result = MagicMock()
    mock_result.result.data_array = [["val1", "val2"]]
    col1 = MagicMock()
    col1.name = "col1"
    col2 = MagicMock()
    col2.name = "col2"
    mock_result.manifest.schema.columns = [col1, col2]
    mock_ws.statement_execution.execute_statement.return_value = mock_result

    executor = SqlExecutor(warehouse_id="abc123")
    rows = executor.execute("SELECT 1")
    assert len(rows) == 1
    assert rows[0]["col1"] == "val1"
