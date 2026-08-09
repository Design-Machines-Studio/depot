---
name: plugin-cache-sync
description: Use when depot plugin updates do not show up -- Claude Desktop or the CLI reports plugins are "up to date" but versions look stale, a cache needs a manual pull, or the Notion manual page needs syncing after a plugin version bump. Covers the three independent marketplace clones (CLI/VSCode, Desktop Cowork, Codex) and the Notion manual update procedure.
---

# Plugin Cache Sync

Depot plugin distribution has more than one cache, and they update independently.
When a version bump does not appear, the problem is almost always a stale clone,
not a bad manifest.

## Troubleshooting Update Failures

If Claude Desktop says plugins are "up to date" but versions look stale:

1. **Check the cached marketplace clone:** `cd ~/.claude/plugins/marketplaces/depot && git log --oneline -1` -- if it's behind `origin/main`, the auto-update `git pull` failed
2. **Manually pull:** `cd ~/.claude/plugins/marketplaces/depot && git pull origin main`
3. **Update individual plugins:** `claude plugin update <plugin-name>@depot`
4. **Check cache versions:** `ls ~/.claude/plugins/cache/depot/<plugin>/` shows which version directories exist

## CLI vs Desktop Cowork: Two Separate Plugin Systems

The CLI/VSCode and Desktop Cowork maintain **independent** plugin caches. Updating one does NOT update the other.

| System | Marketplace clone | Plugin cache |
|--------|------------------|--------------|
| CLI/VSCode | `~/.claude/plugins/marketplaces/depot/` | `~/.claude/plugins/cache/depot/` |
| Desktop Cowork | `~/Library/Application Support/Claude/local-agent-mode-sessions/<session>/<account>/cowork_plugins/marketplaces/depot/` | Same path but `/cache/depot/` |
| Codex | `~/.codex/.tmp/marketplaces/depot/` (see below -- NOT under `plugins/`) | `~/.codex/plugins/cache/depot/` |

To fix stale Desktop plugins, pull the Desktop's marketplace clone directly:

```shell
cd ~/Library/Application\ Support/Claude/local-agent-mode-sessions/*/*/cowork_plugins/marketplaces/depot && git pull origin main
```

Then restart Claude Desktop for it to detect the new versions.

### Codex does not work like the other two

Codex has no marketplace clone under `~/.codex/plugins/`. That directory holds only
`cache/`, an appserver, and ephemeral `marketplace-plugin-source-*` staging dirs.
Ask Codex where its snapshot actually lives rather than assuming a path:

```shell
codex plugin marketplace list
```

On this machine the depot root resolves to `~/.codex/.tmp/marketplaces/depot` -- under
`.tmp/`, not `plugins/`. It is a real git clone, so it can be pulled, but confirm the
root first because the path is Codex-managed and may move between versions.

Refreshing the snapshot does NOT update the cache. These are two steps:

```shell
codex plugin marketplace upgrade          # refresh snapshots; may prompt, so run it interactively
codex plugin add <plugin>@depot           # materialize the new version into the cache
```

If `upgrade` blocks on a prompt in an automated context, pull the resolved root directly
and then run `codex plugin add`, which is non-interactive:

```shell
cd "$(codex plugin marketplace list | awk '$1=="depot"{print $2}')" && git pull origin main
codex plugin add <plugin>@depot
```

Unlike the Claude cache, which accumulates version directories, **the Codex cache keeps
exactly one version per plugin** -- `codex plugin add` installs the new version and prunes
the old. A single directory there is normal, not evidence of a failed install. Confirm the
expected version landed:

```shell
ls ~/.codex/plugins/cache/depot/<plugin>/
```

Agent and skill resolvers throughout the depot check `~/.claude/plugins/cache/depot`
first and fall back to `~/.codex/plugins/cache/depot`. A stale Codex cache is therefore
invisible whenever the Claude cache happens to hold a usable copy. **The silent fallback
is the hazard, not the staleness** -- a Codex-hosted run can execute against plugin
assets several versions behind while every Claude-side check looks current. Verify both
caches whenever a version looks wrong, and after every release.

## Notion Manual Sync

The depot has a manual page in Notion that documents all plugins, versions, and capabilities:
**Notion page ID:** `31ed8793880881749475c5c36dd252df`

When a plugin update changes any of the following, update the Notion manual page using the Notion MCP:
- Plugin version number
- New or removed skills, agents, or reference files
- Changes to key capabilities or ecosystem integration
- Plugin count or total file counts

To update, fetch the page with `notion-fetch`, then use `notion-update-page` with `update_content` to modify the relevant plugin section. Keep the format consistent with the existing entries.
