"""Canonical repository identity and workflow-kernel lease-root binding."""

from __future__ import annotations

import json
import os
import re
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path


_SCOPE_FILE = "repository-scope.json"
_SCOPE_ID = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class RepositoryScope:
    repo_root: Path
    lease_root: Path
    scope_id: str
    repo_device: int
    repo_inode: int
    lease_device: int
    lease_inode: int


def _git_marker(root: Path) -> Path | None:
    marker = root / ".git"
    try:
        info = marker.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(info.st_mode):
        raise ValueError("symlinked git boundary")
    if stat.S_ISDIR(info.st_mode):
        return marker.resolve(strict=True)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("invalid git boundary")
    raw = marker.read_text(encoding="utf-8")
    if len(raw) > 4096 or not raw.startswith("gitdir: ") or "\n" in raw.rstrip("\n"):
        raise ValueError("invalid gitdir file")
    target = Path(raw[8:].strip())
    if not target.is_absolute():
        target = root / target
    target = target.resolve(strict=True)
    if not target.is_dir():
        raise ValueError("invalid gitdir target")
    return target


def _nearest_repo(path: Path) -> tuple[Path, Path]:
    absolute = Path(os.path.abspath(path))
    start = absolute if absolute.is_dir() else absolute.parent
    candidate = start
    while True:
        marker = _git_marker(candidate)
        if marker is not None:
            repo = candidate
            break
        if candidate.parent == candidate:
            raise ValueError("state directory is outside a git repository")
        candidate = candidate.parent
    resolved_repo = repo.resolve(strict=True)
    resolved_start = start.resolve(strict=False)
    try:
        relative = absolute.relative_to(repo)
    except ValueError:
        raise ValueError("state directory escapes repository") from None
    cursor = repo
    for part in relative.parts:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            raise ValueError("symlinked state directory")
    real_candidate = resolved_start
    while True:
        real_marker = _git_marker(real_candidate)
        if real_marker is not None:
            break
        if real_candidate.parent == real_candidate:
            raise ValueError("resolved state directory is outside repository")
        real_candidate = real_candidate.parent
    if real_candidate != resolved_repo or real_marker != marker:
        raise ValueError("cross-repository state directory")
    return resolved_repo, marker


def _directory_identity(path: Path) -> tuple[int, int]:
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError("repository scope directory is invalid")
    return info.st_dev, info.st_ino


def _document(scope: RepositoryScope) -> dict[str, object]:
    return {
        "schema_version": 1,
        "scope_id": scope.scope_id,
        "repo_root": {
            "path": str(scope.repo_root),
            "device": scope.repo_device,
            "inode": scope.repo_inode,
        },
        "lease_root": {
            "path": str(scope.lease_root),
            "device": scope.lease_device,
            "inode": scope.lease_inode,
        },
    }


def _write_once(path: Path, value: dict[str, object]) -> None:
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        pending = encoded
        while pending:
            count = os.write(descriptor, pending)
            if count <= 0:
                raise OSError("scope write made no progress")
            pending = pending[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def repository_scope(state_dir, *, create: bool = False) -> RepositoryScope:
    repo_root, _git_dir = _nearest_repo(Path(state_dir))
    lease_root = repo_root / ".workflow-kernel"
    if create:
        lease_root.mkdir(mode=0o700, parents=False, exist_ok=True)
    if not lease_root.is_dir() or lease_root.is_symlink():
        raise ValueError("canonical lease root unavailable")
    repo_dev, repo_ino = _directory_identity(repo_root)
    lease_dev, lease_ino = _directory_identity(lease_root)
    path = lease_root / _SCOPE_FILE
    if create and not path.exists():
        candidate = RepositoryScope(
            repo_root, lease_root, secrets.token_hex(32),
            repo_dev, repo_ino, lease_dev, lease_ino,
        )
        try:
            _write_once(path, _document(candidate))
        except FileExistsError:
            pass
    if path.is_symlink() or not path.is_file():
        raise ValueError("repository scope identity unavailable")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("invalid repository scope identity") from None
    expected_keys = {"schema_version", "scope_id", "repo_root", "lease_root"}
    identity_keys = {"path", "device", "inode"}
    if (
        type(value) is not dict or set(value) != expected_keys
        or value.get("schema_version") != 1
        or _SCOPE_ID.fullmatch(value.get("scope_id", "")) is None
        or type(value.get("repo_root")) is not dict
        or type(value.get("lease_root")) is not dict
        or set(value["repo_root"]) != identity_keys
        or set(value["lease_root"]) != identity_keys
    ):
        raise ValueError("invalid repository scope identity")
    scope = RepositoryScope(
        repo_root, lease_root, value["scope_id"],
        repo_dev, repo_ino, lease_dev, lease_ino,
    )
    if value != _document(scope):
        raise ValueError("repository scope identity mismatch")
    return scope
