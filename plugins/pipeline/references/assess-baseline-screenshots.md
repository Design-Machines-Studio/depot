# Baseline screenshot persistence

Loaded by the assess phase only when the project has a rendered surface and a
reachable dev server, so baseline screenshots can actually be captured. An
assessment with no rendered surface never loads this file.

#### Baseline Screenshot Persistence

Save all screenshots taken during the UX assessment to disk for later comparison:

1. Create directory: `plans/<feature-slug>/baselines/`
2. Save each screenshot with a descriptive name: `baselines/<route-slug>-<viewport>.png`
   - Example: `baselines/governance-proposals-desktop-1440.png`
   - Example: `baselines/governance-proposals-mobile-375.png`
3. Record the screenshot manifest in the Assessment Brief under a `## Baseline Screenshots` section listing every saved file and its route/viewport.

These baselines serve as the "before" state for visual diff comparisons after implementation. The execution-orchestrator's visual verification protocol compares post-implementation screenshots against these baselines to detect regressions. Expected changes (the feature being built) are fine; unexpected visual differences are findings.

Baseline screenshots are Tier 1 (ephemeral) artifacts per the artifact lifecycle policy (`${CLAUDE_PLUGIN_ROOT}/plugins/pipeline/references/artifact-lifecycle.md`). They are auto-deleted by the execution-orchestrator's cleanup phase (Step 5b). Gitignore enforcement in Step 0d ensures they are never tracked by git.
