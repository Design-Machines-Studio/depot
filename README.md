# depot

DM-013/WORKS -- Design Machines' AI plugin marketplace for Claude Code and Codex.

## Install

```shell
/plugin marketplace add Design-Machines-Studio/depot
```

Then install individual plugins:

```shell
/plugin install ned@depot
/plugin install craft-developer@depot
/plugin install project-manager@depot
/plugin install council@depot
/plugin install design-machines@depot
/plugin install assembly@depot
/plugin install live-wires@depot
/plugin install ghostwriter@depot
/plugin install design-practice@depot
/plugin install project-scaffolder@depot
/plugin install accessibility-compliance@depot
/plugin install dm-review@depot
/plugin install the-local@depot
/plugin install chef@depot
/plugin install pipeline@depot
/plugin install gemini@depot
/plugin install deepseek@depot
```

Codex compatibility is generated from the Claude manifests. Claude remains the
source of truth; do not hand-edit Codex manifest files.

```shell
./tools/generate-codex-manifests.py
./tools/validate-dual-compat.sh
```

## Plugins

17 plugins | 36 skills | 41 agents | 31 commands

### ned

Personal knowledge graph and session capture. 2 skills, 2 commands.

- **ai-memory** -- Interface to the ai-memory knowledge graph (~5,850 entities)
- **recorder** -- Captures conversation sessions into structured summaries, pushes to ai-memory and Notion
- `/capture` -- Quick observation capture to ai-memory
- `/depot-metrics` -- Track and report plugin usage metrics via ai-memory

### craft-developer

Craft CMS 4/5 development expertise. 4 skills, 3 agents, 4 commands.

- **craft-development** -- Element queries, Matrix fields, GraphQL, eager loading, debugging patterns, and a 30+ query cookbook
- **content-modeling** -- Three-layer content modeling methodology with Matrix patterns and CKEditor configuration
- **craft-5-migration** -- Craft 4 to 5 migration patterns, breaking changes, and upgrade checklists
- **craft-mcp** -- Craft CMS MCP server integration for direct database and schema access
- **content-modeler** (agent) -- Full content modeling workflow with MCP integration
- **template-builder** (agent) -- Template development with performance optimization
- **craft-debugger** (agent) -- Deep debugging with MCP tools and systematic analysis
- `/craft-debug` -- Debug Craft CMS issues
- `/craft-migrate` -- Plan and execute Craft CMS migrations
- `/craft-model` -- Start a content modeling session
- `/craft-query` -- Build complex element queries

### project-manager

LT10 methodology and Notion-integrated sprint planning. 2 skills, 1 command.

- **lt10** -- Estimation (90th percentile), scoping, pricing, scheduling, risk management, stakeholder alignment, and communication scripts
- **planner** -- Notion-integrated sprint planning with Userback triage, Calendar.app meeting prep, Mail.app scanning, content ideation, and velocity tracking
- `/sprint-plan` -- Run the full sprint planning workflow

### council

Worker cooperative governance and decolonial content strategy. 2 skills, 1 agent, 1 command.

- **governance** -- BC Cooperative Association Act compliance, bylaw analysis, discovery processes, Co-op OS system design, voting thresholds, and financial governance
- **decolonial-language** -- Decolonial and anti-capitalist content strategy with terminology mappings between legal/regulatory language and solidarity economy alternatives
- **governance-domain** (agent) -- Reviews and guides cooperative governance feature development
- `/governance-check` -- Quick cooperative compliance check

### design-machines

Design Machines business strategy and product intelligence. 1 skill.

- **strategy** -- Product positioning, catalog system, Assembly architecture, partnerships, revenue model, brand language, design system (color palette, GT Standard typography, token architecture), and go-to-market strategy

### assembly

Assembly governance application development with Go, Templ, and Datastar. 1 skill, 2 agents, 1 command.

- **development** -- Docker-based Go development with Templ templates, Datastar reactivity, page-type workflows, component library, database patterns, and governance state machines
- **templ-scaffolder** (agent) -- Scaffolds new Templ pages, handlers, routes, and SSE endpoints
- **datastar-sse** (agent) -- Datastar reactivity and SSE endpoint patterns
- `/assembly-build` -- Build and test Assembly via Docker

### live-wires

Live Wires CSS framework for editorial websites. 1 skill, 1 agent.

- **livewires** -- Layout primitives (stack, grid, cluster, sidebar, cover, reel), baseline rhythm system, design tokens, cascade layers, container queries, and theming
- **css-reviewer** (agent) -- Reviews CSS and HTML for Live Wires framework compliance

### ghostwriter

Travis Gertz's personal writing voice and editorial style engine. 2 skills, 2 agents, 1 command.

- **voice** -- Writing style covering tone, sentence rhythm, argumentation structure, vocabulary, anti-AI-writing patterns, and context-aware register switching
- **social-media** -- Platform-native social media strategy for LinkedIn, Instagram, Bluesky, and Mastodon
- **voice-editor** (agent) -- Reviews and edits content to match Travis's voice
- **social-publisher** (agent) -- Drafts platform-native social media content
- `/voice-check` -- Quick text check against Travis's writing voice

### design-practice

Design philosophy rooted in modernist masters and editorial tradition. 4 skills, 2 agents.

- **typography** -- From Muller-Brockmann, Gerstner, Bringhurst. Modular scales, vertical rhythm, typeface selection
- **layout** -- Editorial layout and art direction. Grid systems, visual hierarchy, pacing
- **dataviz** -- From Tufte, Wong, Franchi. Chart type selection, data-ink ratio, graphical integrity
- **identity** -- From Rand, Bass, Draplin, Wyman, Glaser. Bold simplicity, systematic extensibility
- **design-critic** (agent) -- Evaluates design work against the combined framework
- **design-advisor** (agent) -- Design decisions and strategic direction

### project-scaffolder

Claude Code project infrastructure scaffolding. 1 skill.

- **scaffolding** -- Generates hooks, agents, settings.json, and CLAUDE.md templates for Go+Templ+Datastar, Go library, CSS framework, and Craft CMS projects

### accessibility-compliance

WCAG 2.2 accessibility auditing and enforcement. 2 skills, 5 agents, 1 command.

- **wcag-audit-patterns** -- Automated and manual accessibility auditing for Live Wires, Go+Templ+Datastar, and Craft CMS
- **screen-reader-testing** -- VoiceOver, NVDA, and JAWS testing protocols with manual verification checklists
- **a11y-html-reviewer** (agent) -- Reviews HTML, Templ, and Twig templates for WCAG violations
- **a11y-css-reviewer** (agent) -- Reviews CSS for visual accessibility compliance
- **a11y-dynamic-content-reviewer** (agent) -- Reviews Datastar interactions and DOM updates for a11y
- **a11y-audit-runner** (agent) -- Runs automated audits using Pa11y, axe-core, and Playwright
- **a11y-project-setup** (agent) -- Sets up accessibility testing infrastructure
- `/a11y-audit` -- Run automated accessibility audit on a page or template

### dm-review

Code review orchestrator with parallel agents. 2 skills, 12 agents, 5 commands.

- **review** -- Single-command reviews launching up to 15 parallel agents tailored to Go+Templ+Datastar, Craft CMS, and Live Wires with issue tracking
- **visual-test** -- Standalone visual browser testing for rendered pages using Playwright
- 7 review agents: security-auditor, architecture-reviewer, code-simplicity-reviewer, pattern-recognition-specialist, doc-sync-reviewer, go-build-verifier, craft-reviewer, test-coverage-reviewer, visual-browser-tester, ux-quality-reviewer
- 2 workflow agents: review-consolidator, review-memory-recorder
- `/dm-review` -- Full review with all applicable agents
- `/dm-review-quick` -- Quick review with 5 core agents only
- `/dm-review-fix` -- Resolve pending review findings from todos/
- `/dm-review-visual` -- Visual browser testing on rendered pages
- `/dm-review-loop` -- Review-fix convergence loop until zero findings

### the-local

Self-hosted Matrix network for the workplace democracy movement. 3 skills, 3 commands.

- **element-branding** -- Element Web custom CSS injection, welcome page customization, auth page styling
- **synapse-config** -- Synapse homeserver configuration, email setup via Resend SMTP, Jinja2 template system
- **server-ops** -- Docker Compose service management, SSH access, user creation, backups, deployment
- `/create-user` -- Create a new Matrix user account
- `/deploy` -- Deploy changed files to production
- `/logs` -- Tail Docker Compose logs for services

### chef

Science-driven cooking assistant with dietary analysis. 1 skill, 1 agent, 4 commands.

- **cooking** -- Recipes, dietary analysis (Eve Persak framework), Mela integration, Bali ingredient sourcing, food science
- **recipe-analyzer** (agent) -- Analyzes recipes against the dietary framework
- `/recipe-check` -- Analyze a recipe against dietary guidelines
- `/recipe-convert` -- Convert a recipe to a healthy, Bali-friendly version
- `/meal-plan` -- Generate a meal plan following Eve Persak's timing framework
- `/shop` -- Build a shopping list organized by Bali store

### pipeline

Autonomous feature development pipeline. 3 skills, 2 agents, 4 commands.

- **assess** -- Pre-plan assessment of current codebase state and UX before planning changes
- **research** -- Multi-source context gathering from ai-memory, RAG, web search, and domain plugins
- **promptcraft** -- Generates self-contained execution prompts with overlap-aware dependency ordering
- **plan-adversary** (agent) -- Adversarial review of plans and prompts, iterating to convergence
- **execution-orchestrator** (agent) -- Autonomous worktree execution with review-fix loops and zero-deferral policy
- `/pipeline` -- Full autonomous pipeline: assess, research, plan, prompt, review, execute, deliver
- `/pipeline-assess` -- Pre-plan assessment of current state
- `/pipeline-prompts` -- Generate execution prompts from an existing plan
- `/pipeline-run` -- Execute prompts in worktrees with review-fix loops

### gemini

Gemini CLI delegation for grounded research, large-context diff analysis, and code execution. 1 skill, 3 agents, 2 commands.

- **gemini-delegate** -- Delegates web-grounded search, 2M-context diff analysis, and sandboxed code execution to Gemini
- **gemini-search-grounded** (agent) -- Runs search-grounded research with cited sources
- **gemini-code-executor** (agent) -- Verifies algorithms and data transformations in Gemini's execution sandbox
- **gemini-diff-analyst** (agent) -- Reviews large diffs that exceed normal truncation limits
- `/gemini` -- Delegate a task to Gemini CLI
- `/gemini-search` -- Run search-grounded Gemini research

### deepseek

DeepSeek V4 delegation for lower-cost code review and bulk diff analysis. 1 skill, 3 agents, 1 command.

- **deepseek-delegate** -- Delegates code analysis and review work to DeepSeek V4-Pro/V4-Flash with fallback handling
- **deepseek-bulk-analyst** (agent) -- Reviews large diffs with DeepSeek's long context
- **deepseek-code-analyst** (agent) -- Performs focused code analysis and refactoring review
- **deepseek-agent-runner** (agent) -- Runs dm-review mechanical agents through DeepSeek-compatible prompts
- `/deepseek` -- Delegate a task to DeepSeek

## Orchestration

Plugins compose through five patterns:

1. **Companion Skill Loading** -- A command loads skills from other plugins at specific workflow phases
2. **Multi-Agent Dispatch** -- A skill launches agents in parallel and consolidates results
3. **Memory-Mediated Coordination** -- Plugins write to ai-memory entities that other plugins read later
4. **Pipeline Orchestration** -- A conductor plugin composes all three patterns into an autonomous workflow with review-fix loops
5. **CLI-Mediated Model Delegation** -- A plugin invokes an external model CLI/API and returns structured findings to the calling workflow

See [docs/orchestration-patterns.md](docs/orchestration-patterns.md) for details.

## Validation

```shell
./tools/validate-composition.sh --all    # run all validators
./tools/validate-dual-compat.sh          # check Claude/Codex manifest sync and cache fallbacks
./tools/eval-descriptions.sh             # run description trigger evals
./tools/check-dependencies.sh            # check plugin dependencies
```

## License

MIT
