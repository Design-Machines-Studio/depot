# NED Operations and AI Control Plane

Date: 2026-08-11
Status: Approved
Owner: Travis Gertz
Host: NED 9000 (`ned9000`)

---

## 1. Purpose

NED 9000 is the execution host for Design Machines development. The Mac is the
interactive cockpit: it provides T3 Code, Codex desktop, visual design tools,
and Stream Deck controls, while NED owns repositories, containers, databases,
worktrees, terminals, agents, and long-running AI processes.

The design has two layers:

1. A curated NED runtime with a stable operational interface and explicit
   project inventory.
2. An always-on T3 Code server reachable only through Tailscale, with Claude,
   Codex, and Depot execution occurring on NED.

The system must remain operable through SSH and tmux if T3 Code, Caddy, or a
project runtime is unavailable.

## 2. Goals

- Run every NED-hosted application in an isolated project runtime appropriate
  to that project: Docker Compose, DDEV, static build container, or direct
  one-shot tooling.
- Give persistent previews stable private domains and selectively expose
  client previews through Cloudflare Tunnel plus Cloudflare Access.
- Make project status, startup, restart, logs, routes, and diagnostics
  consistent without merging all projects into one Compose stack.
- Let the Mac control AI work while all provider CLIs and project workloads
  execute on NED.
- Preserve released Depot plugins as the everyday orchestration layer.
- Keep SSH/tmux as an independent recovery path.
- Keep secrets, host credentials, and mutable machine state out of Depot.

## 3. Non-goals

- Kubernetes or k3s.
- One monolithic Compose project for all applications.
- Moving production-only The Local onto NED.
- Replacing the current DigitalOcean production deployment for Live Wires.
- Creating Assembly Baseplate 3 or the standalone Assembly Demo install now.
- Making T3 Code or an application publicly reachable without an explicit
  exposure decision.
- Turning T3 Code into the cross-model workflow scheduler.

## 4. Trust and account boundaries

| Boundary | Responsibility |
|---|---|
| Mac user `trav` | T3 desktop UI, Codex desktop, visual tools, Stream Deck, SSH client |
| NED user `ned` | Repositories, rootless Docker, DDEV projects, AI CLIs, Depot releases, ai-memory, T3 server |
| NED user `trav` | Administrative work, sudo, system packages, system services, Caddy and network changes |
| Tailscale tailnet | Private transport for SSH, application previews, and T3 |
| Cloudflare Tunnel + Access | Deliberately exposed client previews with identity policy |

Normal development and agent work runs as `ned`. System changes are performed
as `trav` and are never hidden inside an AI skill. Deletion, public exposure,
DNS mutation, credential rotation, and production changes always require
explicit confirmation at the time of action.

## 5. Filesystem contract

NED uses three top-level work areas in `/home/ned`:

- `/home/ned/assembly` for Assembly product repositories and fixtures.
- `/home/ned/sites` for websites and client sites.
- `/home/ned/ai` for Depot, ai-memory, T3 support files, and NED operations.

The operational implementation lives outside Depot at:

```text
/home/ned/ai/ned-ops/
  inventory.json
  nedctl
  health/
  systemd/
  README.md
```

`/home/ned/.local/bin/nedctl` is a stable symlink or launcher for the checked
out `nedctl` implementation. `inventory.json` contains paths, runtime types,
domains, ports, persistence intent, and health checks, but no secrets.

## 6. Project inventory

### Persistent application runtimes

| ID | Path | Runtime | Private or preview domain | Purpose |
|---|---|---|---|---|
| `dm006` | `/home/ned/assembly/assembly` | Docker Compose | `dm006.asmbly.app` | Assembly prototype |
| `dm021` | `/home/ned/assembly/assembly-baseplate` | Docker Compose | `dm021.asmbly.app` | Primary Baseplate development install |
| `dm022` | `/home/ned/assembly/assembly-baseplate-2` | Docker Compose | `dm022.asmbly.app` | Independent second install and federation testing |
| `travisgertz` | `/home/ned/sites/travisgertz` | DDEV | `travisgertz.designmachines.xyz` | Production-style NED preview; visual HMR remains on Mac |
| `burnfund` | `/home/ned/sites/burnfund` | DDEV | `burnfund.designmachines.xyz` | To be provisioned; client preview with database, uploads, config, and tracked plugin |
| `livewires` | `/home/ned/sites/livewires` | Static build container | `livewires.designmachines.xyz` | Built preview only; development and HMR remain on Mac |

`prototype.asmbly.app` is an Access-protected alias for `dm006` once the
Cloudflare lane is validated. The existing DigitalOcean prototype must remain
available until the NED alias has passed functional and access validation.

### Ephemeral development runtimes

| ID | Path | Runtime | Domain |
|---|---|---|---|
| `fixture-jig` | `/home/ned/assembly/assembly-fixture-jig` | On-demand Docker test and generation | None |
| `livewires-templ` | `/home/ned/assembly/livewires-templ` | On-demand Docker library development and tests | None |

### Direct one-shot tools

- `ai-memory`: direct `uv` MCP execution from
  `/home/ned/ai/ai-memory`; no MCP container or persistent dashboard service.
- `wiz-control`: direct `uv` execution on demand; no persistent process and no
  Docker container.

### Reserved or deferred

- `dm023`: reserved for a future third Baseplate checkout and three-way
  federation fixture.
- `dm024`: reserved for the future standalone Assembly Demo install. A checkout
  currently exists, but no persistent runtime or route is created now.
- `designmachines`: currently present on NED and slated for NED-only removal; a
  future site will be built from scratch.
- `farewell`: currently present on NED and slated for NED-only removal; future
  production migration targets Cloudflare Pages.
- `the-local`: production-only and not operated on NED.

## 7. Runtime and lifecycle model

Each repository retains its own Compose, DDEV, or build configuration. The
shared layer coordinates lifecycles but does not redefine project internals.

Persistent runtimes are represented by one systemd user unit per project and
grouped under `ned-projects.target`. Units call the project's normal lifecycle
commands and use explicit working directories. Rootless Docker runs as the
`ned` user and user lingering allows persistent workloads to survive logout
and reboot.

The units must:

- start idempotently;
- stop only the selected project;
- declare useful timeouts;
- preserve application data volumes;
- report failure through systemd and `nedctl`;
- avoid shell evaluation of values taken from the inventory;
- avoid automatic startup for ephemeral projects and one-shot tools.

Project containers do not carry host-level restart policies in the NED wrapper.
Systemd owns desired startup and stop state. A separate project-health unit and
`nedctl` report runtime health, because a completed lifecycle launcher is not
evidence that its application remains healthy.

### Current-state audit at approval

The 2026-08-11 audit found:

- rootless `docker.service` is enabled for `ned`, but no per-project user
  services exist;
- Caddy is active;
- Tailscale Serve has no configuration;
- the DDEV router and Travis Gertz are paused;
- the three Assembly applications are not listening on their intended ports;
- Caddy has explicit routes for `dm006`, `dm021`, and `dm022`, but its current
  `*.designmachines.xyz` block forwards every hostname to the DDEV router
  rather than rejecting unknown hosts;
- Burnfund is absent from `/home/ned/sites`;
- `designmachines`, `farewell`, and the deferred `assembly-demo` checkout are
  still present.

These are rollout inputs, not evidence that the desired runtime already works.

## 8. `nedctl` operator interface

`nedctl` is a small host-local CLI implemented with the Python standard
library. It reads the fixed JSON inventory and executes allowlisted operations
without `eval` or arbitrary command interpolation.

Initial interface:

```text
nedctl list
nedctl status [project]
nedctl doctor [project]
nedctl start <project>
nedctl stop <project>
nedctl restart <project>
nedctl logs <project> [--lines N]
nedctl routes
nedctl health [project]
```

Behavioral rules:

- Read-only commands can run without confirmation.
- Start, stop, and restart are restricted to known inventory IDs.
- `stop` reports the affected project and does not remove containers or data.
- No command deletes volumes, repositories, databases, or configuration.
- Logs are bounded by default and redact known credential patterns before
  display to agent contexts.
- A failing health check returns non-zero and identifies the failing layer:
  lifecycle, local port, Caddy route, tailnet route, or external Access route.

## 9. Routing and exposure

Caddy is the shared reverse proxy for NED applications. Private wildcard DNS
maps `*.asmbly.app` and `*.designmachines.xyz` to NED's Tailscale address.
Caddy routes only known hostnames to known loopback ports and returns 404 for
unknown hosts.

Routing has three independently validated lanes:

1. Application health on its loopback port.
2. Private hostname health through Caddy over Tailscale.
3. Optional external hostname health through Cloudflare Tunnel and Access.

Cloudflare exposure is not inferred from the presence of a Caddy route. A
project must be explicitly marked for external preview, receive an Access
policy, and pass both unauthenticated-denial and authenticated-access tests.
Cloudflare credentials are stored in the standard protected cloudflared
location, never in `inventory.json`, Depot, shell history, or logs.

## 10. Depot `ned:operate` skill

The operational skill is added to the existing `ned` plugin. The primary
`SKILL.md` remains concise and loads a detailed project/runtime reference only
when NED operations are requested.

The skill will:

- recognize the NED account, path, project, domain, and runtime conventions;
- audit with read-only commands before proposing changes;
- use `nedctl` for ordinary lifecycle and diagnostics;
- distinguish persistent, ephemeral, direct one-shot, removed, deferred, and
  production-only projects;
- explain which health lane has and has not been proven;
- preserve bounded log output and secret redaction;
- require confirmation for deletion, public exposure, DNS, credentials,
  production, or administrative system changes;
- fall back to explicit SSH diagnostics when `nedctl` itself is unhealthy.

The skill does not carry the inventory, credentials, or a second copy of
machine scripts. Released Depot versions are used for daily work. The local
Depot checkout is used only when intentionally developing Depot.

## 11. Stream Deck control

The Mac receives a single `ned-wiz <scene>` launcher. It validates the scene
name and invokes Wiz Control on NED through the existing plain SSH alias. The
six current Stream Deck actions call that launcher for:

- `video_night`
- `morning`
- `video_day`
- `evening`
- `writing`
- `away`

This removes duplicated SSH command strings from the Stream Deck profile and
fixes the erroneous literal `Command:` prefix in the current `writing` action.
The existing profile is backed up before modification and each scene is tested
individually.

## 12. T3 Code server

T3 Code runs as an always-on `ned` systemd user service and is reachable only
through Tailscale Serve HTTPS. It is not bound to a public network interface
and is not routed through Cloudflare.

The deployment uses:

- a user-scoped current Node LTS runtime;
- a pinned, tested T3 Code package installation rather than an unbounded
  automatic update at every service start;
- an explicit service working directory and PATH;
- restart-on-failure with bounded backoff;
- systemd lifecycle logging only; T3 application streams remain discarded until
  a tested redacting logger and an audited host retention policy exist;
- a pairing token handled as a credential and not copied into design docs,
  repositories, or agent prompts.

The Mac T3 desktop application pairs with the NED server through the tailnet.
Project roots are added individually from `/home/ned/assembly`,
`/home/ned/sites`, and `/home/ned/ai`; the entire home directory is not exposed
as a default workspace.

Changing Tailscale Serve is a security-sensitive network action and requires
an immediate confirmation directly before execution, even though the overall
architecture is approved.

## 13. Provider and model control

Claude Code and Codex CLI are installed and authenticated on NED. T3 provider
adapters point at the NED binaries, so provider sessions, terminal commands,
file access, approvals, and worktrees all execute on NED.

T3 supplies the user interface and session transport. It does not replace
Depot orchestration:

- Codex and Claude are the native subscription-backed execution providers.
- Released Depot plugins supply `/pipeline`, `/pipeline-run`, review loops,
  subagent governance, and OpenRouter delegation.
- OpenRouter is a separately metered fallback or specialist lane and must fail
  clearly when its account cap or credentials prevent execution.
- Mandatory independent model-family or human approval gates remain mandatory;
  T3 connectivity does not weaken them.

Provider configuration and authentication live on NED. The Mac does not need
provider credentials merely to display the paired T3 interface.

## 14. Session and worktree behavior

Long-running sessions must continue when the Mac sleeps or disconnects. T3's
server, provider processes, and terminals live on NED. Reconnecting the Mac
reattaches to the NED session rather than recreating it locally.

Repository work follows each project's existing worktree rules. For the
Assembly family, new concurrent work starts from refreshed `origin/main` in a
fresh isolated worktree, and existing or foreign worktrees are never reused or
deleted implicitly.

SSH aliases provide two fallback modes:

- tmux-attached aliases for interactive persistent maintenance;
- plain aliases without a remote command for T3, scripts, transfers, and
  automation.

## 15. Data flow

### Interactive AI work

1. The Mac T3 app connects to NED through Tailscale HTTPS.
2. The NED T3 server opens the selected repository and provider session.
3. Claude or Codex executes on NED and loads released Depot plugins there.
4. Depot may spawn governed subagents or delegate permitted work to
   OpenRouter.
5. Agents create worktrees, run containers, and inspect previews on NED.
6. T3 streams structured session output, terminal state, and requested files
   back to the Mac UI.

### Application request

1. A private hostname resolves to NED's Tailscale address.
2. Caddy selects a fixed hostname route.
3. Caddy proxies to a loopback-only project port.
4. The project runtime serves the request from its isolated container stack.

For an approved external preview, Cloudflare Access authenticates the visitor
before the Tunnel forwards the request to the same Caddy hostname route.

## 16. Failure and recovery

| Failure | Expected behavior | Recovery path |
|---|---|---|
| T3 desktop disconnects | NED session continues | Reopen and reconnect; use SSH/tmux if needed |
| T3 server fails | Projects and SSH remain available | `systemctl --user status/restart`, inspect bounded journal |
| Provider CLI auth expires | T3 remains reachable; provider reports auth failure | Re-authenticate that provider on NED |
| OpenRouter cap is exhausted | Native Claude/Codex lanes remain usable | Use subscription lane or restore OpenRouter capacity |
| Project health fails | Only that project is unhealthy | `nedctl doctor <id>`, then bounded project logs |
| Caddy route fails | Direct loopback health can still pass | Inspect route configuration and Caddy status as `trav` |
| Cloudflare tunnel fails | Tailnet preview remains available | Diagnose tunnel/Access independently; do not alter app runtime first |
| Rootless Docker fails | Static host services and SSH remain available | Inspect user Docker service and storage without deleting volumes |
| `nedctl` fails | No hidden control dependency | Use the documented underlying systemd/Compose/DDEV commands |

Recovery procedures must diagnose the narrowest failing layer before restart.
No automated recovery deletes data, recreates databases, or rewrites project
configuration.

## 17. Security rules

- T3 and private previews are tailnet-only unless separately exposed.
- Project services bind to loopback or an internal container network, not
  unrestricted host interfaces.
- Pairing tokens, API keys, Cloudflare credentials, SSH keys, and provider
  credentials never enter repositories, command arguments, receipts, or
  unbounded logs.
- Agent-facing log collection is bounded and redacted.
- The `ned:operate` skill cannot grant itself sudo or bypass confirmation.
- Cloudflare Access is proven by both denial and permitted-user checks.
- Production deletion or DigitalOcean retirement occurs only after replacement
  evidence is complete and the user explicitly authorizes it.

## 18. Verification strategy

### Operations

- Validate inventory schema and reject duplicate IDs, domains, or
  project-owned ports; shared router endpoints are typed separately.
- Prove all read-only `nedctl` commands and unknown-project failure behavior.
- Start, stop, and restart one representative Compose, DDEV, and static runtime
  without affecting neighboring projects.
- Reboot NED and verify only persistent projects return.
- Verify ephemeral projects remain stopped.
- Verify unknown Caddy hostnames return 404.

### T3 and providers

- Confirm the Mac T3 app is connected to the NED server, not its local server.
- In T3, record `hostname`, `whoami`, working directory, and process tree from
  both Claude and Codex sessions.
- Start a long-running harmless task, disconnect the Mac, reconnect, and prove
  the same NED process and session survived.
- Paste an image into T3 and prove it reaches a NED-hosted provider session.
- Create an isolated test worktree on NED and verify no Mac worktree appears.
- Exercise one released Depot skill from Claude and Codex on NED.
- Verify an unavailable OpenRouter lane reports a coverage gap instead of being
  treated as success.

### Networking

- Validate loopback, Caddy/tailnet, and Cloudflare/Access as separate evidence
  lanes.
- Confirm T3 is unavailable from the public internet.
- Confirm unauthorized external preview access is denied.

## 19. Rollout order

1. Remove the NED-only `designmachines` and `farewell` checkouts without
   changing their upstream repositories or production deployments.
2. Provision the Burnfund checkout and preserve its tracked nested plugin.
3. Build the inventory and read-only `nedctl` commands.
4. Add lifecycle operations and health checks.
5. Add and validate `ned:operate` in Depot.
6. Repair persistent project startup and verify reboot behavior.
7. Add the Mac `ned-wiz` launcher and update the Stream Deck profile.
8. Install the user-scoped Node runtime and pinned T3 server on NED.
9. Create and validate the T3 systemd user service.
10. Confirm and apply the Tailscale Serve change.
11. Pair the Mac T3 app and validate remote provider execution.
12. Install and verify released Depot plugins for both NED providers.
13. Configure Cloudflare Tunnel and Access one preview at a time.
14. Retire replaced DigitalOcean resources only after explicit approval and
    complete replacement evidence.

## 20. Acceptance criteria

The implementation is accepted when:

- NED reboots into the intended persistent application set.
- `nedctl` accurately reports and controls every in-scope project without
  affecting adjacent projects.
- The `ned:operate` skill uses the host contract and honors all guardrails.
- All Stream Deck scenes execute Wiz Control on NED.
- The Mac T3 app controls NED-hosted Claude, Codex, terminals, files, and
  worktrees while the Mac remains free of the corresponding heavy processes.
- A disconnected Mac does not terminate NED agent work.
- Every exposed preview has independent application, tailnet, Tunnel, and
  Access evidence.
- SSH/tmux remains a functional recovery path throughout.
