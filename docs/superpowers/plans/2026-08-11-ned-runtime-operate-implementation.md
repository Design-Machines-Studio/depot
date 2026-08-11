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
- Depot implementation starts from freshly fetched `origin/main` in a dedicated
  worktree. Never edit, clean, reset, or commit through the shared
  `/home/ned/ai/depot` checkout; preserve its exact pre-existing HEAD and status.

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
- `projects/dm006/compose.override.yml` — NED-only containment for prototype services.
- `projects/dm021/compose.override.yml` — NED-only containment for Baseplate services.
- `projects/dm022/compose.override.yml` — NED-only containment for Baseplate 2 services.
- `projects/livewires/` — external static preview build; Live Wires checkout remains untouched.
- `systemd/` — per-project lifecycle and health units plus generated target.
- `scripts/install-user-units.sh` — idempotent unit and launcher installer.

### `/home/ned/ai/depot/.worktrees/ned-operate` (fresh isolated worktree)

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
- Produces: `HTTPProbe`, `ProjectProbes`, `Project`, `Inventory`, `load_inventory(path: Path) -> Inventory`, `Inventory.project(project_id: str) -> Project`.

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
def test_rejects_duplicate_domain_and_exclusive_port(self):
    path = self.write_inventory([
        self.project("one", domain="one.example.test", port=8091),
        self.project("two", domain="one.example.test", port=8091),
    ])
    with self.assertRaisesRegex(ValueError, "duplicate domain.*duplicate port"):
        load_inventory(path)

def test_allows_two_ddev_projects_on_one_shared_router(self):
    path = self.write_inventory([
        self.project("one", runtime="ddev", port=None,
                     health_url="http://127.0.0.1:8080/"),
        self.project("two", runtime="ddev", port=None,
                     health_url="http://127.0.0.1:8080/"),
    ])
    self.assertEqual(len(load_inventory(path).projects), 2)

def test_rejects_secret_shaped_environment_key(self):
    project = self.project("one", domain="one.example.test", port=8091)
    project["environment"] = {"API_TOKEN": "must-not-be-here"}
    with self.assertRaisesRegex(ValueError, "secret-shaped key"):
        load_inventory(self.write_inventory([project]))

def test_validated_environment_is_immutable(self):
    path = self.write_inventory([
        self.project("one", domain="one.example.test", port=8091,
                     environment={"ASSEMBLY_PORT": "8091"}),
    ])
    project = load_inventory(path).project("one")
    self.assertEqual(project.environment, (("ASSEMBLY_PORT", "8091"),))
    with self.assertRaises(TypeError):
        project.environment[0] = ("ASSEMBLY_PORT", "9999")

def test_model_module_imports(self):
    module = importlib.import_module("nedops.model")
    self.assertTrue(dataclasses.is_dataclass(module.Project))

def test_rejects_missing_or_invalid_probe_port(self):
    project = self.project("one", domain="one.example.test", port=8091)
    del project["probes"]["loopback"]["connect_port"]
    with self.assertRaisesRegex(ValueError, "connect_port"):
        load_inventory(self.write_inventory([project]))

    project = self.project("one", domain="one.example.test", port=8091)
    project["probes"]["loopback"]["connect_port"] = 0
    with self.assertRaisesRegex(ValueError, "connect_port"):
        load_inventory(self.write_inventory([project]))
```

The test module imports `dataclasses` and `importlib` explicitly. The import test
is intentionally discovered with the rest of the module so invalid dataclass
field ordering fails before any inventory behavior can be reported green.

- [ ] **Step 3: Prove the tests fail before implementation**

```bash
cd /home/ned/ai/ned-ops
python3 -m unittest tests.test_inventory -v
```

Expected: import failure for `nedops.inventory`.

- [ ] **Step 4: Implement frozen models and strict JSON validation**

```python
Environment = tuple[tuple[str, str], ...]

@dataclass(frozen=True)
class HTTPProbe:
    lane: str
    scheme: str
    connect_ip: str
    connect_port: int
    host: str
    path: str
    expected_status: int = 200

@dataclass(frozen=True)
class ProjectProbes:
    loopback: HTTPProbe
    local_caddy: HTTPProbe
    tailnet: HTTPProbe

@dataclass(frozen=True)
class Project:
    id: str
    source_path: Path
    runtime_path: Path
    runtime: str
    persistent: bool
    enabled: bool
    probes: ProjectProbes
    domains: tuple[str, ...] = ()
    port: int | None = None
    compose_files: tuple[Path, ...] = ()
    environment: Environment = ()

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
IDs/domains/non-null project-owned ports. Probe lanes are mandatory for every
enabled persistent project and are immutable after validation. Every probe has
a required integer `connect_port`; no function infers or defaults it. `loopback`
may connect only to `127.0.0.1` on the record's validated project port or an
allowlisted shared-router port; `local_caddy` may connect only to
`127.0.0.1:443`; and `tailnet` may connect
only to a caller-supplied validated NED Tailscale IPv4 address, never to an
inventory URL or DNS result. For Caddy and tailnet probes, `host` must be one
of the project's validated domains, `path` must be an absolute path without
userinfo/query/fragment, `scheme` is exactly `https`, and the expected status
is an allowlisted 2xx status. The loader rejects duplicate or non-project
domains, non-literal connect IPs, URL userinfo, redirects as expected results,
unknown fields, and any mutable mapping. Environment keys use a strict
per-runtime allowlist (`ASSEMBLY_PORT`, `ASSEMBLY_DEV_PORT`, and
`ASSEMBLY_DEV_CONTAINER_NAME` initially); arbitrary keys and URL userinfo are
rejected. Compose and static-compose records
must declare at least one absolute `compose_files` path; other runtimes reject
non-empty `compose_files`. After validating the per-runtime allowlist and values,
the loader sorts the environment entries by key and stores them as an immutable
tuple. It constructs the frozen probe objects only after the same validation;
no mutable mapping survives the validation boundary.

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
        "/usr/bin/docker", "compose", "--project-name", "dm022",
        "-f", "/home/ned/assembly/assembly-baseplate-2/docker-compose.yml",
        "-f", "/home/ned/ai/ned-ops/projects/dm022/compose.override.yml",
        "up", "-d",
    ))
    self.assertEqual(dict(command.env)["ASSEMBLY_DEV_PORT"], "8092")

def test_ddev_logs_are_bounded(self):
    self.assertEqual(
        build_command(self.travisgertz, "logs", lines=80).argv,
        ("/usr/local/bin/ddev", "logs", "-s", "web", "--tail", "80"),
    )

def test_runner_uses_only_the_minimal_non_secret_environment(self):
    with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "must-not-pass"}):
        child_env = execution_environment(self.dm022.environment)
    self.assertEqual(child_env["HOME"], "/home/ned")
    self.assertEqual(child_env["PATH"], "/usr/local/bin:/usr/bin:/bin")
    self.assertEqual(child_env["XDG_RUNTIME_DIR"], f"/run/user/{os.getuid()}")
    self.assertNotIn("OPENROUTER_API_KEY", child_env)

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
    env: Environment

def build_command(project: Project, operation: str, lines: int = 120) -> CommandSpec:
    if not project.enabled:
        raise RuntimeError(f"{project.id} is not enabled")
    if project.runtime in {"compose", "static-compose"}:
        files = tuple(part for path in project.compose_files for part in ("-f", str(path)))
        base = ("/usr/bin/docker", "compose", "--project-name", project.id) + files
        argv = {
            "start": base + ("up", "-d"),
            "stop": base + ("stop",),
            "restart": base + ("restart",),
            "status": base + ("ps", "--format", "json"),
            "logs": base + ("logs", "--tail", str(lines)),
        }[operation]
    elif project.runtime == "ddev":
        argv = {
            "start": ("/usr/local/bin/ddev", "start"),
            "stop": ("/usr/local/bin/ddev", "stop"),
            "restart": ("/usr/local/bin/ddev", "restart"),
            "status": ("/usr/local/bin/ddev", "describe", "-j"),
            "logs": ("/usr/local/bin/ddev", "logs", "-s", "web", "--tail", str(lines)),
        }[operation]
    else:
        raise RuntimeError(f"{project.runtime} has no persistent lifecycle")
    return CommandSpec(argv, project.runtime_path, project.environment)
```

`run()` uses `subprocess.Popen(..., shell=False)` and bounded streaming reads.
At the execution boundary, `execution_environment()` creates a new dictionary
from exactly `HOME=/home/ned`, `PATH=/usr/local/bin:/usr/bin:/bin`, and
`XDG_RUNTIME_DIR=/run/user/<validated ned uid>`, then adds the validated
per-runtime entries from `spec.env`. It refuses collisions with those protected
base keys and never copies `os.environ`; ambient provider, SSH, cloud, or other
authority therefore cannot enter a project subprocess. The runner requires the
current UID to be `ned`, verifies the runtime directory is owned by that UID,
and callers never receive a mutable post-validation mapping. It
keeps at most 64 KiB total across stdout and stderr, terminates the process group
at the timeout, and redacts incrementally with overlap between chunks so a
split credential cannot bypass the filter. Tests cover multi-megabyte output,
timeout output, cookies, query parameters, URL userinfo, bearer/assignment/JSON
forms, and PEM material. DDEV operations use `fcntl.flock` at
`/run/user/<uid>/nedctl-ddev.lock`.

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

- [ ] **Step 2: Implement independent HTTP probes and the CLI**

```python
@dataclass(frozen=True)
class ProbeResult:
    lane: str
    ok: bool
    detail: str

def probe_loopback(probe: HTTPProbe, timeout: float = 3.0) -> ProbeResult:
    request = urllib.request.Request(
        f"http://{probe.connect_ip}:{probe.connect_port}{probe.path}",
        headers={"Host": probe.host}, method="GET",
    )
    opener = urllib.request.build_opener(NoRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            return ProbeResult("loopback", response.status == probe.expected_status, f"HTTP {response.status}")
    except urllib.error.HTTPError as error:
        return ProbeResult("loopback", False, f"HTTP {error.code}")
    except OSError as error:
        return ProbeResult("loopback", False, type(error).__name__)
```

`NoRedirectHandler` subclasses `urllib.request.HTTPRedirectHandler` and returns
`None` from `redirect_request()`. Unit tests serve a redirect to an external URL
and prove the probe returns the original 3xx as failed without making the second
request. Implement `probe_local_caddy()` and `probe_tailnet()` separately from
`probe_loopback()`: both connect to the probe's exact validated IP and port 443,
wrap TLS with `server_hostname=probe.host`, issue an exact `Host: probe.host`,
and accept only `expected_status`. The local-Caddy lane uses its immutable
`127.0.0.1` binding; the tailnet lane refuses to run on NED and accepts the
Mac-supplied, independently acquired, validated NED Tailscale IPv4 only as a
function argument. Neither route function follows redirects, resolves DNS, or
falls back to another IP. If the private certificate is intentionally not in the
host trust store, the explicit unverified TLS context is permitted only after
that host/IP binding; certificate validity is a separately named evidence lane,
never silently skipped.

Tests construct a local HTTP server, a TLS test server, and a redirect target.
They prove all three lanes report their own lane name; a 3xx is failed without a
second request; a Caddy request reaches only the supplied loopback IP with the
exact port, host, and SNI; a loopback probe reaches the server only on its exact
random test port and fails rather than falling back when given an adjacent port;
tailnet rejects DNS names, a changed IP, a non-443 port, or invocation on NED;
and no result can be reused for another project or lane. `doctor` aggregates
lifecycle, loopback, and local-Caddy results independently. Its NED-local
tailnet row is exactly `unproven from this host`; only the Mac receipt may mark
that lane passed. The external row is `not configured in this plan` and never
green. Unknown IDs exit 2 before a subprocess runs.

- [ ] **Step 3: Populate enabled persistent inventory records**

Use these exact identities:

| ID | Runtime | Source path | Runtime path | Domain | Port/env |
|---|---|---|---|---|---|
| `dm006` | compose | `/home/ned/assembly/assembly` | same as source | `dm006.asmbly.app` | `ASSEMBLY_PORT=8090` |
| `dm021` | compose | `/home/ned/assembly/assembly-baseplate` | same as source | `dm021.asmbly.app` | `ASSEMBLY_DEV_PORT=8091`, container `assembly-baseplate-app` |
| `dm022` | compose | `/home/ned/assembly/assembly-baseplate-2` | same as source | `dm022.asmbly.app` | `ASSEMBLY_DEV_PORT=8092`, container `assembly-baseplate-2-app` |
| `travisgertz` | ddev | `/home/ned/sites/travisgertz` | same as source | `travisgertz.designmachines.xyz` | no exclusive port; Host probe through shared router 8080 |
| `burnfund` | ddev | `/home/ned/sites/burnfund` | same as source | `burnfund.designmachines.xyz` | no exclusive port; Host probe through shared router 8080 |
| `livewires` | static-compose | `/home/ned/sites/livewires` | `/home/ned/ai/ned-ops/projects/livewires` | `livewires.designmachines.xyz` | 8083 |

The exact `loopback.connect_port` mapping is `dm006=8090`, `dm021=8091`,
`dm022=8092`, `travisgertz=8080`, `burnfund=8080`, and `livewires=8083`.
Every `local_caddy.connect_port` and `tailnet.connect_port` is exactly 443.
`test_enabled_probe_ports_match_runtime_contract()` asserts this complete map so
an inventory edit cannot silently move a probe to a default or adjacent port.

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
- Create: `/home/ned/ai/ned-ops/scripts/assert-loopback-ports.py`

**Interfaces:**
- Consumes: clean checkout `/home/ned/sites/livewires`.
- Produces: loopback preview `127.0.0.1:8083` without changing the Live Wires repository or DigitalOcean workflow.

- [ ] **Step 1: Write the three Assembly containment overrides**

Each override replaces—not appends to—the base Compose `ports` lists using the
installed Compose version's verified `!override` support. Every retained host
publication binds to `127.0.0.1`; unused CSS/HMR publications are removed. It
also disables container-owned restart so systemd remains the host persistence
owner. After rendering, JSON assertions require every published-port
`host_ip` to equal `127.0.0.1` and every service restart policy to equal `no`.
The essential shape is:

```yaml
services:
  app:
    ports: !override
      - "127.0.0.1:${ASSEMBLY_PORT:-8090}:8090"
    restart: "no"
  css:
    ports: !override []
    restart: "no"
```

- [ ] **Step 2: Write the external multi-stage build**

```dockerfile
FROM node:22-alpine@sha256:<reviewed-ned-architecture-digest> AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine@sha256:<reviewed-ned-architecture-digest>
COPY --from=build /app/dist/ /usr/share/nginx/html/
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
```

`Dockerfile.dockerignore` contains `.git`, `node_modules`, and `dist`, one per
line. Resolve both digest placeholders for NED's architecture, record them in
the commit, and review them before the first build; mutable tags alone are not
accepted.

- [ ] **Step 3: Write the loopback-only Compose wrapper**

```yaml
services:
  web:
    build:
      context: /home/ned/sites/livewires
      dockerfile: /home/ned/ai/ned-ops/projects/livewires/Dockerfile
    ports:
      - "127.0.0.1:8083:80"
    restart: "no"
```

- [ ] **Step 4: Validate overrides, build, and prove source checkouts stay unchanged**

```bash
cd /home/ned/ai/ned-ops/projects/livewires
docker compose -f /home/ned/assembly/assembly/docker-compose.yml -f /home/ned/ai/ned-ops/projects/dm006/compose.override.yml config --quiet
docker compose -f /home/ned/assembly/assembly-baseplate/docker-compose.yml -f /home/ned/ai/ned-ops/projects/dm021/compose.override.yml config --quiet
ASSEMBLY_DEV_PORT=8092 ASSEMBLY_DEV_CONTAINER_NAME=assembly-baseplate-2-app docker compose -f /home/ned/assembly/assembly-baseplate-2/docker-compose.yml -f /home/ned/ai/ned-ops/projects/dm022/compose.override.yml config --quiet
docker compose -f /home/ned/assembly/assembly/docker-compose.yml -f /home/ned/ai/ned-ops/projects/dm006/compose.override.yml config --format json > /tmp/ned-compose-dm006.json
docker compose -f /home/ned/assembly/assembly-baseplate/docker-compose.yml -f /home/ned/ai/ned-ops/projects/dm021/compose.override.yml config --format json > /tmp/ned-compose-dm021.json
ASSEMBLY_DEV_PORT=8092 ASSEMBLY_DEV_CONTAINER_NAME=assembly-baseplate-2-app docker compose -f /home/ned/assembly/assembly-baseplate-2/docker-compose.yml -f /home/ned/ai/ned-ops/projects/dm022/compose.override.yml config --format json > /tmp/ned-compose-dm022.json
docker compose --project-name livewires config --quiet
for rendered in /tmp/ned-compose-dm006.json /tmp/ned-compose-dm021.json /tmp/ned-compose-dm022.json; do
  python3 /home/ned/ai/ned-ops/scripts/assert-loopback-ports.py "$rendered"
done
docker compose --project-name livewires up -d --build
curl --fail --silent --show-error http://127.0.0.1:8083/ >/dev/null
test -z "$(git -C /home/ned/sites/livewires status --short)"
```

- [ ] **Step 5: Commit the wrappers**

```bash
cd /home/ned/ai/ned-ops
git add projects/dm006 projects/dm021 projects/dm022 projects/livewires scripts/assert-loopback-ports.py
git commit -m "feat: add Live Wires static preview runtime"
git status --short
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

- [ ] **Step 1: Create collision-checked private transfer state and export the database**

```bash
set -eu
MAC_TRANSFER_DIR=/private/tmp/burnfund-ned-20260811
MAC_EXPORT="$MAC_TRANSFER_DIR/burnfund.sql.gz"
MAC_DIGEST="$MAC_TRANSFER_DIR/burnfund.sql.gz.sha256"
NED_TRANSFER_DIR=/home/ned/.local/state/ned-ops/transfers/burnfund-ned-20260811
test ! -e "$MAC_TRANSFER_DIR"
install -d -m 700 "$MAC_TRANSFER_DIR"
cleanup_mac_transfer() {
  cleanup_status=0
  if rm -f -- "$MAC_EXPORT" "$MAC_DIGEST"; then :; else cleanup_status=$?; fi
  if rmdir -- "$MAC_TRANSFER_DIR" 2>/dev/null; then :; else
    rmdir_status=$?
    if test "$cleanup_status" -eq 0; then cleanup_status=$rmdir_status; fi
  fi
  return "$cleanup_status"
}
cleanup_remote_transfer() {
  ssh ned-plain "set -eu
    if test -e '$NED_TRANSFER_DIR'; then
      rm -f -- '$NED_TRANSFER_DIR/burnfund.sql.gz' '$NED_TRANSFER_DIR/burnfund.sql.gz.sha256'
      rmdir -- '$NED_TRANSFER_DIR'
    fi"
}
cleanup_transfer() {
  status=$?
  trap - EXIT HUP INT TERM
  remote_status=0
  mac_status=0
  if cleanup_remote_transfer; then
    :
  else
    remote_status=$?
  fi
  if cleanup_mac_transfer; then
    :
  else
    mac_status=$?
  fi
  if test "$remote_status" -ne 0; then
    printf '%s\n' "remote transfer cleanup failed; preserved for review: $NED_TRANSFER_DIR" >&2
  fi
  if test "$mac_status" -ne 0; then
    printf '%s\n' "Mac transfer cleanup failed; preserved for review: $MAC_TRANSFER_DIR" >&2
  fi
  if test "$status" -ne 0; then
    exit "$status"
  fi
  if test "$remote_status" -ne 0; then
    exit "$remote_status"
  fi
  if test "$mac_status" -ne 0; then
    exit "$mac_status"
  fi
  exit 0
}
trap cleanup_transfer EXIT HUP INT TERM
cd /Users/trav/Websites/burnfund
ddev status
ddev wp option get home
umask 077
ddev export-db --file="$MAC_EXPORT"
test -s "$MAC_EXPORT"
chmod 600 "$MAC_EXPORT"
test "$(stat -f '%Lp' "$MAC_EXPORT")" = 600
(cd "$MAC_TRANSFER_DIR" && shasum -a 256 burnfund.sql.gz > burnfund.sql.gz.sha256)
chmod 600 "$MAC_DIGEST"
```

Record the non-secret `home` URL in the execution notes.

Steps 1–5 are one fresh-shell transaction so this EXIT trap runs on both failure
and success. Do not clear it until both endpoints have removed the exact export
and digest. A collision is a hard stop: recover only by inspecting the named
prior transfer directory and obtaining a new action-time decision; never reuse,
overwrite, or merge it implicitly.

- [ ] **Step 2: Require an absent target and transfer site plus bound private export**

```bash
ssh ned-plain "set -eu
  test ! -e /home/ned/sites/burnfund
  test ! -e '$NED_TRANSFER_DIR'
  install -d -m 700 /home/ned/sites/burnfund
  install -d -m 700 '$NED_TRANSFER_DIR'"
rsync -a --protect-args \
  --exclude='.ddev/.ddev-docker-compose-*' \
  --exclude='.ddev/mutagen/' \
  --exclude='.ddev/.dbimageBuild/' \
  --exclude='.ddev/.webimageBuild/' \
  /Users/trav/Websites/burnfund/ ned-plain:/home/ned/sites/burnfund/
scp -p "$MAC_EXPORT" "$MAC_DIGEST" "ned-plain:$NED_TRANSFER_DIR/"
ssh ned-plain "set -eu
  test \"\$(stat -c '%a' '$NED_TRANSFER_DIR/burnfund.sql.gz')\" = 600
  test \"\$(stat -c '%a' '$NED_TRANSFER_DIR/burnfund.sql.gz.sha256')\" = 600
  cd '$NED_TRANSFER_DIR'
  sha256sum -c burnfund.sql.gz.sha256"
```

Ordinary provisioning requires `/home/ned/sites/burnfund` to be absent before
the first write. If it exists, stop without invoking `rsync`, DDEV, or cleanup;
recovery is a separate inspected and explicitly authorized repair, not a retry
against an unknown target. The remote transfer directory is private and
collision-checked before `scp`; its exact 0600 bytes must satisfy the Mac-side
SHA-256 receipt before import. The Mac EXIT trap removes both local and exact
remote transient files after any transfer failure; the NED import EXIT trap
removes them after both failed and successful imports. A cleanup failure remains
visible and leaves its exact private path for recovery review.

- [ ] **Step 3: Compare the nested plugin repository on both machines**

```bash
git -C /Users/trav/Websites/burnfund/wp-content/plugins/burnfund-component-library rev-parse HEAD
ssh ned-plain 'git -C /home/ned/sites/burnfund/wp-content/plugins/burnfund-component-library rev-parse HEAD && git -C /home/ned/sites/burnfund/wp-content/plugins/burnfund-component-library status --short --branch'
```

Expected: the HEADs match and the remote plugin retains its `.git` directory.

- [ ] **Step 4: Start DDEV and import**

```bash
ssh ned-plain "set -eu
  cleanup_remote_after_import() {
    rm -f -- '$NED_TRANSFER_DIR/burnfund.sql.gz' '$NED_TRANSFER_DIR/burnfund.sql.gz.sha256'
    rmdir -- '$NED_TRANSFER_DIR'
  }
  trap 'status=\$?; trap - EXIT HUP INT TERM; cleanup_remote_after_import; exit \$status' EXIT HUP INT TERM
  cd /home/ned/sites/burnfund
  ddev start
  ddev import-db --file='$NED_TRANSFER_DIR/burnfund.sql.gz'
  ddev wp option get home"
```

If the imported home URL differs, run `ddev wp search-replace` using the exact
URL recorded in Step 1 and `https://burnfund.designmachines.xyz`, with
`--skip-columns=guid`, then re-read both `home` and `siteurl`.

- [ ] **Step 5: Remove the Mac transient export after the NED cleanup trap**

```bash
cleanup_mac_transfer
trap - EXIT HUP INT TERM
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
- Create: `/home/ned/ai/ned-ops/systemd/ned-project-health@.service`
- Create: `/home/ned/ai/ned-ops/systemd/ned-project-health@.timer`
- Create: `/home/ned/ai/ned-ops/nedops/render.py`
- Create: `/home/ned/ai/ned-ops/tests/test_render.py`
- Create: `/home/ned/ai/ned-ops/scripts/install-user-units.sh`

**Interfaces:**
- Consumes: `/home/ned/.local/bin/nedctl` and enabled inventory IDs.
- Produces: reboot-persistent `ned-projects.target`, isolated per-project
  control, and separate post-start health evidence.

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

- [ ] **Step 2: Render target membership and health timers from inventory**

`nedops.render` reads the validated inventory and deterministically renders the
target's `Wants=` membership plus one health timer per enabled persistent ID.
The health service runs `nedctl health %i` and exits non-zero when required
runtime lanes are unhealthy. No project-to-project ordering is emitted unless a
future schema names a real prerequisite. Tests prove rendered unit membership
equals the enabled persistent inventory exactly. A lifecycle unit's active
state proves desired startup completed; only the health unit and `nedctl` prove
continued application health.

- [ ] **Step 3: Write the idempotent installer**

The installer sets a fixed PATH, verifies every source file, installs them mode
0644 under `/home/ned/.config/systemd/user`, creates the `nedctl` symlink, runs
`systemctl --user daemon-reload`, and enables—but does not start—
`ned-projects.target`.

- [ ] **Step 4: Validate then install**

```bash
set -eu
cd /home/ned/ai/ned-ops
systemd-analyze --user verify systemd/ned-project@.service systemd/ned-projects.target systemd/ned-project-health@.service systemd/ned-project-health@.timer
python3 -m unittest discover -s tests -v
test "$(loginctl show-user ned -p Linger --value)" = yes
./scripts/install-user-units.sh
```

If the Linger assertion fails, stop before installation, request administrative
approval for `sudo loginctl enable-linger ned`, then rerun this entire validation
block from a fresh shell.

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
git add systemd scripts/install-user-units.sh nedops/render.py tests/test_render.py
git commit -m "feat: persist NED project lifecycles"
```

---

### Task 7: Render and install explicit private Caddy routes

**Files:**
- Create: `/home/ned/ai/ned-ops/generated/designmachines-previews.caddy`
- Create: `/home/ned/ai/ned-ops/scripts/assert-caddy-listeners.py`
- Create: `/home/ned/ai/ned-ops/tests/test_caddy_listeners.py`
- Install: `/etc/caddy/conf.d/designmachines-previews.caddy`
- Modify: `/etc/caddy/Caddyfile`
- Backup: `/etc/caddy/Caddyfile.pre-ned-runtime-20260811`

**Interfaces:**
- Consumes: healthy loopback services.
- Produces: explicit private routes and unknown-host 404 behavior.

- [ ] **Step 1: Render routes from inventory**

`nedops.render` emits exactly two wildcard blocks, one for `*.asmbly.app` and
one for `*.designmachines.xyz`. Each block contains one exact host handler for
every enabled inventory domain in its family, derives its loopback upstream only
from the validated immutable probe/backend fields, and ends in a family-local
404 handler. It rejects an enabled domain outside those two allowlisted suffixes
and fails if a domain has no exact backend. Tests prove that the union of both
rendered host sets equals every enabled inventory domain, no backend is emitted
twice, each upstream is a loopback literal/allowlisted port, and arbitrary
unknown names in *each* family receive 404. The system Caddyfile imports the
mode-0644 installed copy under `/etc/caddy/conf.d`; it does not maintain a
second hand-written project list.

The two private preview blocks bind only to `127.0.0.1` and the single freshly
validated NED Tailscale IPv4 address. They must not bind `0.0.0.0`, `[::]`, a
LAN address, or a public address. Automatic HTTP redirects must follow the same
containment. `assert-caddy-listeners.py` consumes fixed `ss -H -ltnp` output
internally and fails closed unless every Caddy listener for private-preview
ports 80 and 443 is on loopback or that exact Tailscale address,
is owned by the `caddy` service account, and resolves to `/usr/bin/caddy`. It
emits only `caddy_listener_contained=true` or a named failed check, never raw
socket rows or process arguments. Tests cover wildcard, LAN/public, wrong UID,
wrong executable, duplicate, missing, inaccessible-process, and malformed-row
cases.

- [ ] **Step 2: Capture pre-change evidence and an immutable backup**

```bash
set -eu
for host in unknown.asmbly.app unknown.designmachines.xyz; do
  baseline_status="$(curl --insecure --silent --show-error --output /dev/null \
    --write-out '%{http_code}' --connect-timeout 5 --max-time 20 \
    --resolve "$host:443:127.0.0.1" "https://$host/")"
  case "$baseline_status" in
    [0-9][0-9][0-9]) ;;
    *) printf '%s\n' "invalid Caddy baseline status for $host" >&2; exit 1 ;;
  esac
  printf '%s %s\n' "$host" "$baseline_status"
done
test ! -e /etc/caddy/Caddyfile.pre-ned-runtime-20260811
sudo install -m 0644 /etc/caddy/Caddyfile /etc/caddy/Caddyfile.pre-ned-runtime-20260811
```

This is a bounded observation of the known-defective pre-change state, not a
404 acceptance gate. In particular, the existing `*.designmachines.xyz`
wildcard may return an application response. Only the post-reload assertions may
establish unknown-host rejection.

- [ ] **Step 3: Replace both inventory-owned wildcard blocks**

Retain both wildcard blocks' TLS certificate lines and import
`/etc/caddy/conf.d/designmachines-previews.caddy`. The installer copies the
validated generated source there. Installation is a `trav` action and requires
an immediate diff review before reload. It must remove the old hand-written
Assembly host map in the same reviewed edit; retaining it would create a second
route authority outside the inventory renderer.

- [ ] **Step 4: Validate before reload**

```bash
set -eu
restore_caddy_backup() {
  sudo install -m 0644 /etc/caddy/Caddyfile.pre-ned-runtime-20260811 /etc/caddy/Caddyfile || return $?
  sudo caddy validate --config /etc/caddy/Caddyfile || return $?
  sudo systemctl reload caddy || return $?
  systemctl is-active --quiet caddy || return $?
}
if ! sudo caddy validate --config /etc/caddy/Caddyfile; then
  restore_caddy_backup || printf '%s\n' 'Caddy backup restoration failed' >&2
  exit 1
fi
if ! sudo systemctl reload caddy; then
  restore_caddy_backup || printf '%s\n' 'Caddy backup restoration failed' >&2
  exit 1
fi
if ! systemctl is-active --quiet caddy; then
  restore_caddy_backup || printf '%s\n' 'Caddy backup restoration failed' >&2
  exit 1
fi
```

Every validation, reload, and active-state failure restores and validates the
immutable backup. A restoration failure stays non-zero and blocks route proof.

- [ ] **Step 5: Prove known and unknown local-Caddy routes**

```bash
set -eu
assert_local_caddy_route() {
  host="$1"
  test "$(curl --insecure --silent --output /dev/null --write-out '%{http_code}' \
    --connect-timeout 5 --max-time 20 --resolve "$host:443:127.0.0.1" \
    "https://$host/")" = 200
}
for host in \
  dm006.asmbly.app dm021.asmbly.app dm022.asmbly.app \
  travisgertz.designmachines.xyz burnfund.designmachines.xyz livewires.designmachines.xyz; do
  assert_local_caddy_route "$host"
done
for host in unknown.asmbly.app unknown.designmachines.xyz; do
  test "$(curl --insecure --silent --output /dev/null --write-out '%{http_code}' \
    --connect-timeout 5 --max-time 20 --resolve "$host:443:127.0.0.1" \
    "https://$host/")" = 404
done
```

These assertions intentionally omit `--location`: any redirect is a failed
route-lane result, never evidence from another host, protocol, or endpoint. They
prove only the local-Caddy lane; Task 10's Mac commands prove the independent
tailnet lane.

- [ ] **Step 6: Prove private listener containment**

```bash
set -eu
NED_TAILSCALE_IP="$(tailscale ip -4)"
test "$(printf '%s\n' "$NED_TAILSCALE_IP" | sed -n '$=')" = 1
python3 -c 'import ipaddress, sys; ipaddress.IPv4Address(sys.argv[1])' "$NED_TAILSCALE_IP"
cd /home/ned/ai/ned-ops
python3 -m unittest tests.test_caddy_listeners -v
sudo python3 /home/ned/ai/ned-ops/scripts/assert-caddy-listeners.py \
  --port 80 \
  --port 443 \
  --allowed-address 127.0.0.1 \
  --allowed-address "$NED_TAILSCALE_IP" \
  --uid "$(id -u caddy)" \
  --executable /usr/bin/caddy
```

Listener containment is required in addition to successful routes. A wildcard,
LAN, or public listener is a failed private-routing result even if every Host
probe passes.

- [ ] **Step 7: Commit the reviewed routing controls**

```bash
set -eu
cd /home/ned/ai/ned-ops
git add generated/designmachines-previews.caddy nedops/render.py \
  scripts/assert-caddy-listeners.py tests/test_render.py tests/test_caddy_listeners.py
git commit -m "feat: install contained private preview routes"
git status --short
```

---

### Deferred final cross-plan stage: move the approved obsolete NED checkouts to trash

This section is a handoff specification, not the next executable task. Do not
run any command in it during Tasks 1–10. It becomes eligible only after Task 10
has passed both its non-reboot and approved post-reboot repetitions, the T3
control-plane plan has passed service/listener/Serve containment, provider,
session-survival, off-tailnet-denial, and reboot acceptance, released provider
surfaces have been verified or explicitly reported unavailable, and SSH/tmux
recovery has been re-proven. Present those exact receipts with a fresh immediate
removal approval. If any lane is missing, this stage remains deferred and both
checkouts remain in place.

**Files:**
- Move: `/home/ned/sites/designmachines`
- Move: `/home/ned/sites/farewell`

**Interfaces:**
- Produces: recoverable trash entries; upstream and production remain untouched.

- [ ] **Step 1: Re-audit immediately before moving**

```bash
set -eu
REMOVAL_STATE=/home/ned/.local/state/ned-ops/approved-removals/20260811
test ! -e "$REMOVAL_STATE"
install -d -m 700 "$REMOVAL_STATE"
umask 077
audit_clean_root() {
  id="$1"
  root="$2"
  git -C "$root" fetch --prune origin
  test "$(git -C "$root" rev-parse --show-toplevel)" = "$root"
  git -C "$root" rev-parse HEAD > "$REMOVAL_STATE/$id.head"
  git -C "$root" status --porcelain=v1 > "$REMOVAL_STATE/$id.status"
  git -C "$root" log --format='%H' '@{upstream}..HEAD' > "$REMOVAL_STATE/$id.unpushed"
  test ! -s "$REMOVAL_STATE/$id.status"
  test ! -s "$REMOVAL_STATE/$id.unpushed"
}
audit_clean_root designmachines /home/ned/sites/designmachines
audit_clean_root farewell /home/ned/sites/farewell
(cd "$REMOVAL_STATE" && sha256sum \
  designmachines.head designmachines.status designmachines.unpushed \
  farewell.head farewell.status farewell.unpushed > approved.sha256)
test "$(stat -c '%a' "$REMOVAL_STATE")" = 700
test ! -e /home/ned/.local/share/Trash/files/designmachines-ned-20260811
test ! -e /home/ned/.local/share/Trash/files/farewell-ned-20260811
```

Expected: both status and unpushed-commit outputs are empty. Stop if either is
non-empty, either top-level path differs, or either exact trash destination
already exists. The protected state directory is the approval receipt: it binds
both root-repository HEADs and the empty status/unpushed evidence by SHA-256 for
the action-time equality check. It is not a generic scratch directory and may
not be reused by a later removal attempt.

- [ ] **Step 2: Request immediate removal confirmation**

Present the two exact source paths, root HEADs and empty status/unpushed evidence
from the protected approval receipt, exact collision-free trash destinations,
and rollback paths. Do not
continue until the user explicitly confirms this immediate stop-and-move action.
The approval of this design is not a substitute for this action-time gate.

- [ ] **Step 3: After confirmation, re-audit equality, stop recognized runtimes, and move both checkouts**

```bash
set -eu
REMOVAL_STATE=/home/ned/.local/state/ned-ops/approved-removals/20260811
test "$(stat -c '%a' "$REMOVAL_STATE")" = 700
(cd "$REMOVAL_STATE" && sha256sum -c approved.sha256)
recheck_approved_root() {
  id="$1"
  root="$2"
  git -C "$root" fetch --prune origin
  test "$(git -C "$root" rev-parse --show-toplevel)" = "$root"
  git -C "$root" rev-parse HEAD > "$REMOVAL_STATE/$id.current.head"
  git -C "$root" status --porcelain=v1 > "$REMOVAL_STATE/$id.current.status"
  git -C "$root" log --format='%H' '@{upstream}..HEAD' > "$REMOVAL_STATE/$id.current.unpushed"
  cmp --silent "$REMOVAL_STATE/$id.head" "$REMOVAL_STATE/$id.current.head"
  cmp --silent "$REMOVAL_STATE/$id.status" "$REMOVAL_STATE/$id.current.status"
  cmp --silent "$REMOVAL_STATE/$id.unpushed" "$REMOVAL_STATE/$id.current.unpushed"
  test ! -s "$REMOVAL_STATE/$id.current.status"
  test ! -s "$REMOVAL_STATE/$id.current.unpushed"
}
recheck_approved_root designmachines /home/ned/sites/designmachines
recheck_approved_root farewell /home/ned/sites/farewell
test ! -e /home/ned/.local/share/Trash/files/designmachines-ned-20260811
test ! -e /home/ned/.local/share/Trash/files/farewell-ned-20260811
stop_recognized_runtime() {
  root="$1"
  compose_file=""
  compose_count=0
  for candidate in docker-compose.yml docker-compose.yaml compose.yml compose.yaml; do
    if test -f "$root/$candidate"; then
      compose_count=$((compose_count + 1))
      compose_file="$root/$candidate"
    fi
  done
  if test -f "$root/.ddev/config.yaml" && test "$compose_count" -eq 0; then
    (cd "$root" && ddev stop)
    return
  fi
  if test ! -f "$root/.ddev/config.yaml" && test "$compose_count" -eq 1; then
    docker compose -f "$compose_file" stop
    return
  fi
  if test ! -f "$root/.ddev/config.yaml" && test "$compose_count" -eq 0; then
    printf '%s\n' "no recognized persistent runtime: $root"
    return
  fi
  printf '%s\n' "unknown or ambiguous runtime markers: $root" >&2
  return 1
}
stop_recognized_runtime /home/ned/sites/designmachines
stop_recognized_runtime /home/ned/sites/farewell
install -d /home/ned/.local/share/Trash/files
mv /home/ned/sites/designmachines /home/ned/.local/share/Trash/files/designmachines-ned-20260811
mv /home/ned/sites/farewell /home/ned/.local/share/Trash/files/farewell-ned-20260811
```

- [ ] **Step 4: Verify recoverability and root HEAD identity**

```bash
test ! -e /home/ned/sites/designmachines
test ! -e /home/ned/sites/farewell
test -d /home/ned/.local/share/Trash/files/designmachines-ned-20260811
test -d /home/ned/.local/share/Trash/files/farewell-ned-20260811
test "$(git -C /home/ned/.local/share/Trash/files/designmachines-ned-20260811 rev-parse --show-toplevel)" = "/home/ned/.local/share/Trash/files/designmachines-ned-20260811"
test "$(git -C /home/ned/.local/share/Trash/files/designmachines-ned-20260811 rev-parse HEAD)" = "$(cat /home/ned/.local/state/ned-ops/approved-removals/20260811/designmachines.head)"
test "$(git -C /home/ned/.local/share/Trash/files/farewell-ned-20260811 rev-parse --show-toplevel)" = "/home/ned/.local/share/Trash/files/farewell-ned-20260811"
test "$(git -C /home/ned/.local/share/Trash/files/farewell-ned-20260811 rev-parse HEAD)" = "$(cat /home/ned/.local/state/ned-ops/approved-removals/20260811/farewell.head)"
```

Any receipt mismatch, unknown runtime marker, runtime stop failure, or HEAD
mismatch is a failed move verification, not successful cleanup. In particular,
do not move either checkout when the other cannot be independently classified
and stopped; leave the protected approval state for recovery review.

---

### Task 9: Add `ned:operate` to Depot

**Files:**
- Create worktree: `/home/ned/ai/depot/.worktrees/ned-operate` from refreshed
  `origin/main`; the shared `/home/ned/ai/depot` checkout remains untouched.
- Create: `/home/ned/ai/depot/.worktrees/ned-operate/plugins/ned/skills/operate/SKILL.md`
- Create: `/home/ned/ai/depot/.worktrees/ned-operate/plugins/ned/skills/operate/references/ned-runtime.md`
- Create: `/home/ned/ai/depot/.worktrees/ned-operate/description-evals/ned-operate.json`
- Modify: `/home/ned/ai/depot/.worktrees/ned-operate/plugins/ned/.claude-plugin/plugin.json`
- Modify: `/home/ned/ai/depot/.worktrees/ned-operate/.claude-plugin/marketplace.json`
- Regenerate: Codex manifests and `docs/search-index.md`

**Interfaces:**
- Consumes: installed `nedctl` and approved design.
- Produces: portable skill version `1.8.0`, with no MCP or secret dependency.

- [ ] **Step 1: Create and bind a fresh isolated Depot worktree**

```bash
set -eu
umask 077
test -d /home/ned/.local/state/ned-ops
NED_OPERATE_ISOLATION_STATE="$(mktemp -d /home/ned/.local/state/ned-ops/ned-operate-isolation.XXXXXX)"
chmod 0700 "$NED_OPERATE_ISOLATION_STATE"
case "$NED_OPERATE_ISOLATION_STATE" in
  /home/ned/.local/state/ned-ops/ned-operate-isolation.*) ;;
  *) printf '%s\n' 'invalid isolation state path' >&2; exit 1 ;;
esac
printf 'NED_OPERATE_ISOLATION_STATE=%s\n' "$NED_OPERATE_ISOLATION_STATE"
git -C /home/ned/ai/depot rev-parse HEAD > "$NED_OPERATE_ISOLATION_STATE/shared-head.before"
git -C /home/ned/ai/depot status --porcelain=v1 > "$NED_OPERATE_ISOLATION_STATE/shared-status.before"
test ! -e /home/ned/ai/depot/.worktrees/ned-operate
if git -C /home/ned/ai/depot show-ref --verify --quiet refs/heads/ai/ned-operate; then
  printf '%s\n' 'branch ai/ned-operate already exists' >&2
  exit 1
fi
git -C /home/ned/ai/depot fetch --prune origin main
git -C /home/ned/ai/depot worktree add -b ai/ned-operate /home/ned/ai/depot/.worktrees/ned-operate origin/main
test "$(git -C /home/ned/ai/depot/.worktrees/ned-operate rev-parse HEAD)" = "$(git -C /home/ned/ai/depot/.worktrees/ned-operate rev-parse origin/main)"
test -z "$(git -C /home/ned/ai/depot/.worktrees/ned-operate status --porcelain)"
```

The fetch may update shared Git refs, but no command may edit, clean, reset, or
commit through the shared checkout. All remaining Task 9 paths and commands run
inside `/home/ned/ai/depot/.worktrees/ned-operate`. Record the printed exact
private state path in the non-secret execution handoff; do not rediscover it by
glob, select a newest directory, or copy it to a fixed pointer. Task 10 requires
that exact path in its fresh shell. A failed or interrupted Task 9 preserves the
directory for explicit recovery review.

- [ ] **Step 2: Add trigger evals before the skill**

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

- [ ] **Step 3: Write the skill frontmatter and guarded workflow**

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

- [ ] **Step 4: Write the runtime reference**

Record account boundaries, `/home/ned/{assembly,sites,ai}`, project
classifications, plain versus tmux SSH aliases, lifecycle/loopback/Caddy/
Cloudflare evidence lanes, and exact read-only recovery commands. State that
ports and enabled state come from `nedctl list --json`, not the plugin.

- [ ] **Step 5: Bump canonical metadata to 1.8.0**

Add the fourth skill capability `operate` with no `mcpDependencies`; update the
plugin and marketplace descriptions; synchronize both versions at `1.8.0`;
change `capabilities_summary.skills` from 3 to 4; add operations tags.

- [ ] **Step 6: Regenerate and validate**

```bash
cd /home/ned/ai/depot/.worktrees/ned-operate
./tools/generate-codex-manifests.py
./tools/validate-composition.sh --generate-index
./tools/eval-descriptions.sh ned-operate.json
./tools/validate-dual-compat.sh
./tools/validate-composition.sh --all
git diff --check
```

Expected: focused eval at least 70%; dual and full composition pass.

- [ ] **Step 7: Commit the reviewed plugin change**

```bash
cd /home/ned/ai/depot/.worktrees/ned-operate
git add plugins/ned .claude-plugin/marketplace.json .agents/plugins/marketplace.json description-evals/ned-operate.json docs/search-index.md
git commit -m "feat(ned): add guarded NED operations skill"
```

Do not tag or push in this step.

- [ ] **Step 8: Request release authority, publish, and verify both providers**

After a fresh exact-head review and `./tools/check-release-preflight.sh` receipt,
request explicit authority for the push and `ned` 1.8.0 tag. If approved, push
the reviewed `ai/ned-operate` worktree commit, publish the tag on that exact
commit, update the Depot
marketplace in NED Codex and Claude, and prove both report `ned` 1.8.0 with the
`operate` skill. If authority is not granted or publication fails, acceptance
must say `ned:operate locally validated; released endpoint unavailable`.

---

### Task 10: Verify the complete private runtime and present the reboot gate

**Files:**
- Modify only if evidence identifies a defect in an earlier task.

**Interfaces:**
- Produces: local and tailnet evidence; Cloudflare remains explicitly unproven.

- [ ] **Step 1: Bind repository and service state**

```bash
set -eu
: "${NED_OPERATE_ISOLATION_STATE:?supply the exact Task 9 isolation state path}"
: "${NED_OPERATE_VERIFICATION_PHASE:?set pre-reboot or post-reboot}"
case "$NED_OPERATE_ISOLATION_STATE" in
  /home/ned/.local/state/ned-ops/ned-operate-isolation.*) ;;
  *) printf '%s\n' 'invalid isolation state path' >&2; exit 1 ;;
esac
case "$NED_OPERATE_VERIFICATION_PHASE" in
  pre-reboot|post-reboot) ;;
  *) printf '%s\n' 'invalid isolation verification phase' >&2; exit 1 ;;
esac
test -d "$NED_OPERATE_ISOLATION_STATE"
test ! -L "$NED_OPERATE_ISOLATION_STATE"
test "$(stat -c '%a' "$NED_OPERATE_ISOLATION_STATE")" = 700
test "$(stat -c '%u' "$NED_OPERATE_ISOLATION_STATE")" = "$(id -u ned)"
git -C /home/ned/ai/ned-ops status --short --branch
git -C /home/ned/ai/ned-ops log -1 --oneline
git -C /home/ned/ai/depot/.worktrees/ned-operate status --short --branch
git -C /home/ned/ai/depot/.worktrees/ned-operate log -2 --oneline
test ! -e "$NED_OPERATE_ISOLATION_STATE/shared-head.$NED_OPERATE_VERIFICATION_PHASE"
test ! -e "$NED_OPERATE_ISOLATION_STATE/shared-status.$NED_OPERATE_VERIFICATION_PHASE"
git -C /home/ned/ai/depot rev-parse HEAD > "$NED_OPERATE_ISOLATION_STATE/shared-head.$NED_OPERATE_VERIFICATION_PHASE"
git -C /home/ned/ai/depot status --porcelain=v1 > "$NED_OPERATE_ISOLATION_STATE/shared-status.$NED_OPERATE_VERIFICATION_PHASE"
if ! cmp --silent "$NED_OPERATE_ISOLATION_STATE/shared-head.before" "$NED_OPERATE_ISOLATION_STATE/shared-head.$NED_OPERATE_VERIFICATION_PHASE" ||
   ! cmp --silent "$NED_OPERATE_ISOLATION_STATE/shared-status.before" "$NED_OPERATE_ISOLATION_STATE/shared-status.$NED_OPERATE_VERIFICATION_PHASE"; then
  printf '%s\n' "shared checkout isolation mismatch; evidence preserved: $NED_OPERATE_ISOLATION_STATE" >&2
  exit 1
fi
if ! systemctl --user --no-pager --full status ned-projects.target; then
  printf '%s\n' "runtime status failed; isolation evidence preserved: $NED_OPERATE_ISOLATION_STATE" >&2
  exit 1
fi
printf '%s\n' "$NED_OPERATE_VERIFICATION_PHASE isolation verified; evidence retained: $NED_OPERATE_ISOLATION_STATE"
```

The shared-checkout comparison is an isolation gate: pre-existing changes are
allowed only when the exact before/after HEAD and porcelain snapshots match.
Run the first pass with `NED_OPERATE_VERIFICATION_PHASE=pre-reboot` and the
approved post-reboot repetition with `NED_OPERATE_VERIFICATION_PHASE=post-reboot`.
Comparison or runtime-status failure preserves all receipts. The pre-reboot pass
and post-reboot Step 1 pass also preserve them intentionally; final cleanup runs
only after every post-reboot lane succeeds.

- [ ] **Step 2: Run every operator evidence lane**

```bash
/home/ned/.local/bin/nedctl list
/home/ned/.local/bin/nedctl status
/home/ned/.local/bin/nedctl health
/home/ned/.local/bin/nedctl routes
for id in dm006 dm021 dm022 travisgertz burnfund livewires; do /home/ned/.local/bin/nedctl doctor "$id"; done
```

Expected: lifecycle, loopback, and local Caddy lanes pass; tailnet is reported
separately from the Mac receipt, and external Access is unconfigured.

- [ ] **Step 3: Prove reserved runtimes remain absent**

```bash
systemctl --user is-enabled ned-projects.target
systemctl --user is-active ned-project@dm023.service; test "$?" -ne 0
systemctl --user is-active ned-project@dm024.service; test "$?" -ne 0
```

- [ ] **Step 4: Verify private hostnames from the Mac**

```bash
set -eu
NED_TAILSCALE_IP="$(ssh ned-plain 'tailscale ip -4')"
test "$(printf '%s\n' "$NED_TAILSCALE_IP" | sed -n '$=')" = 1
python3 -c 'import ipaddress, sys; ipaddress.IPv4Address(sys.argv[1])' "$NED_TAILSCALE_IP"
assert_mac_tailnet_route() {
  host="$1"
  test "$(curl --insecure --silent --output /dev/null --write-out '%{http_code}' \
    --connect-timeout 5 --max-time 20 --resolve "$host:443:$NED_TAILSCALE_IP" \
    "https://$host/")" = 200
}
for host in \
  dm006.asmbly.app dm021.asmbly.app dm022.asmbly.app \
  travisgertz.designmachines.xyz burnfund.designmachines.xyz livewires.designmachines.xyz; do
  assert_mac_tailnet_route "$host"
done
for host in unknown.asmbly.app unknown.designmachines.xyz; do
  test "$(curl --insecure --silent --output /dev/null --write-out '%{http_code}' \
    --connect-timeout 5 --max-time 20 --resolve "$host:443:$NED_TAILSCALE_IP" \
    "https://$host/")" = 404
done
```

The Mac receives the NED IPv4 from the independent authenticated SSH transport,
validates it as one literal address, and binds every TLS hostname to that exact
address with `--resolve`; it does not use ambient DNS. These commands intentionally
omit `--location`, so a 3xx cannot become evidence for another endpoint.

- [ ] **Step 5: Prove denial from outside the tailnet**

Use a controlled device whose Tailscale client is stopped and whose routing
table has no tailnet route. Verify that state through the platform's documented
status interface without printing node or account metadata, then run this block
on that device:

```bash
set -eu
for scheme in http https; do
  for host in \
    dm006.asmbly.app dm021.asmbly.app dm022.asmbly.app \
    travisgertz.designmachines.xyz burnfund.designmachines.xyz livewires.designmachines.xyz; do
    if curl --insecure --silent --output /dev/null \
      --connect-timeout 5 --max-time 10 "$scheme://$host/"; then
      printf '%s\n' "off-tailnet exposure detected: $scheme $host" >&2
      exit 1
    fi
  done
done
printf '%s\n' 'off_tailnet_private_routes_denied=true'
```

Any HTTP response is a failure, regardless of status. DNS failure, unroutable
private addressing, or connection refusal is recorded only as the single
denial verdict above. This lane is independent of the NED listener verifier and
Mac tailnet success; if no controlled off-tailnet device is available, report
the lane unproven and block private-runtime acceptance.

- [ ] **Step 6: Request immediate approval before reboot**

Run Steps 1–5 first with `NED_OPERATE_VERIFICATION_PHASE=pre-reboot` and present
that non-reboot evidence. After explicit approval, run `sudo systemctl reboot`.
After reconnecting, export the same exact `NED_OPERATE_ISOLATION_STATE`, set
`NED_OPERATE_VERIFICATION_PHASE=post-reboot`, repeat Steps 1-5, and verify the
persistent set returned while ephemeral and deferred services stayed inactive. The two
retirement checkouts must still be present and unchanged at this point; only
after this post-reboot proof and the separate T3/provider/recovery acceptance may
the deferred final cross-plan retirement handoff be presented for approval.

After every repeated post-reboot lane has passed, remove only the exact isolation
receipts:

```bash
set -eu
: "${NED_OPERATE_ISOLATION_STATE:?supply the exact Task 9 isolation state path}"
test "${NED_OPERATE_VERIFICATION_PHASE:?}" = post-reboot
case "$NED_OPERATE_ISOLATION_STATE" in
  /home/ned/.local/state/ned-ops/ned-operate-isolation.*) ;;
  *) printf '%s\n' 'invalid isolation state path' >&2; exit 1 ;;
esac
test -d "$NED_OPERATE_ISOLATION_STATE"
test ! -L "$NED_OPERATE_ISOLATION_STATE"
cleanup_failed=0
for receipt in \
  shared-head.before shared-status.before \
  shared-head.pre-reboot shared-status.pre-reboot \
  shared-head.post-reboot shared-status.post-reboot; do
  if test -e "$NED_OPERATE_ISOLATION_STATE/$receipt"; then
    if unlink "$NED_OPERATE_ISOLATION_STATE/$receipt"; then :; else cleanup_failed=1; fi
  fi
done
if rmdir "$NED_OPERATE_ISOLATION_STATE"; then :; else cleanup_failed=1; fi
test "$cleanup_failed" -eq 0
```

Any cleanup failure is reported with the exact remaining private path; never
glob for or remove another run's state.
