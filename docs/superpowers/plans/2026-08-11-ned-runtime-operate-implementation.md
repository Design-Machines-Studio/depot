# NED Runtime and `ned:operate` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a version-controlled NED runtime registry and `nedctl` operator CLI, restore the approved persistent project set, and add the guarded `ned:operate` skill to Depot.

**Architecture:** `/home/ned/ai/ned-ops` is a private host-local repository containing a standard-library Python CLI, declarative inventory, systemd user units, and NED-only runtime wrappers. Depot contains only the portable operational skill and guardrails; it discovers live machine details through `nedctl` instead of shipping credentials or mutable host state.

**Tech Stack:** Python 3.12 standard library, `unittest`, rootless Docker Compose, DDEV, systemd user units, Caddy, Depot Markdown/JSON manifests.

## Global Constraints

- Normal project operations run as NED user `ned`; Caddy and administrative changes run as `trav`.
- Keep Assembly projects as independent checkouts, Compose projects, ports, data directories, and worktrees.
- Never invoke host Go for Assembly verification; project development remains Docker-only.
- Do not clean, reset, commit, or otherwise alter the existing dirty Travis Gertz checkout.
- Do not modify or push the Live Wires repository merely to host the NED preview.
- No command deletes volumes, databases, repositories, or configuration implicitly.
- Move `designmachines` and `farewell` to user trash only after a fresh clean/unpushed audit; stop if either audit fails.
- Public exposure, DNS, Cloudflare, credentials, production, and DigitalOcean retirement are outside this plan.
- Logs shown to agents are bounded and redacted.
- No secrets may enter `inventory.json`, Depot, command arguments, receipts, or unbounded output.
- Depot begins at approved design commit `67fbaac`; preserve unrelated changes if HEAD has moved.

---

## File map

### `/home/ned/ai/ned-ops` (new private host-local Git repository)

- `pyproject.toml` — package metadata and `nedctl` entry point.
- `inventory.json` — non-secret paths, runtimes, domains, ports, persistence, and health probes.
- `nedops/model.py` — immutable inventory types and validation.
- `nedops/inventory.py` — JSON loading and project lookup.
- `nedops/commands.py` — allowlisted Compose and DDEV command construction.
- `nedops/runner.py` — bounded execution, DDEV lock, and redaction.
- `nedops/health.py` — loopback and route probes.
- `nedops/cli.py` — operator commands.
- `tests/` — standard-library unit tests.
- `projects/dm006/compose.override.yml` — NED-only restart policy for prototype services.
- `projects/dm021/compose.override.yml` — NED-only restart policy for Baseplate services.
- `projects/dm022/compose.override.yml` — NED-only restart policy for Baseplate 2 services.
- `projects/livewires/` — external static preview build; Live Wires checkout remains untouched.
- `systemd/` — per-project user unit, target, and ordering drop-ins.
- `scripts/install-user-units.sh` — idempotent unit and launcher installer.

### `/home/ned/ai/depot`

- `plugins/ned/skills/operate/SKILL.md` — guarded operator workflow.
- `plugins/ned/skills/operate/references/ned-runtime.md` — runtime and recovery contract.
- `description-evals/ned-operate.json` — positive and negative trigger cases.
- Canonical Claude manifests — skill registration and version `1.8.0`.
- Generated Codex manifests and search index — regenerated with repository tools.

### System state

- `/home/ned/.config/systemd/user/` — installed user units.
- `/home/ned/.local/bin/nedctl` — launcher symlink.
- `/etc/caddy/Caddyfile` — explicit Design Machines routes and unknown-host 404.
- `/home/ned/sites/burnfund` — transferred DDEV site with nested plugin repository intact.

---

### Task 1: Initialize the operations repository and inventory model

**Files:**
- Create: `/home/ned/ai/ned-ops/pyproject.toml`
- Create: `/home/ned/ai/ned-ops/.gitignore`
- Create: `/home/ned/ai/ned-ops/README.md`
- Create: `/home/ned/ai/ned-ops/nedops/{__init__,model,inventory}.py`
- Create: `/home/ned/ai/ned-ops/tests/test_inventory.py`

**Interfaces:**
- Produces: `Project`, `HealthProbe`, `Inventory`, `load_inventory(path: Path) -> Inventory`, `Inventory.project(project_id: str) -> Project`.

- [ ] **Step 1: Create the repository skeleton**

```bash
mkdir -p /home/ned/ai/ned-ops/nedops /home/ned/ai/ned-ops/tests
cd /home/ned/ai/ned-ops
git init -b main
```

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "ned-ops"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
nedctl = "nedops.cli:main"
```

- [ ] **Step 2: Write failing validation tests**

```python
def test_rejects_duplicate_domain_and_port(self):
    path = self.write_inventory([
        self.project("one", domain="one.example.test", port=8091),
        self.project("two", domain="one.example.test", port=8091),
    ])
    with self.assertRaisesRegex(ValueError, "duplicate domain.*duplicate port"):
        load_inventory(path)

def test_rejects_secret_shaped_environment_key(self):
    project = self.project("one", domain="one.example.test", port=8091)
    project["environment"] = {"API_TOKEN": "must-not-be-here"}
    with self.assertRaisesRegex(ValueError, "secret-shaped key"):
        load_inventory(self.write_inventory([project]))
```

- [ ] **Step 3: Prove the tests fail before implementation**

```bash
cd /home/ned/ai/ned-ops
python3 -m unittest tests.test_inventory -v
```

Expected: import failure for `nedops.inventory`.

- [ ] **Step 4: Implement frozen models and strict JSON validation**

```python
@dataclass(frozen=True)
class HealthProbe:
    url: str | None = None
    expected_status: int = 200
    host_header: str | None = None

@dataclass(frozen=True)
class Project:
    id: str
    path: Path
    runtime: str
    persistent: bool
    enabled: bool
    domains: tuple[str, ...] = ()
    port: int | None = None
    compose_files: tuple[Path, ...] = ()
    environment: dict[str, str] = field(default_factory=dict)
    health: HealthProbe = field(default_factory=HealthProbe)

@dataclass(frozen=True)
class Inventory:
    schema_version: int
    projects: tuple[Project, ...]

    def project(self, project_id: str) -> Project:
        for project in self.projects:
            if project.id == project_id:
                return project
        raise KeyError(project_id)
```

`load_inventory()` accepts schema version 1 and runtime values `compose`,
`ddev`, `static-compose`, `ephemeral`, `direct`, `deferred`, and `removed`.
It rejects malformed IDs, relative paths, ports outside 1024-65535, duplicate
IDs/domains/non-null ports, and environment keys containing `TOKEN`, `SECRET`,
`PASSWORD`, `PASS`, `KEY`, or `CREDENTIAL`. Compose and static-compose records
must declare at least one absolute `compose_files` path; other runtimes reject
non-empty `compose_files`.

- [ ] **Step 5: Run tests and commit**

```bash
cd /home/ned/ai/ned-ops
python3 -m unittest tests.test_inventory -v
git add pyproject.toml .gitignore README.md nedops tests
git commit -m "feat: establish NED operations inventory"
```

---

### Task 2: Add allowlisted runtime commands and redacted execution

**Files:**
- Create: `/home/ned/ai/ned-ops/nedops/commands.py`
- Create: `/home/ned/ai/ned-ops/nedops/runner.py`
- Create: `/home/ned/ai/ned-ops/tests/test_commands.py`
- Create: `/home/ned/ai/ned-ops/tests/test_redaction.py`

**Interfaces:**
- Consumes: `Project`.
- Produces: `CommandSpec`, `build_command(project, operation, lines=120)`, `run(spec, timeout)`, and `redact(text)`.

- [ ] **Step 1: Write failing exact-command and redaction tests**

```python
def test_dm022_uses_distinct_compose_identity(self):
    command = build_command(self.dm022, "start")
    self.assertEqual(command.argv, (
        "docker", "compose", "--project-name", "dm022",
        "-f", "/home/ned/assembly/assembly-baseplate-2/docker-compose.yml",
        "-f", "/home/ned/ai/ned-ops/projects/dm022/compose.override.yml",
        "up", "-d",
    ))
    self.assertEqual(command.env["ASSEMBLY_DEV_PORT"], "8092")

def test_ddev_logs_are_bounded(self):
    self.assertEqual(
        build_command(self.travisgertz, "logs", lines=80).argv,
        ("ddev", "logs", "-s", "web", "--tail", "80"),
    )

def test_redacts_authority_material(self):
    clean = redact('OPENROUTER_API_KEY=abc Bearer xyz {"token":"123"}')
    for secret in ("abc", "xyz", "123"):
        self.assertNotIn(secret, clean)
```

- [ ] **Step 2: Run tests and verify import failures**

```bash
python3 -m unittest tests.test_commands tests.test_redaction -v
```

- [ ] **Step 3: Implement command construction without a shell**

```python
@dataclass(frozen=True)
class CommandSpec:
    argv: tuple[str, ...]
    cwd: Path
    env: dict[str, str]

def build_command(project: Project, operation: str, lines: int = 120) -> CommandSpec:
    if not project.enabled:
        raise RuntimeError(f"{project.id} is not enabled")
    if project.runtime in {"compose", "static-compose"}:
        files = tuple(part for path in project.compose_files for part in ("-f", str(path)))
        base = ("docker", "compose", "--project-name", project.id) + files
        argv = {
            "start": base + ("up", "-d"),
            "stop": base + ("stop",),
            "restart": base + ("restart",),
            "status": base + ("ps", "--format", "json"),
            "logs": base + ("logs", "--tail", str(lines)),
        }[operation]
    elif project.runtime == "ddev":
        argv = {
            "start": ("ddev", "start"),
            "stop": ("ddev", "stop"),
            "restart": ("ddev", "restart"),
            "status": ("ddev", "describe", "-j"),
            "logs": ("ddev", "logs", "-s", "web", "--tail", str(lines)),
        }[operation]
    else:
        raise RuntimeError(f"{project.runtime} has no persistent lifecycle")
    return CommandSpec(argv, project.path, dict(project.environment))
```

`run()` uses `subprocess.run(..., shell=False, capture_output=True, text=True,
timeout=timeout)`, truncates each stream to 64 KiB, redacts assignment, bearer,
and JSON credential shapes, and uses `fcntl.flock` at
`/run/user/<uid>/nedctl-ddev.lock` for DDEV operations.

- [ ] **Step 4: Run tests and commit**

```bash
python3 -m unittest tests.test_commands tests.test_redaction -v
git add nedops/commands.py nedops/runner.py tests/test_commands.py tests/test_redaction.py
git commit -m "feat: add safe project runtime adapters"
```

---

### Task 3: Implement the `nedctl` interface and canonical inventory

**Files:**
- Create: `/home/ned/ai/ned-ops/nedops/health.py`
- Create: `/home/ned/ai/ned-ops/nedops/cli.py`
- Create: `/home/ned/ai/ned-ops/nedctl`
- Create: `/home/ned/ai/ned-ops/inventory.json`
- Create: `/home/ned/ai/ned-ops/tests/test_cli.py`

**Interfaces:**
- Produces: `nedctl list|status|doctor|start|stop|restart|logs|routes|health`, plus `--json` for read-only commands.

- [ ] **Step 1: Write failing CLI selection and exit-code tests**

```python
def test_unknown_project_exits_two(self):
    with self.assertRaises(SystemExit) as raised:
        main(["status", "missing"], inventory=self.inventory, runner=self.runner)
    self.assertEqual(raised.exception.code, 2)

def test_stop_calls_only_selected_project(self):
    self.assertEqual(main(["stop", "dm021"], inventory=self.inventory, runner=self.runner), 0)
    self.assertEqual(len(self.runner.calls), 1)
    self.assertEqual(self.runner.calls[0].cwd, Path("/home/ned/assembly/assembly-baseplate"))
```

- [ ] **Step 2: Implement HTTP probes and the CLI**

```python
@dataclass(frozen=True)
class ProbeResult:
    lane: str
    ok: bool
    detail: str

def probe_loopback(project: Project, timeout: float = 3.0) -> ProbeResult:
    headers = {"Host": project.health.host_header} if project.health.host_header else {}
    request = urllib.request.Request(project.health.url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return ProbeResult("loopback", response.status == project.health.expected_status, f"HTTP {response.status}")
    except OSError as error:
        return ProbeResult("loopback", False, type(error).__name__)
```

`doctor` reports lifecycle, loopback, private Caddy, and external lanes
separately. The external lane prints `not configured in this plan` and never
reports green. Unknown IDs exit 2 before a subprocess runs.

- [ ] **Step 3: Populate enabled persistent inventory records**

Use these exact identities:

| ID | Runtime | Path | Domain | Port/env |
|---|---|---|---|---|
| `dm006` | compose | `/home/ned/assembly/assembly` | `dm006.asmbly.app` | `ASSEMBLY_PORT=8090` |
| `dm021` | compose | `/home/ned/assembly/assembly-baseplate` | `dm021.asmbly.app` | `ASSEMBLY_DEV_PORT=8091`, container `assembly-baseplate-app` |
| `dm022` | compose | `/home/ned/assembly/assembly-baseplate-2` | `dm022.asmbly.app` | `ASSEMBLY_DEV_PORT=8092`, container `assembly-baseplate-2-app` |
| `travisgertz` | ddev | `/home/ned/sites/travisgertz` | `travisgertz.designmachines.xyz` | shared DDEV router 8080, Host header probe |
| `burnfund` | ddev | `/home/ned/sites/burnfund` | `burnfund.designmachines.xyz` | shared DDEV router 8080, Host header probe |
| `livewires` | static-compose | `/home/ned/ai/ned-ops/projects/livewires` | `livewires.designmachines.xyz` | 8083 |

Each Assembly record declares its repository `docker-compose.yml` followed by
`/home/ned/ai/ned-ops/projects/<id>/compose.override.yml`. Live Wires declares
only `/home/ned/ai/ned-ops/projects/livewires/compose.yml`.

Add disabled classified records for `fixture-jig`, `livewires-templ`,
`ai-memory`, `wiz-control`, `dm023`, `dm024`, `designmachines`, `farewell`, and
`the-local`. They have no port or persistent lifecycle.

Do not register `prototype.asmbly.app` yet. That alias remains on DigitalOcean
until the separate Cloudflare exposure plan validates its replacement.

- [ ] **Step 4: Run all tests and exercise read-only output**

```bash
python3 -m unittest discover -s tests -v
./nedctl list --json | python3 -m json.tool >/dev/null
./nedctl status not-a-project; test "$?" -eq 2
```

- [ ] **Step 5: Commit the CLI and inventory**

```bash
git add inventory.json nedctl nedops/health.py nedops/cli.py tests/test_cli.py
git commit -m "feat: add NED operator CLI"
```

---

### Task 4: Add NED-owned persistence overrides and the Live Wires static preview

**Files:**
- Create: `/home/ned/ai/ned-ops/projects/dm006/compose.override.yml`
- Create: `/home/ned/ai/ned-ops/projects/dm021/compose.override.yml`
- Create: `/home/ned/ai/ned-ops/projects/dm022/compose.override.yml`
- Create: `/home/ned/ai/ned-ops/projects/livewires/Dockerfile`
- Create: `/home/ned/ai/ned-ops/projects/livewires/Dockerfile.dockerignore`
- Create: `/home/ned/ai/ned-ops/projects/livewires/compose.yml`

**Interfaces:**
- Consumes: clean checkout `/home/ned/sites/livewires`.
- Produces: loopback preview `127.0.0.1:8083` without changing the Live Wires repository or DigitalOcean workflow.

- [ ] **Step 1: Write the three Assembly restart overrides**

Each override contains exactly:

```yaml
services:
  app:
    restart: unless-stopped
  css:
    restart: unless-stopped
```

- [ ] **Step 2: Write the external multi-stage build**

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist/ /usr/share/nginx/html/
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
```

`Dockerfile.dockerignore` contains `.git`, `node_modules`, and `dist`, one per
line.

- [ ] **Step 3: Write the loopback-only Compose wrapper**

```yaml
services:
  web:
    build:
      context: /home/ned/sites/livewires
      dockerfile: /home/ned/ai/ned-ops/projects/livewires/Dockerfile
    ports:
      - "127.0.0.1:8083:80"
    restart: unless-stopped
```

- [ ] **Step 4: Validate overrides, build, and prove source checkouts stay unchanged**

```bash
cd /home/ned/ai/ned-ops/projects/livewires
docker compose -f /home/ned/assembly/assembly/docker-compose.yml -f /home/ned/ai/ned-ops/projects/dm006/compose.override.yml config --quiet
docker compose -f /home/ned/assembly/assembly-baseplate/docker-compose.yml -f /home/ned/ai/ned-ops/projects/dm021/compose.override.yml config --quiet
ASSEMBLY_DEV_PORT=8092 ASSEMBLY_DEV_CONTAINER_NAME=assembly-baseplate-2-app docker compose -f /home/ned/assembly/assembly-baseplate-2/docker-compose.yml -f /home/ned/ai/ned-ops/projects/dm022/compose.override.yml config --quiet
docker compose --project-name livewires config --quiet
docker compose --project-name livewires up -d --build
curl --fail --silent --show-error http://127.0.0.1:8083/ >/dev/null
test -z "$(git -C /home/ned/sites/livewires status --short)"
```

- [ ] **Step 5: Commit the wrappers**

```bash
cd /home/ned/ai/ned-ops
git add projects/livewires
git commit -m "feat: add Live Wires static preview runtime"
```

---

### Task 5: Provision Burnfund and preserve the tracked nested plugin

**Files:**
- Source: `/Users/trav/Websites/burnfund`
- Create: `/home/ned/sites/burnfund`
- Preserve: `/home/ned/sites/burnfund/wp-content/plugins/burnfund-component-library/.git`

**Interfaces:**
- Consumes: Mac DDEV project and SSH alias `ned-plain`.
- Produces: NED DDEV project `burnfund` routed internally by DDEV.

- [ ] **Step 1: Record source URL and export a protected database**

```bash
cd /Users/trav/Websites/burnfund
ddev status
ddev wp option get home
umask 077
ddev export-db --file=/private/tmp/burnfund-ned.sql.gz
test -s /private/tmp/burnfund-ned.sql.gz
```

Record the non-secret `home` URL in the execution notes.

- [ ] **Step 2: Transfer the site, excluding generated DDEV state**

```bash
ssh ned-plain 'install -d -m 700 /home/ned/sites/burnfund'
rsync -a --protect-args \
  --exclude='.ddev/.ddev-docker-compose-*' \
  --exclude='.ddev/mutagen/' \
  --exclude='.ddev/.dbimageBuild/' \
  --exclude='.ddev/.webimageBuild/' \
  /Users/trav/Websites/burnfund/ ned-plain:/home/ned/sites/burnfund/
scp /private/tmp/burnfund-ned.sql.gz ned-plain:/home/ned/sites/burnfund/.ddev/burnfund-ned.sql.gz
```

- [ ] **Step 3: Compare the nested plugin repository on both machines**

```bash
git -C /Users/trav/Websites/burnfund/wp-content/plugins/burnfund-component-library rev-parse HEAD
ssh ned-plain 'git -C /home/ned/sites/burnfund/wp-content/plugins/burnfund-component-library rev-parse HEAD && git -C /home/ned/sites/burnfund/wp-content/plugins/burnfund-component-library status --short --branch'
```

Expected: the HEADs match and the remote plugin retains its `.git` directory.

- [ ] **Step 4: Start DDEV and import**

```bash
ssh ned-plain 'cd /home/ned/sites/burnfund && ddev start && ddev import-db --file=.ddev/burnfund-ned.sql.gz && ddev wp option get home'
```

If the imported home URL differs, run `ddev wp search-replace` using the exact
URL recorded in Step 1 and `http://burnfund.designmachines.xyz`, with
`--skip-columns=guid`, then re-read the option.

- [ ] **Step 5: Move transient exports to each user's trash**

```bash
mkdir -p /Users/trav/.Trash
mv /private/tmp/burnfund-ned.sql.gz /Users/trav/.Trash/burnfund-ned.sql.gz
ssh ned-plain 'install -d /home/ned/.local/share/Trash/files && mv /home/ned/sites/burnfund/.ddev/burnfund-ned.sql.gz /home/ned/.local/share/Trash/files/burnfund-ned.sql.gz'
```

- [ ] **Step 6: Verify the host-routed application**

```bash
ssh ned-plain 'cd /home/ned/sites/burnfund && ddev describe -j | python3 -m json.tool >/dev/null && curl --fail --silent --show-error -H "Host: burnfund.designmachines.xyz" http://127.0.0.1:8080/ >/dev/null'
```

---

### Task 6: Install persistent user lifecycles

**Files:**
- Create: `/home/ned/ai/ned-ops/systemd/ned-project@.service`
- Create: `/home/ned/ai/ned-ops/systemd/ned-projects.target`
- Create: `/home/ned/ai/ned-ops/systemd/ned-project@dm006.service.d/ordering.conf`
- Create: `/home/ned/ai/ned-ops/systemd/ned-project@burnfund.service.d/ordering.conf`
- Create: `/home/ned/ai/ned-ops/scripts/install-user-units.sh`

**Interfaces:**
- Consumes: `/home/ned/.local/bin/nedctl` and enabled inventory IDs.
- Produces: reboot-persistent `ned-projects.target` and isolated per-project control.

- [ ] **Step 1: Write the template service**

```ini
[Unit]
Description=NED project runtime %i
After=docker.service
Requires=docker.service
PartOf=ned-projects.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/home/ned/.local/bin/nedctl start %i
ExecStop=/home/ned/.local/bin/nedctl stop %i
TimeoutStartSec=300
TimeoutStopSec=120

[Install]
WantedBy=ned-projects.target
```

- [ ] **Step 2: Write the target and ordering drop-ins**

```ini
[Unit]
Description=NED persistent project runtimes
Wants=ned-project@travisgertz.service ned-project@burnfund.service
Wants=ned-project@dm006.service ned-project@dm021.service
Wants=ned-project@dm022.service ned-project@livewires.service
After=docker.service

[Install]
WantedBy=default.target
```

The dm006 and Burnfund drop-ins each contain:

```ini
[Unit]
After=ned-project@travisgertz.service
```

- [ ] **Step 3: Write the idempotent installer**

The installer sets a fixed PATH, verifies every source file, installs them mode
0644 under `/home/ned/.config/systemd/user`, creates the `nedctl` symlink, runs
`systemctl --user daemon-reload`, and enables—but does not start—
`ned-projects.target`.

- [ ] **Step 4: Validate then install**

```bash
cd /home/ned/ai/ned-ops
systemd-analyze --user verify systemd/ned-project@.service systemd/ned-projects.target
python3 -m unittest discover -s tests -v
loginctl show-user ned -p Linger
./scripts/install-user-units.sh
```

Expected: `Linger=yes`. If it is not enabled, request administrative approval
before `sudo loginctl enable-linger ned`, then re-check.

- [ ] **Step 5: Start each project separately and inspect health**

```bash
systemctl --user start ned-project@travisgertz.service
systemctl --user start ned-project@burnfund.service
systemctl --user start ned-project@dm006.service
systemctl --user start ned-project@dm021.service
systemctl --user start ned-project@dm022.service
systemctl --user start ned-project@livewires.service
systemctl --user start ned-projects.target
systemctl --user --no-pager --full status ned-projects.target
/home/ned/.local/bin/nedctl health
```

- [ ] **Step 6: Commit units and installer**

```bash
cd /home/ned/ai/ned-ops
git add systemd scripts/install-user-units.sh
git commit -m "feat: persist NED project lifecycles"
```

---

### Task 7: Replace the permissive Caddy wildcard with explicit private routes

**Files:**
- Modify: `/etc/caddy/Caddyfile`
- Backup: `/etc/caddy/Caddyfile.pre-ned-runtime-20260811`

**Interfaces:**
- Consumes: healthy loopback services.
- Produces: explicit private routes and unknown-host 404 behavior.

- [ ] **Step 1: Capture pre-change evidence and backup**

```bash
curl --insecure --silent --output /dev/null --write-out '%{http_code}\n' --resolve unknown.designmachines.xyz:443:100.77.82.93 https://unknown.designmachines.xyz/
sudo install -m 0644 /etc/caddy/Caddyfile /etc/caddy/Caddyfile.pre-ned-runtime-20260811
```

- [ ] **Step 2: Replace only the Design Machines wildcard block**

```caddyfile
https://*.designmachines.xyz {
	tls /etc/caddy/certs/designmachines.xyz.crt /etc/caddy/certs/designmachines.xyz.key

	@travisgertz host travisgertz.designmachines.xyz
	handle @travisgertz {
		reverse_proxy 127.0.0.1:8080
	}

	@burnfund host burnfund.designmachines.xyz
	handle @burnfund {
		reverse_proxy 127.0.0.1:8080
	}

	@livewires host livewires.designmachines.xyz
	handle @livewires {
		reverse_proxy 127.0.0.1:8083
	}

	handle {
		respond "No Design Machines preview at this hostname (NED 9000)" 404
	}
}
```

- [ ] **Step 3: Validate before reload**

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
systemctl is-active caddy
```

If validation fails, restore the backup with `sudo install` and do not reload.

- [ ] **Step 4: Prove known and unknown routes**

```bash
curl --insecure --fail --silent --resolve travisgertz.designmachines.xyz:443:100.77.82.93 https://travisgertz.designmachines.xyz/ >/dev/null
curl --insecure --fail --silent --resolve burnfund.designmachines.xyz:443:100.77.82.93 https://burnfund.designmachines.xyz/ >/dev/null
curl --insecure --fail --silent --resolve livewires.designmachines.xyz:443:100.77.82.93 https://livewires.designmachines.xyz/ >/dev/null
test "$(curl --insecure --silent --output /dev/null --write-out '%{http_code}' --resolve unknown.designmachines.xyz:443:100.77.82.93 https://unknown.designmachines.xyz/)" = "404"
```

---

### Task 8: Move the approved obsolete NED checkouts to trash

**Files:**
- Move: `/home/ned/sites/designmachines`
- Move: `/home/ned/sites/farewell`

**Interfaces:**
- Produces: recoverable trash entries; upstream and production remain untouched.

- [ ] **Step 1: Re-audit immediately before moving**

```bash
git -C /home/ned/sites/designmachines fetch --prune origin
git -C /home/ned/sites/designmachines status --short
git -C /home/ned/sites/designmachines log --oneline '@{upstream}..HEAD'
git -C /home/ned/sites/farewell fetch --prune origin
git -C /home/ned/sites/farewell status --short
git -C /home/ned/sites/farewell log --oneline '@{upstream}..HEAD'
```

Expected: both status and unpushed-commit outputs are empty. Stop if either is
non-empty.

- [ ] **Step 2: Stop Design Machines DDEV without deleting its data volume**

```bash
cd /home/ned/sites/designmachines
ddev stop
```

- [ ] **Step 3: Move both checkouts to distinct trash paths**

```bash
install -d /home/ned/.local/share/Trash/files
mv /home/ned/sites/designmachines /home/ned/.local/share/Trash/files/designmachines-ned-20260811
mv /home/ned/sites/farewell /home/ned/.local/share/Trash/files/farewell-ned-20260811
```

- [ ] **Step 4: Verify recoverability**

```bash
test ! -e /home/ned/sites/designmachines
test ! -e /home/ned/sites/farewell
test -d /home/ned/.local/share/Trash/files/designmachines-ned-20260811
test -d /home/ned/.local/share/Trash/files/farewell-ned-20260811
```

---

### Task 9: Add `ned:operate` to Depot

**Files:**
- Create: `/home/ned/ai/depot/plugins/ned/skills/operate/SKILL.md`
- Create: `/home/ned/ai/depot/plugins/ned/skills/operate/references/ned-runtime.md`
- Create: `/home/ned/ai/depot/description-evals/ned-operate.json`
- Modify: `/home/ned/ai/depot/plugins/ned/.claude-plugin/plugin.json`
- Modify: `/home/ned/ai/depot/.claude-plugin/marketplace.json`
- Regenerate: Codex manifests and `docs/search-index.md`

**Interfaces:**
- Consumes: installed `nedctl` and approved design.
- Produces: portable skill version `1.8.0`, with no MCP or secret dependency.

- [ ] **Step 1: Add trigger evals before the skill**

```json
[
  {"query":"Check which projects are running on NED 9000","should_trigger":true},
  {"query":"Restart dm022 and show its bounded logs","should_trigger":true},
  {"query":"Why is burnfund.designmachines.xyz down on NED?","should_trigger":true},
  {"query":"Audit Caddy and Docker health on the Linux box","should_trigger":true},
  {"query":"Show the lifecycle status of the Assembly installs","should_trigger":true},
  {"query":"Diagnose the Tailscale route to dm021.asmbly.app","should_trigger":true},
  {"query":"Start the Live Wires static preview on NED","should_trigger":true},
  {"query":"Is T3 Code running on ned9000?","should_trigger":true},
  {"query":"Run nedctl doctor for Travis Gertz","should_trigger":true},
  {"query":"Explain which NED previews survive reboot","should_trigger":true},
  {"query":"Write a Go handler for Assembly","should_trigger":false},
  {"query":"Review this pull request","should_trigger":false},
  {"query":"Search my knowledge graph for Louisa","should_trigger":false},
  {"query":"Create a marketing plan for Design Machines","should_trigger":false},
  {"query":"Build a Vite component on my Mac","should_trigger":false},
  {"query":"Capture this session to ai-memory","should_trigger":false},
  {"query":"Deploy the production website to DigitalOcean","should_trigger":false},
  {"query":"Write a newsletter in my voice","should_trigger":false},
  {"query":"Explain DDEV in general","should_trigger":false},
  {"query":"Design a three-way federation feature","should_trigger":false}
]
```

- [ ] **Step 2: Write the skill frontmatter and guarded workflow**

```yaml
---
name: operate
description: >-
  Operate and diagnose Travis Gertz's NED 9000 Linux development host,
  including nedctl project status, Docker and DDEV runtimes, Caddy domains,
  Tailscale, T3 Code, bounded logs, startup, stop, restart, routing, and server
  troubleshooting. Use for NED, ned9000, dm006, dm021, dm022, Burnfund,
  Travis Gertz, or Live Wires preview operations; not for application feature
  development.
---
```

The body requires: select `ned` versus `trav`; load the runtime reference;
start read-only with `nedctl`; diagnose one evidence lane at a time; bound logs
to 120 lines; use known IDs only; require confirmation for deletion, public
exposure, DNS, credentials, production, sudo, and Tailscale Serve; report
unproven lanes; and fall back to explicit read-only systemd/Docker/DDEV/Caddy/
Tailscale checks if `nedctl` is unavailable.

- [ ] **Step 3: Write the runtime reference**

Record account boundaries, `/home/ned/{assembly,sites,ai}`, project
classifications, plain versus tmux SSH aliases, lifecycle/loopback/Caddy/
Cloudflare evidence lanes, and exact read-only recovery commands. State that
ports and enabled state come from `nedctl list --json`, not the plugin.

- [ ] **Step 4: Bump canonical metadata to 1.8.0**

Add the fourth skill capability `operate` with no `mcpDependencies`; update the
plugin and marketplace descriptions; synchronize both versions at `1.8.0`;
change `capabilities_summary.skills` from 3 to 4; add operations tags.

- [ ] **Step 5: Regenerate and validate**

```bash
cd /home/ned/ai/depot
./tools/generate-codex-manifests.py
./tools/validate-composition.sh --generate-index
./tools/eval-descriptions.sh ned-operate.json
./tools/validate-dual-compat.sh
./tools/validate-composition.sh --all
git diff --check
```

Expected: focused eval at least 70%; dual and full composition pass.

- [ ] **Step 6: Commit without releasing**

```bash
git add plugins/ned .claude-plugin/marketplace.json .agents/plugins/marketplace.json description-evals/ned-operate.json docs/search-index.md
git commit -m "feat(ned): add guarded NED operations skill"
```

Do not tag or push. Publication requires a fresh
`./tools/check-release-preflight.sh` receipt and explicit authority.

---

### Task 10: Verify the complete private runtime and present the reboot gate

**Files:**
- Modify only if evidence identifies a defect in an earlier task.

**Interfaces:**
- Produces: local and tailnet evidence; Cloudflare remains explicitly unproven.

- [ ] **Step 1: Bind repository and service state**

```bash
git -C /home/ned/ai/ned-ops status --short --branch
git -C /home/ned/ai/ned-ops log -1 --oneline
git -C /home/ned/ai/depot status --short --branch
git -C /home/ned/ai/depot log -2 --oneline
systemctl --user --no-pager --full status ned-projects.target
```

- [ ] **Step 2: Run every operator evidence lane**

```bash
/home/ned/.local/bin/nedctl list
/home/ned/.local/bin/nedctl status
/home/ned/.local/bin/nedctl health
/home/ned/.local/bin/nedctl routes
for id in dm006 dm021 dm022 travisgertz burnfund livewires; do /home/ned/.local/bin/nedctl doctor "$id"; done
```

Expected: lifecycle, loopback, and private Caddy lanes pass; external Access is
reported unconfigured.

- [ ] **Step 3: Prove reserved runtimes remain absent**

```bash
systemctl --user is-enabled ned-projects.target
systemctl --user is-active ned-project@dm023.service; test "$?" -ne 0
systemctl --user is-active ned-project@dm024.service; test "$?" -ne 0
```

- [ ] **Step 4: Verify private hostnames from the Mac**

```bash
for url in \
  https://dm006.asmbly.app/ \
  https://dm021.asmbly.app/ \
  https://dm022.asmbly.app/ \
  https://travisgertz.designmachines.xyz/ \
  https://burnfund.designmachines.xyz/ \
  https://livewires.designmachines.xyz/; do
  curl --insecure --fail --silent --show-error "$url" >/dev/null
done
```

- [ ] **Step 5: Request immediate approval before reboot**

Present the non-reboot evidence first. After explicit approval, run
`sudo systemctl reboot`, reconnect, repeat Steps 1-4, and verify the persistent
set returned while ephemeral, deferred, and removed projects stayed absent.
