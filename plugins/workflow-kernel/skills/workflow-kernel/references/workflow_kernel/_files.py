"""Shared verified file identity helpers for durable kernel files."""

from __future__ import annotations

import errno
import os
import stat
from dataclasses import dataclass
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None


class UnsafeFileError(OSError):
    """A durable file path did not resolve to one exclusive regular file."""


class LockingUnsupportedError(UnsafeFileError):
    """Crash-safe advisory locking is unavailable."""


class LockContentionError(UnsafeFileError):
    """Another process owns the advisory lock."""


class LockIdentityError(UnsafeFileError):
    """A locked pathname no longer names the opened lock inode."""


def canonical_path(path: Path) -> Path:
    """Return one absolute lexical path without resolving symbolic links."""
    return Path(os.path.abspath(str(path)))


@dataclass(frozen=True)
class DurablePathBinding:
    """Physical parent binding for one lexical durable-file name."""

    path: Path
    parent_identity: object

    def revalidate_parent(self) -> None:
        if self.parent_identity is None:
            return
        parent = os.lstat(str(self.path.parent))
        if (not stat.S_ISDIR(parent.st_mode)
                or (parent.st_dev, parent.st_ino) != self.parent_identity):
            raise UnsafeFileError(errno.ESTALE, "durable parent identity changed")


def bind_durable_path(path: Path) -> DurablePathBinding:
    """Resolve an existing parent without following the final durable-file name."""
    lexical = canonical_path(Path(path))
    parent = Path(os.path.realpath(str(lexical.parent)))
    bound = parent / lexical.name
    try:
        opened_parent = os.lstat(str(parent))
    except (FileNotFoundError, NotADirectoryError):
        identity = None
    else:
        if not stat.S_ISDIR(opened_parent.st_mode):
            raise UnsafeFileError(errno.ENOTDIR, "durable parent is not a directory")
        identity = (opened_parent.st_dev, opened_parent.st_ino)
    return DurablePathBinding(bound, identity)


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


def require_descriptor_path_identity(descriptor: int, path: Path) -> None:
    """Require an open regular descriptor to remain the exclusive named file."""
    opened = os.fstat(descriptor)
    entry = os.lstat(str(path))
    _require_exclusive_regular(opened, entry, Path(path))


class LockHandle:
    """An open lock descriptor bound to its canonical pathname and inode."""

    def __init__(self, path: Path, descriptor: int):
        self.path = canonical_path(path)
        self._descriptor = descriptor
        self._locked = False
        opened = os.fstat(descriptor)
        self.identity = (opened.st_dev, opened.st_ino)

    @classmethod
    def open(cls, path: Path) -> "LockHandle":
        canonical = canonical_path(path)
        descriptor = open_verified_regular(canonical, os.O_CREAT | os.O_RDWR)
        try:
            return cls(canonical, descriptor)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            raise

    @classmethod
    def acquire(cls, path: Path) -> "LockHandle":
        """Open, exclusively lock, and revalidate one persistent lock file."""
        if fcntl is None:
            raise LockingUnsupportedError(errno.ENOSYS, "crash-safe locking is unavailable", str(path))
        handle = cls.open(path)
        try:
            fcntl.flock(handle.descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            handle._locked = True
        except (BlockingIOError, OSError) as exc:
            try:
                handle.close()
            except OSError:
                pass
            raise LockContentionError(errno.EWOULDBLOCK, "lock is already held", str(handle.path)) from exc
        try:
            handle.revalidate()
        except OSError as exc:
            try:
                handle.release()
            except OSError:
                pass
            raise LockIdentityError(errno.ESTALE, "lock path identity changed", str(handle.path)) from exc
        return handle

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

    def release(self) -> None:
        """Unlock and close without unlinking the persistent lock pathname."""
        if self._descriptor is None:
            return
        failure = None
        try:
            if self._locked:
                fcntl.flock(self._descriptor, fcntl.LOCK_UN)
                self._locked = False
        except BaseException as exc:
            failure = exc
            raise
        finally:
            try:
                self.close()
            except OSError:
                if failure is None:
                    raise


def verified_regular_exists(path: Path) -> bool:
    """Return existence only after rejecting linked or non-regular entries."""
    path = Path(path)
    try:
        entry = os.lstat(str(path))
    except FileNotFoundError:
        return False
    _require_exclusive_regular(entry, entry, path)
    return True
