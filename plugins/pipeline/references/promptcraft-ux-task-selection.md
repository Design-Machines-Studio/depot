# UX task selection gate

Loaded by promptcraft Phase 3j only when the target repo contains `tests/ux/`
and at least one chunk is `renderedSurface: required`. A repo with no `tests/ux/`
directory, or a plan with no rendered surface, never loads this file.

### Phase 3j: UX Task Selection Gate

When the target repo contains `tests/ux/`, reference persona tasks in prompts whose `renderedSurface` is `required`: each rendered-surface chunk's Research Context must name which persona tasks cover the affected routes, and if no task file exists for a new route, add the acceptance criterion "Create task file at `tests/ux/tasks/{area}/{task-name}.md`."

Use `plugins/workflow-kernel/skills/workflow-kernel/references/verification-contract.md`.
Carry the complete selected persona/scenario/route/browser/viewport case set into
acceptance criteria for chunks with `renderedSurface: required`. Task frontmatter is authoritative; do
not turn the generated coverage matrix or a fixed persona sample into coverage.
Required browser criteria must preserve the evidence -> primary process quit ->
fresh primary relaunch/retry -> different engine -> `human_help_required` ladder.
Curl/reachability never satisfies browser evidence.
