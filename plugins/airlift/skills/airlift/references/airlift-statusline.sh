#!/usr/bin/env bash
#
# airlift-statusline.sh: Tier-3 early-warning statusLine monitor for airlift.
#
# WHY THIS EXISTS:
#   airlift's deterministic engine (Tier 1) is the guarantee, but it only fires
#   when something explicitly invokes it. The friendliest moment to fire a
#   checkpoint is BEFORE the cap lands, while the model still has budget to
#   enrich the bundle. Claude Code emits a statusLine payload on STDIN every
#   render; that payload may carry the REAL rate-limit signal
#   (rate_limits.five_hour.used_percentage). This script reads that signal, and
#   when it crosses a threshold, fires the engine's deterministic capture so the
#   handoff bundle is fresh the instant the user wants to bail to another model.
#
# WHAT THIS FIXES:
#   No supported real-time usage API or hook exists (anthropics/claude-code#38380
#   closed as not planned). The statusLine payload is the only in-band place the
#   real five_hour.used_percentage surfaces. This script turns that read-only
#   number into an actionable early warning WITHOUT clobbering the user's
#   existing (caveman) statusLine: it CHAINS the prior command and appends its
#   own segment. ccusage is a strictly OPTIONAL fallback estimate -- every path
#   works with ccusage absent, jq absent, and rate_limits absent.
#
# DEPENDENCIES:
#   - bash 3.2+ (macOS default 3.2.57). NO bash-4 features: no associative
#     arrays, no mapfile/readarray, no ${var^^}, no sed -i.
#   - jq (optional but expected on Claude Code hosts; guarded -- absence degrades
#     gracefully, never errors).
#   - ccusage (OPTIONAL local CLI; FALLBACK estimate only). Absence is normal.
#   - airlift-engine.sh (resolved from the plugin cache; absence -> no-op trip).
#   - python3, awk, cat, rm, mktemp, date, ls (POSIX/BSD-portable usage).
#   - NO network calls. ccusage is a LOCAL tool, not a remote request.
#
# USAGE:
#   Wired automatically by airlift-settings.sh into settings.json statusLine.
#   Manual test:
#     echo '{"rate_limits":{"five_hour":{"used_percentage":92,"resets_at":"..."}}}' \
#       | bash airlift-statusline.sh
#
#   Environment overrides (all optional):
#     AIRLIFT_THRESHOLD       trip threshold percent (default 90)
#     AIRLIFT_PRIOR_STATUSLINE  command string of the statusLine to chain
#     AIRLIFT_DIR             override the .airlift dir (default <repo>/.airlift
#                             or ./.airlift)
#
# SECURITY NOTES:
#   - PATH is reset to a fixed value to prevent a caller-controlled PATH from
#     hijacking jq/python3/ccusage/git/awk/mktemp/rm/date/ls.
#   - The STDIN payload is read ONCE into a 0600 temp file (chmod 600) and reused
#     for every jq/ccusage/chain read so the prior statusLine receives the SAME
#     stdin. A trap on EXIT/INT/TERM sweeps the temp via glob.
#   - The chained prior statusLine command is run through `sh -c` with the saved
#     stdin; it runs with the same fixed PATH this script established. It is the
#     command the USER already trusted in their settings.json (or the value they
#     exported), so no new trust boundary is crossed.
#   - The trip debounce flag (.airlift/.trip) stores the current block's
#     resets_at so a re-render inside the same block does not re-fire; a NEW
#     resets_at re-arms.
#   - This script NEVER errors out and ALWAYS exits 0: a statusLine that exits
#     non-zero would break the user's prompt. Every failure degrades to "emit
#     the chained prior statusLine (or nothing) and exit 0".

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

# ---------------------------------------------------------------------------
# Temp cleanup. Mirror the engine/gemini idiom: mint under TMPDIR with a fixed
# prefix and sweep via glob on exit (command-substitution subshells make a
# per-process registry unreliable).
# ---------------------------------------------------------------------------
airlift_sl_cleanup() {
  rm -f "${TMPDIR:-/tmp}"/airlift-sl.* 2>/dev/null || true
}

airlift_sl_mktemp() {
  local _t
  _t="$(mktemp "${TMPDIR:-/tmp}/airlift-sl.XXXXXX")" || return 1
  chmod 600 "$_t" 2>/dev/null || true
  printf '%s\n' "$_t"
}

# Resolve airlift-engine.sh via the dual-cache pattern: prefer ~/.claude, then
# ~/.codex; newest version dir wins (ls -t | head -1). Echo the path on success,
# empty on failure. Guard with [ -n ] && [ -x ] at the call site.
airlift_sl_resolve_engine() {
  local _base _cand
  for _base in "$HOME/.claude" "$HOME/.codex"; do
    # Newest version directory first. Guard the glob with a -d test so an absent
    # cache yields nothing rather than a literal unexpanded pattern.
    local _verdir
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

# Determine the .airlift dir: explicit override, else repo-root/.airlift, else
# ./.airlift. Best-effort; never fails.
airlift_sl_dir() {
  if [ -n "${AIRLIFT_DIR:-}" ]; then
    printf '%s\n' "$AIRLIFT_DIR"
    return 0
  fi
  local _root
  _root="$(git rev-parse --show-toplevel 2>/dev/null)"
  if [ -n "$_root" ]; then
    printf '%s\n' "${_root}/.airlift"
  else
    printf '%s\n' "./.airlift"
  fi
  return 0
}

airlift_statusline_main() {
  # THRESHOLD default is 90, deliberately NOT 98. The used_percentage is a REAL
  # number, but the exact hard-cutoff moment and the weekly-cap interaction are
  # unpredictable, and the deterministic checkpoint needs a few seconds of live
  # budget to render a good bundle. Tripping at 90 leaves ~10% headroom so the
  # capture finishes before the model goes dark. Override with AIRLIFT_THRESHOLD.
  local threshold="${AIRLIFT_THRESHOLD:-90}"

  # 1. Read stdin ONCE into a 0600 temp so every consumer (jq, ccusage chain,
  #    prior statusLine) sees the SAME payload.
  local stdin_file
  stdin_file="$(airlift_sl_mktemp)" || stdin_file=""
  if [ -n "$stdin_file" ]; then
    cat > "$stdin_file" 2>/dev/null || true
  else
    # Could not mint a temp; drain stdin to avoid a broken pipe and continue
    # signal-less. We still try to chain the prior statusline (with empty stdin).
    cat >/dev/null 2>&1 || true
  fi

  # 2. PRIMARY signal: real rate_limits.five_hour.used_percentage + resets_at.
  local pct="" resets_at="" have_signal=0 signal_src=""
  if [ -n "$stdin_file" ] && command -v jq >/dev/null 2>&1; then
    pct="$(jq -r '.rate_limits.five_hour.used_percentage // empty' "$stdin_file" 2>/dev/null)"
    resets_at="$(jq -r '.rate_limits.five_hour.resets_at // empty' "$stdin_file" 2>/dev/null)"
    if [ -n "$pct" ]; then
      have_signal=1
      signal_src="rate_limits"
    fi
  fi

  # 3. FALLBACK signal: ccusage estimate, ONLY when rate_limits absent AND the
  #    ccusage CLI exists. Parse DEFENSIVELY -- the output shape is medium
  #    confidence, so guard every field access. Any parse failure -> no signal.
  if [ "$have_signal" -eq 0 ] && command -v ccusage >/dev/null 2>&1; then
    local cc_json
    cc_json="$(ccusage blocks --active --json 2>/dev/null)"
    if [ -n "$cc_json" ] && command -v jq >/dev/null 2>&1; then
      # Try several plausible shapes WITHOUT hardcoding a single field name that
      # may not exist. We look for an explicit percent first; if absent, derive
      # one from a used/limit pair when both are present and the limit is > 0.
      # Every path is guarded; a missing field yields empty, not an error.
      local cc_pct
      cc_pct="$(printf '%s' "$cc_json" | jq -r '
        # Normalize to a single active block object if the payload is an array
        # or wraps blocks under a key. Be liberal in what we accept.
        ( if type == "array" then (.[0] // {})
          elif (.blocks? and (.blocks | type == "array")) then (.blocks[0] // {})
          elif (.activeBlock? ) then .activeBlock
          else . end ) as $b
        | (
            # 1) explicit percent fields, several plausible names
            ( $b.usagePercent // $b.percentUsed // $b.percent // $b.projectedPercent // empty )
            //
            # 2) derive from used/limit-ish pairs when both present and limit>0
            ( ( $b.totalTokens // $b.tokensUsed // $b.usedTokens // empty ) as $used
              | ( $b.tokenLimit // $b.limit // $b.maxTokens // empty ) as $lim
              | if ($used != null and $lim != null and ($lim | type == "number") and $lim > 0)
                then ($used / $lim * 100)
                else empty end )
          )
        | select(. != null)
        | (. | tonumber? // empty)
      ' 2>/dev/null | head -1)"
      if [ -n "$cc_pct" ]; then
        # Carry the raw derived value; integer normalization happens ONCE at the
        # single convergence point in step 5 (round for this estimate source).
        pct="$cc_pct"
        if [ -n "$pct" ]; then
          have_signal=1
          signal_src="ccusage-estimate"
          # ccusage has no reset timestamp we can rely on; leave resets_at empty.
        fi
      fi
    fi
  fi

  # 4. CHAIN the prior statusLine. Source order: explicit env override, then the
  #    sidecar backup recorded at wire time. Run it with the SAME stdin.
  local prior_cmd=""
  if [ -n "${AIRLIFT_PRIOR_STATUSLINE:-}" ]; then
    prior_cmd="$AIRLIFT_PRIOR_STATUSLINE"
  else
    local backup="$(airlift_sl_dir)/settings-backup.json"
    if [ -f "$backup" ] && command -v python3 >/dev/null 2>&1; then
      prior_cmd="$(AIRLIFT_BACKUP="$backup" python3 - <<'PY' 2>/dev/null
import json, os
p = os.environ.get("AIRLIFT_BACKUP", "")
try:
    with open(p) as fh:
        data = json.load(fh)
    sl = data.get("statusLine") or {}
    cmd = sl.get("command") or ""
    # Only chain a real command-type prior statusline.
    if isinstance(cmd, str):
        print(cmd)
except Exception:
    pass
PY
)"
    fi
  fi

  local prior_out=""
  if [ -n "$prior_cmd" ]; then
    if [ -n "$stdin_file" ]; then
      prior_out="$(sh -c "$prior_cmd" < "$stdin_file" 2>/dev/null)"
    else
      prior_out="$(printf '' | sh -c "$prior_cmd" 2>/dev/null)"
    fi
  fi

  # 5. THRESHOLD monitor + trip. Only when we have a real or estimated percent.
  local airlift_segment=""
  if [ "$have_signal" -eq 1 ] && [ -n "$pct" ]; then
    # SINGLE normalization point: both signal sources (rate_limits float and the
    # ccusage estimate) converge here and pct is coerced to an integer exactly
    # once. rate_limits is a real measured percent -> floor (p + 0). The ccusage
    # estimate is a derived projection -> round half-up (p + 0.5). No source is
    # normalized twice.
    local pct_int round_bias=0
    [ "$signal_src" = "ccusage-estimate" ] && round_bias="0.5"
    pct_int="$(awk -v p="$pct" -v b="$round_bias" 'BEGIN { printf "%d", (p + b) }' 2>/dev/null)"
    [ -n "$pct_int" ] || pct_int=0

    local label="cap"
    [ "$signal_src" = "ccusage-estimate" ] && label="est"

    local reset_note=""
    [ -n "$resets_at" ] && reset_note=" resets ${resets_at}"

    if [ "$pct_int" -ge "$threshold" ] 2>/dev/null; then
      airlift_sl_trip "$pct_int" "$resets_at" "$signal_src"
      # A loud banner so the user sees it even mid-task. MUST contain the literal
      # resume hint `/airlift-in .airlift` and the bundle path.
      local bundle_dir="$(airlift_sl_dir)"
      airlift_segment="airlift WARNING ${label} ${pct_int}%${reset_note} -- run /airlift-in .airlift (bundle: ${bundle_dir})"
    else
      airlift_segment="airlift ${label} ${pct_int}%${reset_note}"
    fi
  fi

  # 6. Emit. Combine the chained prior output with airlift's segment. If neither
  #    is present, emit nothing. ALWAYS exit 0.
  if [ -n "$prior_out" ] && [ -n "$airlift_segment" ]; then
    printf '%s | %s\n' "$prior_out" "$airlift_segment"
  elif [ -n "$prior_out" ]; then
    printf '%s\n' "$prior_out"
  elif [ -n "$airlift_segment" ]; then
    printf '%s\n' "$airlift_segment"
  fi
  # No-signal + no-prior -> emit nothing at all. Exit 0 regardless.
  return 0
}

# Trip handler: debounce against the current block (compare stored resets_at),
# write the .trip flag, and fire the engine deterministic capture. Best-effort;
# never blocks the statusline, never errors.
airlift_sl_trip() {
  local pct_int="$1"
  local resets_at="$2"
  local signal_src="$3"

  local dir="$(airlift_sl_dir)"
  local trip_flag="${dir}/.trip"

  # Debounce: if a .trip exists whose stored resets_at matches the current
  # block's resets_at, we already fired for this block -- skip. A blank
  # resets_at (e.g. ccusage estimate) compares as the literal empty marker, so
  # consecutive estimate renders with no reset boundary still debounce within a
  # session via the same marker.
  local prior_reset_marker=""
  if [ -f "$trip_flag" ]; then
    # First line of the flag holds the resets_at marker we tripped on.
    prior_reset_marker="$(head -1 "$trip_flag" 2>/dev/null)"
  fi
  local cur_marker="${resets_at:-__no_reset__}"
  if [ -f "$trip_flag" ] && [ "$prior_reset_marker" = "$cur_marker" ]; then
    # Already tripped for this block -- debounced, do nothing.
    return 0
  fi

  # Ensure the dir exists, then write the debounce flag (resets_at marker on
  # line 1; human note on line 2). Use a 0600 temp then mv for atomicity.
  mkdir -p "$dir" 2>/dev/null || true
  local flag_tmp
  flag_tmp="$(airlift_sl_mktemp)" || flag_tmp=""
  if [ -n "$flag_tmp" ]; then
    {
      printf '%s\n' "$cur_marker"
      printf 'tripped at %s%% via %s on %s\n' "$pct_int" "$signal_src" "$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
    } > "$flag_tmp" 2>/dev/null
    mv "$flag_tmp" "$trip_flag" 2>/dev/null || true
  fi

  # Fire the engine deterministic capture. Resolve via dual-cache; no-op if
  # absent (the statusline must never break because the engine is missing).
  local engine
  engine="$(airlift_sl_resolve_engine)"
  if [ -n "$engine" ] && [ -x "$engine" ]; then
    bash "$engine" write --phase early-warning --note "threshold ${pct_int}%" >/dev/null 2>&1 || true
  fi
  return 0
}

# Source-vs-exec guard. Register the cleanup trap only on direct invocation so a
# sourcing caller's shell exit does not fire our sweep.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  trap airlift_sl_cleanup EXIT INT TERM
  airlift_statusline_main "$@"
  # Force a clean exit code regardless of the last command's status: a non-zero
  # statusLine exit would break the user's prompt.
  exit 0
fi
