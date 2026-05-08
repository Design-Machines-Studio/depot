#!/usr/bin/env python3
"""
Generate Codex plugin manifests from the Claude marketplace manifests.

Claude remains the canonical source in this repo:
  - .claude-plugin/marketplace.json
  - plugins/*/.claude-plugin/plugin.json

This script writes the Codex adapter layer:
  - .agents/plugins/marketplace.json
  - plugins/*/.codex-plugin/plugin.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
CODEX_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGINS_DIR = REPO_ROOT / "plugins"

CATEGORY_BY_PLUGIN = {
    "accessibility-compliance": "Developer Tools",
    "assembly": "Developer Tools",
    "chef": "Lifestyle",
    "council": "Knowledge",
    "craft-developer": "Developer Tools",
    "deepseek": "Developer Tools",
    "design-machines": "Business",
    "design-practice": "Design",
    "dm-review": "Developer Tools",
    "gemini": "Developer Tools",
    "ghostwriter": "Writing",
    "live-wires": "Developer Tools",
    "ned": "Knowledge",
    "pipeline": "Developer Tools",
    "project-manager": "Productivity",
    "project-scaffolder": "Developer Tools",
    "the-local": "Developer Tools",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        return json.load(handle)


def dump_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def display_name(name: str) -> str:
    special = {
        "dm-review": "DM Review",
        "ned": "Ned",
    }
    return special.get(name, name.replace("-", " ").title())


def marketplace_tags(entry: dict[str, Any]) -> list[str]:
    summary = entry.get("capabilities_summary", {})
    return list(summary.get("tags", []))[:8]


def codex_plugin_manifest(
    claude_manifest: dict[str, Any],
    marketplace_entry: dict[str, Any],
    plugin_dir: Path,
) -> dict[str, Any]:
    name = claude_manifest["name"]
    description = claude_manifest.get("description", "")
    author = claude_manifest.get("author", {"name": "Design Machines"})

    manifest: dict[str, Any] = {
        "name": name,
        "version": claude_manifest.get("version", marketplace_entry.get("version", "0.0.0")),
        "description": description,
        "author": author,
    }

    for key in ("homepage", "repository", "license", "keywords"):
        if key in claude_manifest:
            manifest[key] = claude_manifest[key]

    if (plugin_dir / "skills").is_dir():
        manifest["skills"] = "./skills/"
    if (plugin_dir / "hooks" / "hooks.json").is_file():
        manifest["hooks"] = "./hooks/hooks.json"
    if (plugin_dir / ".mcp.json").is_file():
        manifest["mcpServers"] = "./.mcp.json"
    if (plugin_dir / ".app.json").is_file():
        manifest["apps"] = "./.app.json"

    # Preserve Agent Card metadata for discovery tools that can use it, even
    # though the Codex manifest only needs the component paths above.
    for key in ("capabilities", "pluginDependencies", "optionalPluginDependencies"):
        if key in claude_manifest:
            manifest[key] = claude_manifest[key]

    tags = marketplace_tags(marketplace_entry)
    manifest["interface"] = {
        "displayName": display_name(name),
        "shortDescription": description[:120],
        "longDescription": description,
        "developerName": author.get("name", "Design Machines") if isinstance(author, dict) else "Design Machines",
        "category": CATEGORY_BY_PLUGIN.get(name, "Productivity"),
        "capabilities": tags,
    }

    return manifest


def codex_marketplace(claude_marketplace: dict[str, Any]) -> dict[str, Any]:
    plugins = []
    for entry in claude_marketplace.get("plugins", []):
        name = entry["name"]
        plugins.append(
            {
                "name": name,
                "source": {
                    "source": "local",
                    "path": f"./plugins/{name}",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": CATEGORY_BY_PLUGIN.get(name, "Productivity"),
            }
        )

    return {
        "name": claude_marketplace.get("name", "depot"),
        "interface": {
            "displayName": "Design Machines Depot",
        },
        "plugins": plugins,
    }


def expected_files() -> dict[Path, str]:
    if not CLAUDE_MARKETPLACE.is_file():
        raise FileNotFoundError(f"Missing {CLAUDE_MARKETPLACE.relative_to(REPO_ROOT)}")

    claude_marketplace = load_json(CLAUDE_MARKETPLACE)
    files = {CODEX_MARKETPLACE: dump_json(codex_marketplace(claude_marketplace))}

    for entry in claude_marketplace.get("plugins", []):
        name = entry["name"]
        plugin_dir = PLUGINS_DIR / name
        claude_plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
        if not claude_plugin_json.is_file():
            raise FileNotFoundError(f"Missing {claude_plugin_json.relative_to(REPO_ROOT)}")
        codex_plugin_json = plugin_dir / ".codex-plugin" / "plugin.json"
        files[codex_plugin_json] = dump_json(
            codex_plugin_manifest(load_json(claude_plugin_json), entry, plugin_dir)
        )

    return files


def write_files(files: dict[Path, str]) -> None:
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        current = path.read_text() if path.exists() else None
        if current != content:
            path.write_text(content)
            print(f"wrote {path.relative_to(REPO_ROOT)}")


def check_files(files: dict[Path, str]) -> int:
    failures = []
    for path, expected in files.items():
        if not path.exists():
            failures.append(f"missing {path.relative_to(REPO_ROOT)}")
            continue
        current = path.read_text()
        if current != expected:
            failures.append(f"stale {path.relative_to(REPO_ROOT)}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print("FIX  run: ./tools/generate-codex-manifests.py")
        return 1

    print(f"OK    {len(files)} Codex manifest files match Claude source manifests")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify generated files are current")
    args = parser.parse_args()

    try:
        files = expected_files()
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1

    if args.check:
        return check_files(files)

    write_files(files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
