# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # Lakebase Sync Setup for Claudit Observability
# MAGIC Creates synced database tables from the SDP pipeline MVs to Lakebase Provisioned.
# MAGIC
# MAGIC **Prerequisites:** Run the `lakebase_sync` pipeline first to create the MVs.
# MAGIC
# MAGIC This notebook is **idempotent** — safe to re-run.

# COMMAND ----------
# Parameters (set by DAB job)
dbutils.widgets.text("catalog", "vdm_classic_rikfy0_catalog")
dbutils.widgets.text("lakebase_instance", "claudit-db")
dbutils.widgets.text("lakebase_database", "claudit")
dbutils.widgets.text("app_name", "claudit-observability")

catalog = dbutils.widgets.get("catalog")
instance_name = dbutils.widgets.get("lakebase_instance")
database_name = dbutils.widgets.get("lakebase_database")
app_name = dbutils.widgets.get("app_name")

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

import uuid
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import (
    SyncedDatabaseTable,
    SyncedTableSpec,
    SyncedTableSchedulingPolicy,
)

w = WorkspaceClient()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: Verify Lakebase Instance

# COMMAND ----------
instance = w.database.get_database_instance(instance_name)
assert instance.state.value == "AVAILABLE", f"Instance {instance_name} is {instance.state}, expected AVAILABLE"
print(f"✓ Instance '{instance_name}' is AVAILABLE")
print(f"  Host: {instance.read_write_dns}")
print(f"  PG Version: {instance.pg_version}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Create Database (if needed)

# COMMAND ----------
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

try:
    run_pg(f"CREATE DATABASE {database_name};")
    print(f"✓ Database '{database_name}' created")
except psycopg.errors.DuplicateDatabase:
    print(f"✓ Database '{database_name}' already exists")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: Create Synced Database Tables
# MAGIC Syncs the SDP pipeline MVs (with synthetic row_id PKs) to Lakebase Provisioned.

# COMMAND ----------
# MVs created by the lakebase_sync SDP pipeline, with synthetic row_id PK
TABLES = [
    {
        "source": f"{catalog}.zerobus_sdp.otel_logs_pg",
        "dest": f"{catalog}.zerobus_sdp.otel_logs_pg_synced",
        "pk": ["row_id"],
    },
    {
        "source": f"{catalog}.zerobus_sdp.otel_metrics_pg",
        "dest": f"{catalog}.zerobus_sdp.otel_metrics_pg_synced",
        "pk": ["row_id"],
    },
    {
        "source": f"{catalog}.zerobus_sdp.otel_spans_pg",
        "dest": f"{catalog}.zerobus_sdp.otel_spans_pg_synced",
        "pk": ["row_id"],
    },
]

pipeline_id = None
sync_results = []

for i, table in enumerate(TABLES, 1):
    source = table["source"]
    dest = table["dest"]
    pk_cols = table["pk"]

    print(f"\nSyncing table {i}/{len(TABLES)}: {source} -> {dest}")

    try:
        spec = SyncedTableSpec(
            source_table_full_name=source,
            scheduling_policy=SyncedTableSchedulingPolicy.SNAPSHOT,
            primary_key_columns=pk_cols,
        )
        if pipeline_id is not None:
            spec.existing_pipeline_id = pipeline_id

        synced = w.database.create_synced_database_table(
            SyncedDatabaseTable(
                name=dest,
                database_instance_name=instance_name,
                logical_database_name=database_name,
                spec=spec,
            )
        )

        status = synced.data_synchronization_status
        if pipeline_id is None and status and status.pipeline_id:
            pipeline_id = status.pipeline_id
            print(f"  Pipeline created: {pipeline_id}")

        sync_results.append({"table": source, "status": "success"})
        print(f"  ✓ Synced: {source}")

    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower():
            sync_results.append({"table": source, "status": "already_exists"})
            print(f"  ✓ Already synced: {source}")
        else:
            sync_results.append({"table": source, "status": "error", "error": error_msg})
            print(f"  ✗ Error syncing {source}: {error_msg}")

import json
print(f"\nSync summary: {json.dumps(sync_results, indent=2)}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3b: Wait for Synced Tables to Come ONLINE
# MAGIC Synced tables start OFFLINE. The internal DLT sync pipeline must run to populate them in PG.
# MAGIC We trigger the pipeline and poll until all tables reach an ONLINE state.

# COMMAND ----------
import time

synced_table_names = [t["dest"] for t in TABLES]

# Discover pipeline_id from any synced table if we didn't capture it during creation
if pipeline_id is None:
    for name in synced_table_names:
        try:
            st = w.database.get_synced_database_table(name)
            if st.data_synchronization_status and st.data_synchronization_status.pipeline_id:
                pipeline_id = st.data_synchronization_status.pipeline_id
                print(f"Discovered pipeline_id from existing table: {pipeline_id}")
                break
        except Exception:
            pass

if pipeline_id:
    # Trigger a full refresh so synced tables get populated in PG
    print(f"Triggering sync pipeline {pipeline_id}...")
    try:
        w.pipelines.start_update(pipeline_id=pipeline_id, full_refresh=True)
        print("  Pipeline update triggered")
    except Exception as e:
        # Pipeline may already be running
        print(f"  Pipeline trigger note: {e}")

# Poll until all synced tables are ONLINE (timeout: 20 minutes)
TIMEOUT_SECONDS = 120
POLL_INTERVAL = 15
start = time.time()


def _is_table_online(table_info) -> tuple:
    """Check if a synced table is online. Returns (is_online, state_str)."""
    # Check data_synchronization_status.detailed_state for SYNCED_TABLE_ONLINE*
    sync_status = table_info.data_synchronization_status
    if sync_status and sync_status.detailed_state:
        state_str = sync_status.detailed_state.value
        if state_str.startswith("SYNCED_TABLE_ONLINE"):
            return True, state_str
        return False, state_str

    # Fallback: check unity_catalog_provisioning_state
    uc_state = table_info.unity_catalog_provisioning_state
    if uc_state:
        state_str = uc_state.value
        if state_str == "ACTIVE":
            return True, f"UC:{state_str}"
        return False, f"UC:{state_str}"

    return False, "UNKNOWN"


while True:
    elapsed = time.time() - start
    if elapsed > TIMEOUT_SECONDS:
        raise TimeoutError(f"Synced tables did not come ONLINE within {TIMEOUT_SECONDS}s")

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
# MAGIC ## Step 4: Create PG Views with JSONB Casts
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
# MAGIC ## Step 4b: Create KPI Materialized View & Indexes
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
FROM zerobus_sdp.otel_logs_pg_synced;
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
# MAGIC ## Step 5: Grant App Service Principal Access

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
        run_pg(f'GRANT USAGE ON SCHEMA zerobus_sdp TO "{sp_role}";', dbname=database_name)
        run_pg(f'GRANT SELECT ON ALL TABLES IN SCHEMA zerobus_sdp TO "{sp_role}";', dbname=database_name)
        run_pg(f'ALTER DEFAULT PRIVILEGES IN SCHEMA zerobus_sdp GRANT SELECT ON TABLES TO "{sp_role}";', dbname=database_name)
        print(f"  ✓ Granted database + schema + table access to {sp_role}")
    except Exception as e:
        print(f"  ✗ Grant failed: {e}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------
print("=" * 60)
print("Lakebase Sync Setup Complete")
print("=" * 60)
print(f"Instance:   {instance_name}")
print(f"Database:   {database_name}")
print(f"Host:       {instance.read_write_dns}")
print(f"Pipeline:   {pipeline_id or 'N/A (tables already synced)'}")
print(f"Tables:     {len([r for r in sync_results if r['status'] in ('success', 'already_exists')])}/{len(TABLES)} synced")
if sp_role:
    print(f"SP Access:  Granted to {sp_role}")
else:
    print("SP Access:  Manual grant required")
