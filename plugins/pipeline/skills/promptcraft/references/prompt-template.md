# Execution Prompt Template

Each generated prompt follows this structure. The goal is a self-contained document that a subagent can execute without needing to read the plan, research brief, or any external context.

## Template

```markdown
# Chunk: [Chunk Title]

## Context

[Keep this compact and chunk-specific. State:
- the larger approved project goal this chunk serves;
- why this chunk exists now;
- the approved requirement or project outcome it addresses; and
- the relevant non-goals and ownership boundary.

Do not paste the full roadmap, assessment, research brief, or Project snapshot.]

## Task

[Clear, imperative description of what to build or change. Be specific -- "Add a new handler for POST /api/proposals" not "implement the proposals API."]

## Files to Modify

| File | Action | Notes |
|------|--------|-------|
| path/to/file.go | Create | New handler file |
| path/to/existing.go | Modify | Add new route registration |
| path/to/template.templ | Create | New page template |

## Files to Read (for context)

| File | Why |
|------|-----|
| path/to/similar.go | Follow this handler's pattern |
| path/to/types.go | DTO definitions to reuse |

[For a declared prototype counterpart, list every relevant prototype template
or component here with its canonical repository and exact commit. Paths may be
resolved in a temporary/available checkout, but never hardcode a permanent
workstation path.]

## Patterns to Follow

[Specific patterns extracted from the assessment. Include actual code snippets where helpful.]

- Handler pattern: [describe or show example]
- Error handling: [describe convention]
- Naming: [describe convention]
- Assembly mutation pattern (when targeting Assembly): consult `assembly:development`'s Mutation Applicability Matrix; include only controls justified by the present behavior, with required events after commit

## Browser Review Target (rendered work only)

[Resolve from current project context and root instructions using dm-review's
`repository-browser-target-discovery.md`: established project code/domain,
canonical serving repo folder, feature branch and source head, existing
build/restart command, and checkout ownership. For selected Assembly development
checkouts, commit/push and verify the head, normally detach only the owned
producer worktree, then select the branch before required browser capture.
Retain producer checkout/state and unfinished evidence until complete
preservation permits publication and destructive cleanup. Foreign occupancy blocks until that owner's exact handoff; never
detach/remove a foreign owner. Other repositories select the feature branch normally.
Review through the existing domain; do not create
a harness or reconfigure the environment. Name concrete exceptions such as
simultaneous Federation peers. Record the prototype target for comparison.
Omit for non-rendered work.]

Host owns browser evidence; `renderedSurface: required` does not add `browser`.

## Companion Skills

Load these skills for domain-specific guidance:
- [skill name] from [plugin] -- [what it helps with]

## Visual References (UI chunks only)

[If the brainstorm or design spec produced visual mockups, summarize the key decisions here. Omit this section entirely for non-UI chunks.]

Approved design: [path to brainstorm.html or mockup file]

Prototype authority (when applicable):
- Repository + exact commit: [canonical identity @ commit]
- Authority source: [user, Issue/PR, root instructions, plan, or Assembly skill]
- Prototype -> target cases: [route, state, viewport pairs]
- Relevant source: [templates/components, Datastar bindings, handlers/client code,
  concise structural excerpts and exact Live Wires classes]
- Interaction trace: [event -> request/timing -> save response -> feedback ->
  reload persistence; approved stub behavior identified]
- Existing UX tasks/personas: [exact source commit and task/profile paths from
  dm-review’s `ui-case-selection.md`; task IDs, persona/role/state/device,
  preconditions, steps, success criteria and screenshot points]
- Cross-app mapping: [prototype/application routes, demo accounts, permissions,
  initial data and record IDs; preserve scenario and authorization]
- Paired results: [prototype result, application result, observed difference;
  save/autosave, reload/revisit, validation, cancel, keyboard/focus as applicable]
- Intentional differences: [approved production constraints and stale task/source conflicts]

Key visual decisions:
- [Decision 1: e.g., "Sidebar headings use h4 with font-medium, not h3"]
- [Decision 2: e.g., "Block/Abstain buttons use button--outline-danger, visually smaller than position buttons"]
- [Decision 3: e.g., "Natural-width buttons, not full-width"]

The rendered result must match these visual treatments. If you cannot determine the visual intent from these descriptions, read the mockup file at the path above.

Prototype-covered choices are primary: inspect exact source, search existing
target/Live Wires components, then preserve hierarchy/classes/shared components,
copy/save behavior/action order/control placement unless approval names divergence.
Generic SaaS heuristics cannot redesign a settled prototype choice.

## Acceptance Criteria

- [ ] [Specific, testable structural criterion]
- [ ] [Another structural criterion]
- [ ] [Build/compile passes]
- [ ] [Tests pass (if applicable)]

### Visual Acceptance Criteria (UI chunks only)

[Omit this subsection for non-UI chunks.]

- [ ] [Visual outcome criterion -- describes what it should LOOK like, not just what class to use]
- [ ] [E.g., "Block and Abstain buttons are visually lighter and smaller than position buttons"]
- [ ] [E.g., "Sidebar headings create a clear hierarchy -- h4 muted style, not competing with page heading"]

Pair structural criteria (classes/components) with rendered impressions
(hierarchy/prominence); neither proves the other.

For a declared prototype counterpart, include both kinds of parity proof:

- [ ] Source comparison confirms the significant semantic/wrapper hierarchy,
  component calls, exact Live Wires class strings, visible copy/metadata, and
  action order, with every intentional difference named and justified.
- [ ] Browser comparison covers prototype and target at matching routes,
  states, and viewports with screenshots plus targeted DOM/accessibility/class
  and computed layout evidence. Do not require global DOM, pixel, theme-token,
  or exact-color equality.
- [ ] Perform affected interactions in both apps using designated demo records:
  change, save/autosave at the same trigger, observe feedback/errors, then
  reload/revisit. Include affected cancel/focus behavior. A click or screenshot
  alone does not prove saving; distinguish prototype stubs from durable storage.
- [ ] If the prototype render is unavailable after browser recovery, preserve
  source work and return `human_help_required`; do not claim rendered parity.

## Tool-Call Exploration Checkpoint & Delivery Contract

Treat approximately 40 tool calls as an exploration checkpoint.
- At that point, stop new research, broad exploration, speculative refactoring, scope expansion, and unrelated improvements.
- Closeout remains allowed: inspect the current diff and status; run proportionate focused verification; perform targeted repairs; commit coherent work; push the candidate branch when authorized; return evidence and final report.
- Only the root publication seam creates/readies PRs after independent candidate review and producer coverage; workers never publish.
- After at most two targeted repair-and-recheck cycles, report remaining failures and preserve recoverable work. Incomplete coverage blocks publication.
- Reaching the exploration checkpoint is never, by itself, a valid reason to leave implemented work unverified, uncommitted, unpushed, or unreported.
- End with `NOT-COVERED:` and `COMMANDS-RUN:` listing unreached work and actual commands.

## Automatic review closeout

Apply `automatic-implementation-closeout.md`: approve plan/prompts; implement;
commit/push; independently review/repair/recheck and preserve source/browser;
owner publishes via `publish-reviewed-pr.sh` after mandatory caller checks.
Workers return evidence, never publish or start another loop. Exact SessionStart
ref is read-only; never bind/update/clear parent context. Playwright checks,
T3 handoff. Draft waits for final-head CI/feedback/designer UI acceptance.
dm-review's designer handoff never requests backend review/create-PR approval.
`noMergeOnCompletion=true`; absent/false legacy values grant no merge.
Preserve planning/material-scope approval.

## Ambiguity Protocol

Keep this invariant aligned with `plan-adversary.md` scope review and the
orchestrator's autonomous fallback. Never choose silently between reasonable
Task/AC interpretations:

- Before edits, list interpretations, choose the smallest adequate one and why.
- In autonomous mode, commit separate `Chose: <interpretation>` and
  `Rejected: <alt-1>; <alt-2>` trailers using `git interpret-trailers` syntax.
- Receipt `ambiguity_resolved: true` with a short summary for later review.
- Fabricating certainty is P1; surfacing ambiguity is never penalized.

## Constraints

- Modify only listed files and AC-serving lines, following existing patterns.
  No new abstractions or unrelated refactoring. Report other issues as
  "Noted, not fixed" outside the diff.
- Every changed line must serve an approved requirement or project outcome from
  Context. Keep adjacent improvements and work owned by another repository out
  of the diff; report them as "Noted, not fixed."
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- For a declared prototype counterpart, inspect the exact prototype source
  before editing and compare both source and matched renders after editing.
  Required functionality, authorization, accessibility, public APIs,
  production data, and Baseplate/Fixture boundaries override imitation and
  must be recorded as intentional differences.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.
- When this chunk actually changes authentication, middleware, an Authorizer action/resource, a privileged read/write, a role/member/account/install/module permission, or a privileged UI capability in Assembly code, the final acceptance criterion must include an Auth Boundary Map receipt covering: surfaces mapped, middleware gates, Authorizer action/resource pairs, default-deny UI capabilities, stale-session/operator/install edge cases, test coverage, and residual risk. A matching path name is a review hint, not proof of a boundary change.
- [Any additional constraints specific to this chunk]

## Research Context

[Relevant findings from the research brief, inlined here. Only include what's directly relevant to this chunk.]
```

## Guidelines for Writing Prompts

Inline task-relevant context and actual pattern snippets; use exact files and
verifiable acceptance criteria. Explain why, scope ownership tightly and cite
approved mockup paths/key decisions. Pair structural criteria (class/component)
with visual impressions (hierarchy/prominence); one never proves the other.
Source inspection remains useful when images cannot be viewed.


9. **The Tool-Call Exploration Checkpoint, Ambiguity Protocol and last two
Constraints bullets are invariant:** copy verbatim into every prompt. They
bound exploration without blocking verification/delivery, require honest
`NOT-COVERED:` / `COMMANDS-RUN:` and expose implementation ambiguity between
adversarial planning and brainstorming. Never shorten them per chunk.
