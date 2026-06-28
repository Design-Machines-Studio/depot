#!/usr/bin/env bash
#
# airlift-hook-flush.sh: Reactive StopFailure backstop for airlift.
#
# WHY THIS EXISTS:
#   The Tier-3 statusLine monitor is an EARLY warning -- it fires before the cap
#   lands, while budget remains. But the statusLine only renders on a successful
#   turn; if a request fails hard (rate_limit, overloaded, billing_error) the
#   early warning may never have run. This hook is the REACTIVE backstop: Claude
#   Code's StopFailure event fires when a turn ends in such a failure, and this
#   handler fires the deterministic engine capture so a fresh handoff bundle
#   exists even when the proactive path was skipped.
#
# WHAT THIS FIXES:
#   Without a reactive capture, a hard failure leaves the user with whatever the
#   last checkpoint was -- possibly stale, possibly nonexistent. This handler
#   guarantees a checkpoint at the moment of failure. It is deliberately tiny and
#   fast: it must never block the harness and must tolerate a missing engine.
#
# DEPENDENCIES:
#   - bash 3.2+ (macOS default 3.2.57). NO bash-4 features.
#   - airlift-engine.sh (resolved from the plugin cache; absence -> no-op).
#   - cat, ls, head (POSIX/BSD-portable usage).
#   - NO network calls.
#
# USAGE:
#   Wired automatically by airlift-settings.sh into settings.json hooks under
#   StopFailure. Reads the hook stdin JSON (drained, not required), fires the
#   engine reactive capture, and exits 0.
#
# SECURITY NOTES:
#   - PATH is reset to a fixed value to prevent caller-controlled hijack of
#     bash/ls/head/cat and the resolved engine.
#   - The hook stdin payload is drained (we do not need its contents to fire the
#     deterministic capture) so the harness never blocks on a full pipe.
#   - ALWAYS exits 0. A non-zero hook exit could surface noise to the user at the
#     worst possible moment (right after a failure); the capture is best-effort.

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

# Resolve airlift-engine.sh via the dual-cache pattern: prefer ~/.claude, then
# ~/.codex; newest version dir wins. Echo path on success, empty on failure.
airlift_flush_resolve_engine() {
  local _base _cand _verdir
  for _base in "$HOME/.claude" "$HOME/.codex"; do
    for _verdir in $(ls -t -d "$_base"/plugins/cache/depot/airlift/*/ 2>/dev/null); do
      [ -d "$_verdir" ] || continue
      _cand="${_verdir}skills/airlift/references/airlift-engine.sh"
      if [ -n "$_cand" ] && [ -x "$_cand" ]; then
        printf '%s\n' "$_cand"
        return 0
      fi
    done
  done
  return 1
}

airlift_flush_main() {
  # Drain stdin so the harness never blocks on a full pipe. We do not need the
  # payload contents -- the deterministic capture reads objective git state.
  cat >/dev/null 2>&1 || true

  local engine
  engine="$(airlift_flush_resolve_engine)"
  if [ -n "$engine" ] && [ -x "$engine" ]; then
    bash "$engine" write --phase reactive --note "StopFailure flush" >/dev/null 2>&1 || true
  fi
  # Missing engine, failed capture, anything -- always exit 0.
  return 0
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  airlift_flush_main "$@"
  exit 0
fi
