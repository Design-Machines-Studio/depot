# HTML Artifacts for the Pipeline Planning Phase

The pipeline's four planning-phase artifacts — `brainstorm`, `assessment`,
`research`, `plan` — are emitted as **self-contained HTML carrying a JSON data
island**, not markdown. This document explains why, the template architecture,
the data-island schema, the editable copy-back loop, the host-CSS detection
ladder, and what stays out of HTML.

## Why HTML

As Opus runs grew to hours, plans ballooned to ~1000 lines of markdown and humans
stopped reading them. A plan you don't read is a plan you don't steer. HTML is a
richer review medium — inline mockups, rendered diagrams, editable decision
tables — so the human actually engages with the spec. A good spec decides where
the multi-hour, multi-dollar autonomous run spends its effort: you're a compute
allocator now, and the planning artifact is the allocation.

The catch: `plan`, `assessment`, and `brainstorm` are not purely human-facing.
They are also the inter-agent handoff medium (promptcraft parses the plan,
plan-adversary reviews it, the orchestrator reads the brainstorm). So each
dual-purpose artifact is **one HTML file** that carries both halves: human-
readable prose/widgets, plus a machine-readable `<script type="application/json"
id="pipeline-data">` island. No dual emission, no drift. Agents read the island;
humans read the page.

## Scope

| Artifact | Format | Path |
|---|---|---|
| `brainstorm` | HTML + island | `plans/<slug>/brainstorm.html` |
| `assessment` | HTML + island | `plans/<slug>/assessment.html` |
| `research` | HTML + island | `plans/<slug>/research.html` |
| `plan` | HTML + island | `plans/<slug>/plan.html` |
| dm-review report · pipeline receipt · delivery report | **inline / markdown (unchanged)** | — |
| `original-prompt.md` · `prompts/NN-*.md` · `manifest.json` · crosscheck · facets · state files | **markdown / JSON (unchanged)** | — |

Terminal status reports stay inline because HTML buys nothing for a one-shot
summary that is read once and discarded. Agent-only handoffs stay markdown/JSON
because no human reviews them in a browser.

## Template architecture

Templates live in `plugins/pipeline/skills/promptcraft/references/templates/`:

```
base.html                 # shell: head, host-CSS slot, landmarks, dark/print CSS
sections/{assessment,research,brainstorm,plan}.html
widgets/decision-table.html · widget-scripts.js · mockup-frame.html · diagram-mermaid.html
data-island.html · baseline.css
detect-host-css.sh · extract-json-island.sh · README.md
```

An emitting agent: (1) runs `detect-host-css.sh` to resolve the host stylesheet,
(2) fills `sections/<kind>.html`, (3) splices in widgets and inlines
`widget-scripts.js` when a decision-table is present, (4) builds the island from
`data-island.html`, (5) substitutes `base.html`'s slots and writes the file. No
build step. Full assembly recipe and slot list: `templates/README.md`.

`base.html` accessibility baseline: `<header>/<nav>/<main>/<footer>` landmarks,
skip-link first, `<meta name="color-scheme" content="light dark">`, a
`prefers-color-scheme: dark` fallback, and a print stylesheet that hides nav and
the copy buttons. Only `<script defer>` is used.

## Data-island schema

```jsonc
// assessment.html — keyRequirements IS the cached requirements source
{ "artifact": "assessment", "slug": "<slug>",
  "keyRequirements": ["..."], "testPersonas": [{"name","id","role","useFor"}],
  "recentLessons": ["..."], "baselineScreenshots": [{"route","viewport","path"}] }

// research.html — synthesized brief; facet files stay markdown
{ "artifact": "research", "slug": "<slug>",
  "findings": ["..."], "references": [{"title","url|path","source"}] }

// brainstorm.html — what promptcraft Phase 2.5 + the orchestrator extract
{ "artifact": "brainstorm", "slug": "<slug>",
  "visualDecisions": [{"area","decision","variant|token|treatment","rationale"}] }

// plan.html (feature) — chunks map 1:1 to prompts/NN-<slug>.md
{ "artifact": "plan", "slug": "<slug>",
  "chunks": [{"n":"01","slug":"reader-service","scope","acceptance","deps":[]}],
  "decisions": [{"id","decision","rationale","alternatives"}],
  "requirementsCoverage": [{"requirement","chunk"}] }

// plan.html (epic / high-level) — enumerates sibling sub-plans
{ "artifact": "plan", "slug": "<slug>",
  "subPlans": [{"n","slug","featureDir"}], "decisions": [...], "requirementsCoverage": [...] }
```

Never copy raw secrets (bearer tokens, session values) into `testPersonas` —
record field names only (see the assess skill's Fixture Discovery redaction note).

Downstream agents read the island instead of grepping prose:

```bash
bash plugins/pipeline/skills/promptcraft/references/templates/extract-json-island.sh \
  plans/<slug>/plan.html | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["chunks"]))'
```

## Editable copy-back loop

Decision tables render with `contenteditable` cells and a **Copy table as JSON**
button. The reviewer edits decisions in the browser, clicks Copy (the table
serializes to island-shaped JSON on the clipboard), and pastes it back to Claude
or into the artifact's `#pipeline-data` island. Each editable section sets
`data-island-key="<key>"`; each `<th data-field="...">` names the JSON key, and a
`data-list="true"` header serializes its column as an array. The serializer lives
once in `widgets/widget-scripts.js`.

## Host-CSS detection ladder

`detect-host-css.sh` (run from the target project root) prints either a complete
`<link rel="stylesheet">` or the literal `FALLBACK`. First match wins:

1. `.dm-review-css` override file (single-line path) → verbatim
2. Assembly: `go.mod` + `internal/assets/css/` → `/static/css/assembly.css`
3. Live Wires: `package.json` `livewires` dep OR `src/css/0_settings/` → `/dist/livewires.css` (override via `livewires.config.json` `cssPath`)
4. Tailwind: `tailwind.config.*` + `dist/output.css` → `/dist/output.css`
5. Craft: `config/general.php` → `/css/site.css`
6. else → `FALLBACK` (caller inlines `baseline.css` into a `<style>` block)

## Plans directory convention

Artifacts live in flat sibling **feature dirs** under `plans/` (the
assembly-baseplate convention): `plans/<feature-slug>/{assessment,research,
brainstorm,plan}.html` alongside `prompts/NN-<slug>.md`, `manifest.json`,
`original-prompt.md`, and the `baselines/` / `prototype-evidence/` dirs. A
**high-level/epic plan** is its own dir whose `prompts/<major>.<minor>-<slug>.md`
seed sibling feature dirs; its `plan.html` uses the epic variant (`subPlans`).
The pipeline does not auto-generate the epic→sub-plan tree — that orchestration
stays a manual workflow layer; `plan.html` is merely layout-aware (it links
siblings and maps chunks to `prompts/NN-*.md`).

## Validation

`./tools/validate-composition.sh` runs `validate_html_templates()`: `base.html`
has every `{{...}}` slot, fragments have balanced comments/script tags, sections
reference their island, and the two helpers are executable + `bash -n` clean.
(We deliberately avoid `xmllint --html` — libxml2's HTML4 parser emits false
errors on HTML5 semantic elements while still exiting 0.)

## Notion sync

Notion renders raw HTML as text, so the canonical artifact stays in-repo. When
syncing a pipeline run to the depot manual or ops dashboard, upload screenshots
of the rendered HTML and/or a short markdown summary — do not paste the HTML
source.
