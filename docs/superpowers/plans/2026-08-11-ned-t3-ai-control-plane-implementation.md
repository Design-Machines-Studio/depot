# NED T3 AI Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pair the Mac T3 Code desktop app with an always-on, tailnet-only T3 server whose Claude, Codex, terminals, repositories, worktrees, and Depot workflows execute on NED.

**Architecture:** A pinned T3 installation and systemd user service run as `ned`. T3 uses its documented Tailscale Serve integration on port 8443; initial pairing happens interactively so the pairing credential is never captured in journals or agent output. T3 is the remote UI and provider transport, while released Depot plugins remain the cross-model workflow and subagent layer.

**Tech Stack:** Ubuntu-signed Node.js 22 LTS and npm packages, npm lockfile,
T3 Code CLI/server, Tailscale Serve HTTPS, systemd user service, Claude Code
2.1.227+, Codex CLI 0.147.0+, Depot marketplace releases, macOS T3 Code desktop.

## Global Constraints

- T3 is available to the Tailscale tailnet only; do not enable Tailscale Funnel or Cloudflare routing for T3.
- Request immediate confirmation directly before the first command that changes Tailscale Serve.
- Pairing URLs, pairing tokens, provider credentials, API keys, and auth material must not enter chat, repositories, journals, receipts, screenshots, or captured tool output.
- Run the T3 server and both provider CLIs as NED user `ned`, never as `trav` or root.
- Use explicit provider binary paths `/home/ned/.local/bin/codex` and `/home/ned/.local/bin/claude`; non-interactive SSH currently lacks `/home/ned/.local/bin` in PATH.
- Preserve SSH/tmux aliases as an independent recovery path.
- Use released Depot versions for everyday work; use `/home/ned/ai/depot` only for intentional Depot development.
- T3 does not replace `/pipeline`, `/pipeline-run`, review loops, OpenRouter delegation, or mandatory independent-family/human gates.
- The Mac may run T3's desktop UI support process; acceptance requires provider and project workloads—not the UI—to run on NED.
- Do not expose the entire `/home/ned` tree as one default workspace; add approved project roots individually.
- Public preview and Cloudflare work are outside this plan.

---

## File map

### NED

- `/usr/bin/node`, `/usr/bin/npm`, and `/usr/bin/npx` — Ubuntu archive-signed
  packages installed by `trav`, not downloaded archives extracted by `ned`.
- `/home/ned/ai/t3-code/package.json` — private pinned T3 dependency.
- `/home/ned/ai/t3-code/package-lock.json` — exact npm dependency graph.
- `/home/ned/ai/t3-code/README.md` — upgrade, pairing, recovery, and log policy.
- `/home/ned/ai/t3-code/scripts/check-serve-containment.py` — reads a protected
  Serve config and emits only a boolean containment verdict.
- `/home/ned/.config/systemd/user/ned-t3.service` — always-on T3 service.
- `/home/ned/.config/systemd/user/default.target.wants/ned-t3.service` — enablement symlink created by systemd.
- `/home/ned/.codex/` and `/home/ned/.claude/` — existing provider state and released plugin caches.

### Mac

- `/Applications/T3 Code (Alpha).app` — existing desktop client.
- T3 application support — the Mac app owns client-side pairing authority; the
  implementation must verify its storage path and permissions without printing
  values. NED owns server-side T3 state. Neither side may copy pairing authority
  into repositories, service arguments, journals, or agent-visible output.

---

### Task 1: Install the Ubuntu archive-signed Node 22 LTS runtime

**Files:**
- Install: Ubuntu `nodejs` and `npm` packages through APT as `trav`.

**Interfaces:**
- Produces: `/usr/bin/{node,npm,npx}` from NED's configured signed Ubuntu
  archive, with no manually extracted remote archive.

- [ ] **Step 1: Verify the signed distro candidates without changing state**

```bash
apt-cache policy nodejs npm
apt-cache show nodejs | sed -n '1,30p'
```

Expected from the 2026-08-11 audit: Node `22.22.1` from Ubuntu `resolute` and
npm `9.2.0`. Stop if the candidate origin is not a configured signed Ubuntu
archive or Node is older than the minimum required by the current T3 package.

- [ ] **Step 2: Request administrative approval and install exact candidates**

```bash
sudo apt-get update
sudo apt-get install --yes nodejs npm
```

- [ ] **Step 3: Verify package provenance and runtime paths**

```bash
apt-cache policy nodejs npm
dpkg-query -W -f='${Package} ${Version}\n' nodejs npm
command -v node npm npx
node --version
npm --version
```

Expected: binaries resolve under `/usr/bin` and installed versions match the
signed package records.

- [ ] **Step 4: Verify explicit user-service resolution**

```bash
/usr/bin/node --version
systemd-run --user --wait --pipe /usr/bin/node --version
```

---

### Task 2: Create a pinned T3 Code installation

**Files:**
- Create: `/home/ned/ai/t3-code/package.json`
- Create: `/home/ned/ai/t3-code/package-lock.json`
- Create: `/home/ned/ai/t3-code/README.md`

**Interfaces:**
- Consumes: Node runtime from Task 1.
- Produces: `/home/ned/ai/t3-code/node_modules/.bin/t3` pinned by lockfile.

- [ ] **Step 1: Resolve a candidate version and record immutable metadata without executing it**

```bash
install -d -m 700 /home/ned/ai/t3-code
cd /home/ned/ai/t3-code
NED_T3_VERSION="$(/usr/bin/npm view t3 version)"
printf '%s\n' "$NED_T3_VERSION"
/usr/bin/npm view "t3@$NED_T3_VERSION" dist.integrity dist.tarball engines --json
```

Stop if the result is empty or invalid. Record the exact version, integrity,
tarball URL, engine requirement, query time, and registry in a review receipt.
Confirm the package identity against T3's official documentation before any
install command.

- [ ] **Step 2: Fetch and inspect the exact package with lifecycle scripts disabled**

```json
{
  "name": "ned-t3-server",
  "private": true,
  "version": "1.0.0",
  "description": "Pinned T3 Code server installation for NED 9000",
  "dependencies": {}
}
```

Then fetch without installation:

```bash
cd /home/ned/ai/t3-code
umask 077
NED_T3_PACK_DIR="$(mktemp -d /private/tmp/ned-t3-pack.XXXXXX)"
cd "$NED_T3_PACK_DIR"
/usr/bin/npm pack "t3@$NED_T3_VERSION" --ignore-scripts --json > pack.json
/usr/bin/npm view "t3@$NED_T3_VERSION" dist.integrity --json > expected-integrity.json
tar -tf ./*.tgz > archive-files.txt
```

Inspect the bounded file list, package manifest, declared scripts, archive paths,
and npm-reported integrity. Reject absolute/traversal paths, unexpected native
binaries, install scripts without a documented need, or a mismatch with the
recorded metadata. The review receipt must approve the exact tarball digest
before proceeding.

- [ ] **Step 3: Create the lockfile and install with scripts disabled**

```bash
/usr/bin/npm install --save-exact --ignore-scripts "t3@$NED_T3_VERSION"
/usr/bin/npm ci --ignore-scripts
./node_modules/.bin/t3 --help
/usr/bin/npm ls t3 --depth=0
```

Expected: npm reports exactly one pinned reviewed version and the CLI help exits
0 without lifecycle scripts. If the CLI requires a script-generated artifact,
stop and review that single script before executing it; never enable all scripts
with `--ignore-scripts=false`.

- [ ] **Step 4: Document bounded upgrade and recovery commands**

`README.md` records: explicit Node/T3 paths; `npm ci --ignore-scripts`; manual
version upgrades using the same fetch/inspect/approve/install sequence; service
status/restart; `tailscale serve
status`; `tailscale serve reset` as a confirmation-gated rollback; SSH/tmux
fallback; and the rule that pairing output is interactive only.

- [ ] **Step 5: Initialize and commit the private installation repository**

```bash
cd /home/ned/ai/t3-code
git init -b main
printf '%s\n' 'node_modules/' '*.log' > .gitignore
git add package.json package-lock.json README.md .gitignore
git commit -m "chore: pin NED T3 server"
```

---

### Task 3: Prepare the always-on systemd user service without starting it

**Files:**
- Create: `/home/ned/ai/t3-code/systemd/ned-t3.service`
- Install: `/home/ned/.config/systemd/user/ned-t3.service`

**Interfaces:**
- Consumes: pinned T3 executable.
- Produces: disabled-but-valid service ready for the pairing gate.

- [ ] **Step 1: Write the service unit**

```ini
[Unit]
Description=NED T3 Code server over Tailscale Serve
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/ned/ai/t3-code
Environment=HOME=/home/ned
Environment=PATH=/home/ned/.local/bin:/usr/local/bin:/usr/bin:/bin
UMask=0077
ExecStart=/home/ned/ai/t3-code/node_modules/.bin/t3 serve --tailscale-serve --tailscale-serve-port 8443
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
StandardOutput=null
StandardError=null

[Install]
WantedBy=default.target
```

Both application streams are discarded so pairing or provider authority cannot
enter the journal. systemd still records lifecycle transitions and exit status.
Pairing is performed interactively in Task 4. A future redacting logger requires
its own tests and an audited host journald retention policy before enablement.

- [ ] **Step 2: Validate and install without enabling or starting**

```bash
systemd-analyze --user verify /home/ned/ai/t3-code/systemd/ned-t3.service
install -m 0644 /home/ned/ai/t3-code/systemd/ned-t3.service /home/ned/.config/systemd/user/ned-t3.service
systemctl --user daemon-reload
systemctl --user is-enabled ned-t3.service; test "$?" -ne 0
systemctl --user is-active ned-t3.service; test "$?" -ne 0
```

- [ ] **Step 3: Commit the unit**

```bash
cd /home/ned/ai/t3-code
git add systemd/ned-t3.service
git commit -m "feat: add always-on T3 user service"
```

---

### Task 4: Pair through Tailscale and enable the service

**Files:**
- Modify: Tailscale Serve configuration on NED.
- Modify: Mac T3 application pairing state.
- Modify: systemd enablement for `ned-t3.service`.

**Interfaces:**
- Consumes: prepared service and Mac T3 app.
- Produces: authenticated tailnet pairing on HTTPS port 8443.

- [ ] **Step 1: Capture the no-Serve baseline**

```bash
tailscale serve status
tailscale funnel status
ss -ltn
```

Expected: no Serve configuration and no Funnel configuration.

- [ ] **Step 2: Request immediate confirmation**

Explain that the next command configures a tailnet-only HTTPS endpoint through
Tailscale Serve, not a public Funnel. Do not continue until the user explicitly
confirms this immediate action.

- [ ] **Step 3: Run pairing in a disposable non-recorded terminal**

Open a dedicated interactive terminal whose scrollback and session recording are
disabled. Do not use the existing persistent tmux session, an agent tool, shell
history, or `script`. Run:

```bash
umask 077
cd /home/ned/ai/t3-code
./node_modules/.bin/t3 pair --tailscale
```

Use the Mac T3 app to consume the displayed pairing URL/QR directly. Do not
paste it into chat or a shell transcript. After the Mac confirms pairing, stop
the interactive pair process cleanly, close the disposable terminal, and verify
that no pairing material remains in shell history or tmux scrollback.

- [ ] **Step 4: Enable and start the always-on service**

```bash
systemctl --user enable --now ned-t3.service
systemctl --user is-active ned-t3.service
tailscale serve status
```

Expected: service active and Tailscale Serve HTTPS present on port 8443.

- [ ] **Step 5: Verify network containment**

```bash
tailscale funnel status
ss -ltnp | rg '8443|t3|node' || true
NED_SERVE_CONFIG="$(mktemp /private/tmp/ned-serve-config.XXXXXX)"
chmod 600 "$NED_SERVE_CONFIG"
tailscale serve get-config "$NED_SERVE_CONFIG" --all
python3 /home/ned/ai/t3-code/scripts/check-serve-containment.py "$NED_SERVE_CONFIG"
unlink "$NED_SERVE_CONFIG"
```

Expected: no Funnel; no T3 process bound to `0.0.0.0` or `[::]`; Serve targets
the T3 local service.

- [ ] **Step 6: Verify the journal contains no pairing authority**

```bash
if journalctl --user -u ned-t3.service --since '10 minutes ago' --no-pager -n 200 | rg -qi 'pair|token|secret|credential|https://.*auth'; then
  printf '%s\n' 'credential-shaped T3 journal content detected' >&2
  exit 1
fi
```

Expected: no matching output. The predicate is quiet so a failure never prints
the matching authority. If it fails, stop the service, rotate pairing through
the T3 app, and fix logging before proceeding.

- [ ] **Step 7: Verify pairing-state ownership without reading values**

Before pairing, identify the exact Mac client-state and NED server-state paths
from current T3 documentation or CLI help; do not guess or glob. After pairing,
run value-free `stat` checks against those exact paths. Require the Mac state to
be owned by `trav`, the NED state to be owned by `ned`, and neither to grant
group or other access. Record only path, owner, and mode—never names or contents
of credential-bearing child files. Stop the service and correct permissions if
either check fails.

---

### Task 5: Configure NED provider binaries and verify authentication

**Files:**
- Modify: T3 remote provider settings through the Mac app.
- Read: `/home/ned/.codex` and `/home/ned/.claude` authentication state.

**Interfaces:**
- Consumes: existing authenticated NED binaries.
- Produces: T3 provider entries bound to explicit NED paths.

- [ ] **Step 1: Re-verify provider binaries and auth without reading credentials**

```bash
/home/ned/.local/bin/codex --version
/home/ned/.local/bin/codex login status
/home/ned/.local/bin/claude --version
/home/ned/.local/bin/claude auth status
```

Expected: Codex reports ChatGPT login and Claude reports logged in. If either
fails, authenticate interactively on NED before touching T3 provider settings.

- [ ] **Step 2: Add explicit remote providers in T3**

In the paired NED environment, set:

```text
Provider: Codex
Binary path: /home/ned/.local/bin/codex

Provider: Claude Code
Binary path: /home/ned/.local/bin/claude
```

Do not add Mac binary paths or copy Mac provider credentials.

- [ ] **Step 3: Run a location proof from each provider**

Ask each provider through T3 to execute only:

```bash
hostname
whoami
pwd
printf '%s\n' "$HOME"
```

Expected for both: hostname `ned9000`, user `ned`, a selected `/home/ned/...`
project directory, and home `/home/ned`.

- [ ] **Step 4: Verify provider processes exist only on NED**

On NED:

```bash
pgrep -af '/home/ned/.local/bin/(codex|claude)|/home/ned/.codex/.*/codex|/home/ned/.local/share/claude' | sed -n '1,80p'
```

On the Mac:

```bash
pgrep -af '/Users/trav/.*/(codex|claude)' | sed -n '1,80p'
```

Interpret the Mac's T3 UI support processes separately. Acceptance requires the
two sessions just opened in T3 to correspond to NED PIDs, not that every Mac AI
application is closed.

---

### Task 6: Install released Depot plugins for NED Codex and verify both providers

**Files:**
- Modify: `/home/ned/.codex` marketplace/plugin configuration.
- Read: `/home/ned/.claude` released Depot installation.

**Interfaces:**
- Produces: the same everyday released Depot surfaces in NED Codex and Claude.

- [ ] **Step 1: Add the canonical Depot marketplace to Codex**

```bash
export PATH=/home/ned/.local/bin:/usr/bin:/bin
codex plugin marketplace add Design-Machines-Studio/depot --ref main --json
codex plugin marketplace list
```

Expected: marketplace name `depot` backed by the canonical Git repository, not
the local `/home/ned/ai/depot` checkout.

- [ ] **Step 2: Install the approved everyday plugin set**

```bash
for plugin in ned pipeline dm-review assembly live-wires openrouter workflow-kernel airlift; do
  codex plugin add "$plugin@depot" --json
done
```

If dependency resolution installs additional Depot plugins, retain them and
record them. Do not install a local checkout as the daily runtime.

- [ ] **Step 3: Compare released versions across providers**

```bash
codex plugin list | rg '@depot|Marketplace `depot`'
claude plugin list | sed -n '1,220p'
```

Expected: the requested plugin set is enabled for both. If the separately
reviewed `ned:operate` release was authorized and published, both report `ned`
1.8.0. Otherwise both remain on 1.7.1 and this plan records the operations skill
as an explicit unavailable lane.

- [ ] **Step 4: Exercise one released workflow in each T3 provider**

In a harmless repository context, ask Claude and Codex to list the available
Depot pipeline and NED skills without starting a development pipeline. Verify
that both can load released skill content from their NED cache paths.

- [ ] **Step 5: Verify ai-memory locality**

From each provider, inspect its ai-memory MCP configuration and confirm the
server command resolves to `/home/ned/ai/ai-memory` via
`/home/ned/.local/bin/uv`. Do not write a test observation. The native Mac
ai-memory graph is not valid evidence for this check.

---

### Task 7: Add project workspaces and prove remote persistence

**Files:**
- Modify: T3 paired-environment workspace list.
- Create/remove: disposable NED worktree and `/tmp/t3-survival-*` evidence.

**Interfaces:**
- Produces: verified remote files, terminals, images, worktrees, and surviving sessions.

- [ ] **Step 1: Add project roots individually**

Add these NED directories through the paired T3 environment:

```text
/home/ned/assembly/assembly
/home/ned/assembly/assembly-baseplate
/home/ned/assembly/assembly-baseplate-2
/home/ned/sites/travisgertz
/home/ned/sites/burnfund
/home/ned/sites/livewires
/home/ned/ai/depot
/home/ned/ai/ned-ops
```

Do not add `/home/ned` as a blanket workspace.

- [ ] **Step 2: Prove terminal execution is remote**

Open a T3 terminal in `/home/ned/ai/ned-ops` and run:

```bash
hostname
whoami
git rev-parse --show-toplevel
docker context show
```

Expected: NED hostname/user/path and NED's rootless Docker context.

- [ ] **Step 3: Prove worktrees are created on NED**

```bash
cd /home/ned/ai/ned-ops
git worktree add .worktrees/t3-verification -b verify/t3-remote main
git worktree list
```

Confirm the path appears on NED and nowhere under the Mac's project roots. Then
remove it with `git worktree remove .worktrees/t3-verification` and delete the
disposable branch with `git branch -D verify/t3-remote` after verifying it has
no commits.

- [ ] **Step 4: Prove image transfer reaches a NED provider session**

Paste a non-sensitive screenshot into a T3 chat and ask the NED provider to
report its pixel dimensions and a one-sentence description. Verify the
attachment appears in the remote session; do not use a credential-bearing
screenshot.

- [ ] **Step 5: Prove a session survives Mac disconnection**

From a T3 terminal on NED:

```bash
sh -c 'printf "%s\n" "$$" > /tmp/t3-survival.pid; sleep 90; date -Is > /tmp/t3-survival.done' &
```

Disconnect or sleep the Mac for more than 90 seconds, reconnect to the same T3
environment, and run:

```bash
cat /tmp/t3-survival.pid /tmp/t3-survival.done
```

Expected: both files exist and the timestamp occurred during disconnection.
Move them to `/home/ned/.local/share/Trash/files/` after recording the result.

- [ ] **Step 6: Verify SSH/tmux recovery remains functional**

From the Mac:

```bash
ssh ned-plain 'systemctl --user is-active ned-t3.service; tailscale serve status'
```

Separately open `ssh ned9000` with no remote command and confirm it attaches to
the expected tmux session. The plain scripted alias and tmux-attached interactive
alias must both work independently of the T3 desktop UI.

---

### Task 8: Prove tailnet containment and reboot persistence

- [ ] **Step 1: Prove denial from outside the tailnet**

From a controlled device with Tailscale disconnected, attempt the NED T3 HTTPS
hostname and port. Record only the connection-failed verdict. Separately confirm
no Caddy, cloudflared, Funnel, firewall, or NAT rule forwards port 8443. A local
listener audit alone is not public-denial evidence.

- [ ] **Step 2: Request immediate reboot approval**

Present the service, provider, workspace, disconnection, recovery, and
off-tailnet-denial evidence. Do not reboot until the user explicitly approves
this immediate action.

- [ ] **Step 3: Reboot and re-run acceptance**

After approval, reboot NED, reconnect through `ned-plain`, and verify the T3
service, Tailscale Serve mapping, no-Funnel state, both provider sessions, Mac
reconnection, and SSH/tmux recovery. The always-on claim remains unproven until
this reboot pass succeeds.
