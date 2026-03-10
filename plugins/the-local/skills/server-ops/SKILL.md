---
name: server-ops
description: Provides complete operational knowledge for The Local's self-hosted Matrix infrastructure — Docker Compose service management, SSH access, Matrix user creation, database backup, performance monitoring, and deployment methods. Use when SSH-ing into the server, managing Docker services, creating Matrix accounts, checking logs, backing up data, restarting Synapse or other services, or performing any operational task on the DigitalOcean droplet at 143.110.221.2. Trigger for any mention of: the droplet, docker compose, synapse restart, user creation, register_new_matrix_user, backup, logs, force-recreate, or server-side operations on thelocal.chat infrastructure.
---

# The Local — Server Operations

Self-hosted Matrix infrastructure on a DigitalOcean droplet. All commands run from `/opt/thelocal` as root.

## Access

```bash
ssh root@143.110.221.2
cd /opt/thelocal
```

## Services (Docker Compose)

Six services on a shared `thelocal` Docker network:

| Service | Role | Internal Port |
|---------|------|---------------|
| caddy | Reverse proxy + TLS | 80, 443 |
| synapse | Matrix homeserver | 8008 |
| postgres | Synapse database | 5432 |
| element | Element Web browser client | (static files) |
| livekit | WebRTC SFU for calls | 7880, 7881, 50100-50200/udp |
| lk-jwt | JWT auth bridge for LiveKit | 8080 |

**Caddy routes**: `thelocal.chat` → Element + `.well-known`, `matrix.thelocal.chat` → Synapse, `/livekit/jwt/*` → JWT service, `/livekit/sfu/*` → LiveKit WebSocket.

## Common Commands

```bash
# Service logs
docker compose logs -f synapse
docker compose logs -f caddy
docker compose logs --tail=100 synapse

# Restart services
docker compose restart synapse
docker compose restart element
docker compose restart        # all services

# Update images and redeploy
docker compose pull && docker compose up -d

# Resource usage (quick check)
docker stats --no-stream
```

## Deploying File Changes

**Two deployment methods depending on change type:**

### Method 1: scp (preserves inode — no container recreate needed)

Use for: `assets/custom.css`, `assets/index.html`, `element-config.json`, `welcome/index.html`, `templates/*`

```bash
# From local repo root
scp assets/custom.css root@143.110.221.2:/opt/thelocal/assets/custom.css
scp assets/index.html root@143.110.221.2:/opt/thelocal/assets/index.html
scp templates/*.html root@143.110.221.2:/opt/thelocal/templates/
```

**Why scp**: Docker bind mounts track inodes (not filenames). `scp` overwrites in-place, preserving the inode — the container sees the change immediately without restart.

### Method 2: git pull (replaces inodes — requires --force-recreate)

Use for: `docker-compose.yml`, `homeserver.yaml`, `Caddyfile`, or bulk changes.

```bash
ssh root@143.110.221.2 'cd /opt/thelocal && git pull && docker compose up -d --force-recreate element'
```

**Why force-recreate**: `git pull` replaces file inodes. The running container still points to the old inode. `--force-recreate` remounts the bind mounts fresh.

After Synapse config changes:
```bash
# Regenerate .active config from template, then restart
ssh root@143.110.221.2 'cd /opt/thelocal && source .env && sed -e "s|%%POSTGRES_PASSWORD%%|${POSTGRES_PASSWORD}|g" -e "s|%%REGISTRATION_SECRET%%|${REGISTRATION_SECRET}|g" -e "s|%%MACAROON_SECRET%%|${MACAROON_SECRET}|g" -e "s|%%FORM_SECRET%%|${FORM_SECRET}|g" -e "s|%%RESEND_API_KEY%%|${RESEND_API_KEY}|g" homeserver.yaml > homeserver.yaml.active && docker compose restart synapse'
```

## Matrix User Management

```bash
# Create a new user (CLI — no email required)
docker compose exec synapse register_new_matrix_user \
  -u USERNAME -p PASSWORD --no-admin \
  -c /data/homeserver.yaml http://localhost:8008

# Create admin user
docker compose exec synapse register_new_matrix_user \
  -u USERNAME -p PASSWORD --admin \
  -c /data/homeserver.yaml http://localhost:8008
```

**User ID format**: `@username:thelocal.chat` (permanent — cannot change domain)

**Naming convention**:
- Spaces: "The Local [Co-op Name]" or "The Local [Number]" (union local style)
- DM rooms: `#dm-general:thelocal.chat`, `#dm-assembly`, `#dm-watercooler`
- Co-op rooms: `#taco-general`, `#solidstate-general`

## Database Backup

```bash
# PostgreSQL dump
docker compose exec postgres pg_dump -U synapse synapse > backup-$(date +%Y%m%d).sql

# Media store backup
docker compose cp synapse:/data/media_store ./media-backup-$(date +%Y%m%d)
```

DigitalOcean weekly automated backups are enabled on the droplet.

## Performance & Monitoring

**Current resource profile** (idle): ~190MB across 6 containers, ~1GB total with buffers.

DigitalOcean built-in metrics dashboard covers: CPU, RAM, disk, network.

**Watch for**:
- RAM consistently above 80% → resize droplet ($12/mo → $24/mo for 4GB)
- CPU spikes during calls → normal (LiveKit transcoding)
- Unexpected disk growth → media uploads accumulating in `/data/media_store`

**Tuning applied** (in `homeserver.yaml`):
- Cache factor: 0.3 (conservative for 2GB RAM)
- 2GB swap file (swappiness 10)
- Presence disabled (resource savings)
- Rate limiting tuned for call key-sharing bursts

## Rollout Phases

- **Circle 1** (current): DM + collaborators, 5-10 people. Federation disabled, CLI-only accounts.
- **Circle 2** (3-6mo): Solid State co-ops, Slate, TACO — 30-50 people.
- **Circle 3** (6-12mo): Broader movement. Enable federation: remove `federation_domain_whitelist` from `homeserver.yaml`.

## Known Issues

- **Element X mobile** repeatedly prompts for recovery key — widespread Element bug. Workaround: reset Secure Backup, skip encryption prompts on mobile.
- **Element desktop app** requires direct homeserver URL `matrix.thelocal.chat` (not root domain) for login.
- **DigitalOcean blocks SMTP ports** 25/465/587. Resend SMTP uses port 2587.
- **QR code login** requires Matrix Authentication Service — not implemented in Circle 1.
- **Phone verification** requires Sydent + Twilio — not worth it for this scale.
