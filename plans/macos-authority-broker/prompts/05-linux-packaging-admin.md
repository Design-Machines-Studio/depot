# Chunk: Package the minimal Linux service and admin lifecycle

## Context

This is workstream E after the authority/FIDO and composed provider daemon exist. It owns Linux fixed paths, systemd activation, the public/operator client, focused injected-root tests, and the minimum safe enrollment/credential/status lifecycle.

This chunk must be fully testable against an injected root. It must not install, enable, enroll, provision, or contact anything live during execution.

## Task

Implement one Go client source installed as public `workflow-authority` and root-only `workflow-authority-admin`, Linux platform path/peer/service adapter, tests, and systemd resources. Provide `dispatch-provider-request`, `status`, `enroll-fido`, `provision-openrouter`, `revoke-openrouter`, `disable`, and `uninstall-plan`. Dispatch uses one connection: the same fixed client receives the challenge, displays it on `/dev/tty`, acknowledges display, waits for daemon-owned FIDO, verifies terminal evidence, then releases response bytes to fd 3.

Mutating admin commands require effective UID 0 and a stable controlling `/dev/tty`; credential input is read directly by the Go admin process without Python, shell argv, environment, or temporary files. `status` is public and content-free; it must not become an authorization oracle.

## Files to Modify

| File | Action | Notes |
|---|---|---|
| `native/workflow-authority/cmd/workflow-authority/main.go` | Create | Fixed-socket public client and response channel contract |
| `native/workflow-authority/internal/platform/linux.go` | Create | Frozen Linux paths, peer/service interfaces, injected test root |
| `native/workflow-authority/internal/platform/linux_test.go` | Create | Injected-root paths, TTY, lifecycle and service tests |
| `native/workflow-authority/packaging/linux/workflow-authority.socket` | Create | Root-owned systemd socket unit |
| `native/workflow-authority/packaging/linux/workflow-authority.service` | Create | Root daemon service with hardened environment |

## Files to Read (for context)

| File | Why |
|---|---|
| `plugins/workflow-kernel/skills/workflow-kernel/references/provider-dispatch-request-schema.json` | Frozen M0 framing and operation fields |
| `plugins/workflow-kernel/skills/workflow-kernel/references/provider-dispatch-status-schema.json` | Frozen public status contract |
| `tests/test_provider_dispatch_contract.py` | Production-ineligible fake and injected-root conventions |
| `plans/macos-authority-broker/plan.html` | Frozen Linux path/owner/mode table and authorization gates |

## Patterns to Follow

- Installed paths: client `/usr/local/bin/workflow-authority`; admin `/usr/local/sbin/workflow-authority-admin`; daemon `/usr/local/libexec/design-machines/workflow-authorityd`; socket `/run/design-machines/workflow-authority/authority.sock`.
- Policy `/etc/design-machines/workflow-authority/provider-policy.json`; credential `/etc/design-machines/workflow-authority/credentials/openrouter`; state `/var/lib/design-machines/workflow-authority`.
- Service runs as root with a minimal fixed environment, no proxy variables, private temporary directory, restrictive umask, bounded descriptors/processes/memory, and explicit shutdown timeout.
- Socket parent root:workflow-authority 0750; socket 0660; credential parent 0700 and file root:root 0600.
- Test-root injection is a Go constructor/build-test seam, never a production CLI flag or environment variable.

## Companion Skills

- `assembly:golang-patterns` -- Go CLI boundaries and testable platform adapters
- `developer-essentials:auth-implementation-patterns` -- root/TTY custody and status-vs-authority separation
- `developer-essentials:error-handling-patterns` -- recovery-safe lifecycle messages

## Acceptance Criteria

- [ ] `REQ-PACKAGE-01`: production binaries use only the frozen Linux paths and reject caller socket, state, policy, credential, scanner, service, or provider-base overrides.
- [ ] `REQ-PACKAGE-02`: systemd socket/service units create the required ownership/modes, remove provider/proxy authority from the environment, bound resources, and invoke only the installed daemon.
- [ ] `REQ-PACKAGE-03`: public client stdout contains only a signed content-free receipt/status document; automated response content uses the inherited anonymous fd-3 contract and rejects regular files or caller output paths.
- [ ] `REQ-PACKAGE-04`: mutating admin commands require euid 0 plus a controlling `/dev/tty` whose identity remains stable through the operation; redirected stdin, `setsid`, changed TTY, or non-root invocation fails before secret input.
- [ ] `REQ-PACKAGE-05`: the Go admin process reads the provider credential directly from `/dev/tty`, provisions atomically, zeroizes buffers, and never passes it through shell/Python/env/argv/temp/log/result.
- [ ] `REQ-PACKAGE-06`: revoke makes new dispatch impossible before returning success, fsyncs durable state, and does not expose prior credential bytes.
- [ ] `REQ-PACKAGE-07`: public `status` distinguishes unavailable/not-enrolled/ready/degraded without exposing secret existence details to unauthorized peers and without authorizing dispatch.
- [ ] `REQ-PACKAGE-08`: `disable` and `uninstall-plan` are idempotent, preserve forensic tombstones by default, name exact manual recovery steps, and never recursively target an unresolved/broad path.
- [ ] `REQ-PACKAGE-09`: invalid/missing policy, wrong modes/owners/types/links, unexpected unit fields, or corrupt state makes service startup fail non-zero.
- [ ] `REQ-PACKAGE-10`: injected-root tests prove install layout, status, provision, revoke, disable, uninstall plan, missing/changed TTY, symlink/hard-link/parent swaps, and recovery messages without root mutation.
- [ ] `REQ-PACKAGE-11`: `enroll-fido` and single-connection `dispatch-provider-request` preserve the controlling terminal, render exact scope, use the production libfido2 adapter, and never pass raw credential/assertion/PIN material through shell, Python, argv, environment, or files.
- [ ] `REQ-PACKAGE-12`: client implements the exact M0 framing, fixed exits, fd-3 anonymous-pipe validation, trust-chain verification, buffering-before-release, and rejection of second-connection authorization/retrieval.
- [ ] No live `systemctl`, root filesystem write, FIDO enrollment, provider credential, or network operation runs.
- [ ] `go test -race ./...` passes; native systemd/root behavior remains an explicit later live gate.

## Tool-Call Budget & Partial-Return Contract

You run under a hard budget. Treat every tool call as spend you track.

- **Hard cap: 40 tool calls** (50 if this chunk drives a browser). Keep a running count.
- **At 80% of budget (32 calls) stop exploring and finish the edit + write-up.** A subagent that dies mid-flight (spend limit, context overflow, crash) returns NOTHING and its whole chunk is lost. Partial progress committed beats a perfect diff never returned.
- **End your response with two sections, even if you had to stop early:**
  - `NOT-COVERED:` -- acceptance criteria, files, or checks the budget did not reach.
  - `COMMANDS-RUN:` -- the build/test/search commands you actually ran.

## Ambiguity Protocol

This block is one of three layers in the pipeline's ambiguity defence. Sibling layers: `plan-adversary.md` Sprint Contract Negotiation (catches structural ambiguity at prompt-review time, cheapest) and `execution-orchestrator.md` Ambiguity Handling (autonomous-mode commit-trailer fallback). Keep the wording here in sync with those two.

If the Task or Acceptance Criteria allow more than one reasonable interpretation, do not pick silently.

- Name the interpretations in a single short list before you touch code. Example: "Task says 'make the members page faster' -- this could mean (a) reduce server render time, (b) reduce perceived load time via progressive rendering, (c) reduce bundle size. Proceeding with (a) because the assessment flagged a slow query; alternatives rejected for lack of evidence."
- When running under the execution-orchestrator's autonomous mode, record the chosen interpretation and rejected alternatives as two separate git-style trailer lines in the chunk's commit message: one `Chose: <interpretation>` line and one `Rejected: <alt-1>; <alt-2>` line. Multiple rejected alternatives are `; `-separated on the single `Rejected:` line. Follow the canonical `git interpret-trailers` shape so downstream tools can parse them.
- Flag the decision in the chunk receipt (`ambiguity_resolved: true` with a one-line summary) so the adversarial reviewer on the next round can evaluate whether the right path was taken.
- Fabricating certainty is a P1 failure. Surfacing ambiguity is never penalized.

## Constraints

- Only modify the files listed above.
- Do not run live install, `systemctl`, root mutation, FIDO enrollment, credential provisioning, or uninstall.
- Do not add macOS behavior or claim platform parity from Linux tests.
- Config validation is fail-closed at boot; no warning-and-continue defaults.
- Shutdown ordering is explicit and tested; unordered defer cleanup is insufficient.
- Runbooks beyond actionable CLI error text remain a later docs chunk.
- Do not create or modify `*_templ.go` files. Run `docker compose exec app templ generate` to regenerate them after editing `.templ` source files.
- When adding database migrations, verify the next sequence number: `ls migrations/*.sql | sort | tail -1`. Use the next consecutive number.

## Research Context

The minimum safe dispatch needs enough lifecycle to install and revoke the root-owned provider credential, but not a broad enterprise console. Root plus stable `/dev/tty` keeps provisioning outside repository-worker argv, environment, and Python memory while retaining Linux/macOS protocol parity for later work.

## Required Handoff Evidence

- Include the literal installed-path/owner/group/mode table exercised by tests.
- Record every systemd hardening directive and its intended boundary.
- Separate injected-root proof from unrun root/systemd live evidence.
- Report `/dev/tty`, `setsid`, redirected-input, and changed-terminal cases.
- Include an actionable recovery command for each partial lifecycle failure.
