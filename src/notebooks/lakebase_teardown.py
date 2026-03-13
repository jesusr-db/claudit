# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # Lakebase Teardown
# MAGIC Removes artifacts created by `lakebase_setup` that are **not** managed by DAB:
# MAGIC - Synced database tables (+ their internal sync pipeline)
# MAGIC - PG views
# MAGIC - PG database
# MAGIC - Unused Autoscaling project `claudit-otel`
# MAGIC
# MAGIC **Does NOT delete** the Lakebase Provisioned instance (`claudit-db`).
# MAGIC
# MAGIC Safe to re-run (idempotent).

# COMMAND ----------
# Parameters — match lakebase_setup defaults
dbutils.widgets.text("catalog", "vdm_classic_rikfy0_catalog")
dbutils.widgets.text("lakebase_instance", "claudit-db")
dbutils.widgets.text("lakebase_database", "claudit")
dbutils.widgets.dropdown("delete_instance", "no", ["no", "yes"])

catalog = dbutils.widgets.get("catalog")
instance_name = dbutils.widgets.get("lakebase_instance")
database_name = dbutils.widgets.get("lakebase_database")
delete_instance = dbutils.widgets.get("delete_instance") == "yes"

# COMMAND ----------
# MAGIC %pip install -U "databricks-sdk>=0.81.0" "psycopg[binary]>=3.0"

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
catalog = dbutils.widgets.get("catalog")
instance_name = dbutils.widgets.get("lakebase_instance")
database_name = dbutils.widgets.get("lakebase_database")
delete_instance = dbutils.widgets.get("delete_instance") == "yes"

import uuid
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: Delete Synced Database Tables
# MAGIC This also removes them from PG and cleans up their internal sync pipeline
# MAGIC once the last table referencing it is deleted.

# COMMAND ----------
SYNCED_TABLES = [
    f"{catalog}.zerobus_sdp.otel_logs_pg_synced",
    f"{catalog}.zerobus_sdp.otel_metrics_pg_synced",
    f"{catalog}.zerobus_sdp.otel_spans_pg_synced",
]

for name in SYNCED_TABLES:
    try:
        w.database.delete_synced_database_table(name)
        print(f"  ✓ Deleted synced table: {name}")
    except Exception as e:
        if "not found" in str(e).lower() or "does not exist" in str(e).lower():
            print(f"  - Already gone: {name}")
        else:
            print(f"  ✗ Error deleting {name}: {e}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Drop PG Views and Database

# COMMAND ----------
import psycopg

instance = w.database.get_database_instance(instance_name)

cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=[instance_name],
)
token = cred.token
email = w.current_user.me().user_name

def run_pg(sql: str, dbname: str = "postgres"):
    conninfo = f"host={instance.read_write_dns} port=5432 dbname={dbname} user={email} password={token} sslmode=require"
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute(sql)

# Drop views first (they reference synced tables which may already be gone)
PG_VIEWS = ["otel_logs", "otel_metrics", "otel_spans"]

for view in PG_VIEWS:
    try:
        run_pg(f"DROP VIEW IF EXISTS zerobus_sdp.{view} CASCADE;", dbname=database_name)
        print(f"  ✓ Dropped view: zerobus_sdp.{view}")
    except Exception as e:
        print(f"  - View zerobus_sdp.{view}: {e}")

# Drop the database (must disconnect all sessions first)
try:
    run_pg(f"DROP DATABASE {database_name} WITH (FORCE);")
    print(f"  ✓ Dropped database: {database_name}")
except Exception as e:
    if "does not exist" in str(e).lower():
        print(f"  - Database '{database_name}' already gone")
    else:
        print(f"  ✗ Error dropping database: {e}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: Delete Unused Autoscaling Project

# COMMAND ----------
import subprocess

result = subprocess.run(
    ["databricks", "postgres", "delete-project", "projects/claudit-otel"],
    capture_output=True, text=True,
)
if result.returncode == 0:
    print("  ✓ Deleted unused project: claudit-otel")
elif "not found" in result.stderr.lower() or "not found" in result.stdout.lower():
    print("  - Project claudit-otel already gone")
else:
    print(f"  - Project delete note: {result.stderr or result.stdout}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4 (Optional): Delete Lakebase Instance

# COMMAND ----------
if delete_instance:
    try:
        w.database.delete_database_instance(instance_name)
        print(f"  ✓ Deleted Lakebase instance: {instance_name}")
    except Exception as e:
        print(f"  ✗ Error deleting instance: {e}")
else:
    print(f"  - Skipping instance deletion (set delete_instance=yes to remove '{instance_name}')")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------
print("=" * 60)
print("Lakebase Teardown Complete")
print("=" * 60)
print(f"Synced tables:  {len(SYNCED_TABLES)} removed")
print(f"PG views:       {len(PG_VIEWS)} dropped")
print(f"PG database:    {database_name} dropped")
print(f"Instance:       {'deleted' if delete_instance else 'kept'}")
