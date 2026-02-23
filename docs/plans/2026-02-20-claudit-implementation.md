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
- Test: `tests/backend/test_sessions_router.py`

**Step 1: Write the failing test**

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

**Step 2: Write implementation**

```python
# backend/routers/sessions.py
from typing import Optional, List
from fastapi import APIRouter, Query
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
    query = query_service.build_sessions_list_query(limit=1, offset=0)
    # Re-query with session filter via timeline aggregation
    query = f"""
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
        FROM {query_service.logs_table}
        WHERE attributes['session.id'] = '{session_id}'
        GROUP BY attributes['session.id'], attributes['user.id']
    """.strip()
    rows = get_executor().execute(query)
    if not rows:
        from fastapi import HTTPException
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

**Step 3: Commit**

```bash
git add backend/routers/ tests/backend/
git commit -m "feat(backend): add sessions router with timeline endpoint"
```

---

## Phase 3: Frontend Core

### Task 3.1: Initialize React Frontend

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/app/App.tsx`
- Create: `frontend/src/app/providers/QueryProvider.tsx`
- Create: `frontend/src/types/api.ts`

Standard Vite + React + Chakra UI + TanStack Query setup. Configure vite proxy to FastAPI on port 8000.

**Step 1: Create frontend scaffold**

Follow standard Vite React TS template with Chakra UI provider, React Router, and TanStack Query provider.

**Step 2: Create types/api.ts matching backend models**

```typescript
// frontend/src/types/api.ts
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
  event_count: number;
  prompt_count: number;
  total_cost_usd: number;
  tool_calls: number;
  errors: number;
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
```

**Step 3: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): initialize React frontend with types and providers"
```

---

### Task 3.2: Build Dashboard View

**Files:**
- Create: `frontend/src/views/dashboard/DashboardPage.tsx`
- Create: `frontend/src/views/dashboard/components/SummaryCards.tsx`
- Create: `frontend/src/views/dashboard/components/ToolUsageTable.tsx`
- Create: `frontend/src/views/dashboard/components/ErrorsTable.tsx`
- Create: `frontend/src/shared/hooks/useApi.ts`

Build the analytics dashboard showing:
- Summary cards (total sessions, users, events, cost, errors)
- Tool usage table (name, call count, avg duration, success rate)
- MCP tool filter toggle
- Error breakdown table
- API performance stats

Use TanStack Query hooks to fetch from `/api/v1/metrics/*` endpoints.

**Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add analytics dashboard view"
```

---

### Task 3.3: Build Sessions List View

**Files:**
- Create: `frontend/src/views/sessions/SessionsPage.tsx`
- Create: `frontend/src/views/sessions/components/SessionCard.tsx`

Session list page with:
- List of sessions with summary stats (cost, events, prompts, errors)
- Click to navigate to session detail
- Pagination

**Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add sessions list view"
```

---

### Task 3.4: Build Session Timeline View

**Files:**
- Create: `frontend/src/views/sessions/SessionDetailPage.tsx`
- Create: `frontend/src/views/sessions/components/SessionTimeline.tsx`
- Create: `frontend/src/views/sessions/components/TimelineEvent.tsx`

Timeline view showing:
- Session header (id, user, duration, cost)
- Event filter chips (All, Prompts, API Calls, Tools, Errors)
- Chronological event list with color-coded event types
- Event detail expansion (show all attributes)

Event rendering by type:
- `user_prompt`: Show prompt text, prompt_length
- `api_request`: Show model, duration, tokens (in/out/cache), cost
- `api_error`: Show model, error message, status_code, duration
- `tool_decision`: Show tool_name, decision, source
- `tool_result`: Show tool_name, duration, success, result_size

**Commit**

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

Wire up routing:
- `/` -> redirect to `/dashboard`
- `/dashboard` -> DashboardPage
- `/sessions` -> SessionsPage
- `/sessions/:id` -> SessionDetailPage

Navigation sidebar with Dashboard and Sessions links.

**Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): add view registry, routing, and layout"
```

---

## Phase 4: Integration & Deployment

### Task 4.1: Frontend Build Integration

**Files:**
- Modify: `backend/main.py` (serve frontend dist)
- Modify: `frontend/vite.config.ts` (output to correct dist path)

Configure Vite to build into `frontend/dist/`. FastAPI serves this as static files. Vite dev proxy points to FastAPI.

**Commit**

```bash
git add backend/ frontend/
git commit -m "feat: integrate frontend build with backend static serving"
```

---

### Task 4.2: End-to-End Smoke Test

**Files:**
- Test: `tests/integration/test_smoke.py`

Integration test that:
1. Starts FastAPI test client
2. Mocks SqlExecutor with realistic OTEL data
3. Verifies `/api/v1/metrics/summary` returns data
4. Verifies `/api/v1/sessions` returns sessions
5. Verifies `/api/v1/sessions/{id}/timeline` returns events
6. Verifies `/health` returns healthy

**Commit**

```bash
git add tests/
git commit -m "test: add end-to-end smoke test with mock OTEL data"
```

---

### Task 4.3: Deploy to Databricks

**Steps:**
1. `databricks bundle validate -t dev`
2. `databricks bundle deploy -t dev`
3. Verify app is running and accessible
4. Test live queries against real OTEL tables

**Commit**

```bash
git commit -m "chore: verify deployment configuration"
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
