---
name: review
description: Code review orchestrator that launches parallel specialized agents across accessibility, security, architecture, CSS, voice, and governance domains. Use when reviewing code changes, PRs, branches, or files. Invoke with /dm-review for full review or /dm-review quick for core agents only. Also use when the user says "review this", "check my code", "run a code review", or "review before merging".
disable-model-invocation: true
argument-hint: "[scope: PR number, branch, path, or blank]"
---

# DM Code Review

A single-command code review system that launches parallel specialized agents tailored to Design Machines stacks: Go+Templ+Datastar, Craft CMS+Twig, and Live Wires CSS.

## Usage

- `/dm-review` — Full review: all applicable agents + memory capture
- `/dm-review quick` — Quick review: 5 core agents only, no conditional agents, no memory capture

## Orchestration Phases

Execute these 6 phases in order. Do not skip phases.

---

### Phase 1: Target Detection

Determine what files changed. Try these sources in order:

1. **If a PR number or URL was given:** `gh pr diff <number>`
2. **If on a feature branch:** `git diff main...HEAD --name-only`
3. **If uncommitted changes exist:** `git diff --name-only` + `git diff --cached --name-only`
4. **If a specific path was given:** use that path directly

Store the list of changed files and their extensions. If no changes detected, tell the user and stop.

Also get the full diff content for the agents:
```bash
git diff main...HEAD  # or appropriate diff command based on the target
```

---

### Phase 2: Project Type Detection

Detect the project type by checking for marker files in the project root:

| Check | Project Type |
|-------|-------------|
| `go.mod` exists | Go project |
| `docker-compose.yml` exists AND Go project | Go+Templ+Datastar |
| `craft/` directory exists OR `.ddev/` directory exists | Craft CMS |
| `package.json` exists AND `.css` files changed | CSS Framework |

A project can be multiple types (e.g., Go+Templ+Datastar with CSS).

If reviewing the depot itself, project type is "Plugin Marketplace (Markdown+JSON)".

---

### Phase 3: Agent Selection

Select which agents to launch based on mode, changed file extensions, and project type.

#### Always-Run Agents (both Full and Quick mode)

These 5 agents always run:

1. **code-simplicity-reviewer** — read agent from `plugins/dm-review/agents/review/code-simplicity-reviewer.md`
2. **security-auditor** — read agent from `plugins/dm-review/agents/review/security-auditor.md`
3. **pattern-recognition-specialist** — read agent from `plugins/dm-review/agents/review/pattern-recognition-specialist.md`
4. **architecture-reviewer** — read agent from `plugins/dm-review/agents/review/architecture-reviewer.md`
5. **doc-sync-reviewer** — read agent from `plugins/dm-review/agents/review/doc-sync-reviewer.md`

**If mode is "quick", stop here. Skip to Phase 4 with only these 5 agents.**

#### Conditional Agents (Full mode only)

Add these agents based on which file extensions appear in the changed files:

| Condition | Agent | Agent definition file |
|-----------|-------|-----------------------|
| `.templ`, `.twig`, or `.html` changed | **a11y-html-reviewer** | `plugins/accessibility-compliance/agents/review/a11y-html-reviewer.md` |
| `.css` changed | **a11y-css-reviewer** | `plugins/accessibility-compliance/agents/review/a11y-css-reviewer.md` |
| `.css` changed | **css-reviewer** | `plugins/live-wires/agents/review/css-reviewer.md` |
| `.templ`, `.js`, or `.ts` changed AND project is Go+Templ+Datastar | **a11y-dynamic-content-reviewer** | `plugins/accessibility-compliance/agents/review/a11y-dynamic-content-reviewer.md` |
| `.md` or `.txt` changed, OR user-facing text in templates | **voice-editor** | `plugins/ghostwriter/agents/review/voice-editor.md` |
| Any source file changed AND test infrastructure exists | **test-coverage-reviewer** | `plugins/dm-review/agents/review/test-coverage-reviewer.md` |
| Paths contain `governance`, `proposal`, `voting`, `member`, `resolution`, or `bylaw` | **governance-domain** | `plugins/council/agents/review/governance-domain.md` |
| `.go` or `.templ` changed AND `go.mod` exists | **go-build-verifier** | `plugins/dm-review/agents/review/go-build-verifier.md` |
| `.twig` or `.php` changed AND (`craft/` or `.ddev/` exists) | **craft-reviewer** | `plugins/dm-review/agents/review/craft-reviewer.md` |
| `.templ`, `.twig`, `.html`, or `.css` changed | **visual-browser-tester** | `plugins/dm-review/agents/review/visual-browser-tester.md` |

#### Report Selection

After selecting agents, tell the user:

```
Launching X agents for [project type] review ([Full/Quick] mode):
- [agent-name-1]
- [agent-name-2]
- ...

Skipping Y agents:
- [agent-name] — reason (e.g., "no .css files changed")
```

---

### Phase 4: Parallel Agent Launch

Launch ALL selected agents simultaneously using multiple Agent tool calls in a single message. This is critical for performance — agents must run in parallel, not sequentially.

#### How to launch each agent

For each agent, follow this pattern:

1. **Read the agent definition file** from the depot (the path listed in the agent selection table)
2. **Build the agent prompt** by combining:
   - The full content of the agent definition file (this is the agent's system prompt)
   - The list of changed files
   - The diff content
   - Any relevant context (project type, file paths)
3. **Launch via the Agent tool** with:
   - `subagent_type`: "general-purpose"
   - `description`: short description (e.g., "Security audit of changes")
   - `prompt`: the combined prompt from step 2
   - `model`: "sonnet" (for all review agents)

**Example prompt structure for each agent:**

```
[Full content of the agent definition .md file]

---

## Files to Review

Changed files:
- path/to/file1.go
- path/to/file2.templ

## Diff

[full diff content]

## Project Context

Project type: Go+Templ+Datastar
Project root: /path/to/project
```

#### Browser-based agents

The `visual-browser-tester` agent uses Playwright MCP tools (prefixed `mcp__plugin_compound-engineering_pw__browser_*`) instead of reading files. It launches in parallel with all other agents. If the dev server is not running, it reports "Skipped" and does not block the review.

#### Parallelization rules

- Launch ALL agents in a single message with multiple Agent tool calls
- Do not wait for one agent to finish before launching the next
- Each agent runs independently with its own copy of the diff
- If an agent fails or times out, note it in the report but don't retry

---

### Phase 5: Consolidation

After all agents complete, synthesize their findings into the unified report.

Read the consolidation instructions from `plugins/dm-review/agents/workflow/review-consolidator.md` and follow them exactly:

1. **Collect** all findings from all agent outputs
2. **Deduplicate** findings that reference the same file and line
3. **Map severity** using the rules in `${CLAUDE_SKILL_DIR}/references/severity-mapping.md`
4. **Determine merge recommendation** using the logic:
   - Any P1 → "BLOCKS MERGE"
   - P2 only → "APPROVE WITH FIXES"
   - P3 only or clean → "CLEAN"
5. **Generate the unified report** following the template in `${CLAUDE_SKILL_DIR}/references/output-format.md`

Output the full report to the user.

---

### Phase 5.5: Simplification Pass

After outputting the review report, perform a simplification pass on the changed files. This catches complexity, redundancy, and over-engineering that the code-simplicity-reviewer identified — and applies fixes automatically rather than just reporting them.

**Execution:**

1. Review each changed file for simplification opportunities: dead code removal, redundant abstractions, overly complex logic, unused imports/variables, unnecessary indirection, functions that can be inlined, and patterns that can be consolidated. Focus on the specific findings from the code-simplicity-reviewer agent, but also look for anything it missed.
2. Apply simplification edits directly — this is not a report, it's an active refactoring pass. Make the code simpler, clearer, and shorter while preserving behavior.
3. After making changes, verify the build still passes:
   - Go projects: `docker compose exec app templ generate && docker compose exec app go build ./cmd/api`
   - CSS projects: `npm run build` (or equivalent)
   - Craft projects: clear caches if needed
4. If no simplification opportunities exist, note "Simplification pass: clean" and continue.

**Commit simplification changes separately** from the reviewed code:

```bash
git add -A
git commit -m "refactor: simplify per dm-review pass"
```

This phase mirrors Claude Code's built-in `/simplify` command. If `/simplify` is available, you can invoke it directly instead of performing the pass manually.

---

### Phase 6: Issue Tracking (Full mode only)

**Skip this phase in Quick mode.**

After outputting the report, ask the user how to track findings:

```
How should I track these findings?
1. Text files (todos/ directory) — one file per P1/P2 finding
2. GitHub Issues — one issue per P1/P2 finding
3. Skip — report only, no tracking
```

**If text files:**

Create `todos/` directory if it doesn't exist. For each P1 and P2 finding, create a file following the template in `${CLAUDE_SKILL_DIR}/references/issue-tracking.md`:

```
todos/{id}-pending-{priority}-{slug}.md
```

Examples:
```
todos/001-pending-p1-sql-injection-in-search.md
todos/002-pending-p2-missing-csrf-protection.md
```

P3 findings are NOT tracked individually — they stay in the report only.

After creating all files, summarize what was created:
```
Created N todo files in todos/:
- 001-pending-p1-... (description)
- 002-pending-p2-... (description)

Resolve with: /dm-review-fix
```

**If GitHub Issues:**

For each P1 and P2 finding, create a GitHub Issue using `gh issue create`:

```bash
gh issue create --title "[P1] Finding title" \
  --body "$(cat <<'EOF'
## Problem
Description from the review finding.

## Location
`path/to/file.ext:line`

## Fix
Remediation steps.

## Reference
OWASP/WCAG/pattern reference.

---
*From dm-review ([Full] mode, DATE)*
EOF
)" --label "review,p1"
```

Use labels `review` + `p1`/`p2` for severity. Create the labels first if they don't exist.

---

### Phase 7: Memory Capture (Full mode only)

**Skip this phase in Quick mode.**

After issue tracking (or if skipped), record the review in ai-memory:

1. Read the memory recorder instructions from `plugins/dm-review/agents/workflow/review-memory-recorder.md`
2. Use the ai-memory MCP tools to:
   - Search for the project entity
   - Add a review summary observation (under 300 characters)
   - Add P1 architectural observations if any
3. Call `save` to persist

If ai-memory tools are not available, skip silently.

---

## Reference Files

These files are loaded on demand during the review process:

- `${CLAUDE_SKILL_DIR}/references/severity-mapping.md` — P1/P2/P3 mapping rules per agent
- `${CLAUDE_SKILL_DIR}/references/agent-registry.md` — Complete agent catalog with trigger conditions
- `${CLAUDE_SKILL_DIR}/references/output-format.md` — Unified report template
- `${CLAUDE_SKILL_DIR}/references/issue-tracking.md` — Todo file template and GitHub Issue conventions

## Agent Definition Paths

See `${CLAUDE_SKILL_DIR}/references/agent-registry.md` for the complete agent catalog with trigger conditions, file matchers, and source plugins. Agent definition files are organized as:

- **dm-review agents:** `plugins/dm-review/agents/review/*.md`
- **Depot-native agents:** `plugins/{accessibility-compliance,live-wires,ghostwriter,council}/agents/review/*.md`
- **Workflow agents:** `plugins/dm-review/agents/workflow/*.md`

## Notes

- Agent definition files are read at runtime from the depot. If the exact path is not accessible (e.g., installed as a remote plugin), search for the file by name.
- The maximum number of parallel agents is 15 (full mode, all triggers hit). The minimum is 5 (quick mode).
- Each agent uses the `sonnet` model for speed and cost efficiency.
- The consolidator and memory recorder run after all review agents complete — they are not launched in parallel with the review agents.
