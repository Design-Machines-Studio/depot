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
  widget-scripts.js       # copy-back JS — INLINE into {{WIDGET_SCRIPTS}}
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
3. **Add widgets where needed.** Splice `decision-table.html` (rows filled) into
   the section's editable areas. Add `mockup-frame.html` / `diagram-mermaid.html`
   as needed. If any decision-table is present, inline `widget-scripts.js` into
   `{{WIDGET_SCRIPTS}}` inside a single `<script defer> ... </script>`.
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

`{{SIBLING_NAV}}` is a `<ul>` of links to the run's other artifacts
(`assessment.html`, `research.html`, and `prompts/` for a plan) — relative links
within the same `plans/<feature-slug>/` directory.

## Data island schemas

The per-artifact island schemas (`assessment`, `research`, `brainstorm`, `plan`
feature + epic variants) are defined canonically in **`docs/html-artifacts.md`
§Data-island schema** (repo root). It is the single source of truth — do not
duplicate the field list here; link to it so the two cannot drift.

`keyRequirements` in `assessment.html` is the cached Key Requirements source the
pipeline re-reads in Phases 3/4/7. `chunks[].n` + `chunks[].slug` map 1:1 onto
`prompts/NN-<slug>.md` (the assembly-baseplate chunk-prompt convention).

## Reading the island downstream

```bash
bash "${CLAUDE_PLUGIN_ROOT}/plugins/pipeline/skills/promptcraft/references/templates/extract-json-island.sh" \
  plans/<slug>/plan.html | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["chunks"]))'
```

## Copy-back round-trip

Decision tables render with `contenteditable` cells and a **Copy table as JSON**
button. The human edits decisions in the browser, clicks Copy (serializes the
table to island-shaped JSON on the clipboard), and pastes it back to Claude or
into the artifact's `#pipeline-data` island. Each editable section sets
`data-island-key="<key>"` and each `<th data-field="...">` names the JSON key; a
`data-list="true"` header serializes its column as an array.

## Plans directory convention (assembly-baseplate)

Artifacts live in flat sibling feature dirs under `plans/`:
`plans/<feature-slug>/{assessment,research,brainstorm,plan}.html` alongside
`prompts/NN-<slug>.md`, `manifest.json`, `original-prompt.md`, and evidence dirs.
A high-level/epic plan is its own dir whose `prompts/<major>.<minor>-<slug>.md`
seed sibling feature dirs; its `plan.html` uses the epic variant (`subPlans`).
