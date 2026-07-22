# Development Setup

## Prerequisites

- Docker Desktop (running)
- Node.js 20+ (for frontend tooling: lightningcss, esbuild)
- `/etc/hosts` entry:
  ```
  127.0.0.1 assembly.coop.site api.assembly.coop.site
  ```

## Quick Start

```bash
npm install                # Frontend dev dependencies
./scripts/start.sh         # Auto-detects ddev-router vs standalone
```

Visit `http://assembly.coop.site` -- the app should be running.

## How It Works

`scripts/start.sh` auto-detects your environment:

- **ddev mode** -- if ddev-router is running, installs Traefik config to `~/.ddev/traefik/config/assembly.yaml` and connects to the `ddev_default` network
- **Standalone mode** -- creates `ddev_default` network and starts its own Traefik container

The Go backend runs inside Docker with Air for hot reload. Templ files are regenerated and the binary rebuilt automatically on save.

## Key Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Dev environment (Go app with Air hot reload) |
| `Dockerfile.dev` | Dev image: golang:1.25-alpine + templ + air |
| `scripts/start.sh` | Smart startup (ddev or standalone) |
| `scripts/stop.sh` | Clean shutdown + Traefik config cleanup |
| `vite.config.js` | Frontend HMR + API proxy to Docker |
| `package.json` | Build scripts (lightningcss + esbuild) |
| `.air.toml` | Air config: watches .go/.templ, rebuilds on save |

## Frontend Development

Vite runs on port 3000 for CSS/JS hot module replacement:

```bash
npm run dev    # Start Vite dev server (HMR)
npm run build  # Production build -> public/dist/
```

Build uses lightningcss for CSS bundling/minification and esbuild for JS.

## Backend Development

All Go commands run inside Docker -- never on the host. Manual verification is
planned through Workflow Kernel using
`plugins/assembly/skills/assembly-build/references/assembly-baseplate-verification-profile.json`.
Use `/assembly-build generate`, `/assembly-build build`, `/assembly-build
focused`, `/assembly-build test`, or `/assembly-build race`; execute only the
safe argv selected by the repository verification plan.

The Baseplate profile defaults to an ephemeral Compose `run --rm --no-deps`
container, `go tool templ generate`, `-tags=dev`, fresh `-count=1` tests, and the
`./cmd/assembly` package. A project profile can override those defaults, but an
`exec app` command requires current matching service-state proof. A missing,
stopped, stale, or mismatched service uses a declared ephemeral lane or returns
`unavailable`; ambient Docker state is not proof.

Project configuration outranks the Assembly profile, and the Assembly profile
outranks heuristics. If Workflow Kernel, a valid matching profile, or required
declarations cannot be resolved, stop with actionable `unavailable` evidence
instead of guessing a generic command. Air still handles rebuilds on file save;
the planner path is for fresh verification and troubleshooting.

Focused changed-package tests do not automatically force full race. Full,
race, security, container, browser, accessibility, PR, push, schedule,
merge-group, and post-merge evidence remain separate. UX task frontmatter is
authoritative; browser recovery remains primary browser quit, fresh primary
retry, a different configured engine, then `human_help_required`, with curl as
diagnostic only.

## Configuration

No `.env` files needed. Configuration lives in YAML:

- `backend/config/coop.yaml` -- Co-op identity (name, jurisdiction, founded date)
- `backend/config/modules.yaml` -- Feature toggles (members, proposals, meetings, etc.)

## Database

SQLite at `backend/data/coop.db` (volume-mounted, gitignored). Migrations in `backend/migrations/` run automatically on startup.

## Networking

- App: port 8090 (Air proxy) inside Docker
- API: port 8080 internal, proxied via Traefik to `assembly.coop.site`
- Vite: port 3000, proxies `/api` and `/sse` to the Docker API service
- `/etc/hosts` maps `*.coop.site` domains to `127.0.0.1`

## Teardown

```bash
./scripts/stop.sh   # Stops containers, removes Traefik config
```
