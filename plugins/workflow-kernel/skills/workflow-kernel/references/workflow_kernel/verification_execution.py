"""Contained local command admission and execution for repository verification."""

from __future__ import annotations

import os
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .verification_contract import byte_digest
from .verification_errors import VerificationPlannerError


MAX_COMMAND_SECONDS = 3600
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
FIXED_SUBPROCESS_PATH = (
    "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
)
BASE_EXECUTION_ENVIRONMENT = frozenset({
    "TMPDIR", "DOCKER_HOST", "DOCKER_CONTEXT",
    "DOCKER_TLS_VERIFY", "DOCKER_API_VERSION",
    "GOFLAGS", "GOWORK", "DM_VERIFICATION_SUBSTRATE",
})
FORBIDDEN_EXECUTABLES = frozenset({"bash", "dash", "env", "fish", "sh", "zsh"})


def execution_environment(profile, environment):
    requested = {
        name
        for lane in profile["lanes"]
        for name in (
            *lane["cache_environment"], *lane["required_environment"],
        )
    }
    result = {"PATH": FIXED_SUBPROCESS_PATH}
    for name in sorted(BASE_EXECUTION_ENVIRONMENT | requested):
        if name in environment:
            result[name] = environment[name]
    return result


def _relative_executable(value):
    if (
        not value or value.startswith(("/", "\\", "-")) or "\\" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise VerificationPlannerError(
            "verification executable must be a safe relative path",
        )
    return value


def resolve_executable(repository, value):
    name = Path(value).name
    if name in FORBIDDEN_EXECUTABLES:
        raise VerificationPlannerError("verification executable is not permitted")
    if os.path.isabs(value):
        candidate = Path(value)
        if (
            candidate.is_symlink()
            and candidate.resolve(strict=True)
            != Path(sys.executable).resolve(strict=True)
        ):
            raise VerificationPlannerError(
                "absolute verification executable may not be a symlink",
            )
        executable = candidate.resolve(strict=True)
        allowed = {
            Path(directory).resolve()
            for directory in FIXED_SUBPROCESS_PATH.split(":")
            if Path(directory).exists()
        }
        if (
            executable.parent not in allowed
            and executable != Path(sys.executable).resolve(strict=True)
        ):
            raise VerificationPlannerError(
                "absolute verification executable is outside the fixed path",
            )
    elif "/" in value:
        relative = _relative_executable(value.removeprefix("./"))
        executable = (repository / relative).resolve(strict=True)
        try:
            executable.relative_to(repository)
        except ValueError:
            raise VerificationPlannerError(
                "verification executable escapes the repository",
            ) from None
    else:
        resolved = shutil.which(value, path=FIXED_SUBPROCESS_PATH)
        if resolved is None:
            raise VerificationPlannerError("verification executable is unavailable")
        executable = Path(resolved).resolve(strict=True)
    if executable.is_symlink() or not executable.is_file() or not os.access(
        executable, os.X_OK,
    ):
        raise VerificationPlannerError("verification executable is unavailable")
    return str(executable)


def run_bounded_capture(
    argv, cwd, environment, timeout_seconds, *,
    max_output_bytes=None,
):
    """Run one argv array with bounded streams, time, and descendants."""
    if max_output_bytes is None:
        max_output_bytes = MAX_OUTPUT_BYTES
    started = time.monotonic()
    reason = "command_completed"
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    totals = {"stdout": 0, "stderr": 0}
    process = subprocess.Popen(
        argv, cwd=cwd, env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
    )
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    deadline = started + timeout_seconds
    terminated = False
    killed = False
    termination_deadline = None
    drain_deadline = None

    def terminate_group(sig):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Some hosts allow the owned subprocess but deny process-group
            # signalling. Preserve the bounded-output/timeout guarantee by
            # signalling the leader directly; do not turn a cleanup-policy
            # limitation into an unhandled verifier exception. This fallback
            # does not claim descendant cleanup -- the command outcome remains
            # failed and the normal bounded drain still applies.
            try:
                process.send_signal(sig)
            except (ProcessLookupError, PermissionError):
                pass

    while selector.get_map():
        now = time.monotonic()
        remaining = deadline - now
        if remaining <= 0 and not terminated:
            reason = "command_timeout"
            terminated = True
            termination_deadline = now + 2.0
            terminate_group(signal.SIGTERM)
        if terminated and not killed and now >= termination_deadline:
            killed = True
            drain_deadline = now + 2.0
            terminate_group(signal.SIGKILL)
        if killed and now >= drain_deadline:
            for key in tuple(selector.get_map().values()):
                selector.unregister(key.fileobj)
            break
        wake_at = deadline
        if terminated and not killed:
            wake_at = termination_deadline
        elif killed:
            wake_at = drain_deadline
        wait = max(0.0, min(0.1, wake_at - now))
        for key, _mask in selector.select(wait):
            try:
                chunk = os.read(key.fileobj.fileno(), 65536)
            except BlockingIOError:
                continue
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            name = key.data
            totals[name] += len(chunk)
            available = max(0, max_output_bytes - len(streams[name]))
            streams[name].extend(chunk[:available])
            if totals[name] > max_output_bytes and not terminated:
                reason = "command_output_limit_exceeded"
                terminated = True
                termination_deadline = time.monotonic() + 2.0
                terminate_group(signal.SIGTERM)
    selector.close()
    process.stdout.close()
    process.stderr.close()
    try:
        exit_code = process.wait(timeout=0.5 if killed else 2.0)
    except subprocess.TimeoutExpired:
        terminate_group(signal.SIGKILL)
        try:
            exit_code = process.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            exit_code = None
    if exit_code is not None:
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            descendants_alive = False
        except PermissionError:
            descendants_alive = True
        else:
            descendants_alive = True
        if descendants_alive:
            terminate_group(signal.SIGTERM)
            time.sleep(0.05)
            terminate_group(signal.SIGKILL)
            if reason == "command_completed":
                reason = "command_descendants_terminated"
    if reason != "command_completed":
        exit_code = None
    return {
        "exit_code": exit_code,
        "reason": reason,
        "duration_seconds": round(time.monotonic() - started, 6),
        "stdout": bytes(streams["stdout"]),
        "stderr": bytes(streams["stderr"]),
        "stdout_bytes": totals["stdout"],
        "stderr_bytes": totals["stderr"],
    }


def run_local_command(repository, lane, environment):
    """Run one argv array with bounded streams, time, descendants, and home."""
    argv = [resolve_executable(repository, lane["argv"][0]), *lane["argv"][1:]]
    with tempfile.TemporaryDirectory(prefix="workflow-kernel-home-") as home:
        result = run_bounded_capture(
            argv, repository, {**environment, "HOME": home},
            lane["timeout_seconds"],
        )
    stdout = result["stdout"]
    stderr = result["stderr"]
    if stdout:
        sys.stdout.buffer.write(stdout)
        sys.stdout.buffer.flush()
    if stderr:
        sys.stderr.buffer.write(stderr)
        sys.stderr.buffer.flush()
    status = (
        "passed"
        if result["exit_code"] == 0 and result["reason"] == "command_completed"
        else "failed"
    )
    return {
        "status": status,
        "reason": result["reason"],
        "exit_code": result["exit_code"],
        "duration_seconds": result["duration_seconds"],
        "source_receipt_digest": None,
        "stdout_digest": byte_digest(stdout),
        "stderr_digest": byte_digest(stderr),
        "stdout_bytes": result["stdout_bytes"],
        "stderr_bytes": result["stderr_bytes"],
    }
