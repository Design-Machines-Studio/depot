---
name: create-user
description: Create a new Matrix user account on The Local (thelocal.chat). Prompts for username and password, then runs register_new_matrix_user via docker compose exec.
argument-hint: "[username]"
allowed-tools: Bash
---

Create a new Matrix user account on The Local's Synapse server.

## Process

1. Ask the user for:
   - **Username** (Matrix local part — will become `@username:thelocal.chat`)
   - **Password** (or offer to generate a secure one)
   - **Admin?** (usually no — only for The Local administrators)

2. Run the registration command on the server:

```bash
# Standard user
ssh root@143.110.221.2 'cd /opt/thelocal && docker compose exec synapse \
  register_new_matrix_user \
  -u USERNAME -p "PASSWORD" --no-admin \
  -c /data/homeserver.yaml http://localhost:8008'

# Admin user
ssh root@143.110.221.2 'cd /opt/thelocal && docker compose exec synapse \
  register_new_matrix_user \
  -u USERNAME -p "PASSWORD" --admin \
  -c /data/homeserver.yaml http://localhost:8008'
```

3. Confirm success and provide the user with:
   - Full Matrix ID: `@username:thelocal.chat`
   - Login URL: `https://thelocal.chat`
   - Note: Element desktop app requires `matrix.thelocal.chat` as the homeserver URL (not the root domain)

## Username Conventions

- Lowercase, no spaces
- Keep it short and professional
- The Matrix ID `@username:thelocal.chat` is permanent and cannot be changed

## Security Note

Passwords passed via command line are visible in shell history. After creation, prompt the user to change their password on first login, or use the Synapse Admin API for password resets.
