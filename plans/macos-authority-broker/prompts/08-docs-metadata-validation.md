> **SUPERSEDED — NON-DISPATCHABLE.** Historical revision 5 prompt; it does not cover revision 6 external-provider dispatch and conveys no implementation authority.

# Chunk: Migrate Consumers, Document, Version, and Validate

## Context

This final product chunk migrates the canonical Pipeline and Assembly consumers, documents the implemented Linux-first broker, records the repository convention expansion, updates canonical metadata, regenerates Codex shims, and runs Depot validation.
It must describe real evidence and gaps without performing a release or live installation.

## Task

Write one cross-platform operator and threat-model guide.
Update Workflow Kernel documentation and skill contracts for public FIDO provider mode, legacy HMAC separation, non-secret substrate handles, and repeated cadence.
Document systemd and launchd workflows with identical semantics.
Document the current OrbStack socket as trusted host infrastructure and state precisely that deliberate developer/host-agent engine tampering is outside scope.
Migrate the canonical Pipeline orchestrator and Assembly build/test/profile surfaces from production `--receipt-key-stdin` use to fixed v2 provider and substrate handles, preserving legacy HMAC only as an explicit compatibility path.
Update canonical plugin/marketplace versions, regenerate derived Codex manifests, and run repository validation.

## Files to Modify

| File | Action |
|---|---|
| `docs/workflow-authority.md` | Create |
| `docs/workflow-kernel.md` | Modify |
| `plugins/workflow-kernel/skills/workflow-kernel/SKILL.md` | Modify |
| `plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification.md` | Modify |
| `plugins/pipeline/agents/workflow/execution-orchestrator.md` | Modify canonical production consumer |
| `plugins/assembly/commands/assembly-build.md` | Modify canonical command consumer |
| `plugins/assembly/skills/assembly-build/SKILL.md` | Regenerate command-skill alias only |
| `plugins/assembly/agents/workflow/go-test-runner.md` | Modify canonical agent consumer |
| `plugins/assembly/references/repository-verification-profile.example.json` | Modify canonical handle/profile example |
| `AGENTS.md` | Modify |
| `CLAUDE.md` | Modify while preserving the pre-existing Airlift marker |
| `docs/dependency-graph.md` | Modify minimum-version edges |
| `tools/check-dependencies.sh` | Modify dependency assertions |
| `plugins/workflow-kernel/.claude-plugin/plugin.json` | Modify canonical version |
| `plugins/pipeline/.claude-plugin/plugin.json` | Modify dependency/version only as required by consumer migration |
| `plugins/assembly/.claude-plugin/plugin.json` | Modify dependency/version only if implementation requires it |
| `.claude-plugin/marketplace.json` | Modify canonical versions |
| `plugins/workflow-kernel/.codex-plugin/plugin.json` | Regenerate only |
| `plugins/pipeline/.codex-plugin/plugin.json` | Regenerate only |
| `plugins/assembly/.codex-plugin/plugin.json` | Regenerate only |
| `.agents/plugins/marketplace.json` | Regenerate only |

## Documentation Requirements

Include:

- threat actors, protected assets, trust assumptions, and residual trusted-display risk
- identical Linux/macOS architecture and the narrow adapter differences
- compatible FIDO2 authenticator requirements, UP/UV policy, enrollment, rotation, revocation, loss, and recovery
- daemon-owned libfido2 device I/O, root-only raw allow-list credential ID handling, and raw uncompressed P-256 public-key storage for offline verification
- libfido2 and exact Go 1.26.5 prerequisites
- candidate-container exclusion from Docker, broker, FIDO, credential, and service-manager control surfaces
- exact install, status, doctor, endpoint enrollment, use, recovery, uninstall, and purge steps for both service managers
- explicit distinction between staged/offline proof and separately gated live acceptance
- exact Baseplate-compatible example exporting only fixed non-secret provider and substrate handles
- explicit legacy `--receipt-key-stdin` compatibility with no production fallback
- exact historical verification chain: FIDO run authorization to ephemeral public key to ordered operation, observed-result, cleanup-result, and final-receipt signatures
- cadence examples for chunk, revision batch, execution level, merge candidate, and provider attestation
- failure/recovery reason codes and zero-residue cleanup requirement
- uninstall preservation of public enrollment/revocation/audit state
- remaining risks and exact next authorization gates

Never print or demonstrate a real PIN, credential reference, assertion, receipt key, Docker object ID, user-specific socket path, token, or repository secret.
Use placeholders that cannot be mistaken for credentials.

## Canonical Consumer Migration

Update the Pipeline execution orchestrator, Assembly command and agent, and Assembly verification-profile example to use only the fixed non-secret provider and substrate handles in production v2 mode.
Preserve the complete repeated cadence across chunk, revision batch, execution level, merge candidate, result recording, and provider attestation.
Remove production instructions that pipe `HOST_AUTHORITY_BROKER` bytes to `--receipt-key-stdin`; retain that flag only in clearly named legacy schema-v1 compatibility documentation/tests with no automatic fallback.
Set exact minimum Workflow Kernel dependencies based on the implemented unreleased version, update the dependency graph and dependency validator, then regenerate the Assembly command-skill alias and Codex manifests from canonical sources.
Add validator coverage that fails if canonical Pipeline/Assembly production surfaces still prescribe raw-key stdin, an opaque substrate label, or Workflow Kernel `>=0.6.1` when the new provider contract requires a later version.

## Required Execution Order

This large final chunk follows a fixed order to avoid a half-migrated repository:

1. Inspect current canonical versions and record chosen unreleased versions plus rationale.
2. Migrate Pipeline/Assembly canonical consumers and dependency assertions.
3. Update canonical manifests, then regenerate aliases and Codex manifests.
4. Write operator/threat-model/repository-convention documentation from the implemented behavior.
5. Run the complete validation suite last against the converged tree.

If the tool budget prevents completion, do not describe the feature as complete; `NOT-COVERED` must enumerate every unwritten document, unmigrated consumer, ungenerated artifact, and unrun validator exactly.

## Repository Convention Update

Depot previously allowed one sanctioned executable exception: stdlib-only Python 3.12 Workflow Kernel.
Update `AGENTS.md` and canonical `CLAUDE.md` to describe the new separately built Go host companion, its non-shipping source/tests, Go 1.26.5/libfido2 validation, and Linux/macOS packaging.
Do not weaken the Python stdlib-only rule.
Do not imply the native companion is automatically installed with the plugin cache.

## Metadata and Generation

Choose the next coherent unreleased versions based on current canonical manifests and actual compatibility changes.
Update Claude manifests first.
Regenerate Codex manifests; never hand-edit generated JSON.
Regenerate command-skill aliases only if canonical command sources changed.
Keep Assembly dependency changes minimal and evidence-based.
Do not create tags, releases, marketplace publications, installs, or cache updates.

## Validation

Run:

- focused Python and Go validator suites
- `./tools/validate-workflow-authority.py`
- `./tools/validate-workflow-kernel.py`
- `./tools/generate-codex-manifests.py --check`
- `./tools/generate-codex-command-skills.py --check`
- `./tools/validate-dual-compat.sh`
- `./tools/check-dependencies.sh`
- `./tools/validate-composition.sh --all`
- `git diff --check`

Record exact commands, outcomes, unavailable external lanes, and the worktree diff scope.
Do not call hardware, live root-service, or real-engine acceptance green unless it actually ran.

## Companion Skills

Load:

- `developer-essentials:auth-implementation-patterns` for accurate threat/runbook wording.
- `developer-essentials:error-handling-patterns` for recovery guidance.

## Acceptance Criteria

- [ ] AC-01 Documentation states identical Linux/macOS features and names only systemd/launchd and peer-credential syscalls as adapters.
- [ ] AC-02 Threat model explains why no production receipt key exists, why the enrolled Docker engine is trusted host infrastructure, and what deliberate-host threats are excluded.
- [ ] AC-03 Setup/use/recovery/rotation/revocation/uninstall/purge steps are exact for both platforms and distinguish offline from live gates.
- [ ] AC-04 Baseplate example exports only non-secret fixed provider/substrate handles and uses all repeated cadence operations.
- [ ] AC-04A Documentation explains how historical verification validates the recorded FIDO-to-ephemeral-key-to-result/cleanup/receipt chain without a live daemon.
- [ ] AC-05 Current OrbStack is documented as a trusted host endpoint whose socket is never exposed inside candidate containers.
- [ ] AC-06 Residual terminal-spoofing, deliberate host-engine tampering, hardware availability, and privileged-service risks are explicit.
- [ ] AC-07 Repository executable conventions describe the Go companion without weakening Workflow Kernel’s stdlib-only Python rule.
- [ ] AC-08 Canonical versions/dependencies are coherent and Codex manifests are regenerated rather than hand-edited.
- [ ] AC-09 All listed validators pass or report exact environmental gaps; unavailable lanes are not promoted to proof.
- [ ] AC-10 No install, enrollment, release, tag, push, PR, publication, or external worktree mutation occurs.
- [ ] AC-11 The handoff lists implementation decisions, test evidence, remaining risks, and the exact next authorization gate.
- [ ] AC-12 `git diff --check` passes and only owned files plus the preserved Airlift marker remain.
- [ ] AC-13 Canonical Pipeline and Assembly execution surfaces use fixed non-secret v2 provider/substrate handles across every repeated cadence operation with no production HMAC fallback.
- [ ] AC-14 Pipeline/Assembly minimum Workflow Kernel versions, dependency graph, manifests, generated aliases/shims, and dependency checks agree exactly.
- [ ] AC-15 Validation fails on any remaining canonical production `--receipt-key-stdin`, opaque-substrate, or stale `>=0.6.1` instruction.
- [ ] AC-16 Operator docs match the implementation: the daemon owns device I/O, the raw allow-list credential ID remains root-only, and the retained public key uses the documented stdlib-verifiable P-256 format.
- [ ] AC-17 Documentation names the controlling-terminal run-open flow, root-only lifecycle admission matrix, one-retry behavior, and exact lost-authenticator command sequence.
- [ ] AC-18 Work follows the required order, all validators run last, and any budget truncation produces an exact `NOT-COVERED` inventory rather than a completion claim.

## Behavioral Contract Inputs

- `REQ-001` through `REQ-010` receive documentation and final validation traceability.
- `CHK-023`: operator parity/documentation review.
- `CHK-024`: canonical/generated metadata and full Depot validation.
- `CHK-025`: prohibited live/publication actions remain absent.

## Tool-Call Budget & Partial-Return Contract

You run under a hard budget. Treat every tool call as spend you track.

- **Hard cap: 40 tool calls** (50 if this chunk drives a browser). Keep a running count.
- **At 80% of budget (32 calls) stop exploring and finish the edit + write-up.** A subagent that dies mid-flight (spend limit, context overflow, crash) returns NOTHING and its whole chunk is lost. Partial progress committed beats a perfect diff never returned.
- **End your response with two sections, even if you had to stop early:**
  - `NOT-COVERED:` -- acceptance criteria, files, or checks the budget did not reach.
  - `COMMANDS-RUN:` -- the build/test/search commands you actually ran.

## Ambiguity Protocol

If the Task or Acceptance Criteria allow more than one reasonable interpretation, do not pick silently.

- Name the interpretations in a single short list before you touch code. Example: "Task says 'make the members page faster' -- this could mean (a) reduce server render time, (b) reduce perceived load time via progressive rendering, (c) reduce bundle size. Proceeding with (a) because the assessment flagged a slow query; alternatives rejected for lack of evidence."
- When running under the execution-orchestrator's autonomous mode, record the chosen interpretation and rejected alternatives as two separate git-style trailer lines in the chunk's commit message: one `Chose: <interpretation>` line and one `Rejected: <alt-1>; <alt-2>` line. Multiple rejected alternatives are `; `-separated on the single `Rejected:` line. Follow the canonical `git interpret-trailers` shape so downstream tools can parse them.
- Flag the decision in the chunk receipt (`ambiguity_resolved: true` with a one-line summary) so the adversarial reviewer on the next round can evaluate whether the right path was taken.
- Fabricating certainty is a P1 failure. Surfacing ambiguity is never penalized.

## Constraints

- Only modify listed files.
- Preserve unrelated changes and the existing Airlift marker.
- Do not hand-edit generated Codex manifests.
- Do not disclose secret/authenticator/Docker/repository values.
- Do not stage, commit, push, install, enroll, release, tag, publish, or touch external worktrees.
- Follow existing patterns -- do not introduce new abstractions.
- Do not refactor surrounding code unless required for the task.
- Only lines that directly serve the Acceptance Criteria should change. If you notice unrelated issues in files you are editing, list them at the end of your response as "Noted, not fixed" -- do not include them in the diff.
- Do not reformat, rewrite comments, tighten types, or adjust imports on lines you are not otherwise changing for this chunk.

## Research Context

FIDO2 authorizes one closed run and binds its memory-only ephemeral signing key.
Docker is trusted host infrastructure; candidate containers must receive none of its control surfaces.
Linux is primary, but macOS must satisfy the same contract and tests.
