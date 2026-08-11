# NED T3 AI Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pair the Mac T3 Code desktop app with an always-on, tailnet-only T3 server whose Claude, Codex, terminals, repositories, worktrees, and Depot workflows execute on NED.

**Architecture:** A pinned T3 installation and systemd user service run as `ned`. T3 uses its documented Tailscale Serve integration on port 8443; initial pairing happens interactively so the pairing credential is never captured in journals or agent output. T3 is the remote UI and provider transport, while released Depot plugins remain the cross-model workflow and subagent layer.

**Tech Stack:** Node.js 24 LTS user installation, npm lockfile, T3 Code CLI/server, Tailscale Serve HTTPS, systemd user service, Claude Code 2.1.227+, Codex CLI 0.147.0+, Depot marketplace releases, macOS T3 Code desktop.

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

- Node install directory printed by `printf '/home/ned/.local/lib/node-%s-linux-x64\n' "$NED_NODE_VERSION"` — checksum-verified Node LTS files.
- `/home/ned/.local/node` — stable symlink used by systemd.
- `/home/ned/ai/t3-code/package.json` — private pinned T3 dependency.
- `/home/ned/ai/t3-code/package-lock.json` — exact npm dependency graph.
- `/home/ned/ai/t3-code/README.md` — upgrade, pairing, recovery, and log policy.
- `/home/ned/.config/systemd/user/ned-t3.service` — always-on T3 service.
- `/home/ned/.config/systemd/user/default.target.wants/ned-t3.service` — enablement symlink created by systemd.
- `/home/ned/.config/environment.d/20-ned-local-bin.conf` — stable user-service PATH.
- `/home/ned/.codex/` and `/home/ned/.claude/` — existing provider state and released plugin caches.

### Mac

- `/Applications/T3 Code (Alpha).app` — existing desktop client.
- T3 application support — paired remote environment metadata only; pairing material is handled by the app.

---

### Task 1: Install a checksum-verified user-scoped Node 24 LTS runtime

**Files:**
- Create: the exact Node directory printed from the verified `NED_NODE_VERSION` in Step 1.
- Create: `/home/ned/.local/node`
- Create: `/home/ned/.config/environment.d/20-ned-local-bin.conf`

**Interfaces:**
- Produces: `/home/ned/.local/node/bin/{node,npm,npx}` and a stable PATH for user services.

- [ ] **Step 1: Resolve the current Node 24 LTS patch from the official release index**

```bash
NED_NODE_VERSION="$(curl --fail --silent --show-error https://nodejs.org/dist/index.json | python3 -c 'import json,sys; print(next(x["version"] for x in json.load(sys.stdin) if x["version"].startswith("v24.") and x["lts"]))')"
printf '%s\n' "$NED_NODE_VERSION"
```

Expected: one `v24.x.y` value with a non-false LTS field. Stop if resolution is
empty or returns a non-v24 value.

- [ ] **Step 2: Download the archive and official checksum into a private temporary directory**

```bash
NED_NODE_TMP="$(mktemp -d /tmp/ned-node.XXXXXX)"
chmod 700 "$NED_NODE_TMP"
curl --fail --location --output "$NED_NODE_TMP/node.tar.xz" "https://nodejs.org/dist/$NED_NODE_VERSION/node-$NED_NODE_VERSION-linux-x64.tar.xz"
curl --fail --location --output "$NED_NODE_TMP/SHASUMS256.txt" "https://nodejs.org/dist/$NED_NODE_VERSION/SHASUMS256.txt"
```

- [ ] **Step 3: Verify the checksum before extraction**

```bash
cd "$NED_NODE_TMP"
rg "  node-$NED_NODE_VERSION-linux-x64.tar.xz$" SHASUMS256.txt > node.sha256
sed -i "s#node-$NED_NODE_VERSION-linux-x64.tar.xz#node.tar.xz#" node.sha256
sha256sum --check node.sha256
```

Expected: `node.tar.xz: OK`.

- [ ] **Step 4: Install without sudo and create the stable symlink**

```bash
install -d /home/ned/.local/lib
tar -C /home/ned/.local/lib -xJf "$NED_NODE_TMP/node.tar.xz"
ln -sfn "/home/ned/.local/lib/node-$NED_NODE_VERSION-linux-x64" /home/ned/.local/node
/home/ned/.local/node/bin/node --version
/home/ned/.local/node/bin/npm --version
```

- [ ] **Step 5: Configure user-service PATH and remove temporary files**

```bash
install -d /home/ned/.config/environment.d /home/ned/.local/share/Trash/files
printf '%s\n' 'PATH=/home/ned/.local/node/bin:/home/ned/.local/bin:/usr/local/bin:/usr/bin:/bin' > /home/ned/.config/environment.d/20-ned-local-bin.conf
systemctl --user set-environment PATH=/home/ned/.local/node/bin:/home/ned/.local/bin:/usr/local/bin:/usr/bin:/bin
mv "$NED_NODE_TMP" /home/ned/.local/share/Trash/files/node-install-20260811
```

- [ ] **Step 6: Verify explicit and user-service resolution**

```bash
/home/ned/.local/node/bin/node --version
systemd-run --user --wait --pipe /usr/bin/env PATH=/home/ned/.local/node/bin:/home/ned/.local/bin:/usr/bin:/bin node --version
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

- [ ] **Step 1: Resolve and record the current published T3 version**

```bash
install -d -m 700 /home/ned/ai/t3-code
cd /home/ned/ai/t3-code
NED_T3_VERSION="$(/home/ned/.local/node/bin/npm view t3 version)"
printf '%s\n' "$NED_T3_VERSION"
```

Stop if the result is empty or is not a valid semantic version.

- [ ] **Step 2: Write private package metadata and install exactly that version**

```json
{
  "name": "ned-t3-server",
  "private": true,
  "version": "1.0.0",
  "description": "Pinned T3 Code server installation for NED 9000",
  "dependencies": {}
}
```

Then run:

```bash
cd /home/ned/ai/t3-code
/home/ned/.local/node/bin/npm install --save-exact "t3@$NED_T3_VERSION"
```

- [ ] **Step 3: Verify the lockfile and CLI without starting a server**

```bash
/home/ned/.local/node/bin/npm ci --ignore-scripts=false
./node_modules/.bin/t3 --help
/home/ned/.local/node/bin/npm ls t3 --depth=0
```

Expected: npm reports exactly one pinned `t3` version and the CLI help exits 0.

- [ ] **Step 4: Document bounded upgrade and recovery commands**

`README.md` records: explicit Node/T3 paths; `npm ci`; manual version upgrades
using `npm install --save-exact`; service status/restart; `tailscale serve
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
Environment=PATH=/home/ned/.local/node/bin:/home/ned/.local/bin:/usr/local/bin:/usr/bin:/bin
UMask=0077
ExecStart=/home/ned/ai/t3-code/node_modules/.bin/t3 serve --tailscale-serve --tailscale-serve-port 8443
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
StandardOutput=null
StandardError=journal

[Install]
WantedBy=default.target
```

`StandardOutput=null` prevents pairing URLs emitted on stdout from entering the
journal. Pairing is performed interactively in Task 4.

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

- [ ] **Step 3: Run pairing interactively without tool capture or journaling**

In NED's existing interactive `ned` tmux session, run:

```bash
cd /home/ned/ai/t3-code
./node_modules/.bin/t3 pair --tailscale
```

Use the Mac T3 app to consume the displayed pairing URL/QR directly. Do not
paste it into chat or a shell transcript. After the Mac confirms pairing, stop
the interactive pair process cleanly.

- [ ] **Step 4: Enable and start the always-on service**

```bash
systemctl --user enable --now ned-t3.service
systemctl --user --no-pager --full status ned-t3.service
tailscale serve status
```

Expected: service active and Tailscale Serve HTTPS present on port 8443.

- [ ] **Step 5: Verify network containment**

```bash
tailscale funnel status
ss -ltnp | rg '8443|t3|node' || true
tailscale serve get-config --all
```

Expected: no Funnel; no T3 process bound to `0.0.0.0` or `[::]`; Serve targets
the T3 local service.

- [ ] **Step 6: Verify the journal contains no pairing authority**

```bash
if journalctl --user -u ned-t3.service --since '10 minutes ago' --no-pager | rg -i 'pair|token|secret|credential|https://.*auth'; then
  exit 1
fi
```

Expected: no matching output. If authority appears, stop the service, rotate
pairing through the T3 app, and fix logging before proceeding.

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

Expected: the requested plugin set is enabled for both. `ned` remains 1.7.1
until the separately validated `ned:operate` release is tagged and published;
do not claim the unreleased 1.8.0 checkout is installed.

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
ssh ned9000 'hostname; tmux list-sessions'
ssh ned-plain 'systemctl --user is-active ned-t3.service; tailscale serve status'
```

Expected: tmux maintenance and plain automation paths both work independently
of the T3 desktop UI.
