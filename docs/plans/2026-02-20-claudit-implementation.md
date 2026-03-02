# Claudit Observability App - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an observability app for Claude Code that queries OTEL logs/metrics tables directly, with React frontend and FastAPI backend deployed on Databricks Apps.

**Architecture:** FastAPI queries OTEL tables directly via Databricks SQL. React renders analytics dashboard and session timeline. Packaged in DAB bundle. No ETL for MVP.

**Tech Stack:** Python 3.11, FastAPI, React 18, Chakra UI, TanStack Query, Databricks SDK, DAB

**Source Tables (verified):**
- `{catalog}.{schema}.otel_logs` - Claude Code event stream (user_prompt, api_request, api_error, tool_decision, tool_result)
- `{catalog}.{schema}.otel_metrics` - Aggregated counters (token.usage, cost.usage, active_time.total, session.count)

---

## Phase 1: Project Scaffolding & DAB Configuration

### Task 1.1: Initialize Project Structure

**Files:**
- Create: `pyproject.toml`
- Create: `package.json`
- Create: `.gitignore`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "claudit"
version = "0.1.0"
description = "Claude Code Observability Dashboard"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "databricks-sdk>=0.20.0",
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    "httpx>=0.26.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Create package.json**

```json
{
  "name": "claudit-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "test:ui": "vitest --ui",
    "lint": "eslint . --ext ts,tsx"
  },
  "dependencies": {
    "@chakra-ui/react": "^2.8.0",
    "@emotion/react": "^11.11.0",
    "@emotion/styled": "^11.11.0",
    "@tanstack/react-query": "^5.17.0",
    "date-fns": "^3.2.0",
    "framer-motion": "^10.18.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-icons": "^5.0.0",
    "react-router-dom": "^6.21.0",
    "recharts": "^2.10.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.2.0",
    "@testing-library/react": "^14.1.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "vitest": "^1.2.0"
  }
}
```

**Step 3: Create .gitignore**

```
# Python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.mypy_cache/
*.egg-info/
dist/
build/

# Node
node_modules/
frontend/dist/

# IDE
.idea/
.vscode/
*.swp

# Databricks
.databricks/
*.whl

# Environment
.env
.env.local

# OS
.DS_Store
```

**Step 4: Commit**

```bash
git add pyproject.toml package.json .gitignore
git commit -m "chore: initialize project with Python and Node configs"
```

---

### Task 1.2: Create DAB Bundle Configuration

**Files:**
- Create: `databricks.yml`
- Create: `resources/apps.yml`
- Create: `app.yaml`

**Step 1: Create databricks.yml**

```yaml
bundle:
  name: claudit-observability

include:
  - resources/*.yml

variables:
  catalog:
    description: "Unity Catalog containing OTEL tables"
    default: jmr_demo
  schema:
    description: "Schema containing OTEL tables"
    default: zerobus
  warehouse_id:
    description: "SQL Warehouse ID for app queries"

targets:
  dev:
    mode: development
    default: true
    workspace:
      host: ${DATABRICKS_HOST}
    variables:
      catalog: jmr_demo
      schema: zerobus

  prod:
    mode: production
    workspace:
      host: ${DATABRICKS_HOST}
    variables:
      catalog: jmr_demo
      schema: zerobus
    run_as:
      service_principal_name: claudit-service-principal
```

**Step 2: Create resources/apps.yml**

```yaml
resources:
  apps:
    claudit_app:
      name: claudit-observability
      description: "Claude Code Observability Dashboard"
      source_code_path: .
      config:
        command:
          - uvicorn
          - "backend.main:app"
          - "--host"
          - "0.0.0.0"
          - "--port"
          - "8000"
        env:
          - name: CATALOG
            value: ${var.catalog}
          - name: SCHEMA
            value: ${var.schema}
          - name: SQL_WAREHOUSE_ID
            value: ${var.warehouse_id}
      resources:
        - name: sql_warehouse
          sql_warehouse:
            id: ${var.warehouse_id}
            permission: CAN_USE
      permissions:
        - user_name: ${workspace.current_user.userName}
          level: CAN_MANAGE
```

**Step 3: Create app.yaml**

```yaml
command:
  - uvicorn
  - "backend.main:app"
  - "--host"
  - "0.0.0.0"
  - "--port"
  - "8000"

env:
  - name: PYTHONPATH
    value: "/app"
```

**Step 4: Commit**

```bash
git add databricks.yml resources/ app.yaml
git commit -m "chore: add DAB bundle configuration"
```

---

## Phase 2: Backend Core

### Task 2.1: Create Backend Config and Models

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/config.py`
- Create: `backend/models/__init__.py`
- Create: `backend/models/events.py`
- Create: `backend/models/sessions.py`
- Create: `backend/models/metrics.py`
- Test: `tests/__init__.py`, `tests/backend/__init__.py`
- Test: `tests/backend/test_models.py`

**Step 1: Write the failing test**

```python
# tests/backend/test_models.py
import pytest
from datetime import datetime
from backend.models.events import OtelLogEvent, EventName
from backend.models.sessions import SessionSummary
from backend.models.metrics import TokenUsage, CostUsage


def test_event_name_enum():
    assert EventName.USER_PROMPT.value == "user_prompt"
    assert EventName.API_REQUEST.value == "api_request"
    assert EventName.API_ERROR.value == "api_error"
    assert EventName.TOOL_DECISION.value == "tool_decision"
    assert EventName.TOOL_RESULT.value == "tool_result"


def test_otel_log_event_from_row():
    """Test parsing a raw otel_logs row into structured event."""
    row = {
        "body": "claude_code.tool_result",
        "attributes": {
            "event.name": "tool_result",
            "event.timestamp": "2026-02-23T18:06:25.499Z",
            "event.sequence": "50",
            "session.id": "996a6297-0787-454a-94b8-96191aa0a22c",
            "prompt.id": "70c91395-e300-4989-ac61-b2a97091f944",
            "user.id": "c35b69e8d2d591e01edc4cee16bda6467c047ca6d44038c0eb87fc779a4fcc2f",
            "terminal.type": "iTerm.app",
            "tool_name": "Bash",
            "duration_ms": "2330",
            "success": "true",
            "tool_result_size_bytes": "1274",
        },
    }
    event = OtelLogEvent.from_row(row)
    assert event.event_name == EventName.TOOL_RESULT
    assert event.session_id == "996a6297-0787-454a-94b8-96191aa0a22c"
    assert event.sequence == 50
    assert event.tool_name == "Bash"
    assert event.duration_ms == 2330


def test_session_summary():
    summary = SessionSummary(
        session_id="996a6297-0787-454a-94b8-96191aa0a22c",
        user_id="c35b69e8...",
        start_time=datetime(2026, 2, 23, 18, 2, 20),
        end_time=datetime(2026, 2, 23, 19, 30, 0),
        event_count=111,
        prompt_count=5,
        total_cost_usd=0.44,
        tool_calls=29,
        errors=22,
    )
    assert summary.session_id == "996a6297-0787-454a-94b8-96191aa0a22c"
    assert summary.event_count == 111


def test_token_usage():
    usage = TokenUsage(
        session_id="996a...",
        model="databricks-claude-opus-4-6",
        input_tokens=4,
        output_tokens=545,
        cache_read_tokens=47356,
        cache_creation_tokens=68504,
    )
    assert usage.total_tokens == 4 + 545 + 47356 + 68504
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_models.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/__init__.py
# (empty)

# backend/config.py
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
```

```python
# backend/models/__init__.py
from backend.models.events import OtelLogEvent, EventName
from backend.models.sessions import SessionSummary
from backend.models.metrics import TokenUsage, CostUsage

__all__ = [
    "OtelLogEvent",
    "EventName",
    "SessionSummary",
    "TokenUsage",
    "CostUsage",
]
```

```python
# backend/models/events.py
from datetime import datetime
from enum import Enum
from typing import Optional, Dict
from pydantic import BaseModel


class EventName(str, Enum):
    USER_PROMPT = "user_prompt"
    API_REQUEST = "api_request"
    API_ERROR = "api_error"
    TOOL_DECISION = "tool_decision"
    TOOL_RESULT = "tool_result"


class OtelLogEvent(BaseModel):
    """Parsed event from otel_logs table."""
    event_name: EventName
    timestamp: str
    sequence: int
    session_id: str
    prompt_id: Optional[str] = None
    user_id: Optional[str] = None
    terminal_type: Optional[str] = None

    # user_prompt fields
    prompt: Optional[str] = None
    prompt_length: Optional[int] = None

    # api_request fields
    model: Optional[str] = None
    duration_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_creation_tokens: Optional[int] = None
    speed: Optional[str] = None

    # api_error fields
    error: Optional[str] = None
    status_code: Optional[str] = None
    attempt: Optional[int] = None

    # tool_decision fields
    tool_name: Optional[str] = None
    decision: Optional[str] = None
    source: Optional[str] = None

    # tool_result fields
    success: Optional[bool] = None
    tool_parameters: Optional[str] = None
    tool_result_size_bytes: Optional[int] = None

    # Raw attributes for anything not explicitly modeled
    raw_attributes: Optional[Dict[str, str]] = None

    @classmethod
    def from_row(cls, row: dict) -> "OtelLogEvent":
        """Parse a raw otel_logs row (with attributes as a dict)."""
        attrs = row.get("attributes", {})

        def _int(key: str) -> Optional[int]:
            v = attrs.get(key)
            return int(v) if v is not None else None

        def _float(key: str) -> Optional[float]:
            v = attrs.get(key)
            return float(v) if v is not None else None

        def _bool(key: str) -> Optional[bool]:
            v = attrs.get(key)
            if v is None:
                return None
            return v.lower() == "true" if isinstance(v, str) else bool(v)

        return cls(
            event_name=EventName(attrs.get("event.name", "")),
            timestamp=attrs.get("event.timestamp", ""),
            sequence=int(attrs.get("event.sequence", 0)),
            session_id=attrs.get("session.id", ""),
            prompt_id=attrs.get("prompt.id"),
            user_id=attrs.get("user.id"),
            terminal_type=attrs.get("terminal.type"),
            # user_prompt
            prompt=attrs.get("prompt"),
            prompt_length=_int("prompt_length"),
            # api_request / api_error
            model=attrs.get("model"),
            duration_ms=_int("duration_ms"),
            cost_usd=_float("cost_usd"),
            input_tokens=_int("input_tokens"),
            output_tokens=_int("output_tokens"),
            cache_read_tokens=_int("cache_read_tokens"),
            cache_creation_tokens=_int("cache_creation_tokens"),
            speed=attrs.get("speed"),
            error=attrs.get("error"),
            status_code=attrs.get("status_code"),
            attempt=_int("attempt"),
            # tool_decision / tool_result
            tool_name=attrs.get("tool_name"),
            decision=attrs.get("decision"),
            source=attrs.get("source"),
            success=_bool("success"),
            tool_parameters=attrs.get("tool_parameters"),
            tool_result_size_bytes=_int("tool_result_size_bytes"),
            raw_attributes=attrs,
        )

    @property
    def is_mcp_tool(self) -> bool:
        """MCP tools have names starting with 'mcp__'."""
        return self.tool_name.startswith("mcp__") if self.tool_name else False

    @property
    def mcp_server(self) -> Optional[str]:
        """Extract MCP server name from tool_name like 'mcp__glean__search'."""
        if self.is_mcp_tool and self.tool_name:
            parts = self.tool_name.split("__")
            return parts[1] if len(parts) >= 2 else None
        return None
```

```python
# backend/models/sessions.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SessionSummary(BaseModel):
    session_id: str
    user_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    event_count: int = 0
    prompt_count: int = 0
    total_cost_usd: float = 0.0
    tool_calls: int = 0
    errors: int = 0
```

```python
# backend/models/metrics.py
from typing import Optional
from pydantic import BaseModel


class TokenUsage(BaseModel):
    session_id: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )


class CostUsage(BaseModel):
    session_id: str
    model: str
    cost_usd: float = 0.0
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_models.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/ tests/
git commit -m "feat(backend): add Pydantic models aligned with actual OTEL data"
```

---

### Task 2.2: Create Query Service (Direct OTEL Queries)

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/query_service.py`
- Test: `tests/backend/test_query_service.py`

**Step 1: Write the failing test**

```python
# tests/backend/test_query_service.py
import pytest
from backend.services.query_service import QueryService


@pytest.fixture
def svc():
    return QueryService(catalog="jmr_demo", schema="zerobus")


def test_build_sessions_list_query(svc):
    query = svc.build_sessions_list_query(limit=10, offset=0)
    assert "otel_logs" in query
    assert "session.id" in query
    assert "GROUP BY" in query
    assert "LIMIT 10" in query


def test_build_session_timeline_query(svc):
    query = svc.build_session_timeline_query(
        session_id="996a6297-0787-454a-94b8-96191aa0a22c"
    )
    assert "otel_logs" in query
    assert "996a6297" in query
    assert "ORDER BY" in query


def test_build_session_timeline_query_with_event_filter(svc):
    query = svc.build_session_timeline_query(
        session_id="996a6297",
        event_names=["api_request", "api_error"],
    )
    assert "api_request" in query
    assert "api_error" in query


def test_build_token_usage_query(svc):
    query = svc.build_token_usage_query()
    assert "otel_metrics" in query
    assert "token.usage" in query


def test_build_cost_usage_query(svc):
    query = svc.build_cost_usage_query()
    assert "otel_metrics" in query
    assert "cost.usage" in query


def test_build_tool_stats_query(svc):
    query = svc.build_tool_stats_query()
    assert "otel_logs" in query
    assert "tool_result" in query


def test_build_error_stats_query(svc):
    query = svc.build_error_stats_query()
    assert "otel_logs" in query
    assert "api_error" in query
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_query_service.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# backend/services/__init__.py
from backend.services.query_service import QueryService

__all__ = ["QueryService"]
```

```python
# backend/services/query_service.py
from typing import Optional, List


class QueryService:
    """Builds SQL queries against OTEL source tables directly."""

    def __init__(self, catalog: str, schema: str):
        self.catalog = catalog
        self.schema = schema

    @property
    def logs_table(self) -> str:
        return f"{self.catalog}.{self.schema}.otel_logs"

    @property
    def metrics_table(self) -> str:
        return f"{self.catalog}.{self.schema}.otel_metrics"

    def build_sessions_list_query(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
    ) -> str:
        conditions = []
        if user_id:
            conditions.append(f"attributes['user.id'] = '{user_id}'")

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes['session.id'] as session_id,
                attributes['user.id'] as user_id,
                MIN(attributes['event.timestamp']) as start_time,
                MAX(attributes['event.timestamp']) as end_time,
                COUNT(*) as event_count,
                COUNT(DISTINCT attributes['prompt.id']) as prompt_count,
                COUNT(CASE WHEN attributes['event.name'] IN ('tool_decision', 'tool_result') THEN 1 END) as tool_calls,
                COUNT(CASE WHEN attributes['event.name'] = 'api_error' THEN 1 END) as errors,
                SUM(CASE WHEN attributes['event.name'] = 'api_request'
                    THEN CAST(attributes['cost_usd'] AS DOUBLE) ELSE 0 END) as total_cost_usd
            FROM {self.logs_table}
            {where}
            GROUP BY attributes['session.id'], attributes['user.id']
            ORDER BY start_time DESC
            LIMIT {limit}
            OFFSET {offset}
        """.strip()

    def build_session_timeline_query(
        self,
        session_id: str,
        event_names: Optional[List[str]] = None,
    ) -> str:
        conditions = [f"attributes['session.id'] = '{session_id}'"]

        if event_names:
            names_str = ", ".join(f"'{n}'" for n in event_names)
            conditions.append(f"attributes['event.name'] IN ({names_str})")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes['event.name'] as event_name,
                attributes['event.timestamp'] as timestamp,
                CAST(attributes['event.sequence'] AS INT) as sequence,
                attributes['session.id'] as session_id,
                attributes['prompt.id'] as prompt_id,
                attributes['user.id'] as user_id,
                attributes['tool_name'] as tool_name,
                attributes['model'] as model,
                attributes['duration_ms'] as duration_ms,
                attributes['cost_usd'] as cost_usd,
                attributes['input_tokens'] as input_tokens,
                attributes['output_tokens'] as output_tokens,
                attributes['cache_read_tokens'] as cache_read_tokens,
                attributes['cache_creation_tokens'] as cache_creation_tokens,
                attributes['error'] as error,
                attributes['status_code'] as status_code,
                attributes['success'] as success,
                attributes['decision'] as decision,
                attributes['source'] as source,
                attributes['prompt'] as prompt,
                attributes['prompt_length'] as prompt_length,
                attributes['tool_result_size_bytes'] as tool_result_size_bytes,
                attributes['speed'] as speed
            FROM {self.logs_table}
            {where}
            ORDER BY CAST(attributes['event.sequence'] AS INT) ASC
        """.strip()

    def build_token_usage_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = ["name = 'claude_code.token.usage'"]
        if session_id:
            conditions.append(f"sum.attributes['session.id'] = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                sum.attributes['session.id'] as session_id,
                sum.attributes['model'] as model,
                sum.attributes['type'] as token_type,
                sum.value as value,
                sum.start_time_unix_nano,
                sum.time_unix_nano
            FROM {self.metrics_table}
            {where}
            ORDER BY sum.time_unix_nano DESC
        """.strip()

    def build_cost_usage_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = ["name = 'claude_code.cost.usage'"]
        if session_id:
            conditions.append(f"sum.attributes['session.id'] = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                sum.attributes['session.id'] as session_id,
                sum.attributes['model'] as model,
                sum.value as cost_usd,
                sum.start_time_unix_nano,
                sum.time_unix_nano
            FROM {self.metrics_table}
            {where}
            ORDER BY sum.time_unix_nano DESC
        """.strip()

    def build_tool_stats_query(
        self,
        session_id: Optional[str] = None,
        mcp_only: bool = False,
    ) -> str:
        conditions = ["attributes['event.name'] = 'tool_result'"]
        if session_id:
            conditions.append(f"attributes['session.id'] = '{session_id}'")
        if mcp_only:
            conditions.append("attributes['tool_name'] LIKE 'mcp__%'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes['tool_name'] as tool_name,
                COUNT(*) as call_count,
                AVG(CAST(attributes['duration_ms'] AS DOUBLE)) as avg_duration_ms,
                SUM(CASE WHEN attributes['success'] = 'true' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN attributes['success'] = 'false' THEN 1 ELSE 0 END) as failure_count,
                SUM(CAST(attributes['tool_result_size_bytes'] AS BIGINT)) as total_result_bytes
            FROM {self.logs_table}
            {where}
            GROUP BY attributes['tool_name']
            ORDER BY call_count DESC
        """.strip()

    def build_error_stats_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = ["attributes['event.name'] = 'api_error'"]
        if session_id:
            conditions.append(f"attributes['session.id'] = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes['model'] as model,
                attributes['status_code'] as status_code,
                attributes['error'] as error,
                COUNT(*) as error_count,
                AVG(CAST(attributes['duration_ms'] AS DOUBLE)) as avg_duration_ms
            FROM {self.logs_table}
            {where}
            GROUP BY attributes['model'], attributes['status_code'], attributes['error']
            ORDER BY error_count DESC
        """.strip()

    def build_api_performance_query(
        self,
        session_id: Optional[str] = None,
    ) -> str:
        conditions = ["attributes['event.name'] = 'api_request'"]
        if session_id:
            conditions.append(f"attributes['session.id'] = '{session_id}'")

        where = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                attributes['model'] as model,
                COUNT(*) as request_count,
                AVG(CAST(attributes['duration_ms'] AS DOUBLE)) as avg_duration_ms,
                PERCENTILE(CAST(attributes['duration_ms'] AS DOUBLE), 0.5) as p50_duration_ms,
                PERCENTILE(CAST(attributes['duration_ms'] AS DOUBLE), 0.95) as p95_duration_ms,
                SUM(CAST(attributes['input_tokens'] AS BIGINT)) as total_input_tokens,
                SUM(CAST(attributes['output_tokens'] AS BIGINT)) as total_output_tokens,
                SUM(CAST(attributes['cache_read_tokens'] AS BIGINT)) as total_cache_read_tokens,
                SUM(CAST(attributes['cost_usd'] AS DOUBLE)) as total_cost_usd
            FROM {self.logs_table}
            {where}
            GROUP BY attributes['model']
        """.strip()

    def build_summary_query(self) -> str:
        return f"""
            SELECT
                COUNT(DISTINCT attributes['session.id']) as total_sessions,
                COUNT(DISTINCT attributes['user.id']) as total_users,
                COUNT(*) as total_events,
                COUNT(CASE WHEN attributes['event.name'] = 'user_prompt' THEN 1 END) as total_prompts,
                COUNT(CASE WHEN attributes['event.name'] = 'api_request' THEN 1 END) as total_api_calls,
                COUNT(CASE WHEN attributes['event.name'] = 'api_error' THEN 1 END) as total_errors,
                SUM(CASE WHEN attributes['event.name'] = 'api_request'
                    THEN CAST(attributes['cost_usd'] AS DOUBLE) ELSE 0 END) as total_cost_usd
            FROM {self.logs_table}
        """.strip()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_query_service.py -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add backend/services/ tests/backend/test_query_service.py
git commit -m "feat(backend): add QueryService for direct OTEL table queries"
```

---

### Task 2.3: Create SQL Execution Service

**Files:**
- Create: `backend/services/sql_executor.py`
- Modify: `backend/services/__init__.py`
- Test: `tests/backend/test_sql_executor.py`

**Step 1: Write the failing test**

```python
# tests/backend/test_sql_executor.py
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
    mock_result.manifest.schema.columns = [
        MagicMock(name="col1"),
        MagicMock(name="col2"),
    ]
    mock_ws.statement_execution.execute_statement.return_value = mock_result

    executor = SqlExecutor(warehouse_id="abc123")
    rows = executor.execute("SELECT 1")
    assert len(rows) == 1
    assert rows[0]["col1"] == "val1"
```

**Step 2: Write implementation**

```python
# backend/services/sql_executor.py
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
```

**Step 3: Commit**

```bash
git add backend/services/ tests/backend/test_sql_executor.py
git commit -m "feat(backend): add SqlExecutor for Databricks SQL warehouse queries"
```

---

### Task 2.4: Create FastAPI Application with Metrics Router

**Files:**
- Create: `backend/main.py`
- Create: `backend/routers/__init__.py`
- Create: `backend/routers/metrics.py`
- Test: `tests/backend/test_metrics_router.py`

**Step 1: Write the failing test**

```python
# tests/backend/test_metrics_router.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_executor():
    with patch("backend.routers.metrics.get_executor") as mock:
        executor = MagicMock()
        mock.return_value = executor
        yield executor


@pytest.fixture
def client(mock_executor):
    from backend.main import app
    return TestClient(app)


def test_get_summary(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "total_sessions": "3",
            "total_users": "1",
            "total_events": "111",
            "total_prompts": "8",
            "total_api_calls": "24",
            "total_errors": "22",
            "total_cost_usd": "0.44",
        }
    ]
    response = client.get("/api/v1/metrics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_sessions" in data


def test_get_tool_stats(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "tool_name": "Bash",
            "call_count": "15",
            "avg_duration_ms": "2100.5",
            "success_count": "14",
            "failure_count": "1",
            "total_result_bytes": "15000",
        }
    ]
    response = client.get("/api/v1/metrics/tools")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tools"]) == 1
    assert data["tools"][0]["tool_name"] == "Bash"


def test_health_check(client, mock_executor):
    response = client.get("/health")
    assert response.status_code == 200
```

**Step 2: Write implementation**

```python
# backend/routers/__init__.py
from backend.routers.metrics import router as metrics_router
from backend.routers.sessions import router as sessions_router

__all__ = ["metrics_router", "sessions_router"]
```

```python
# backend/routers/metrics.py
from fastapi import APIRouter, Query
from typing import Optional
from backend.config import settings
from backend.services.query_service import QueryService
from backend.services.sql_executor import SqlExecutor

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])

query_service = QueryService(
    catalog=settings.catalog,
    schema=settings.schema_name,
)


def get_executor() -> SqlExecutor:
    return SqlExecutor(warehouse_id=settings.sql_warehouse_id)


@router.get("/summary")
async def get_summary():
    query = query_service.build_summary_query()
    rows = get_executor().execute(query)
    return rows[0] if rows else {}


@router.get("/usage")
async def get_token_usage(session_id: Optional[str] = Query(None)):
    query = query_service.build_token_usage_query(session_id=session_id)
    rows = get_executor().execute(query)
    return {"usage": rows}


@router.get("/costs")
async def get_cost_usage(session_id: Optional[str] = Query(None)):
    query = query_service.build_cost_usage_query(session_id=session_id)
    rows = get_executor().execute(query)
    return {"costs": rows}


@router.get("/tools")
async def get_tool_stats(
    session_id: Optional[str] = Query(None),
    mcp_only: bool = Query(False),
):
    query = query_service.build_tool_stats_query(
        session_id=session_id, mcp_only=mcp_only
    )
    rows = get_executor().execute(query)
    return {"tools": rows}


@router.get("/errors")
async def get_error_stats(session_id: Optional[str] = Query(None)):
    query = query_service.build_error_stats_query(session_id=session_id)
    rows = get_executor().execute(query)
    return {"errors": rows}


@router.get("/performance")
async def get_api_performance(session_id: Optional[str] = Query(None)):
    query = query_service.build_api_performance_query(session_id=session_id)
    rows = get_executor().execute(query)
    return {"performance": rows}
```

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.routers import metrics_router, sessions_router

app = FastAPI(
    title="Claudit Observability",
    description="Claude Code Observability Dashboard API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router)
app.include_router(sessions_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Serve static files in production
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
```

**Step 3: Commit**

```bash
git add backend/ tests/
git commit -m "feat(backend): add FastAPI app with metrics router"
```

---

### Task 2.5: Create Sessions Router

**Files:**
- Create: `backend/routers/sessions.py`
- Modify: `backend/services/query_service.py` (add `build_session_detail_query`)
- Test: `tests/backend/test_sessions_router.py`

**Step 1: Add `build_session_detail_query` to QueryService**

Add this method to `backend/services/query_service.py` after `build_sessions_list_query`:

```python
    def build_session_detail_query(self, session_id: str) -> str:
        return f"""
            SELECT
                attributes['session.id'] as session_id,
                attributes['user.id'] as user_id,
                MIN(attributes['event.timestamp']) as start_time,
                MAX(attributes['event.timestamp']) as end_time,
                COUNT(*) as event_count,
                COUNT(DISTINCT attributes['prompt.id']) as prompt_count,
                COUNT(CASE WHEN attributes['event.name'] IN ('tool_decision', 'tool_result') THEN 1 END) as tool_calls,
                COUNT(CASE WHEN attributes['event.name'] = 'api_error' THEN 1 END) as errors,
                SUM(CASE WHEN attributes['event.name'] = 'api_request'
                    THEN CAST(attributes['cost_usd'] AS DOUBLE) ELSE 0 END) as total_cost_usd
            FROM {self.logs_table}
            WHERE attributes['session.id'] = '{session_id}'
            GROUP BY attributes['session.id'], attributes['user.id']
        """.strip()
```

**Step 2: Add test for `build_session_detail_query` to `tests/backend/test_query_service.py`**

```python
def test_build_session_detail_query(svc):
    query = svc.build_session_detail_query(session_id="996a6297")
    assert "otel_logs" in query
    assert "996a6297" in query
    assert "GROUP BY" in query
    assert "total_cost_usd" in query
```

**Step 3: Run tests to verify QueryService update**

Run: `pytest tests/backend/test_query_service.py -v`
Expected: PASS (8 tests)

**Step 4: Write the sessions router test**

```python
# tests/backend/test_sessions_router.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_executor():
    with patch("backend.routers.sessions.get_executor") as mock_sess, \
         patch("backend.routers.metrics.get_executor") as mock_met:
        executor = MagicMock()
        mock_sess.return_value = executor
        mock_met.return_value = executor
        yield executor


@pytest.fixture
def client(mock_executor):
    from backend.main import app
    return TestClient(app)


def test_list_sessions(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "session_id": "996a6297-0787-454a-94b8-96191aa0a22c",
            "user_id": "c35b69e8...",
            "start_time": "2026-02-23T18:02:20Z",
            "end_time": "2026-02-23T19:30:00Z",
            "event_count": "111",
            "prompt_count": "5",
            "tool_calls": "29",
            "errors": "22",
            "total_cost_usd": "0.44",
        }
    ]
    response = client.get("/api/v1/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "996a6297-0787-454a-94b8-96191aa0a22c"


def test_get_session_detail(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "session_id": "996a6297",
            "user_id": "c35b69e8...",
            "start_time": "2026-02-23T18:02:20Z",
            "end_time": "2026-02-23T19:30:00Z",
            "event_count": "111",
            "prompt_count": "5",
            "tool_calls": "29",
            "errors": "22",
            "total_cost_usd": "0.44",
        }
    ]
    response = client.get("/api/v1/sessions/996a6297")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "996a6297"


def test_get_session_detail_not_found(client, mock_executor):
    mock_executor.execute.return_value = []
    response = client.get("/api/v1/sessions/nonexistent")
    assert response.status_code == 404


def test_get_session_timeline(client, mock_executor):
    mock_executor.execute.return_value = [
        {
            "event_name": "user_prompt",
            "timestamp": "2026-02-23T18:02:20.757Z",
            "sequence": 1,
            "session_id": "996a6297",
            "prompt_id": "efeed64b",
            "user_id": "c35b69e8",
            "tool_name": None,
            "model": None,
            "duration_ms": None,
            "prompt": "can you review OTEL log configuration...",
        }
    ]
    response = client.get("/api/v1/sessions/996a6297/timeline")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "996a6297"
    assert len(data["events"]) == 1
    assert data["events"][0]["event_name"] == "user_prompt"
```

**Step 5: Run sessions router tests to verify they fail**

Run: `pytest tests/backend/test_sessions_router.py -v`
Expected: FAIL with ModuleNotFoundError (sessions router not created yet)

**Step 6: Write sessions router implementation**

```python
# backend/routers/sessions.py
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from backend.config import settings
from backend.services.query_service import QueryService
from backend.services.sql_executor import SqlExecutor

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

query_service = QueryService(
    catalog=settings.catalog,
    schema=settings.schema_name,
)


def get_executor() -> SqlExecutor:
    return SqlExecutor(warehouse_id=settings.sql_warehouse_id)


@router.get("")
async def list_sessions(
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = query_service.build_sessions_list_query(
        limit=limit, offset=offset, user_id=user_id
    )
    rows = get_executor().execute(query)
    return {"sessions": rows}


@router.get("/{session_id}")
async def get_session(session_id: str):
    query = query_service.build_session_detail_query(session_id=session_id)
    rows = get_executor().execute(query)
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")
    return rows[0]


@router.get("/{session_id}/timeline")
async def get_session_timeline(
    session_id: str,
    event_names: Optional[List[str]] = Query(None),
):
    query = query_service.build_session_timeline_query(
        session_id=session_id, event_names=event_names
    )
    rows = get_executor().execute(query)
    return {"session_id": session_id, "events": rows}
```

**Step 7: Run sessions router tests to verify they pass**

Run: `pytest tests/backend/test_sessions_router.py -v`
Expected: PASS (4 tests)

**Step 8: Commit**

```bash
git add backend/services/query_service.py backend/routers/sessions.py tests/backend/
git commit -m "feat(backend): add sessions router using QueryService (no inline SQL)"
```

---

## Phase 3: Frontend Core

### Task 3.1: Initialize React Frontend

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/providers/QueryProvider.tsx`
- Create: `frontend/src/types/api.ts`
- Create: `frontend/src/vite-env.d.ts`

**Step 1: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Claudit - Claude Code Observability</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

**Step 3: Create `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

**Step 4: Create `frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
```

**Step 5: Create `frontend/src/vite-env.d.ts`**

```typescript
/// <reference types="vite/client" />
```

**Step 6: Create `frontend/src/types/api.ts`**

```typescript
export type EventName =
  | "user_prompt"
  | "api_request"
  | "api_error"
  | "tool_decision"
  | "tool_result";

export interface SessionSummary {
  session_id: string;
  user_id: string;
  start_time: string;
  end_time: string | null;
  event_count: string;
  prompt_count: string;
  total_cost_usd: string;
  tool_calls: string;
  errors: string;
}

export interface TimelineEvent {
  event_name: EventName;
  timestamp: string;
  sequence: number;
  session_id: string;
  prompt_id: string | null;
  user_id: string | null;
  tool_name: string | null;
  model: string | null;
  duration_ms: string | null;
  cost_usd: string | null;
  input_tokens: string | null;
  output_tokens: string | null;
  cache_read_tokens: string | null;
  cache_creation_tokens: string | null;
  error: string | null;
  status_code: string | null;
  success: string | null;
  decision: string | null;
  source: string | null;
  prompt: string | null;
  prompt_length: string | null;
  tool_result_size_bytes: string | null;
  speed: string | null;
}

export interface ToolStat {
  tool_name: string;
  call_count: string;
  avg_duration_ms: string;
  success_count: string;
  failure_count: string;
  total_result_bytes: string;
}

export interface MetricsSummary {
  total_sessions: string;
  total_users: string;
  total_events: string;
  total_prompts: string;
  total_api_calls: string;
  total_errors: string;
  total_cost_usd: string;
}

export interface ErrorStat {
  model: string;
  status_code: string;
  error: string;
  error_count: string;
  avg_duration_ms: string;
}
```

**Step 7: Create `frontend/src/app/providers/QueryProvider.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode } from "react";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export function QueryProvider({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

**Step 8: Create `frontend/src/app/App.tsx`**

```tsx
import { ChakraProvider } from "@chakra-ui/react";
import { BrowserRouter } from "react-router-dom";
import { QueryProvider } from "./providers/QueryProvider";

export default function App() {
  return (
    <ChakraProvider>
      <QueryProvider>
        <BrowserRouter>
          <div>Claudit app shell</div>
        </BrowserRouter>
      </QueryProvider>
    </ChakraProvider>
  );
}
```

**Step 9: Create `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./app/App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

**Step 10: Install dependencies**

Run: `cd frontend && npm install`
Expected: `added N packages` (no errors)

**Step 11: Verify TypeScript compilation**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 12: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): initialize React frontend with Vite, Chakra, TanStack Query"
```

---

### Task 3.2: Build Dashboard View

**Files:**
- Create: `frontend/src/shared/hooks/useApi.ts`
- Create: `frontend/src/views/dashboard/DashboardPage.tsx`
- Create: `frontend/src/views/dashboard/components/SummaryCards.tsx`
- Create: `frontend/src/views/dashboard/components/ToolUsageTable.tsx`
- Create: `frontend/src/views/dashboard/components/ErrorsTable.tsx`
- Test: `frontend/src/views/dashboard/__tests__/DashboardPage.test.tsx`

**Step 1: Create `frontend/src/shared/hooks/useApi.ts`**

```typescript
import { useQuery } from "@tanstack/react-query";
import type { MetricsSummary, ToolStat, ErrorStat } from "@/types/api";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export function useSummary() {
  return useQuery<MetricsSummary>({
    queryKey: ["metrics", "summary"],
    queryFn: () => fetchJson("/api/v1/metrics/summary"),
  });
}

export function useToolStats(mcp_only = false) {
  return useQuery<{ tools: ToolStat[] }>({
    queryKey: ["metrics", "tools", { mcp_only }],
    queryFn: () =>
      fetchJson(`/api/v1/metrics/tools?mcp_only=${mcp_only}`),
  });
}

export function useErrorStats() {
  return useQuery<{ errors: ErrorStat[] }>({
    queryKey: ["metrics", "errors"],
    queryFn: () => fetchJson("/api/v1/metrics/errors"),
  });
}

export function useSessions(limit = 50, offset = 0) {
  return useQuery<{ sessions: import("@/types/api").SessionSummary[] }>({
    queryKey: ["sessions", { limit, offset }],
    queryFn: () =>
      fetchJson(`/api/v1/sessions?limit=${limit}&offset=${offset}`),
  });
}

export function useSessionTimeline(
  sessionId: string,
  eventNames?: string[]
) {
  const params = new URLSearchParams();
  if (eventNames) {
    eventNames.forEach((n) => params.append("event_names", n));
  }
  const qs = params.toString() ? `?${params.toString()}` : "";
  return useQuery<{
    session_id: string;
    events: import("@/types/api").TimelineEvent[];
  }>({
    queryKey: ["sessions", sessionId, "timeline", eventNames],
    queryFn: () =>
      fetchJson(`/api/v1/sessions/${sessionId}/timeline${qs}`),
    enabled: !!sessionId,
  });
}
```

**Step 2: Create `frontend/src/views/dashboard/components/SummaryCards.tsx`**

```tsx
import {
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Card,
  CardBody,
  Spinner,
  Text,
} from "@chakra-ui/react";
import { useSummary } from "@/shared/hooks/useApi";

export function SummaryCards() {
  const { data, isLoading, error } = useSummary();

  if (isLoading) return <Spinner />;
  if (error) return <Text color="red.500">Failed to load summary</Text>;
  if (!data) return null;

  const cards = [
    { label: "Sessions", value: data.total_sessions },
    { label: "Users", value: data.total_users },
    { label: "Events", value: data.total_events },
    { label: "Prompts", value: data.total_prompts },
    { label: "API Calls", value: data.total_api_calls },
    { label: "Errors", value: data.total_errors },
    {
      label: "Total Cost",
      value: `$${parseFloat(data.total_cost_usd || "0").toFixed(2)}`,
    },
  ];

  return (
    <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
      {cards.map((c) => (
        <Card key={c.label} size="sm">
          <CardBody>
            <Stat>
              <StatLabel>{c.label}</StatLabel>
              <StatNumber>{c.value}</StatNumber>
            </Stat>
          </CardBody>
        </Card>
      ))}
    </SimpleGrid>
  );
}
```

**Step 3: Create `frontend/src/views/dashboard/components/ToolUsageTable.tsx`**

```tsx
import {
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Spinner,
  Text,
  Switch,
  FormControl,
  FormLabel,
  Box,
} from "@chakra-ui/react";
import { useState } from "react";
import { useToolStats } from "@/shared/hooks/useApi";

export function ToolUsageTable() {
  const [mcpOnly, setMcpOnly] = useState(false);
  const { data, isLoading, error } = useToolStats(mcpOnly);

  if (isLoading) return <Spinner />;
  if (error) return <Text color="red.500">Failed to load tool stats</Text>;

  return (
    <Box>
      <FormControl display="flex" alignItems="center" mb={3}>
        <FormLabel mb="0">MCP tools only</FormLabel>
        <Switch
          isChecked={mcpOnly}
          onChange={(e) => setMcpOnly(e.target.checked)}
        />
      </FormControl>
      <Table size="sm" variant="simple">
        <Thead>
          <Tr>
            <Th>Tool</Th>
            <Th isNumeric>Calls</Th>
            <Th isNumeric>Avg Duration (ms)</Th>
            <Th isNumeric>Success</Th>
            <Th isNumeric>Failures</Th>
          </Tr>
        </Thead>
        <Tbody>
          {(data?.tools || []).map((t) => (
            <Tr key={t.tool_name}>
              <Td>{t.tool_name}</Td>
              <Td isNumeric>{t.call_count}</Td>
              <Td isNumeric>{parseFloat(t.avg_duration_ms).toFixed(0)}</Td>
              <Td isNumeric>{t.success_count}</Td>
              <Td isNumeric>{t.failure_count}</Td>
            </Tr>
          ))}
        </Tbody>
      </Table>
    </Box>
  );
}
```

**Step 4: Create `frontend/src/views/dashboard/components/ErrorsTable.tsx`**

```tsx
import {
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Spinner,
  Text,
} from "@chakra-ui/react";
import { useErrorStats } from "@/shared/hooks/useApi";

export function ErrorsTable() {
  const { data, isLoading, error } = useErrorStats();

  if (isLoading) return <Spinner />;
  if (error) return <Text color="red.500">Failed to load error stats</Text>;

  return (
    <Table size="sm" variant="simple">
      <Thead>
        <Tr>
          <Th>Model</Th>
          <Th>Status</Th>
          <Th>Error</Th>
          <Th isNumeric>Count</Th>
          <Th isNumeric>Avg Duration (ms)</Th>
        </Tr>
      </Thead>
      <Tbody>
        {(data?.errors || []).map((e, i) => (
          <Tr key={i}>
            <Td>{e.model}</Td>
            <Td>{e.status_code}</Td>
            <Td maxW="300px" isTruncated>{e.error}</Td>
            <Td isNumeric>{e.error_count}</Td>
            <Td isNumeric>{parseFloat(e.avg_duration_ms).toFixed(0)}</Td>
          </Tr>
        ))}
      </Tbody>
    </Table>
  );
}
```

**Step 5: Create `frontend/src/views/dashboard/DashboardPage.tsx`**

```tsx
import { Box, Heading, VStack } from "@chakra-ui/react";
import { SummaryCards } from "./components/SummaryCards";
import { ToolUsageTable } from "./components/ToolUsageTable";
import { ErrorsTable } from "./components/ErrorsTable";

export default function DashboardPage() {
  return (
    <Box p={6}>
      <VStack spacing={8} align="stretch">
        <Heading size="lg">Analytics Dashboard</Heading>
        <SummaryCards />
        <Box>
          <Heading size="md" mb={4}>
            Tool Usage
          </Heading>
          <ToolUsageTable />
        </Box>
        <Box>
          <Heading size="md" mb={4}>
            Errors
          </Heading>
          <ErrorsTable />
        </Box>
      </VStack>
    </Box>
  );
}
```

**Step 6: Write test `frontend/src/views/dashboard/__tests__/DashboardPage.test.tsx`**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import DashboardPage from "../DashboardPage";

// Mock the API hooks
vi.mock("@/shared/hooks/useApi", () => ({
  useSummary: () => ({
    data: {
      total_sessions: "3",
      total_users: "1",
      total_events: "111",
      total_prompts: "8",
      total_api_calls: "24",
      total_errors: "22",
      total_cost_usd: "0.44",
    },
    isLoading: false,
    error: null,
  }),
  useToolStats: () => ({
    data: {
      tools: [
        {
          tool_name: "Bash",
          call_count: "15",
          avg_duration_ms: "2100.5",
          success_count: "14",
          failure_count: "1",
          total_result_bytes: "15000",
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
  useErrorStats: () => ({
    data: {
      errors: [
        {
          model: "claude-haiku-4-5-20251001",
          status_code: "404",
          error: "endpoint not found",
          error_count: "22",
          avg_duration_ms: "344.0",
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
}));

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <ChakraProvider>
      <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
    </ChakraProvider>
  );
}

describe("DashboardPage", () => {
  it("renders the dashboard heading", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("Analytics Dashboard")).toBeDefined();
  });

  it("renders summary cards with data", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("3")).toBeDefined(); // total_sessions
    expect(screen.getByText("$0.44")).toBeDefined(); // total_cost
  });

  it("renders tool usage table", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("Bash")).toBeDefined();
    expect(screen.getByText("15")).toBeDefined(); // call_count
  });

  it("renders errors table", () => {
    renderWithProviders(<DashboardPage />);
    expect(screen.getByText("404")).toBeDefined();
  });
});
```

**Step 7: Run frontend tests**

Run: `cd frontend && npx vitest run src/views/dashboard/__tests__/DashboardPage.test.tsx`
Expected: PASS (4 tests)

**Step 8: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add analytics dashboard with summary, tools, and errors"
```

---

### Task 3.3: Build Sessions List View

**Files:**
- Create: `frontend/src/views/sessions/SessionsPage.tsx`
- Create: `frontend/src/views/sessions/components/SessionCard.tsx`
- Test: `frontend/src/views/sessions/__tests__/SessionsPage.test.tsx`

**Step 1: Create `frontend/src/views/sessions/components/SessionCard.tsx`**

```tsx
import {
  Card,
  CardBody,
  HStack,
  VStack,
  Text,
  Badge,
  Stat,
  StatLabel,
  StatNumber,
  SimpleGrid,
} from "@chakra-ui/react";
import { useNavigate } from "react-router-dom";
import type { SessionSummary } from "@/types/api";

interface Props {
  session: SessionSummary;
}

export function SessionCard({ session }: Props) {
  const navigate = useNavigate();

  return (
    <Card
      cursor="pointer"
      onClick={() => navigate(`/sessions/${session.session_id}`)}
      _hover={{ shadow: "md" }}
      size="sm"
    >
      <CardBody>
        <VStack align="stretch" spacing={2}>
          <HStack justify="space-between">
            <Text fontFamily="mono" fontSize="sm" fontWeight="bold">
              {session.session_id.slice(0, 8)}...
            </Text>
            <Text fontSize="xs" color="gray.500">
              {new Date(session.start_time).toLocaleString()}
            </Text>
          </HStack>
          <SimpleGrid columns={4} spacing={2}>
            <Stat size="sm">
              <StatLabel>Events</StatLabel>
              <StatNumber fontSize="md">{session.event_count}</StatNumber>
            </Stat>
            <Stat size="sm">
              <StatLabel>Prompts</StatLabel>
              <StatNumber fontSize="md">{session.prompt_count}</StatNumber>
            </Stat>
            <Stat size="sm">
              <StatLabel>Cost</StatLabel>
              <StatNumber fontSize="md">
                ${parseFloat(session.total_cost_usd || "0").toFixed(2)}
              </StatNumber>
            </Stat>
            <Stat size="sm">
              <StatLabel>Errors</StatLabel>
              <StatNumber
                fontSize="md"
                color={parseInt(session.errors) > 0 ? "red.500" : "green.500"}
              >
                {session.errors}
              </StatNumber>
            </Stat>
          </SimpleGrid>
        </VStack>
      </CardBody>
    </Card>
  );
}
```

**Step 2: Create `frontend/src/views/sessions/SessionsPage.tsx`**

```tsx
import { Box, Heading, VStack, Spinner, Text } from "@chakra-ui/react";
import { useSessions } from "@/shared/hooks/useApi";
import { SessionCard } from "./components/SessionCard";

export default function SessionsPage() {
  const { data, isLoading, error } = useSessions();

  return (
    <Box p={6}>
      <Heading size="lg" mb={6}>
        Sessions
      </Heading>
      {isLoading && <Spinner />}
      {error && <Text color="red.500">Failed to load sessions</Text>}
      <VStack spacing={3} align="stretch">
        {(data?.sessions || []).map((s) => (
          <SessionCard key={s.session_id} session={s} />
        ))}
        {data?.sessions?.length === 0 && (
          <Text color="gray.500">No sessions found</Text>
        )}
      </VStack>
    </Box>
  );
}
```

**Step 3: Write test `frontend/src/views/sessions/__tests__/SessionsPage.test.tsx`**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import SessionsPage from "../SessionsPage";

vi.mock("@/shared/hooks/useApi", () => ({
  useSessions: () => ({
    data: {
      sessions: [
        {
          session_id: "996a6297-0787-454a-94b8-96191aa0a22c",
          user_id: "c35b69e8...",
          start_time: "2026-02-23T18:02:20Z",
          end_time: "2026-02-23T19:30:00Z",
          event_count: "111",
          prompt_count: "5",
          total_cost_usd: "0.44",
          tool_calls: "29",
          errors: "22",
        },
      ],
    },
    isLoading: false,
    error: null,
  }),
}));

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ChakraProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter>{ui}</MemoryRouter>
      </QueryClientProvider>
    </ChakraProvider>
  );
}

describe("SessionsPage", () => {
  it("renders sessions heading", () => {
    renderWithProviders(<SessionsPage />);
    expect(screen.getByText("Sessions")).toBeDefined();
  });

  it("renders session card with truncated id", () => {
    renderWithProviders(<SessionsPage />);
    expect(screen.getByText("996a6297...")).toBeDefined();
  });

  it("renders session stats", () => {
    renderWithProviders(<SessionsPage />);
    expect(screen.getByText("111")).toBeDefined(); // event_count
    expect(screen.getByText("$0.44")).toBeDefined(); // cost
  });
});
```

**Step 4: Run test**

Run: `cd frontend && npx vitest run src/views/sessions/__tests__/SessionsPage.test.tsx`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add sessions list view with session cards"
```

---

### Task 3.4: Build Session Timeline View

**Files:**
- Create: `frontend/src/views/sessions/SessionDetailPage.tsx`
- Create: `frontend/src/views/sessions/components/SessionTimeline.tsx`
- Create: `frontend/src/views/sessions/components/TimelineEvent.tsx`
- Test: `frontend/src/views/sessions/__tests__/TimelineEvent.test.tsx`

**Step 1: Create `frontend/src/views/sessions/components/TimelineEvent.tsx`**

```tsx
import { Box, HStack, Text, Badge, VStack, Code } from "@chakra-ui/react";
import type { TimelineEvent as TEvent } from "@/types/api";

const EVENT_COLORS: Record<string, string> = {
  user_prompt: "teal",
  api_request: "green",
  api_error: "red",
  tool_decision: "blue",
  tool_result: "cyan",
};

const EVENT_ICONS: Record<string, string> = {
  user_prompt: ">>>",
  api_request: "\u25CB",
  api_error: "\u26A0",
  tool_decision: "\u25C6",
  tool_result: "\u25C6",
};

interface Props {
  event: TEvent;
}

export function TimelineEventRow({ event }: Props) {
  const color = EVENT_COLORS[event.event_name] || "gray";
  const icon = EVENT_ICONS[event.event_name] || "\u2022";
  const ts = new Date(event.timestamp).toLocaleTimeString();

  return (
    <Box borderLeft="3px solid" borderColor={`${color}.400`} pl={4} py={2}>
      <HStack spacing={3} mb={1}>
        <Text fontSize="xs" color="gray.500" fontFamily="mono" minW="50px">
          #{event.sequence}
        </Text>
        <Text fontSize="xs" color="gray.500">
          {ts}
        </Text>
        <Badge colorScheme={color} fontSize="xs">
          {icon} {event.event_name.toUpperCase()}
        </Badge>
        {event.model && (
          <Badge variant="outline" fontSize="xs">
            {event.model}
          </Badge>
        )}
        {event.tool_name && (
          <Badge variant="outline" fontSize="xs">
            {event.tool_name}
          </Badge>
        )}
      </HStack>

      <VStack align="stretch" spacing={0} pl="62px" fontSize="sm">
        {event.event_name === "user_prompt" && event.prompt && (
          <Text noOfLines={2} color="gray.700">
            "{event.prompt}"
          </Text>
        )}
        {event.event_name === "api_request" && (
          <>
            <HStack spacing={4}>
              <Text>Duration: {event.duration_ms}ms</Text>
              <Text>Cost: ${event.cost_usd}</Text>
            </HStack>
            <Text fontSize="xs" color="gray.500">
              Tokens: {event.input_tokens} in / {event.output_tokens} out /{" "}
              {event.cache_read_tokens} cache_read
            </Text>
          </>
        )}
        {event.event_name === "api_error" && (
          <Text color="red.600">
            {event.status_code}: {event.error}
          </Text>
        )}
        {event.event_name === "tool_decision" && (
          <Text>
            {event.decision} via {event.source}
          </Text>
        )}
        {event.event_name === "tool_result" && (
          <HStack spacing={4}>
            <Text>
              Duration: {event.duration_ms}ms
            </Text>
            <Badge colorScheme={event.success === "true" ? "green" : "red"}>
              {event.success === "true" ? "success" : "failed"}
            </Badge>
            {event.tool_result_size_bytes && (
              <Text fontSize="xs">{event.tool_result_size_bytes} bytes</Text>
            )}
          </HStack>
        )}
      </VStack>
    </Box>
  );
}
```

**Step 2: Create `frontend/src/views/sessions/components/SessionTimeline.tsx`**

```tsx
import { VStack, HStack, Button, Box } from "@chakra-ui/react";
import { useState } from "react";
import type { TimelineEvent } from "@/types/api";
import { TimelineEventRow } from "./TimelineEvent";

const FILTERS = [
  { label: "All", value: undefined },
  { label: "Prompts", value: ["user_prompt"] },
  { label: "API Calls", value: ["api_request"] },
  { label: "Tools", value: ["tool_decision", "tool_result"] },
  { label: "Errors", value: ["api_error"] },
] as const;

interface Props {
  events: TimelineEvent[];
}

export function SessionTimeline({ events }: Props) {
  const [filter, setFilter] = useState<string[] | undefined>(undefined);

  const filtered = filter
    ? events.filter((e) => filter.includes(e.event_name))
    : events;

  return (
    <Box>
      <HStack spacing={2} mb={4}>
        {FILTERS.map((f) => (
          <Button
            key={f.label}
            size="sm"
            variant={
              JSON.stringify(filter) === JSON.stringify(f.value)
                ? "solid"
                : "outline"
            }
            onClick={() => setFilter(f.value as string[] | undefined)}
          >
            {f.label}
          </Button>
        ))}
      </HStack>
      <VStack spacing={1} align="stretch">
        {filtered.map((e) => (
          <TimelineEventRow key={`${e.sequence}`} event={e} />
        ))}
      </VStack>
    </Box>
  );
}
```

**Step 3: Create `frontend/src/views/sessions/SessionDetailPage.tsx`**

```tsx
import {
  Box,
  Heading,
  HStack,
  Text,
  Spinner,
  Badge,
  VStack,
} from "@chakra-ui/react";
import { useParams } from "react-router-dom";
import { useSessionTimeline } from "@/shared/hooks/useApi";
import { SessionTimeline } from "./components/SessionTimeline";

export default function SessionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useSessionTimeline(id || "");

  if (!id) return <Text>No session ID</Text>;
  if (isLoading) return <Spinner />;
  if (error) return <Text color="red.500">Failed to load session</Text>;

  const events = data?.events || [];

  return (
    <Box p={6}>
      <VStack align="stretch" spacing={4}>
        <Heading size="lg">Session Timeline</Heading>
        <HStack spacing={4}>
          <Text fontFamily="mono" fontSize="sm">
            {id}
          </Text>
          <Badge>{events.length} events</Badge>
        </HStack>
        <SessionTimeline events={events} />
      </VStack>
    </Box>
  );
}
```

**Step 4: Write test `frontend/src/views/sessions/__tests__/TimelineEvent.test.tsx`**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import { TimelineEventRow } from "../components/TimelineEvent";
import type { TimelineEvent } from "@/types/api";

function renderEvent(event: Partial<TimelineEvent>) {
  const defaults: TimelineEvent = {
    event_name: "user_prompt",
    timestamp: "2026-02-23T18:02:20.757Z",
    sequence: 1,
    session_id: "996a6297",
    prompt_id: null,
    user_id: null,
    tool_name: null,
    model: null,
    duration_ms: null,
    cost_usd: null,
    input_tokens: null,
    output_tokens: null,
    cache_read_tokens: null,
    cache_creation_tokens: null,
    error: null,
    status_code: null,
    success: null,
    decision: null,
    source: null,
    prompt: null,
    prompt_length: null,
    tool_result_size_bytes: null,
    speed: null,
    ...event,
  };
  return render(
    <ChakraProvider>
      <TimelineEventRow event={defaults} />
    </ChakraProvider>
  );
}

describe("TimelineEventRow", () => {
  it("renders user_prompt with prompt text", () => {
    renderEvent({
      event_name: "user_prompt",
      prompt: "review my config",
    });
    expect(screen.getByText(/review my config/)).toBeDefined();
    expect(screen.getByText(/USER_PROMPT/)).toBeDefined();
  });

  it("renders api_request with model and cost", () => {
    renderEvent({
      event_name: "api_request",
      model: "claude-opus-4-6",
      duration_ms: "7221",
      cost_usd: "0.039",
      input_tokens: "1",
      output_tokens: "470",
      cache_read_tokens: "47356",
    });
    expect(screen.getByText("claude-opus-4-6")).toBeDefined();
    expect(screen.getByText(/\$0.039/)).toBeDefined();
  });

  it("renders api_error with status and message", () => {
    renderEvent({
      event_name: "api_error",
      model: "claude-haiku-4-5",
      status_code: "404",
      error: "endpoint not found",
    });
    expect(screen.getByText(/404: endpoint not found/)).toBeDefined();
  });

  it("renders tool_result with success badge", () => {
    renderEvent({
      event_name: "tool_result",
      tool_name: "Bash",
      duration_ms: "2330",
      success: "true",
      tool_result_size_bytes: "1274",
    });
    expect(screen.getByText("Bash")).toBeDefined();
    expect(screen.getByText("success")).toBeDefined();
  });
});
```

**Step 5: Run test**

Run: `cd frontend && npx vitest run src/views/sessions/__tests__/TimelineEvent.test.tsx`
Expected: PASS (4 tests)

**Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add session timeline view with event rendering"
```

---

### Task 3.5: Add View Registry and Router

**Files:**
- Create: `frontend/src/app/router/viewRegistry.ts`
- Create: `frontend/src/app/Layout.tsx`
- Modify: `frontend/src/app/App.tsx`
- Test: `frontend/src/app/__tests__/App.test.tsx`

**Step 1: Create `frontend/src/app/router/viewRegistry.ts`**

```typescript
import { lazy } from "react";

const DashboardPage = lazy(
  () => import("@/views/dashboard/DashboardPage")
);
const SessionsPage = lazy(
  () => import("@/views/sessions/SessionsPage")
);
const SessionDetailPage = lazy(
  () => import("@/views/sessions/SessionDetailPage")
);

export interface ViewEntry {
  id: string;
  path: string;
  component: React.LazyExoticComponent<React.ComponentType>;
  label?: string;
  nav: boolean;
}

export const viewRegistry: ViewEntry[] = [
  {
    id: "dashboard",
    path: "/dashboard",
    component: DashboardPage,
    label: "Dashboard",
    nav: true,
  },
  {
    id: "sessions",
    path: "/sessions",
    component: SessionsPage,
    label: "Sessions",
    nav: true,
  },
  {
    id: "session-detail",
    path: "/sessions/:id",
    component: SessionDetailPage,
    nav: false,
  },
];
```

**Step 2: Create `frontend/src/app/Layout.tsx`**

```tsx
import {
  Box,
  Flex,
  VStack,
  Link as ChakraLink,
  Heading,
  Divider,
} from "@chakra-ui/react";
import { Link, useLocation, Outlet } from "react-router-dom";
import { viewRegistry } from "./router/viewRegistry";

export function Layout() {
  const location = useLocation();

  const navItems = viewRegistry.filter((v) => v.nav);

  return (
    <Flex minH="100vh">
      <Box w="220px" bg="gray.50" p={4} borderRight="1px" borderColor="gray.200">
        <Heading size="md" mb={4}>
          Claudit
        </Heading>
        <Divider mb={4} />
        <VStack align="stretch" spacing={1}>
          {navItems.map((v) => (
            <ChakraLink
              as={Link}
              to={v.path}
              key={v.id}
              px={3}
              py={2}
              borderRadius="md"
              bg={location.pathname.startsWith(v.path) ? "blue.50" : "transparent"}
              color={location.pathname.startsWith(v.path) ? "blue.600" : "gray.700"}
              fontWeight={location.pathname.startsWith(v.path) ? "semibold" : "normal"}
              _hover={{ bg: "blue.50" }}
            >
              {v.label}
            </ChakraLink>
          ))}
        </VStack>
      </Box>
      <Box flex={1} overflow="auto">
        <Outlet />
      </Box>
    </Flex>
  );
}
```

**Step 3: Update `frontend/src/app/App.tsx`**

```tsx
import { ChakraProvider } from "@chakra-ui/react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Suspense } from "react";
import { Spinner, Center } from "@chakra-ui/react";
import { QueryProvider } from "./providers/QueryProvider";
import { Layout } from "./Layout";
import { viewRegistry } from "./router/viewRegistry";

function LoadingFallback() {
  return (
    <Center h="100vh">
      <Spinner size="xl" />
    </Center>
  );
}

export default function App() {
  return (
    <ChakraProvider>
      <QueryProvider>
        <BrowserRouter>
          <Suspense fallback={<LoadingFallback />}>
            <Routes>
              <Route element={<Layout />}>
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                {viewRegistry.map((v) => (
                  <Route key={v.id} path={v.path} element={<v.component />} />
                ))}
              </Route>
            </Routes>
          </Suspense>
        </BrowserRouter>
      </QueryProvider>
    </ChakraProvider>
  );
}
```

**Step 4: Write test `frontend/src/app/__tests__/App.test.tsx`**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "../App";

// Mock all lazy-loaded views
vi.mock("@/views/dashboard/DashboardPage", () => ({
  default: () => <div>Dashboard Mock</div>,
}));
vi.mock("@/views/sessions/SessionsPage", () => ({
  default: () => <div>Sessions Mock</div>,
}));
vi.mock("@/views/sessions/SessionDetailPage", () => ({
  default: () => <div>Session Detail Mock</div>,
}));

describe("App", () => {
  it("renders and redirects to dashboard", async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("Claudit")).toBeDefined();
    });
  });

  it("renders navigation links", async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText("Dashboard")).toBeDefined();
      expect(screen.getByText("Sessions")).toBeDefined();
    });
  });
});
```

**Step 5: Run test**

Run: `cd frontend && npx vitest run src/app/__tests__/App.test.tsx`
Expected: PASS (2 tests)

**Step 6: Verify full TypeScript compilation**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

**Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add view registry, routing, and layout"
```

---

## Phase 4: Integration & Deployment

### Task 4.1: Frontend Build Integration

**Files:**
- Modify: `backend/main.py` (already handles static files)
- Verify: `frontend/vite.config.ts` (output configured correctly)

**Step 1: Build the frontend**

Run: `cd frontend && npm run build`
Expected: Output to `frontend/dist/` with `index.html` and assets

**Step 2: Verify `backend/main.py` serves static files**

The code already has this at the bottom of `backend/main.py`:

```python
# Serve static files in production
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
```

Verify this path resolves correctly:

Run: `python -c "import os; print(os.path.exists('frontend/dist/index.html'))"`
Expected: `True`

**Step 3: Commit**

```bash
git add frontend/dist/ backend/
git commit -m "feat: integrate frontend build with backend static serving"
```

---

### Task 4.2: End-to-End Smoke Test

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_smoke.py`

**Step 1: Write the smoke test**

```python
# tests/integration/test_smoke.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


MOCK_SESSIONS = [
    {
        "session_id": "996a6297-0787-454a-94b8-96191aa0a22c",
        "user_id": "c35b69e8",
        "start_time": "2026-02-23T18:02:20Z",
        "end_time": "2026-02-23T19:30:00Z",
        "event_count": "111",
        "prompt_count": "5",
        "tool_calls": "29",
        "errors": "22",
        "total_cost_usd": "0.44",
    }
]

MOCK_SUMMARY = [
    {
        "total_sessions": "3",
        "total_users": "1",
        "total_events": "111",
        "total_prompts": "8",
        "total_api_calls": "24",
        "total_errors": "22",
        "total_cost_usd": "0.44",
    }
]

MOCK_TIMELINE = [
    {
        "event_name": "user_prompt",
        "timestamp": "2026-02-23T18:02:20.757Z",
        "sequence": 1,
        "session_id": "996a6297",
        "prompt_id": "efeed64b",
        "user_id": "c35b69e8",
        "tool_name": None,
        "model": None,
        "duration_ms": None,
        "cost_usd": None,
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "cache_creation_tokens": None,
        "error": None,
        "status_code": None,
        "success": None,
        "decision": None,
        "source": None,
        "prompt": "review OTEL config",
        "prompt_length": "18",
        "tool_result_size_bytes": None,
        "speed": None,
    },
    {
        "event_name": "api_request",
        "timestamp": "2026-02-23T18:02:25.000Z",
        "sequence": 2,
        "session_id": "996a6297",
        "prompt_id": "efeed64b",
        "user_id": "c35b69e8",
        "tool_name": None,
        "model": "claude-opus-4-6",
        "duration_ms": "7221",
        "cost_usd": "0.039",
        "input_tokens": "1",
        "output_tokens": "470",
        "cache_read_tokens": "47356",
        "cache_creation_tokens": "521",
        "error": None,
        "status_code": None,
        "success": None,
        "decision": None,
        "source": None,
        "prompt": None,
        "prompt_length": None,
        "tool_result_size_bytes": None,
        "speed": "65.1",
    },
]

MOCK_TOOLS = [
    {
        "tool_name": "Bash",
        "call_count": "15",
        "avg_duration_ms": "2100.5",
        "success_count": "14",
        "failure_count": "1",
        "total_result_bytes": "15000",
    }
]

MOCK_ERRORS = [
    {
        "model": "claude-haiku-4-5-20251001",
        "status_code": "404",
        "error": "endpoint does not exist",
        "error_count": "22",
        "avg_duration_ms": "344.0",
    }
]


def mock_execute_side_effect(query: str):
    """Route mock responses based on SQL query content."""
    q = query.lower()
    if "group by attributes['session.id']" in q and "limit" in q:
        return MOCK_SESSIONS
    if "count(distinct attributes['session.id'])" in q:
        return MOCK_SUMMARY
    if "order by cast(attributes['event.sequence']" in q:
        return MOCK_TIMELINE
    if "event.name'] = 'tool_result'" in q and "group by" in q:
        return MOCK_TOOLS
    if "event.name'] = 'api_error'" in q and "group by" in q:
        return MOCK_ERRORS
    return []


@pytest.fixture
def client():
    with patch("backend.routers.metrics.get_executor") as mock_met, \
         patch("backend.routers.sessions.get_executor") as mock_sess:
        executor = MagicMock()
        executor.execute.side_effect = mock_execute_side_effect
        mock_met.return_value = executor
        mock_sess.return_value = executor

        from backend.main import app
        yield TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_metrics_summary(client):
    response = client.get("/api/v1/metrics/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_sessions"] == "3"
    assert data["total_cost_usd"] == "0.44"


def test_metrics_tools(client):
    response = client.get("/api/v1/metrics/tools")
    assert response.status_code == 200
    data = response.json()
    assert len(data["tools"]) >= 1
    assert data["tools"][0]["tool_name"] == "Bash"


def test_metrics_errors(client):
    response = client.get("/api/v1/metrics/errors")
    assert response.status_code == 200
    data = response.json()
    assert len(data["errors"]) >= 1
    assert data["errors"][0]["status_code"] == "404"


def test_sessions_list(client):
    response = client.get("/api/v1/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) >= 1
    assert data["sessions"][0]["session_id"] == "996a6297-0787-454a-94b8-96191aa0a22c"


def test_session_timeline(client):
    response = client.get("/api/v1/sessions/996a6297/timeline")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "996a6297"
    assert len(data["events"]) == 2
    assert data["events"][0]["event_name"] == "user_prompt"
    assert data["events"][1]["event_name"] == "api_request"
```

**Step 2: Run the smoke test**

Run: `pytest tests/integration/test_smoke.py -v`
Expected: PASS (6 tests)

**Step 3: Run all backend tests together**

Run: `pytest tests/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/
git commit -m "test: add end-to-end smoke test with mock OTEL data"
```

---

### Task 4.3: Validate and Deploy to Databricks

**Step 1: Validate DAB bundle**

Run: `databricks bundle validate -t dev`
Expected: `Successfully validated bundle` (no errors)

**Step 2: Build frontend for production**

Run: `cd frontend && npm run build`
Expected: Output in `frontend/dist/` with no errors

**Step 3: Deploy to Databricks**

Run: `databricks bundle deploy -t dev`
Expected: Successful deployment message with app URL

**Step 4: Verify app is running**

Run: `databricks apps get claudit-observability --profile DEFAULT`
Expected: App status shows `RUNNING`

**Step 5: Commit**

```bash
git add -A
git commit -m "chore: validate and deploy claudit to Databricks Apps"
```

---

## Phase 5 (Backlog): Modular Extensions

### Backlog Module 1: Materialized Tables (Scale)

When direct queries become slow (>10K events):
- Create `resources/jobs.yml` with ETL job
- Create `etl/obs_materialization.py`
- Create `resources/schemas.yml` for materialized tables
- Add batch session summaries and daily rollups

### Backlog Module 2: MCP Server Logs

- Add `mcp_logs_table` config variable
- Create `backend/services/mcp_query_service.py`
- Create `backend/routers/mcp.py` with endpoints:
  - `GET /api/v1/mcp/servers` - MCP server stats
  - `GET /api/v1/mcp/calls` - MCP call details
- Create `frontend/src/views/mcp/` view
- Correlate MCP server logs with OTEL tool events via tool_name + timestamp

### Backlog Module 3: Inference Tables

- Add `inference_table` config variable
- Create `backend/services/inference_query_service.py`
- Create `backend/routers/inference.py` with endpoints:
  - `GET /api/v1/inference/requests` - LLM request/response payloads
  - `GET /api/v1/inference/session/{id}` - Inference calls for a session
- Create `frontend/src/views/inference/` view
- Link inference records to OTEL `api_request` events via timestamp + model

### Backlog Module 4: System Tables

- Create `backend/services/system_query_service.py`
- Create `backend/routers/system.py` with endpoints:
  - `GET /api/v1/system/billing` - Billing/usage from `system.billing.usage`
  - `GET /api/v1/system/serving` - Serving metrics from `system.serving.*`
- Create `frontend/src/views/costs/` view

### Backlog Module 5: User Correlation

- Create user mapping table (`user_id_hash` -> `email`)
- Add user lookup to session queries
- Create `frontend/src/views/users/` view
- Manager dashboard with per-user comparisons

### Backlog Module 8: Optimization Chatbot

Contextual advisor for model right-sizing based on Model Efficiency tab data:
- Recommend specific optimization methods: `--model` flag, CLAUDE.md directives, `/model` switching, MCP server config, API gateway routing, prompt optimization
- UX: inline recommendations panel, chat sidebar, or action cards per rightsizing opportunity
- Dependencies: Model Efficiency tab (done), drill-down details (done)

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-02-20-claudit-implementation.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
