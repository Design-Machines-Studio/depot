#!/usr/bin/env bash
#
# check-release-preflight.sh -- Verify a depot release is actually safe to tag
# and push, and print a release receipt.
#
# WHY THIS EXISTS
#   CLAUDE.md forbids claiming release/tag/push completion unless git auth, a
#   clean tree, version bumps, manifests, and tag preflights are verified. That
#   was an instruction with nothing behind it. This script makes it checkable.
#
# WHAT THIS CHECKS
#   1. Working tree is clean (no uncommitted or untracked residue)
#   2. marketplace.json and plugin.json declare the same version, per plugin
#   3. Codex manifests are in sync   (generate-codex-manifests.py --check)
#   4. Codex command skills are in sync (generate-codex-command-skills.py --check)
#   5. Every plugin changed since its last tag has had its version bumped
#   6. Push auth reachable (git ls-remote against origin)
#
# READ-ONLY. Creates no tags, pushes nothing, writes nothing. Exit non-zero on
# any failure -- a failing preflight means the release claim would be a lie.
#
# DEPENDENCIES: git, python3. Uses python3 rather than jq for JSON because the
#   sibling generators (generate-codex-*.py) already require python3, and jq is
#   not guaranteed present on a fresh macOS box.
#
# USAGE
#   ./tools/check-release-preflight.sh            # all checks
#   ./tools/check-release-preflight.sh --no-net   # skip the ls-remote auth probe

# Deliberately no `set -e`: we want every check to run and report, not abort on
# the first failure. `set -u` and pipefail are safe and wanted.
set -uo pipefail

# Fixed PATH -- prevent a caller-controlled PATH from hijacking git/python3.
PATH="/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin:/opt/homebrew/bin"
export PATH

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || exit 2

SKIP_NET=0
[ "${1:-}" = "--no-net" ] && SKIP_NET=1

failures=0
pass() { printf "  OK    %s\n" "$1"; }
fail() { printf "  FAIL  %s\n" "$1"; failures=1; }
skip() { printf "  SKIP  %s\n" "$1"; }

printf "Release Preflight\n"
printf "=================\n\n"

# --------------------------------------------------------------------------
# 1. Clean working tree
# --------------------------------------------------------------------------
printf "Working tree:\n"
residue="$(git status --porcelain)"
if [ -z "$residue" ]; then
  pass "clean tree"
else
  fail "uncommitted or untracked changes present"
  printf "%s\n" "$residue" | sed 's/^/          /'
fi

# --------------------------------------------------------------------------
# 2. Version sync: marketplace.json vs plugin.json
# --------------------------------------------------------------------------
printf "\nVersion sync:\n"
version_report="$(python3 - <<'PY'
import json, os, re, sys

root = os.getcwd()
mpath = os.path.join(root, ".claude-plugin", "marketplace.json")
if not os.path.exists(mpath):
    print("SKIP|marketplace.json not found")
    sys.exit(0)

try:
    with open(mpath) as f:
        market = json.load(f)
except (OSError, ValueError) as e:
    print(f"FAIL|marketplace.json unreadable: {e}")
    sys.exit(1)

# A plugin name reaches `git tag -l` and os.path.join below. Reject anything
# that could be read as a git option (leading '-') or escape the plugins dir
# ('.', '/'). This is first-party committed content, so the check is a
# tripwire, not a defence -- but a malformed name must FAIL, never skip.
NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")

for entry in market.get("plugins", []):
    name = entry.get("name")
    mver = entry.get("version")
    if not isinstance(name, str) or not NAME_RE.match(name):
        print(f"FAIL|{name!r}: invalid plugin name (want ^[a-z][a-z0-9-]*$)")
        continue
    if not isinstance(mver, str) or not re.match(r"^[0-9][0-9A-Za-z.+-]*$", mver):
        print(f"FAIL|{name}: invalid version {mver!r}")
        continue
    ppath = os.path.join(root, "plugins", name, ".claude-plugin", "plugin.json")
    if not os.path.exists(ppath):
        print(f"FAIL|{name}: plugin.json not found")
        continue
    # One unreadable manifest must not abort the loop and silently drop every
    # plugin after it -- that would print READY while skipping the check.
    try:
        with open(ppath) as f:
            pver = json.load(f).get("version")
    except (OSError, ValueError) as e:
        print(f"FAIL|{name}: plugin.json unreadable: {e}")
        continue
    if mver != pver:
        print(f"FAIL|{name}: marketplace.json={mver} but plugin.json={pver}")
    else:
        print(f"OK|{name} {pver}")
PY
)"
py_rc=$?

# Without this the script prints READY when the checker crashed: the while-loop
# below sees no FAIL| lines, so `failures` stays 0 and the unchecked plugins are
# invisible rather than blocking. A preflight that cannot run has not passed.
if [ "$py_rc" -ne 0 ]; then
  fail "version-sync checker exited non-zero (rc=$py_rc) -- cannot certify this release"
fi

sync_failed=0
while IFS='|' read -r status msg; do
  [ -z "${status:-}" ] && continue
  case "$status" in
    OK)   ;;  # counted below, not printed one-by-one
    FAIL) fail "$msg"; sync_failed=1 ;;
    SKIP) skip "$msg" ;;
  esac
done <<< "$version_report"

synced=$(printf "%s\n" "$version_report" | grep -c '^OK|' || true)
[ "$sync_failed" -eq 0 ] && [ "$synced" -gt 0 ] && pass "$synced plugins version-synced"

# --------------------------------------------------------------------------
# 3 + 4. Codex shims in sync
# --------------------------------------------------------------------------
printf "\nCodex shims:\n"
for gen in generate-codex-manifests.py generate-codex-command-skills.py; do
  if [ ! -x "$SCRIPT_DIR/$gen" ] && [ ! -f "$SCRIPT_DIR/$gen" ]; then
    fail "$gen not found"
    continue
  fi
  if python3 "$SCRIPT_DIR/$gen" --check >/dev/null 2>&1; then
    pass "$gen --check clean"
  else
    fail "$gen --check reports drift -- regenerate before releasing"
  fi
done

# --------------------------------------------------------------------------
# 5. Tag preflight
#
# An existing tag is not itself a problem -- most plugins are unchanged in any
# given release. The problem is a plugin whose FILES changed since its last tag
# but whose VERSION did not. That plugin would either collide on tag, or ship
# silently under a version Claude Desktop already has cached.
# --------------------------------------------------------------------------
printf "\nTag preflight:\n"
to_cut=0
unchanged=0
while IFS='|' read -r status msg; do
  [ "${status:-}" != "OK" ] && continue
  # msg is "<name> <version>"
  name="${msg% *}"
  ver="${msg##* }"
  tag="${name}-v${ver}"

  if [ -z "$(git tag -l "$tag")" ]; then
    to_cut=$((to_cut + 1))
    continue
  fi

  # Tag exists. Did anything under the plugin change since it was cut?
  changed="$(git diff --name-only "$tag..HEAD" -- "plugins/$name" 2>/dev/null | wc -l | tr -d ' ')"
  if [ "${changed:-0}" -gt 0 ]; then
    fail "$name: $changed file(s) changed since $tag but version is still $ver -- bump it"
  else
    unchanged=$((unchanged + 1))
  fi
done <<< "$version_report"

[ "$to_cut" -gt 0 ] && pass "$to_cut new tag(s) to cut"
[ "$unchanged" -gt 0 ] && pass "$unchanged plugin(s) already released and unchanged"

# --------------------------------------------------------------------------
# 6. Push auth
# --------------------------------------------------------------------------
printf "\nPush auth:\n"
if [ "$SKIP_NET" -eq 1 ]; then
  skip "ls-remote probe skipped (--no-net)"
elif ! git remote get-url origin >/dev/null 2>&1; then
  fail "no 'origin' remote configured"
elif git ls-remote --exit-code origin HEAD >/dev/null 2>&1; then
  pass "origin reachable and authenticated"
else
  fail "cannot reach or authenticate to origin -- do not claim a push succeeded"
fi

# --------------------------------------------------------------------------
# Receipt
# --------------------------------------------------------------------------
printf "\n"
printf '%s\n' "Release Receipt"
printf '%s\n' "---------------"
printf "  Commit:      %s\n" "$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
printf "  Branch:      %s\n" "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
printf "  Tree:        %s\n" "$([ -z "$residue" ] && echo clean || echo DIRTY)"
printf "  Plugins:     %s version-synced\n" "$synced"
printf "  New tags:    %s\n" "$(printf '%s\n' "$version_report" | awk -F'|' '$1=="OK"{split($2,a," "); print a[1]"-v"a[2]}' | while read -r t; do [ -z "$(git tag -l "$t")" ] && printf '%s ' "$t"; done)"
printf "\n"

if [ "$failures" -ne 0 ]; then
  printf "BLOCKED: release preflight failed. Do not tag, do not push, and do not\n"
  printf "         report the release as complete.\n\n"
  exit 1
fi

printf "READY: preflight passed. Tagging and pushing are safe to perform.\n"
printf "       This script performed neither -- run them explicitly.\n\n"
