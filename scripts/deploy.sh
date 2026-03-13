#!/usr/bin/env bash
# Deploy Claudit with Lakebase — handles bootstrap ordering:
#   1. Deploy DAB (creates instance, but app fails due to missing PG database — that's OK)
#   2. Wait for instance to be AVAILABLE
#   3. Create PG database on the new instance
#   4. Deploy DAB again (app resource now succeeds)
#   5. Run setup job (synced tables, views, SP grants)
set -euo pipefail

TARGET="${1:-dev}"
INSTANCE="${LAKEBASE_INSTANCE:-claudit-db}"
DATABASE="${LAKEBASE_DATABASE:-claudit}"

echo "=== Step 1: Deploy bundle (instance + pipelines + jobs) ==="
# First deploy may fail if app resource can't find the PG database yet — that's expected
databricks bundle deploy -t "$TARGET" 2>&1 && FIRST_DEPLOY=ok || FIRST_DEPLOY=partial
echo "  First deploy: ${FIRST_DEPLOY}"

echo ""
echo "=== Step 2: Wait for instance '${INSTANCE}' to be AVAILABLE ==="
python3 - "$INSTANCE" <<'PYEOF'
import sys, time
from databricks.sdk import WorkspaceClient

instance_name = sys.argv[1]
w = WorkspaceClient()

timeout = 600
start = time.time()
while True:
    elapsed = time.time() - start
    if elapsed > timeout:
        raise TimeoutError(f"Instance {instance_name} not AVAILABLE after {timeout}s")
    try:
        inst = w.database.get_database_instance(instance_name)
        state = inst.state.value
        print(f"  Instance state: {state} ({int(elapsed)}s)")
        if state == "AVAILABLE":
            break
    except Exception as e:
        print(f"  Waiting for instance... ({int(elapsed)}s) {e}")
    time.sleep(15)
PYEOF

echo ""
echo "=== Step 3: Ensure PG database '${DATABASE}' exists ==="
python3 - "$INSTANCE" "$DATABASE" <<'PYEOF'
import sys, uuid
from databricks.sdk import WorkspaceClient
import psycopg

instance_name, database_name = sys.argv[1], sys.argv[2]
w = WorkspaceClient()

instance = w.database.get_database_instance(instance_name)
cred = w.database.generate_database_credential(
    request_id=str(uuid.uuid4()),
    instance_names=[instance_name],
)
email = w.current_user.me().user_name
conninfo = f"host={instance.read_write_dns} port=5432 dbname=postgres user={email} password={cred.token} sslmode=require"

with psycopg.connect(conninfo, autocommit=True) as conn:
    try:
        conn.execute(f"CREATE DATABASE {database_name};")
        print(f"  Created database '{database_name}'")
    except psycopg.errors.DuplicateDatabase:
        print(f"  Database '{database_name}' already exists")
PYEOF

if [ "$FIRST_DEPLOY" = "partial" ]; then
    echo ""
    echo "=== Step 4: Re-deploy bundle (app resource can now find database) ==="
    databricks bundle deploy -t "$TARGET"
fi

echo ""
echo "=== Step 5: Run lakebase_setup job ==="
databricks bundle run lakebase_setup -t "$TARGET"

echo ""
echo "=== Deploy complete ==="
