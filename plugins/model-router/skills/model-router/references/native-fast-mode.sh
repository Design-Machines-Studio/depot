#!/usr/bin/env bash
# Native configuration support only; served-tier confirmation is separate.
# Return 0 supported, 1 confirmed unsupported, 2 unavailable discovery.
codex_fast_supported() {
  [ -n "$1" ] && [ -x "$1" ] || return 2
  local features help
  features="$("$1" features list 2>/dev/null)" || return 2
  help="$("$1" exec --help 2>/dev/null)" || return 2
  # Read complete bounded native output first: grep -q in a pipe can make a
  # healthy CLI exit via SIGPIPE under pipefail and invent unavailability.
  grep -Eq '^fast_mode[[:space:]]' <<< "$features" || return 1
  grep -Fq -- '--strict-config' <<< "$help"
}
