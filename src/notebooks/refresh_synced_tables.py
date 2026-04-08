# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # Refresh Synced Tables
# MAGIC Triggers ALL internal sync pipelines so SNAPSHOT-mode synced tables
# MAGIC pick up the latest data from the Delta materialized views.
# MAGIC
# MAGIC Discovers unique pipeline IDs across all synced tables and triggers each one.

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
    f"{catalog}.{schema_name}.cc_logs_synced",
    f"{catalog}.{schema_name}.cc_spans_synced",
]

# Discover ALL unique sync pipeline IDs across synced tables
pipeline_ids = set()
for name in synced_table_names:
    try:
        st = w.database.get_synced_database_table(name)
        if st.data_synchronization_status and st.data_synchronization_status.pipeline_id:
            pid = st.data_synchronization_status.pipeline_id
            pipeline_ids.add(pid)
            print(f"  {name.split('.')[-1]}: pipeline {pid}")
    except Exception as e:
        print(f"  {name.split('.')[-1]}: skip ({e})")

if not pipeline_ids:
    print("No sync pipelines found — synced tables may not exist yet. Skipping.")
    dbutils.notebook.exit("skipped")

print(f"\nFound {len(pipeline_ids)} unique sync pipeline(s)")

# Trigger each pipeline
update_tracking = {}
for pid in pipeline_ids:
    try:
        w.pipelines.stop(pipeline_id=pid)
        time.sleep(5)
    except Exception:
        pass

    try:
        resp = w.pipelines.start_update(pipeline_id=pid, full_refresh=True)
        update_tracking[pid] = resp.update_id
        print(f"  Triggered pipeline {pid}: update {resp.update_id}")
    except Exception as e:
        print(f"  Failed to trigger {pid}: {e}")

# Wait for all pipelines to complete
TIMEOUT = 300
start = time.time()
while update_tracking:
    elapsed = time.time() - start
    if elapsed > TIMEOUT:
        print(f"Timed out after {TIMEOUT}s — {len(update_tracking)} pipeline(s) still running")
        break

    done = []
    for pid, uid in update_tracking.items():
        try:
            info = w.pipelines.get_update(pipeline_id=pid, update_id=uid)
            state = info.update.state.value if info.update.state else "UNKNOWN"
            if state in ("COMPLETED", "FAILED", "CANCELED"):
                print(f"  Pipeline {pid}: {state} ({int(elapsed)}s)")
                done.append(pid)
        except Exception:
            pass

    for pid in done:
        del update_tracking[pid]

    if update_tracking:
        time.sleep(15)

# Final status
print("\nSynced table status:")
for name in synced_table_names:
    try:
        st = w.database.get_synced_database_table(name)
        sync_status = st.data_synchronization_status
        if sync_status and sync_status.detailed_state:
            print(f"  {name.split('.')[-1]}: {sync_status.detailed_state.value}")
        else:
            print(f"  {name.split('.')[-1]}: unknown")
    except Exception as e:
        print(f"  {name.split('.')[-1]}: error - {e}")

dbutils.notebook.exit("refreshed")
