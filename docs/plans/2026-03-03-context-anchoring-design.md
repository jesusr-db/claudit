# Active Context Anchoring — Design Doc

**Date:** 2026-03-03
**Problem:** Mid-session context degradation in marathon Claude Code sessions. As conversations grow, auto-compaction drops architectural decisions, task progress, and code context.

**Approach:** Four-layer defense against context loss.

## Layer 1: CLAUDE.md (Stable Project Knowledge)

Location: `./CLAUDE.md` (committed to git)

Contains stable, rarely-changing project knowledge:
- Architecture overview (tech stack, file structure)
- Key files and their purposes
- Coding conventions
- A "Current Focus" section updated at session/phase boundaries

Survives every compaction (re-read from disk automatically). Target 80-120 lines, max 200.

## Layer 2: PreCompact Hook + Context Anchor

**Hook:** `~/.claude/hooks/hooks.json` — PreCompact hook that cats `.claude/context-anchor.md` into the surviving context before compaction fires.

**Context anchor:** `.claude/context-anchor.md` (gitignored, local-only) — volatile session state:
- Current task description
- Decisions made this session
- Files modified so far
- What's left to do

Updated during the session by Claude or the user. Injected automatically when compaction fires.

Key distinction: CLAUDE.md = stable knowledge. Context anchor = volatile session state.

## Layer 3: Strategic Compaction + Task Tracking

**Manual `/compact [focus]`:** Run proactively when `/context` shows high usage. Focus instructions guide what the summary preserves.

**`/context` monitoring:** Check periodically to see context consumption before auto-compaction fires at 95%.

**TaskCreate for progress:** Create tasks at the start of multi-step work. Tasks persist independently of context compression. After compaction, Claude checks TaskList to recover progress state.

**Session rhythm:**
1. Start session — Claude reads CLAUDE.md
2. Describe goal — create tasks for steps
3. Work 30-60 min
4. Check `/context` — if filling, run `/compact [focus]`
5. PreCompact hook fires — injects context anchor
6. Claude checks TaskList — picks up progress
7. Update context-anchor.md with new decisions
8. Repeat 3-7

## Layer 4: Subagent Offloading (Prevention)

Reduce context consumption rate by offloading verbose operations to subagents:
- Exploratory reads (3+ files)
- Test runs
- Search operations across codebase
- Documentation/API research

Keep inline: file edits, architectural decisions, small targeted reads.

Encoded as a persistent instruction in CLAUDE.md so it survives compaction.

## Files to Create/Modify

1. `./CLAUDE.md` — New file, project knowledge anchor
2. `~/.claude/hooks/hooks.json` — New file, PreCompact hook
3. `.claude/context-anchor.md` — New file, volatile session state (gitignored)
4. `.gitignore` — Add `.claude/context-anchor.md`
