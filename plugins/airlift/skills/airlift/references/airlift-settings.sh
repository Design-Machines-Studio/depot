#!/usr/bin/env bash
#
# airlift-settings.sh: Idempotent settings.json auto-wire for airlift Tier-3.
#
# WHY THIS EXISTS:
#   The Tier-3 early-warning monitor (airlift-statusline.sh) and the reactive
#   backstop (airlift-hook-flush.sh) only help if they are wired into the
#   harness. Hand-editing settings.json is error-prone: it is easy to clobber an
#   existing statusLine (the user's caveman prompt) or to double-wrap on a second
#   run. This tool wires both, CHAINS rather than clobbers the existing
#   statusLine, and is fully idempotent -- a second wire makes no changes.
#
# WHAT THIS FIXES:
#   - Preserves the existing statusLine by backing it up to a sidecar
#     (.airlift/settings-backup.json) on the FIRST wire only, then recording the
#     prior command so the wrapper can chain it.
#   - Adds a StopFailure hook that fires the reactive flush on rate_limit /
#     overloaded / billing_error failures.
#   - unwire restores the original statusLine byte-exact and removes every
#     airlift hook entry.
#   - ALL JSON edits go through python3 (json.load / json.dump). NEVER jq -i,
#     NEVER sed on JSON.
#
# DEPENDENCIES:
#   - bash 3.2+ (macOS default 3.2.57). NO bash-4 features.
#   - python3 (the ONLY JSON editor; json module).
#   - ls, head, command (POSIX/BSD-portable usage).
#   - NO network calls.
#
# USAGE:
#   bash airlift-settings.sh wire   [--settings <path>]   # default ~/.claude/settings.json
#   bash airlift-settings.sh unwire [--settings <path>]
#   bash airlift-settings.sh status [--settings <path>]
#
# SECURITY NOTES:
#   - PATH is reset to a fixed value to prevent caller-controlled hijack of
#     python3/ls/head and the resolved scripts.
#   - The sidecar backup is written via python3 json.dump; it stores ONLY the
#     prior statusLine object (no secrets are read from or copied into it).
#   - The sidecar is written once and NEVER overwritten -- a second wire that
#     re-backed-up the (already airlift-ified) statusLine would lose the true
#     original. unwire restores from this immutable backup.
#   - Settings writes go to a sibling temp then os.replace() for atomicity, so a
#     crash mid-write cannot truncate the user's settings.json.

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

# The sentinel substring every airlift-installed command string must contain so
# that check-before-add and unwire can find airlift entries unambiguously.
AIRLIFT_SENTINEL="airlift"

# Resolve a sibling script next to THIS file (airlift-statusline.sh /
# airlift-hook-flush.sh). Echo absolute path on success. Uses BASH_SOURCE so it
# works through symlinks/wrappers. Falls back to the dual-cache if the sibling
# is missing (e.g. invoked from an unusual location).
airlift_settings_resolve_sibling() {
  local name="$1"
  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
  if [ -n "$script_dir" ] && [ -f "${script_dir}/${name}" ]; then
    printf '%s\n' "${script_dir}/${name}"
    return 0
  fi
  # Dual-cache fallback: ~/.claude then ~/.codex, newest version dir wins.
  local _base _verdir _cand
  for _base in "$HOME/.claude" "$HOME/.codex"; do
    for _verdir in $(ls -t -d "$_base"/plugins/cache/depot/airlift/*/ 2>/dev/null); do
      [ -d "$_verdir" ] || continue
      _cand="${_verdir}skills/airlift/references/${name}"
      if [ -f "$_cand" ]; then
        printf '%s\n' "$_cand"
        return 0
      fi
    done
  done
  return 1
}

# Determine the .airlift dir (repo root if inside a git repo, else CWD). The
# sidecar backup lives here so it travels with the project, matching where the
# engine writes its bundle.
airlift_settings_dir() {
  if [ -n "${AIRLIFT_DIR:-}" ]; then
    printf '%s\n' "$AIRLIFT_DIR"
    return 0
  fi
  local _root
  _root="$(git rev-parse --show-toplevel 2>/dev/null)"
  if [ -n "$_root" ]; then
    printf '%s\n' "${_root}/.airlift"
  else
    printf '%s\n' "$PWD/.airlift"
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Adversary schema check: before writing the StopFailure hook, READ the target
# settings.json (and the local ~/.claude/settings.json if available) to confirm
# the installed hook schema places `matcher` on the event-group object with a
# nested `hooks` array -- the shape this tool assumes. If the installed schema
# differs, SURFACE it as ambiguity rather than guessing.
# ---------------------------------------------------------------------------
airlift_settings_schema_check() {
  local target="$1"
  AIRLIFT_TARGET="$target" AIRLIFT_LOCAL="$HOME/.claude/settings.json" python3 - <<'PY' 2>/dev/null
import json, os

def load(p):
    try:
        with open(p) as fh:
            return json.load(fh)
    except Exception:
        return None

def shape_of(doc):
    # Inspect any existing hook event group for the assumed shape:
    #   { "<Event>": [ { "matcher": "...", "hooks": [ {type,command}, ... ] } ] }
    if not isinstance(doc, dict):
        return "absent"
    hooks = doc.get("hooks")
    if not isinstance(hooks, dict) or not hooks:
        return "absent"
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for g in groups:
            if not isinstance(g, dict):
                continue
            has_group_matcher = "matcher" in g
            inner = g.get("hooks")
            has_inner_array = isinstance(inner, list)
            if has_group_matcher and has_inner_array:
                return "group-matcher"  # assumed shape confirmed
            if has_inner_array and not has_group_matcher:
                # hooks nested but matcher absent at group level; ambiguous
                return "group-matcher"  # still group-level grouping, matcher optional
            if not has_inner_array and ("command" in g or "type" in g):
                return "flat"  # per-hook entries directly in the event list
    return "absent"

target_shape = shape_of(load(os.environ.get("AIRLIFT_TARGET", "")))
local_shape = shape_of(load(os.environ.get("AIRLIFT_LOCAL", "")))

# Emit machine-readable result for the shell to consume.
print("TARGET_SHAPE=%s" % target_shape)
print("LOCAL_SHAPE=%s" % local_shape)
PY
}

# ---------------------------------------------------------------------------
# wire
# ---------------------------------------------------------------------------
airlift_settings_wire() {
  local settings="${1:-$HOME/.claude/settings.json}"

  local statusline_path hook_path
  statusline_path="$(airlift_settings_resolve_sibling airlift-statusline.sh)"
  if [ -z "$statusline_path" ]; then
    echo "ERROR: cannot resolve airlift-statusline.sh" >&2
    return 1
  fi
  hook_path="$(airlift_settings_resolve_sibling airlift-hook-flush.sh)"
  if [ -z "$hook_path" ]; then
    echo "ERROR: cannot resolve airlift-hook-flush.sh" >&2
    return 1
  fi

  local dir
  dir="$(airlift_settings_dir)"
  mkdir -p "$dir" 2>/dev/null || true
  local backup="${dir}/settings-backup.json"

  # ADVERSARY: schema check before writing the StopFailure hook.
  local schema_out target_shape local_shape
  schema_out="$(airlift_settings_schema_check "$settings")"
  target_shape="$(printf '%s\n' "$schema_out" | grep '^TARGET_SHAPE=' | head -1 | cut -d= -f2)"
  local_shape="$(printf '%s\n' "$schema_out" | grep '^LOCAL_SHAPE=' | head -1 | cut -d= -f2)"
  [ -n "$target_shape" ] || target_shape="absent"
  [ -n "$local_shape" ] || local_shape="absent"
  # If either inspected file uses a FLAT (per-hook matcher) schema, the assumed
  # group-matcher shape may be wrong. Surface it; proceed with the documented
  # Claude Code group-matcher shape (the verified installed schema), but tell the
  # user so they can audit.
  if [ "$target_shape" = "flat" ] || [ "$local_shape" = "flat" ]; then
    echo "airlift NOTE (ambiguity): an inspected settings.json uses a FLAT hook schema (matcher per-hook) rather than the assumed group-matcher shape. Proceeding with the group-matcher shape documented for Claude Code StopFailure. Audit the result if your harness differs." >&2
  fi

  AIRLIFT_SETTINGS="$settings" \
  AIRLIFT_BACKUP="$backup" \
  AIRLIFT_STATUSLINE_PATH="$statusline_path" \
  AIRLIFT_HOOK_PATH="$hook_path" \
  AIRLIFT_SENTINEL="$AIRLIFT_SENTINEL" \
  python3 - <<'PY'
import json, os, sys, tempfile

settings_path = os.environ["AIRLIFT_SETTINGS"]
backup_path = os.environ["AIRLIFT_BACKUP"]
statusline_path = os.environ["AIRLIFT_STATUSLINE_PATH"]
hook_path = os.environ["AIRLIFT_HOOK_PATH"]
sentinel = os.environ["AIRLIFT_SENTINEL"]

def load(p):
    try:
        with open(p) as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except Exception as e:
        sys.stderr.write("ERROR: cannot parse %s: %s\n" % (p, e))
        sys.exit(1)

doc = load(settings_path)
if not isinstance(doc, dict):
    sys.stderr.write("ERROR: %s is not a JSON object\n" % settings_path)
    sys.exit(1)

# The statusLine command we want to install. The wrapper chains the prior
# command via the sidecar backup, so we only need to point at our script.
desired_status_cmd = "bash %s" % statusline_path

# --- statusLine: back up the ORIGINAL once, then install the airlift chainer.
existing_status = doc.get("statusLine")
already_wired = (
    isinstance(existing_status, dict)
    and isinstance(existing_status.get("command"), str)
    and sentinel in existing_status.get("command", "")
    and statusline_path in existing_status.get("command", "")
)

# Sidecar backup: write ONLY on first wire (never overwrite -- that would lose
# the true original). The backup stores the prior statusLine object verbatim.
if not os.path.exists(backup_path):
    backup_obj = {"statusLine": existing_status if existing_status is not None else None}
    btmp = backup_path + ".tmp"
    with open(btmp, "w") as fh:
        json.dump(backup_obj, fh, indent=2)
        fh.write("\n")
    os.replace(btmp, backup_path)

if not already_wired:
    new_status = {}
    # Preserve type and padding from the prior statusLine when present.
    if isinstance(existing_status, dict):
        if "type" in existing_status:
            new_status["type"] = existing_status["type"]
        if "padding" in existing_status:
            new_status["padding"] = existing_status["padding"]
    new_status.setdefault("type", "command")
    new_status["command"] = desired_status_cmd
    doc["statusLine"] = new_status

# --- StopFailure hook (group-matcher shape): check-before-add via sentinel.
hooks = doc.get("hooks")
if not isinstance(hooks, dict):
    hooks = {}
sf = hooks.get("StopFailure")
if not isinstance(sf, list):
    sf = []

def group_contains_sentinel(group):
    if not isinstance(group, dict):
        return False
    for h in (group.get("hooks") or []):
        if isinstance(h, dict) and sentinel in (h.get("command") or ""):
            return True
    return False

has_airlift = any(group_contains_sentinel(g) for g in sf)

if not has_airlift:
    sf.append({
        "matcher": "rate_limit|overloaded|billing_error",
        "hooks": [
            {"type": "command", "command": "bash %s" % hook_path},
        ],
    })

hooks["StopFailure"] = sf
doc["hooks"] = hooks

# Atomic write: sibling temp then os.replace.
d = os.path.dirname(os.path.abspath(settings_path)) or "."
fd, tmp = tempfile.mkstemp(prefix=".airlift-settings.", dir=d)
try:
    with os.fdopen(fd, "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, settings_path)
except Exception:
    try:
        os.unlink(tmp)
    except Exception:
        pass
    raise
PY
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "ERROR: wire failed (python3 edit returned $rc)" >&2
    return "$rc"
  fi
  echo "airlift: wired statusLine + StopFailure hook into ${settings} (backup: ${backup}); existing statusLine preserved via chaining."
  return 0
}

# ---------------------------------------------------------------------------
# unwire
# ---------------------------------------------------------------------------
airlift_settings_unwire() {
  local settings="${1:-$HOME/.claude/settings.json}"
  local dir
  dir="$(airlift_settings_dir)"
  local backup="${dir}/settings-backup.json"

  AIRLIFT_SETTINGS="$settings" \
  AIRLIFT_BACKUP="$backup" \
  AIRLIFT_SENTINEL="$AIRLIFT_SENTINEL" \
  python3 - <<'PY'
import json, os, sys, tempfile

settings_path = os.environ["AIRLIFT_SETTINGS"]
backup_path = os.environ["AIRLIFT_BACKUP"]
sentinel = os.environ["AIRLIFT_SENTINEL"]

try:
    with open(settings_path) as fh:
        doc = json.load(fh)
except FileNotFoundError:
    # Nothing to unwire.
    sys.exit(0)
except Exception as e:
    sys.stderr.write("ERROR: cannot parse %s: %s\n" % (settings_path, e))
    sys.exit(1)

if not isinstance(doc, dict):
    sys.exit(0)

changed = False

# --- Restore statusLine byte-exact from the sidecar backup.
backup = None
if os.path.exists(backup_path):
    try:
        with open(backup_path) as fh:
            backup = json.load(fh)
    except Exception:
        backup = None

if isinstance(backup, dict) and "statusLine" in backup:
    orig = backup["statusLine"]
    cur = doc.get("statusLine")
    # Only restore if the current statusLine is the airlift one (contains the
    # sentinel) -- a second unwire (already restored) is a no-op.
    cur_is_airlift = (
        isinstance(cur, dict)
        and isinstance(cur.get("command"), str)
        and sentinel in cur.get("command", "")
    )
    if cur_is_airlift:
        if orig is None:
            if "statusLine" in doc:
                del doc["statusLine"]
                changed = True
        else:
            if doc.get("statusLine") != orig:
                doc["statusLine"] = orig
                changed = True

# --- Remove all StopFailure hook groups whose inner hooks reference the sentinel.
hooks = doc.get("hooks")
if isinstance(hooks, dict) and isinstance(hooks.get("StopFailure"), list):
    def group_has_sentinel(group):
        if not isinstance(group, dict):
            return False
        for h in (group.get("hooks") or []):
            if isinstance(h, dict) and sentinel in (h.get("command") or ""):
                return True
        return False
    before = hooks["StopFailure"]
    after = [g for g in before if not group_has_sentinel(g)]
    if len(after) != len(before):
        changed = True
    if after:
        hooks["StopFailure"] = after
    else:
        del hooks["StopFailure"]
    # Drop an empty hooks object only if WE emptied it and nothing else remains.
    if not hooks:
        del doc["hooks"]
    else:
        doc["hooks"] = hooks

if not changed:
    # Idempotent no-op: do not rewrite the file.
    sys.exit(0)

d = os.path.dirname(os.path.abspath(settings_path)) or "."
fd, tmp = tempfile.mkstemp(prefix=".airlift-settings.", dir=d)
try:
    with os.fdopen(fd, "w") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, settings_path)
except Exception:
    try:
        os.unlink(tmp)
    except Exception:
        pass
    raise
PY
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "ERROR: unwire failed (python3 edit returned $rc)" >&2
    return "$rc"
  fi
  echo "airlift: unwired ${settings} (statusLine restored from ${backup}; airlift hooks removed)."
  return 0
}

# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------
airlift_settings_status() {
  local settings="${1:-$HOME/.claude/settings.json}"

  local ccusage_state="absent"
  if command -v ccusage >/dev/null 2>&1; then
    ccusage_state="detected"
  fi

  AIRLIFT_SETTINGS="$settings" \
  AIRLIFT_SENTINEL="$AIRLIFT_SENTINEL" \
  AIRLIFT_CCUSAGE="$ccusage_state" \
  python3 - <<'PY'
import json, os

settings_path = os.environ["AIRLIFT_SETTINGS"]
sentinel = os.environ["AIRLIFT_SENTINEL"]
ccusage_state = os.environ["AIRLIFT_CCUSAGE"]

wired_status = False
wired_hook = False
try:
    with open(settings_path) as fh:
        doc = json.load(fh)
    sl = doc.get("statusLine")
    if isinstance(sl, dict) and sentinel in (sl.get("command") or ""):
        wired_status = True
    hooks = doc.get("hooks") or {}
    for g in (hooks.get("StopFailure") or []):
        for h in (g.get("hooks") or []):
            if sentinel in (h.get("command") or ""):
                wired_hook = True
except Exception:
    pass

state = "wired" if (wired_status and wired_hook) else ("partially wired" if (wired_status or wired_hook) else "unwired")
print("airlift settings status (%s)" % settings_path)
print("  state:           %s" % state)
print("  statusLine:      %s" % ("airlift chainer installed" if wired_status else "not airlift"))
print("  StopFailure hook:%s" % (" airlift reactive flush installed" if wired_hook else " not installed"))
print("  ccusage:         %s" % ccusage_state)
print("  rate_limits note: the REAL five_hour.used_percentage is the primary signal,")
print("                    but it is only present on Pro/Max plans AFTER the first API")
print("                    response of a session, and may be absent otherwise. ccusage")
print("                    is a cost-based ESTIMATE of the 5-hour block, used only as a")
print("                    fallback when rate_limits is unavailable.")
PY
  return 0
}

# ---------------------------------------------------------------------------
# Dispatch + arg parse
# ---------------------------------------------------------------------------
airlift_settings_main() {
  local sub="${1:-}"
  if [ -n "$sub" ]; then shift; fi

  local settings=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --settings)
        if [ -z "${2:-}" ]; then echo "ERROR: --settings requires a path" >&2; return 2; fi
        settings="$2"; shift 2 ;;
      *)
        echo "ERROR: unknown option '$1'" >&2; return 2 ;;
    esac
  done
  [ -n "$settings" ] || settings="$HOME/.claude/settings.json"

  case "$sub" in
    wire)   airlift_settings_wire "$settings" ;;
    unwire) airlift_settings_unwire "$settings" ;;
    status) airlift_settings_status "$settings" ;;
    ""|-h|--help|help)
      cat >&2 <<'USAGE'
airlift-settings.sh -- idempotent settings.json auto-wire for airlift Tier-3

  wire   [--settings <path>]   Install the airlift chaining statusLine + StopFailure
                               hook. Backs up the ORIGINAL statusLine once. Idempotent.
  unwire [--settings <path>]   Restore the original statusLine + remove airlift hooks.
  status [--settings <path>]   Report wired/unwired + ccusage detection + signal notes.

  Default settings path: ~/.claude/settings.json
USAGE
      [ -z "$sub" ] && return 2 || return 0 ;;
    *)
      echo "ERROR: unknown subcommand '$sub' (expected: wire | unwire | status)" >&2
      return 2 ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  airlift_settings_main "$@"
fi
