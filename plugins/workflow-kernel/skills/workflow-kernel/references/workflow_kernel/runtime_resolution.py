"""Side-effect-free workflow-kernel runtime candidate resolution.

This module is the single owner of manifest, semantic-version, and realpath
trust policy.  It intentionally imports only the Python standard library so
the isolated shell launcher can execute this trusted copy before probing any
candidate runtime code.
"""

from __future__ import annotations

import json
import os
import pwd
import re
import sys
from pathlib import Path


KERNEL_VERSION_FLOOR = (0, 1, 0)
_KERNEL_SEMVER = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
)


def compatible_kernel_version(text):
    """Return the parsed compatible semver tuple, otherwise ``None``."""
    if type(text) is not str:
        return None
    match = _KERNEL_SEMVER.fullmatch(text)
    if match is None:
        return None
    version = tuple(int(part) for part in match.groups())
    if version[0] != KERNEL_VERSION_FLOOR[0] or version < KERNEL_VERSION_FLOOR:
        return None
    return version


def _contained(path: Path, boundary: Path) -> bool:
    try:
        return path.resolve(strict=True).is_relative_to(boundary.resolve(strict=True))
    except (OSError, RuntimeError, ValueError):
        return False


def _manifest_document(plugin_root: Path):
    for marker in (".claude-plugin", ".codex-plugin"):
        candidate = plugin_root / marker / "plugin.json"
        try:
            resolved = candidate.resolve(strict=True)
            if not resolved.is_file() or not _contained(resolved, plugin_root):
                continue
            document = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            continue
        if type(document) is dict:
            return document
    return None


def _validated_references(plugin_root, boundary, path_version):
    try:
        root = Path(plugin_root).resolve(strict=True)
        boundary = Path(boundary).resolve(strict=True)
        if not root.is_dir() or not root.is_relative_to(boundary):
            return None
        document = _manifest_document(root)
        if document is None or document.get("name") != "workflow-kernel":
            return None
        declared = compatible_kernel_version(document.get("version"))
        if declared is None or path_version is not None and declared != path_version:
            return None
        references = (root / "skills" / "workflow-kernel" / "references").resolve(
            strict=True
        )
        package = (references / "workflow_kernel").resolve(strict=True)
        initializer_path = package / "__init__.py"
        initializer = (
            initializer_path.resolve(strict=True)
            if initializer_path.exists() or initializer_path.is_symlink()
            else None
        )
        entrypoint = (package / "__main__.py").resolve(strict=True)
        if not (
            references.is_dir()
            and package.is_dir()
            and (initializer is None or initializer.is_file())
            and entrypoint.is_file()
            and references.is_relative_to(root)
            and package.is_relative_to(root)
            and (initializer is None or initializer.is_relative_to(root))
            and entrypoint.is_relative_to(root)
            and not any(path.is_symlink() for path in package.rglob("*"))
        ):
            return None
        return references
    except (OSError, RuntimeError, ValueError):
        return None


def workflow_kernel_runtime_candidates(canonical_plugin_root, *, home=None):
    """Return validated candidates in deterministic preference order."""
    source = Path(canonical_plugin_root).resolve(strict=True)
    if not source.is_dir():
        raise ValueError("invalid canonical plugin root")
    roots = []
    if source.parent.name == "plugins":
        depot = source.parent.parent.resolve(strict=True)
        lexical_depot = Path(os.path.abspath(str(canonical_plugin_root))).parent.parent
        roots.append((lexical_depot / "plugins" / "workflow-kernel", depot, None))
        if home is None:
            home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    else:
        provider = source.parent.parent.parent.parent.parent
        if not (
            source.parent.name == "workflow-kernel"
            and source.parent.parent.name == "depot"
            and source.parent.parent.parent.name == "cache"
            and source.parent.parent.parent.parent.name == "plugins"
            and provider.name in {".claude", ".codex"}
        ):
            raise ValueError("invalid canonical plugin root")
        if home is None:
            home = provider.parent
    home = Path(home)
    for cache_name in (".claude", ".codex"):
        cache = home / cache_name / "plugins" / "cache" / "depot" / "workflow-kernel"
        if not cache.is_dir():
            continue
        candidates = []
        for candidate in cache.iterdir():
            version = compatible_kernel_version(candidate.name)
            if version is not None:
                candidates.append((version, candidate))
        roots.extend(
            (candidate, cache.resolve(strict=True), version)
            for version, candidate in sorted(candidates, reverse=True)
        )
    resolved = []
    for candidate, boundary, path_version in roots:
        references = _validated_references(candidate, boundary, path_version)
        if references is not None and references not in resolved:
            resolved.append(references)
    return tuple(resolved)


def resolve_workflow_kernel_runtime(canonical_plugin_root, *, home=None):
    candidates = workflow_kernel_runtime_candidates(canonical_plugin_root, home=home)
    if not candidates:
        raise FileNotFoundError("compatible workflow-kernel runtime unavailable")
    return candidates[0]


def _main(argv):
    if len(argv) != 2 or argv[0] != "--candidates":
        return 2
    try:
        candidates = workflow_kernel_runtime_candidates(argv[1])
    except (OSError, RuntimeError, ValueError):
        return 1
    for candidate in candidates:
        print(candidate)
    return 0 if candidates else 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
