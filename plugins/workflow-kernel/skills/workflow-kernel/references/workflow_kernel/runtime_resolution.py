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
import stat
import sys
from dataclasses import dataclass
from pathlib import Path


KERNEL_VERSION_FLOOR = (0, 5, 0)
KERNEL_VERSION = (0, 11, 3)
_KERNEL_SEMVER = re.compile(
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
)
_PLUGIN_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,127}")
_ASSET_SEGMENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")


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


def semantic_version(text):
    """Parse one strict release semantic version, excluding mutable aliases."""
    if type(text) is not str:
        return None
    match = _KERNEL_SEMVER.fullmatch(text)
    return tuple(int(part) for part in match.groups()) if match is not None else None


@dataclass(frozen=True, slots=True)
class PluginBundle:
    """One coherent installed-plugin root and its durable selection receipt."""

    root: Path
    cache_class: str
    version: str
    reason: str

    def to_dict(self):
        return {
            "schema_version": 1,
            "selected_root": (
                f"~/.{self.cache_class}/plugins/cache/depot/"
                f"{self.root.parent.name}/{self.root.name}"
            ),
            "cache_class": self.cache_class,
            "version": self.version,
            "reason": self.reason,
        }


def _asset_path(root, relative, *, executable=False):
    if type(relative) is not str or not relative or "\\" in relative:
        return None
    path = Path(relative)
    if (
        path.is_absolute()
        or any(not _ASSET_SEGMENT.fullmatch(part) for part in path.parts)
        or any(part in {".", ".."} for part in path.parts)
    ):
        return None
    try:
        resolved = (root / path).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None
    try:
        mode = resolved.stat().st_mode
    except OSError:
        return None
    if (
        not stat.S_ISREG(mode)
        or not resolved.is_relative_to(root)
        or any(
            (root / Path(*path.parts[:index])).is_symlink()
            for index in range(1, len(path.parts) + 1)
        )
        or mode & (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH) == 0
        or not os.access(resolved, os.R_OK)
        or executable and (
            mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) == 0
            or not os.access(resolved, os.X_OK)
        )
    ):
        return None
    return resolved


def _plugin_bundle_candidate(root, cache_boundary, plugin_name, version,
                             cache_class, required_assets,
                             required_executables):
    try:
        if root.is_symlink():
            return None
        resolved = root.resolve(strict=True)
        boundary = cache_boundary.resolve(strict=True)
        if not resolved.is_dir() or not resolved.is_relative_to(boundary):
            return None
        marker = ".claude-plugin" if cache_class == "claude" else ".codex-plugin"
        manifest_path = resolved / marker / "plugin.json"
        if manifest_path.is_symlink():
            return None
        manifest = manifest_path.resolve(strict=True)
        if not manifest.is_file() or not manifest.is_relative_to(resolved):
            return None
        document = json.loads(manifest.read_text(encoding="utf-8"))
        if (
            type(document) is not dict
            or document.get("name") != plugin_name
            or document.get("version") != version
        ):
            return None
        if any(_asset_path(resolved, asset) is None for asset in required_assets):
            return None
        if any(
            _asset_path(resolved, asset, executable=True) is None
            for asset in required_executables
        ):
            return None
        return resolved
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return None


def resolve_plugin_bundle(plugin_name, required_assets=(), *, home=None,
                          active_host=None, minimum_version=None,
                          required_executables=()):
    """Select one highest compatible complete bundle across Claude/Codex caches.

    Compatibility is same-major at or above ``minimum_version`` when supplied.
    The active host affects only an equal-version tie.
    """
    if type(plugin_name) is not str or _PLUGIN_NAME.fullmatch(plugin_name) is None:
        raise ValueError("invalid plugin name")
    if (
        type(required_assets) not in {tuple, list}
        or type(required_executables) not in {tuple, list}
        or not required_assets and not required_executables
    ):
        raise ValueError("required assets are missing")
    if active_host not in {None, "claude", "codex"}:
        raise ValueError("invalid active host")
    floor = semantic_version(minimum_version) if minimum_version is not None else None
    if minimum_version is not None and floor is None:
        raise ValueError("invalid minimum version")
    home = (
        Path(pwd.getpwuid(os.getuid()).pw_dir)
        if home is None else Path(home)
    )
    candidates = []
    for cache_class in ("claude", "codex"):
        cache = (
            home / f".{cache_class}" / "plugins" / "cache" / "depot"
            / plugin_name
        )
        if not cache.is_dir():
            continue
        for entry in cache.iterdir():
            version = semantic_version(entry.name)
            if version is None or (
                floor is not None and (version[0] != floor[0] or version < floor)
            ):
                continue
            root = _plugin_bundle_candidate(
                entry, cache, plugin_name, entry.name, cache_class,
                required_assets, required_executables,
            )
            if root is not None:
                candidates.append((version, cache_class, root, entry.name))
    if not candidates:
        raise FileNotFoundError("compatible complete plugin bundle unavailable")
    highest = max(item[0] for item in candidates)
    equal = [item for item in candidates if item[0] == highest]
    equal.sort(key=lambda item: (
        0 if item[1] == active_host else 1,
        0 if item[1] == "claude" else 1,
        str(item[2]),
    ))
    _parsed, cache_class, root, version = equal[0]
    reason = (
        "active_host_equal_version_tiebreak"
        if len(equal) > 1 and active_host is not None
        else "highest_compatible_semver"
    )
    return PluginBundle(root, cache_class, version, reason)


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
