"""Canonical repository identity and workflow-kernel lease-root binding."""

from __future__ import annotations

import json
import os
import re
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path

from ._files import PinnedDirectory, UnsafeFileError


_SCOPE_FILE = "repository-scope.json"
_LEASE_DIRECTORY = ".workflow-kernel"
_SCOPE_ID = re.compile(r"[0-9a-f]{64}")
_MAX_SCOPE_BYTES = 64 * 1024
_MAX_GITDIR_BYTES = 4096


@dataclass(frozen=True)
class RepositoryScope:
    repo_root: Path
    lease_root: Path
    scope_id: str
    repo_device: int
    repo_inode: int
    lease_device: int
    lease_inode: int


def _read_all(descriptor: int, maximum: int) -> bytes:
    chunks = []
    total = 0
    while True:
        chunk = os.read(descriptor, min(8192, maximum + 1 - total))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > maximum:
            raise ValueError("durable file is too large")
        chunks.append(chunk)


def _git_marker(root: Path) -> tuple[Path, tuple[int, int]] | None:
    try:
        directory = PinnedDirectory.open(root)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except UnsafeFileError:
        raise ValueError("unsafe git boundary") from None
    try:
        try:
            entry = os.stat(".git", dir_fd=directory.descriptor, follow_symlinks=False)
        except FileNotFoundError:
            directory.revalidate()
            return None
        marker = root / ".git"
        if stat.S_ISLNK(entry.st_mode):
            raise ValueError("symlinked git boundary")
        if stat.S_ISDIR(entry.st_mode):
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(".git", flags, dir_fd=directory.descriptor)
            try:
                opened = os.fstat(descriptor)
                current = os.stat(".git", dir_fd=directory.descriptor, follow_symlinks=False)
                identity = (opened.st_dev, opened.st_ino)
                if (
                    not stat.S_ISDIR(opened.st_mode)
                    or not stat.S_ISDIR(current.st_mode)
                    or identity != (current.st_dev, current.st_ino)
                ):
                    raise ValueError("git boundary identity changed")
            finally:
                os.close(descriptor)
            directory.revalidate()
            return marker.resolve(strict=True), identity
        if not stat.S_ISREG(entry.st_mode):
            raise ValueError("invalid git boundary")
        descriptor = directory.open_regular(".git", os.O_RDONLY)
        try:
            directory.require_identity(descriptor, ".git")
            raw = _read_all(descriptor, _MAX_GITDIR_BYTES)
            directory.require_identity(descriptor, ".git")
        finally:
            os.close(descriptor)
        directory.revalidate()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("invalid gitdir file") from None
        if not text.startswith("gitdir: ") or "\n" in text.rstrip("\n"):
            raise ValueError("invalid gitdir file")
        target = Path(text[8:].strip())
        if not target.is_absolute():
            target = root / target
        target = target.resolve(strict=True)
        with PinnedDirectory.open(target) as git_directory:
            identity = git_directory.identity
            git_directory.revalidate()
        return target, identity
    except UnsafeFileError:
        raise ValueError("unsafe git boundary") from None
    finally:
        directory.close()


def _nearest_repo(path: Path) -> tuple[Path, tuple[int, int]]:
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
    with PinnedDirectory.open(resolved_repo) as repository:
        identity = repository.identity
        repository.revalidate()
    return resolved_repo, identity


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


def _open_lease_directory(
    repository: PinnedDirectory, repo_root: Path, *, create: bool,
) -> PinnedDirectory:
    try:
        entry = os.stat(
            _LEASE_DIRECTORY, dir_fd=repository.descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        if not create:
            raise ValueError("canonical lease root unavailable") from None
        os.mkdir(_LEASE_DIRECTORY, mode=0o700, dir_fd=repository.descriptor)
        repository.fsync()
        entry = os.stat(
            _LEASE_DIRECTORY, dir_fd=repository.descriptor,
            follow_symlinks=False,
        )
    if not stat.S_ISDIR(entry.st_mode) or stat.S_ISLNK(entry.st_mode):
        raise ValueError("canonical lease root unavailable")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(_LEASE_DIRECTORY, flags, dir_fd=repository.descriptor)
    try:
        opened = os.fstat(descriptor)
        current = os.stat(
            _LEASE_DIRECTORY, dir_fd=repository.descriptor,
            follow_symlinks=False,
        )
        identity = (opened.st_dev, opened.st_ino)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(current.st_mode)
            or identity != (current.st_dev, current.st_ino)
        ):
            raise ValueError("canonical lease root identity changed")
        return PinnedDirectory(repo_root / _LEASE_DIRECTORY, descriptor, identity)
    except Exception:
        os.close(descriptor)
        raise


def _write_once(directory: PinnedDirectory, value: dict[str, object]) -> None:
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    descriptor = directory.open_regular(
        _SCOPE_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600,
    )
    try:
        pending = encoded
        while pending:
            count = os.write(descriptor, pending)
            if count <= 0:
                raise OSError("scope write made no progress")
            pending = pending[count:]
        os.fsync(descriptor)
        directory.require_identity(descriptor, _SCOPE_FILE)
        directory.fsync()
        directory.require_identity(descriptor, _SCOPE_FILE)
        directory.revalidate()
    finally:
        os.close(descriptor)


def _read_scope(directory: PinnedDirectory) -> dict[str, object]:
    descriptor = directory.open_regular(_SCOPE_FILE, os.O_RDONLY)
    try:
        directory.require_identity(descriptor, _SCOPE_FILE)
        raw = _read_all(descriptor, _MAX_SCOPE_BYTES)
        directory.require_identity(descriptor, _SCOPE_FILE)
        directory.revalidate()
    finally:
        os.close(descriptor)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("invalid repository scope identity") from None


def repository_scope(state_dir, *, create: bool = False) -> RepositoryScope:
    repo_root, repo_identity = _nearest_repo(Path(state_dir))
    try:
        with PinnedDirectory.open(repo_root, repo_identity) as repository:
            lease = _open_lease_directory(repository, repo_root, create=create)
            try:
                repo_dev, repo_ino = repository.identity
                lease_dev, lease_ino = lease.identity
                path_exists = lease.regular_exists(_SCOPE_FILE)
                if create and not path_exists:
                    candidate = RepositoryScope(
                        repo_root, lease.path, secrets.token_hex(32),
                        repo_dev, repo_ino, lease_dev, lease_ino,
                    )
                    try:
                        _write_once(lease, _document(candidate))
                    except FileExistsError:
                        pass
                value = _read_scope(lease)
                expected_keys = {
                    "schema_version", "scope_id", "repo_root", "lease_root",
                }
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
                    repo_root, lease.path, value["scope_id"],
                    repo_dev, repo_ino, lease_dev, lease_ino,
                )
                if value != _document(scope):
                    raise ValueError("repository scope identity mismatch")
                lease.revalidate()
                repository.revalidate()
                return scope
            finally:
                lease.close()
    except (UnsafeFileError, OSError) as exc:
        raise ValueError("unsafe repository scope identity") from exc
