# Databricks notebook source

# COMMAND ----------
# MAGIC %md
# MAGIC # Lakebase Setup for Claudit Observability
# MAGIC Provisions Lakebase Autoscaling project, syncs OTEL tables, grants app SP access.
# MAGIC This notebook is **idempotent** — safe to re-run.

# COMMAND ----------
# Parameters (set by DAB job)
dbutils.widgets.text("catalog", "jmr_demo")
dbutils.widgets.text("lakebase_project", "claudit-otel")
dbutils.widgets.text("lakebase_branch", "production")
dbutils.widgets.text("lakebase_endpoint", "primary")
dbutils.widgets.text("lakebase_database", "claudit")

catalog = dbutils.widgets.get("catalog")
project_id = dbutils.widgets.get("lakebase_project")
branch_id = dbutils.widgets.get("lakebase_branch")
endpoint_id = dbutils.widgets.get("lakebase_endpoint")
database_name = dbutils.widgets.get("lakebase_database")

# COMMAND ----------
import subprocess
import json
import time

def run_cli(args: list[str]) -> dict:
    """Run a databricks CLI command and return parsed JSON output."""
    result = subprocess.run(
        ["databricks"] + args + ["--output", "json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"CLI failed: {result.stderr}")
    return json.loads(result.stdout) if result.stdout.strip() else {}

def run_cli_allow_fail(args: list[str]) -> tuple[bool, dict]:
    """Run CLI command, return (success, result) without raising."""
    try:
        result = run_cli(args)
        return True, result
    except Exception as e:
        return False, {"error": str(e)}

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 1: Create Lakebase Project

# COMMAND ----------
# Check if project exists
success, project = run_cli_allow_fail(["postgres", "get-project", f"projects/{project_id}"])

if success:
    print(f"✓ Project '{project_id}' already exists")
else:
    print(f"Creating project '{project_id}'...")
    run_cli([
        "postgres", "create-project", project_id,
        "--json", json.dumps({"spec": {"display_name": "Claudit OTEL Data"}}),
        "--no-wait"
    ])
    print(f"✓ Project '{project_id}' created")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 2: Wait for Branch + Endpoint

# COMMAND ----------
def wait_for_active(resource_type: str, check_fn, timeout: int = 300):
    """Poll until resource reaches ACTIVE/READY state."""
    start = time.time()
    while time.time() - start < timeout:
        state = check_fn()
        print(f"  {resource_type} state: {state}")
        if state in ("ACTIVE", "READY"):
            return True
        time.sleep(10)
    raise TimeoutError(f"{resource_type} did not become ACTIVE within {timeout}s")

def get_branch_state():
    branches = run_cli(["postgres", "list-branches", f"projects/{project_id}"])
    for b in branches:
        if b.get("branch_id") == branch_id or b.get("name", "").endswith(f"/branches/{branch_id}"):
            return b.get("status", {}).get("current_state", "UNKNOWN")
    return "NOT_FOUND"

def get_endpoint_state():
    endpoints = run_cli(["postgres", "list-endpoints", f"projects/{project_id}/branches/{branch_id}"])
    for e in endpoints:
        if e.get("endpoint_id") == endpoint_id or e.get("name", "").endswith(f"/endpoints/{endpoint_id}"):
            return e.get("status", {}).get("current_state", "UNKNOWN")
    return "NOT_FOUND"

print("Waiting for branch...")
wait_for_active("Branch", get_branch_state)
print(f"✓ Branch '{branch_id}' is READY")

print("Waiting for endpoint...")
wait_for_active("Endpoint", get_endpoint_state)
print(f"✓ Endpoint '{endpoint_id}' is ACTIVE")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 3: Create Database

# COMMAND ----------
# Get endpoint host for psql commands
endpoints = run_cli(["postgres", "list-endpoints", f"projects/{project_id}/branches/{branch_id}"])
endpoint_host = endpoints[0]["status"]["hosts"]["host"]

# Generate token
cred = run_cli(["postgres", "generate-database-credential",
    f"projects/{project_id}/branches/{branch_id}/endpoints/{endpoint_id}"])
token = cred["token"]

# Get current user email
me = run_cli(["current-user", "me"])
email = me["userName"]

def run_psql(sql: str, dbname: str = "postgres"):
    """Run a SQL command against Lakebase via psql."""
    import os
    env = os.environ.copy()
    env["PGPASSWORD"] = token
    connstr = f"host={endpoint_host} port=5432 dbname={dbname} user={email} sslmode=require"
    result = subprocess.run(
        ["psql", connstr, "-c", sql],
        capture_output=True, text=True, env=env
    )
    if result.returncode != 0 and "already exists" not in result.stderr:
        raise RuntimeError(f"psql failed: {result.stderr}")
    return result.stdout

# Create database (idempotent)
try:
    run_psql(f"CREATE DATABASE {database_name};")
    print(f"✓ Database '{database_name}' created")
except RuntimeError as e:
    if "already exists" in str(e):
        print(f"✓ Database '{database_name}' already exists")
    else:
        raise

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 4-5: Sync Delta Tables

# COMMAND ----------
# Table sync configuration
TABLES = [
    {"source": f"{catalog}.zerobus.otel_logs", "pg_table": "zerobus_otel_logs", "order": 1},
    {"source": f"{catalog}.zerobus.otel_metrics", "pg_table": "zerobus_otel_metrics", "order": 2},
    {"source": f"{catalog}.default.otel_spans", "pg_table": "mcp_otel_spans", "order": 3},
    {"source": f"{catalog}.default.otel_logs", "pg_table": "mcp_otel_logs", "order": 4},
    {"source": f"{catalog}.default.otel_metrics", "pg_table": "mcp_otel_metrics", "order": 5},
]

pipeline_id = None
sync_results = []

for table in TABLES:
    source = table["source"]
    pg_table = table["pg_table"]
    order = table["order"]

    print(f"\nSyncing table {order}/5: {source} -> {pg_table}")

    try:
        cli_args = [
            "database", "create-synced-database-table", source,
            "--database-instance-name", f"projects/{project_id}",
            "--logical-database-name", database_name,
            "--table-name", pg_table,
            "--scheduling-policy", "SNAPSHOT",
        ]

        if pipeline_id is not None:
            cli_args.extend(["--existing-pipeline-id", pipeline_id])

        result = run_cli(cli_args)

        # Capture pipeline ID from first table creation
        if pipeline_id is None and "pipeline_id" in result:
            pipeline_id = result["pipeline_id"]
            print(f"  Pipeline created: {pipeline_id}")

        sync_results.append({"table": pg_table, "status": "success"})
        print(f"  ✓ Synced: {source} -> {pg_table}")

    except Exception as e:
        error_msg = str(e)
        if "already exists" in error_msg.lower():
            sync_results.append({"table": pg_table, "status": "already_exists"})
            print(f"  ✓ Already synced: {pg_table}")
        else:
            sync_results.append({"table": pg_table, "status": "error", "error": error_msg})
            print(f"  ✗ Error syncing {pg_table}: {error_msg}")

print(f"\nSync summary: {json.dumps(sync_results, indent=2)}")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Step 6-7: Grant SP Access

# COMMAND ----------
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Discover app's service principal
app = w.apps.get("claudit-observability")
sp_id = None
if hasattr(app, 'service_principal') and app.service_principal:
    sp_id = app.service_principal.id
elif hasattr(app, 'effective_service_principal_id'):
    sp_id = app.effective_service_principal_id

if sp_id:
    # Get SP details to find its username
    sp = w.service_principals.get(sp_id)
    sp_name = sp.application_id  # Use application_id as PG role name

    print(f"App SP: {sp_name} (ID: {sp_id})")

    # Refresh token for psql (previous token may have expired)
    cred = run_cli(["postgres", "generate-database-credential",
        f"projects/{project_id}/branches/{branch_id}/endpoints/{endpoint_id}"])
    token = cred["token"]

    # Grant SELECT on all synced tables
    for table in TABLES:
        pg_table = table["pg_table"]
        try:
            run_psql(f"GRANT SELECT ON {pg_table} TO \"{sp_name}\";", dbname=database_name)
            print(f"  ✓ Granted SELECT on {pg_table} to {sp_name}")
        except Exception as e:
            print(f"  ✗ Grant failed for {pg_table}: {e}")
else:
    print("⚠ Could not discover app service principal. Manual grant required.")

# COMMAND ----------
# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------
print("=" * 60)
print("Lakebase Setup Complete")
print("=" * 60)
print(f"Project:    {project_id}")
print(f"Branch:     {branch_id}")
print(f"Endpoint:   {endpoint_id}")
print(f"Database:   {database_name}")
print(f"Pipeline:   {pipeline_id or 'N/A (tables already synced)'}")
print(f"Tables:     {len([r for r in sync_results if r['status'] in ('success', 'already_exists')])}/{len(TABLES)} synced")
if sp_id:
    print(f"SP Access:  Granted to {sp_name}")
else:
    print("SP Access:  Manual grant required")
