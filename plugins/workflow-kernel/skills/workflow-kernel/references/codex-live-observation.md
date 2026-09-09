# Codex live observation

This adapter targets Codex CLI 0.153.4. It uses the
[official hook contract](https://learn.chatgpt.com/docs/hooks), verified against
the installed tool during OBS-LIVE-01 development. Release documentation is the
schema reference; newer `main` branch schemas are not coverage evidence.
See [live observation v1](live-observation-contract.md) and the adjacent schema.

## Configure once per workspace

Use the trusted Workflow Kernel launcher and coherent bundle resolution from
[runtime resolution](runtime-resolution.md). Resolve Workflow Kernel >=0.21.0
with the skill, launcher, `workflow_kernel/live_observation.py`,
`workflow_kernel/codex_observation.py`, schema and this guide as required assets.
Use all assets from that one selected root. Do not glob or mix caches. Source
development may use the repository launcher; installed-consumer support requires
a separate release, installation and acceptance receipt. This change performs
none of those operations.

Provision an empty private parent once, outside source/evidence trees exposed by
other systems. Record its device and inode with `stat` and assign an opaque
workspace ID. Keep the parent location fixed and its mode 0700. Do not put its
path into a public snapshot. Root replacement requires deliberate reconfiguration.

Append a group for each listed event to the existing workspace
`.codex/hooks.json`; preserve every existing group and handler. A handler looks
like this (replace the four uppercase placeholders with reviewed fixed values):

```json
{
  "type": "command",
  "command": "ABSOLUTE_TRUSTED_LAUNCHER codex-observation-hook --parent ABSOLUTE_PRIVATE_PARENT --identity DEVICE:INODE --workspace OPAQUE_WORKSPACE",
  "timeout": 1,
  "async": true
}
```

Place it inside `{"hooks":{"UserPromptSubmit":[{"hooks":[HANDLER]}]}}`,
replacing HANDLER with the object above. Repeat for SessionStart, SessionEnd,
PreToolUse, PostToolUse, PermissionRequest, PreCompact, PostCompact,
SubagentStart, SubagentStop, Stop and Interrupt. Use `async: false` for SessionEnd;
the native contract always runs it synchronously. Omit matchers to receive every
supported occurrence. Quote fixed absolute paths according to the host shell;
never interpolate callback data into the command. A POSIX command wrapper may
redirect launcher failures and return `{}` with exit zero if the runtime itself
is missing; it must not launch or wrap the model process.

Enable `[features] hooks = true` in the supported project configuration if needed.
On first opening, trust the disposable/approved project layer and review these
exact hook definitions through native `/hooks`. Hook trust follows the definition
hash. After this one-time step, start Codex normally. No observation flag, run
registration or observer service restart is required. This guide is an example;
it does not install into existing user configurations.

## Supported metadata projection

| Callback | Recorded meaning |
|---|---|
| SessionStart | Session identity; startup/resume/clear/compact distinguished |
| UserPromptSubmit | Turn submitted, response open |
| PreToolUse / PostToolUse | Tool invocation started/returned; tool-call identity |
| PermissionRequest | Approval requested; waiting and attention |
| PreCompact / PostCompact | Compaction boundary within the same session |
| SubagentStart / SubagentStop | Explicit child ID and parent session relationship |
| Stop | Response closed, objective outcome unknown |
| Interrupt | Root turn interrupted, objective outcome unknown |
| SessionEnd | Root session closed, verification unknown |

SubagentStart/Stop carry the parent session, turn and model. Their `agent_id`
identifies the child. The adapter records the parent turn as `trigger_turn` and
never attributes the parent's model to the child. Child model facts require a
callback from that child's own execution context. Multi-level attachment uses
explicit IDs only; no nickname, agent type or directory inference is allowed.

Native event identity, source timestamps, attempt IDs, fork linkage, served
model identity and workflow outcomes are unsupported by this adapter's source
contract. Explicit neutral fixtures exercise outcomes and attempts; they are
not native acceptance. Stop hooks may be followed by continuation or resume.
Hosted tools and specialized paths outside the native local tool hook surface
remain gaps. Async hooks may be cancelled when a session ends. IDE, desktop,
cloud, remote server and headless launch paths require separate acceptance.
No all-runs coverage claim follows from this producer.

## Floor handoff (specification only)

Bind the consumer to Floor commit
`265d855b67b884474306f0eea77dbefadfbb68ce`, tree
`e18df9ecc7c7cdb9443aa61eaaf3443ee65175f2`.
The seams are `server/config.js::parseCliArgs`, new
`server/discovery.js::discoverObservationRuns`, new
`server/live-observation.js::normalizeLiveObservation`,
`server/evidence.js::createEvidenceReader/snapshot/readStableFile`,
`server/index.js::createFloorServer`, `src/lib/poll-runs.js::createRunsPoller`,
`src/lib/run-view.js::orderRuns/runCounts/runRoutes`,
`FloorApp.vue::handleSnapshot/handleConnection`, and `RunLedger.vue`.

Discover direct children every two seconds. Poll from the browser every second
with a three-second request timeout. An empty configured parent must work.
Under the 200-session bound, prove foreground source-to-visible delay <=5 seconds.
Keep one run per explicit work identity and attach agents/stages where supplied.
Missing lane/task relations never suppress a run. Keep Floor GET/HEAD-only.
The separate Foreman repair must handle lifecycle before index publication
without rewriting or weakening observation-index-v1. Foreman reference:
`35d09ab26046f669469ad82033b828d64f9a462a`.

Required downstream acceptance remains separate: use actual Floor candidate
commit/tree and built assets with this producer's real live inputs at 375x812,
768x1024 and 1440x900. Prove new session arrival without refresh, restart or root
registration; live changes; parent/child display; attention/waiting; available
explicit outcomes; stale contact and recovery. Test background-tab return
separately from foreground latency.

Measure focus persistence through arrival/reordering, keyboard selection,
Escape focus return, accessible relationships and status announcements, reduced
motion, contrast, zero page overflow and Gantt-only horizontal scrolling.
Capture semantic/interaction measurements, console errors and application
requests; screenshots alone do not pass. Bind receipts to origin, candidate
commit/tree, asset digests, browser engine/version/session, viewport, source
revisions/digests and timestamps. Keep injected cases separate from normally
started work. Historical completed runs do not establish live acceptance.

Visible copy uses Ghostwriter and preserves the existing design. Substantive
visual refinement requires the requested Fable 5.1; unavailability is a named
blocker, never permission to substitute.

Floor browser acceptance: pending consumer implementation.


## Repository validation evidence

Pass `--evidence-output` to the canonical kernel validator with an exact owned
ignored path. For `validate-composition.sh --all`, set
`WORKFLOW_KERNEL_EVIDENCE_OUTPUT` to that same owned path (or a second owned
filename). The explicit CLI option takes precedence. This keeps this execution's
evidence out of historical receipt locations while preserving the default for
existing callers that do not supply either override.
