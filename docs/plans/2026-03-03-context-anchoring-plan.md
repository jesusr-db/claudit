# Active Context Anchoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up a four-layer defense against mid-session context degradation in marathon Claude Code sessions.

**Architecture:** CLAUDE.md provides stable project knowledge that survives compaction. A PreCompact hook injects volatile session state from a context-anchor file. Task tracking and subagent discipline are encoded as persistent instructions.

**Tech Stack:** Claude Code hooks (JSON), Markdown files, gitignore

---

### Task 1: Create CLAUDE.md

**Files:**
- Create: `./CLAUDE.md`

**Step 1: Create the file**

```markdown
# Claudit - Claude Code Observability Dashboard

## Architecture
- **Databricks App**: FastAPI backend + React frontend
- **Backend**: FastAPI with routers for metrics, sessions, mcp_tools, platform, mcp_servers, kpis
- **Frontend**: React + Vite + TypeScript, views/shared/app structure
- **Data**: Unity Catalog tables in `jmr_demo.zerobus`, queried via SQL Warehouse
- **Deployment**: `app.yaml` -> Databricks Apps, uvicorn on port 8000

## Key Files
- `backend/main.py` — FastAPI entry, mounts routers + serves static files
- `backend/routers/` — API routes: metrics, sessions, mcp_tools, platform, mcp_servers, kpis
- `backend/config.py` — Environment config (CATALOG, SCHEMA_NAME, SQL_WAREHOUSE_ID)
- `frontend/src/views/` — React page components
- `frontend/src/shared/` — Shared components, hooks, utilities
- `frontend/src/app/` — App shell, routing, layout
- `app.yaml` — Databricks App config with env vars
- `databricks.yml` — Asset bundle config
- `design-system/` — Soft UI Evolution design tokens and guidelines

## Conventions
- Commits: conventional commits (feat:, fix:, docs:, refactor:)
- CSS: Soft UI Evolution design system
- Charts: Recharts library
- Backend: FastAPI routers pattern, one router per domain
- Frontend: TypeScript strict, functional components

## Context Management
- Use subagents for exploratory reads (3+ files), test runs, and search operations
- Keep edits and decision-making in the main conversation
- After compaction, check TaskList to recover progress state
- Update .claude/context-anchor.md with decisions as you go

## Current Focus
<!-- Update this when starting each session or major phase -->
- Active feature: TBD
- Key decisions: TBD
```

**Step 2: Verify the file exists and reads correctly**

Run: `cat CLAUDE.md | wc -l`
Expected: ~35 lines (well under 200 limit)

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md for context anchoring"
```

---

### Task 2: Create PreCompact hook

**Files:**
- Create: `~/.claude/hooks/hooks.json`

**Step 1: Create the hooks file**

```json
{
  "hooks": {
    "PreCompact": [
      {
        "matcher": "auto",
        "hooks": [
          {
            "type": "command",
            "command": "cat .claude/context-anchor.md 2>/dev/null || echo 'No context anchor found — update .claude/context-anchor.md with current session state'"
          }
        ]
      }
    ]
  }
}
```

**Step 2: Verify the hook file is valid JSON**

Run: `python3 -c "import json; json.load(open(os.path.expanduser('~/.claude/hooks/hooks.json'))); print('VALID')" 2>&1 || echo 'INVALID JSON'`
Expected: VALID

**Step 3: No commit needed** — this is a user-level file outside the repo.

---

### Task 3: Create context-anchor template

**Files:**
- Create: `.claude/context-anchor.md`

**Step 1: Create the .claude directory if needed and the template file**

```markdown
# Session Context Anchor
<!-- This file is injected into context before compaction via PreCompact hook -->
<!-- Update this during your session with decisions, progress, and state -->

## Current Task
Not set — describe what you're working on

## Decisions Made This Session
- (none yet)

## Files Modified So Far
- (none yet)

## What's Left
- [ ] (add items as you go)
```

**Step 2: Verify the file exists**

Run: `cat .claude/context-anchor.md | head -5`
Expected: First 5 lines of the template

**Step 3: No commit** — this file will be gitignored in Task 4.

---

### Task 4: Update .gitignore

**Files:**
- Modify: `.gitignore`

**Step 1: Add context-anchor to gitignore**

Append to `.gitignore`:

```
# Context anchor (volatile session state, not for version control)
.claude/context-anchor.md
```

**Step 2: Verify it's ignored**

Run: `git check-ignore .claude/context-anchor.md`
Expected: `.claude/context-anchor.md`

**Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore context-anchor.md (volatile session state)"
```

---

### Task 5: Verify the full system works

**Step 1: Confirm CLAUDE.md is loaded**

Start a new session or run `/clear`. Claude should reference project architecture without being told.

**Step 2: Confirm hook is registered**

Run: `cat ~/.claude/hooks/hooks.json`
Expected: The PreCompact hook definition

**Step 3: Test the hook output**

Run: `cat .claude/context-anchor.md`
Expected: The template contents (this is what gets injected on compaction)

**Step 4: Commit the design doc**

```bash
git add docs/plans/2026-03-03-context-anchoring-design.md docs/plans/2026-03-03-context-anchoring-plan.md
git commit -m "docs: add context anchoring design and implementation plan"
```
