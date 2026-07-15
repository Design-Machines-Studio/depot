#!/bin/bash -p
# Stable, isolated entry point for the workflow-kernel CLI.
#
# WHY THIS EXISTS
#   The runtime package is nested below a plugin references directory, so it is
#   not importable from an arbitrary project working directory.
#
# WHAT THIS FIXES
#   The host invokes this executable from an already trusted workflow-kernel
#   plugin root. This shim resets executable discovery, ignores inherited shell
#   and Python startup hooks, asks the adjacent side-effect-free resolver for
#   validated candidates, probes them in order, and executes the first viable
#   runtime. Candidate code never runs before manifest and descendant-realpath
#   validation.
#
# DEPENDENCIES
#   macOS system Bash 3.2+ and Python 3.12+ on the fixed PATH below.
#
# USAGE
#   workflow-kernel-launcher.sh <subcommand> [args...]

PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH
unset BASH_ENV ENV PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE

EXIT_RUNTIME_UNAVAILABLE=4

fail() {
  echo "workflow-kernel-launcher: $1" >&2
  exit "$EXIT_RUNTIME_UNAVAILABLE"
}

SELF="$0"
SELF_HOPS=0
while [ -L "$SELF" ]; do
  SELF_HOPS=$((SELF_HOPS + 1))
  [ "$SELF_HOPS" -le 40 ] || fail "launcher path symlink chain exceeds 40 hops (cycle?)"
  LINK="$(readlink "$SELF")" || fail "cannot read launcher symlink"
  case "$LINK" in
    /*) SELF="$LINK" ;;
    *) SELF="$(dirname "$SELF")/$LINK" ;;
  esac
done
SELF_DIR="$(cd "$(dirname "$SELF")" 2>/dev/null && pwd -P)" || fail "cannot resolve launcher directory"

PYTHON=""
for CANDIDATE in python3 python3.13 python3.12; do
  if command -v "$CANDIDATE" >/dev/null 2>&1 && \
     "$CANDIDATE" -I -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
    PYTHON="$(command -v "$CANDIDATE")"
    break
  fi
done
[ -n "$PYTHON" ] || fail "python3 >= 3.12 not found on the fixed PATH"

RESOLVER_DIR="$(cd "$SELF_DIR/workflow_kernel" 2>/dev/null && pwd -P)" || fail "trusted runtime resolver unavailable"
case "$RESOLVER_DIR" in
  "$SELF_DIR"/*) ;;
  *) fail "trusted runtime resolver escapes launcher root" ;;
esac
RESOLVER="$RESOLVER_DIR/runtime_resolution.py"
[ -f "$RESOLVER" ] && [ ! -L "$RESOLVER" ] || fail "trusted runtime resolver unavailable"

PLUGIN_ROOT="$(cd "$SELF_DIR/../../.." 2>/dev/null && pwd -P)" || fail "cannot resolve trusted plugin root"
RUNTIME_CANDIDATES="$($PYTHON -I "$RESOLVER" --candidates "$PLUGIN_ROOT" 2>/dev/null)" || fail "workflow-kernel runtime not found"

run_module() {
  RUNTIME="$1"
  shift
  "$PYTHON" -I -c 'import runpy,sys; runtime=sys.argv[1]; args=sys.argv[2:]; sys.path.insert(0, runtime); sys.argv=["workflow_kernel", *args]; runpy.run_module("workflow_kernel", run_name="__main__")' "$RUNTIME" "$@"
}

KERNEL_REFS=""
while IFS= read -r CANDIDATE; do
  [ -n "$CANDIDATE" ] || continue
  if run_module "$CANDIDATE" --help >/dev/null 2>&1; then
    KERNEL_REFS="$CANDIDATE"
    break
  fi
done <<EOF
$RUNTIME_CANDIDATES
EOF

[ -n "$KERNEL_REFS" ] || fail "workflow-kernel runtime not found"
run_module "$KERNEL_REFS" "$@"
