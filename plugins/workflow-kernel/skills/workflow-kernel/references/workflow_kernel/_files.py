"""Shared verified file identity helpers for durable kernel files."""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path


class UnsafeFileError(OSError):
    """A durable file path did not resolve to one exclusive regular file."""


def canonical_path(path: Path) -> Path:
    """Return one absolute lexical path without resolving symbolic links."""
    return Path(os.path.abspath(str(path)))


def _require_exclusive_regular(opened, entry, path: Path) -> None:
    if (not stat.S_ISREG(opened.st_mode) or stat.S_ISLNK(entry.st_mode)
            or opened.st_nlink != 1 or entry.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != (entry.st_dev, entry.st_ino)):
        raise UnsafeFileError(errno.ELOOP, "refusing linked or non-regular file", str(path))


def open_verified_regular(path: Path, flags: int, mode: int = 0o600) -> int:
    """Open a single-link regular file relative to its verified parent handle."""
    path = Path(path)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory = os.open(str(path.parent), directory_flags)
    descriptor = None
    try:
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path.name, flags | nofollow, mode, dir_fd=directory)
        opened = os.fstat(descriptor)
        entry = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        _require_exclusive_regular(opened, entry, path)
        return descriptor
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        raise
    finally:
        os.close(directory)


class LockHandle:
    """An open lock descriptor bound to its canonical pathname and inode."""

    def __init__(self, path: Path, descriptor: int):
        self.path = canonical_path(path)
        self._descriptor = descriptor
        opened = os.fstat(descriptor)
        self.identity = (opened.st_dev, opened.st_ino)

    @classmethod
    def open(cls, path: Path) -> "LockHandle":
        canonical = canonical_path(path)
        descriptor = open_verified_regular(canonical, os.O_CREAT | os.O_RDWR)
        try:
            return cls(canonical, descriptor)
        except Exception:
            os.close(descriptor)
            raise

    @property
    def descriptor(self) -> int:
        if self._descriptor is None:
            raise UnsafeFileError(errno.EBADF, "lock handle is closed", str(self.path))
        return self._descriptor

    def revalidate(self) -> None:
        """Require the canonical path to still name this exclusive regular inode."""
        descriptor = self.descriptor
        opened = os.fstat(descriptor)
        entry = os.lstat(str(self.path))
        _require_exclusive_regular(opened, entry, self.path)
        if (opened.st_dev, opened.st_ino) != self.identity:
            raise UnsafeFileError(errno.ESTALE, "lock descriptor identity changed", str(self.path))

    def close(self) -> None:
        if self._descriptor is None:
            return
        descriptor = self._descriptor
        self._descriptor = None
        os.close(descriptor)


def verified_regular_exists(path: Path) -> bool:
    """Return existence only after rejecting linked or non-regular entries."""
    path = Path(path)
    try:
        entry = os.lstat(str(path))
    except FileNotFoundError:
        return False
    _require_exclusive_regular(entry, entry, path)
    return True
