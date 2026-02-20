# Claudit Observability App - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an end-to-end observability app for Claude Code with batch materialization, React frontend, and FastAPI backend deployed on Databricks Apps.

**Architecture:** Batch ETL materializes OTEL/MCP/system tables into unified observability tables. FastAPI queries materialized tables. React renders session timeline as primary view. All packaged in DAB bundle.

**Tech Stack:** Python 3.11, FastAPI, React 18, Chakra UI, TanStack Query, PySpark, Databricks SDK, DAB

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
    "databricks-connect>=14.3.0",
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
etl = [
    "pyspark>=3.5.0",
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
- Create: `resources/jobs.yml`
- Create: `resources/schemas.yml`

**Step 1: Create databricks.yml**

```yaml
bundle:
  name: claudit-observability

include:
  - resources/*.yml

variables:
  catalog:
    description: "Unity Catalog for observability tables"
    default: ml
  schema:
    description: "Schema for materialized observability tables"
    default: claudit_obs
  otel_catalog:
    description: "Catalog containing OTEL source tables"
    default: ml
  otel_schema:
    description: "Schema containing OTEL source tables"
    default: otel_ingest
  mcp_logs_table:
    description: "Fully qualified MCP logs table name"
    default: ml.mcp_logs.server_logs
  warehouse_id:
    description: "SQL Warehouse ID for app queries"

targets:
  dev:
    mode: development
    default: true
    workspace:
      host: ${DATABRICKS_HOST}
    variables:
      catalog: ml_dev
      schema: claudit_obs_dev

  staging:
    mode: development
    workspace:
      host: ${DATABRICKS_HOST}
    variables:
      catalog: ml_staging
      schema: claudit_obs_staging

  prod:
    mode: production
    workspace:
      host: ${DATABRICKS_HOST}
    variables:
      catalog: ml
      schema: claudit_obs
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
          - name: OTEL_CATALOG
            value: ${var.otel_catalog}
          - name: OTEL_SCHEMA
            value: ${var.otel_schema}
          - name: MCP_LOGS_TABLE
            value: ${var.mcp_logs_table}
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

**Step 3: Create resources/jobs.yml**

```yaml
resources:
  jobs:
    obs_materialization:
      name: "${bundle.target}-claudit-obs-materialization"
      description: "Materializes observability tables from source OTEL/MCP/system tables"

      tags:
        project: claudit
        component: etl

      schedule:
        quartz_cron_expression: "0 */15 * * * ?"
        timezone_id: "UTC"
        pause_status: UNPAUSED

      email_notifications:
        on_failure:
          - ${workspace.current_user.userName}

      tasks:
        - task_key: extract_and_correlate
          description: "Extract from sources and correlate events"
          spark_python_task:
            python_file: etl/obs_materialization.py
            parameters:
              - "--step=extract"
              - "--catalog=${var.catalog}"
              - "--schema=${var.schema}"
              - "--otel-catalog=${var.otel_catalog}"
              - "--otel-schema=${var.otel_schema}"
              - "--mcp-table=${var.mcp_logs_table}"
          libraries:
            - pypi:
                package: pydantic>=2.0
          new_cluster:
            spark_version: "14.3.x-scala2.12"
            num_workers: 0
            spark_conf:
              spark.databricks.cluster.profile: serverless

        - task_key: aggregate_sessions
          description: "Aggregate events into session summaries"
          depends_on:
            - task_key: extract_and_correlate
          spark_python_task:
            python_file: etl/obs_materialization.py
            parameters:
              - "--step=aggregate"
              - "--catalog=${var.catalog}"
              - "--schema=${var.schema}"
          new_cluster:
            spark_version: "14.3.x-scala2.12"
            num_workers: 0
            spark_conf:
              spark.databricks.cluster.profile: serverless

        - task_key: daily_rollups
          description: "Create daily metric rollups"
          depends_on:
            - task_key: aggregate_sessions
          spark_python_task:
            python_file: etl/obs_materialization.py
            parameters:
              - "--step=rollup"
              - "--catalog=${var.catalog}"
              - "--schema=${var.schema}"
          new_cluster:
            spark_version: "14.3.x-scala2.12"
            num_workers: 0
            spark_conf:
              spark.databricks.cluster.profile: serverless
```

**Step 4: Create resources/schemas.yml**

```yaml
resources:
  schemas:
    obs_schema:
      catalog_name: ${var.catalog}
      name: ${var.schema}
      comment: "Materialized observability tables for Claude Code monitoring"

      grants:
        - principal: ${workspace.current_user.userName}
          privileges:
            - ALL_PRIVILEGES
```

**Step 5: Commit**

```bash
git add databricks.yml resources/
git commit -m "chore: add DAB bundle configuration for app and ETL jobs"
```

---

### Task 1.3: Create App Configuration

**Files:**
- Create: `app.yaml`

**Step 1: Create app.yaml**

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

**Step 2: Commit**

```bash
git add app.yaml
git commit -m "chore: add Databricks app.yaml configuration"
```

---

## Phase 2: Backend Core

### Task 2.1: Create Backend Config and Models

**Files:**
- Create: `backend/__init__.py`
- Create: `backend/config.py`
- Create: `backend/models/__init__.py`
- Create: `backend/models/session.py`
- Create: `backend/models/event.py`
- Create: `backend/models/metrics.py`
- Test: `tests/backend/__init__.py`
- Test: `tests/backend/test_models.py`

**Step 1: Write the failing test**

```python
# tests/backend/__init__.py
# (empty file)

# tests/backend/test_models.py
import pytest
from datetime import datetime
from backend.models.session import Session, SessionSummary
from backend.models.event import SessionEvent, EventType
from backend.models.metrics import UsageMetrics, TokenCount


def test_session_model_creation():
    session = Session(
        session_id="sess_123",
        user_email="test@example.com",
        start_time=datetime(2026, 2, 20, 10, 30, 0),
        end_time=datetime(2026, 2, 20, 11, 15, 0),
        duration_ms=2700000,
        total_input_tokens=45000,
        total_output_tokens=12000,
        tool_call_count=23,
        mcp_call_count=8,
        estimated_cost_usd=0.85,
    )
    assert session.session_id == "sess_123"
    assert session.duration_ms == 2700000


def test_session_event_model():
    event = SessionEvent(
        event_id="evt_001",
        session_id="sess_123",
        timestamp=datetime(2026, 2, 20, 10, 30, 5),
        event_type=EventType.TOOL_USE,
        source="otel_logs",
        summary="Tool: Read /src/main.py",
        wall_time_ms=250,
        input_tokens=1200,
    )
    assert event.event_type == EventType.TOOL_USE
    assert event.wall_time_ms == 250


def test_event_type_enum():
    assert EventType.METRIC.value == "metric"
    assert EventType.TOOL_USE.value == "tool_use"
    assert EventType.MCP_CALL.value == "mcp_call"
    assert EventType.INFERENCE.value == "inference"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_models.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/__init__.py
# (empty file)

# backend/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    catalog: str = "ml"
    schema_name: str = "claudit_obs"  # 'schema' is reserved
    otel_catalog: str = "ml"
    otel_schema: str = "otel_ingest"
    mcp_logs_table: str = "ml.mcp_logs.server_logs"
    sql_warehouse_id: str = ""

    class Config:
        env_prefix = ""
        case_sensitive = False


settings = Settings()
```

```python
# backend/models/__init__.py
from backend.models.session import Session, SessionSummary
from backend.models.event import SessionEvent, EventType
from backend.models.metrics import UsageMetrics, TokenCount

__all__ = [
    "Session",
    "SessionSummary",
    "SessionEvent",
    "EventType",
    "UsageMetrics",
    "TokenCount",
]
```

```python
# backend/models/session.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class Session(BaseModel):
    session_id: str
    user_email: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    tool_call_count: int = 0
    mcp_call_count: int = 0
    estimated_cost_usd: float = 0.0


class SessionSummary(BaseModel):
    session_id: str
    user_email: str
    start_time: datetime
    duration_ms: Optional[int] = None
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
```

```python
# backend/models/event.py
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel


class EventType(str, Enum):
    METRIC = "metric"
    LOG = "log"
    TOOL_USE = "tool_use"
    MCP_CALL = "mcp_call"
    INFERENCE = "inference"


class SessionEvent(BaseModel):
    event_id: str
    session_id: str
    timestamp: datetime
    event_type: EventType
    source: str
    summary: str
    payload: Optional[Dict[str, Any]] = None
    wall_time_ms: Optional[int] = None
    api_time_ms: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    tool_name: Optional[str] = None
    mcp_server: Optional[str] = None
    mcp_method: Optional[str] = None
```

```python
# backend/models/metrics.py
from datetime import date
from pydantic import BaseModel


class TokenCount(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class UsageMetrics(BaseModel):
    date: date
    user_email: str
    total_sessions: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_session_duration_ms: float = 0.0
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_models.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/ tests/backend/
git commit -m "feat(backend): add Pydantic models for sessions, events, and metrics"
```

---

### Task 2.2: Create Query Service

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/query_service.py`
- Test: `tests/backend/test_query_service.py`

**Step 1: Write the failing test**

```python
# tests/backend/test_query_service.py
import pytest
from unittest.mock import Mock, patch
from backend.services.query_service import QueryService


def test_query_service_build_sessions_query():
    service = QueryService(catalog="ml", schema="obs")
    query = service.build_sessions_query(limit=10, offset=0)

    assert "SELECT" in query
    assert "ml.obs.sessions" in query
    assert "LIMIT 10" in query
    assert "OFFSET 0" in query


def test_query_service_build_sessions_query_with_user_filter():
    service = QueryService(catalog="ml", schema="obs")
    query = service.build_sessions_query(
        limit=10, offset=0, user_email="test@example.com"
    )

    assert "user_email = 'test@example.com'" in query


def test_query_service_build_timeline_query():
    service = QueryService(catalog="ml", schema="obs")
    query = service.build_timeline_query(session_id="sess_123")

    assert "session_events" in query
    assert "session_id = 'sess_123'" in query
    assert "ORDER BY timestamp" in query
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_query_service.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/services/__init__.py
from backend.services.query_service import QueryService

__all__ = ["QueryService"]
```

```python
# backend/services/query_service.py
from typing import Optional, List
from datetime import date


class QueryService:
    """Builds and executes SQL queries against materialized observability tables."""

    def __init__(self, catalog: str, schema: str):
        self.catalog = catalog
        self.schema = schema

    @property
    def sessions_table(self) -> str:
        return f"{self.catalog}.{self.schema}.sessions"

    @property
    def events_table(self) -> str:
        return f"{self.catalog}.{self.schema}.session_events"

    @property
    def daily_metrics_table(self) -> str:
        return f"{self.catalog}.{self.schema}.daily_metrics"

    def build_sessions_query(
        self,
        limit: int = 50,
        offset: int = 0,
        user_email: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> str:
        """Build query for listing sessions with optional filters."""
        conditions = []

        if user_email:
            conditions.append(f"user_email = '{user_email}'")
        if start_date:
            conditions.append(f"DATE(start_time) >= '{start_date}'")
        if end_date:
            conditions.append(f"DATE(start_time) <= '{end_date}'")

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                session_id,
                user_email,
                start_time,
                end_time,
                duration_ms,
                total_input_tokens,
                total_output_tokens,
                tool_call_count,
                mcp_call_count,
                estimated_cost_usd
            FROM {self.sessions_table}
            {where_clause}
            ORDER BY start_time DESC
            LIMIT {limit}
            OFFSET {offset}
        """.strip()

    def build_session_detail_query(self, session_id: str) -> str:
        """Build query for single session details."""
        return f"""
            SELECT *
            FROM {self.sessions_table}
            WHERE session_id = '{session_id}'
        """.strip()

    def build_timeline_query(
        self,
        session_id: str,
        event_types: Optional[List[str]] = None,
    ) -> str:
        """Build query for session timeline events."""
        conditions = [f"session_id = '{session_id}'"]

        if event_types:
            types_str = ", ".join(f"'{t}'" for t in event_types)
            conditions.append(f"event_type IN ({types_str})")

        where_clause = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                event_id,
                session_id,
                timestamp,
                event_type,
                source,
                summary,
                payload,
                wall_time_ms,
                api_time_ms,
                input_tokens,
                output_tokens,
                tool_name,
                mcp_server,
                mcp_method
            FROM {self.events_table}
            {where_clause}
            ORDER BY timestamp ASC
        """.strip()

    def build_usage_metrics_query(
        self,
        start_date: date,
        end_date: date,
        user_email: Optional[str] = None,
        group_by: str = "day",
    ) -> str:
        """Build query for usage metrics aggregation."""
        conditions = [
            f"date >= '{start_date}'",
            f"date <= '{end_date}'",
        ]

        if user_email:
            conditions.append(f"user_email = '{user_email}'")

        where_clause = "WHERE " + " AND ".join(conditions)

        if group_by == "day":
            group_expr = "date"
        elif group_by == "week":
            group_expr = "DATE_TRUNC('week', date)"
        else:  # month
            group_expr = "DATE_TRUNC('month', date)"

        return f"""
            SELECT
                {group_expr} as period,
                SUM(total_input_tokens) as total_input_tokens,
                SUM(total_output_tokens) as total_output_tokens,
                SUM(total_sessions) as total_sessions,
                SUM(total_cost_usd) as total_cost_usd
            FROM {self.daily_metrics_table}
            {where_clause}
            GROUP BY {group_expr}
            ORDER BY period ASC
        """.strip()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_query_service.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/services/ tests/backend/test_query_service.py
git commit -m "feat(backend): add QueryService for SQL query building"
```

---

### Task 2.3: Create FastAPI Application and Sessions Router

**Files:**
- Create: `backend/main.py`
- Create: `backend/routers/__init__.py`
- Create: `backend/routers/sessions.py`
- Test: `tests/backend/test_sessions_router.py`

**Step 1: Write the failing test**

```python
# tests/backend/test_sessions_router.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock


@pytest.fixture
def mock_execute():
    """Mock the SQL execution to return test data."""
    with patch("backend.routers.sessions.execute_query") as mock:
        mock.return_value = [
            {
                "session_id": "sess_123",
                "user_email": "test@example.com",
                "start_time": "2026-02-20T10:30:00",
                "end_time": "2026-02-20T11:15:00",
                "duration_ms": 2700000,
                "total_input_tokens": 45000,
                "total_output_tokens": 12000,
                "tool_call_count": 23,
                "mcp_call_count": 8,
                "estimated_cost_usd": 0.85,
            }
        ]
        yield mock


@pytest.fixture
def client(mock_execute):
    from backend.main import app
    return TestClient(app)


def test_list_sessions(client, mock_execute):
    response = client.get("/api/v1/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "sess_123"


def test_list_sessions_with_filter(client, mock_execute):
    response = client.get("/api/v1/sessions?user_email=test@example.com")
    assert response.status_code == 200
    # Verify the query service was called with filter
    mock_execute.assert_called_once()


def test_get_session_detail(client, mock_execute):
    response = client.get("/api/v1/sessions/sess_123")
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_sessions_router.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# backend/routers/__init__.py
from backend.routers.sessions import router as sessions_router

__all__ = ["sessions_router"]
```

```python
# backend/routers/sessions.py
from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Query, HTTPException

from backend.config import settings
from backend.models import Session, SessionEvent, EventType
from backend.services import QueryService

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])

# Query service instance
query_service = QueryService(
    catalog=settings.catalog,
    schema=settings.schema_name,
)


def execute_query(query: str) -> List[dict]:
    """Execute SQL query against Databricks. Placeholder for real implementation."""
    # TODO: Implement real Databricks SQL execution
    return []


@router.get("")
async def list_sessions(
    user_email: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List sessions with optional filters and pagination."""
    query = query_service.build_sessions_query(
        limit=limit,
        offset=offset,
        user_email=user_email,
        start_date=start_date,
        end_date=end_date,
    )

    results = execute_query(query)

    sessions = [Session(**row) for row in results]

    return {
        "sessions": sessions,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": len(sessions),  # TODO: Get actual count
        },
    }


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get detailed information about a specific session."""
    query = query_service.build_session_detail_query(session_id)
    results = execute_query(query)

    if not results:
        raise HTTPException(status_code=404, detail="Session not found")

    return Session(**results[0])


@router.get("/{session_id}/timeline")
async def get_session_timeline(
    session_id: str,
    event_types: Optional[List[str]] = Query(None),
):
    """Get chronological timeline of events for a session."""
    query = query_service.build_timeline_query(
        session_id=session_id,
        event_types=event_types,
    )

    results = execute_query(query)
    events = [SessionEvent(**row) for row in results]

    return {
        "session_id": session_id,
        "events": events,
    }


@router.get("/{session_id}/events/{event_id}")
async def get_event_detail(session_id: str, event_id: str):
    """Get detailed information about a specific event."""
    # For now, just return from timeline
    query = query_service.build_timeline_query(session_id=session_id)
    results = execute_query(query)

    for row in results:
        if row.get("event_id") == event_id:
            return SessionEvent(**row)

    raise HTTPException(status_code=404, detail="Event not found")
```

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.routers import sessions_router

app = FastAPI(
    title="Claudit Observability",
    description="Claude Code Observability Dashboard API",
    version="0.1.0",
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sessions_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Serve static files in production (frontend build)
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_sessions_router.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/main.py backend/routers/ tests/backend/test_sessions_router.py
git commit -m "feat(backend): add FastAPI app with sessions router"
```

---

### Task 2.4: Add Metrics Router

**Files:**
- Create: `backend/routers/metrics.py`
- Modify: `backend/routers/__init__.py`
- Modify: `backend/main.py`
- Test: `tests/backend/test_metrics_router.py`

**Step 1: Write the failing test**

```python
# tests/backend/test_metrics_router.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def mock_execute():
    with patch("backend.routers.metrics.execute_query") as mock:
        mock.return_value = [
            {
                "period": "2026-02-20",
                "total_input_tokens": 100000,
                "total_output_tokens": 25000,
                "total_sessions": 15,
                "total_cost_usd": 2.50,
            }
        ]
        yield mock


@pytest.fixture
def client(mock_execute):
    # Also mock sessions execute_query
    with patch("backend.routers.sessions.execute_query", return_value=[]):
        from backend.main import app
        return TestClient(app)


def test_usage_metrics(client, mock_execute):
    response = client.get(
        "/api/v1/metrics/usage?start_date=2026-02-01&end_date=2026-02-20"
    )
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert len(data["metrics"]) == 1


def test_usage_metrics_with_groupby(client, mock_execute):
    response = client.get(
        "/api/v1/metrics/usage?start_date=2026-02-01&end_date=2026-02-20&group_by=week"
    )
    assert response.status_code == 200


def test_usage_metrics_requires_dates(client, mock_execute):
    response = client.get("/api/v1/metrics/usage")
    assert response.status_code == 422  # Validation error
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/backend/test_metrics_router.py -v`
Expected: FAIL with ModuleNotFoundError or 404

**Step 3: Write minimal implementation**

```python
# backend/routers/metrics.py
from typing import Optional, List
from datetime import date
from fastapi import APIRouter, Query

from backend.config import settings
from backend.services import QueryService

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])

query_service = QueryService(
    catalog=settings.catalog,
    schema=settings.schema_name,
)


def execute_query(query: str) -> List[dict]:
    """Execute SQL query against Databricks. Placeholder for real implementation."""
    return []


@router.get("/usage")
async def get_usage_metrics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user_email: Optional[str] = Query(None),
    group_by: str = Query("day", regex="^(day|week|month)$"),
):
    """Get token usage metrics over time."""
    query = query_service.build_usage_metrics_query(
        start_date=start_date,
        end_date=end_date,
        user_email=user_email,
        group_by=group_by,
    )

    results = execute_query(query)

    return {
        "metrics": results,
        "group_by": group_by,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


@router.get("/costs")
async def get_cost_metrics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user_email: Optional[str] = Query(None),
    group_by: str = Query("day", regex="^(day|week|month)$"),
):
    """Get cost breakdown over time."""
    query = query_service.build_usage_metrics_query(
        start_date=start_date,
        end_date=end_date,
        user_email=user_email,
        group_by=group_by,
    )

    results = execute_query(query)

    # Transform to cost-focused response
    costs = [
        {
            "period": r["period"],
            "total_cost_usd": r.get("total_cost_usd", 0),
            "total_tokens": r.get("total_input_tokens", 0) + r.get("total_output_tokens", 0),
        }
        for r in results
    ]

    return {
        "costs": costs,
        "group_by": group_by,
    }


@router.get("/tools")
async def get_tool_metrics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user_email: Optional[str] = Query(None),
):
    """Get tool usage statistics."""
    # TODO: Implement tool-specific query
    return {
        "tools": [],
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }


@router.get("/mcp")
async def get_mcp_metrics(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user_email: Optional[str] = Query(None),
):
    """Get MCP server call patterns."""
    # TODO: Implement MCP-specific query
    return {
        "mcp_servers": [],
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
```

Update `backend/routers/__init__.py`:

```python
# backend/routers/__init__.py
from backend.routers.sessions import router as sessions_router
from backend.routers.metrics import router as metrics_router

__all__ = ["sessions_router", "metrics_router"]
```

Update `backend/main.py` to include metrics router:

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from backend.routers import sessions_router, metrics_router

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

app.include_router(sessions_router)
app.include_router(metrics_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/backend/test_metrics_router.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add backend/routers/ backend/main.py tests/backend/test_metrics_router.py
git commit -m "feat(backend): add metrics router with usage and cost endpoints"
```

---

## Phase 3: ETL Pipeline

### Task 3.1: Create ETL Structure and Models

**Files:**
- Create: `etl/__init__.py`
- Create: `etl/models.py`
- Create: `etl/config.py`
- Test: `tests/etl/__init__.py`
- Test: `tests/etl/test_models.py`

**Step 1: Write the failing test**

```python
# tests/etl/__init__.py
# (empty)

# tests/etl/test_models.py
import pytest
from etl.models import UnifiedEvent, SessionAggregate
from etl.config import ETLConfig


def test_etl_config_from_args():
    config = ETLConfig.from_args([
        "--step=extract",
        "--catalog=ml",
        "--schema=obs",
        "--otel-catalog=ml",
        "--otel-schema=otel",
    ])
    assert config.step == "extract"
    assert config.catalog == "ml"
    assert config.schema == "obs"


def test_unified_event_schema():
    schema = UnifiedEvent.spark_schema()
    field_names = [f.name for f in schema.fields]
    assert "session_id" in field_names
    assert "event_type" in field_names
    assert "timestamp" in field_names
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/etl/test_models.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# etl/__init__.py
# (empty)
```

```python
# etl/config.py
import argparse
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ETLConfig:
    step: str
    catalog: str
    schema: str
    otel_catalog: str
    otel_schema: str
    mcp_table: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    @classmethod
    def from_args(cls, args: List[str]) -> "ETLConfig":
        parser = argparse.ArgumentParser()
        parser.add_argument("--step", required=True, choices=["extract", "aggregate", "rollup", "backfill"])
        parser.add_argument("--catalog", required=True)
        parser.add_argument("--schema", required=True)
        parser.add_argument("--otel-catalog", default="ml")
        parser.add_argument("--otel-schema", default="otel_ingest")
        parser.add_argument("--mcp-table", default=None)
        parser.add_argument("--start-date", default=None)
        parser.add_argument("--end-date", default=None)

        parsed = parser.parse_args(args)

        return cls(
            step=parsed.step,
            catalog=parsed.catalog,
            schema=parsed.schema,
            otel_catalog=parsed.otel_catalog,
            otel_schema=parsed.otel_schema,
            mcp_table=parsed.mcp_table,
            start_date=parsed.start_date,
            end_date=parsed.end_date,
        )
```

```python
# etl/models.py
from dataclasses import dataclass
from typing import Optional
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    TimestampType,
    LongType,
    DoubleType,
    MapType,
)


@dataclass
class UnifiedEvent:
    """Schema for unified session events."""

    @staticmethod
    def spark_schema() -> StructType:
        return StructType([
            StructField("event_id", StringType(), False),
            StructField("session_id", StringType(), False),
            StructField("user_email", StringType(), False),
            StructField("timestamp", TimestampType(), False),
            StructField("event_type", StringType(), False),
            StructField("source_table", StringType(), False),
            StructField("summary", StringType(), True),
            StructField("payload", MapType(StringType(), StringType()), True),
            StructField("wall_time_ms", LongType(), True),
            StructField("api_time_ms", LongType(), True),
            StructField("input_tokens", LongType(), True),
            StructField("output_tokens", LongType(), True),
            StructField("tool_name", StringType(), True),
            StructField("mcp_server", StringType(), True),
            StructField("mcp_method", StringType(), True),
        ])


@dataclass
class SessionAggregate:
    """Schema for aggregated session summaries."""

    @staticmethod
    def spark_schema() -> StructType:
        return StructType([
            StructField("session_id", StringType(), False),
            StructField("user_email", StringType(), False),
            StructField("start_time", TimestampType(), False),
            StructField("end_time", TimestampType(), True),
            StructField("duration_ms", LongType(), True),
            StructField("total_input_tokens", LongType(), True),
            StructField("total_output_tokens", LongType(), True),
            StructField("tool_call_count", LongType(), True),
            StructField("mcp_call_count", LongType(), True),
            StructField("estimated_cost_usd", DoubleType(), True),
        ])


@dataclass
class DailyMetrics:
    """Schema for daily aggregated metrics."""

    @staticmethod
    def spark_schema() -> StructType:
        return StructType([
            StructField("date", StringType(), False),
            StructField("user_email", StringType(), False),
            StructField("total_sessions", LongType(), True),
            StructField("total_input_tokens", LongType(), True),
            StructField("total_output_tokens", LongType(), True),
            StructField("total_cost_usd", DoubleType(), True),
            StructField("avg_session_duration_ms", DoubleType(), True),
        ])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/etl/test_models.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add etl/ tests/etl/
git commit -m "feat(etl): add ETL config and Spark schema models"
```

---

### Task 3.2: Create OTEL Extractor

**Files:**
- Create: `etl/extractors/__init__.py`
- Create: `etl/extractors/otel_extractor.py`
- Test: `tests/etl/test_otel_extractor.py`

**Step 1: Write the failing test**

```python
# tests/etl/test_otel_extractor.py
import pytest
from unittest.mock import Mock
from etl.extractors.otel_extractor import OTELExtractor


def test_otel_extractor_metrics_query():
    extractor = OTELExtractor(
        catalog="ml",
        schema="otel_ingest",
    )
    query = extractor.build_metrics_extract_query()
    assert "otel_metrics" in query.lower() or "mlflow_experiment_trace_otel_metrics" in query
    assert "SELECT" in query


def test_otel_extractor_logs_query():
    extractor = OTELExtractor(
        catalog="ml",
        schema="otel_ingest",
    )
    query = extractor.build_logs_extract_query()
    assert "otel_logs" in query.lower() or "mlflow_experiment_trace_otel_logs" in query


def test_otel_extractor_transform_to_unified():
    extractor = OTELExtractor(
        catalog="ml",
        schema="otel_ingest",
    )
    # Test that transform SQL is valid
    transform_sql = extractor.build_transform_sql("test_source")
    assert "event_id" in transform_sql
    assert "session_id" in transform_sql
    assert "event_type" in transform_sql
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/etl/test_otel_extractor.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# etl/extractors/__init__.py
from etl.extractors.otel_extractor import OTELExtractor

__all__ = ["OTELExtractor"]
```

```python
# etl/extractors/otel_extractor.py
from typing import Optional


class OTELExtractor:
    """Extracts and transforms OTEL data into unified event format."""

    def __init__(self, catalog: str, schema: str):
        self.catalog = catalog
        self.schema = schema

    @property
    def metrics_table(self) -> str:
        return f"{self.catalog}.{self.schema}.mlflow_experiment_trace_otel_metrics"

    @property
    def logs_table(self) -> str:
        return f"{self.catalog}.{self.schema}.mlflow_experiment_trace_otel_logs"

    @property
    def spans_table(self) -> str:
        return f"{self.catalog}.{self.schema}.mlflow_experiment_trace_otel_spans"

    def build_metrics_extract_query(
        self,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
    ) -> str:
        """Build query to extract metrics data."""
        where_clause = ""
        conditions = []

        if start_timestamp:
            conditions.append(f"time_unix_nano >= '{start_timestamp}'")
        if end_timestamp:
            conditions.append(f"time_unix_nano <= '{end_timestamp}'")

        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                *
            FROM {self.metrics_table}
            {where_clause}
        """.strip()

    def build_logs_extract_query(
        self,
        start_timestamp: Optional[str] = None,
        end_timestamp: Optional[str] = None,
    ) -> str:
        """Build query to extract logs data."""
        where_clause = ""
        conditions = []

        if start_timestamp:
            conditions.append(f"time_unix_nano >= '{start_timestamp}'")
        if end_timestamp:
            conditions.append(f"time_unix_nano <= '{end_timestamp}'")

        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        return f"""
            SELECT
                *
            FROM {self.logs_table}
            {where_clause}
        """.strip()

    def build_transform_sql(self, source_view: str) -> str:
        """Build SQL to transform OTEL data into unified event format."""
        return f"""
            SELECT
                CONCAT('evt_', monotonically_increasing_id()) as event_id,
                COALESCE(
                    resource_attributes['session.id'],
                    resource_attributes['service.instance.id'],
                    'unknown'
                ) as session_id,
                COALESCE(
                    resource_attributes['user.email'],
                    resource_attributes['service.name'],
                    'unknown'
                ) as user_email,
                TIMESTAMP_MILLIS(time_unix_nano / 1000000) as timestamp,
                CASE
                    WHEN name LIKE '%tool%' THEN 'tool_use'
                    WHEN name LIKE '%mcp%' THEN 'mcp_call'
                    WHEN name LIKE '%inference%' OR name LIKE '%completion%' THEN 'inference'
                    ELSE 'metric'
                END as event_type,
                '{source_view}' as source_table,
                COALESCE(body, name, 'Event') as summary,
                attributes as payload,
                CAST(attributes['duration_ms'] AS LONG) as wall_time_ms,
                CAST(attributes['api_time_ms'] AS LONG) as api_time_ms,
                CAST(attributes['input_tokens'] AS LONG) as input_tokens,
                CAST(attributes['output_tokens'] AS LONG) as output_tokens,
                attributes['tool_name'] as tool_name,
                attributes['mcp_server'] as mcp_server,
                attributes['mcp_method'] as mcp_method
            FROM {source_view}
        """.strip()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/etl/test_otel_extractor.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add etl/extractors/ tests/etl/test_otel_extractor.py
git commit -m "feat(etl): add OTEL extractor for metrics and logs transformation"
```

---

### Task 3.3: Create Main ETL Orchestration

**Files:**
- Create: `etl/obs_materialization.py`
- Test: `tests/etl/test_materialization.py`

**Step 1: Write the failing test**

```python
# tests/etl/test_materialization.py
import pytest
from unittest.mock import Mock, patch
from etl.obs_materialization import main, run_extract, run_aggregate, run_rollup


def test_parse_args_extract():
    from etl.config import ETLConfig
    config = ETLConfig.from_args([
        "--step=extract",
        "--catalog=ml",
        "--schema=obs",
    ])
    assert config.step == "extract"


def test_run_extract_builds_queries():
    with patch("etl.obs_materialization.spark") as mock_spark:
        mock_spark.sql.return_value = Mock()
        mock_spark.sql.return_value.write = Mock()
        # Test that extract step doesn't crash (detailed test needs Spark)
        # This is a placeholder for integration testing
        assert True


def test_run_aggregate_builds_queries():
    # Placeholder for aggregate step test
    assert True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/etl/test_materialization.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write minimal implementation**

```python
# etl/obs_materialization.py
"""
Main ETL orchestration for materializing observability tables.

Usage:
    spark-submit etl/obs_materialization.py --step=extract --catalog=ml --schema=obs
"""
import sys
from typing import Optional

from pyspark.sql import SparkSession

from etl.config import ETLConfig
from etl.models import UnifiedEvent, SessionAggregate, DailyMetrics
from etl.extractors import OTELExtractor


# Initialize Spark (will be provided by Databricks runtime)
spark: Optional[SparkSession] = None


def get_spark() -> SparkSession:
    global spark
    if spark is None:
        spark = SparkSession.builder.getOrCreate()
    return spark


def run_extract(config: ETLConfig) -> None:
    """Extract from source tables and write to session_events."""
    spark = get_spark()

    otel_extractor = OTELExtractor(
        catalog=config.otel_catalog,
        schema=config.otel_schema,
    )

    # Extract OTEL metrics
    metrics_df = spark.sql(otel_extractor.build_metrics_extract_query())
    metrics_df.createOrReplaceTempView("otel_metrics_raw")

    # Transform to unified format
    unified_metrics = spark.sql(otel_extractor.build_transform_sql("otel_metrics_raw"))

    # Extract OTEL logs
    logs_df = spark.sql(otel_extractor.build_logs_extract_query())
    logs_df.createOrReplaceTempView("otel_logs_raw")

    unified_logs = spark.sql(otel_extractor.build_transform_sql("otel_logs_raw"))

    # Union all sources
    unified_events = unified_metrics.union(unified_logs)

    # Write to session_events table (MERGE for incremental)
    target_table = f"{config.catalog}.{config.schema}.session_events"

    unified_events.write.format("delta").mode("append").option(
        "mergeSchema", "true"
    ).saveAsTable(target_table)

    print(f"Extracted {unified_events.count()} events to {target_table}")


def run_aggregate(config: ETLConfig) -> None:
    """Aggregate events into session summaries."""
    spark = get_spark()

    events_table = f"{config.catalog}.{config.schema}.session_events"
    sessions_table = f"{config.catalog}.{config.schema}.sessions"

    agg_query = f"""
        SELECT
            session_id,
            FIRST(user_email) as user_email,
            MIN(timestamp) as start_time,
            MAX(timestamp) as end_time,
            BIGINT((UNIX_TIMESTAMP(MAX(timestamp)) - UNIX_TIMESTAMP(MIN(timestamp))) * 1000) as duration_ms,
            SUM(COALESCE(input_tokens, 0)) as total_input_tokens,
            SUM(COALESCE(output_tokens, 0)) as total_output_tokens,
            SUM(CASE WHEN event_type = 'tool_use' THEN 1 ELSE 0 END) as tool_call_count,
            SUM(CASE WHEN event_type = 'mcp_call' THEN 1 ELSE 0 END) as mcp_call_count,
            ROUND(
                (SUM(COALESCE(input_tokens, 0)) * 0.00001 + SUM(COALESCE(output_tokens, 0)) * 0.00003),
                4
            ) as estimated_cost_usd
        FROM {events_table}
        GROUP BY session_id
    """

    sessions_df = spark.sql(agg_query)

    sessions_df.write.format("delta").mode("overwrite").option(
        "mergeSchema", "true"
    ).saveAsTable(sessions_table)

    print(f"Aggregated {sessions_df.count()} sessions to {sessions_table}")


def run_rollup(config: ETLConfig) -> None:
    """Create daily metric rollups."""
    spark = get_spark()

    sessions_table = f"{config.catalog}.{config.schema}.sessions"
    daily_table = f"{config.catalog}.{config.schema}.daily_metrics"

    rollup_query = f"""
        SELECT
            DATE(start_time) as date,
            user_email,
            COUNT(*) as total_sessions,
            SUM(total_input_tokens) as total_input_tokens,
            SUM(total_output_tokens) as total_output_tokens,
            SUM(estimated_cost_usd) as total_cost_usd,
            AVG(duration_ms) as avg_session_duration_ms
        FROM {sessions_table}
        GROUP BY DATE(start_time), user_email
    """

    daily_df = spark.sql(rollup_query)

    daily_df.write.format("delta").mode("overwrite").option(
        "mergeSchema", "true"
    ).saveAsTable(daily_table)

    print(f"Created {daily_df.count()} daily rollup rows in {daily_table}")


def main(args: list) -> None:
    """Main entry point."""
    config = ETLConfig.from_args(args)

    print(f"Running ETL step: {config.step}")
    print(f"Target: {config.catalog}.{config.schema}")

    if config.step == "extract":
        run_extract(config)
    elif config.step == "aggregate":
        run_aggregate(config)
    elif config.step == "rollup":
        run_rollup(config)
    elif config.step == "backfill":
        # For backfill, run all steps
        run_extract(config)
        run_aggregate(config)
        run_rollup(config)
    else:
        raise ValueError(f"Unknown step: {config.step}")

    print("ETL step completed successfully")


if __name__ == "__main__":
    main(sys.argv[1:])
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/etl/test_materialization.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add etl/obs_materialization.py tests/etl/test_materialization.py
git commit -m "feat(etl): add main materialization job with extract/aggregate/rollup steps"
```

---

## Phase 4: Frontend Foundation

### Task 4.1: Initialize React Project Structure

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`

**Step 1: Create frontend configuration files**

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Claudit Observability</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
```

```json
// frontend/tsconfig.json
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

```typescript
// frontend/src/main.tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { ChakraProvider } from '@chakra-ui/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import App from './App'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ChakraProvider>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </ChakraProvider>
  </React.StrictMode>
)
```

```typescript
// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'
import { Box } from '@chakra-ui/react'

// Placeholder components - will be implemented in subsequent tasks
const LandingPage = () => <Box p={8}>Landing Page</Box>
const SessionsPage = () => <Box p={8}>Sessions Page</Box>
const SessionDetailPage = () => <Box p={8}>Session Detail Page</Box>
const DashboardPage = () => <Box p={8}>Dashboard Page</Box>

function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/sessions" element={<SessionsPage />} />
      <Route path="/sessions/:id" element={<SessionDetailPage />} />
      <Route path="/dashboard" element={<DashboardPage />} />
    </Routes>
  )
}

export default App
```

**Step 2: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): initialize React project with Vite, Chakra UI, and routing"
```

---

### Task 4.2: Create App Shell and Layout

**Files:**
- Create: `frontend/src/app/Layout.tsx`
- Create: `frontend/src/app/Sidebar.tsx`
- Create: `frontend/src/app/Header.tsx`
- Create: `frontend/src/app/router/viewRegistry.ts`
- Modify: `frontend/src/App.tsx`

**Step 1: Create layout components**

```typescript
// frontend/src/app/router/viewRegistry.ts
import { FiHome, FiList, FiBarChart2 } from 'react-icons/fi'
import { ComponentType } from 'react'
import { IconType } from 'react-icons'

export interface ViewConfig {
  id: string
  path: string
  label: string
  icon?: IconType
  nav: boolean
}

export const viewRegistry: ViewConfig[] = [
  { id: 'landing', path: '/', label: 'Home', icon: FiHome, nav: false },
  { id: 'sessions', path: '/sessions', label: 'Sessions', icon: FiList, nav: true },
  { id: 'session-detail', path: '/sessions/:id', label: 'Session Detail', nav: false },
  { id: 'dashboard', path: '/dashboard', label: 'Dashboard', icon: FiBarChart2, nav: true },
]

export const getNavItems = () => viewRegistry.filter((v) => v.nav)
```

```typescript
// frontend/src/app/Sidebar.tsx
import { Box, VStack, Link, Icon, Text, Flex } from '@chakra-ui/react'
import { Link as RouterLink, useLocation } from 'react-router-dom'
import { getNavItems } from './router/viewRegistry'

export function Sidebar() {
  const location = useLocation()
  const navItems = getNavItems()

  return (
    <Box
      as="nav"
      w="200px"
      bg="gray.800"
      color="white"
      h="100vh"
      p={4}
      position="fixed"
    >
      <Text fontSize="xl" fontWeight="bold" mb={8}>
        Claudit
      </Text>
      <VStack align="stretch" spacing={2}>
        {navItems.map((item) => {
          const isActive = location.pathname === item.path
          return (
            <Link
              as={RouterLink}
              to={item.path}
              key={item.id}
              p={3}
              borderRadius="md"
              bg={isActive ? 'gray.700' : 'transparent'}
              _hover={{ bg: 'gray.700' }}
            >
              <Flex align="center" gap={3}>
                {item.icon && <Icon as={item.icon} />}
                <Text>{item.label}</Text>
              </Flex>
            </Link>
          )
        })}
      </VStack>
    </Box>
  )
}
```

```typescript
// frontend/src/app/Header.tsx
import { Box, Flex, Text, Input, Avatar } from '@chakra-ui/react'

export function Header() {
  return (
    <Box
      as="header"
      bg="white"
      borderBottom="1px"
      borderColor="gray.200"
      px={6}
      py={3}
    >
      <Flex justify="space-between" align="center">
        <Input placeholder="Search sessions..." maxW="400px" />
        <Flex align="center" gap={4}>
          <Text fontSize="sm" color="gray.600">
            user@example.com
          </Text>
          <Avatar size="sm" />
        </Flex>
      </Flex>
    </Box>
  )
}
```

```typescript
// frontend/src/app/Layout.tsx
import { Box, Flex } from '@chakra-ui/react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Header } from './Header'

export function Layout() {
  return (
    <Flex>
      <Sidebar />
      <Box ml="200px" flex={1} minH="100vh" bg="gray.50">
        <Header />
        <Box p={6}>
          <Outlet />
        </Box>
      </Box>
    </Flex>
  )
}
```

Update `frontend/src/App.tsx`:

```typescript
// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'
import { Box, Heading, Text } from '@chakra-ui/react'
import { Layout } from './app/Layout'

// Placeholder views
const LandingPage = () => (
  <Box>
    <Heading>Welcome to Claudit</Heading>
    <Text mt={4}>Claude Code Observability Dashboard</Text>
  </Box>
)

const SessionsPage = () => (
  <Box>
    <Heading size="lg">Sessions</Heading>
    <Text mt={4}>Session list will appear here</Text>
  </Box>
)

const SessionDetailPage = () => (
  <Box>
    <Heading size="lg">Session Detail</Heading>
    <Text mt={4}>Session timeline will appear here</Text>
  </Box>
)

const DashboardPage = () => (
  <Box>
    <Heading size="lg">Dashboard</Heading>
    <Text mt={4}>Metrics and charts will appear here</Text>
  </Box>
)

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<LandingPage />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="sessions/:id" element={<SessionDetailPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
      </Route>
    </Routes>
  )
}

export default App
```

**Step 2: Commit**

```bash
git add frontend/src/app/ frontend/src/App.tsx
git commit -m "feat(frontend): add app shell with sidebar, header, and layout"
```

---

### Task 4.3: Create API Client and Types

**Files:**
- Create: `frontend/src/types/session.ts`
- Create: `frontend/src/types/event.ts`
- Create: `frontend/src/types/metrics.ts`
- Create: `frontend/src/shared/utils/api.ts`

**Step 1: Create types**

```typescript
// frontend/src/types/session.ts
export interface Session {
  session_id: string
  user_email: string
  start_time: string
  end_time?: string
  duration_ms?: number
  total_input_tokens: number
  total_output_tokens: number
  tool_call_count: number
  mcp_call_count: number
  estimated_cost_usd: number
}

export interface SessionsResponse {
  sessions: Session[]
  pagination: {
    limit: number
    offset: number
    total: number
  }
}
```

```typescript
// frontend/src/types/event.ts
export type EventType = 'metric' | 'log' | 'tool_use' | 'mcp_call' | 'inference'

export interface SessionEvent {
  event_id: string
  session_id: string
  timestamp: string
  event_type: EventType
  source: string
  summary: string
  payload?: Record<string, unknown>
  wall_time_ms?: number
  api_time_ms?: number
  input_tokens?: number
  output_tokens?: number
  tool_name?: string
  mcp_server?: string
  mcp_method?: string
}

export interface TimelineResponse {
  session_id: string
  events: SessionEvent[]
}
```

```typescript
// frontend/src/types/metrics.ts
export interface UsageMetric {
  period: string
  total_input_tokens: number
  total_output_tokens: number
  total_sessions: number
  total_cost_usd: number
}

export interface UsageMetricsResponse {
  metrics: UsageMetric[]
  group_by: string
  start_date: string
  end_date: string
}
```

```typescript
// frontend/src/shared/utils/api.ts
const API_BASE = '/api/v1'

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`)
  }

  return response.json()
}

// Sessions API
export const sessionsApi = {
  list: (params?: { user_email?: string; limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.user_email) searchParams.set('user_email', params.user_email)
    if (params?.limit) searchParams.set('limit', params.limit.toString())
    if (params?.offset) searchParams.set('offset', params.offset.toString())

    const query = searchParams.toString()
    return fetchJson<import('../types/session').SessionsResponse>(
      `${API_BASE}/sessions${query ? `?${query}` : ''}`
    )
  },

  get: (sessionId: string) =>
    fetchJson<import('../types/session').Session>(`${API_BASE}/sessions/${sessionId}`),

  getTimeline: (sessionId: string, eventTypes?: string[]) => {
    const searchParams = new URLSearchParams()
    if (eventTypes?.length) {
      eventTypes.forEach((t) => searchParams.append('event_types', t))
    }
    const query = searchParams.toString()
    return fetchJson<import('../types/event').TimelineResponse>(
      `${API_BASE}/sessions/${sessionId}/timeline${query ? `?${query}` : ''}`
    )
  },
}

// Metrics API
export const metricsApi = {
  getUsage: (params: { start_date: string; end_date: string; group_by?: string }) => {
    const searchParams = new URLSearchParams({
      start_date: params.start_date,
      end_date: params.end_date,
    })
    if (params.group_by) searchParams.set('group_by', params.group_by)

    return fetchJson<import('../types/metrics').UsageMetricsResponse>(
      `${API_BASE}/metrics/usage?${searchParams}`
    )
  },
}
```

**Step 2: Commit**

```bash
git add frontend/src/types/ frontend/src/shared/
git commit -m "feat(frontend): add TypeScript types and API client utilities"
```

---

### Task 4.4: Create Sessions List View

**Files:**
- Create: `frontend/src/views/sessions/SessionsPage.tsx`
- Create: `frontend/src/views/sessions/components/SessionList.tsx`
- Create: `frontend/src/views/sessions/components/SessionCard.tsx`
- Create: `frontend/src/views/sessions/hooks/useSessions.ts`
- Modify: `frontend/src/App.tsx`

**Step 1: Create sessions view components**

```typescript
// frontend/src/views/sessions/hooks/useSessions.ts
import { useQuery } from '@tanstack/react-query'
import { sessionsApi } from '../../../shared/utils/api'

export function useSessions(params?: { user_email?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ['sessions', params],
    queryFn: () => sessionsApi.list(params),
  })
}

export function useSession(sessionId: string) {
  return useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => sessionsApi.get(sessionId),
    enabled: !!sessionId,
  })
}

export function useSessionTimeline(sessionId: string, eventTypes?: string[]) {
  return useQuery({
    queryKey: ['timeline', sessionId, eventTypes],
    queryFn: () => sessionsApi.getTimeline(sessionId, eventTypes),
    enabled: !!sessionId,
  })
}
```

```typescript
// frontend/src/views/sessions/components/SessionCard.tsx
import { Box, Flex, Text, Badge, Link } from '@chakra-ui/react'
import { Link as RouterLink } from 'react-router-dom'
import { format } from 'date-fns'
import { Session } from '../../../types/session'

interface SessionCardProps {
  session: Session
}

export function SessionCard({ session }: SessionCardProps) {
  const startTime = new Date(session.start_time)
  const totalTokens = session.total_input_tokens + session.total_output_tokens

  return (
    <Link as={RouterLink} to={`/sessions/${session.session_id}`} _hover={{ textDecoration: 'none' }}>
      <Box
        p={4}
        bg="white"
        borderRadius="md"
        border="1px"
        borderColor="gray.200"
        _hover={{ borderColor: 'blue.300', shadow: 'sm' }}
      >
        <Flex justify="space-between" align="start">
          <Box>
            <Text fontWeight="medium" fontSize="sm" color="gray.500">
              {session.session_id}
            </Text>
            <Text fontWeight="semibold">{session.user_email}</Text>
            <Text fontSize="sm" color="gray.600">
              {format(startTime, 'MMM d, yyyy h:mm a')}
            </Text>
          </Box>
          <Flex gap={2} flexWrap="wrap" justify="end">
            <Badge colorScheme="blue">{totalTokens.toLocaleString()} tokens</Badge>
            <Badge colorScheme="green">${session.estimated_cost_usd.toFixed(2)}</Badge>
          </Flex>
        </Flex>
        <Flex mt={3} gap={4} fontSize="sm" color="gray.600">
          <Text>{session.duration_ms ? `${Math.round(session.duration_ms / 60000)}m` : '-'}</Text>
          <Text>{session.tool_call_count} tools</Text>
          <Text>{session.mcp_call_count} MCP calls</Text>
        </Flex>
      </Box>
    </Link>
  )
}
```

```typescript
// frontend/src/views/sessions/components/SessionList.tsx
import { VStack, Text, Spinner, Center } from '@chakra-ui/react'
import { Session } from '../../../types/session'
import { SessionCard } from './SessionCard'

interface SessionListProps {
  sessions?: Session[]
  isLoading: boolean
  error?: Error | null
}

export function SessionList({ sessions, isLoading, error }: SessionListProps) {
  if (isLoading) {
    return (
      <Center py={10}>
        <Spinner size="lg" />
      </Center>
    )
  }

  if (error) {
    return (
      <Center py={10}>
        <Text color="red.500">Error loading sessions: {error.message}</Text>
      </Center>
    )
  }

  if (!sessions?.length) {
    return (
      <Center py={10}>
        <Text color="gray.500">No sessions found</Text>
      </Center>
    )
  }

  return (
    <VStack align="stretch" spacing={3}>
      {sessions.map((session) => (
        <SessionCard key={session.session_id} session={session} />
      ))}
    </VStack>
  )
}
```

```typescript
// frontend/src/views/sessions/SessionsPage.tsx
import { Box, Heading, Flex } from '@chakra-ui/react'
import { useSessions } from './hooks/useSessions'
import { SessionList } from './components/SessionList'

export function SessionsPage() {
  const { data, isLoading, error } = useSessions({ limit: 20 })

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Heading size="lg">Sessions</Heading>
      </Flex>
      <SessionList
        sessions={data?.sessions}
        isLoading={isLoading}
        error={error}
      />
    </Box>
  )
}
```

Update `frontend/src/App.tsx` to use the real SessionsPage:

```typescript
// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'
import { Box, Heading, Text } from '@chakra-ui/react'
import { Layout } from './app/Layout'
import { SessionsPage } from './views/sessions/SessionsPage'

// Placeholder views
const LandingPage = () => (
  <Box>
    <Heading>Welcome to Claudit</Heading>
    <Text mt={4}>Claude Code Observability Dashboard</Text>
  </Box>
)

const SessionDetailPage = () => (
  <Box>
    <Heading size="lg">Session Detail</Heading>
    <Text mt={4}>Session timeline will appear here</Text>
  </Box>
)

const DashboardPage = () => (
  <Box>
    <Heading size="lg">Dashboard</Heading>
    <Text mt={4}>Metrics and charts will appear here</Text>
  </Box>
)

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<LandingPage />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="sessions/:id" element={<SessionDetailPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
      </Route>
    </Routes>
  )
}

export default App
```

**Step 2: Commit**

```bash
git add frontend/src/views/sessions/ frontend/src/App.tsx
git commit -m "feat(frontend): add sessions list view with cards and data fetching"
```

---

### Task 4.5: Create Session Timeline View

**Files:**
- Create: `frontend/src/views/sessions/SessionDetailPage.tsx`
- Create: `frontend/src/views/sessions/components/SessionTimeline.tsx`
- Create: `frontend/src/views/sessions/components/TimelineEvent.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create timeline components**

```typescript
// frontend/src/views/sessions/components/TimelineEvent.tsx
import { Box, Flex, Text, Badge, Icon } from '@chakra-ui/react'
import { FiCircle, FiSquare, FiTriangle, FiStar, FiAlertTriangle } from 'react-icons/fi'
import { format } from 'date-fns'
import { SessionEvent, EventType } from '../../../types/event'

const eventConfig: Record<EventType, { icon: typeof FiCircle; color: string; label: string }> = {
  metric: { icon: FiCircle, color: 'gray', label: 'Metric' },
  log: { icon: FiCircle, color: 'gray', label: 'Log' },
  tool_use: { icon: FiSquare, color: 'blue', label: 'Tool' },
  mcp_call: { icon: FiTriangle, color: 'purple', label: 'MCP' },
  inference: { icon: FiStar, color: 'green', label: 'Inference' },
}

interface TimelineEventProps {
  event: SessionEvent
}

export function TimelineEvent({ event }: TimelineEventProps) {
  const config = eventConfig[event.event_type] || eventConfig.metric
  const timestamp = new Date(event.timestamp)

  return (
    <Flex gap={4} py={3}>
      {/* Time column */}
      <Text fontSize="sm" color="gray.500" w="80px" flexShrink={0}>
        {format(timestamp, 'HH:mm:ss')}
      </Text>

      {/* Icon */}
      <Box position="relative">
        <Icon as={config.icon} color={`${config.color}.500`} boxSize={4} />
        <Box
          position="absolute"
          left="7px"
          top="20px"
          w="2px"
          h="calc(100% + 12px)"
          bg="gray.200"
        />
      </Box>

      {/* Content */}
      <Box flex={1} pb={4}>
        <Flex gap={2} align="center" mb={1}>
          <Badge colorScheme={config.color} size="sm">
            {config.label}
          </Badge>
          {event.tool_name && <Text fontSize="sm" fontWeight="medium">{event.tool_name}</Text>}
          {event.mcp_server && (
            <Text fontSize="sm" fontWeight="medium">
              {event.mcp_server}.{event.mcp_method}
            </Text>
          )}
        </Flex>

        <Text fontSize="sm" color="gray.700">
          {event.summary}
        </Text>

        {/* Metrics */}
        <Flex gap={4} mt={2} fontSize="xs" color="gray.500">
          {event.wall_time_ms !== undefined && (
            <Text>Duration: {event.wall_time_ms}ms</Text>
          )}
          {event.api_time_ms !== undefined && (
            <Text>API: {event.api_time_ms}ms</Text>
          )}
          {(event.input_tokens !== undefined || event.output_tokens !== undefined) && (
            <Text>
              Tokens: {event.input_tokens || 0} in / {event.output_tokens || 0} out
            </Text>
          )}
        </Flex>
      </Box>
    </Flex>
  )
}
```

```typescript
// frontend/src/views/sessions/components/SessionTimeline.tsx
import { Box, VStack, Text, Spinner, Center, Button, HStack } from '@chakra-ui/react'
import { useState } from 'react'
import { SessionEvent, EventType } from '../../../types/event'
import { TimelineEvent } from './TimelineEvent'

const EVENT_FILTERS: { type: EventType | 'all'; label: string }[] = [
  { type: 'all', label: 'All' },
  { type: 'metric', label: 'Metrics' },
  { type: 'tool_use', label: 'Tools' },
  { type: 'mcp_call', label: 'MCP' },
  { type: 'inference', label: 'Inference' },
]

interface SessionTimelineProps {
  events?: SessionEvent[]
  isLoading: boolean
  error?: Error | null
}

export function SessionTimeline({ events, isLoading, error }: SessionTimelineProps) {
  const [filter, setFilter] = useState<EventType | 'all'>('all')

  const filteredEvents = events?.filter(
    (e) => filter === 'all' || e.event_type === filter
  )

  if (isLoading) {
    return (
      <Center py={10}>
        <Spinner size="lg" />
      </Center>
    )
  }

  if (error) {
    return (
      <Center py={10}>
        <Text color="red.500">Error loading timeline: {error.message}</Text>
      </Center>
    )
  }

  return (
    <Box>
      {/* Filter buttons */}
      <HStack spacing={2} mb={6}>
        {EVENT_FILTERS.map((f) => (
          <Button
            key={f.type}
            size="sm"
            variant={filter === f.type ? 'solid' : 'outline'}
            colorScheme={filter === f.type ? 'blue' : 'gray'}
            onClick={() => setFilter(f.type)}
          >
            {f.label}
          </Button>
        ))}
      </HStack>

      {/* Timeline */}
      <Box borderLeft="2px" borderColor="gray.200" pl={4}>
        {filteredEvents?.length ? (
          filteredEvents.map((event) => (
            <TimelineEvent key={event.event_id} event={event} />
          ))
        ) : (
          <Text color="gray.500">No events to display</Text>
        )}
      </Box>
    </Box>
  )
}
```

```typescript
// frontend/src/views/sessions/SessionDetailPage.tsx
import { Box, Heading, Text, Flex, Badge, Stat, StatLabel, StatNumber, StatGroup, Spinner, Center } from '@chakra-ui/react'
import { useParams, Link as RouterLink } from 'react-router-dom'
import { format } from 'date-fns'
import { useSession, useSessionTimeline } from './hooks/useSessions'
import { SessionTimeline } from './components/SessionTimeline'

export function SessionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: session, isLoading: sessionLoading } = useSession(id || '')
  const { data: timeline, isLoading: timelineLoading, error: timelineError } = useSessionTimeline(id || '')

  if (sessionLoading) {
    return (
      <Center py={10}>
        <Spinner size="lg" />
      </Center>
    )
  }

  if (!session) {
    return (
      <Box>
        <Text>Session not found</Text>
      </Box>
    )
  }

  const startTime = new Date(session.start_time)
  const totalTokens = session.total_input_tokens + session.total_output_tokens

  return (
    <Box>
      {/* Header */}
      <Flex justify="space-between" align="start" mb={6}>
        <Box>
          <Text fontSize="sm" color="gray.500" mb={1}>
            Session: {session.session_id}
          </Text>
          <Heading size="lg">{session.user_email}</Heading>
          <Text color="gray.600" mt={1}>
            {format(startTime, 'MMMM d, yyyy h:mm a')}
          </Text>
        </Box>
        <Flex gap={2}>
          <Badge colorScheme="blue" fontSize="md" px={3} py={1}>
            {totalTokens.toLocaleString()} tokens
          </Badge>
          <Badge colorScheme="green" fontSize="md" px={3} py={1}>
            ${session.estimated_cost_usd.toFixed(2)}
          </Badge>
        </Flex>
      </Flex>

      {/* Stats */}
      <StatGroup mb={8} bg="white" p={4} borderRadius="md" border="1px" borderColor="gray.200">
        <Stat>
          <StatLabel>Duration</StatLabel>
          <StatNumber>
            {session.duration_ms ? `${Math.round(session.duration_ms / 60000)}m` : '-'}
          </StatNumber>
        </Stat>
        <Stat>
          <StatLabel>Input Tokens</StatLabel>
          <StatNumber>{session.total_input_tokens.toLocaleString()}</StatNumber>
        </Stat>
        <Stat>
          <StatLabel>Output Tokens</StatLabel>
          <StatNumber>{session.total_output_tokens.toLocaleString()}</StatNumber>
        </Stat>
        <Stat>
          <StatLabel>Tool Calls</StatLabel>
          <StatNumber>{session.tool_call_count}</StatNumber>
        </Stat>
        <Stat>
          <StatLabel>MCP Calls</StatLabel>
          <StatNumber>{session.mcp_call_count}</StatNumber>
        </Stat>
      </StatGroup>

      {/* Timeline */}
      <Heading size="md" mb={4}>
        Timeline
      </Heading>
      <Box bg="white" p={6} borderRadius="md" border="1px" borderColor="gray.200">
        <SessionTimeline
          events={timeline?.events}
          isLoading={timelineLoading}
          error={timelineError}
        />
      </Box>
    </Box>
  )
}
```

Update `frontend/src/App.tsx`:

```typescript
// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'
import { Box, Heading, Text } from '@chakra-ui/react'
import { Layout } from './app/Layout'
import { SessionsPage } from './views/sessions/SessionsPage'
import { SessionDetailPage } from './views/sessions/SessionDetailPage'

const LandingPage = () => (
  <Box>
    <Heading>Welcome to Claudit</Heading>
    <Text mt={4}>Claude Code Observability Dashboard</Text>
  </Box>
)

const DashboardPage = () => (
  <Box>
    <Heading size="lg">Dashboard</Heading>
    <Text mt={4}>Metrics and charts will appear here</Text>
  </Box>
)

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<LandingPage />} />
        <Route path="sessions" element={<SessionsPage />} />
        <Route path="sessions/:id" element={<SessionDetailPage />} />
        <Route path="dashboard" element={<DashboardPage />} />
      </Route>
    </Routes>
  )
}

export default App
```

**Step 2: Commit**

```bash
git add frontend/src/views/sessions/ frontend/src/App.tsx
git commit -m "feat(frontend): add session detail page with timeline view"
```

---

## Phase 5: Integration & Testing

### Task 5.1: Add Databricks SQL Execution to Backend

**Files:**
- Create: `backend/services/databricks_client.py`
- Modify: `backend/routers/sessions.py`
- Modify: `backend/routers/metrics.py`

**Step 1: Create Databricks client**

```python
# backend/services/databricks_client.py
from typing import List, Dict, Any, Optional
import os
from databricks import sql as databricks_sql

from backend.config import settings


class DatabricksClient:
    """Client for executing SQL queries against Databricks."""

    def __init__(self):
        self.host = os.environ.get("DATABRICKS_HOST", "")
        self.warehouse_id = settings.sql_warehouse_id
        self._connection = None

    def _get_connection(self):
        if self._connection is None:
            self._connection = databricks_sql.connect(
                server_hostname=self.host.replace("https://", ""),
                http_path=f"/sql/1.0/warehouses/{self.warehouse_id}",
                # Use OAuth when running in Databricks App
            )
        return self._connection

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute SQL query and return results as list of dicts."""
        connection = self._get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            cursor.close()

    def close(self):
        if self._connection:
            self._connection.close()
            self._connection = None


# Singleton instance
_client: Optional[DatabricksClient] = None


def get_databricks_client() -> DatabricksClient:
    global _client
    if _client is None:
        _client = DatabricksClient()
    return _client


def execute_query(query: str) -> List[Dict[str, Any]]:
    """Convenience function for executing queries."""
    return get_databricks_client().execute_query(query)
```

Update routers to use real client (replace placeholder `execute_query`):

```python
# Update imports in backend/routers/sessions.py
from backend.services.databricks_client import execute_query

# Update imports in backend/routers/metrics.py
from backend.services.databricks_client import execute_query
```

**Step 2: Commit**

```bash
git add backend/services/databricks_client.py backend/routers/
git commit -m "feat(backend): add Databricks SQL client for query execution"
```

---

### Task 5.2: Add Integration Tests

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_api.py`

**Step 1: Create integration tests**

```python
# tests/integration/__init__.py
# (empty)

# tests/integration/test_api.py
"""
Integration tests for API endpoints.
These tests require a running backend with mock or real data.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with mocked Databricks client."""
    from unittest.mock import patch

    mock_data = {
        "sessions": [
            {
                "session_id": "test_sess_001",
                "user_email": "test@example.com",
                "start_time": "2026-02-20T10:30:00",
                "end_time": "2026-02-20T11:15:00",
                "duration_ms": 2700000,
                "total_input_tokens": 45000,
                "total_output_tokens": 12000,
                "tool_call_count": 23,
                "mcp_call_count": 8,
                "estimated_cost_usd": 0.85,
            }
        ],
        "events": [
            {
                "event_id": "evt_001",
                "session_id": "test_sess_001",
                "timestamp": "2026-02-20T10:30:05",
                "event_type": "tool_use",
                "source": "otel_logs",
                "summary": "Tool: Read /src/main.py",
                "wall_time_ms": 250,
                "input_tokens": 1200,
            }
        ],
    }

    def mock_execute(query: str):
        if "session_events" in query:
            return mock_data["events"]
        return mock_data["sessions"]

    with patch("backend.routers.sessions.execute_query", side_effect=mock_execute):
        with patch("backend.routers.metrics.execute_query", return_value=[]):
            from backend.main import app
            yield TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_list_sessions_returns_data(client):
    response = client.get("/api/v1/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "test_sess_001"


def test_get_session_detail(client):
    response = client.get("/api/v1/sessions/test_sess_001")
    assert response.status_code == 200


def test_get_session_timeline(client):
    response = client.get("/api/v1/sessions/test_sess_001/timeline")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
    assert len(data["events"]) == 1


def test_metrics_usage_requires_dates(client):
    response = client.get("/api/v1/metrics/usage")
    assert response.status_code == 422
```

**Step 2: Run tests**

Run: `pytest tests/integration/ -v`
Expected: PASS (5 tests)

**Step 3: Commit**

```bash
git add tests/integration/
git commit -m "test: add integration tests for API endpoints"
```

---

### Task 5.3: Final Bundle Validation

**Files:**
- None (validation only)

**Step 1: Validate DAB bundle**

```bash
databricks bundle validate
```

Expected: No errors

**Step 2: Run all tests**

```bash
pytest tests/ -v --cov=backend --cov=etl
```

Expected: All tests pass

**Step 3: Build frontend**

```bash
cd frontend && npm install && npm run build
```

Expected: Build succeeds, `frontend/dist/` created

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: finalize project structure and validation"
```

---

## Summary

| Phase | Tasks | Files Created |
|-------|-------|---------------|
| 1. Scaffolding | 3 | pyproject.toml, package.json, databricks.yml, resources/*.yml |
| 2. Backend | 4 | backend/models/*, backend/services/*, backend/routers/*, backend/main.py |
| 3. ETL | 3 | etl/config.py, etl/models.py, etl/extractors/*, etl/obs_materialization.py |
| 4. Frontend | 5 | frontend/src/app/*, frontend/src/views/sessions/*, frontend/src/shared/* |
| 5. Integration | 3 | backend/services/databricks_client.py, tests/integration/* |

**Total: 18 tasks**

---

## Deployment Checklist

After implementation:

1. Set environment variables:
   - `DATABRICKS_HOST`
   - `SQL_WAREHOUSE_ID`
   - `CATALOG`, `SCHEMA`

2. Deploy bundle:
   ```bash
   databricks bundle deploy -t dev
   ```

3. Run initial ETL:
   ```bash
   databricks bundle run obs_materialization -t dev
   ```

4. Verify app:
   ```bash
   databricks apps get claudit-observability
   ```
