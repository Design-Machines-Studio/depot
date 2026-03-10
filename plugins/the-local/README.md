# the-local

Claude Code plugin for The Local — a self-hosted Matrix communication network for the workplace democracy movement, built on Synapse + Element Web.

## What This Plugin Provides

Three auto-activating skills that load context when you're working on The Local, and three slash commands for common operational tasks.

## Skills (auto-activating)

| Skill | Triggers when you're... |
|-------|------------------------|
| `server-ops` | SSH-ing in, managing Docker, creating users, checking logs, deploying |
| `element-branding` | Editing custom.css, welcome page, auth styles, element-config.json |
| `synapse-config` | Working with homeserver.yaml, email templates, Resend SMTP, registration tokens |

## Commands

| Command | What it does |
|---------|-------------|
| `/the-local:deploy` | Deploy changed files to the server (scp or git pull + force-recreate) |
| `/the-local:logs [service]` | Tail Docker Compose logs (defaults to synapse) |
| `/the-local:create-user [username]` | Create a new Matrix account on thelocal.chat |

## Infrastructure

- **Server**: `root@143.110.221.2` (DigitalOcean, Ubuntu 24.04)
- **App directory**: `/opt/thelocal`
- **Domain**: `thelocal.chat` / `matrix.thelocal.chat`
- **Stack**: Synapse + PostgreSQL 16 + Element Web + LiveKit + Caddy
