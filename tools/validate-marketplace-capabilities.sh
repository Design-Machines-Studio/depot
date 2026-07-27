#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)

REPO_ROOT="$REPO_ROOT" python3 <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path


root = Path(os.environ["REPO_ROOT"])
failures: list[str] = []


def load(relative: str):
    with (root / relative).open() as handle:
        return json.load(handle)


def check(condition: bool, message: str) -> None:
    if condition:
        print(f"  OK    {message}")
    else:
        print(f"  FAIL  {message}")
        failures.append(message)


canonical = load("plugins/dm-review/.claude-plugin/plugin.json")
generated = load("plugins/dm-review/.codex-plugin/plugin.json")
marketplace = load(".claude-plugin/marketplace.json")
codex_marketplace = load(".agents/plugins/marketplace.json")

caps = canonical.get("capabilities", {})
expected_counts = {"skills": 3, "agents": 15, "commands": 6}
actual_counts = {
    key: len(caps.get(key, []))
    for key in ("skills", "agents", "commands")
}
check(actual_counts == expected_counts, "canonical dm-review counts are 3 skills, 15 agents, 6 commands")

entry = next(
    (item for item in marketplace.get("plugins", []) if item.get("name") == "dm-review"),
    None,
)
check(entry is not None, "canonical marketplace contains dm-review")
if entry is not None:
    summary_counts = {
        key: entry.get("capabilities_summary", {}).get(key)
        for key in ("skills", "agents", "commands")
    }
    check(summary_counts == actual_counts, "dm-review capabilities_summary matches canonical arrays")

quality_skill = next(
    (item for item in caps.get("skills", []) if item.get("id") == "quality-pulse"),
    None,
)
quality_command = next(
    (
        item
        for item in caps.get("commands", [])
        if item.get("id") == "dm-review-quality-pulse"
    ),
    None,
)
check(quality_skill is not None, "canonical dm-review registers quality-pulse skill")
check(quality_command is not None, "canonical dm-review registers dm-review-quality-pulse command")
if quality_skill is not None:
    check(
        quality_skill.get("description")
        == "Deterministic scheduled/local repository quality audit using trusted profiles and authoritative receipts",
        "quality-pulse canonical description is exact",
    )
    check(
        {
            "run the scheduled repository quality pulse",
            "audit repository quality using .dm-review/quality-pulse.json",
            "compare today's quality pulse with the last compatible baseline",
        }
        <= set(quality_skill.get("triggers", [])),
        "quality-pulse canonical triggers cover scheduled, profile, and trend use",
    )
if quality_command is not None:
    check(
        quality_command.get("argumentHint") == "[optional: --profile <path>]",
        "quality-pulse command preserves its profile argument hint",
    )

check(
    generated.get("capabilities") == caps,
    "generated dm-review manifest preserves canonical capability arrays",
)
check(
    (root / "plugins/dm-review/commands/dm-review-quality-pulse.md").is_file(),
    "canonical Claude quality-pulse command exists",
)
check(
    (root / "plugins/dm-review/skills/dm-review-quality-pulse/SKILL.md").is_file(),
    "generated Codex quality-pulse command-skill alias exists",
)

interface_tags = generated.get("interface", {}).get("capabilities")
check(
    isinstance(interface_tags, list)
    and len(interface_tags) <= 8
    and all(isinstance(item, str) and item for item in interface_tags),
    "generated dm-review interface capabilities are bounded to eight tags",
)
check(
    isinstance(interface_tags, list)
    and {"quality-pulse", "repository-audit"} <= set(interface_tags),
    "bounded generated interface retains quality-pulse discovery tags",
)

check(
    set(codex_marketplace) == {"name", "interface", "plugins"},
    "global Codex marketplace uses its actual top-level schema",
)
codex_entries = codex_marketplace.get("plugins", [])
canonical_names = [item.get("name") for item in marketplace.get("plugins", [])]
codex_names = [item.get("name") for item in codex_entries]
check(codex_names == canonical_names, "global Codex marketplace preserves canonical plugin order")
entry_shape_ok = all(
    isinstance(item, dict)
    and set(item) == {"name", "source", "policy", "category"}
    and set(item.get("source", {})) == {"source", "path"}
    and set(item.get("policy", {})) == {"installation", "authentication"}
    for item in codex_entries
)
check(entry_shape_ok, "global Codex marketplace entries satisfy only the generated entry schema")

if failures:
    print(f"FAIL  marketplace capability validation failed ({len(failures)} checks)")
    raise SystemExit(1)

print("PASS  marketplace capability and cross-platform discovery contracts are intact")
PY
