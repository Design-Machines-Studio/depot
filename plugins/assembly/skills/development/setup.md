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

Visit `http://assembly.coop.site` — the app should be running.

## How It Works

`scripts/start.sh` auto-detects your environment:

- **ddev mode** — if ddev-router is running, installs Traefik config to `~/.ddev/traefik/config/assembly.yaml` and connects to the `ddev_default` network
- **Standalone mode** — creates `ddev_default` network and starts its own Traefik container

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
npm run build  # Production build → public/dist/
```

Build uses lightningcss for CSS bundling/minification and esbuild for JS.

## Backend Development

All Go commands run inside Docker — never on the host:

```bash
docker compose exec app templ generate              # Regenerate Templ files
docker compose exec app go build -o assembly ./cmd/api  # Build binary
docker compose exec app go test ./...               # Run tests
docker compose restart app                          # Restart to pick up changes
```

Air handles this automatically on file save. Manual commands are for troubleshooting.

## Configuration

No `.env` files needed. Configuration lives in YAML:

- `backend/config/coop.yaml` — Co-op identity (name, jurisdiction, founded date)
- `backend/config/modules.yaml` — Feature toggles (members, proposals, meetings, etc.)

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
