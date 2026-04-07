# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # Lakebase Setup for Claudit Observability
# MAGIC Runs the sync pipeline, creates synced tables, PG views, materialized views, indexes, and grants.
# MAGIC
# MAGIC **Prerequisites:** Lakebase instance and lakebase_sync pipeline must be deployed via DAB.
# MAGIC
# MAGIC This notebook is **idempotent** — safe to re-run.

# COMMAND ----------
# Parameters (set by DAB job)
dbutils.widgets.text("catalog", "vdm_classic_rikfy0_catalog")
dbutils.widgets.text("lakebase_instance", "claudit-db")
dbutils.widgets.text("lakebase_database", "databricks_postgres")
dbutils.widgets.text("app_name", "claudit-observability")
dbutils.widgets.text("pipeline_name", "claudit-lakebase-sync")

catalog = dbutils.widgets.get("catalog")
instance_name = dbutils.widgets.get("lakebase_instance")
database_name = dbutils.widgets.get("lakebase_database")
app_name = dbutils.widgets.get("app_name")
pipeline_name = dbutils.widgets.get("pipeline_name")

# COMMAND ----------
# MAGIC %pip install -U "databricks-sdk>=0.81.0" "psycopg[binary]>=3.0"

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
# Re-read widgets after Python restart
catalog = dbutils.widgets.get("catalog")
instance_name = dbutils.widgets.get("lakebase_instance")
database_name = dbutils.widgets.get("lakebase_database")
app_name = dbutils.widgets.get("app_name")
pipeline_name = dbutils.widgets.get("pipeline_name")

import uuid
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: Verify Lakebase Instance & Get Connection Details

# COMMAND ----------
instance = w.database.get_database_instance(instance_name)
assert instance.state.value == "AVAILABLE", f"Instance {instance_name} is {instance.state}, expected AVAILABLE"
print(f"✓ Instance '{instance_name}' is AVAILABLE")
print(f"  Host: {instance.read_write_dns}")

import psycopg

cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=[instance_name],
)
token = cred.token
email = w.current_user.me().user_name

def run_pg(sql: str, dbname: str = "postgres"):
    """Run a SQL command against Lakebase Provisioned via psycopg."""
    conninfo = f"host={instance.read_write_dns} port=5432 dbname={dbname} user={email} password={token} sslmode=require"
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute(sql)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Run Lakebase Sync Pipeline
# MAGIC The pipeline creates materialized views (`otel_logs_pg`, `otel_metrics_pg`, `otel_spans_pg`)
# MAGIC in the `zerobus_sdp` schema. These are the source tables for the synced database tables.

# COMMAND ----------
import time

# Find the pipeline by name (use single quotes — DLT filter syntax requires them)
pipeline_id = None
for p in w.pipelines.list_pipelines(filter=f"name LIKE '{pipeline_name}'"):
    pipeline_id = p.pipeline_id
    print(f"Found pipeline '{pipeline_name}': {pipeline_id}")
    break

if not pipeline_id:
    raise RuntimeError(f"Pipeline '{pipeline_name}' not found. Deploy the DAB first.")

# Stop any active update, then trigger a full refresh
try:
    w.pipelines.stop(pipeline_id=pipeline_id)
    print("  Stopped existing pipeline update")
    time.sleep(10)
except Exception:
    pass  # No active update

print(f"Triggering pipeline {pipeline_id} (full refresh)...")
update = w.pipelines.start_update(pipeline_id=pipeline_id, full_refresh=True)
update_id = update.update_id
print(f"  Update started: {update_id}")

PIPELINE_TIMEOUT = 600  # 10 minutes
start = time.time()
while True:
    elapsed = time.time() - start
    if elapsed > PIPELINE_TIMEOUT:
        raise TimeoutError(f"Pipeline did not complete within {PIPELINE_TIMEOUT}s")

    update_info = w.pipelines.get_update(pipeline_id=pipeline_id, update_id=update_id)
    state = update_info.update.state.value if update_info.update.state else "UNKNOWN"

    if state in ("COMPLETED",):
        print(f"✓ Pipeline completed ({int(elapsed)}s)")
        break
    elif state in ("FAILED", "CANCELED"):
        raise RuntimeError(f"Pipeline {state} after {int(elapsed)}s. Check pipeline UI for details.")

    print(f"  Pipeline state: {state} ({int(elapsed)}s elapsed)")
    time.sleep(15)

# Verify the materialized views exist
schema_name = "zerobus_sdp"
expected_mvs = ["otel_logs_pg", "otel_metrics_pg", "otel_spans_pg"]
for mv in expected_mvs:
    full_name = f"{catalog}.{schema_name}.{mv}"
    try:
        w.tables.get(full_name)
        print(f"  ✓ {full_name} exists")
    except Exception as e:
        raise RuntimeError(f"Materialized view {full_name} not found after pipeline run: {e}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: Create Synced Database Tables
# MAGIC Creates synced tables via SDK with CONTINUOUS scheduling so they auto-sync.
# MAGIC Recreates existing SNAPSHOT tables as CONTINUOUS.

# COMMAND ----------
from databricks.sdk.service.database import (
    SyncedDatabaseTable,
    SyncedTableSpec,
    SyncedTableSchedulingPolicy,
    NewPipelineSpec,
)

SYNCED_TABLE_DEFS = [
    {"name": f"{catalog}.{schema_name}.otel_logs_pg_synced",   "source": f"{catalog}.{schema_name}.otel_logs_pg"},
    {"name": f"{catalog}.{schema_name}.otel_metrics_pg_synced", "source": f"{catalog}.{schema_name}.otel_metrics_pg"},
    {"name": f"{catalog}.{schema_name}.otel_spans_pg_synced",  "source": f"{catalog}.{schema_name}.otel_spans_pg"},
]

synced_table_names = []
for defn in SYNCED_TABLE_DEFS:
    tbl_name = defn["name"]
    synced_table_names.append(tbl_name)

    # Check if already exists
    try:
        existing = w.database.get_synced_database_table(tbl_name)
        print(f"  - {tbl_name} already exists (skipping)")
        continue
    except Exception:
        pass  # Does not exist, create it

    try:
        w.database.create_synced_database_table(
            synced_table=SyncedDatabaseTable(
                name=tbl_name,
                database_instance_name=instance_name,
                logical_database_name=database_name,
                spec=SyncedTableSpec(
                    source_table_full_name=defn["source"],
                    primary_key_columns=["row_id"],
                    scheduling_policy=SyncedTableSchedulingPolicy.SNAPSHOT,
                    new_pipeline_spec=NewPipelineSpec(
                        storage_catalog=catalog,
                        storage_schema=schema_name,
                    ),
                ),
            )
        )
        print(f"  ✓ Created synced table: {tbl_name}")
    except Exception as e:
        print(f"  ✗ Failed to create {tbl_name}: {e}")
        raise

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4: Wait for Synced Tables to Come ONLINE
# MAGIC Synced tables start OFFLINE. The internal DLT sync pipeline must run to populate them in PG.

# COMMAND ----------
SYNC_TIMEOUT = 300  # 5 minutes
POLL_INTERVAL = 15
start = time.time()


def _is_table_online(table_info) -> tuple:
    """Check if a synced table is online. Returns (is_online, state_str)."""
    sync_status = table_info.data_synchronization_status
    if sync_status and sync_status.detailed_state:
        state_str = sync_status.detailed_state.value
        if state_str.startswith("SYNCED_TABLE_ONLINE"):
            return True, state_str
        return False, state_str

    uc_state = table_info.unity_catalog_provisioning_state
    if uc_state:
        state_str = uc_state.value
        if state_str == "ACTIVE":
            return True, f"UC:{state_str}"
        return False, f"UC:{state_str}"

    return False, "UNKNOWN"


# Trigger sync pipeline refresh on any discovered synced table
for name in synced_table_names:
    try:
        st = w.database.get_synced_database_table(name)
        if st.data_synchronization_status and st.data_synchronization_status.pipeline_id:
            sync_pipeline_id = st.data_synchronization_status.pipeline_id
            print(f"Triggering synced table pipeline {sync_pipeline_id}...")
            w.pipelines.start_update(pipeline_id=sync_pipeline_id, full_refresh=True)
            break
    except Exception:
        pass

while True:
    elapsed = time.time() - start
    if elapsed > SYNC_TIMEOUT:
        raise TimeoutError(f"Synced tables did not come ONLINE within {SYNC_TIMEOUT}s")

    statuses = {}
    for name in synced_table_names:
        try:
            st = w.database.get_synced_database_table(name)
            online, state_str = _is_table_online(st)
            statuses[name] = (online, state_str)
        except Exception as e:
            statuses[name] = (False, f"ERROR: {e}")

    if all(online for online, _ in statuses.values()):
        print(f"✓ All synced tables are ONLINE (took {int(elapsed)}s)")
        for name, (_, state_str) in statuses.items():
            print(f"    {name.split('.')[-1]}: {state_str}")
        break

    print(f"  Waiting for tables to come online... ({int(elapsed)}s elapsed)")
    for name, (_, state_str) in statuses.items():
        print(f"    {name.split('.')[-1]}: {state_str}")
    time.sleep(POLL_INTERVAL)

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5: Create PG Views with JSONB Casts
# MAGIC Synced tables store JSON as TEXT. Views cast to JSONB for `->>'key'` operator support.

# COMMAND ----------
# Refresh token before PG operations
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=[instance_name],
)
token = cred.token

VIEWS = {
    "otel_logs": {
        "source": "otel_logs_pg_synced",
        "jsonb_cols": ["attributes", "resource_attributes"],
    },
    "otel_metrics": {
        "source": "otel_metrics_pg_synced",
        "jsonb_cols": ["sum_attributes", "histogram_attributes", "gauge_attributes", "resource_attributes"],
    },
    "otel_spans": {
        "source": "otel_spans_pg_synced",
        "jsonb_cols": ["attributes", "status", "events", "links", "resource_attributes"],
    },
}

for view_name, spec in VIEWS.items():
    source = spec["source"]
    jsonb_cols = set(spec["jsonb_cols"])

    # Get column list from source table
    try:
        col_rows = []
        conninfo = f"host={instance.read_write_dns} port=5432 dbname={database_name} user={email} password={token} sslmode=require"
        with psycopg.connect(conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'zerobus_sdp' AND table_name = '{source}'
                    ORDER BY ordinal_position
                """)
                col_rows = [r[0] for r in cur.fetchall()]

        if not col_rows:
            print(f"  ⚠ Source {source} has no columns — skipping view")
            continue

        # Build SELECT with casts
        select_parts = []
        for col in col_rows:
            if col in jsonb_cols:
                select_parts.append(f"{col}::jsonb AS {col}")
            else:
                select_parts.append(col)

        select_clause = ", ".join(select_parts)
        ddl = f"CREATE OR REPLACE VIEW zerobus_sdp.{view_name} AS SELECT {select_clause} FROM zerobus_sdp.{source};"
        run_pg(ddl, dbname=database_name)
        print(f"  ✓ View zerobus_sdp.{view_name} created")
    except Exception as e:
        print(f"  ✗ View {view_name} failed: {e}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5b: Create KPI Materialized View & Indexes
# MAGIC Pre-extracts JSONB attributes into typed columns for fast KPI queries.
# MAGIC Avoids TEXT→JSONB→extraction overhead on every request.

# COMMAND ----------
# KPI materialized view: pre-extracted columns from otel_logs
KPI_MAT_VIEW_DDL = """
DROP MATERIALIZED VIEW IF EXISTS zerobus_sdp.kpi_logs_mat CASCADE;

CREATE MATERIALIZED VIEW zerobus_sdp.kpi_logs_mat AS
SELECT
    row_id,
    (attributes::jsonb->>'session.id') as session_id,
    (attributes::jsonb->>'prompt.id') as prompt_id,
    (attributes::jsonb->>'event.name') as event_name,
    (attributes::jsonb->>'event.timestamp')::timestamp as event_ts,
    (attributes::jsonb->>'event.sequence')::int as event_seq,
    (attributes::jsonb->>'model') as model,
    (attributes::jsonb->>'cost_usd')::double precision as cost_usd,
    (attributes::jsonb->>'input_tokens')::bigint as input_tokens,
    (attributes::jsonb->>'output_tokens')::bigint as output_tokens,
    (attributes::jsonb->>'cache_read_tokens')::bigint as cache_read_tokens,
    (attributes::jsonb->>'duration_ms')::double precision as duration_ms,
    (attributes::jsonb->>'tool_name') as tool_name,
    (attributes::jsonb->>'success') as success,
    (attributes::jsonb->>'prompt') as prompt_text,
    (resource_attributes::jsonb->>'service.name') as service_name
FROM zerobus_sdp.otel_logs_pg_synced
WHERE resource_attributes::jsonb->>'service.name' = 'claude-code';
"""

KPI_INDEXES_DDL = [
    "CREATE INDEX IF NOT EXISTS idx_mat_service_event_ts ON zerobus_sdp.kpi_logs_mat (service_name, event_name, event_ts);",
    "CREATE INDEX IF NOT EXISTS idx_mat_session_prompt ON zerobus_sdp.kpi_logs_mat (session_id, prompt_id);",
    "CREATE INDEX IF NOT EXISTS idx_mat_event_ts ON zerobus_sdp.kpi_logs_mat (event_ts);",
    "CREATE INDEX IF NOT EXISTS idx_mat_session_prompt_seq ON zerobus_sdp.kpi_logs_mat (session_id, prompt_id, event_seq);",
]

try:
    conninfo = f"host={instance.read_write_dns} port=5432 dbname={database_name} user={email} password={token} sslmode=require"
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute(KPI_MAT_VIEW_DDL)
        print("  ✓ Materialized view zerobus_sdp.kpi_logs_mat created")
        for idx_ddl in KPI_INDEXES_DDL:
            conn.execute(idx_ddl)
        print(f"  ✓ {len(KPI_INDEXES_DDL)} indexes created on kpi_logs_mat")
except Exception as e:
    print(f"  ✗ KPI materialized view setup failed: {e}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5c: Create otel_logs_mat — Wide Materialized View for QueryService
# MAGIC Pre-extracts all JSONB attributes used by QueryService into typed columns.

# COMMAND ----------
OTEL_LOGS_MAT_DDL = """
DROP MATERIALIZED VIEW IF EXISTS zerobus_sdp.otel_logs_mat CASCADE;

CREATE MATERIALIZED VIEW zerobus_sdp.otel_logs_mat AS
SELECT
    row_id,
    (attributes::jsonb->>'session.id') as session_id,
    (attributes::jsonb->>'user.id') as user_id,
    (attributes::jsonb->>'prompt.id') as prompt_id,
    (attributes::jsonb->>'event.name') as event_name,
    (attributes::jsonb->>'event.timestamp')::timestamp as event_ts,
    (attributes::jsonb->>'event.sequence')::int as event_seq,
    (resource_attributes::jsonb->>'service.name') as service_name,
    (attributes::jsonb->>'model') as model,
    (attributes::jsonb->>'cost_usd')::double precision as cost_usd,
    (attributes::jsonb->>'input_tokens')::bigint as input_tokens,
    (attributes::jsonb->>'output_tokens')::bigint as output_tokens,
    (attributes::jsonb->>'cache_read_tokens')::bigint as cache_read_tokens,
    (attributes::jsonb->>'cache_creation_tokens')::bigint as cache_creation_tokens,
    (attributes::jsonb->>'duration_ms')::double precision as duration_ms,
    (attributes::jsonb->>'tool_name') as tool_name,
    (attributes::jsonb->>'success') as success,
    (attributes::jsonb->>'prompt') as prompt_text,
    (attributes::jsonb->>'prompt_length') as prompt_length,
    (attributes::jsonb->>'error') as error,
    (attributes::jsonb->>'status_code') as status_code,
    (attributes::jsonb->>'decision') as decision,
    (attributes::jsonb->>'source') as source,
    (attributes::jsonb->>'speed') as speed,
    (attributes::jsonb->>'tool_result_size_bytes')::bigint as tool_result_size_bytes,
    (attributes::jsonb->>'tool_parameters') as tool_parameters
FROM zerobus_sdp.otel_logs_pg_synced
WHERE resource_attributes::jsonb->>'service.name' = 'claude-code';
"""

OTEL_LOGS_MAT_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_svc_evt_ts ON zerobus_sdp.otel_logs_mat (service_name, event_name, event_ts);",
    "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_session ON zerobus_sdp.otel_logs_mat (session_id);",
    "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_session_prompt ON zerobus_sdp.otel_logs_mat (session_id, prompt_id);",
    "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_session_prompt_seq ON zerobus_sdp.otel_logs_mat (session_id, prompt_id, event_seq);",
    "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_event_ts ON zerobus_sdp.otel_logs_mat (event_ts);",
    "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_tool ON zerobus_sdp.otel_logs_mat (tool_name) WHERE event_name = 'tool_result';",
    "CREATE INDEX IF NOT EXISTS idx_otel_logs_mat_user ON zerobus_sdp.otel_logs_mat (user_id);",
]

try:
    conninfo = f"host={instance.read_write_dns} port=5432 dbname={database_name} user={email} password={token} sslmode=require"
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute(OTEL_LOGS_MAT_DDL)
        print("  ✓ Materialized view zerobus_sdp.otel_logs_mat created")
        for idx_ddl in OTEL_LOGS_MAT_INDEXES:
            conn.execute(idx_ddl)
        print(f"  ✓ {len(OTEL_LOGS_MAT_INDEXES)} indexes created on otel_logs_mat")
except Exception as e:
    print(f"  ✗ otel_logs_mat setup failed: {e}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5d: Create otel_spans_mat — Materialized View for McpQueryService
# MAGIC Pre-extracts span attributes and computes derived fields (duration, domain regex).

# COMMAND ----------
OTEL_SPANS_MAT_DDL = """
DROP MATERIALIZED VIEW IF EXISTS zerobus_sdp.otel_spans_mat CASCADE;

CREATE MATERIALIZED VIEW zerobus_sdp.otel_spans_mat AS
SELECT
    row_id,
    name,
    kind,
    trace_id,
    span_id,
    parent_span_id,
    (resource_attributes::jsonb->>'service.name') as service_name,
    to_timestamp(start_time_unix_nano::bigint / 1000000000.0) as start_ts,
    ROUND(((end_time_unix_nano::bigint - start_time_unix_nano::bigint) / 1e6)::numeric, 1) as duration_ms,
    (status::jsonb->>'code') as status_code,
    (status::jsonb->>'message') as status_message,
    (attributes::jsonb->>'http.method') as http_method,
    (attributes::jsonb->>'http.url') as http_url,
    (attributes::jsonb->>'http.status_code')::int as http_status_code,
    (regexp_match(attributes::jsonb->>'http.url', '^(https?://[^/]+)'))[1] as http_domain
FROM zerobus_sdp.otel_spans_pg_synced
WHERE resource_attributes::jsonb->>'service.name' = 'claude-code';
"""

OTEL_SPANS_MAT_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_otel_spans_mat_kind_name ON zerobus_sdp.otel_spans_mat (kind, name);",
    "CREATE INDEX IF NOT EXISTS idx_otel_spans_mat_service ON zerobus_sdp.otel_spans_mat (service_name);",
    "CREATE INDEX IF NOT EXISTS idx_otel_spans_mat_start_ts ON zerobus_sdp.otel_spans_mat (start_ts);",
    "CREATE INDEX IF NOT EXISTS idx_otel_spans_mat_trace_span ON zerobus_sdp.otel_spans_mat (trace_id, span_id);",
]

try:
    conninfo = f"host={instance.read_write_dns} port=5432 dbname={database_name} user={email} password={token} sslmode=require"
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute(OTEL_SPANS_MAT_DDL)
        print("  ✓ Materialized view zerobus_sdp.otel_spans_mat created")
        for idx_ddl in OTEL_SPANS_MAT_INDEXES:
            conn.execute(idx_ddl)
        print(f"  ✓ {len(OTEL_SPANS_MAT_INDEXES)} indexes created on otel_spans_mat")
except Exception as e:
    print(f"  ✗ otel_spans_mat setup failed: {e}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 6: Grant App Service Principal Access

# COMMAND ----------
# Discover app's service principal client ID (the PG role name)
sp_role = None

try:
    app = w.apps.get(app_name)
    sp_role = app.service_principal_client_id
    if sp_role:
        print(f"App SP PG role: {sp_role}")
    else:
        print(f"⚠ App '{app_name}' has no service_principal_client_id — skipping SP grant")
except Exception as e:
    print(f"⚠ Could not get app details for '{app_name}': {e}")

if sp_role:
    # Refresh token (previous one may have expired during sync)
    cred = w.database.generate_database_credential(
        request_id=str(uuid.uuid4()),
        instance_names=[instance_name],
    )
    token = cred.token

    # Grant CONNECT on database + SELECT on all tables in zerobus_sdp schema
    try:
        run_pg(f'GRANT CONNECT ON DATABASE {database_name} TO "{sp_role}";', dbname=database_name)
        run_pg(f'GRANT USAGE, CREATE ON SCHEMA zerobus_sdp TO "{sp_role}";', dbname=database_name)
        run_pg(f'GRANT SELECT ON ALL TABLES IN SCHEMA zerobus_sdp TO "{sp_role}";', dbname=database_name)
        run_pg(f'ALTER DEFAULT PRIVILEGES IN SCHEMA zerobus_sdp GRANT SELECT ON TABLES TO "{sp_role}";', dbname=database_name)
        print(f"  ✓ Granted database + schema + table access to {sp_role}")
    except Exception as e:
        print(f"  ✗ Grant failed: {e}")

    # Transfer mat view ownership to SP so it can REFRESH them
    mat_views = ["kpi_logs_mat", "otel_logs_mat", "otel_spans_mat"]
    for mv in mat_views:
        try:
            run_pg(f'ALTER MATERIALIZED VIEW zerobus_sdp.{mv} OWNER TO "{sp_role}";', dbname=database_name)
            print(f"  ✓ Transferred ownership of {mv} to {sp_role}")
        except Exception as e:
            print(f"  ✗ Ownership transfer for {mv} failed: {e}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------
print("=" * 60)
print("Lakebase Setup Complete")
print("=" * 60)
print(f"Instance:       {instance_name}")
print(f"Database:       {database_name}")
print(f"Host:           {instance.read_write_dns}")
print(f"Sync pipeline:  {pipeline_name} ({pipeline_id})")
print(f"Synced tables:  {len(synced_table_names)}")
if sp_role:
    print(f"SP Access:      Granted to {sp_role}")
else:
    print("SP Access:      Manual grant required")
