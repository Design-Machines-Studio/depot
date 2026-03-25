# Plugin Orchestration Patterns

Three patterns for cross-plugin composition in the depot. Each tells you when to use it, how to declare it, and what to do when it fails.

---

## Pattern 1: Companion Skill Loading

One plugin's command loads skills from other plugins at specific phases of a workflow.

### When to use

Your command has a multi-phase workflow where certain phases need domain expertise from a different plugin. The expertise is additive -- the command works without it but produces richer results with it.

### How to declare

**In plugin.json:** Add the companion plugin to `dependencies`:

```json
{
  "dependencies": {
    "ghostwriter": ">=3.7.0",
    "council": ">=1.5.0"
  }
}
```

**In the command .md:** List companion skills with their phases:

```markdown
### Companion Skills

Load these skills when reaching their relevant phases:

- **Phase 5 (Calendar):** Load `strategy` skill from design-machines plugin
- **Phase 7 (Content):** Load `social-media` and `voice` from ghostwriter plugin
```

### Real example

`plugins/project-manager/commands/sprint-plan.md` (Step 5) loads:
- `ai-memory` from ned (Phases 1, 3)
- `strategy` from design-machines (Phase 5)
- `social-media` + `voice` from ghostwriter (Phase 7)
- `governance` from council (Phase 7)
- `lt10` from project-manager itself (Phase 8)

### Failure modes

| Failure | Handling |
|---------|----------|
| Companion plugin not installed | Skip that phase. Note: "Skipped Phase 7 -- ghostwriter not installed." |
| Companion skill removed in newer version | Dependency version constraint should prevent this. If it happens, skip the phase. |
| Companion skill loads but returns unexpected data | The command owns the workflow -- treat companion output as advisory, not authoritative. |

---

## Pattern 2: Multi-Agent Dispatch

A skill launches multiple agents in parallel, collects their outputs, and consolidates results.

### When to use

You need multiple specialized perspectives on the same input. Each perspective is independent -- agents don't need to see each other's output. A consolidator merges everything at the end.

### How to declare

**In plugin.json:** Add `dependencies` for external agent providers:

```json
{
  "dependencies": {
    "accessibility-compliance": ">=1.2.0",
    "live-wires": ">=1.5.1"
  }
}
```

**In the skill SKILL.md:** Define the orchestration phases:

1. **Agent selection table** -- maps file types to agents with paths:
   ```markdown
   | Condition | Agent | Path |
   |-----------|-------|------|
   | `.css` changed | a11y-css-reviewer | plugins/accessibility-compliance/agents/review/a11y-css-reviewer.md |
   ```

2. **Dispatch rules** -- launch all agents in a single message with multiple Agent tool calls.

3. **Consolidation** -- reference a consolidator agent that merges outputs.

**Agent definition files** follow the standard format:
```yaml
---
name: agent-name
description: One-line purpose
---
```

Each agent produces findings in the severity format (P1/P2/P3) or an explicit no-findings indicator.

### Real example

`plugins/dm-review/skills/review/SKILL.md` orchestrates up to 15 agents:
- 5 always-run core agents (from dm-review itself)
- 10 conditional agents (from dm-review, accessibility-compliance, live-wires, ghostwriter, council)
- Input guardrails (Phase 3.5) validate diff size and filter sensitive files
- Output guardrails (Phase 5) check structure, cap findings, detect ghost files
- Failure handling classifies core vs conditional agent failures

### Failure modes

| Failure | Handling |
|---------|----------|
| Agent times out (>120s) | Skip. Record in Agent Summary table. |
| Agent returns malformed output | Flag as malformed. Include raw output in collapsible section. |
| Core agent fails | Flag review as "REVIEW INCOMPLETE." |
| All conditional agents fail | Review is "Degraded" but still valid with core agents. |
| Consolidator fails | Output raw agent findings as unmerged list. |

See `plugins/dm-review/skills/review/references/guardrails.md` and `references/graceful-degradation.md` for the full rule set.

---

## Pattern 3: Memory-Mediated Coordination

Plugins write observations to ai-memory entities. Other plugins (or the same plugin in a later session) read those observations for context.

### When to use

You need state that persists across sessions. One plugin produces information that another plugin consumes -- but they don't run at the same time, so they can't pass data directly. ai-memory acts as the shared state layer.

### How to declare

**In SKILL.md or command .md frontmatter:** List ai-memory tools in `allowed-tools`:

```yaml
allowed-tools:
  - mcp__ai-memory__search_entities
  - mcp__ai-memory__get_entity
  - mcp__ai-memory__add_observation
  - mcp__ai-memory__save
```

**Entity naming convention:** Use namespaced prefixes for depot-level entities:
- `DepotMetrics` -- global marketplace metrics (type: System)
- `DepotPlugin:<name>` -- per-plugin metrics (type: Tool)
- Project entities use the project's actual name (type: Project)

**Observation format:** Date-prefix, factual, specific, <300 characters:
```
[2026-03-25] Invocation: voice -- correct
[2026-03-25] Review session: 9/11 agents completed, 2 skipped
```

### Real example

- `plugins/ned/skills/recorder/SKILL.md` writes session summaries to project entities
- `plugins/ned/commands/depot-metrics.md` records skill invocation outcomes to `DepotPlugin:*` entities
- `plugins/dm-review/skills/review/SKILL.md` Phase 7 writes review summaries to project entities
- `plugins/dm-review/skills/review/SKILL.md` Phase 7b writes agent dispatch data to `DepotMetrics`

### Failure modes

| Failure | Handling |
|---------|----------|
| ai-memory MCP not available | Skip silently. Never block a workflow on memory writes. |
| Entity doesn't exist | Search first. Create if not found. Use the correct entity type. |
| Observation duplicated | Check existing observations before adding. Use date prefixes to detect same-day duplicates. |
| Entity has too many observations | Roll up monthly per the policy in `docs/plugin-memory-schema.md`. |

See `docs/plugin-memory-schema.md` for the full entity schema and rollup policy.

---

## Choosing a Pattern

| Situation | Pattern |
|-----------|---------|
| Multi-phase workflow needs expertise from other plugins | Companion Skill Loading |
| Need multiple independent perspectives on the same input | Multi-Agent Dispatch |
| State must persist across sessions or between unrelated plugins | Memory-Mediated Coordination |
| Combination: workflow with parallel agents AND persistent tracking | Use all three (see dm-review, which combines dispatch + memory) |

---

## Validation

Run `./tools/validate-composition.sh` to verify all cross-plugin references resolve. Run `./tools/validate-composition.sh --all` to check everything: description evals, dependencies, and composition in one pass.
