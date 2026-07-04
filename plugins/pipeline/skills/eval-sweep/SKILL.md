---
name: eval-sweep
description: Ledger-first, scripted system-wide evaluation harness for a running web app. Use when evaluating, auditing, or sweeping an entire app across every route, role, and breakpoint -- system-wide evaluation, whole-app audit, "screenshot every page", route x role x breakpoint matrix, accessibility probe, or a survivable review that ships partial value if the session dies. Scaffolds append-only deliverables and ledgers FIRST, then runs one scripted browser sweep (sweep.mjs) and one a11y probe (a11y-probe.mjs) instead of hundreds of live MCP browser calls. Invoke directly or as the evaluation phase of a large review.
argument-hint: "[base-url] [optional: routes file, roles, breakpoints]"
---

# Eval Sweep -- Ledger-First Evaluation Harness

A system-wide evaluation of a running web app that **survives its own death**. The pattern comes from the 2026-07-04 assembly-baseplate session-3-6 evaluation, where 4 uncapped review subagents died on a monthly spend limit and returned zero findings, while a ledger-first + scripted-sweep run survived the same failure with no lost work.

Two ideas do the work:

1. **Ledger-first.** Every deliverable skeleton, the append-only `findings-ledger.md`, and `commands-log.md` are written to disk BEFORE any analysis. A session that dies at 20% still ships 20% of a real report, not an empty file.
2. **Scripted sweep, not live clicking.** One `node sweep.mjs` call walks the whole route x role x breakpoint matrix and emits metrics JSON + a PNG per cell. One Bash call replaces 100+ interactive MCP browser calls -- the exact thing that runs a session out of budget.

## When To Use

- "Evaluate / audit / sweep the whole app" -- every page, every role, every breakpoint.
- A review large enough that live MCP browser driving would blow the budget.
- Any evaluation that MUST leave durable partial value if it is interrupted.

For a single PR diff, use `dm-review`. For one page, drive it directly. This skill is for breadth.

## Tool-Call Budget & Partial-Return Contract

This skill is itself budget-disciplined. The whole point is to spend one scripted Bash call where a naive run spends hundreds of MCP calls.

- **Hard cap: 40 tool calls** for the orchestrating agent (the sweep scripts do the fan-out internally and do not count against per-cell interaction).
- **Flush after every phase.** Never hold results in context waiting to write them at the end -- append to the ledger and rewrite the deliverable after each phase completes.
- **At 80% of budget, stop and write up what you have,** with a `NOT-COVERED:` list of routes/roles/checks not reached.

## Phase 0: Scaffolding (BEFORE any analysis)

Write these to the evaluation output directory FIRST. This is non-negotiable -- it is what makes the run survivable.

1. **Stamp HEAD.** `git rev-parse HEAD` -> put the SHA in every deliverable header so a resumed or partial run is anchored to an exact tree.
2. **Deliverable skeletons.** One file per evaluation area (e.g. `01-routing.md`, `02-accessibility.md`, ...), each starting with the header from `references/ledger-templates.md` (HEAD SHA, timestamp placeholder, status: SCAFFOLDED).
3. **`findings-ledger.md`** -- append-only. Every finding is appended the moment it is confirmed, in the fixed ledger block format. Never rewritten, only appended.
4. **`commands-log.md`** -- append-only. Every command/script invocation is logged here as it runs, so a resumed session knows exactly what was already executed.

Templates for all four live in `references/ledger-templates.md`. Copy them verbatim.

## Phase 1: Curl-First Probes (cheapest signal first)

Before spending a browser, probe with curl -- it is nearly free and catches whole classes of issues. See `references/curl-probes.sh`.

- Compression + caching headers (`Content-Encoding`, `Cache-Control`, `ETag`).
- Error-page correctness (404/500 return the right status, not a 200 shell).
- Authed login flow. **Note:** gorilla/csrf (used by Assembly) requires an `Origin` header on the login POST or it rejects with 403 -- `curl-probes.sh` sets it. Capture the session cookie for the browser sweep to reuse.

Append every probe to `commands-log.md`; append findings to `findings-ledger.md`.

## Phase 2: Scripted Browser Sweep

Run the matrix in ONE call. See `references/sweep.mjs`.

```bash
node references/sweep.mjs \
  --base-url http://localhost:8080 \
  --routes references/routes.json \
  --roles anon,member,admin \
  --vp 375,768,1440 \
  --engine chromium \
  --out ./out/sweep
```

Per (route x role x breakpoint) cell the script emits:

- `metrics/<route>__<role>__<vp>.json` -- `status`, `overflowX` (horizontal overflow bool + amount), `consoleErrors[]`, `failedRequests[]`, `domContentLoaded` (ms).
- `png/<route>__<role>__<vp>.png` -- full-page screenshot.
- `summary.json` -- the whole matrix rolled up, plus a `problems[]` list (any non-2xx status, any overflowX, any console error, any failed request).

Flags:

- `--engine firefox` -- re-run a cell set on Firefox to catch engine-specific rendering.
- `--vp 768` (single value) -- narrow to one breakpoint when chasing a specific regression.

Read `summary.json` (one Read), append its `problems[]` to the ledger, and rewrite `01-routing.md` from it. Do NOT open every PNG -- open only the PNGs `problems[]` points at.

## Phase 3: Accessibility Probe

Run `references/a11y-probe.mjs` against the same matrix (or a page subset). It checks what static linters cannot: keyboard tab order, dialog open/close focus lifecycle (trap + restore), live-region announcements, `aria-current` on the active nav item, and focus-visibility (does the focused element have a visible indicator). Emits `a11y/<route>__<role>.json` and an `a11y-summary.json`. Append violations to the ledger; rewrite `02-accessibility.md`.

## Checkpoint Discipline & Degradation Ladder

Flush the ledger and rewrite affected deliverables after EVERY phase. If budget pressure forces cuts, drop in this order (documented so the report says what was skipped):

1. Drop the Firefox re-run (Chromium is representative).
2. Drop the largest breakpoint set to a single representative width (`--vp 1440`).
3. Drop the a11y probe to the highest-traffic routes only.
4. **Never dropped:** Phase 0 scaffolding, the curl probes, and at least one full Chromium sweep pass at one breakpoint. If even that cannot finish, the ledger + skeletons still ship whatever completed.

Every drop is logged as a `NOT-COVERED:` entry. Silent truncation that reads as full coverage is the failure this skill exists to prevent.

## Output

A directory of deliverables anchored to one HEAD SHA, an append-only findings ledger in the fixed block format, a commands log, and a `summary.json` + PNG evidence set. Findings use:

```
### [P1|P2|P3] <one-line title>
- where: <route> @ <role>/<vp>  (or <path>:<anchor>)
- evidence: <metric or screenshot reference>
- fix: <concrete change>
```
