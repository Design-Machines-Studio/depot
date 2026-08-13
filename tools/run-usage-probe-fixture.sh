#!/usr/bin/env bash
# run-usage-probe-fixture.sh -- deterministic, fixture-only usage-probe runner.
#
# Usage: run-usage-probe-fixture.sh [codex-app-server-fixture.json]
# With no argument, fixture bytes are read from stdin. The fixture replaces only
# the Codex app-server command output; the production probe owns all parsing,
# aggregation, profile selection, and evidence construction.

set -euo pipefail

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
USAGE_PROBE="$REPO_ROOT/plugins/pipeline/references/usage-probe.sh"

if [ "$#" -gt 1 ]; then
  echo "usage: $0 [codex-app-server-fixture.json]" >&2
  exit 2
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "usage-probe fixture wrapper: jq required" >&2
  exit 2
fi

fixture_root="$(mktemp -d "${TMPDIR:-/tmp}/usage-probe-fixture.XXXXXX")"
fixture_tmp="$fixture_root/codex-app-server.json"
fixture_repo="$fixture_root/repository"
trap 'rm -rf "$fixture_root"' EXIT

if [ "$#" -eq 1 ]; then
  [ -f "$1" ] && [ ! -L "$1" ] && [ -r "$1" ] || {
    echo "usage-probe fixture wrapper: fixture must be a readable regular file, not a symlink" >&2
    exit 2
  }
  command cat "$1" > "$fixture_tmp"
else
  command cat > "$fixture_tmp"
fi

# Keep the deterministic interface small enough that an accidentally supplied
# log or stream cannot turn a repository validator into an unbounded probe.
fixture_bytes="$(wc -c < "$fixture_tmp" | tr -d '[:space:]')"
case "$fixture_bytes" in
  ''|*[!0-9]*) echo "usage-probe fixture wrapper: could not size fixture" >&2; exit 2 ;;
esac
if [ "$fixture_bytes" -gt 1048576 ]; then
  echo "usage-probe fixture wrapper: fixture exceeds 1 MiB limit" >&2
  exit 2
fi

echo "usage-probe fixture wrapper: FIXTURE-ONLY EVIDENCE; NOT LIVE CAPACITY" >&2

# Bash exports functions to Bash children, so the real production probe sees a
# fixed test double at `command -v codex` even after it resets PATH. The double
# accepts only the production app-server invocation and treats fixture bytes as
# data. It neither evaluates fixture content nor accepts an executable path.
codex() {
  [ "$#" -eq 2 ] && [ "$1" = "app-server" ] && [ "$2" = "--stdio" ] \
    || return 2
  command cat "$USAGE_PROBE_FIXTURE_BYTES_FILE"
}
export -f codex
export USAGE_PROBE_FIXTURE_BYTES_FILE="$fixture_tmp"

# No configured OpenRouter credential reaches the production child, so this
# test-only runner cannot make the probe's one network request.
unset OPENROUTER_API_KEY OPENROUTER_API_KEY_FILE OPENROUTER_BUNDLE_RESOLVED
unset OPENROUTER_BUNDLE_REF OPENROUTER_BUNDLE_VERSION WORKFLOW_KERNEL

# Run from a wrapper-owned empty checkout so a developer's real operator
# profile cannot execute during deterministic fixture tests.
git init -q "$fixture_repo"
probe_output="$(cd "$fixture_repo" && bash "$USAGE_PROBE")"
printf '%s\n' "$probe_output" | jq -ce '.probe_source = "fixture"'
