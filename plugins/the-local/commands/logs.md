---
name: logs
description: Tail Docker Compose logs for The Local services (synapse, caddy, element, livekit, postgres). Defaults to synapse if no service specified.
argument-hint: "[synapse|caddy|element|livekit|lk-jwt|postgres|all]"
allowed-tools: Bash
---

Tail logs for The Local Docker services on the server at `root@143.110.221.2`.

## Available Services

- `synapse` — Matrix homeserver (default)
- `caddy` — Reverse proxy / TLS
- `element` — Element Web (static; rarely has log output)
- `livekit` — WebRTC SFU for calls
- `lk-jwt` — LiveKit JWT auth bridge
- `postgres` — PostgreSQL database

## Commands

If the user specifies a service, tail that service. If no argument, default to `synapse`.

```bash
# Follow logs for a specific service
ssh root@143.110.221.2 'cd /opt/thelocal && docker compose logs -f synapse'

# Last 100 lines without following
ssh root@143.110.221.2 'cd /opt/thelocal && docker compose logs --tail=100 synapse'

# All services
ssh root@143.110.221.2 'cd /opt/thelocal && docker compose logs -f'

# Quick resource check (not logs, but useful alongside)
ssh root@143.110.221.2 'docker stats --no-stream'
```

## Common Log Patterns to Watch For

In Synapse logs:
- `ERROR` lines → actual problems
- `WARN` lines → usually informational (rate limiting, federation probes)
- Template errors → `jinja2.exceptions.TemplateNotFound`
- Email errors → connection to smtp.resend.com
- Auth errors → `Failed to authenticate`

Run the command, show the output, and highlight any errors or warnings worth noting.
