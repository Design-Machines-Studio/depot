---
name: synapse-config
description: Synapse Matrix homeserver configuration, email setup via Resend SMTP, Jinja2 email/page template system, registration token management, and homeserver.yaml template pattern for The Local. Use when editing homeserver.yaml, adding or modifying email templates, configuring SMTP, managing registration tokens, working with Synapse's Jinja2 template system, or troubleshooting Synapse behaviour. Trigger for any mention of: homeserver.yaml, registration_requires_token, Resend, SMTP port 2587, email templates, Jinja2, _base.html, notif_mail, password_reset, synapse templates directory, or any Synapse server configuration concern.
---

# The Local — Synapse Configuration

Synapse is the Matrix homeserver at `matrix.thelocal.chat`. This skill covers the config template pattern, email system, and Jinja2 template customization.

## Config Template Pattern

Secrets are never committed. Instead:

- `homeserver.yaml` — template file checked into git, contains `%%PLACEHOLDER%%` tokens
- `homeserver.yaml.active` — generated file with real secrets (gitignored, used by Docker)
- `.env` — contains `POSTGRES_PASSWORD`, `REGISTRATION_SECRET`, `MACAROON_SECRET`, `FORM_SECRET`, `RESEND_API_KEY`

**Always edit the template** (`homeserver.yaml`), not `.active`. After editing, regenerate and restart:

```bash
ssh root@143.110.221.2 'cd /opt/thelocal && source .env && \
  sed -e "s|%%POSTGRES_PASSWORD%%|${POSTGRES_PASSWORD}|g" \
      -e "s|%%REGISTRATION_SECRET%%|${REGISTRATION_SECRET}|g" \
      -e "s|%%MACAROON_SECRET%%|${MACAROON_SECRET}|g" \
      -e "s|%%FORM_SECRET%%|${FORM_SECRET}|g" \
      -e "s|%%RESEND_API_KEY%%|${RESEND_API_KEY}|g" \
  homeserver.yaml > homeserver.yaml.active && \
  docker compose restart synapse'
```

Same pattern applies to `livekit/livekit.yaml` → `livekit/livekit.yaml.active`.

## Email via Resend SMTP

DigitalOcean blocks standard SMTP ports (25, 465, 587) on all droplets. Resend provides port 2587 (STARTTLS).

**Config in `homeserver.yaml`**:
```yaml
email:
  smtp_host: smtp.resend.com
  smtp_port: 2587
  smtp_user: resend
  smtp_pass: "%%RESEND_API_KEY%%"
  require_transport_security: true
  notif_from: "The Local <noreply@thelocal.chat>"
  app_name: "The Local"
  template_dir: /data/templates
```

**DNS setup** (in Namecheap for `thelocal.chat`): DKIM + SPF records from Resend dashboard.
**Free tier**: 3,000 emails/month — more than sufficient for The Local's scale.

## Jinja2 Template System

Custom templates override Synapse defaults. Location on server: `/data/templates` (bind-mounted from `/opt/thelocal/templates/`).

Synapse falls back to its bundled defaults for any file not present in `template_dir`.

### Template Inventory

| File | When Sent/Shown | Key Jinja2 Variables |
|------|----------------|----------------------|
| `_base.html` | Extended by all HTML templates | — |
| `style.css` | Included by `_base.html` | — |
| `add_threepid.html` | Email: verify new email address | `{{ link }}` |
| `add_threepid.txt` | Same, plain text version | `{{ link }}` |
| `password_reset.html` | Email: password reset link | `{{ link }}` |
| `password_reset.txt` | Same, plain text version | `{{ link }}` |
| `registration.html` | Email: verify account email | `{{ link }}` |
| `registration.txt` | Same, plain text version | `{{ link }}` |
| `add_threepid_success.html` | Web page: email added | — |
| `add_threepid_failure.html` | Web page: email add failed | `{{ failure_reason }}` |
| `password_reset_success.html` | Web page: password reset done | — |
| `password_reset_failure.html` | Web page: reset link expired | `{{ failure_reason }}` |
| `registration_failure.html` | Web page: registration failed | `{{ failure_reason }}` |
| `registration_token.html` | Web page: token entry form | `{{ myurl }}`, `{{ error }}`, `{{ session }}` |
| `invalid_token.html` | Web page: invalid token | — |
| `already_in_use.html` | Web page: email already registered | — |
| `already_in_use.txt` | Email: collision notice | — |
| `notif_mail.html` | Email: room notification digest | `user_display_name`, `rooms`, `unsubscribe_link` |
| `notif_mail.txt` | Same, plain text version | same |
| `room.html` | **Required** sub-template included by `notif_mail.html` | room context variables (name, avatar, notifications) |

### HTML Email Template Pattern

All HTML email templates extend `_base.html`:

```html
{% extends "_base.html" %}
{% block title %}Reset your password — The Local{% endblock %}
{% block body %}
<p>You requested a password reset for your account on <strong>The Local</strong>.</p>
<p><a class="btn" href="{{ link }}">Reset password</a></p>
<p>If you didn't request this, ignore this email — your account is safe.</p>
{% endblock %}
```

**Never modify `_base.html` or `style.css`** — they provide the shared layout and brand styles.

### Plain Text Template Pattern

```
Reset your password — The Local

You requested a password reset for your The Local account.

{{ link }}

If you didn't request this, ignore this message.

— The Local (thelocal.chat)
```

### notif_mail.html Structure

Uses sub-template includes — preserve this structure:

```html
{% extends "_base.html" %}
{% block body %}
<p>Hi {{ user_display_name }},</p>
{% for room in rooms %}
  {%- include 'room.html' -%}
{% endfor %}
<p><a href="{{ unsubscribe_link }}">Unsubscribe</a></p>
{% endblock %}
```

Requires a `room.html` sub-template that receives room context variables.

## Registration Tokens

Registration is token-gated (`registration_requires_token: true` in `homeserver.yaml`).

```bash
# Create a registration token via Synapse Admin API
curl -X POST "https://matrix.thelocal.chat/_synapse/admin/v1/registration_tokens/new" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"uses_allowed": 5}'

# List tokens
curl "https://matrix.thelocal.chat/_synapse/admin/v1/registration_tokens" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

Get `ADMIN_TOKEN` by logging in as an admin user and copying the access token from Element → Settings → Help & About → Access Token.

## Key Security Settings

```yaml
# In homeserver.yaml (template)
federation_domain_whitelist: []          # empty = federation disabled (Circle 1)
registration_requires_token: true        # token-gated signup
enable_registration: true               # required for token registration to work
allow_guest_access: false
```

## Inspect Bundled Defaults

To see Synapse's bundled default template (e.g., to understand available variables):

```bash
docker compose exec synapse cat /usr/local/lib/python3.13/site-packages/synapse/res/templates/notif_mail.html
docker compose exec synapse ls /usr/local/lib/python3.13/site-packages/synapse/res/templates/
```
