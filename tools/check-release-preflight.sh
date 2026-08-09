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
#   6. Installed Codex plugins match the canonical marketplace versions
#   7. Remote branches do not carry equal versions for independently changed plugins
#   8. Push auth reachable (git ls-remote against origin)
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

# Cache remote object probes by advertised SHA. Bash 3.2 has no associative
# arrays, so the small ls-remote set is stored as newline-delimited SHA|rc rows.
# A cached failure is returned to every affected plugin without repeating the
# network operation, preserving per-plugin FAIL receipts.
fetch_remote_sha_once() {
  fetch_sha="$1"
  cached_fetch_rc="$(printf '%s\n' "$remote_fetch_records" | awk -F'|' -v sha="$fetch_sha" '$1 == sha {print $2; exit}')"
  if [ -n "$cached_fetch_rc" ]; then
    remote_fetch_rc="$cached_fetch_rc"
    return 0
  fi

  git fetch --no-tags --quiet --no-write-fetch-head origin "$fetch_sha"
  remote_fetch_rc=$?
  remote_fetch_records="${remote_fetch_records}${remote_fetch_records:+$'\n'}${fetch_sha}|${remote_fetch_rc}"
}

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
# 6. Codex cache freshness
#
# Resolve the depot marketplace root through Codex itself. The root is managed
# by Codex and has moved before, so neither the snapshot nor cache location may
# be inferred from a documented path. `plugin list --json` is the authoritative
# installed-set view and avoids reconstructing a cache path from the snapshot.
# --------------------------------------------------------------------------
check_codex_cache_freshness() {
printf "\nCodex cache freshness:\n"
if ! command -v codex >/dev/null 2>&1; then
  skip "codex CLI not installed; Codex cache freshness not checked"
else
  codex_marketplaces="$(codex plugin marketplace list)"
  codex_marketplaces_rc=$?
  codex_marketplace_root="$(printf '%s\n' "$codex_marketplaces" | awk '$1 == "depot" {$1=""; sub(/^[[:space:]]+/, ""); print; exit}')"

  if [ "$codex_marketplaces_rc" -ne 0 ]; then
    skip "codex plugin marketplace list failed (rc=$codex_marketplaces_rc); Codex cache freshness not checked"
  elif [ -z "$codex_marketplace_root" ] || [ ! -d "$codex_marketplace_root" ]; then
    skip "codex plugin marketplace list did not resolve a readable depot root; Codex cache freshness not checked"
  else
    codex_plugins="$(codex plugin list --marketplace depot --json)"
    codex_plugins_rc=$?
    if [ "$codex_plugins_rc" -ne 0 ]; then
      skip "codex installed-plugin query failed (rc=$codex_plugins_rc); Codex cache freshness not checked"
    else
      codex_cache_report="$(printf '%s\n' "$codex_plugins" | python3 -c '
import json, re, sys

marketplace_path = sys.argv[1]
name_re = re.compile(r"^[a-z][a-z0-9-]*$")
try:
    installed_doc = json.load(sys.stdin)
    with open(marketplace_path) as fh:
        canonical_doc = json.load(fh)
except (OSError, ValueError) as exc:
    print(f"SKIP|Codex cache data unreadable: {exc}")
    raise SystemExit(0)

if not isinstance(installed_doc, dict) or not isinstance(canonical_doc, dict):
    print("SKIP|Codex cache data has an unexpected top-level JSON shape")
    raise SystemExit(0)

installed = installed_doc.get("installed")
plugins = canonical_doc.get("plugins")
if not isinstance(installed, list) or not isinstance(plugins, list):
    print("SKIP|Codex cache data has an unexpected JSON shape")
    raise SystemExit(0)

canonical = {
    row.get("name"): row.get("version")
    for row in plugins
    if isinstance(row, dict)
}
checked = 0
for row in installed:
    if not isinstance(row, dict) or row.get("installed") is not True:
        continue
    name = row.get("name")
    cached = row.get("version")
    if not isinstance(name, str) or not name_re.match(name) or not isinstance(cached, str):
        print("SKIP|Codex installed-plugin data contains an invalid name or version")
        raise SystemExit(0)
    expected = canonical.get(name)
    if not isinstance(expected, str):
        print(f"FAIL|{name}: Codex has {cached}, but the plugin is absent from canonical marketplace.json")
    elif cached != expected:
        print(f"FAIL|{name}: Codex cache={cached}, canonical marketplace={expected}; fix: run codex plugin marketplace upgrade interactively, then codex plugin add {name}@depot")
    checked += 1
print(f"OK|{checked} installed Codex plugin(s) checked against {sys.argv[2]}")
' "$REPO_ROOT/.claude-plugin/marketplace.json" "$codex_marketplace_root")"
      codex_cache_report_rc=$?

      codex_cache_failed=0
      codex_cache_ok=""
      if [ "$codex_cache_report_rc" -ne 0 ]; then
        fail "Codex cache checker exited non-zero (rc=$codex_cache_report_rc) -- cannot certify installed plugin versions"
        codex_cache_failed=1
      else
        while IFS='|' read -r status msg; do
          [ -z "${status:-}" ] && continue
          case "$status" in
            OK)   codex_cache_ok="$msg" ;;
            FAIL) fail "$msg"; codex_cache_failed=1 ;;
            SKIP) skip "$msg" ;;
          esac
        done <<< "$codex_cache_report"
      fi
      [ "$codex_cache_failed" -eq 0 ] && [ -n "$codex_cache_ok" ] && pass "$codex_cache_ok"
    fi
  fi
fi
}

check_codex_cache_freshness

# --------------------------------------------------------------------------
# 7. Cross-lane equal-bump guard
#
# A version that exceeds one parent but equals another can auto-merge without a
# conflict. Inspect only remote branches descended from the last plugin release
# tag, and only their plugin manifest, so the network and object cost is bounded.
# --------------------------------------------------------------------------
check_cross_lane_bumps() {
printf "\nCross-lane version bumps:\n"
if [ "$SKIP_NET" -eq 1 ]; then
  skip "remote equal-bump probe skipped (--no-net)"
elif ! git remote get-url origin >/dev/null 2>&1; then
  fail "no 'origin' remote configured; cannot inspect cross-lane version bumps"
else
  remote_heads="$(git ls-remote --heads origin 2>&1)"
  remote_heads_rc=$?
  if [ "$remote_heads_rc" -ne 0 ]; then
    fail "cannot list origin branches for equal-bump inspection (rc=$remote_heads_rc)"
  else
    remote_fetch_records=""
    equal_bump_checked=0
    equal_bump_failed=0
    current_branch="$(git rev-parse --abbrev-ref HEAD)"
    while IFS='|' read -r status msg; do
      [ "${status:-}" != "OK" ] && continue
      name="${msg% *}"
      ver="${msg##* }"
      manifest="plugins/$name/.claude-plugin/plugin.json"
      last_tag="$(git tag --merged HEAD --sort=-version:refname -l "${name}-v*" | head -1)"
      [ -z "$last_tag" ] && continue
      git diff --quiet "$last_tag..HEAD" -- "plugins/$name"
      local_plugin_diff_rc=$?
      case "$local_plugin_diff_rc" in
        0) continue ;;
        1) ;;
        *)
          fail "$name: cannot compare local plugin files with $last_tag (git diff rc=$local_plugin_diff_rc)"
          equal_bump_failed=1
          continue
          ;;
      esac

      while IFS=$'\t' read -r remote_sha remote_ref; do
        [ -z "${remote_sha:-}" ] && continue
        remote_branch="${remote_ref#refs/heads/}"

        fetch_remote_sha_once "$remote_sha"
        fetch_rc="$remote_fetch_rc"
        if [ "$fetch_rc" -ne 0 ]; then
          fail "$name: cannot inspect origin/$remote_branch for an equal bump (fetch rc=$fetch_rc)"
          equal_bump_failed=1
          continue
        fi
        git merge-base --is-ancestor "$last_tag" "$remote_sha"
        release_ancestor_rc=$?
        case "$release_ancestor_rc" in
          0) ;;
          1) continue ;;
          *)
            fail "$name: cannot classify origin/$remote_branch against $last_tag (merge-base rc=$release_ancestor_rc)"
            equal_bump_failed=1
            continue
            ;;
        esac
        # A remote head already contained in the local branch is shared history,
        # not an independent lane. For divergent heads, both manifests must have
        # changed from their merge base for equal versions to be hazardous.
        git merge-base --is-ancestor "$remote_sha" HEAD
        contained_remote_rc=$?
        case "$contained_remote_rc" in
          0) continue ;;
          1) ;;
          *)
            fail "$name: cannot classify whether origin/$remote_branch is contained in HEAD (merge-base rc=$contained_remote_rc)"
            equal_bump_failed=1
            continue
            ;;
        esac
        lane_base="$(git merge-base HEAD "$remote_sha")"
        lane_base_rc=$?
        if [ "$lane_base_rc" -ne 0 ] || [ -z "$lane_base" ]; then
          fail "$name: cannot establish a merge base with origin/$remote_branch"
          equal_bump_failed=1
          continue
        fi
        git diff --quiet "$lane_base..HEAD" -- "$manifest"
        local_manifest_diff_rc=$?
        git diff --quiet "$lane_base..$remote_sha" -- "$manifest"
        remote_manifest_diff_rc=$?
        if [ "$local_manifest_diff_rc" -gt 1 ] || [ "$remote_manifest_diff_rc" -gt 1 ]; then
          fail "$name: cannot compare divergent manifests with origin/$remote_branch (local rc=$local_manifest_diff_rc, remote rc=$remote_manifest_diff_rc)"
          equal_bump_failed=1
          continue
        fi
        if [ "$local_manifest_diff_rc" -eq 0 ] || [ "$remote_manifest_diff_rc" -eq 0 ]; then
          continue
        fi

        remote_manifest="$(git show "$remote_sha:$manifest" 2>&1)"
        remote_manifest_rc=$?
        if [ "$remote_manifest_rc" -ne 0 ]; then
          fail "$name: origin/$remote_branch changed $manifest but its manifest cannot be read"
          equal_bump_failed=1
          continue
        fi
        remote_ver="$(printf '%s\n' "$remote_manifest" | python3 -c 'import json,sys; value=json.load(sys.stdin).get("version"); print(value if isinstance(value, str) else "")' 2>&1)"
        remote_ver_rc=$?
        if [ "$remote_ver_rc" -ne 0 ] || [ -z "$remote_ver" ]; then
          fail "$name: origin/$remote_branch has an unreadable plugin version"
          equal_bump_failed=1
          continue
        fi

        equal_bump_checked=$((equal_bump_checked + 1))
        if [ "$remote_ver" = "$ver" ]; then
          fail "$name: local $current_branch and origin/$remote_branch both declare $ver after changing the plugin; keep both changes and re-bump one side above the other before merge"
          equal_bump_failed=1
        fi
      done <<< "$remote_heads"
    done <<< "$version_report"
    [ "$equal_bump_failed" -eq 0 ] && pass "$equal_bump_checked remote changed-plugin manifest(s) checked for equal bumps"
  fi
fi
}

check_cross_lane_bumps

# --------------------------------------------------------------------------
# 8. Push auth
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

if [ "$SKIP_NET" -eq 1 ]; then
  printf "READY: local preflight passed. The repository is ready for tagging.\n"
  printf "       Push safety is unverified because --no-net skipped the origin probe.\n"
else
  printf "READY: preflight passed. Tagging and pushing are safe to perform.\n"
fi
printf "       This script performed neither -- run them explicitly.\n\n"
