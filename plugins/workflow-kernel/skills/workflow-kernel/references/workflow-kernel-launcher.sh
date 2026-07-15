#!/bin/bash
# workflow-kernel-launcher.sh -- stable entry point for the workflow-kernel CLI
#
# WHY THIS EXISTS
#   Integration blocks in pipeline and dm-review invoke `python3 -m
#   workflow_kernel`, but the module is nested under this plugin's
#   skills/workflow-kernel/references/ directory and is not importable from a
#   project working directory. Every caller needs the same resolution,
#   interpreter check, and module-path setup; this launcher owns all three so
#   the Markdown contracts stay declarative.
#
# WHAT THIS FIXES
#   dm-review finding 062: `python3 -m workflow_kernel` fails with
#   ModuleNotFoundError from any project cwd, and the runtime resolver itself
#   lives inside the unimportable package. The launcher resolves the canonical
#   runtime (the repo checkout beneath this script's own realpath first, then
#   semver-sorted versioned cache directories under ~/.claude and ~/.codex),
#   verifies Python 3.12+, sets PYTHONPATH, and execs the CLI.
#
# DEPENDENCIES
#   bash 3.2+ (macOS default), python3 >= 3.12 on the fixed PATH below
#   (python3, python3.13, or python3.12). No other tools beyond POSIX
#   utilities already guaranteed by the fixed PATH.
#
# USAGE
#   workflow-kernel-launcher.sh <subcommand> [args...]
#   e.g. workflow-kernel-launcher.sh init .workflow-kernel/runs/run-1 \
#          --run-id run-1 --mode shadow --occurred-at 2026-07-15T00:00:00Z
#   Exit codes are the workflow-kernel CLI's own stable codes; the launcher
#   exits 4 (runtime unavailable) when no compatible runtime or interpreter
#   can be resolved.

# Fixed PATH reset: never trust caller-controlled PATH for dependency lookup.
PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH

EXIT_RUNTIME_UNAVAILABLE=4

fail() {
  echo "workflow-kernel-launcher: $1" >&2
  exit "$EXIT_RUNTIME_UNAVAILABLE"
}

# --- Resolve this script's own real directory (following symlinks) ---------
SELF="$0"
while [ -L "$SELF" ]; do
  LINK="$(readlink "$SELF")" || break
  case "$LINK" in
    /*) SELF="$LINK" ;;
    *) SELF="$(dirname "$SELF")/$LINK" ;;
  esac
done
SELF_DIR="$(cd "$(dirname "$SELF")" 2>/dev/null && pwd -P)" || fail "cannot resolve launcher directory"

# --- Resolve the canonical runtime ------------------------------------------
# 1. Repo checkout: this launcher ships beside the runtime package. When the
#    executing copy is a repository checkout (not an installed plugin cache),
#    its own references directory is the canonical runtime.
# 2. Otherwise: newest compatible (same-major, >= 0.1.0) semver-named version
#    directory under ~/.claude then ~/.codex plugin caches. Never mtime order:
#    re-pulling an older version must not shadow a newer one.
KERNEL_REFS=""
case "$SELF_DIR" in
  */plugins/cache/depot/workflow-kernel/*) ;; # installed cache copy: prefer cache scan below
  *)
    if [ -f "$SELF_DIR/workflow_kernel/__main__.py" ]; then
      KERNEL_REFS="$SELF_DIR"
    fi
    ;;
esac

if [ -z "$KERNEL_REFS" ]; then
  for CACHE_ROOT in "$HOME/.claude/plugins/cache/depot/workflow-kernel" \
                    "$HOME/.codex/plugins/cache/depot/workflow-kernel"; do
    [ -d "$CACHE_ROOT" ] || continue
    # Same-major compatibility with the declared >=0.1.0 dependency floor:
    # accept 0.x.y (x >= 1), sort numerically by semver segments, newest first.
    while IFS= read -r VERSION; do
      CANDIDATE="$CACHE_ROOT/$VERSION/skills/workflow-kernel/references"
      if [ -f "$CANDIDATE/workflow_kernel/__main__.py" ]; then
        KERNEL_REFS="$CANDIDATE"
        break
      fi
    done <<EOF
$(ls "$CACHE_ROOT" 2>/dev/null | grep -E '^0\.[0-9]+\.[0-9]+$' | grep -v '^0\.0\.' | sort -t. -k1,1nr -k2,2nr -k3,3nr)
EOF
    [ -n "$KERNEL_REFS" ] && break
  done
fi

# Installed-cache copy with no scannable cache (unusual): fall back to itself.
if [ -z "$KERNEL_REFS" ] && [ -f "$SELF_DIR/workflow_kernel/__main__.py" ]; then
  KERNEL_REFS="$SELF_DIR"
fi

[ -n "$KERNEL_REFS" ] || fail "no compatible workflow-kernel runtime found (repo checkout or ~/.claude|~/.codex plugin cache)"

# --- Verify a Python 3.12+ interpreter --------------------------------------
PYTHON=""
for CANDIDATE in python3 python3.13 python3.12; do
  if command -v "$CANDIDATE" >/dev/null 2>&1 && \
     "$CANDIDATE" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; then
    PYTHON="$(command -v "$CANDIDATE")"
    break
  fi
done
[ -n "$PYTHON" ] || fail "python3 >= 3.12 not found on the fixed PATH"

# --- Exec the CLI with the module path set ----------------------------------
PYTHONPATH="$KERNEL_REFS" exec "$PYTHON" -m workflow_kernel "$@"
