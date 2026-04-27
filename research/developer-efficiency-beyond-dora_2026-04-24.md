# Developer Efficiency Beyond DORA — Brainstorm
_Generated: 2026-04-24 | Model: Claude Opus_

---

## Framing

The goal is to move beyond the classic DORA four-keys framework and design a "Developer Efficiency Panel" purpose-built for **GenAI/AI-harness-assisted coding workflows** — where Claude Code (and agent harnesses in general) sit between the developer and the code produced. DORA measures delivery-system outcomes (deploy frequency, lead time, CFR, MTTR) but is **blind to the human+AI loop**: whether the AI is helping or hindering, whether tokens are being spent productively, whether harness patterns are converging or thrashing, and whether the AI is genuinely reducing cognitive load vs. creating new classes of rework.

The 2025 DORA report calls this out as the "productivity paradox": individual throughput is up 21-34% with AI, but organizational delivery metrics stay flat, bugs/dev are up 54%, and review time is up 5x. "Tokenmaxxing" — treating tokens consumed as a proxy for productivity — is widely discredited (10x token cost for 2x throughput).

**Key constraints:**
- Data source today: OTEL telemetry in `cc_logs` / `cc_spans` materialized views in `jmr_demo.zerobus`, synced to Lakebase.
- Git, CI/CD, ticketing, and survey/perception systems are **not instrumented**. Classic DORA cannot be computed from current data.
- New tables/pipelines must be defined as SDP SQL files in DAB (CLAUDE.md rule: no bespoke artifacts).
- Panel must compose on top of existing tabs (Sessions, Token Consumption, Turnaround, Coding Agents, Platform, Model Efficiency, Introspection) — not duplicate them.

## Assumptions

1. Audience is mixed — engineering leaders (DORA-familiar framing) and platform/DevRel owners (harness tuning).
2. "Developer efficiency" = effective outcomes per unit of developer-time + AI-cost, not throughput or tokens. Tokens are an input/cost, never an output.
3. v1 should not wait on git/CI integration. Session-level efficiency metrics ship first.
4. Session-to-outcome linkage (git commit hook or branch-name convention emitting a correlation attribute) is the single highest-leverage phase-2 enhancement.
5. Named, defensible framework preferred over a bag-of-metrics. Leaders respond to "we implemented SPACE + DevEx for AI" better than "we made up these metrics."
6. No survey/perception data available today; deferred to phase 3.
7. "Harness" means the Claude Code agent loop itself — tool-use patterns, planning, decision ratios, retry/recovery, context depth.

## Perspectives

- **Engineering leader (VP/Director):** Board-ready numbers, DORA-familiar framing, credible AI net-impact story. Distrusts raw token metrics.
- **Platform / Claude Code admin:** Whether harness patterns converge (few iterations, clean tool chains) or thrash (orphan decisions, rework loops, retries). Optimizes prompts, rules, rate limits.
- **Individual developer:** Are feedback loops fast? Is flow state preserved? Is rework decreasing?
- **Finance / FinOps:** Cost-per-outcome and ROI. Needs cost tied to something real downstream (merged PR, closed ticket).
- **Security / governance:** Tool-use safety signals: escalating permissions, denied decisions, risky invocations, cache blowouts.
- **Skeptic researcher (METR / DX Research):** Demands paired observational metrics and rework signals, not self-reported throughput.

## Options

### Option A — Pure DORA-lite
Implement the four DORA keys plus AI-usage overlays.

**Pros:** Instantly recognizable to leaders. Directly comparable to the 2025 DORA report.
**Cons:** Requires git/CI/incident instrumentation Claudit does not have. Several months of integration before any signal. DORA 2025 itself expanded to 20+ metrics precisely because the four keys are insufficient for AI.
**Fit:** Low for v1. High cost, little differentiation. Punts on the "beyond DORA" ask.

---

### Option B — SPACE-for-AI
Implement the [SPACE framework](https://queue.acm.org/detail.cfm?id=3454124) (Satisfaction, Performance, Activity, Communication, Efficiency/flow) with metrics rebuilt for AI-harness telemetry.

**Mapping to Claudit data:**
- **S:** Deferred to phase 2. For v1: Decision Acceptance Rate (`decision='accept'` / total `tool_decision`).
- **P:** Session Outcome Rate, Rework Ratio (successive Edit/Write to same file within N prompts).
- **A:** Already exists — Token Consumption, Coding Agents tab. Reuse.
- **C:** Clarification Density (`AskUserQuestion` calls per prompt), Plan-to-Execute Ratio.
- **E:** Uninterrupted Streak (mean tokens between tool failures), Context Thrash (re-reads of same file).

**Pros:** Named, defensible, widely adopted. Explicitly handles the productivity-paradox trap. Most signals fit existing schema.
**Cons:** Satisfaction dimension requires new instrumentation. Some composites (rework, thrash) are non-trivial SQL.
**Fit:** High.

---

### Option C — DevEx + SPACE hybrid ⭐ RECOMMENDED
Core panel = SPACE-for-AI (Option B), augmented with [DevEx](https://queue.acm.org/detail.cfm?id=3595878)'s three AI-native dimensions — **Feedback Loops, Cognitive Load, Flow State** — as a "Developer Experience Index."

Add the DORA 2025 "Seven AI Capabilities" as a **qualitative maturity card** at the top (config-driven checkboxes, not a computed metric). This is how DORA 2025 itself frames AI organizational readiness.

**Signature AI-native metrics unique to this hybrid:**
1. **Feedback Loop Latency** — p50/p95 seconds from tool call to tool result, by tool type.
2. **Cognitive Load Index** — composite: (avg tools per prompt) × (context thrash) × (orphan decision rate). Lower is better.
3. **Flow State Disruption Rate** — prompts/hour ending in `api_error` or abandoned tool chains.
4. **AI-Effective Yield (AEY)** — net applied edits / total AI cost (USD). The "tokenmaxxing" counter-metric.
5. **Harness Convergence Score** — `(prompts_per_session ÷ tools_per_prompt) × successful_completion_rate`. Rising = harness more efficient.

**Pros:** Directly addresses "beyond DORA." Introduces novel indexes (CLi, AEY) the existing ecosystem lacks. Uses every signal Claudit already captures. Frames DORA as the phase-2 overlay.
**Cons:** More metrics = more explanation burden. Composites need tuning + docs. Must pick headline 5-6 ruthlessly.
**Fit:** Highest. Best match for existing `cc_logs`/`cc_spans` data and the explicit user ask.

## Recommendation

**Ship Option C (SPACE + DevEx hybrid with AI-native indexes), phased.**

**Phase 1 — v1 panel (data already in Claudit):**
Implement SPACE-for-AI with four of five dimensions (defer S), plus the three DevEx dimensions as a "Developer Experience Index" card. Headline five metrics with drill-downs:
1. **AI-Effective Yield (AEY)** — $ cost per accepted edit (labeled "in-session" until phase 2)
2. **Cognitive Load Index** — composite, lower is better; tooltip shows inputs
3. **Feedback Loop Latency** — p50/p95 by tool type
4. **Harness Convergence Score** — trended over time
5. **Rework Ratio** — re-edits within N prompts of same file

Plus a top-of-panel "AI Capability Maturity" qualitative card (config YAML, 7 DORA 2025 capabilities, toggle-able).

**Phase 2 — requires new instrumentation:**
- Lightweight git-commit-hook / session correlation ID to join Claude sessions → PRs/commits
- Unlocks real DORA overlays, true Rework Ratio, and AEY with merged-outcome denominators

**Phase 3 (optional):** Developer pulse survey for the S (Satisfaction) dimension.

**Top 2 risks:**
1. **Composite metric credibility** — Cognitive Load Index and Harness Convergence Score are derived formulas. Every composite must have a tooltip showing inputs and a published formula. Start with equal weights.
2. **Absent outcome signal in v1** — without git/PR linkage, AEY uses in-session `decision='accept'` as numerator. Must be explicitly labeled "In-session AEY" paired with a phase-2 roadmap callout to avoid recreating the tokenmaxxing mistake.

## Data Requirements

### Available now in `jmr_demo.zerobus` — no new instrumentation needed

| Metric | Source | Key columns / filters | Granularity |
|---|---|---|---|
| **AI-Effective Yield (in-session)** | `cc_logs` | `cost_usd` where `event_name='api_request'`; denominator = `tool_decision` where `decision='accept'` | per session, per user, rolling 7/30d |
| **Cognitive Load Index** | `cc_logs` | (a) tool calls per prompt: `tool_result` / distinct `prompt_id`; (b) context thrash: repeated `Read` on same `file_path` within session; (c) orphan `tool_decision` without matching `tool_result` | per session; aggregate per user/day |
| **Feedback Loop Latency** | `cc_logs` + `cc_spans` | `duration_ms` on `tool_result` rows; percentiles by `tool_name` | per tool call; p50/p95 per tool per day |
| **Harness Convergence Score** | `cc_logs` | (prompts per session) ÷ (tools per prompt) × (1 - api_error rate) | per session, trended daily |
| **Rework Ratio (in-session)** | `cc_logs` | Successive `Edit`/`Write`/`MultiEdit` on same `file_path` within rolling N prompts in same `session_id` | per session, per file |
| **Decision Acceptance Rate** | `cc_logs` | `tool_decision` with `decision` bucketed (accept / reject / ask) | per user, per tool, per day |
| **Clarification Density** | `cc_logs` | `AskUserQuestion` count / distinct `prompt_id` | per session |
| **Plan-to-Execute Ratio** | `cc_logs` | `ExitPlanMode` followed by successful tool chain (no subsequent `api_error`) within same session | per session |
| **Flow State Disruption Rate** | `cc_logs` | Prompts where terminal event = `api_error` OR orphan `tool_decision` / hour | per user, per day |
| **Uninterrupted Streak** | `cc_logs` | Mean tokens between consecutive `api_error` events in same session | per session |

### Requires new instrumentation (phase 2)

| Metric | What's needed | How |
|---|---|---|
| **DORA: Deploy Frequency, Lead Time** | Git/CI events correlated to Claude session via session-id tag (commit trailer or branch-name convention) | New `git_events` bronze table in `jmr_demo.zerobus` via GitHub Actions webhook → Lakeflow Connect OR client-side git hook emitting OTEL with `session.id` |
| **DORA: Change Failure Rate** | CI failure + rollback signals tagged to commits | Same pipeline + optional Jira/PagerDuty |
| **DORA: MTTR** | Incident open/close timestamps tagged to originating commit | Jira / incident system; out of scope for v1 |
| **True Rework Ratio** | Post-commit edit churn vs. reverts within 7/30d | git-events + git-blame pipeline |
| **AEY with merged-outcome denominator** | Session → merged-PR linkage | session-id-in-commit-trailer |
| **Satisfaction (SPACE-S)** | Developer pulse survey responses | In-app micro-survey or Slack pulse → `zerobus.dev_pulse` table |
| **AI Capability Maturity card** | Manual config (not a metric) | `config/ai_capabilities.yml` in `resources/`; 7 booleans + notes |

### New materialized views recommended (DAB SDP SQL files)

- **`cc_prompt_summary`** — one row per (`session_id`, `prompt_id`): total tools, api_errors, tool_decisions by decision type, clarification count, plan-mode flag, first_ts/last_ts. Backbone for CLi, Rework Ratio, Harness Convergence.
- **`cc_session_summary`** — one row per `session_id`: prompt-level aggregates, total cost, terminal status. Backbone for AEY and session trends.
- **`cc_file_touch`** — one row per (`session_id`, `file_path`, `event_ts`) from `tool_parameters` on Edit/Write/Read. Backbone for Rework Ratio and Context Thrash.

All three defined in `src/pipelines/lakebase_sync/` SDP SQL files, registered in `resources/lakebase_sync.yml` (DAB-compliant per CLAUDE.md).

---

## Sources

- [2025 DORA State of AI-Assisted Software Development](https://cloud.google.com/resources/content/2025-dora-ai-assisted-software-development-report)
- [DORA Report 2025 full PDF](https://services.google.com/fh/files/misc/2025_state_of_ai_assisted_software_development.pdf)
- [Faros: Key Takeaways from the 2025 DORA Report](https://www.faros.ai/blog/key-takeaways-from-the-dora-report-2025)
- [The SPACE of Developer Productivity — ACM Queue](https://queue.acm.org/detail.cfm?id=3454124)
- [DevEx: What Actually Drives Productivity — ACM Queue](https://queue.acm.org/detail.cfm?id=3595878)
- [DevEx, a New Metrics Framework from the Authors of SPACE — InfoQ](https://www.infoq.com/articles/devex-metrics-framework/)
- [Faros: Tokenmaxxing — why token consumption isn't AI engineering productivity](https://www.faros.ai/blog/tokenmaxxing)
- [METR: Measuring the Impact of Early-2025 AI on Experienced OSS Developer Productivity](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/)
- [DX: How to measure AI's impact on developer productivity](https://getdx.com/blog/ai-measurement-hub/)
