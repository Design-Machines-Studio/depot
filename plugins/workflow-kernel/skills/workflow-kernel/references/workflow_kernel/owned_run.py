"""Exact-owned disposable run roots and bounded diagnostic retention."""

from __future__ import annotations

import json
import os
import pwd
import re
import secrets
import shlex
import shutil
import signal
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ._files import LockHandle, PinnedDirectory, bind_durable_path


_METADATA = ".depot-owned-run.json"
_LOCK = ".depot-owned-run.lock"
_CLEANUP = "CLEANUP.txt"
_VERSION = 1
_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
_RELATIVE_SEGMENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,127}")
_KINDS = frozenset({
    "temporary-directory", "temporary-repository", "cache", "raw-output",
    "diagnostic",
})
_OUTCOMES = frozenset({
    "succeeded", "failed", "blocked", "cancelled", "interrupted",
    "review-aborted",
})
_MAX_METADATA_BYTES = 256 * 1024
_MAX_DIAGNOSTIC_FILES = 128
_MAX_DIAGNOSTIC_BYTES = 2 * 1024 * 1024
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def default_run_base() -> Path:
    """Return the account-owned XDG state root without trusting ``$HOME``."""
    configured = os.environ.get("XDG_STATE_HOME")
    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            raise ValueError("XDG_STATE_HOME must be absolute")
    else:
        candidate = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".local" / "state"
    return candidate / "design-machines" / "depot" / "runs"


def _identity(path: Path) -> tuple[int, int]:
    value = os.lstat(path)
    if not stat.S_ISDIR(value.st_mode) or stat.S_ISLNK(value.st_mode):
        raise ValueError("owned run path must be a real directory")
    return value.st_dev, value.st_ino


def _safe_identifier(value: str, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
    return value


def _safe_relative(value: str) -> Path:
    if type(value) is not str or not value or "\\" in value:
        raise ValueError("invalid owned relative path")
    result = Path(value)
    if result.is_absolute() or any(
        part in {"", ".", ".."} or _RELATIVE_SEGMENT.fullmatch(part) is None
        for part in result.parts
    ):
        raise ValueError("invalid owned relative path")
    return result


def _safe_absolute(path: Path, label: str) -> Path:
    text = str(path)
    if (
        not path.is_absolute() or not text or len(text) > 4096
        or _CONTROL.search(text) is not None
    ):
        raise ValueError(f"invalid {label}")
    return path


def _atomic_metadata(root: Path, value: dict[str, object]) -> None:
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(encoded) > _MAX_METADATA_BYTES:
        raise ValueError("owned run metadata too large")
    with PinnedDirectory.open(root, tuple(value["root_identity"])) as directory:
        descriptor, temporary = directory.create_temporary(_METADATA + ".tmp-", "")
        try:
            pending = encoded
            while pending:
                count = os.write(descriptor, pending)
                if count <= 0:
                    raise OSError("owned run metadata write made no progress")
                pending = pending[count:]
            os.fsync(descriptor)
            directory.require_identity(descriptor, temporary)
            directory.replace(temporary, _METADATA)
            temporary = None
            directory.fsync()
        finally:
            os.close(descriptor)
            if temporary is not None:
                try:
                    directory.unlink(temporary)
                except FileNotFoundError:
                    pass


def _load_metadata(root: Path) -> dict[str, object]:
    with PinnedDirectory.open(root) as directory:
        descriptor = directory.open_regular(_METADATA, os.O_RDONLY)
        try:
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(8192, _MAX_METADATA_BYTES + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_METADATA_BYTES:
                    raise ValueError("owned run metadata too large")
                chunks.append(chunk)
            directory.require_identity(descriptor, _METADATA)
        finally:
            os.close(descriptor)
    try:
        value = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("invalid owned run metadata") from None
    required = {
        "version", "workflow", "run_id", "root", "root_identity",
        "base_identity", "resources",
    }
    if (
        type(value) is not dict or set(value) != required
        or value.get("version") != _VERSION
        or type(value.get("root_identity")) is not list
        or type(value.get("base_identity")) is not list
        or len(value["root_identity"]) != 2 or len(value["base_identity"]) != 2
        or any(type(item) is not int for item in value["root_identity"] + value["base_identity"])
        or type(value.get("resources")) is not list
        or value.get("root") != str(root)
    ):
        raise ValueError("invalid owned run metadata")
    _safe_identifier(value.get("workflow"), "workflow")
    _safe_identifier(value.get("run_id"), "run id")
    seen = set()
    for resource in value["resources"]:
        if (
            type(resource) is not dict
            or set(resource) != {"kind", "relative_path", "device", "inode"}
            or resource.get("kind") not in _KINDS
            or type(resource.get("device")) is not int
            or type(resource.get("inode")) is not int
        ):
            raise ValueError("invalid owned run metadata")
        relative = str(_safe_relative(resource.get("relative_path")))
        if relative in seen:
            raise ValueError("duplicate owned run resource")
        seen.add(relative)
    if _identity(root) != tuple(value["root_identity"]):
        raise ValueError("owned run root identity changed")
    if _identity(root.parent) != tuple(value["base_identity"]):
        raise ValueError("owned run base identity changed")
    return value


def _remove_entry(path: Path) -> None:
    try:
        value = os.lstat(path)
    except FileNotFoundError:
        return
    if stat.S_ISDIR(value.st_mode) and not stat.S_ISLNK(value.st_mode):
        shutil.rmtree(path)
    else:
        os.unlink(path)


def _bounded_diagnostic(path: Path) -> tuple[int, int]:
    files = 0
    size = 0
    for current, directories, names in os.walk(path, followlinks=False):
        current_path = Path(current)
        for name in tuple(directories):
            child = current_path / name
            value = os.lstat(child)
            if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
                raise ValueError("diagnostic root contains an unsafe entry")
        for name in names:
            child = current_path / name
            value = os.lstat(child)
            if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode):
                raise ValueError("diagnostic root contains an unsafe entry")
            files += 1
            size += value.st_size
            if files > _MAX_DIAGNOSTIC_FILES or size > _MAX_DIAGNOSTIC_BYTES:
                raise ValueError("diagnostic root exceeds bounded retention limits")
    return files, size


@dataclass(frozen=True)
class FinishReport:
    status: str
    path: str
    reason: str | None = None
    contains: str | None = None
    cleanup_command: str | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"status": self.status, "path": self.path}
        if self.reason is not None:
            result["reason"] = self.reason
        if self.contains is not None:
            result["contains"] = self.contains
        if self.cleanup_command is not None:
            result["cleanup_command"] = self.cleanup_command
        return result


class ExactOwnedRun:
    """One unique run root whose complete contents belong to one invocation."""

    def __init__(self, root: Path, metadata: dict[str, object]):
        self.root = root
        self._metadata = metadata

    @classmethod
    def start(
        cls, workflow: str, run_id: str, *, base: Path | None = None,
    ) -> "ExactOwnedRun":
        workflow = _safe_identifier(workflow, "workflow")
        run_id = _safe_identifier(run_id, "run id")
        base = _safe_absolute(
            Path(base) if base is not None else default_run_base(),
            "owned run base",
        )
        existed = base.exists()
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not existed:
            os.chmod(base, 0o700)
        base = Path(os.path.abspath(base))
        base_identity = _identity(base)
        root = Path(tempfile.mkdtemp(prefix=f"{workflow}-{run_id}-", dir=base))
        os.chmod(root, 0o700)
        metadata = {
            "version": _VERSION,
            "workflow": workflow,
            "run_id": run_id,
            "root": str(root),
            "root_identity": list(_identity(root)),
            "base_identity": list(base_identity),
            "resources": [],
        }
        try:
            _atomic_metadata(root, metadata)
            LockHandle.open_bound(bind_durable_path(root / _LOCK)).close()
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise
        return cls(root, metadata)

    @classmethod
    def open(cls, root: Path) -> "ExactOwnedRun":
        root = _safe_absolute(Path(os.path.abspath(root)), "owned run root")
        return cls(root, _load_metadata(root))

    @property
    def workflow(self) -> str:
        return self._metadata["workflow"]

    @property
    def run_id(self) -> str:
        return self._metadata["run_id"]

    @contextmanager
    def _lock(self):
        handle = LockHandle.acquire_bound(bind_durable_path(self.root / _LOCK))
        try:
            yield handle
        finally:
            handle.release()

    def create_path(self, kind: str, relative_path: str) -> Path:
        if kind not in _KINDS:
            raise ValueError("invalid owned path kind")
        relative = _safe_relative(relative_path)
        with self._lock():
            metadata = _load_metadata(self.root)
            if kind == "diagnostic" and (
                len(relative.parts) != 1
                or any(item["kind"] == "diagnostic" for item in metadata["resources"])
            ):
                raise ValueError("owned run permits one top-level diagnostic path")
            path = self.root / relative
            parent = path.parent
            if parent != self.root:
                parent_value = parent.resolve(strict=True)
                if not parent_value.is_relative_to(self.root) or parent.is_symlink():
                    raise ValueError("owned path escapes run root")
            if os.path.lexists(path):
                raise FileExistsError(str(path))
            path.mkdir(mode=0o700)
            value = os.lstat(path)
            resource = {
                "kind": kind, "relative_path": str(relative),
                "device": value.st_dev, "inode": value.st_ino,
            }
            metadata["resources"].append(resource)
            try:
                _atomic_metadata(self.root, metadata)
            except Exception:
                _remove_entry(path)
                raise
            self._metadata = metadata
            return path

    def record_path(self, kind: str, relative_path: str) -> Path:
        """Record an already-created child inside this invocation's fresh root."""
        if kind not in _KINDS:
            raise ValueError("invalid owned path kind")
        relative = _safe_relative(relative_path)
        with self._lock():
            metadata = _load_metadata(self.root)
            if kind == "diagnostic" and (
                len(relative.parts) != 1
                or any(item["kind"] == "diagnostic" for item in metadata["resources"])
            ):
                raise ValueError("owned run permits one top-level diagnostic path")
            path = self.root / relative
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(self.root) or path.is_symlink():
                raise ValueError("owned path escapes run root")
            value = os.lstat(path)
            if not stat.S_ISDIR(value.st_mode):
                raise ValueError("owned path must be a directory")
            if any(item["relative_path"] == str(relative) for item in metadata["resources"]):
                raise ValueError("duplicate owned run resource")
            metadata["resources"].append({
                "kind": kind, "relative_path": str(relative),
                "device": value.st_dev, "inode": value.st_ino,
            })
            _atomic_metadata(self.root, metadata)
            self._metadata = metadata
            return path

    def _remove_root(self) -> FinishReport:
        metadata = _load_metadata(self.root)
        identity = tuple(metadata["root_identity"])
        with PinnedDirectory.open(self.root.parent, tuple(metadata["base_identity"])) as parent:
            quarantine = self.root.name + ".cleanup-" + secrets.token_hex(12)
            os.rename(
                self.root.name, quarantine,
                src_dir_fd=parent.descriptor, dst_dir_fd=parent.descriptor,
            )
            target = self.root.parent / quarantine
            if _identity(target) != identity:
                raise ValueError("owned run root identity changed during cleanup")
        try:
            shutil.rmtree(target)
        except Exception:
            if target.exists() and not self.root.exists() and _identity(target) == identity:
                with PinnedDirectory.open(
                    self.root.parent, tuple(metadata["base_identity"]),
                ) as parent:
                    os.rename(
                        target.name, self.root.name,
                        src_dir_fd=parent.descriptor,
                        dst_dir_fd=parent.descriptor,
                    )
            raise
        return FinishReport("removed", str(self.root))

    def _retain(self, reason: str, contains: str) -> FinishReport:
        if type(reason) is not str or not reason.strip() or "\n" in reason:
            raise ValueError("retained diagnostic reason must be one line")
        if type(contains) is not str or not contains.strip() or "\n" in contains:
            raise ValueError("retained diagnostic contents must be one line")
        metadata = _load_metadata(self.root)
        diagnostic = next((
            item for item in metadata["resources"] if item["kind"] == "diagnostic"
        ), None)
        if diagnostic is None:
            path = self.root / "diagnostic"
            if os.path.lexists(path):
                raise ValueError("unregistered diagnostic path")
            path.mkdir(mode=0o700)
            value = os.lstat(path)
            diagnostic = {
                "kind": "diagnostic", "relative_path": "diagnostic",
                "device": value.st_dev, "inode": value.st_ino,
            }
        diagnostic_path = self.root / diagnostic["relative_path"]
        if _identity(diagnostic_path) != (diagnostic["device"], diagnostic["inode"]):
            raise ValueError("diagnostic path identity changed")
        files, size = _bounded_diagnostic(diagnostic_path)
        for child in tuple(self.root.iterdir()):
            if child.name in {_METADATA, _LOCK} or child == diagnostic_path:
                continue
            _remove_entry(child)
        metadata["resources"] = [diagnostic]
        _atomic_metadata(self.root, metadata)
        command = "rm -rf -- " + shlex.quote(str(self.root))
        cleanup_text = (
            f"Retained diagnostic root: {self.root}\n"
            f"Reason: {reason.strip()}\n"
            f"Contains: {contains.strip()} ({files} file(s), {size} byte(s))\n"
            f"Cleanup: {command}\n"
        )
        cleanup_path = self.root / _CLEANUP
        descriptor = os.open(
            cleanup_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            os.write(descriptor, cleanup_text.encode("utf-8"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return FinishReport(
            "retained", str(self.root), reason.strip(), contains.strip(), command,
        )

    def finish(
        self, outcome: str, *, retain_diagnostics: bool = False,
        reason: str | None = None, contains: str | None = None,
    ) -> FinishReport:
        if outcome not in _OUTCOMES:
            raise ValueError("invalid owned run outcome")
        if outcome == "succeeded" and retain_diagnostics:
            raise ValueError("successful runs cannot retain diagnostics")
        with self._lock():
            if retain_diagnostics:
                return self._retain(reason or outcome, contains or "compact diagnostics")
            return self._remove_root()


def run_owned_command(
    workflow: str, run_id: str, command: Sequence[str], *,
    base: Path | None = None, resume_root: Path | None = None,
    retain_on_failure: bool = False, diagnostic_contains: str = "compact command diagnostics",
) -> tuple[int, FinishReport]:
    """Supervise one argv command and reconcile its root on INT/TERM/exit."""
    if not command or any(type(value) is not str or not value for value in command):
        raise ValueError("owned command argv is required")
    run = (
        ExactOwnedRun.open(resume_root) if resume_root is not None
        else ExactOwnedRun.start(workflow, run_id, base=base)
    )
    if run.workflow != workflow or run.run_id != run_id:
        raise ValueError("resumed owned run identity mismatch")
    if retain_on_failure and not any(
        item["kind"] == "diagnostic" for item in run._metadata["resources"]
    ):
        run.create_path("diagnostic", "diagnostic")
    environment = dict(os.environ)
    environment["DEPOT_EXACT_RUN_ROOT"] = str(run.root)
    received = []
    child = None

    def forward(signum, _frame):
        received.append(signum)
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass

    previous = {name: signal.getsignal(name) for name in (signal.SIGINT, signal.SIGTERM)}
    for name in previous:
        signal.signal(name, forward)
    launch_failed = False
    try:
        try:
            child = subprocess.Popen(tuple(command), env=environment, start_new_session=True)
            return_code = child.wait()
        except OSError:
            launch_failed = True
            return_code = 127
    finally:
        for name, handler in previous.items():
            signal.signal(name, handler)
    if received:
        signum = received[-1]
        report = run.finish(
            "interrupted", retain_diagnostics=retain_on_failure,
            reason=f"received {signal.Signals(signum).name}",
            contains=diagnostic_contains,
        )
        return 128 + signum, report
    if launch_failed:
        report = run.finish(
            "failed", retain_diagnostics=retain_on_failure,
            reason="command launch failed", contains=diagnostic_contains,
        )
        return return_code, report
    if return_code == 0:
        return return_code, run.finish("succeeded")
    report = run.finish(
        "failed", retain_diagnostics=retain_on_failure,
        reason=f"command exited {return_code}", contains=diagnostic_contains,
    )
    return return_code, report


@contextmanager
def owned_temporary_directory(kind: str, prefix: str):
    """Create a recorded execution directory when a supervised root is active."""
    root = os.environ.get("DEPOT_EXACT_RUN_ROOT")
    if not root:
        with tempfile.TemporaryDirectory(prefix=prefix) as directory:
            yield directory
        return
    run = ExactOwnedRun.open(Path(root))
    stem = prefix.rstrip("-")
    _safe_identifier(stem, "temporary directory prefix")
    relative = stem + "-" + secrets.token_hex(12)
    path = run.create_path(kind, relative)
    try:
        yield str(path)
    finally:
        _remove_entry(path)
