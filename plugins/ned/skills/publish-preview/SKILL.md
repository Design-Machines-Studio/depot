---
name: publish-preview
description: Preview hostname publication for exact dmNNN.asmbly.app or <slug>.designmachines.xyz addresses. Use when asked to expose, plan, inspect, verify, inventory, or unpublish a protected preview through the existing tunnel.
---

# Publish a NED preview

Operate this as a careful playbook, not a deployment platform. The agent performs ordinary project work as
`ned`, prepares the smallest exact system/provider changes, shows one complete plan, waits for approval, and
then applies and verifies each layer. Reuse `ned:operate-ned` for the account boundary and `ned:ai-memory`
for current canonical NED context.

This publishes development and small client-review sites only. It never publishes a production service.

## Local records

- Inventory: `/home/ned/.config/design-machines/publish-preview/inventory.json`
- Receipts and reviewed plans: `/home/ned/.local/state/design-machines/publish-preview/`
- NED-host mutation lock: `/home/ned/.local/state/design-machines/publish-preview/mutation.lock`
- Schema and fictional example: `references/inventory.schema.json` and
  `references/inventory.example.json`

These host-local files are not part of Depot. Never copy client identities, API tokens, service tokens,
notification topics, or other credential values into inventory, plans, receipts, prompts, logs, or AI Memory.

## Conversational operations

Interpret the user's request as one of these operations:

- **list/status** — read inventory and compare it with live state; never mutate.
- **plan** — discover runtime and provider state and print the complete non-secret plan; never mutate.
- **publish** — repeat discovery, reject drift, obtain explicit approval of the current plan, then apply.
- **verify** — recheck every applicable layer without mutation.
- **unpublish** — plan the exact owned removals, obtain approval, remove exposure first, and keep the runtime.

If the project is not inventoried, draft an entry for the operator to review before planning publication.
Do not silently infer client identities or anonymous access.

## Required sequence

1. Run the `ned:operate-ned` development preflight. Require `ned9000`, user `ned`, a checkout below
   `/home/ned`, the rootless Docker daemon rooted at `/home/ned/.local/share/docker`, and no passwordless
   sudo. Stop on a Docker-context or authority mismatch.
2. Open the exact AI Memory entities `NED 9000` and `NED 9000 Dev Environment`. Prefer newer
   `CANONICAL` observations, especially publication and monitoring guidance. Retrieve no credentials.
3. Load and validate the whole inventory. Reject duplicate hostnames, factory codes, and backend endpoints
   shared by Assembly or generic Compose projects,
   receipt IDs, or ownership markers; invalid domains/codes/slugs; paths outside approved roots; traversal;
   unsafe symlinks; shell metacharacters; and ownership conflicts.
   Require `DM-NNN` to map to exactly `dmNNN.asmbly.app`, and require a website `siteSlug` to equal the
   first label of its `.designmachines.xyz` hostname. The sole endpoint-uniqueness exception is that
   multiple DDEV sites may share the canonical
   `127.0.0.1:8080` entrypoint when exact hostname routing and direct origin probes disambiguate them.
4. Discover the project as `ned`: resolve Compose or DDEV configuration, identify the stable service,
   confirm a meaningful healthcheck, persistent state, restart policy, running/healthy status, and direct
   origin response. Published ports should bind to `127.0.0.1`. Treat all-interface bindings as a blocker
   for a new publication and a migration item for existing Assembly previews.
5. Read current Caddy, tunnel/DNS, Access, and Kuma state without printing secret-bearing configuration.
   A same-name resource without this workflow's marker is a conflict, not something to adopt.
6. Write a non-secret plan using `references/plan-and-receipt.md`. Include before-state fingerprints,
   exact proposed changes, authority (`ned` or bounded `trav` through `ssh ned9000-plain`), verification,
   rollback, conflicts, and gaps.
7. Show the plan and ask for explicit approval. Approval applies only to that plan and its before-state
   fingerprints. Re-read relevant state immediately before mutation; changed state invalidates approval.
8. As `ned` on NED, acquire one exclusive `flock` on
   `/home/ned/.local/state/design-machines/publish-preview/mutation.lock` and hold it from final
   before-state discovery through mutation, rollback if needed, and terminal receipt persistence. Create
   the receipt before the first mutation. Apply one layer at a time and atomically persist that step's
   non-secret ID, ownership, and outcome before advancing. Stop on malformed, ambiguous, or conflicting
   state. Never report success for a manual or incomplete step.
9. Run the verification ladder. Authenticated Access evidence must come from a real browser session;
   curl, a login redirect, or caller-supplied assertions do not count.
10. Save a receipt. On partial failure, state exactly what changed and the safest next action.

## Routing rules

- Assembly hostnames are exactly `dmNNN.asmbly.app`; codes are uppercase `DM-NNN` in inventory.
- Website hostnames are exactly `<slug>.designmachines.xyz` using a lowercase DNS slug.
- DDEV reaches Caddy through `127.0.0.1:8080` unless current canonical architecture says otherwise.
- Preserve current Assembly mappings, including 8090/DM-006, 8091/DM-021, and 8092/DM-022.
- Unmatched Assembly codes return an honest 404, never another installation.
- Prefer a generated workflow-owned Caddy fragment included before existing fallback handlers.
- A bounded `trav` operation may install/restore that fragment, validate the full Caddyfile, and reload.
  Never run a general agent as `trav`, edit unrelated routes, or apply live Caddy changes while developing
  this skill.

## Cloudflare and monitoring rules

- Use the existing Cloudflare Tunnel and one exact proxied CNAME to its tunnel target.
- Never proxy an A record pointing at NED's Tailscale/CGNAT address and never alter DNS-only wildcards.
- Create an exact self-hosted Access application and an app-scoped Allow policy for operator-approved
  identities. Access denies unmatched identities by default; do not add a blanket “Block Everyone”.
- Anonymous publication requires its own explicit approval and must never be inferred from missing data.
- Use protected file-backed credentials or the existing approved mechanism. Never put sensitive values in
  argv, environment, output, receipts, fixtures, or memory.
- Identity files are owned by `ned`, mode `0600`, beneath a `0700` operator directory. Record only their
  digest and entry count; never their contents.
- Enroll persistent previews in Kuma. Prefer application health/content. Attach the existing
  `NED monitoring alerts` provider by identity without reading or printing its ntfy topic.
- Do not edit Kuma SQLite. If a tested integration is unavailable, stop with a bounded manual Kuma UI step.
- For Access-protected sites, monitor origin health or use a deliberately scoped service token stored only
  in Kuma, plus a separate authenticated browser check. Never weaken Access to make monitoring green.
- Do not alter Beszel, Healthchecks.io, the existing ntfy topic, tunnels, wildcard DNS, certificates,
  notification providers, or unrelated monitors.

## Apply and rollback order

For a protected preview: healthy runtime → validated Caddy route → Access app/policy → exact tunnel/DNS
publication → Kuma → browser and monitoring verification. If current provider tooling cannot safely
automate a step, present a bounded manual action instead of improvising.

Rollback removes public exposure before local routing: exact DNS/tunnel hostname → verify exposure is gone
→ exact Access resources → exact owned Kuma monitor → exact owned Caddy fragment. Restore an updated owned
resource from the receipt; delete only a resource created by this publication. Leave the project runtime
running unless the user separately asks to stop it.

## Verification ladder

Report each item as passed, failed, blocked, manual, or not applicable:

1. NED identity and authority boundary.
2. Runtime running and Docker/application health.
3. Direct loopback origin returns the expected signal.
4. Caddy maps the exact hostname to the intended backend.
5. Public HTTPS reaches the exact hostname through the existing tunnel.
6. An allowed identity reaches the real application in a browser.
7. A clean unauthorized browser context is denied.
8. Kuma checks the intended application signal and existing alert provider.
9. Restart/reboot persistence is configured.
10. Unrelated routes, DNS, Access resources, and monitors are unchanged.
11. Output, receipt, diff, argv, and environment contain no credentials.

The publication is complete only when every required item passes. Browser and reboot checks that were not
actually performed remain explicit acceptance gaps.

## Development gate

Building or reviewing this skill authorizes read-only inspection only. Do not modify real Caddy, Cloudflare,
Access, DNS, Kuma, ntfy, Healthchecks, or project runtime state without a separate, explicit dogfood request
that names the preview and permitted layers.
