# NED Stream Deck Wiz Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace six Mac-local Wiz Control Stream Deck commands with one validated Mac launcher that executes the matching scene on NED over SSH.

**Architecture:** Version the launcher and a narrowly scoped profile updater in `ned-ops`, install the launcher at `/Users/trav/.local/bin/ned-wiz`, and rewrite exactly six `shellCommand` values after a full profile backup. Elgato Key Light actions stay local and unchanged; only WiZ scene execution moves to NED.

**Tech Stack:** zsh, OpenSSH, Python 3 standard library, Elgato Stream Deck profile JSON, NED `uv` and Wiz Control.

## Global Constraints

- Preserve every non-target JSON field and value. Parsing may change serialized
  byte layout, so tests compare the parsed data model after removing only the
  six explicitly targeted `shellCommand` values.
- Back up the complete `.sdProfile` directory before modifying the manifest.
- Update exactly six Run Shell actions: `video_night`, `morning`, `video_day`, `evening`, `writing`, and `away`.
- Remove the erroneous literal `Command:` prefix from the writing action by replacing the entire command.
- The launcher accepts only the six approved scene names and uses SSH alias `ned-plain` with batch mode and a five-second connection timeout.
- Wiz Control runs directly through `/home/ned/.local/bin/uv`; it does not depend on Docker, T3, or a persistent HTTP service.
- Do not commit or clean either unborn Wiz Control repository as part of this work.

---

## File map

- Create: `/home/ned/ai/ned-ops/mac/ned-wiz` — versioned launcher source.
- Create: `/home/ned/ai/ned-ops/mac/update_streamdeck.py` — exact six-action updater.
- Create: `/home/ned/ai/ned-ops/tests/test_streamdeck_update.py` — mutation-count and preservation tests.
- Install: `/Users/trav/.local/bin/ned-wiz` — executable Mac launcher.
- Modify: `/Users/trav/Library/Application Support/com.elgato.StreamDeck/ProfilesV3/B22EB0C7-B569-4E1F-85A6-1555CE993C30.sdProfile/Profiles/A61C3F28-3C81-4824-8B42-23CAB335D6BF/manifest.json`.
- Backup: `/Users/trav/Documents/Stream Deck Backups/Atmosphere-20260811.sdProfile`.

---

### Task 1: Add and test the validated SSH launcher

**Files:**
- Create: `/home/ned/ai/ned-ops/mac/ned-wiz`

**Interfaces:**
- Consumes: one scene argument.
- Produces: remote invocation of `/home/ned/ai/wiz-control/scenes.py` as `ned`.

- [ ] **Step 1: Write the launcher**

```zsh
#!/bin/zsh
set -eu

if (( $# != 1 )); then
  print -u2 "usage: ned-wiz {video_night|morning|video_day|evening|writing|away}"
  exit 64
fi
readonly scene="$1"
case "$scene" in
  video_night|morning|video_day|evening|writing|away) ;;
  *)
    print -u2 "usage: ned-wiz {video_night|morning|video_day|evening|writing|away}"
    exit 64
    ;;
esac

exec /usr/bin/ssh \
  -o BatchMode=yes \
  -o ConnectTimeout=5 \
  ned-plain \
  /home/ned/.local/bin/uv run \
  --directory /home/ned/ai/wiz-control \
  python scenes.py "$scene"
```

- [ ] **Step 2: Commit the launcher source**

Commit the versioned source, then bind the reviewed commit, Git blob, and blob
SHA-256 before copying any bytes to the Mac:

```bash
cd /home/ned/ai/ned-ops
git add mac/ned-wiz
git commit -m "feat: add Mac launcher for NED Wiz scenes"
NED_WIZ_REVIEWED_COMMIT="$(git rev-parse HEAD)"
NED_WIZ_REVIEWED_BLOB="$(git rev-parse "$NED_WIZ_REVIEWED_COMMIT:mac/ned-wiz")"
NED_WIZ_REVIEWED_SHA256="$(git cat-file blob "$NED_WIZ_REVIEWED_BLOB" | sha256sum | awk '{print $1}')"
test -n "$NED_WIZ_REVIEWED_COMMIT"
test -n "$NED_WIZ_REVIEWED_BLOB"
test -n "$NED_WIZ_REVIEWED_SHA256"
printf '%s\n' \
  "reviewed_commit=$NED_WIZ_REVIEWED_COMMIT" \
  "launcher_blob=$NED_WIZ_REVIEWED_BLOB" \
  "launcher_sha256=$NED_WIZ_REVIEWED_SHA256"
```

Record those three non-secret values in the execution receipt. Later steps use
the immutable blob object, never `/home/ned/ai/ned-ops/mac/ned-wiz` from the
mutable worktree.

- [ ] **Step 3: Download once, validate, and install the exact launcher bytes**

NED stores the versioned launcher source but does not provide zsh. On the Mac,
materialize the reviewed Git blob once into a private staging directory. All
syntax checks and the installed launcher consume those exact mode-0600 bytes.
Replace the receipt placeholders below with the exact values recorded in Step 2;
do not resolve `HEAD` or read the mutable worktree in this step.

```bash
set -eu
umask 077
NED_WIZ_REVIEWED_COMMIT='<reviewed-commit-from-step-2>'
NED_WIZ_REVIEWED_BLOB='<launcher-blob-from-step-2>'
NED_WIZ_REVIEWED_SHA256='<launcher-sha256-from-step-2>'
case "$NED_WIZ_REVIEWED_COMMIT:$NED_WIZ_REVIEWED_BLOB:$NED_WIZ_REVIEWED_SHA256" in
  *[!0-9a-f:]*|'') printf '%s\n' 'invalid reviewed launcher identity' >&2; exit 1 ;;
esac
NED_WIZ_STAGE="$(mktemp -d /private/tmp/ned-wiz.XXXXXX)"
chmod 0700 "$NED_WIZ_STAGE"
trap 'rm -rf "$NED_WIZ_STAGE"' EXIT HUP INT TERM
NED_WIZ_SOURCE="$NED_WIZ_STAGE/ned-wiz"
ssh -o BatchMode=yes -o ConnectTimeout=5 ned-plain \
  "set -eu
   test \"\$(git -C /home/ned/ai/ned-ops rev-parse '$NED_WIZ_REVIEWED_COMMIT:mac/ned-wiz')\" = '$NED_WIZ_REVIEWED_BLOB'
   git -C /home/ned/ai/ned-ops cat-file blob '$NED_WIZ_REVIEWED_BLOB'" \
  > "$NED_WIZ_SOURCE"
chmod 0600 "$NED_WIZ_SOURCE"
test "$(stat -f '%Lp' "$NED_WIZ_SOURCE")" = 600
test "$NED_WIZ_REVIEWED_SHA256" = "$(/usr/bin/shasum -a 256 "$NED_WIZ_SOURCE" | awk '{print $1}')"
/bin/zsh -n "$NED_WIZ_SOURCE"
if /bin/zsh "$NED_WIZ_SOURCE"; then exit 1; else test "$?" -eq 64; fi
if /bin/zsh "$NED_WIZ_SOURCE" invalid-scene; then exit 1; else test "$?" -eq 64; fi
if /bin/zsh "$NED_WIZ_SOURCE" morning extra; then exit 1; else test "$?" -eq 64; fi
mkdir -p /Users/trav/.local/bin
NED_WIZ_TARGET=/Users/trav/.local/bin/ned-wiz
NED_WIZ_INSTALL="$(mktemp /Users/trav/.local/bin/.ned-wiz.install.XXXXXX)"
NED_WIZ_ROLLBACK=''
NED_WIZ_ORIGINAL_MODE=''
NED_WIZ_HAD_TARGET=0
NED_WIZ_REPLACED=0
rollback_launcher() {
  status=$?
  trap - EXIT HUP INT TERM
  rollback_status=0
  if test "$status" -ne 0 && test "$NED_WIZ_REPLACED" -eq 1; then
    if test "$NED_WIZ_HAD_TARGET" -eq 1; then
      /bin/mv -f "$NED_WIZ_ROLLBACK" "$NED_WIZ_TARGET" || rollback_status=$?
      if test "$rollback_status" -eq 0; then
        chmod "$NED_WIZ_ORIGINAL_MODE" "$NED_WIZ_TARGET" || rollback_status=$?
      fi
    else
      rm -f -- "$NED_WIZ_TARGET" || rollback_status=$?
    fi
  fi
  rm -f -- "$NED_WIZ_INSTALL" "$NED_WIZ_ROLLBACK"
  rm -rf -- "$NED_WIZ_STAGE"
  if test "$rollback_status" -ne 0; then
    printf '%s\n' 'launcher rollback failed' >&2
    exit "$rollback_status"
  fi
  exit "$status"
}
trap rollback_launcher EXIT HUP INT TERM
/bin/cp "$NED_WIZ_SOURCE" "$NED_WIZ_INSTALL"
chmod 0700 "$NED_WIZ_INSTALL"
test "$(stat -f '%Lp' "$NED_WIZ_INSTALL")" = 700
test "$NED_WIZ_REVIEWED_SHA256" = "$(/usr/bin/shasum -a 256 "$NED_WIZ_INSTALL" | awk '{print $1}')"
/bin/zsh -n "$NED_WIZ_INSTALL"
if test -e "$NED_WIZ_TARGET"; then
  test -f "$NED_WIZ_TARGET"
  test ! -L "$NED_WIZ_TARGET"
  NED_WIZ_ORIGINAL_MODE="$(stat -f '%Lp' "$NED_WIZ_TARGET")"
  NED_WIZ_ROLLBACK="$(mktemp /Users/trav/.local/bin/.ned-wiz.rollback.XXXXXX)"
  /bin/cp "$NED_WIZ_TARGET" "$NED_WIZ_ROLLBACK"
  chmod 0600 "$NED_WIZ_ROLLBACK"
  test "$(stat -f '%Lp' "$NED_WIZ_ROLLBACK")" = 600
  test -n "$(/usr/bin/shasum -a 256 "$NED_WIZ_ROLLBACK" | awk '{print $1}')"
  NED_WIZ_HAD_TARGET=1
fi
/bin/mv -f "$NED_WIZ_INSTALL" "$NED_WIZ_TARGET"
NED_WIZ_REPLACED=1
test "$(stat -f '%Lp' "$NED_WIZ_TARGET")" = 700
test "$NED_WIZ_REVIEWED_SHA256" = "$(/usr/bin/shasum -a 256 "$NED_WIZ_TARGET" | awk '{print $1}')"
/bin/zsh -n "$NED_WIZ_TARGET"
rm -f -- "$NED_WIZ_ROLLBACK"
trap - EXIT HUP INT TERM
rm -rf "$NED_WIZ_STAGE"
```

The install candidate and rollback copy are private siblings of the target, so
the rename is same-filesystem and atomic. Any failure after replacement restores
the exact prior bytes and mode; when no prior launcher existed, it removes the
failed new target. A rollback failure remains non-zero and explicit.

- [ ] **Step 4: Verify the installed launcher without downloading again**

```bash
/bin/zsh -n /Users/trav/.local/bin/ned-wiz
if /Users/trav/.local/bin/ned-wiz invalid-scene; then exit 1; else test "$?" -eq 64; fi
```

---

### Task 2: Build an exact six-action profile updater

**Files:**
- Create: `/home/ned/ai/ned-ops/mac/update_streamdeck.py`
- Create: `/home/ned/ai/ned-ops/tests/test_streamdeck_update.py`

**Interfaces:**
- Produces: `rewrite_manifest(backup: dict, document: dict) -> tuple[dict, list[str]]` and `verify_applied(backup: dict, document: dict) -> list[str]`.

- [ ] **Step 1: Create and audit the authoritative backup before deriving `COMMAND_MAP`**

Quit Stream Deck and use a timeout-bounded process gate so it cannot rewrite the
profile during the copy. Create the complete backup before inspecting or
deriving any old command value:

```bash
set -eu
/usr/bin/osascript -e 'tell application "Elgato Stream Deck" to quit'
STREAMDECK_WAITED=0
while /usr/bin/pgrep -x 'Stream Deck' >/dev/null 2>&1; do
  if test "$STREAMDECK_WAITED" -ge 30; then
    printf '%s\n' 'Stream Deck did not exit within 30 seconds' >&2
    exit 1
  fi
  /bin/sleep 1
  STREAMDECK_WAITED=$((STREAMDECK_WAITED + 1))
done
if /usr/bin/pgrep -x 'Stream Deck' >/dev/null 2>&1; then exit 1; fi
mkdir -p '/Users/trav/Documents/Stream Deck Backups'
test ! -e '/Users/trav/Documents/Stream Deck Backups/Atmosphere-20260811.sdProfile'
/usr/bin/ditto \
  '/Users/trav/Library/Application Support/com.elgato.StreamDeck/ProfilesV3/B22EB0C7-B569-4E1F-85A6-1555CE993C30.sdProfile' \
  '/Users/trav/Documents/Stream Deck Backups/Atmosphere-20260811.sdProfile'
```

Audit the six complete Run Shell command strings only from the backup manifest.
Assign each one to its intended scene and stop if the audit finds fewer or more
than six target actions, duplicate old commands, a command with authority
material, or any uncertainty about a scene. The backup is immutable evidence:
later steps must never derive mappings from the mutable live manifest. Reopen
Stream Deck after the audit if desired; Task 3 re-quiesces it and refuses to
mutate if its parsed state no longer matches the audited backup.

- [ ] **Step 2: Write failing preservation, transition, and resume tests**

```python
def test_rewrites_exact_six_commands(self):
    updated, scenes = rewrite_manifest(self.backup, self.fixture)
    self.assertEqual(scenes, [
        "away", "evening", "morning", "video_day", "video_night", "writing",
    ])
    commands = collect_shell_commands(updated)
    self.assertEqual(set(commands), {
        "/Users/trav/.local/bin/ned-wiz away",
        "/Users/trav/.local/bin/ned-wiz evening",
        "/Users/trav/.local/bin/ned-wiz morning",
        "/Users/trav/.local/bin/ned-wiz video_day",
        "/Users/trav/.local/bin/ned-wiz video_night",
        "/Users/trav/.local/bin/ned-wiz writing",
    })

def test_preserves_non_shell_actions(self):
    before = collect_non_shell_actions(self.fixture)
    updated, _ = rewrite_manifest(self.backup, self.fixture)
    self.assertEqual(collect_non_shell_actions(updated), before)

def test_preserves_decoy_with_matching_suffix(self):
    self.fixture["Actions"].append(decoy_run_shell_action(
        "python scenes.py morning",
    ))
    updated, _ = rewrite_manifest(self.backup, self.fixture)
    self.assertEqual(last_shell_command(updated), "python scenes.py morning")

def test_rejects_mixed_duplicate_or_unexpected_state(self):
    self.fixture = replace_one_target_with_new_command(self.fixture, "morning")
    with self.assertRaisesRegex(RuntimeError, "mixed|duplicate|unexpected"):
        rewrite_manifest(self.backup, self.fixture)

def test_verification_only_accepts_exact_already_applied_state(self):
    updated, _ = rewrite_manifest(self.backup, self.fixture)
    self.assertEqual(verify_applied(self.backup, updated), EXPECTED_SCENES)
    self.assertEqual(verify_applied(self.backup, updated), EXPECTED_SCENES)
```

- [ ] **Step 3: Prove the tests fail**

```bash
cd /home/ned/ai/ned-ops
python3 -m unittest tests.test_streamdeck_update -v
```

Expected: import failure for `mac.update_streamdeck` until the module exists.

- [ ] **Step 4: Implement recursive exact matching and a verification-only resume path**

Populate `COMMAND_MAP` only with the six audited complete command strings from
the backup, including the writing command's literal `Command:` prefix. The
updater walks dictionaries and lists, selects objects whose `UUID` is
`com.thoughtasylum.macauto.runshell`, and permits only the six exact
`Settings.shellCommand` substitutions to `/Users/trav/.local/bin/ned-wiz
<scene>`. It identifies the fields by their recursive paths, so a
suffix-equivalent decoy remains unchanged.

Implement `rewrite_manifest(backup, document)` and `verify_applied(backup,
document)`. Both compare parsed JSON, not serialized bytes. They must prove
that every field and action from the backup is unchanged except for exactly six
unique, path-matched old-to-new shell-command substitutions. `rewrite_manifest`
accepts only the all-original state and raises on a missing, duplicate, mixed,
or unexpected target state. `verify_applied` accepts only the all-new state,
performs no write, and raises on the same invalid states. JSON output uses
`ensure_ascii=False` and compact separators to match the existing one-line
manifest.

```python
UUID = "com.thoughtasylum.macauto.runshell"
COMMAND_MAP = {
    # Populate only from the audited backup before this source is committed.
    # old_complete_command: scene_name
}

def rewrite_manifest(backup: dict, document: dict) -> tuple[dict, list[str]]:
    assert_all_original(backup, document, COMMAND_MAP)
    updated = copy.deepcopy(document)
    changed: list[str] = []
    for item in walk_objects(updated):
        if item.get("UUID") != UUID:
            continue
        settings = item.get("Settings", {})
        scene = COMMAND_MAP.get(settings.get("shellCommand", ""))
        if scene is not None:
            settings["shellCommand"] = f"/Users/trav/.local/bin/ned-wiz {scene}"
            changed.append(scene)
    if sorted(changed) != sorted(COMMAND_MAP.values()):
        raise RuntimeError(f"expected six scenes, changed {sorted(changed)}")
    return updated, sorted(changed)
```

Its CLI accepts `--backup <backup-manifest>` and exactly one live manifest path.
It parses both files, calls `rewrite_manifest()`, verifies the resulting
transition against the backup, and creates both candidate and rollback files as
mode-0600 private siblings of the live manifest. It rejects symlinks, validates
the candidate JSON and semantic transition, records and rechecks its SHA-256 and
mode, flushes and fsyncs the file and containing directory, then atomically
replaces the live manifest with `os.replace()`. It immediately reopens the live
file, rechecks the candidate digest and `verify_applied()`, and removes the
rollback sibling only after both pass. Any failure after replacement atomically
restores the exact original bytes and mode, fsyncs the directory, and exits
non-zero; rollback failure remains explicit. Before every write it rejects a
mixed, duplicate, missing, or unexpected state. On a safe resume where the live
manifest is already exactly applied, it performs no write and prints
`already-applied` plus the six sorted scene names. `--verify-only` accepts only
that already-applied state, performs no mutation, and prints `verified` plus
those same six names. Tests inject failures immediately before and after each
rename and prove either the all-original or exact all-new state survives, never a
mixed or missing manifest.

- [ ] **Step 5: Run tests and commit**

```bash
cd /home/ned/ai/ned-ops
python3 -m unittest tests.test_streamdeck_update -v
git add mac/update_streamdeck.py tests/test_streamdeck_update.py
git commit -m "feat: add exact Stream Deck scene updater"
git status --short
NED_STREAMDECK_REVIEWED_COMMIT="$(git rev-parse HEAD)"
NED_STREAMDECK_REVIEWED_BLOB="$(git rev-parse "$NED_STREAMDECK_REVIEWED_COMMIT:mac/update_streamdeck.py")"
NED_STREAMDECK_REVIEWED_SHA256="$(git cat-file blob "$NED_STREAMDECK_REVIEWED_BLOB" | sha256sum | awk '{print $1}')"
test -n "$NED_STREAMDECK_REVIEWED_COMMIT"
test -n "$NED_STREAMDECK_REVIEWED_BLOB"
test -n "$NED_STREAMDECK_REVIEWED_SHA256"
printf '%s\n' \
  "reviewed_commit=$NED_STREAMDECK_REVIEWED_COMMIT" \
  "updater_blob=$NED_STREAMDECK_REVIEWED_BLOB" \
  "updater_sha256=$NED_STREAMDECK_REVIEWED_SHA256"
```

Record those three non-secret values in the execution receipt. Task 3 consumes
that immutable Git blob rather than the mutable updater worktree path.

---

### Task 3: Back up and update the live Stream Deck profile

**Files:**
- Backup and manifest paths from the file map.

**Interfaces:**
- Consumes: tested updater and installed launcher.
- Produces: six NED-backed actions with all adjacent actions preserved.

- [ ] **Step 1: Quiesce Stream Deck and bind the live profile to the audited backup**

```bash
set -eu
/usr/bin/osascript -e 'tell application "Elgato Stream Deck" to quit'
STREAMDECK_WAITED=0
while /usr/bin/pgrep -x 'Stream Deck' >/dev/null 2>&1; do
  if test "$STREAMDECK_WAITED" -ge 30; then
    printf '%s\n' 'Stream Deck did not exit within 30 seconds' >&2
    exit 1
  fi
  /bin/sleep 1
  STREAMDECK_WAITED=$((STREAMDECK_WAITED + 1))
done
if /usr/bin/pgrep -x 'Stream Deck' >/dev/null 2>&1; then exit 1; fi
```

The updater must compare the live parsed manifest to the backup and stop without
writing if any field/action has changed since the backup audit; create a new
backup and repeat the audit instead.

- [ ] **Step 2: Download once, validate, execute, and reverify the exact updater bytes**

```bash
set -eu
umask 077
NED_STREAMDECK_REVIEWED_COMMIT='<reviewed-commit-from-task-2-step-5>'
NED_STREAMDECK_REVIEWED_BLOB='<updater-blob-from-task-2-step-5>'
NED_STREAMDECK_REVIEWED_SHA256='<updater-sha256-from-task-2-step-5>'
case "$NED_STREAMDECK_REVIEWED_COMMIT:$NED_STREAMDECK_REVIEWED_BLOB:$NED_STREAMDECK_REVIEWED_SHA256" in
  *[!0-9a-f:]*|'') printf '%s\n' 'invalid reviewed updater identity' >&2; exit 1 ;;
esac
NED_STREAMDECK_STAGE="$(mktemp -d /private/tmp/update-streamdeck.XXXXXX)"
chmod 0700 "$NED_STREAMDECK_STAGE"
trap 'rm -rf "$NED_STREAMDECK_STAGE"' EXIT HUP INT TERM
NED_STREAMDECK_UPDATER="$NED_STREAMDECK_STAGE/update_streamdeck.py"
NED_STREAMDECK_BACKUP='/Users/trav/Documents/Stream Deck Backups/Atmosphere-20260811.sdProfile/Profiles/A61C3F28-3C81-4824-8B42-23CAB335D6BF/manifest.json'
NED_STREAMDECK_MANIFEST='/Users/trav/Library/Application Support/com.elgato.StreamDeck/ProfilesV3/B22EB0C7-B569-4E1F-85A6-1555CE993C30.sdProfile/Profiles/A61C3F28-3C81-4824-8B42-23CAB335D6BF/manifest.json'
ssh -o BatchMode=yes -o ConnectTimeout=5 ned-plain \
  "set -eu
   test \"\$(git -C /home/ned/ai/ned-ops rev-parse '$NED_STREAMDECK_REVIEWED_COMMIT:mac/update_streamdeck.py')\" = '$NED_STREAMDECK_REVIEWED_BLOB'
   git -C /home/ned/ai/ned-ops cat-file blob '$NED_STREAMDECK_REVIEWED_BLOB'" \
  > "$NED_STREAMDECK_UPDATER"
chmod 0600 "$NED_STREAMDECK_UPDATER"
test "$(stat -f '%Lp' "$NED_STREAMDECK_UPDATER")" = 600
test "$NED_STREAMDECK_REVIEWED_SHA256" = "$(/usr/bin/shasum -a 256 "$NED_STREAMDECK_UPDATER" | awk '{print $1}')"
/usr/bin/python3 -m py_compile "$NED_STREAMDECK_UPDATER"
/usr/bin/python3 "$NED_STREAMDECK_UPDATER" --backup "$NED_STREAMDECK_BACKUP" "$NED_STREAMDECK_MANIFEST"
test "$NED_STREAMDECK_REVIEWED_SHA256" = "$(/usr/bin/shasum -a 256 "$NED_STREAMDECK_UPDATER" | awk '{print $1}')"
/usr/bin/python3 "$NED_STREAMDECK_UPDATER" --backup "$NED_STREAMDECK_BACKUP" --verify-only "$NED_STREAMDECK_MANIFEST"
trap - EXIT HUP INT TERM
rm -rf "$NED_STREAMDECK_STAGE"
```

Expected: the first invocation prints either `updated` or `already-applied` and
the six sorted scene names. The second prints `verified` and the same six names;
it is the safe, non-mutating resume/verification path.

- [ ] **Step 3: Validate the resulting JSON and retained command set**

```bash
jq empty '/Users/trav/Library/Application Support/com.elgato.StreamDeck/ProfilesV3/B22EB0C7-B569-4E1F-85A6-1555CE993C30.sdProfile/Profiles/A61C3F28-3C81-4824-8B42-23CAB335D6BF/manifest.json'
```

The updater's `--verify-only` result is the authoritative semantic check: it
proves exactly six unique allowed substitutions and preservation of every other
parsed field/action. `jq` is only a syntax check; do not substitute textual
search output for the transition proof.

- [ ] **Step 4: Restart Stream Deck**

```bash
/usr/bin/open -a 'Elgato Stream Deck'
```

---

### Task 4: Verify all six physical actions

**Files:**
- No changes unless a verified mapping defect is found.

- [ ] **Step 1: Verify NED reachability without changing lights**

```bash
ssh -o BatchMode=yes -o ConnectTimeout=5 ned-plain 'test -x /home/ned/.local/bin/uv && test -f /home/ned/ai/wiz-control/scenes.py'
```

- [ ] **Step 2: Press each scene action once**

Press `Morning`, `Day meet`, `Night meet`, `Evening`, `Writing`, and `Away`,
allowing each remote command to finish before the next. Confirm the WiZ scene
changes and that the existing Elgato Key Light actions still execute in their
original multi-actions.

- [ ] **Step 3: Verify no Mac-local Wiz Python process remains**

```bash
set -eu
MAC_WIZ_PIDS="$(/usr/bin/pgrep -f '/Users/trav/Websites/ai/wiz-control.*scenes[.]py' || true)"
if test -n "$MAC_WIZ_PIDS"; then
  for pid in $MAC_WIZ_PIDS; do
    /bin/ps -p "$pid" -o pid=,comm=
  done | /usr/bin/sed -n '1,20p'
  exit 1
fi
printf '%s\n' 'mac_local_wiz_process=false'
ssh -o BatchMode=yes -o ConnectTimeout=5 ned-plain '
  pids="$(pgrep -f "/home/ned/ai/wiz-control.*scenes[.]py" || true)"
  if test -n "$pids"; then
    printf "%s\n" "ned_wiz_process_active=true"
  else
    printf "%s\n" "ned_wiz_process_active=false"
  fi'
```

Instant scenes normally exit before inspection; the important result is that
no new Mac-local Wiz process appears and the physical lights changed. The Mac
predicate uses the macOS-supported `pgrep -f`, then prints at most 20 matching
PID/process-name rows and never unrelated arguments. The NED check emits only a
boolean and never process arguments or environment values.

- [ ] **Step 4: Report backup and rollback**

Report the backup path. Rollback consists of quitting Stream Deck, restoring
the backed-up `.sdProfile` with `ditto`, and reopening Stream Deck.
