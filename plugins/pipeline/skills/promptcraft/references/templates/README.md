# Pipeline HTML Artifact Templates

Self-contained HTML templates for the four pipeline **planning-phase** artifacts:
`assessment`, `research`, `brainstorm`, `plan`. Each rendered file is human-facing
prose plus a machine-readable JSON **data island** that downstream agents read
instead of grepping markdown. Terminal status reports (dm-review reports, pipeline
receipts, delivery reports) stay inline/markdown and are **not** templated here.

See `docs/html-artifacts.md` (repo root) for the full rationale and schema.

## Files

```
base.html                 # shell: head, host-CSS slot, landmarks, dark/print CSS
sections/                 # one body per artifact kind
  assessment.html  research.html  brainstorm.html  plan.html
widgets/
  decision-table.html     # editable table fragment
  widget-scripts.js       # copy-back JS -- INLINE into {{WIDGET_SCRIPTS}}
  mockup-frame.html       # sandboxed iframe mockup
  diagram-mermaid.html    # Mermaid diagram (+ CDN script note)
data-island.html          # <script type="application/json"> snippet
baseline.css              # inlined when no host CSS detected
detect-host-css.sh        # prints a <link> tag or FALLBACK
extract-json-island.sh    # prints an artifact's island JSON
```

## How an agent assembles an artifact

1. **Detect host CSS** from the target project root:
   ```bash
   HOST_CSS_LINK=$(bash "${CLAUDE_PLUGIN_ROOT}/plugins/pipeline/skills/promptcraft/references/templates/detect-host-css.sh" 2>/dev/null || echo "FALLBACK")
   ```
   If the output is `FALLBACK`, set the `{{HOST_CSS_HREF}}` substitution to
   `<style>` + the contents of `baseline.css` + `</style>`. Otherwise use the
   emitted `<link>` tag verbatim.
2. **Fill the section.** Take `sections/<kind>.html` and replace its `{{...}}`
   content slots with rendered HTML.
   - For a **full-mode plan**, set `EXECUTION_SCOPE_HEADING` to `Chunk
     Decomposition`. Set `EXECUTION_SCOPE_BODY` to an editable
     `data-island-key="chunks"` wrapper containing the chunk table and the note
     that each row becomes `prompts/NN-<slug>.md`.
   - For a **Lean-mode plan**, set `EXECUTION_SCOPE_HEADING` to `Single-pass
     Execution Scope`. Set `EXECUTION_SCOPE_BODY` to the reviewed single-pass
     scope and verification criteria as rendered prose. Do not emit a chunk
     table, a `data-island-key="chunks"` wrapper, or any prompt-file link.
3. **Add widgets and visuals where needed.** Splice `decision-table.html` (rows
   filled) into the section's editable areas. Add `mockup-frame.html` /
   `diagram-mermaid.html` as needed. If any decision-table is present, inline
   `widget-scripts.js` into `{{WIDGET_SCRIPTS}}` inside a single
   `<script defer> ... </script>`.
   - **Render evidence as images, not filenames.** Baseline screenshots,
     mockups, and any captured PNGs go in an `<img>` gallery, never a text list
     of paths. The whole reason these artifacts are HTML is so the human SEES
     the visuals inline. Use `<div class="grid" style="--grid-min: 22rem;">` of
     `<figure class="stack">` blocks with `<a href="..."><img src="..."
     alt="..." loading="lazy"></a>` + `<figcaption>`. Image `src` is relative to
     the artifact file (e.g. `baselines/dashboard-desktop-1440.png`).
   - **Lay out with host primitives, not invented classes.** The emitted markup
     uses Live Wires primitives the host stylesheet already defines: `.center`
     (measure), `.stack` (vertical rhythm), `.grid` (galleries/cards), `.cluster`
     (inline groups). `<main>` carries `class="artifact-main center stack"` and
     `<body>` carries a `scheme-*` class (default `scheme-subtle`) so the linked
     host CSS themes the doc. baseline.css ships minimal fallbacks for the
     FALLBACK case.
4. **Build the island.** Fill `data-island.html`'s `{{ISLAND_JSON}}` with the
   artifact's schema object (see below), then place it in `{{DATA_ISLAND}}`.
5. **Substitute base.html** slots and `Write` the final file to
   `plans/<feature-slug>/<kind>.html`.

> Assembly is mechanical string substitution of the `{{SLOT}}` tokens. Template
> documentation comments deliberately refer to slots by **bare name** (e.g.
> `BODY`, not `{{BODY}}`) so a naive global replace can't corrupt the notes or
> emit a duplicate data island. You may strip the `<!-- ... -->` comments from
> the final artifact, but it isn't required.

### base.html slots

`{{TITLE}}` `{{ARTIFACT_KIND}}` `{{GENERATED_AT}}` `{{HOST_CSS_HREF}}`
`{{SIBLING_NAV}}` `{{BODY}}` `{{WIDGET_SCRIPTS}}` `{{DATA_ISLAND}}`

`{{SIBLING_NAV}}` is a `<ul>` of relative links within the same
`plans/<feature-slug>/` directory. A full-mode plan links `assessment.html`,
`research.html`, and `prompts/`. A Lean-mode plan links `assessment.html` and
`research.html` only; it MUST NOT link `prompts/` or `manifest.json`, because
those artifacts do not exist in Lean mode.

## Data island schemas

The per-artifact island schemas (`assessment`, `research`, `brainstorm`, `plan`
feature + epic variants) are defined canonically in **`docs/html-artifacts.md`
§Data-island schema** (repo root). It is the single source of truth -- do not
duplicate the field list here; link to it so the two cannot drift.

`keyRequirements` in `assessment.html` becomes the cached authoritative source
only after the combined discovery response is persisted and verified. The
compact Project Alignment record stays in the existing rendered assessment
prose rather than creating a second island schema. Pipeline re-reads the
approved requirements in Phases 3/4/7. In full mode, `chunks[].n` +
`chunks[].slug` map 1:1 onto `prompts/NN-<slug>.md` (the assembly-baseplate
chunk-prompt convention). In Lean mode, `chunks` is absent and each
`requirementsCoverage` entry maps its requirement to `single-pass scope`.

## Reading the island downstream

```bash
bash "${CLAUDE_PLUGIN_ROOT}/plugins/pipeline/skills/promptcraft/references/templates/extract-json-island.sh" \
  plans/<slug>/plan.html | python3 -c 'import json,sys; print(json.load(sys.stdin)["artifact"])'
```

## Copy-back round-trip

Decision tables render with `contenteditable` cells and a **Copy table as JSON**
button. The human edits decisions in the browser, clicks Copy (serializes the
table to island-shaped JSON on the clipboard), and pastes it back to Claude or
into the artifact's `#pipeline-data` island. Each editable section sets
`data-island-key="<key>"` and each `<th data-field="...">` names the JSON key; a
`data-list="true"` header serializes its column as an array.

## Plans directory convention (assembly-baseplate)

Artifacts live in flat sibling feature dirs under `plans/`. Both modes contain
`plans/<feature-slug>/{assessment,research,brainstorm,plan}.html`,
`original-prompt.md`, and applicable evidence directories. Full mode also
contains `prompts/NN-<slug>.md` and `manifest.json`; Lean mode deliberately
contains neither.
A high-level/epic plan is its own dir whose `prompts/<major>.<minor>-<slug>.md`
seed sibling feature dirs; its `plan.html` uses the epic variant (`subPlans`).
