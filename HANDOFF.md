# Claudit — Operations Handoff

> **Status:** Live in dev. App `claudit-observability` is RUNNING; all 5 Lakebase synced tables ONLINE; pipeline is on the 15-min schedule.
>
> **App:** https://claudit-observability-1351565862180944.aws.databricksapps.com

This document is the operational reference: how the system is wired, how to deploy, and how to recover from the failure modes we've actually hit.

---

## What's deployed

All resources are managed by the DAB at `databricks.yml`:

| Resource | Name / ID | What it does |
|---|---|---|
| Database instance | `claudit-db` (CU_1) | Lakebase Postgres holding the synced OTEL tables |
| DLT pipeline | `[dev jesus_rodriguez] claudit-lakebase-sync` | Runs the 5 Delta MVs in `src/pipelines/lakebase_sync/` |
| Job | `claudit-lakebase-setup` | One-shot bootstrap: refresh pipeline, create synced tables, build indexes, drop legacy views, grant SP access |
| Job | `claudit-lakebase-sync-scheduled` | Runs every 15 min: triggers the pipeline + a synced-table refresh |
| Job | `claudit-lakebase-teardown` | Cleans up the instance + synced tables |
| App | `claudit-observability` | FastAPI + React, two resources attached: `sql_warehouse` (CAN_USE) + `lakebase` (CAN_CONNECT_AND_CREATE) |
| Dashboard | `[dev jesus_rodriguez] Claude Code Monitoring` | AI/BI dashboard |

Resource IDs (dev target) drift on every redeploy; pull current values with:

```bash
databricks bundle summary -t dev
```

---

## Data flow

```
UC source tables                  →  SDP pipeline (5 Delta MVs)        →  Lakebase synced tables
${catalog}.zerobus.otel_logs         cc_logs           (claude-code only,     zerobus_sdp.cc_logs_synced
${catalog}.zerobus.otel_metrics       typed columns)                          zerobus_sdp.cc_spans_synced
${catalog}.zerobus.otel_spans        cc_spans          (claude-code only)    zerobus_sdp.otel_logs_pg_synced
                                     otel_logs_pg     (all services,         zerobus_sdp.otel_metrics_pg_synced
                                       typed columns)                         zerobus_sdp.otel_spans_pg_synced
                                     otel_spans_pg    (all services)
                                     otel_metrics_pg  (filtered to 5 metric
                                       names: claude_code.token.usage,
                                       claude_code.cost.usage,
                                       mcp.tool.calls, mcp.tool.latency,
                                       http.client.duration)
```

The synced PG tables expose typed columns directly — **no PG views, no JSONB casts**. See `CLAUDE.md` → "Data Architecture Rules" for the rule and rationale.

---

## Deploy from clean

```bash
# 1. Bundle deploy (idempotent — instance + pipeline + jobs + app)
databricks bundle deploy -t dev

# 2. Run the setup job (creates synced tables, indexes, grants)
databricks jobs run-now <setup_job_id>      # find it with `bundle summary`

# 3. Deploy app source code
databricks apps deploy claudit-observability \
  --source-code-path "/Workspace/Users/<you>/.bundle/claudit-observability/dev/files"
```

A successful end state:
- `databricks database get-database-instance claudit-db` → `AVAILABLE`
- All 5 entries in `zerobus_sdp.*` show `SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE`
- `databricks apps get claudit-observability` → `app_status=RUNNING`, `compute_status=ACTIVE`

---

## Failure modes we've hit (and the fix)

### 1. App deploy fails: `Role <uuid> not found in instance claudit-db`
The very first deploy of an app with a `lakebase` resource on a brand-new instance fails because the PG role for the app's SP is provisioned async by the grant attempt.

**Fix:** two-stage deploy.
```bash
# Edit resources/apps.yml, comment out the `- name: lakebase` resource block
databricks bundle deploy -t dev          # succeeds, app comes up without Lakebase
# Restore the lakebase block
databricks bundle deploy -t dev          # succeeds — PG role now exists
```

### 2. Setup job hangs forever waiting for synced tables to come ONLINE
Symptom: `Waiting for tables to come online... (3000s+ elapsed)` with one or more tables stuck in `PROVISIONING_INITIAL_SNAPSHOT` or `OFFLINE_FAILED`. Two root causes seen:

- **Duplicate or NULL `row_id`** in a source MV → the synced-table internal pipeline fails with `PRIMARY_KEY_CONSTRAINT_VIOLATION`. Source MVs now use `coalesce()` on every `md5(concat(...))` input plus a `ROW_NUMBER` dedup guard. Verify: `SELECT COUNT(*) total, COUNT(DISTINCT row_id) distinct, COUNT(*) FILTER (WHERE row_id IS NULL) nulls FROM zerobus_sdp.<mv>;` should have `total = distinct` and `nulls = 0`.
- **Setup notebook re-triggering an in-progress snapshot** → the previous version of the notebook called `start_update(full_refresh=True)` on the first synced table's pipeline, which stopped the in-progress initial snapshot of large tables and dropped them into `OFFLINE_FAILED`. Removed.

### 3. `Destination table <name> already exists in schema zerobus_sdp` when creating a synced table
When a synced table is deleted at the UC level, the underlying PG table is **not** removed and blocks recreation.

**Fix:**
```bash
databricks database delete-synced-database-table vdm_classic_rikfy0_catalog.zerobus_sdp.<name>
psql ... -c 'DROP TABLE IF EXISTS zerobus_sdp.<name> CASCADE;'
# then re-run the setup job (or `create-synced-database-table` directly)
```

### 4. App returns `permission denied for schema zerobus_sdp` after redeploy
The setup job is the thing that grants `USAGE`, `SELECT`, and default privileges to the app SP. If setup is still in flight (waiting on snapshots) the grants haven't run yet.

**Fix:** if you need to unblock the app early without waiting, grant manually:
```bash
SP=$(databricks apps get claudit-observability --output json | jq -r .service_principal_client_id)
psql ... <<EOF
GRANT CONNECT ON DATABASE databricks_postgres TO "$SP";
GRANT USAGE ON SCHEMA zerobus_sdp TO "$SP";
GRANT SELECT ON ALL TABLES IN SCHEMA zerobus_sdp TO "$SP";
ALTER DEFAULT PRIVILEGES IN SCHEMA zerobus_sdp GRANT SELECT ON TABLES TO "$SP";
EOF
```

### 5. `function round(double precision, integer) does not exist` in a PG query
Postgres only has `ROUND(numeric, int)`. Float divisions need `::numeric` before `ROUND`. Wrong: `ROUND(COUNT(*)::float / NULLIF(...), 2)`. Right: `ROUND((COUNT(*)::float / NULLIF(...))::numeric, 2)`.

---

## Connecting to Lakebase by hand

```bash
INSTANCE=claudit-db
HOST=$(databricks database get-database-instance $INSTANCE --output json | jq -r .read_write_dns)
TOKEN=$(databricks database generate-database-credential \
  --json "{\"request_id\":\"$(uuidgen)\",\"instance_names\":[\"$INSTANCE\"]}" \
  --output json | jq -r .token)
EMAIL=$(databricks current-user me --output json | jq -r .userName)

PGPASSWORD="$TOKEN" psql "host=$HOST port=5432 dbname=databricks_postgres user=$EMAIL sslmode=require"
```

---

## Reference docs (historical)

- `research/developer-efficiency-beyond-dora_2026-04-24.md` — SPACE+DevEx framework rationale for the Efficiency panel
- `docs/superpowers/specs/2026-03-10-lakebase-migration-design.md` — original Lakebase migration design
- `docs/superpowers/specs/2026-03-19-introspection-panel-design.md` — Introspection feature spec
- `docs/superpowers/specs/2026-04-14-ai-gateway-dashboards-design.md` — AI Gateway dashboards
- `docs/plans/*` — earlier implementation plans (kept as historical record)
