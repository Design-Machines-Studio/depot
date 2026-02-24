# Production Deployment

## Architecture

- **Host**: Digital Ocean droplet (Ubuntu 24.04)
- **Reverse proxy**: Caddy (auto-TLS via Let's Encrypt)
- **Containers**: Docker images from GitHub Container Registry (GHCR)
- **CI/CD**: GitHub Actions on push to `main`
- **Multi-instance**: Each co-op runs as a separate container

## Pipeline Flow

1. Push to `main` triggers `.github/workflows/deploy.yml`
2. GitHub Actions builds multi-stage Docker image (`Dockerfile`)
3. Image pushed to `ghcr.io/design-machines-studio/assembly:latest` (+ SHA tag)
4. SSH to droplet: `docker compose pull && up -d`

## Build Stages (Dockerfile)

| Stage | Base | Work |
|-------|------|------|
| Frontend | node:20-alpine | `npm ci`, lightningcss + esbuild → `public/dist/` |
| Backend | golang:1.25-alpine | `templ generate`, `go build` → binary |
| Runtime | alpine:3.19 | Binary + migrations + config + static assets |

The runtime image includes a healthcheck on `/health` with a 30-second start period.

## Key Files

| File | Purpose |
|------|---------|
| `Dockerfile` | 3-stage production build |
| `deploy/docker-compose.prod.yml` | Multi-instance production orchestration |
| `deploy/Caddyfile` | Reverse proxy with auto-TLS |
| `deploy/setup.sh` | Droplet provisioning (Docker + Caddy + firewall) |
| `.github/workflows/deploy.yml` | CI/CD pipeline |

## Multi-Instance Design

Each co-op is a separate Docker container with isolated config and data:

```yaml
# deploy/docker-compose.prod.yml
dm006:
  image: ghcr.io/design-machines-studio/assembly:latest
  ports: ["8001:8080"]
  volumes:
    - dm006-data:/app/data
    - ./instances/dm006/config:/app/config:ro
```

Caddy routes domains to containers:

```
dm006.asmbly.app {
    reverse_proxy localhost:8001
}
```

## Droplet Setup (First Time)

1. Run `deploy/setup.sh` as root on a fresh Ubuntu 24.04 droplet
2. Add deploy SSH key to `/home/deploy/.ssh/authorized_keys`
3. Authenticate to GHCR: `docker login ghcr.io` (PAT with `read:packages`)
4. Create instance directories:
   ```bash
   mkdir -p /opt/assembly/instances/dm006/config
   ```
5. Copy `coop.yaml` and `modules.yaml` to the instance config directory
6. Copy `deploy/docker-compose.prod.yml` and `deploy/Caddyfile` to `/opt/assembly/`
7. Run `docker compose -f docker-compose.prod.yml up -d`

## Adding a New Instance

1. Add a service block in `deploy/docker-compose.prod.yml` (new name, port, volume)
2. Add a domain block in `deploy/Caddyfile`
3. Create config directory: `mkdir -p /opt/assembly/instances/{id}/config`
4. Copy `coop.yaml` + `modules.yaml` to the new instance config
5. Deploy: `docker compose -f docker-compose.prod.yml up -d`

## GitHub Actions Secrets

| Secret | Purpose |
|--------|---------|
| `DROPLET_IP` | Droplet IP address for SSH deployment |
| `DEPLOY_SSH_KEY` | SSH private key for the `deploy` user |

## Monitoring

- Healthcheck: `curl https://dm006.asmbly.app/health`
- Logs: `docker compose -f docker-compose.prod.yml logs dm006`
- Image info: `docker image inspect ghcr.io/design-machines-studio/assembly:latest`

## Rollback

Pull a previous image tag (Git SHA) from GHCR:

```bash
docker compose -f docker-compose.prod.yml pull  # pulls :latest
# Or pin a specific version:
# image: ghcr.io/design-machines-studio/assembly:abc1234
docker compose -f docker-compose.prod.yml up -d
```

## Related Architecture Docs

These docs in the Assembly repo define the broader distribution strategy:

| Document | Purpose |
|----------|---------|
| `docs/DISTRIBUTION.md` | Three-phase distribution model, registry, config hierarchy |
| `docs/PILOT-SCOPE.md` | What ships for the first pilot client, acceptance criteria |
| `docs/UPDATE-FLOW.md` | Update check/apply/rollback sequence (Phase 1+) |
