"""Shared verified file identity helpers for durable kernel files."""

from __future__ import annotations

import errno
import os
import secrets
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

    def pin_parent(self) -> "PinnedDirectory":
        """Open and verify the bound parent, retaining its descriptor."""
        return PinnedDirectory.open(self.path.parent, self.parent_identity)


class PinnedDirectory:
    """Owned directory descriptor used for all durable child operations."""

    __slots__ = ("path", "identity", "_descriptor")

    def __init__(self, path: Path, descriptor: int, identity: object):
        self.path = Path(path)
        self.identity = identity
        self._descriptor = descriptor

    @classmethod
    def open(cls, path: Path, expected_identity=None) -> "PinnedDirectory":
        path = Path(path)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(str(path), flags)
        try:
            opened = os.fstat(descriptor)
            entry = os.lstat(str(path))
            identity = (opened.st_dev, opened.st_ino)
            if (not stat.S_ISDIR(opened.st_mode) or not stat.S_ISDIR(entry.st_mode)
                    or identity != (entry.st_dev, entry.st_ino)
                    or (expected_identity is not None and identity != expected_identity)):
                raise UnsafeFileError(errno.ESTALE, "durable parent identity changed")
            return cls(path, descriptor, identity)
        except Exception:
            os.close(descriptor)
            raise

    @property
    def descriptor(self) -> int:
        if self._descriptor is None:
            raise UnsafeFileError(errno.EBADF, "durable parent handle is closed")
        return self._descriptor

    def revalidate(self) -> None:
        opened = os.fstat(self.descriptor)
        entry = os.lstat(str(self.path))
        if (not stat.S_ISDIR(opened.st_mode) or not stat.S_ISDIR(entry.st_mode)
                or (opened.st_dev, opened.st_ino) != self.identity
                or (entry.st_dev, entry.st_ino) != self.identity):
            raise UnsafeFileError(errno.ESTALE, "durable parent identity changed")

    def open_regular(self, name: str, flags: int, mode: int = 0o600) -> int:
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(name, flags | nofollow, mode, dir_fd=self.descriptor)
        try:
            self.require_identity(descriptor, name)
            return descriptor
        except Exception:
            os.close(descriptor)
            raise

    def require_identity(self, descriptor: int, name: str) -> None:
        opened = os.fstat(descriptor)
        entry = os.stat(name, dir_fd=self.descriptor, follow_symlinks=False)
        _require_exclusive_regular(opened, entry, self.path / name)

    def regular_exists(self, name: str) -> bool:
        try:
            entry = os.stat(name, dir_fd=self.descriptor, follow_symlinks=False)
        except FileNotFoundError:
            return False
        _require_exclusive_regular(entry, entry, self.path / name)
        return True

    def create_temporary(self, prefix: str, suffix: str) -> tuple[int, str]:
        for _ in range(100):
            name = prefix + secrets.token_hex(12) + suffix
            try:
                descriptor = self.open_regular(name, os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except FileExistsError:
                continue
            return descriptor, name
        raise UnsafeFileError(errno.EEXIST, "could not create durable temporary file")

    def replace(self, source: str, target: str) -> None:
        os.rename(source, target, src_dir_fd=self.descriptor, dst_dir_fd=self.descriptor)

    def unlink(self, name: str) -> None:
        os.unlink(name, dir_fd=self.descriptor)

    def fsync(self) -> str:
        try:
            os.fsync(self.descriptor)
            return "completed"
        except OSError as exc:
            unsupported = {errno.EINVAL, errno.EBADF, errno.EPERM}
            for name in ("ENOTSUP", "EOPNOTSUPP"):
                value = getattr(errno, name, None)
                if value is not None:
                    unsupported.add(value)
            if exc.errno in unsupported:
                return "unsupported"
            raise

    def close(self) -> None:
        if self._descriptor is None:
            return
        descriptor = self._descriptor
        self._descriptor = None
        os.close(descriptor)

    def __enter__(self) -> "PinnedDirectory":
        return self

    def __exit__(self, *_args) -> None:
        self.close()


class _OwnedResourceScope:
    """Close every owned durable resource while preserving a primary failure."""

    __slots__ = ("directory", "descriptors", "callbacks", "temporary_name")

    def __init__(self):
        self.directory = None
        self.descriptors = []
        self.callbacks = []
        self.temporary_name = None

    def pin(self, binding: DurablePathBinding) -> PinnedDirectory:
        self.directory = binding.pin_parent()
        return self.directory

    def own(self, descriptor: int, cleanup_error=None) -> int:
        self.descriptors.append((descriptor, cleanup_error))
        return descriptor

    def own_temporary(self, descriptor: int, name: str) -> int:
        self.temporary_name = name
        return self.own(descriptor)

    def disown_temporary(self) -> None:
        self.temporary_name = None

    def own_callback(self, callback, cleanup_error=None) -> None:
        self.callbacks.append((callback, cleanup_error))

    def __enter__(self) -> "_OwnedResourceScope":
        return self

    def __exit__(self, exc_type, _exc, _traceback) -> bool:
        failures = []
        if self.directory is not None and self.temporary_name is not None:
            try:
                self.directory.unlink(self.temporary_name)
            except FileNotFoundError:
                pass
            except OSError as error:
                failures.append(error)
        while self.descriptors:
            descriptor, cleanup_error = self.descriptors.pop()
            try:
                os.close(descriptor)
            except OSError as error:
                failures.append(cleanup_error or error)
        while self.callbacks:
            callback, cleanup_error = self.callbacks.pop()
            try:
                callback()
            except OSError as error:
                failures.append(cleanup_error or error)
        if self.directory is not None:
            directory = self.directory
            self.directory = None
            try:
                directory.close()
            except OSError as error:
                failures.append(error)
        if exc_type is None and failures:
            raise failures[0]
        return False


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


class LockHandle:
    """An open lock descriptor bound to its canonical pathname and inode."""

    def __init__(self, path: Path, descriptor: int, directory: PinnedDirectory):
        self.path = canonical_path(path)
        self._descriptor = descriptor
        self._directory = directory
        self._locked = False
        opened = os.fstat(descriptor)
        self.identity = (opened.st_dev, opened.st_ino)

    @classmethod
    def open_bound(cls, binding: DurablePathBinding) -> "LockHandle":
        directory = binding.pin_parent()
        descriptor = None
        try:
            descriptor = directory.open_regular(binding.path.name, os.O_CREAT | os.O_RDWR)
            return cls(binding.path, descriptor, directory)
        except Exception:
            try:
                if descriptor is not None:
                    os.close(descriptor)
            except OSError:
                pass
            try:
                directory.close()
            except OSError:
                pass
            raise

    @classmethod
    def acquire_bound(cls, binding: DurablePathBinding) -> "LockHandle":
        """Acquire a lock while retaining the verified parent descriptor."""
        path = binding.path
        if fcntl is None:
            raise LockingUnsupportedError(errno.ENOSYS, "crash-safe locking is unavailable", str(path))
        handle = cls.open_bound(binding)
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

    @property
    def directory(self) -> PinnedDirectory:
        return self._directory

    def revalidate(self) -> None:
        """Require the canonical path to still name this exclusive regular inode."""
        descriptor = self.descriptor
        opened = os.fstat(descriptor)
        self._directory.revalidate()
        self._directory.require_identity(descriptor, self.path.name)
        if (opened.st_dev, opened.st_ino) != self.identity:
            raise UnsafeFileError(errno.ESTALE, "lock descriptor identity changed", str(self.path))

    def close(self) -> None:
        if self._descriptor is None:
            return
        descriptor = self._descriptor
        self._descriptor = None
        failure = None
        try:
            os.close(descriptor)
        except OSError as exc:
            failure = exc
        try:
            if self._directory is not None:
                self._directory.close()
                self._directory = None
        except OSError:
            if failure is None:
                raise
        if failure is not None:
            raise failure

    def close_inherited(self) -> None:
        """Close a post-fork inherited descriptor without changing its flock."""
        self._locked = False
        self.close()

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
