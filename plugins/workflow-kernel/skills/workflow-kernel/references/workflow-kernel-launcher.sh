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
#   dm-review finding 082: the launcher enforces the same trust boundaries as
#   the runtime-resolution.md contract, in validate-before-execute order.
#   Every candidate must pass realpath containment, a plugin.json name +
#   version check (cache candidates: declared version == directory segment),
#   and the shared same-major >= 0.1.0 semver rule BEFORE the importability
#   probe runs any candidate code. Caller PYTHONPATH/PYTHONHOME/PYTHONSTARTUP
#   are unset up front so neither the interpreter check nor the probe executes
#   caller-controlled startup code, and launcher-path symlink resolution is
#   hop-bounded so a symlink cycle exits 4 instead of hanging.
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

# Never inherit caller-controlled Python startup surface: a rogue PYTHONPATH
# (sitecustomize/encodings) or PYTHONSTARTUP would execute arbitrary code the
# moment any interpreter below starts, and PYTHONHOME would survive into the
# final exec. PYTHONPATH is re-set explicitly where the runtime needs it.
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP

EXIT_RUNTIME_UNAVAILABLE=4

fail() {
  echo "workflow-kernel-launcher: $1" >&2
  exit "$EXIT_RUNTIME_UNAVAILABLE"
}

# --- Resolve this script's own real directory (following symlinks) ---------
# Hop-bounded: a symlink cycle must exit 4, never hang the caller.
SELF="$0"
SELF_HOPS=0
while [ -L "$SELF" ]; do
  SELF_HOPS=$((SELF_HOPS + 1))
  [ "$SELF_HOPS" -le 40 ] || fail "launcher path symlink chain exceeds 40 hops (cycle?)"
  LINK="$(readlink "$SELF")" || break
  case "$LINK" in
    /*) SELF="$LINK" ;;
    *) SELF="$(dirname "$SELF")/$LINK" ;;
  esac
done
SELF_DIR="$(cd "$(dirname "$SELF")" 2>/dev/null && pwd -P)" || fail "cannot resolve launcher directory"

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

# Probe a candidate references directory: the module must actually run.
# -P keeps a workflow_kernel package in the caller's cwd from shadowing the
# resolved runtime (python -m otherwise prepends cwd to sys.path).
# Validation order is fixed: this probe EXECUTES candidate code, so it runs
# only after realpath containment and the manifest checks below have passed.
viable() {
  PYTHONPATH="$1" "$PYTHON" -P -m workflow_kernel --help >/dev/null 2>&1
}

# Validate a candidate plugin root's manifest without executing candidate
# code: plugin.json (or .codex-plugin/plugin.json) must declare
# name == workflow-kernel and a same-major version at or above the shared
# >= 0.1.0 floor. $2, when non-empty, is the cache directory version segment
# the declared version must equal (a mismatch is a corrupt install).
manifest_ok() {
  "$PYTHON" -P - "$1" "$2" <<'MANIFEST_PY'
import json, re, sys
from pathlib import Path
root, expected = Path(sys.argv[1]), sys.argv[2]
for marker in (".claude-plugin", ".codex-plugin"):
    manifest = root / marker / "plugin.json"
    if manifest.is_file():
        break
else:
    raise SystemExit(1)
try:
    document = json.loads(manifest.read_text())
except Exception:
    raise SystemExit(1)
if not isinstance(document, dict) or document.get("name") != "workflow-kernel":
    raise SystemExit(1)
version = document.get("version")
if not isinstance(version, str) or re.fullmatch(r"0\.(?:[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version) is None:
    raise SystemExit(1)
raise SystemExit(0 if not expected or version == expected else 1)
MANIFEST_PY
}

# Realpath containment: the resolved candidate directory must stay beneath
# the resolved boundary root. Rejects symlinked version directories that
# escape the plugin cache (or repo) trust boundary.
contained() {
  BOUNDARY="$(cd "$1" 2>/dev/null && pwd -P)" || return 1
  RESOLVED="$(cd "$2" 2>/dev/null && pwd -P)" || return 1
  case "$RESOLVED" in
    "$BOUNDARY"|"$BOUNDARY"/*) return 0 ;;
    *) return 1 ;;
  esac
}

# --- Resolve the canonical runtime ------------------------------------------
# 1. Repo checkout: this launcher ships beside the runtime package. When the
#    executing copy is a repository checkout (not an installed plugin cache),
#    its own references directory is the canonical runtime.
# 2. Otherwise: newest compatible (same-major, >= 0.1.0) semver-named version
#    directory under ~/.claude then ~/.codex plugin caches, probed for
#    importability. Never mtime order: re-pulling an older version must not
#    shadow a newer one.
# A references directory is trusted only after (in this order): the package
# entry point exists, the owning plugin root's manifest validates, and only
# then the importability probe executes it. $2 is the expected cache version
# segment ("" for the repo checkout / self fallback).
trusted_runtime() {
  [ -f "$1/workflow_kernel/__main__.py" ] || return 1
  manifest_ok "$1/../../.." "$2" || return 1
  viable "$1"
}

KERNEL_REFS=""
case "$SELF_DIR" in
  */plugins/cache/depot/workflow-kernel/*) ;; # installed cache copy: prefer cache scan below
  *)
    if trusted_runtime "$SELF_DIR" ""; then
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
    # Each candidate must pass realpath containment under the cache root and
    # the manifest name/version==segment check BEFORE the probe executes it.
    while IFS= read -r VERSION; do
      [ -n "$VERSION" ] || continue
      contained "$CACHE_ROOT" "$CACHE_ROOT/$VERSION" || continue
      CANDIDATE="$CACHE_ROOT/$VERSION/skills/workflow-kernel/references"
      if trusted_runtime "$CANDIDATE" "$VERSION"; then
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
if [ -z "$KERNEL_REFS" ] && trusted_runtime "$SELF_DIR" ""; then
  KERNEL_REFS="$SELF_DIR"
fi

[ -n "$KERNEL_REFS" ] || fail "workflow-kernel runtime not found (repo checkout or ~/.claude|~/.codex plugin cache)"

# --- Exec the CLI with the module path set ----------------------------------
PYTHONPATH="$KERNEL_REFS" exec "$PYTHON" -P -m workflow_kernel "$@"
