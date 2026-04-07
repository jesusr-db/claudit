# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # Refresh Synced Tables
# MAGIC Triggers the internal sync pipeline so SNAPSHOT-mode synced tables
# MAGIC pick up the latest data from the Delta materialized views.
# MAGIC
# MAGIC Runs as a downstream task in the scheduled sync job.

# COMMAND ----------
dbutils.widgets.text("catalog", "vdm_classic_rikfy0_catalog")

catalog = dbutils.widgets.get("catalog")

# COMMAND ----------
# MAGIC %pip install -U "databricks-sdk>=0.81.0"

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
catalog = dbutils.widgets.get("catalog")

from databricks.sdk import WorkspaceClient
import time

w = WorkspaceClient()

schema_name = "zerobus_sdp"
synced_table_names = [
    f"{catalog}.{schema_name}.otel_logs_pg_synced",
    f"{catalog}.{schema_name}.otel_metrics_pg_synced",
    f"{catalog}.{schema_name}.otel_spans_pg_synced",
]

# Discover the sync pipeline ID from any synced table
pipeline_id = None
for name in synced_table_names:
    try:
        st = w.database.get_synced_database_table(name)
        if st.data_synchronization_status and st.data_synchronization_status.pipeline_id:
            pipeline_id = st.data_synchronization_status.pipeline_id
            print(f"Discovered sync pipeline from {name}: {pipeline_id}")
            break
    except Exception as e:
        print(f"  Could not check {name}: {e}")

if not pipeline_id:
    print("No sync pipeline found — synced tables may not exist yet. Skipping.")
    dbutils.notebook.exit("skipped")

# Stop any active update first, then trigger a fresh one
try:
    w.pipelines.stop(pipeline_id=pipeline_id)
    print("Stopped existing pipeline update, waiting for it to settle...")
    time.sleep(15)
except Exception:
    pass

print(f"Triggering sync pipeline {pipeline_id} (full_refresh=True)...")
try:
    update_resp = w.pipelines.start_update(pipeline_id=pipeline_id, full_refresh=True)
    update_id = update_resp.update_id
    print(f"  Update started: {update_id}")
except Exception as e:
    print(f"  Trigger failed: {e}")
    dbutils.notebook.exit(f"trigger_failed: {e}")

# Wait for the pipeline update to complete
TIMEOUT = 300
start = time.time()
while True:
    elapsed = time.time() - start
    if elapsed > TIMEOUT:
        print(f"Timed out after {TIMEOUT}s")
        break

    try:
        update_info = w.pipelines.get_update(pipeline_id=pipeline_id, update_id=update_id)
        state = update_info.update.state.value if update_info.update.state else "UNKNOWN"

        if state in ("COMPLETED",):
            print(f"✓ Sync pipeline completed ({int(elapsed)}s)")
            break
        elif state in ("FAILED", "CANCELED"):
            print(f"✗ Sync pipeline {state} ({int(elapsed)}s)")
            break

        print(f"  Pipeline state: {state} ({int(elapsed)}s)")
    except Exception as e:
        print(f"  Poll error: {e}")

    time.sleep(15)

# Verify all synced tables are online
for name in synced_table_names:
    try:
        st = w.database.get_synced_database_table(name)
        sync_status = st.data_synchronization_status
        if sync_status and sync_status.detailed_state:
            print(f"  {name.split('.')[-1]}: {sync_status.detailed_state.value}")
        else:
            print(f"  {name.split('.')[-1]}: unknown state")
    except Exception as e:
        print(f"  {name.split('.')[-1]}: error - {e}")

dbutils.notebook.exit("refreshed")
