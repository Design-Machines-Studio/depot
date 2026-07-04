# Eval-Sweep Ledger Templates

Copy these verbatim in **Phase 0**, before any analysis. Writing them first is what makes the run survivable: a session that dies at 20% still ships 20% of a real report.

Fill `<...>` placeholders once at scaffold time. Stamp the HEAD SHA from `git rev-parse HEAD`.

---

## Deliverable skeleton (`NN-<area>.md`)

One per evaluation area (routing, accessibility, performance, auth-surface, ...).

```markdown
# <Area> Evaluation

- HEAD: <sha>
- Base URL: <base-url>
- Generated: <timestamp -- leave as PENDING until the phase completes>
- Status: SCAFFOLDED   <!-- SCAFFOLDED -> IN-PROGRESS -> COMPLETE | PARTIAL -->

## Summary

_(rewritten from summary.json / a11y-summary.json after the phase runs)_

## Findings

_(pulled from findings-ledger.md, filtered to this area)_

## NOT-COVERED

_(routes/roles/checks this area did not reach, with the reason)_
```

Set `Status: PARTIAL` and fill `NOT-COVERED` if the phase is cut under budget pressure. Never leave `Status: COMPLETE` on a phase that was truncated.

---

## `findings-ledger.md` (append-only)

```markdown
# Findings Ledger (append-only)

- HEAD: <sha>
- Started: <timestamp>

<!-- Append one block per confirmed finding, in order. Never rewrite earlier
     blocks; a resumed session appends after the last block. -->

### [P1|P2|P3] <one-line title>
- where: <route> @ <role>/<vp>  (or <path>:<anchor>)
- evidence: <metric value, screenshot path, or header line>
- fix: <concrete change>
```

The append-only rule matters: it means a crash can never corrupt earlier findings, and a resumed session only has to append.

---

## `commands-log.md` (append-only)

```markdown
# Commands Log (append-only)

- HEAD: <sha>

<!-- Append each command/script as it runs, with a one-line result, so a
     resumed session knows exactly what already executed and does not repeat
     an expensive sweep. -->

- `<timestamp>` `node references/sweep.mjs --base-url ... --out ./out/sweep` -> <N cells, M problems>
- `<timestamp>` `./references/curl-probes.sh http://localhost:8080` -> <login 303, 404 ok>
```

---

## Sample `routes.json`

Consumed by both `sweep.mjs` and `a11y-probe.mjs`. Keep credentials OUT of this file when it is committed -- prefer `EVAL_<ROLE>_EMAIL` / `EVAL_<ROLE>_PASSWORD` env vars, or a gitignored copy.

```json
{
  "login": {
    "url": "/login",
    "usernameField": "email",
    "passwordField": "password",
    "submitSelector": "button[type=\"submit\"]",
    "roles": {
      "member": { "email": "$EVAL_MEMBER_EMAIL", "password": "$EVAL_MEMBER_PASSWORD" },
      "admin":  { "email": "$EVAL_ADMIN_EMAIL",  "password": "$EVAL_ADMIN_PASSWORD" }
    }
  },
  "routes": [
    "/", "/dashboard", "/members", "/account", "/account/interface",
    "/admin", "/admin/audit", "/super/settings", "/super/events",
    "/notifications", "/search"
  ]
}
```
