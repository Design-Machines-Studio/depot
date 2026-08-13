# NED preview operator runbook

This is the compact operational companion to `ned:publish-preview`. It assumes one agent is working as
`ned` and escalates only exact system operations through `ssh ned9000-plain`.

## Status or plan

1. Run `ned:operate-ned` preflight and open the canonical NED memory entities.
2. Read the host-local inventory; validate the schema plus cross-entry uniqueness and realpath rules.
3. Resolve Compose with `docker compose config --quiet` or DDEV with `ddev describe -j` from the pinned
   checkout. Inspect labels, health, mounts, restart policy, and port bindings through rootless Docker.
4. Probe the origin directly on loopback using the inventoried path/status/keyword.
5. Inspect Caddy structurally and the exact provider/Kuma resources read-only. Do not export full service
   files or secret-bearing provider configuration.
6. Produce the reviewed plan described in `plan-and-receipt.md`. Stop on a conflict or incomplete runtime.

## Publish

After explicit approval of the current plan:

1. Acquire the one host-wide publish-preview mutation lock. Hold it through final state discovery, every
   Caddy/provider/Kuma mutation, rollback, and the terminal receipt write. Re-read inventory and every
   relevant before-state fingerprint under that lock; reject a stale plan.
2. Create the durable receipt in `planned` state before mutation. Atomically replace it after every
   attempted/completed step and resource ID before moving to the next layer. After interruption, rediscover
   live state and resume only from this receipt; never reconstruct ownership from a hostname alone.
3. As `ned`, ensure the already-running project remains healthy. Do not restart it because an external
   probe failed.
4. Prepare the deterministic exact-host Caddy fragment. Through one bounded `trav` operation, atomically
   install only that owned fragment, validate the full Caddyfile, reload, and restore the prior fragment if
   validation, reload, or route verification fails.
5. Create or reconcile the exact self-hosted Access application and app-scoped Allow policy before public
   exposure. Same-domain resources without matching ownership are conflicts. Approved identity values are
   read from a protected local file and never echoed.
6. Reconcile the exact hostname with the existing Tunnel and an exact proxied CNAME to its tunnel target.
   Preserve the terminal 404 and every unrelated ingress/DNS record. If safe conditional reconciliation is
   unavailable, provide the exact Cloudflare dashboard action and record `manual-required`.
7. Enroll Kuma through a tested API seam or provide a bounded UI step. Do not edit SQLite. Reference the
   existing `NED monitoring alerts` provider without opening its configuration.
8. Verify the complete ladder. Use Playwright with a real authorized browser context and a separate clean
   unauthorized context for Access evidence. A redirect/login page is not the application.
9. Mark the durable receipt `verified` only when the full required ladder passed. Otherwise use `partial`
   or `manual-required` and list every unresolved acceptance item.

## Unpublish

Plan and approve unpublication separately. Confirm every target using both its provider ID and workflow
ownership marker. Remove exact public exposure first, verify it is gone, then remove the exact Access app
and policy, owned Kuma monitor, and owned Caddy fragment. Restore updated owned resources from receipt
before-state rather than deleting them. Never remove shared wildcard DNS, the tunnel, certificates,
notification providers, or unrelated routes. Leave the project running.

## Troubleshooting by layer

Follow this order and stop at the first failing layer:

1. Rootless container running, Docker health, and logs.
2. Direct loopback origin signal.
3. Exact local Caddy host route and backend.
4. Tunnel ingress and exact proxied DNS.
5. Access authentication, authorization, and real-app browser response.
6. Kuma target, signal, heartbeat, and notification-provider attachment.

Never restart the project solely because public HTTPS fails. Never weaken Access to make a monitor green.

## Acceptance gaps

Skill development performs no live changes. A future dogfood request must name the preview and permitted
layers. Until that run occurs, the receipt must say that live Caddy/Cloudflare/Kuma mutation, authorized and
unauthorized browser checks, and reboot persistence are unperformed.
