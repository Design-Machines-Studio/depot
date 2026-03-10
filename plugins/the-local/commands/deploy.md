---
name: deploy
description: Deploy changed files to The Local server at 143.110.221.2. Handles scp for asset/template files (no container restart needed) and git pull + force-recreate for structural changes.
argument-hint: "[service|file]"
allowed-tools: Bash, Read, Glob
---

Deploy changed files from the local repo to The Local server at `root@143.110.221.2`.

## What to Deploy

Determine from context what has changed. The user may specify a file, service, or say "deploy everything".

## Deployment Methods

**Use scp** for files served via Docker bind mounts (preserves inode — container sees change immediately, no restart needed):
- `assets/custom.css` → `/opt/thelocal/assets/custom.css`
- `assets/index.html` → `/opt/thelocal/assets/index.html`
- `welcome/index.html` → `/opt/thelocal/welcome/index.html`
- `element-config.json` → `/opt/thelocal/element-config.json`
- `templates/*.html`, `templates/*.txt` → `/opt/thelocal/templates/`

**Use git pull + force-recreate** when `docker-compose.yml`, `Caddyfile`, `homeserver.yaml`, or multiple files have changed:
```bash
ssh root@143.110.221.2 'cd /opt/thelocal && git pull && docker compose up -d --force-recreate element'
```

After Synapse config changes (`homeserver.yaml`), regenerate the `.active` file and restart:
```bash
ssh root@143.110.221.2 'cd /opt/thelocal && source .env && \
  sed -e "s|%%POSTGRES_PASSWORD%%|${POSTGRES_PASSWORD}|g" \
      -e "s|%%REGISTRATION_SECRET%%|${REGISTRATION_SECRET}|g" \
      -e "s|%%MACAROON_SECRET%%|${MACAROON_SECRET}|g" \
      -e "s|%%FORM_SECRET%%|${FORM_SECRET}|g" \
      -e "s|%%RESEND_API_KEY%%|${RESEND_API_KEY}|g" \
  homeserver.yaml > homeserver.yaml.active && docker compose restart synapse'
```

## Process

1. Identify which files changed (use `git status` or ask the user)
2. Choose the right method (scp vs git pull) based on the file type
3. Run the appropriate commands
4. Confirm success (no errors in output)
5. If deploying CSS changes: remind the user to hard-reload their browser (`Cmd+Shift+R` or `Ctrl+Shift+R`)

## Examples

```bash
# Deploy only custom.css
scp assets/custom.css root@143.110.221.2:/opt/thelocal/assets/custom.css

# Deploy all templates
scp templates/*.html templates/*.txt root@143.110.221.2:/opt/thelocal/templates/

# Deploy element config
scp element-config.json root@143.110.221.2:/opt/thelocal/element-config.json

# Deploy welcome page
scp welcome/index.html root@143.110.221.2:/opt/thelocal/welcome/index.html
```

After deploying `assets/index.html` (which contains the CSS version number), also restart element to ensure the bind mount inode is correct — or use `--force-recreate` if the file was previously git-pulled.
