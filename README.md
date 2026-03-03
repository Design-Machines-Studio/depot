# depot

DM-013/WORKS — Design Machines' AI plugin marketplace for Claude Code.

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
```

## Plugins

### ned

Personal knowledge graph and session capture. Provides two skills and one command:

- **ai-memory** — Interface to the ai-memory knowledge graph
- **recorder** — Captures conversation sessions into structured summaries, pushes to ai-memory and Notion
- `/capture` — Quick observation capture to ai-memory

### craft-developer

Craft CMS development expertise covering Craft 4 and 5. Provides four skills:

- **craft-development** — Element queries, Matrix fields, GraphQL, eager loading, debugging patterns, and a 30+ query cookbook
- **content-modeling** — Three-layer content modeling methodology with Matrix patterns and CKEditor configuration
- **craft-5-migration** — Craft 4 to 5 migration patterns, breaking changes, and upgrade checklists
- **craft-mcp** — Craft CMS MCP server integration for AI-assisted workflows

### project-manager

Project management based on Louder Than Ten (LT10) principles. Provides two skills:

- **lt10** — Estimation (90th percentile), scoping, pricing, scheduling, risk management, stakeholder alignment, and communication scripts
- **planner** — Notion-integrated sprint planning, time tracking, and session workflows

### council

Worker cooperative governance and decolonial content strategy. Provides two skills and one command:

- **governance** — BC Cooperative Association Act compliance, bylaw analysis, discovery processes, Co-op OS system design, voting thresholds, and financial governance
- **decolonial-language** — Decolonial and anti-capitalist content strategy with terminology mappings between legal/regulatory language and solidarity economy alternatives
- `/governance-check` — Quick cooperative compliance status check

### design-machines

Design Machines OÜ business intelligence. Provides:

- **strategy** — Product positioning, catalog system, Assembly architecture, partnerships, revenue model, brand language, and go-to-market strategy

### assembly

Assembly governance application development. Provides:

- **development** — Docker-based Go development with Templ templates, Datastar reactivity, page-type workflows, component library, database patterns, and governance state machines
- `/assembly-build` — Build and test Assembly via Docker

### live-wires

Live Wires CSS framework for editorial websites. Provides:

- **livewires** — Layout primitives (stack, grid, cluster, sidebar, cover, reel), baseline rhythm system, design tokens, utility classes, theming, and QA testing patterns

### ghostwriter

Travis Gertz's personal writing voice and editorial style engine. Provides:

- **voice** — Writing style profile covering tone, sentence rhythm, argumentation structure, vocabulary, cultural references, anti-AI-writing patterns, and context-aware register switching
- **social-media** — Platform-native social media content for LinkedIn, Instagram, Bluesky, and Mastodon
- **voice-editor** (agent) — Reviews and edits content to match Travis's voice
- `/voice-check` — Quick text check against Travis's writing voice

### design-practice

Design philosophy rooted in modernist masters and editorial tradition. Provides four skills:

- **typography** — Typographic principles from Müller-Brockmann, Gerstner, Bringhurst, and others. Modular scales, vertical rhythm, typeface selection, and evaluation frameworks
- **layout** — Editorial layout and art direction. Grid systems, visual hierarchy, pacing, and cross-media design
- **dataviz** — Data visualization from Tufte, Wong, and Franchi. Chart type selection, data-ink ratio, graphical integrity, and editorial integration
- **identity** — Identity and logo design from Rand, Bass, Draplin, Wyman, and Glaser. Bold simplicity, systematic extensibility, and the ten-point evaluation framework
- **design-critic** (agent) — Evaluates design work against the combined framework
- **design-advisor** (agent) — Helps with design decisions and provides strategic direction

### project-scaffolder

Claude Code project infrastructure scaffolding. Provides:

- **scaffolding** — Generates hooks, agents, settings.json, and CLAUDE.md templates for Go+Templ+Datastar, Go library, CSS framework, and Craft CMS projects

### accessibility-compliance

WCAG 2.2 accessibility auditing and enforcement. Provides two skills and one command:

- **wcag-audit-patterns** — Automated and manual accessibility auditing for Live Wires, Go+Templ+Datastar, and Craft CMS projects
- **screen-reader-testing** — VoiceOver, NVDA, and JAWS testing protocols with manual verification checklists
- `/a11y-audit` — Quick automated accessibility audit on a page or template

### dm-review

Code review orchestrator that runs parallel agents across accessibility, security, architecture, CSS, voice, and governance. Provides:

- **review** — Single-command reviews launching up to 14 parallel agents tailored to Go+Templ+Datastar, Craft CMS, and Live Wires projects with issue tracking (text files or GitHub Issues)
- `/dm-review-fix` — Resolve pending review findings from todos/
