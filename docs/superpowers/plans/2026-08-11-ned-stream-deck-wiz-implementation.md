# NED Stream Deck Wiz Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace six Mac-local Wiz Control Stream Deck commands with one validated Mac launcher that executes the matching scene on NED over SSH.

**Architecture:** Version the launcher and a narrowly scoped profile updater in `ned-ops`, install the launcher at `/Users/trav/.local/bin/ned-wiz`, and rewrite exactly six `shellCommand` values after a full profile backup. Elgato Key Light actions stay local and unchanged; only WiZ scene execution moves to NED.

**Tech Stack:** zsh, OpenSSH, Python 3 standard library, Elgato Stream Deck profile JSON, NED `uv` and Wiz Control.

## Global Constraints

- Preserve all non-Wiz Stream Deck actions, images, coordinates, titles, device IDs, Key Light settings, and profile metadata byte-for-data-model.
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
- Create: `/home/ned/ai/ned-ops/mac/__init__.py` — importable updater package for tests.
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

readonly scene="${1:-}"
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

- [ ] **Step 2: Validate syntax and rejection before installing**

```bash
/bin/zsh -n /home/ned/ai/ned-ops/mac/ned-wiz
/bin/zsh /home/ned/ai/ned-ops/mac/ned-wiz invalid-scene; test "$?" -eq 64
```

- [ ] **Step 3: Commit the launcher source**

```bash
cd /home/ned/ai/ned-ops
git add mac/ned-wiz
git commit -m "feat: add Mac launcher for NED Wiz scenes"
```

- [ ] **Step 4: Install it on the Mac**

```bash
mkdir -p /Users/trav/.local/bin
scp ned-plain:/home/ned/ai/ned-ops/mac/ned-wiz /Users/trav/.local/bin/ned-wiz
chmod 0755 /Users/trav/.local/bin/ned-wiz
/bin/zsh -n /Users/trav/.local/bin/ned-wiz
```

---

### Task 2: Build an exact six-action profile updater

**Files:**
- Create: `/home/ned/ai/ned-ops/mac/update_streamdeck.py`
- Create: `/home/ned/ai/ned-ops/mac/__init__.py`
- Create: `/home/ned/ai/ned-ops/tests/test_streamdeck_update.py`

**Interfaces:**
- Produces: `rewrite_manifest(document: dict) -> tuple[dict, list[str]]`.

- [ ] **Step 1: Write failing preservation and count tests**

```python
def test_rewrites_exact_six_commands(self):
    updated, scenes = rewrite_manifest(self.fixture)
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
    updated, _ = rewrite_manifest(self.fixture)
    self.assertEqual(collect_non_shell_actions(updated), before)
```

- [ ] **Step 2: Prove the tests fail**

```bash
cd /home/ned/ai/ned-ops
python3 -m unittest tests.test_streamdeck_update -v
```

Expected: import failure for `mac.update_streamdeck` until the module exists.

- [ ] **Step 3: Implement recursive exact matching**

The updater walks dictionaries and lists, selects objects whose `UUID` is
`com.thoughtasylum.macauto.runshell`, reads `Settings.shellCommand`, and maps
only commands ending in `python scenes.py <scene>` for the six allowlisted
scenes. It writes `/Users/trav/.local/bin/ned-wiz <scene>`, sorts the returned
scene list, and raises `RuntimeError` unless each approved scene appears exactly
once. JSON output uses `ensure_ascii=False` and compact separators to match the
existing one-line manifest.

```python
SCENES = {"video_night", "morning", "video_day", "evening", "writing", "away"}
UUID = "com.thoughtasylum.macauto.runshell"

def rewrite_manifest(document: dict) -> tuple[dict, list[str]]:
    updated = copy.deepcopy(document)
    changed: list[str] = []
    for item in walk_objects(updated):
        if item.get("UUID") != UUID:
            continue
        settings = item.get("Settings", {})
        command = settings.get("shellCommand", "")
        for scene in SCENES:
            if command.endswith(f"python scenes.py {scene}"):
                settings["shellCommand"] = f"/Users/trav/.local/bin/ned-wiz {scene}"
                changed.append(scene)
                break
    if sorted(changed) != sorted(SCENES):
        raise RuntimeError(f"expected six scenes, changed {sorted(changed)}")
    return updated, sorted(changed)
```

Its CLI accepts exactly one manifest path, parses JSON, calls
`rewrite_manifest()`, writes a sibling temporary file with mode 0600, flushes
and fsyncs it, then atomically replaces the manifest with `os.replace()`. It
prints only the six changed scene names.

- [ ] **Step 4: Run tests and commit**

```bash
cd /home/ned/ai/ned-ops
python3 -m unittest tests.test_streamdeck_update -v
git add mac/update_streamdeck.py tests/test_streamdeck_update.py
git commit -m "feat: add exact Stream Deck scene updater"
```

---

### Task 3: Back up and update the live Stream Deck profile

**Files:**
- Backup and manifest paths from the file map.

**Interfaces:**
- Consumes: tested updater and installed launcher.
- Produces: six NED-backed actions with all adjacent actions preserved.

- [ ] **Step 1: Quit Stream Deck so it cannot overwrite the profile during mutation**

```bash
/usr/bin/osascript -e 'tell application "Elgato Stream Deck" to quit'
```

Wait until the Stream Deck process exits.

- [ ] **Step 2: Back up the complete profile**

```bash
mkdir -p '/Users/trav/Documents/Stream Deck Backups'
test ! -e '/Users/trav/Documents/Stream Deck Backups/Atmosphere-20260811.sdProfile'
/usr/bin/ditto \
  '/Users/trav/Library/Application Support/com.elgato.StreamDeck/ProfilesV3/B22EB0C7-B569-4E1F-85A6-1555CE993C30.sdProfile' \
  '/Users/trav/Documents/Stream Deck Backups/Atmosphere-20260811.sdProfile'
```

- [ ] **Step 3: Run the tested updater against the exact manifest**

```bash
scp ned-plain:/home/ned/ai/ned-ops/mac/update_streamdeck.py /private/tmp/update_streamdeck.py
/usr/bin/python3 /private/tmp/update_streamdeck.py \
  '/Users/trav/Library/Application Support/com.elgato.StreamDeck/ProfilesV3/B22EB0C7-B569-4E1F-85A6-1555CE993C30.sdProfile/Profiles/A61C3F28-3C81-4824-8B42-23CAB335D6BF/manifest.json'
```

Expected: updater prints exactly the six sorted scene names.

- [ ] **Step 4: Validate the resulting JSON and command set**

```bash
jq empty '/Users/trav/Library/Application Support/com.elgato.StreamDeck/ProfilesV3/B22EB0C7-B569-4E1F-85A6-1555CE993C30.sdProfile/Profiles/A61C3F28-3C81-4824-8B42-23CAB335D6BF/manifest.json'
rg -o '/Users/trav/.local/bin/ned-wiz (video_night|morning|video_day|evening|writing|away)' '/Users/trav/Library/Application Support/com.elgato.StreamDeck/ProfilesV3/B22EB0C7-B569-4E1F-85A6-1555CE993C30.sdProfile/Profiles/A61C3F28-3C81-4824-8B42-23CAB335D6BF/manifest.json' | sort
```

Expected: six unique lines and no local `uv ... scenes.py` commands remain.

- [ ] **Step 5: Restart Stream Deck**

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
if pgrep -af '/Users/trav/Websites/ai/wiz-control.*scenes.py'; then exit 1; fi
ssh ned-plain 'pgrep -af "/home/ned/ai/wiz-control.*scenes.py" || true'
```

Instant scenes normally exit before inspection; the important result is that
no new Mac-local Wiz process appears and the physical lights changed.

- [ ] **Step 4: Report backup and rollback**

Report the backup path. Rollback consists of quitting Stream Deck, restoring
the backed-up `.sdProfile` with `ditto`, and reopening Stream Deck.
