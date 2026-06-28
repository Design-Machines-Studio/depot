---
name: airlift-install
description: Wire, unwire, or check the airlift Tier-3 early-warning monitor in settings.json. Installs a usage-cap statusLine that CHAINS (never clobbers) the existing one, plus a reactive StopFailure backstop. ccusage is optional.
argument-hint: "[wire | unwire | status]"
allowed-tools: Bash, Read
---

# Airlift Install

Wire the airlift Tier-3 early-warning monitor into the harness `settings.json`,
or unwire it, or report its status. The subcommand is `$ARGUMENTS` (default
`status` when omitted).

## What this does

- **wire** -- Installs an airlift statusLine that reads the REAL
  `rate_limits.five_hour.used_percentage` signal and, on crossing a threshold
  (default 90%), fires a deterministic checkpoint and shows a loud
  `run /airlift-in .airlift` banner. It also adds a `StopFailure` hook that fires
  a reactive checkpoint when a turn ends in `rate_limit`, `overloaded`, or
  `billing_error`.
  - **The existing statusLine is PRESERVED.** Wiring backs up your current
    statusLine to `airlift-settings-backup.json` next to your `settings.json`
    (only on the first wire, never overwriting a prior backup) and the airlift
    statusLine CHAINS it -- the prior command is embedded into the global
    statusLine command string and run with the same stdin, shown alongside the
    airlift segment. Nothing is clobbered, and no repo-local file is ever
    executed by the statusLine.
  - **Idempotent.** A second `wire` makes no further changes: the statusLine is
    not double-wrapped and the StopFailure hook is not duplicated.
- **unwire** -- Restores the original statusLine byte-exact from the
  `airlift-settings-backup.json` sidecar (next to `settings.json`) and removes
  every airlift hook entry. A second `unwire` is a no-op.
- **status** -- Reports wired/unwired, whether `ccusage` is detected, and a note
  on when the real `rate_limits` signal is available.

## ccusage is optional

`ccusage` is an OPTIONAL local CLI used only as a FALLBACK estimate when the real
`rate_limits` signal is unavailable. Every path works with ccusage absent -- the
monitor simply relies on the real signal (or stays silent when neither is
present). The real `rate_limits.five_hour.used_percentage` is the PRIMARY signal;
ccusage is a cost-based estimate of the 5-hour block only, not the weekly cap.

## How to run

Resolve `airlift-settings.sh` from the installed plugin cache (newest version,
preferring `~/.claude` then `~/.codex`) and run it with the requested
subcommand:

```bash
SUB="${ARGUMENTS:-status}"
SETTINGS_SH=""
for BASE in "$HOME/.claude" "$HOME/.codex"; do
  for VERDIR in $(ls -t -d "$BASE"/plugins/cache/depot/airlift/*/ 2>/dev/null); do
    CAND="${VERDIR}skills/airlift/references/airlift-settings.sh"
    if [ -f "$CAND" ]; then SETTINGS_SH="$CAND"; break; fi
  done
  [ -n "$SETTINGS_SH" ] && break
done
if [ -z "$SETTINGS_SH" ]; then
  echo "airlift-settings.sh not found in the plugin cache." >&2
  exit 1
fi
bash "$SETTINGS_SH" "$SUB"
```

After `wire`, restart the harness (or trigger a statusLine re-render) so the new
statusLine command takes effect. After `unwire`, the original statusLine is
restored from the sidecar backup.
