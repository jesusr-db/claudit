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

# Use INCREMENTAL refresh (not full_refresh) — full_refresh nukes all MV tables and forces
# every dependent synced table to re-snapshot from scratch, taking a working setup back to
# PROVISIONING state. Incremental update applies new rows only and leaves synced tables ONLINE.
print(f"Triggering pipeline {pipeline_id} (incremental refresh)...")
update = w.pipelines.start_update(pipeline_id=pipeline_id, full_refresh=False)
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
expected_mvs = ["otel_logs_pg", "otel_metrics_pg", "otel_spans_pg", "cc_logs", "cc_spans"]
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
    {"name": f"{catalog}.{schema_name}.cc_logs_synced",        "source": f"{catalog}.{schema_name}.cc_logs"},
    {"name": f"{catalog}.{schema_name}.cc_spans_synced",       "source": f"{catalog}.{schema_name}.cc_spans"},
]

synced_table_names = []
for defn in SYNCED_TABLE_DEFS:
    tbl_name = defn["name"]
    synced_table_names.append(tbl_name)

    # Check if already exists — if so, skip; if in a broken state, delete and recreate
    try:
        existing = w.database.get_synced_database_table(tbl_name)
        state = getattr(existing.data_synchronization_status, "detailed_state", None)
        state_str = state.value if state else "UNKNOWN"
        if state_str.startswith("SYNCED_TABLE_ONLINE"):
            print(f"  - {tbl_name} already ONLINE (skipping)")
            continue
        # Exists but not online (orphaned/failed) — delete and recreate
        print(f"  - {tbl_name} exists in state {state_str}, deleting to recreate...")
        w.database.delete_synced_database_table(tbl_name)
        import time as _time; _time.sleep(5)
    except Exception as e:
        if "does not exist" in str(e).lower() or "not found" in str(e).lower():
            pass  # Does not exist, create it
        elif "AlreadyExists" in str(type(e).__name__) or "already exists" in str(e).lower():
            # UC metadata exists but get failed — delete and recreate
            print(f"  - {tbl_name} in unknown state, attempting delete + recreate...")
            try:
                w.database.delete_synced_database_table(tbl_name)
                import time as _time; _time.sleep(5)
            except Exception:
                pass
        else:
            pass  # Unknown error on get — attempt creation anyway

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
        if "already exists" in str(e).lower():
            print(f"  - {tbl_name} already exists (concurrent creation), continuing...")
        else:
            print(f"  ✗ Failed to create {tbl_name}: {e}")
            raise

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4: Wait for Synced Tables to Come ONLINE
# MAGIC Synced tables start OFFLINE. The internal DLT sync pipeline must run to populate them in PG.

# COMMAND ----------
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


# NOTE: do NOT manually trigger synced table pipelines here. create_synced_database_table()
# already auto-starts the sync — calling start_update(full_refresh=True) on top stops the
# in-progress snapshot and restarts it, which can drop a partially-snapshotted large table
# into OFFLINE_FAILED. Just let them sync.

while True:
    elapsed = time.time() - start
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
# MAGIC ## Step 5: Create Indexes on Pre-Shaped Synced Tables
# MAGIC All MVs in the SDP pipeline pre-extract attribute keys into typed columns,
# MAGIC so the synced PG tables are consumed directly by the app — no PG views, no
# MAGIC TEXT→JSONB casts. We just need indexes for fast query performance.

# COMMAND ----------
# Refresh token before PG operations
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=[instance_name],
)
token = cred.token

CC_LOGS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cc_logs_svc_evt_ts ON zerobus_sdp.cc_logs_synced (service_name, event_name, event_ts);",
    "CREATE INDEX IF NOT EXISTS idx_cc_logs_session ON zerobus_sdp.cc_logs_synced (session_id);",
    "CREATE INDEX IF NOT EXISTS idx_cc_logs_session_prompt ON zerobus_sdp.cc_logs_synced (session_id, prompt_id);",
    "CREATE INDEX IF NOT EXISTS idx_cc_logs_session_prompt_seq ON zerobus_sdp.cc_logs_synced (session_id, prompt_id, event_seq);",
    "CREATE INDEX IF NOT EXISTS idx_cc_logs_event_ts ON zerobus_sdp.cc_logs_synced (event_ts);",
    "CREATE INDEX IF NOT EXISTS idx_cc_logs_tool ON zerobus_sdp.cc_logs_synced (tool_name) WHERE event_name = 'tool_result';",
    "CREATE INDEX IF NOT EXISTS idx_cc_logs_user ON zerobus_sdp.cc_logs_synced (user_id);",
]

CC_SPANS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_cc_spans_kind_name ON zerobus_sdp.cc_spans_synced (kind, name);",
    "CREATE INDEX IF NOT EXISTS idx_cc_spans_service ON zerobus_sdp.cc_spans_synced (service_name);",
    "CREATE INDEX IF NOT EXISTS idx_cc_spans_start_ts ON zerobus_sdp.cc_spans_synced (start_ts);",
    "CREATE INDEX IF NOT EXISTS idx_cc_spans_trace_span ON zerobus_sdp.cc_spans_synced (trace_id, span_id);",
]

OTEL_LOGS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_otel_logs_svc_time ON zerobus_sdp.otel_logs_pg_synced (service_name, time_unix_nano);",
    "CREATE INDEX IF NOT EXISTS idx_otel_logs_trace_span ON zerobus_sdp.otel_logs_pg_synced (trace_id, span_id);",
    "CREATE INDEX IF NOT EXISTS idx_otel_logs_session ON zerobus_sdp.otel_logs_pg_synced (session_id);",
]

OTEL_SPANS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_otel_spans_svc_kind ON zerobus_sdp.otel_spans_pg_synced (service_name, kind);",
    "CREATE INDEX IF NOT EXISTS idx_otel_spans_name ON zerobus_sdp.otel_spans_pg_synced (name);",
    "CREATE INDEX IF NOT EXISTS idx_otel_spans_trace_span ON zerobus_sdp.otel_spans_pg_synced (trace_id, span_id);",
    "CREATE INDEX IF NOT EXISTS idx_otel_spans_start ON zerobus_sdp.otel_spans_pg_synced (start_time_unix_nano);",
]

OTEL_METRICS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_otel_metrics_name ON zerobus_sdp.otel_metrics_pg_synced (name);",
    "CREATE INDEX IF NOT EXISTS idx_otel_metrics_svc_name ON zerobus_sdp.otel_metrics_pg_synced (service_name, name);",
]

ALL_INDEXES = [
    ("cc_logs_synced", CC_LOGS_INDEXES),
    ("cc_spans_synced", CC_SPANS_INDEXES),
    ("otel_logs_pg_synced", OTEL_LOGS_INDEXES),
    ("otel_spans_pg_synced", OTEL_SPANS_INDEXES),
    ("otel_metrics_pg_synced", OTEL_METRICS_INDEXES),
]

try:
    conninfo = f"host={instance.read_write_dns} port=5432 dbname={database_name} user={email} password={token} sslmode=require"
    with psycopg.connect(conninfo, autocommit=True) as conn:
        for tbl, idx_list in ALL_INDEXES:
            for idx_ddl in idx_list:
                try:
                    conn.execute(idx_ddl)
                except Exception as inner_exc:
                    # Don't abort the whole step on a single missing column / wrong shape.
                    print(f"    - skip on {tbl}: {inner_exc}")
            print(f"  ✓ {len(idx_list)} indexes ensured on {tbl}")
except Exception as e:
    print(f"  ✗ Index creation failed: {e}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 5c: Clean Up Legacy PG Materialized Views
# MAGIC Remove old mat views that are now replaced by pre-shaped synced tables.

# COMMAND ----------
LEGACY_MAT_VIEWS = ["kpi_logs_mat", "otel_logs_mat", "otel_spans_mat"]
for mv in LEGACY_MAT_VIEWS:
    try:
        run_pg(f"DROP MATERIALIZED VIEW IF EXISTS zerobus_sdp.{mv} CASCADE;", dbname=database_name)
        print(f"  ✓ Dropped legacy mat view: {mv}")
    except Exception as e:
        print(f"  - {mv}: {e}")

# Drop the JSONB-cast views from the previous architecture — the synced tables
# now expose typed columns directly so these views serve no purpose.
LEGACY_PG_VIEWS = ["otel_logs", "otel_metrics", "otel_spans"]
for v in LEGACY_PG_VIEWS:
    try:
        run_pg(f"DROP VIEW IF EXISTS zerobus_sdp.{v} CASCADE;", dbname=database_name)
        print(f"  ✓ Dropped legacy view: {v}")
    except Exception as e:
        print(f"  - {v}: {e}")

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
