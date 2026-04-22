# Plugin Orchestration Patterns

Plugins compose through five patterns. Each solves a different coordination problem -- when to load another plugin's expertise, how to run agents in parallel, where to persist state across sessions, how to orchestrate autonomous multi-phase workflows, and how to delegate to external AI models.

---

## Pattern 1: Companion Skill Loading

One plugin's command loads skills from other plugins at specific phases of a workflow.

### When to use

Your command has a multi-phase workflow where certain phases need domain expertise from a different plugin. The expertise is optional -- the command works without it, richer with it.

### How to declare

**In plugin.json:** Add the companion plugin to `pluginDependencies`:

```json
{
  "pluginDependencies": {
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
- `lt10` from project-manager itself (Phase 8) -- self-reference, no `dependencies` declaration needed

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

**In plugin.json:** Add `pluginDependencies` for external agent providers:

```json
{
  "pluginDependencies": {
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

You need state that persists across sessions. One plugin produces information that another plugin consumes -- but they don't run at the same time, so they can't pass data directly. ai-memory is the shared state layer.

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

## Pattern 4: Pipeline Orchestration

The pipeline plugin composes all three patterns above into a sequential workflow with review-fix loops at each execution stage.

### When to use

You have a multi-step development workflow that needs to run autonomously: assess current state, research context, generate execution prompts, review adversarially, execute chunks in worktrees, run review-fix loops after each chunk, and deliver a clean feature branch.

### How it works

The pipeline plugin combines:

1. **Companion Skill Loading** -- Each phase loads domain skills (ai-memory from ned, development from assembly, livewires from live-wires, etc.)
2. **Multi-Agent Dispatch** -- Research phase dispatches 5 parallel research agents; adversarial review dispatches 3 perspective agents; execution dispatches subagents per chunk
3. **Memory-Mediated Coordination** -- Records pipeline sessions to ai-memory for cross-session learning
4. **Worktree Isolation** -- Each execution chunk runs in its own worktree, merged back after passing review
5. **Review-Fix Convergence** -- dm-review-loop runs after each chunk with zero-deferral policy (all P1/P2/P3 fixed)

### Execution model

```
assess (parallel: code + UX agents)
  -> research (parallel: 5 research agents)
    -> plan (user or compound-engineering)
      -> promptcraft (overlap analysis, manifest generation)
        -> adversarial review (3 perspectives, iterate to convergence)
          -> execution (worktree per chunk, dm-review-loop per chunk)
            -> final review (full dm-review on feature branch)
              -> deliver (clean feature branch ready for PR)
```

### Real example

`plugins/pipeline/commands/pipeline.md` orchestrates the full workflow:

- Phase 1 (Assess): Assess skill with parallel code + UX agents
- Phase 2 (Research): Research skill with 5 parallel research sources
- Phase 3 (Plan): User or compound-engineering creates the plan
- Phase 4 (Prompts): Promptcraft skill generates manifests with overlap-aware ordering
- Phase 5 (Adversarial Review): Plan-adversary agent iterates to convergence
- Phase 6 (Execute): Execution-orchestrator manages worktrees, subagents, and dm-review-loop; records to ai-memory via ned
- Phase 7 (Deliver): Final review, branch summary, PR option

### Failure modes

| Failure | Handling |
|---------|----------|
| Subagent fails to complete chunk | Flag chunk, skip dependent chunks, continue independent chunks |
| Review-fix loop doesn't converge (max iterations) | Flag chunk as "needs attention," continue pipeline |
| Merge conflict after chunk | Attempt auto-resolution; if complex, flag and continue |
| Worktree creation fails | Fall back to branch-based execution without worktree isolation |
| ai-memory unavailable | Skip memory capture, note in final report |

---

## Pattern 5: CLI-Mediated Model Delegation

A Claude subagent constructs a prompt, invokes an external AI model via a CLI tool, parses the structured response, and formats findings for the calling workflow.

### When to use

A task benefits from capabilities that Claude doesn't have natively -- Google search grounding with citations, very large context windows (2M tokens), or a code execution sandbox. The external model supplements Claude; it never replaces Claude as the orchestrator.

### How it works

1. A Claude subagent (model: sonnet) is dispatched as part of a normal Multi-Agent Dispatch
2. The subagent constructs a self-contained prompt (the external model has no conversation context)
3. The subagent invokes the external CLI via Bash with `timeout` and `--output-format json`
4. The subagent parses the JSON response and formats findings for the consolidator
5. On any failure (timeout, rate limit, empty, malformed), the subagent reports gracefully and the review/research proceeds without it

### Key constraint

The external model is stateless -- each invocation is a fresh session with no memory. Every prompt must be fully self-contained. The external model cannot access Claude's MCP servers, conversation history, or tool results.

### Real example

`plugins/gemini/` wraps Gemini CLI as a subagent. Three agents use this pattern:

- **gemini-diff-analyst** -- dm-review conditional agent. When diffs exceed 5000 lines, sends the full untruncated diff to Gemini's 2M token context for analysis alongside the truncated-diff core agents.
- **gemini-search-grounded** -- pipeline research Agent 6. Delegates web research to Gemini's Google search grounding, which returns structured citations with URLs.
- **gemini-code-executor** -- on-demand agent. Delegates algorithm verification to Gemini's Python sandbox.

### Failure modes

| Failure | Handling |
|---------|----------|
| CLI timeout | Report "timed out," proceed without external input |
| Model rate limit (quota exhausted) | Fall back through model chain (pro -> flash -> flash-lite -> skip) |
| Empty or malformed response | Report and skip gracefully |
| CLI not installed | Skip at source detection phase (graceful skip) |

---

## Pattern 6: Soft Cross-Skill Companions

Skills cross-reference each other in their SKILL.md text without declaring a hard `pluginDependencies` constraint. Loading happens implicitly when Claude reads the skill body and follows a path pointer to a sibling reference; nothing forces the sibling to be installed.

This pattern is appropriate when:

- The cross-reference enriches behavior but the source skill remains useful without it.
- The pointed-at file is documentation a reader can fall back to reading manually.
- Hard `pluginDependencies` would over-constrain installation for users who do not need the enrichment.

When to upgrade to a hard dependency:

- The source skill makes assertions that depend on the sibling existing (e.g., "the canonical glossary lives at `plugins/council/skills/governance/references/plain-language-glossary.md`" assumes council is installed).
- The user-experience drop is severe without the sibling (broken cross-reference looks like a bug).
- Multiple skills point at the same sibling, so a missing sibling cascades.

**Examples:**

- `plugins/design-machines/skills/strategy/SKILL.md` references `plugins/council/skills/governance/references/plain-language-glossary.md` as a "source of truth." This is a hard dependency: design-machines now declares `pluginDependencies: { "council": ">=1.9.0" }` in its plugin.json.
- `plugins/ghostwriter/skills/voice/SKILL.md` references `plugins/design-machines/skills/audience/references/language-card.md` from the Audience Awareness section. Voice still functions without audience awareness, just less well; ghostwriter declares `optionalPluginDependencies: { "design-machines": ">=1.5.0" }` to express the soft expectation.
- `plugins/design-machines/skills/audience/SKILL.md` lists `council:governance`, `council:decolonial-language`, `ghostwriter:voice`, and `ghostwriter:social-media` as Companion Skills. These pointers help Claude assemble the right context window when audience-related work begins; none of them are strict requirements.

**Validation:** `./tools/check-dependencies.sh --graph` reflects only declared `pluginDependencies` and `optionalPluginDependencies`. Soft cross-skill pointers do not appear in the graph by design. If you want a soft pointer to be visible to the validator, upgrade it to an `optionalPluginDependencies` entry.

---

## Choosing a Pattern

| Situation | Pattern |
|-----------|---------|
| Multi-phase workflow needs expertise from other plugins | Companion Skill Loading |
| Need multiple independent perspectives on the same input | Multi-Agent Dispatch |
| State must persist across sessions or between unrelated plugins | Memory-Mediated Coordination |
| Combination: workflow with parallel agents AND persistent tracking | Use all three (see dm-review, which combines dispatch + memory) |
| Autonomous multi-phase workflow combining all three patterns with review-fix loops | Pipeline Orchestration |
| Task benefits from capabilities of an external AI model (search grounding, large context, code execution) | CLI-Mediated Model Delegation |
| Skills cross-reference each other in body text without hard install requirements | Soft Cross-Skill Companions |

---

## Validation

Run `./tools/validate-composition.sh` to verify all cross-plugin references resolve. Run `./tools/validate-composition.sh --all` to check everything: description evals, dependencies, and composition in one pass.
