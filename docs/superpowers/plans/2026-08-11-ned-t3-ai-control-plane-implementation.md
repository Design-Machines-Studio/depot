# NED T3 AI Control Plane Implementation Plan

> **STATUS: SUPERSEDED / DO NOT EXECUTE AS WRITTEN**
>
> Live state observed 2026-08-12 already has `t3code.service` enabled and active,
> with T3 0.0.33 running from `/home/ned/.local/state/t3-code/runtime` and
> `127.0.0.1:3773` listening. Tailscale Serve maps tailnet port 8443 to that
> listener and retains a separate 9443-to-8099 route. The proposed
> `/home/ned/ai/t3-code` tree and `ned-t3.service` do not exist. Preserve the
> working service and both Serve routes. A future plan must inventory this live
> state, then explicitly choose adoption, migration, or replacement.

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
- `/home/ned/ai/t3-code/review/approved-package.json` — non-secret approval
  record binding the complete resolved dependency graph: every package name,
  exact version, resolved URL, npm SRI integrity, SHA-256 digest, and protected
  local artifact path, plus the reviewed lockfile digest.
- `/home/ned/ai/t3-code/review/cli-contract.json` — value-free command contract
  derived from the pinned installed CLI help; it binds the exact `serve`,
  `auth pairing create`, and `project add` forms used below.
- `/home/ned/ai/t3-code/review/active-release.json` — exact installed-file
  manifest and digest for the atomically activated release.
- `/home/ned/ai/t3-code/.artifacts/` — mode-0700 host-local package cache;
  ignored by Git and containing the exact reviewed tarball used by `npm ci`.
- `/home/ned/ai/t3-code/releases/<lock-sha256>/` — read-only installed release
  containing the approved `node_modules`, fixed supervisor, and runtime scripts.
- `/home/ned/ai/t3-code/current` — atomically replaced symlink to the one
  manifest-verified active release.
- `/home/ned/ai/t3-code/README.md` — upgrade, pairing, recovery, and log policy.
- `/home/ned/ai/t3-code/scripts/check-serve-containment.py` — reads a protected
  Serve config and emits only a boolean containment verdict.
- `/home/ned/ai/t3-code/scripts/verify-reviewed-package.py` — fail-closed
  verifier and artifact stager for the approved dependency graph, digests,
  integrity, protected paths, npm cache, and lockfile binding.
- `/home/ned/ai/t3-code/scripts/verify-installed-release.py` — creates and
  verifies the exact installed-file manifest, contained symlinks, permissions,
  active-release identity, supervisor bytes, and pinned CLI-help contract.
- `/home/ned/ai/t3-code/scripts/check-t3-listener.py` — value-free,
  fail-closed verifier of the actual T3 listener address, port, UID, and
  executable identity.
- `/home/ned/ai/t3-code/scripts/check-provider-session-processes.py` —
  value-free verifier that binds observed Codex and Claude process identities to
  their documented T3 session metadata.
- `/home/ned/ai/t3-code/scripts/check-ai-memory-config.py` — reads only the
  named ai-memory MCP entry from an exact provider config path and emits a
  value-free executable/path verdict without enumerating adjacent configuration.
- `/home/ned/ai/t3-code/scripts/run-t3-redacted.py` — fixed-argument T3
  supervisor with overlap-aware redaction and bounded protected logs.
- `/home/ned/ai/t3-code/scripts/audit-t3-log.py` — value-free log security and
  lifecycle audit.
- `/home/ned/.config/systemd/user/ned-t3.service` — always-on T3 service.
- `/home/ned/.local/state/t3/log/` — mode-0700 directory containing bounded,
  mode-0600 redacted application logs.
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
- Create: `/home/ned/ai/t3-code/review/candidate-graph.json`
- Create: `/home/ned/ai/t3-code/review/approved-package.json`
- Create: `/home/ned/ai/t3-code/review/cli-contract.json`
- Create: `/home/ned/ai/t3-code/review/active-release.json`
- Create: `/home/ned/ai/t3-code/scripts/verify-reviewed-package.py`
- Create: `/home/ned/ai/t3-code/scripts/verify-installed-release.py`
- Create: `/home/ned/ai/t3-code/tests/test_verify_reviewed_package.py`
- Create: `/home/ned/ai/t3-code/tests/test_verify_installed_release.py`
- Ignore: `/home/ned/ai/t3-code/.artifacts/`
- Ignore: `/home/ned/ai/t3-code/.install-staging/`
- Ignore: `/home/ned/ai/t3-code/releases/`
- Ignore: `/home/ned/ai/t3-code/current`

**Interfaces:**
- Consumes: Node runtime from Task 1.
- Produces: a reviewed dependency graph and a private candidate installation;
  Task 3 binds the supervisor into it and atomically activates `current`.

- [ ] **Step 1: Resolve a candidate version and record immutable metadata without executing it**

```bash
set -eu
install -d -m 700 /home/ned/ai/t3-code
cd /home/ned/ai/t3-code
install -d -m 700 .artifacts review scripts tests
NED_T3_VERSION="$(/usr/bin/npm view t3 version)"
test -n "$NED_T3_VERSION"
printf '%s\n' "$NED_T3_VERSION" > review/candidate-version.txt
/usr/bin/npm config get registry > review/candidate-registry.txt
/usr/bin/npm view "t3@$NED_T3_VERSION" dist.integrity --json > review/candidate-integrity.json
/usr/bin/npm view "t3@$NED_T3_VERSION" dist.tarball --json > review/candidate-tarball-url.json
/usr/bin/npm view "t3@$NED_T3_VERSION" engines --json > review/candidate-engines.json
```

Stop if the result is empty or invalid. Record the exact version, integrity,
tarball URL, engine requirement, query time, and registry in a review receipt.
Confirm the package identity against T3's official documentation before any
install command. These files contain no authority material and make the next
step independent of shell variables from this one.

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
set -eu
cd /home/ned/ai/t3-code
umask 077
NED_T3_VERSION="$(tr -d '\n' < review/candidate-version.txt)"
test -n "$NED_T3_VERSION"
NED_T3_PACK_DIR="/home/ned/ai/t3-code/.artifacts/candidate-$NED_T3_VERSION"
test ! -e "$NED_T3_PACK_DIR"
install -d -m 700 "$NED_T3_PACK_DIR"
printf '%s\n' "$NED_T3_PACK_DIR" > review/candidate-pack-dir.txt
/usr/bin/npm pack "t3@$NED_T3_VERSION" --ignore-scripts --json \
  --pack-destination "$NED_T3_PACK_DIR" > "$NED_T3_PACK_DIR/pack.json"
NED_T3_PACKED_NAME="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[0]["filename"])' "$NED_T3_PACK_DIR/pack.json")"
NED_T3_PACKED_TARBALL="$NED_T3_PACK_DIR/$NED_T3_PACKED_NAME"
test -f "$NED_T3_PACKED_TARBALL"
sha256sum "$NED_T3_PACKED_TARBALL" > "$NED_T3_PACK_DIR/archive.sha256"
tar -tf "$NED_T3_PACKED_TARBALL" > "$NED_T3_PACK_DIR/archive-files.txt"
```

Inspect the bounded file list, package manifest, declared scripts, archive paths,
and npm-reported integrity. Reject absolute/traversal paths, unexpected native
binaries, install scripts without a documented need, or a mismatch with the
recorded metadata. This root-tarball inspection is not an installation approval:
the complete resolved dependency graph must be staged and approved before any
code is installed or executed. The eventual approval record contains an ordered
artifact entry for every root and transitive package: package name, exact version,
resolved URL, npm SRI integrity, SHA-256 digest, and absolute protected local
path; it also records the exact package-lock digest and approval timestamp. It
contains no token, cookie, header, environment value, or npm configuration dump.

Implement `verify-reviewed-package.py` before installation. Its `stage-graph`
mode strictly parses the generated lockfile, rejects unknown/missing package
metadata, and fetches each resolved artifact only during the review phase. It
verifies lockfile SRI and a newly computed SHA-256, copies each artifact into the
mode-0700 `.artifacts/` store at mode 0600, seeds a protected npm cache from
those exact files, and atomically writes only `review/candidate-graph.json`.
Staging cannot create or overwrite `approved-package.json`.

After a human approves the exact candidate-graph digest, artifact list, and
lockfile digest, the separate `seal-approval` mode consumes that unchanged
candidate file and atomically creates `approved-package.json`. It refuses an
existing approval path, candidate or lockfile drift, absent action-time approval,
and a candidate generated by a different tool/schema version. Verification
rejects unknown/missing fields, lockfile entries without an approved artifact,
extra approved artifacts, symlinks, non-regular files, paths outside
`/home/ned/ai/t3-code/.artifacts`, wrong ownership or modes broader than 0600,
digest/SRI mismatch, cache drift, and lockfile drift. Normal success is quiet;
failure reports only the failed check, never package contents or
authority-shaped values.

Write failing tests first. They cover root and transitive digest/integrity
tampering, missing/extra graph nodes, path escape, symlink replacement,
permissive modes, malformed records, cache misses, lockfile drift, staging that
attempts to write an approval, sealing before action-time approval, candidate
mutation between review and sealing, an existing approval destination, and a
valid stage-review-seal transition.

After the root candidate has been reviewed, create the lockfile and stage the
complete graph in this independent fresh-shell block. This is still a
review-phase network operation; it must not install `node_modules`, execute
package lifecycle scripts, or create an approval record:

```bash
set -eu
cd /home/ned/ai/t3-code
NED_T3_VERSION="$(tr -d '\n' < review/candidate-version.txt)"
NED_T3_PACK_DIR="$(tr -d '\n' < review/candidate-pack-dir.txt)"
NED_T3_PACKED_NAME="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[0]["filename"])' "$NED_T3_PACK_DIR/pack.json")"
/usr/bin/npm install --package-lock-only --ignore-scripts \
  "$NED_T3_PACK_DIR/$NED_T3_PACKED_NAME"
python3 scripts/verify-reviewed-package.py stage-graph \
  --version "$NED_T3_VERSION" \
  --registry-file review/candidate-registry.txt \
  --integrity-file review/candidate-integrity.json \
  --tarball-url-file review/candidate-tarball-url.json \
  --pack-json "$NED_T3_PACK_DIR/pack.json" \
  --candidate-tarball "$NED_T3_PACK_DIR/$NED_T3_PACKED_NAME" \
  --lockfile package-lock.json \
  --artifact-dir /home/ned/ai/t3-code/.artifacts \
  --npm-cache /home/ned/ai/t3-code/.artifacts/npm-cache \
  --output review/candidate-graph.json
python3 scripts/verify-reviewed-package.py verify-candidate \
  --candidate review/candidate-graph.json --lockfile package-lock.json
test ! -e review/approved-package.json
```

Inspect the resulting lockfile and bounded, non-secret candidate artifact list.
Present their exact SHA-256 digests and obtain explicit approval for that exact
graph. Stop if staging needs an artifact not represented in the lockfile or if
the graph cannot be made complete. Only after approval, in the same action-time
session, seal the unchanged candidate:

```bash
set -eu
cd /home/ned/ai/t3-code
test ! -e review/approved-package.json
python3 scripts/verify-reviewed-package.py seal-approval \
  --candidate review/candidate-graph.json \
  --lockfile package-lock.json \
  --output review/approved-package.json \
  --approval-confirmed
python3 scripts/verify-reviewed-package.py verify \
  --approval review/approved-package.json --lockfile package-lock.json
```

`--approval-confirmed` is accepted only by `seal-approval`; it records no user
text or authority and is not inferred from the design's approval status.

- [ ] **Step 3: Install the approved graph into a private candidate release**

```bash
set -euo pipefail
cd /home/ned/ai/t3-code
NED_T3_REVIEW=/home/ned/ai/t3-code/review/approved-package.json
python3 scripts/verify-reviewed-package.py verify \
  --approval "$NED_T3_REVIEW" --lockfile package-lock.json
NED_T3_VERSION="$(python3 scripts/verify-reviewed-package.py field \
  --approval "$NED_T3_REVIEW" --name version)"
NED_T3_LOCK_SHA256="$(sha256sum package-lock.json | awk '{print $1}')"
NED_T3_CANDIDATE="/home/ned/ai/t3-code/.install-staging/$NED_T3_LOCK_SHA256"
test ! -e "$NED_T3_CANDIDATE"
install -d -m 700 /home/ned/ai/t3-code/.install-staging
install -d -m 700 "$NED_T3_CANDIDATE"
install -m 0600 package.json package-lock.json "$NED_T3_CANDIDATE/"
cd "$NED_T3_CANDIDATE"
NPM_CONFIG_REGISTRY=https://registry.invalid \
  /usr/bin/npm ci --offline --ignore-scripts \
    --cache /home/ned/ai/t3-code/.artifacts/npm-cache
python3 /home/ned/ai/t3-code/scripts/verify-reviewed-package.py verify \
  --approval "$NED_T3_REVIEW" --lockfile package-lock.json
/usr/bin/npm ls "t3@$NED_T3_VERSION" --depth=0
```

Expected: npm reports exactly one pinned reviewed version. Installation runs
only from the protected approved cache, with offline mode and an unusable
registry endpoint; any cache miss, network attempt, lockfile drift, or unapproved
graph node is a hard failure. The candidate is not executable through `current`
yet. If T3 requires a script-generated artifact, stop and review that single
script before executing it; never enable all scripts with
`--ignore-scripts=false`.

Task 3 adds the supervisor and verifier scripts, captures CLI help from this
exact candidate, builds the installed-file manifest, changes the sealed tree to
read-only modes, renames it to `releases/<lock-sha256>`, and atomically replaces
`current` only after a fresh exact-manifest verification.

- [ ] **Step 4: Document bounded upgrade and recovery commands**

`README.md` records: explicit Node/T3 paths and backend port 3773 versus
Tailscale HTTPS port 8443; offline `npm ci --offline
--ignore-scripts` with the protected reviewed cache; manual version upgrades using
the same stage/review/seal/install/activate sequence; atomic rollback of `current`
to a previously verified release; service status/restart; `tailscale serve
status`; `tailscale serve reset` as a confirmation-gated rollback; SSH/tmux
fallback; and the rule that pairing output is interactive only.

- [ ] **Step 5: Initialize and commit the private installation repository**

```bash
cd /home/ned/ai/t3-code
git init -b main
printf '%s\n' '.artifacts/' '.install-staging/' 'releases/' 'current' 'review/candidate-*' '*.log' > .gitignore
python3 -m unittest \
  tests.test_verify_reviewed_package \
  tests.test_verify_installed_release -v
git add package.json package-lock.json README.md .gitignore \
  review/approved-package.json \
  scripts/verify-reviewed-package.py scripts/verify-installed-release.py \
  tests/test_verify_reviewed_package.py tests/test_verify_installed_release.py
git commit -m "chore: pin NED T3 server"
```

---

### Task 3: Prepare the always-on systemd user service without starting it

**Files:**
- Create: `/home/ned/ai/t3-code/systemd/ned-t3.service`
- Create: `/home/ned/ai/t3-code/scripts/run-t3-redacted.py`
- Create: `/home/ned/ai/t3-code/scripts/audit-t3-log.py`
- Create: `/home/ned/ai/t3-code/scripts/check-t3-listener.py`
- Create: `/home/ned/ai/t3-code/scripts/check-serve-containment.py`
- Create: `/home/ned/ai/t3-code/scripts/check-provider-session-processes.py`
- Create: `/home/ned/ai/t3-code/scripts/check-ai-memory-config.py`
- Create: `/home/ned/ai/t3-code/tests/test_t3_redacted_log.py`
- Create: `/home/ned/ai/t3-code/tests/test_t3_listener.py`
- Create: `/home/ned/ai/t3-code/tests/test_serve_containment.py`
- Create: `/home/ned/ai/t3-code/tests/test_provider_session_processes.py`
- Create: `/home/ned/ai/t3-code/tests/test_ai_memory_config.py`
- Install: `/home/ned/.config/systemd/user/ned-t3.service`

**Interfaces:**
- Consumes: approved private candidate installation from Task 2.
- Produces: exact-manifest-bound `current` release and a disabled-but-valid
  service ready for the pairing gate.

- [ ] **Step 1: Write failing tests for every trusted verifier**

Before implementation, write hostile fixtures and prove the focused suite fails
because the modules do not exist. The tests cover:

- listener: missing/duplicate sockets, loopback IPv4/IPv6, wildcard binds,
  wrong backend port, wrong UID/executable, inaccessible `/proc`, changed
  supervisor ancestry, and malformed `ss` rows;
- Serve/Funnel: exact external HTTPS 8443 to `http://127.0.0.1:3773`, a wrong
  target/port/path, extra handler, Funnel/public flag, malformed/oversized JSON,
  symlink, wrong owner, and group/other-readable protected inputs;
- provider sessions: missing/duplicate/stale PID, wrong UID, resolved executable
  mismatch, cgroup/ancestry mismatch, session/provider mismatch, malformed or
  permissive metadata, and value-free output on an authority-shaped fixture;
- ai-memory: exact Codex TOML and Claude JSON entries, wrong executable/path,
  authority-bearing entry fields, adjacent secret-shaped entries that are never
  emitted, symlink, wrong owner/mode, and malformed config;
- installed release: missing/extra/changed files, escaping symlinks, mode drift,
  wrong active symlink, changed supervisor bytes, CLI-help digest drift, and a
  valid atomic activation manifest.

```bash
set -eu
cd /home/ned/ai/t3-code
if python3 -m unittest \
  tests.test_t3_listener \
  tests.test_serve_containment \
  tests.test_provider_session_processes \
  tests.test_ai_memory_config \
  tests.test_verify_installed_release -v; then
  printf '%s\n' 'expected verifier tests to fail before implementation' >&2
  exit 1
fi
```

- [ ] **Step 2: Implement bounded logging and value-free verifiers**

`run-t3-redacted.py` is a standard-library supervisor with no user-controlled
arguments. It launches this fixed argv with `shell=False`:

```text
/home/ned/ai/t3-code/current/node_modules/.bin/t3 serve --host 127.0.0.1 --port 3773 --base-dir /home/ned/.local/state/t3/server --tailscale-serve --tailscale-serve-port 8443
```

The exact ordering and availability of `--port`, `--base-dir`,
`--tailscale-serve`, and `--tailscale-serve-port` must match the pinned
`review/cli-contract.json`; no service file or supervisor is rendered until the
captured help proves that contract. Backend 3773 and external Tailscale HTTPS
8443 are distinct constants and may never be substituted for one another.

It captures child stdout/stderr internally, applies overlap-aware streaming
redaction before any write, and never copies raw child bytes to its own standard
streams. Redaction covers pairing URLs/connection strings, query parameters,
URL userinfo, bearer/cookie/assignment/JSON credential forms, PEM material, and
provider authority patterns. The log directory is mode 0700, files are mode
0600, symlinks are rejected, each file is capped at 1 MiB, and at most three
rotations are retained. The supervisor also writes value-free structured events
for supervisor start, child start, redaction applied, signal received, and child
exit; it records neither child argv nor environment.

`audit-t3-log.py` streams every byte of the protected current log and all three
rotations, with an absolute 4 MiB total-retention ceiling derived from the
rotation policy. It fails closed if any retained byte cannot be read, the set is
missing/oversized, a file is duplicated, replaced during collection, symlinked,
wrongly owned, or too broadly permissioned, or if structured lifecycle events
are malformed/missing or any credential-shaped content remains. It prints only
a boolean verdict and failed check name, never a matching line. Tests use
synthetic credentials and prove split-chunk redaction, full-set scanning,
boundary replacement, bounded rotation, value-free lifecycle retention,
permission/symlink rejection, and silent handling of matching authority.

`check-t3-listener.py` runs a fixed `ss -H -ltnp` collection and inspects the
corresponding `/proc/<pid>` identity without printing either raw socket rows or
process arguments. It fails closed unless exactly one TCP listener on backend
port 3773 is bound to `127.0.0.1` or `[::1]`, no listener for that port is bound to
`0.0.0.0` or `[::]`, the listener UID is `ned`, and its executable is the
administrator-installed `/usr/bin/node` launched by the fixed T3 supervisor.
Its output is only `listener_contained=true` or a named failed check.

`check-serve-containment.py` accepts two exact mode-0600, `ned`-owned regular
files: `tailscale serve get-config --all` JSON and `tailscale funnel status
--json`. It never prints or copies either document. It requires exactly one T3
Serve HTTPS endpoint on external port 8443 mapped to
`http://127.0.0.1:3773`, rejects redirects, alternate targets or hostnames,
fallbacks, extra paths, public/Funnel mappings, and every unrecognized schema
field.

`check-provider-session-processes.py` and `check-ai-memory-config.py` implement
the exact value-free checks described in Tasks 5 and 6. No verifier accepts raw
JSON/TOML through argv, prints matching values, enumerates neighboring entries,
or converts an inaccessible input into success.

```bash
set -eu
cd /home/ned/ai/t3-code
python3 -m unittest \
  tests.test_t3_redacted_log \
  tests.test_t3_listener \
  tests.test_serve_containment \
  tests.test_provider_session_processes \
  tests.test_ai_memory_config \
  tests.test_verify_installed_release -v
```

- [ ] **Step 3: Capture pinned CLI help, seal the installed release, and activate it**

Run only the already approved, offline-installed candidate. Capture help into a
mode-0700 review directory without displaying it, reject credential-shaped or
over-budget output, and bind every help file digest into `cli-contract.json`:

```bash
set -euo pipefail
cd /home/ned/ai/t3-code
umask 077
NED_T3_LOCK_SHA256="$(sha256sum package-lock.json | awk '{print $1}')"
NED_T3_CANDIDATE="/home/ned/ai/t3-code/.install-staging/$NED_T3_LOCK_SHA256"
NED_T3_HELP=/home/ned/ai/t3-code/review/cli-help
test -d "$NED_T3_CANDIDATE/node_modules"
test ! -e "$NED_T3_HELP"
install -d -m 700 "$NED_T3_HELP" "$NED_T3_CANDIDATE/scripts"
"$NED_T3_CANDIDATE/node_modules/.bin/t3" --help > "$NED_T3_HELP/t3.txt"
"$NED_T3_CANDIDATE/node_modules/.bin/t3" serve --help > "$NED_T3_HELP/serve.txt"
"$NED_T3_CANDIDATE/node_modules/.bin/t3" auth pairing create --help > "$NED_T3_HELP/auth-pairing-create.txt"
"$NED_T3_CANDIDATE/node_modules/.bin/t3" project --help > "$NED_T3_HELP/project.txt"
"$NED_T3_CANDIDATE/node_modules/.bin/t3" project add --help > "$NED_T3_HELP/project-add.txt"
python3 scripts/verify-installed-release.py bind-cli-contract \
  --help-dir "$NED_T3_HELP" \
  --backend-port 3773 --serve-https-port 8443 \
  --state-dir /home/ned/.local/state/t3/server \
  --output review/cli-contract.json
install -m 0500 scripts/run-t3-redacted.py "$NED_T3_CANDIDATE/scripts/"
for script in audit-t3-log.py check-t3-listener.py check-serve-containment.py \
  check-provider-session-processes.py check-ai-memory-config.py \
  verify-installed-release.py; do
  install -m 0500 "scripts/$script" "$NED_T3_CANDIDATE/scripts/$script"
done
python3 scripts/verify-installed-release.py seal \
  --candidate "$NED_T3_CANDIDATE" \
  --approval review/approved-package.json \
  --cli-contract review/cli-contract.json \
  --output review/active-release.json
python3 scripts/verify-installed-release.py activate \
  --candidate "$NED_T3_CANDIDATE" \
  --release-root /home/ned/ai/t3-code/releases \
  --active-link /home/ned/ai/t3-code/current \
  --manifest review/active-release.json
python3 current/scripts/verify-installed-release.py verify-active \
  --active-link /home/ned/ai/t3-code/current \
  --manifest review/active-release.json
```

`bind-cli-contract` fails unless the exact pinned help supports the fixed
loopback `serve` invocation, persistent `--base-dir`, supported `auth pairing
create`, and exact server-side `project add --base-dir <directory>
<absolute-path>` command. It also fails if a later CLI changes the reviewed
project-management form. `seal` records every regular-file digest and contained
symlink target,
including all `node_modules` and supervisor bytes. `activate` changes the staged
tree to read-only file/directory modes, renames it to
`releases/<lock-sha256>`, verifies it again, and atomically replaces `current`;
it never mutates an existing release. Any later drift blocks service start.

- [ ] **Step 4: Write the service unit**

```ini
[Unit]
Description=NED T3 Code server over Tailscale Serve
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/ned/ai/t3-code/current
Environment=HOME=/home/ned
Environment=PATH=/home/ned/.local/bin:/usr/local/bin:/usr/bin:/bin
UMask=0077
ExecStartPre=/usr/bin/install -d -m 0700 /home/ned/.local/state/t3/log
ExecStartPre=/usr/bin/python3 /home/ned/ai/t3-code/current/scripts/verify-installed-release.py verify-active --active-link /home/ned/ai/t3-code/current --manifest /home/ned/ai/t3-code/review/active-release.json
ExecStart=/usr/bin/python3 /home/ned/ai/t3-code/current/scripts/run-t3-redacted.py
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
StandardOutput=null
StandardError=null

[Install]
WantedBy=default.target
```

The supervisor never emits raw application streams, so pairing or provider
authority cannot enter the journal. systemd records service transitions and exit
status; the protected bounded log retains redacted application context plus
value-free security/lifecycle events. Pairing is performed interactively in
Task 4 and bypasses all captured logging. The pre-start verifier emits only
`active_release_verified=true` or a named failed check.

- [ ] **Step 5: Validate and install without enabling or starting**

```bash
set -eu
cd /home/ned/ai/t3-code
systemd-analyze --user verify /home/ned/ai/t3-code/systemd/ned-t3.service
python3 -m unittest \
  tests.test_t3_redacted_log \
  tests.test_t3_listener \
  tests.test_serve_containment \
  tests.test_provider_session_processes \
  tests.test_ai_memory_config \
  tests.test_verify_installed_release -v
python3 scripts/verify-installed-release.py verify-active \
  --active-link /home/ned/ai/t3-code/current \
  --manifest review/active-release.json
install -m 0644 /home/ned/ai/t3-code/systemd/ned-t3.service /home/ned/.config/systemd/user/ned-t3.service
systemctl --user daemon-reload
if systemctl --user is-enabled ned-t3.service; then
  printf '%s\n' 'ned-t3 unexpectedly enabled before pairing gate' >&2
  exit 1
else
  status=$?
  test "$status" -eq 1
fi
if systemctl --user is-active ned-t3.service; then
  printf '%s\n' 'ned-t3 unexpectedly active before pairing gate' >&2
  exit 1
else
  status=$?
  test "$status" -eq 3
fi
```

- [ ] **Step 6: Commit every reviewed service and verifier surface**

```bash
set -eu
cd /home/ned/ai/t3-code
git add systemd/ned-t3.service review/cli-contract.json review/cli-help \
  review/active-release.json \
  scripts/run-t3-redacted.py scripts/audit-t3-log.py \
  scripts/check-t3-listener.py scripts/check-serve-containment.py \
  scripts/check-provider-session-processes.py scripts/check-ai-memory-config.py \
  scripts/verify-installed-release.py \
  tests/test_t3_redacted_log.py tests/test_t3_listener.py \
  tests/test_serve_containment.py tests/test_provider_session_processes.py \
  tests/test_ai_memory_config.py tests/test_verify_installed_release.py
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
set -eu
umask 077
NED_T3_BASELINE="$(mktemp -d /tmp/ned-t3-network-baseline.XXXXXX)"
trap 'rm -rf -- "$NED_T3_BASELINE"' EXIT HUP INT TERM
tailscale serve get-config "$NED_T3_BASELINE/serve.json" --all
tailscale funnel status --json > "$NED_T3_BASELINE/funnel.json"
chmod 0600 "$NED_T3_BASELINE/serve.json" "$NED_T3_BASELINE/funnel.json"
python3 /home/ned/ai/t3-code/current/scripts/check-serve-containment.py \
  --serve-config "$NED_T3_BASELINE/serve.json" \
  --funnel-status "$NED_T3_BASELINE/funnel.json" \
  --require-empty
python3 /home/ned/ai/t3-code/current/scripts/check-t3-listener.py \
  --port 3773 --require-absent
rm -rf -- "$NED_T3_BASELINE"
trap - EXIT HUP INT TERM
```

Expected: value-free verdicts prove no Serve, Funnel, or backend listener. Raw
Serve/Funnel documents are protected, never displayed, and removed on success
or failure.

- [ ] **Step 2: Request immediate confirmation**

Explain that the next command configures a tailnet-only HTTPS endpoint through
Tailscale Serve, not a public Funnel. Do not continue until the user explicitly
confirms this immediate action.

- [ ] **Step 3: Run pairing in a disposable non-recorded terminal**

Open a dedicated interactive terminal whose scrollback, shell history, and
session recording are disabled. Do not use the existing persistent tmux
session, an agent tool, or `script`. Re-verify `review/cli-contract.json`, then
run the supported pinned `serve` command against the same persistent state and
ports the service will use:

```bash
set -euo pipefail
umask 077
cd /home/ned/ai/t3-code
python3 current/scripts/verify-installed-release.py verify-active \
  --active-link /home/ned/ai/t3-code/current \
  --manifest review/active-release.json
./current/node_modules/.bin/t3 serve \
  --host 127.0.0.1 \
  --port 3773 \
  --base-dir /home/ned/.local/state/t3/server \
  --tailscale-serve \
  --tailscale-serve-port 8443
```

Use the Mac T3 app to consume the displayed pairing URL/QR directly. Do not
paste it into chat or a shell transcript. After the Mac confirms pairing, stop
the interactive server cleanly and run
`python3 current/scripts/check-t3-listener.py --port 3773 --require-absent` to
prove backend port 3773 is free. Then close the
disposable terminal, and verify that no pairing material remains in history or
scrollback. This is the supported initial `serve` pairing flow. Later pairings
use the exact pinned `t3 auth pairing create` command from
`review/cli-contract.json` while the persistent service is active, also only in
a non-recorded terminal. Both flows use
`/home/ned/.local/state/t3/server`; a different or implicit state directory is a
hard stop.

After the persistent service is active, any additional pairing uses this exact
command in another disposable non-recorded terminal. Its output is consumed
directly by the Mac app and is never redirected, copied, or recorded:

```bash
set -euo pipefail
umask 077
cd /home/ned/ai/t3-code
./current/node_modules/.bin/t3 auth pairing create \
  --base-dir /home/ned/.local/state/t3/server
```

- [ ] **Step 4: Enable and start the always-on service**

```bash
set -eu
systemctl --user enable --now ned-t3.service
systemctl --user is-enabled --quiet ned-t3.service
systemctl --user is-active --quiet ned-t3.service
```

Expected: service enabled and active. Network claims wait for the protected
structured proof in the next step.

- [ ] **Step 5: Verify network containment**

```bash
set -eu
umask 077
NED_T3_NETWORK_PROOF="$(mktemp -d /tmp/ned-t3-network-proof.XXXXXX)"
trap 'rm -rf -- "$NED_T3_NETWORK_PROOF"' EXIT HUP INT TERM
tailscale serve get-config "$NED_T3_NETWORK_PROOF/serve.json" --all
tailscale funnel status --json > "$NED_T3_NETWORK_PROOF/funnel.json"
chmod 0600 "$NED_T3_NETWORK_PROOF/serve.json" "$NED_T3_NETWORK_PROOF/funnel.json"
python3 /home/ned/ai/t3-code/current/scripts/check-t3-listener.py \
  --port 3773 --uid "$(id -u ned)" --executable /usr/bin/node \
  --supervisor /home/ned/ai/t3-code/current/scripts/run-t3-redacted.py
python3 /home/ned/ai/t3-code/current/scripts/check-serve-containment.py \
  --serve-config "$NED_T3_NETWORK_PROOF/serve.json" \
  --funnel-status "$NED_T3_NETWORK_PROOF/funnel.json" \
  --https-port 8443 --backend http://127.0.0.1:3773
rm -rf -- "$NED_T3_NETWORK_PROOF"
trap - EXIT HUP INT TERM
```

Expected: the listener verifier proves the actual Node backend socket is
loopback-only on 3773 and owned by `ned`; the separate protected-config verifier
proves tailnet-only Serve HTTPS 8443 maps exactly to
`http://127.0.0.1:3773`; and parsed Funnel JSON proves there is no public
mapping. A human `ss` inspection may be collected separately as bounded
diagnostics, but cannot substitute for either verifier or turn a collection
failure into success.

- [ ] **Step 6: Audit bounded logs without exposing matching authority**

```bash
set -euo pipefail
cd /home/ned/ai/t3-code
python3 current/scripts/audit-t3-log.py \
  --log-dir /home/ned/.local/state/t3/log \
  --max-total-bytes 4194304 \
  --require-complete-retained-set \
  --require-event child_start
journalctl --user -u ned-t3.service --since '10 minutes ago' \
  --no-pager -n 200 -o json \
  | python3 current/scripts/audit-t3-log.py --journal-json --max-bytes 262144
```

Expected: both commands emit only a clean boolean verdict. The protected-log
audit reads every byte of the complete bounded retained set, proves a retained
child-start event, and rejects credential-shaped residue;
the journal audit proves no raw application stream escaped the supervisor. A
missing, unreadable, malformed, stale, or over-budget collection is a failure,
not an empty-success case. If either audit fails, stop the service, rotate
pairing through the T3 app, and fix logging before proceeding.

- [ ] **Step 7: Verify pairing-state ownership without reading values**

The NED server state is the pinned CLI contract's exact
`/home/ned/.local/state/t3/server`; verify that directory without listing child
names or values. Identify the exact Mac client-state path from the pinned desktop
version's documentation or UI, never a glob. Require the Mac state to be owned
by `trav`, the NED state to be owned by `ned`, and neither to grant group or
other access. Record only the already-approved top-level path, owner, and mode—
never names or contents of credential-bearing child files. Stop the service and
correct permissions if either check fails.

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

Before this check, obtain the exact provider session identifiers and process
metadata through T3's current documented value-free session-inspection interface.
Do not guess a state path, glob provider directories, or print process arguments.
Store the minimal provider/session/PID association in a mode-0600 file under
`/home/ned/.local/state/t3/` owned by `ned`; stop if T3 cannot provide a binding.
The verifier checks that each recorded PID is a live `ned` process, has the
expected provider executable identity, is in the T3 service cgroup/ancestry, and
matches the documented T3 session association. It emits only session provider,
PID, UID, executable identity, and a boolean verdict.

On NED:

```bash
/home/ned/ai/t3-code/current/scripts/check-provider-session-processes.py \
  --session-metadata /home/ned/.local/state/t3/provider-session-identities.json \
  --provider codex --executable /home/ned/.local/bin/codex --uid "$(id -u ned)"
/home/ned/ai/t3-code/current/scripts/check-provider-session-processes.py \
  --session-metadata /home/ned/.local/state/t3/provider-session-identities.json \
  --provider claude --executable /home/ned/.local/bin/claude --uid "$(id -u ned)"
```

On the Mac:

```bash
ps -axo pid=,uid=,comm= | awk '($3 ~ /(^|\/)(codex|claude)$/) {print $1, $2, $3}' | sed -n '1,80p'
```

Interpret the Mac's T3 UI support processes separately. Acceptance requires the
two documented T3 sessions to bind to the verified NED PIDs, not that every Mac
AI application is closed. The Mac listing is diagnostic only and never prints
arguments or establishes the NED session binding.

---

### Task 6: Install released Depot plugins for NED Codex and verify both providers

**Files:**
- Modify: `/home/ned/.codex` marketplace/plugin configuration.
- Read: `/home/ned/.claude` released Depot installation.

**Interfaces:**
- Produces: the same everyday released Depot surfaces in NED Codex and Claude.

- [ ] **Step 1: Add the canonical Depot marketplace to Codex**

```bash
/home/ned/.local/bin/codex plugin marketplace add Design-Machines-Studio/depot --ref main --json
/home/ned/.local/bin/codex plugin marketplace list
```

Expected: marketplace name `depot` backed by the canonical Git repository, not
the local `/home/ned/ai/depot` checkout.

- [ ] **Step 2: Install the approved everyday plugin set**

```bash
for plugin in ned pipeline dm-review assembly live-wires openrouter workflow-kernel airlift; do
  /home/ned/.local/bin/codex plugin add "$plugin@depot" --json
done
```

If dependency resolution installs additional Depot plugins, retain them and
record them. Do not install a local checkout as the daily runtime.

- [ ] **Step 3: Compare released versions across providers**

```bash
/home/ned/.local/bin/codex plugin list | rg '@depot|Marketplace `depot`'
/home/ned/.local/bin/claude plugin list | sed -n '1,220p'
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

Do not print, grep, serialize, or ask a provider to display either full config.
Run the exact value-free parser directly on NED:

```bash
set -eu
/home/ned/ai/t3-code/current/scripts/check-ai-memory-config.py \
  --provider codex \
  --config /home/ned/.codex/config.toml \
  --server-name ai-memory \
  --executable /home/ned/.local/bin/uv \
  --project-root /home/ned/ai/ai-memory \
  --uid "$(id -u ned)"
/home/ned/ai/t3-code/current/scripts/check-ai-memory-config.py \
  --provider claude \
  --config /home/ned/.claude.json \
  --server-name ai-memory \
  --executable /home/ned/.local/bin/uv \
  --project-root /home/ned/ai/ai-memory \
  --uid "$(id -u ned)"
```

Each invocation emits only `ai_memory_binding=true` or a named failed check. It
reads only the exact named entry, rejects authority-bearing `env`, header, URL,
or credential fields in that entry, and never enumerates or prints adjacent MCP
configuration. Do not write a test observation. The native Mac ai-memory graph
is not valid evidence for this check.

---

### Task 7: Add project workspaces and prove remote persistence

**Files:**
- Modify: T3 paired-environment workspace list.
- Create/remove: disposable NED worktree and `/tmp/t3-survival-*` evidence.

**Interfaces:**
- Produces: verified remote files, terminals, images, worktrees, and surviving sessions.

- [ ] **Step 1: Add project roots with the pinned server-side CLI**

The remote GUI does not own project registration. First verify that
`review/cli-contract.json` still binds the active release's help and the exact
`project add --base-dir <directory> <absolute-path>` form. The pinned CLI has no
`project list` subcommand, so this plan does not invent or call one. Then run
these commands
on NED against the same persistent state as the service:

```bash
set -eu
cd /home/ned/ai/t3-code
python3 current/scripts/verify-installed-release.py verify-active \
  --active-link /home/ned/ai/t3-code/current \
  --manifest review/active-release.json
for project_root in \
  /home/ned/assembly/assembly \
  /home/ned/assembly/assembly-baseplate \
  /home/ned/assembly/assembly-baseplate-2 \
  /home/ned/sites/travisgertz \
  /home/ned/sites/burnfund \
  /home/ned/sites/livewires \
  /home/ned/ai/depot \
  /home/ned/ai/ned-ops; do
  test -d "$project_root"
  ./current/node_modules/.bin/t3 project add \
    --base-dir /home/ned/.local/state/t3/server \
    "$project_root"
done
```

Each exact `project add` command must exit zero. Verify the eight roots are
visible in the paired Mac UI without copying project metadata into chat or a
receipt; restart the service once and verify the same eight roots remain. If the
pinned help does not support the exact command, any command fails, any root is
missing after restart, or an unapproved root appears, stop and update the
reviewed CLI contract before adding anything else. Do not add `/home/ned` as a
blanket workspace.

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

Confirm the path appears on NED and nowhere under the Mac's project roots. At
cleanup time, require an empty `git -C .worktrees/t3-verification status
--porcelain`, exact `git worktree list --porcelain` binding to that path, and
`git rev-list --count main..verify/t3-remote` equal to zero. Present those
value-free checks and request immediate confirmation before retirement. Only
then use `git worktree remove .worktrees/t3-verification` followed by the
non-forcing `git branch -d verify/t3-remote`; stop on any changed action-time
identity or failed check.

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
