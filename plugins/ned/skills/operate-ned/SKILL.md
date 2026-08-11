---
name: operate-ned
description: Use when a task must run on NED, NED 9000, or ned9000; when choosing between the trav and ned accounts or their SSH aliases; when T3 or Codex should execute remotely; or when work touches rootless Docker, system Docker, sudo, Caddy, system services, /home/ned, /etc, or /srv on NED.
---

# Operate NED

Route work to the least-privileged NED account that can complete it. Select authority by task type,
not convenience, urgency, or the account already connected.

## Canonical account matrix

| Route | Identity | Use | Boundary |
|---|---|---|---|
| T3 NED environment | `ned` | Default AI development | No sudo; rootless Docker |
| `ssh ned` | `ned` + tmux | Interactive development | No system administration |
| `ssh ned-plain` | `ned`, no RemoteCommand | Automation, SCP, remote tools | No system administration |
| `ssh ned9000` | `trav` + tmux | Interactive operations | Root-equivalent via passwordless sudo |
| `ssh ned9000-plain` | `trav`, no RemoteCommand | Bounded automated operations | Root-equivalent via passwordless sudo |

Treat `trav` as root-equivalent even before `sudo` appears. Keep routine agents out of that account.
Authenticate key-only over Tailscale through the configured Mac SSH aliases. Do not bypass host
verification or invent a direct-IP fallback when an alias fails.

## Select the account

Use `ned` for all ordinary development:

- Run Codex, Claude, T3 sessions, subagents, pipelines, and tmux jobs.
- Read or edit checkouts below `/home/ned/ai`, `/home/ned/assembly`, and `/home/ned/sites`.
- Run Git, builds, tests, DDEV, project Compose, and rootless containers.
- Manage `ned` user services and files owned by `ned`.

Use `trav` only for an exact operation that requires system authority:

- Change `/etc`, system packages, mounts, `/srv`, Caddy, Tailscale host configuration, or system
  services.
- Operate the system Docker daemon and system/media stacks.
- Perform a command whose reviewed failure as `ned` proves that sudo is required.

Start uncertain work as `ned`. Treat a permission boundary as a stop signal, not an invitation to
move the whole task into `trav`.

## Verify before mutation

Run the appropriate block before changing state.

Development preflight:

```bash
test "$(hostname -s)" = ned9000
test "$(id -un)" = ned
case "$(pwd -P)" in /home/ned|/home/ned/*) ;; *) exit 1 ;; esac
test "$(docker context show)" = rootless
! sudo -n true >/dev/null 2>&1
```

Operations preflight:

```bash
test "$(hostname -s)" = ned9000
test "$(id -un)" = trav
sudo -n true
test "$(docker context show)" = default
```

Stop on any mismatch. Report the observed hostname, user, working directory, and Docker context.
Never repair a mismatch by weakening authentication, changing sudoers, or adding `ned` to the
`docker` group.

## Split mixed development and operations

Keep mixed tasks in separate authority phases:

1. Connect directly as `ned`; investigate, edit, test, and prepare the smallest diff or immutable
   artifact.
2. Identify the exact privileged action, target, rollback, and validation command.
3. Obtain authorization when the privileged action exceeds the user's existing request.
4. Connect separately as `trav`; execute only the bounded operation. Do not start an interactive
   coding agent there.
5. Return to `ned` for project-level verification and continued development.

From Codex Desktop on the Mac, route development through `ssh ned-plain`. From T3, select the NED
environment; its backend already runs as `ned`. If an agent running on NED lacks an authorized route
to `trav`, present the exact operations command and stop rather than manufacturing access.

## Non-negotiable boundaries

- Never run Codex, Claude, a pipeline, or general subagents as `trav`.
- Never enter through `trav` and launch an agent with `sudo -iu ned`; connect directly as `ned`.
- Never use `sudo docker` or the `default` Docker context for a development checkout.
- Never add `ned` to the `docker` group. Membership is root-equivalent.
- Never collapse the two phases because a demo, deadline, or outage makes one privileged session
  seem faster.
- Never store SSH keys, pairing tokens, API keys, or secret values in AI Memory, prompts, logs, or
  skill files.

## Rationalizations to reject

| Rationalization | Required response |
|---|---|
| “Connect once as trav; it is faster.” | Open separate direct sessions. Ambient root authority is not a convenience feature. |
| “Launch Codex as ned from the trav shell.” | Exit and connect with `ssh ned-plain`. Preserve an auditable authority boundary. |
| “The project needs Docker and Caddy together.” | Use rootless Docker as `ned`; handle only the Caddy operation as `trav`. |
| “It is only one small change.” | Treat that as a hypothesis; run identity and scope checks first. |
| “The client demo is imminent.” | Reduce test breadth if justified; never broaden account authority. |

## Memory and drift

When AI Memory is available, open the exact entities `NED 9000` and `NED 9000 Dev Environment`.
Prefer observations titled `CANONICAL` over older setup history. Treat remembered versions and
service state as context, then verify cheap, drift-prone facts live before acting.

