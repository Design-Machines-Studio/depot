"""Bounded execution for selected repository-verification lanes."""

from __future__ import annotations

import json
import math
import os
import re
import selectors
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .argv import validate_safe_argv
from .repository_verification import (
    canonical_digest, validate_repository_profile, validate_repository_state,
    validate_verification_plan, validate_verification_result,
)


MAX_GO_EVENTS = 100_000
MAX_GO_PACKAGES = 4_096
_COVERAGE = re.compile(r"coverage:\s+([0-9]+(?:\.[0-9]+)?)%")
MAX_GO_ELAPSED_SECONDS = 86_400


def _now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _blocked_result(lane, plan, reason, started):
    return validate_verification_result({
        "schema_version": 1, "lane_id": lane["id"],
        "plan_digest": plan["plan_digest"], "status": "blocked",
        "started_at": started, "completed_at": _now(), "exit_code": None,
        "command_digest": canonical_digest(lane["argv"]), "evidence_refs": [],
        "packages": [], "parser_status": "not_applicable", "parser_reason": reason,
    })


def repository_doctor_checks(plan, profile, current_repository, prerequisite_states):
    """Return separate deterministic preflight facts without running commands."""
    plan = validate_verification_plan(plan)
    profile = validate_repository_profile(profile)
    current = validate_repository_state(current_repository)
    if type(prerequisite_states) is not dict or any(type(key) is not str or type(value) is not str for key, value in prerequisite_states.items()):
        raise ValueError("invalid prerequisite states")
    checks = []

    def add(identifier, passed, reason):
        checks.append({"id": identifier, "status": "passed" if passed else "blocked", "reason": reason})

    repository_matches = plan["repository"] == current
    add("branch_worktree_binding", repository_matches, "current" if repository_matches else "repository_state_changed")
    profile_matches = plan["profile_digest"] == canonical_digest(profile)
    add("profile_binding", profile_matches, "current" if profile_matches else "profile_changed")
    commands_valid = True
    try:
        for lane in plan["lanes"]:
            if lane["runnable"]:
                validate_safe_argv(lane["argv"])
    except ValueError:
        commands_valid = False
    add("command_validity", commands_valid, "valid" if commands_valid else "unsafe_command")
    for lane in plan["lanes"]:
        if not lane["selected"]:
            continue
        for item in lane["prerequisites"]:
            key = f"{item['kind']}:{item['id']}"
            observed = prerequisite_states.get(key, "unavailable")
            passed = observed == "available" or not item["required"]
            add(f"prerequisite:{key}", passed, observed)
    doctor_checks = {
        lane["doctor_check"] for lane in plan["lanes"]
        if lane["tier"] == "doctor" and lane["selected"]
    }
    for identifier in ("generator_drift", "diff_check"):
        declared = identifier in doctor_checks
        checks.append({
            "id": identifier, "status": "pending" if declared else "unavailable",
            "reason": "declared_check" if declared else "not_declared",
        })
    return checks


def _kill_process_session(process):
    """Terminate the process and every descendant in its private session."""
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        elif process.poll() is None:
            process.kill()
    except ProcessLookupError:
        pass


def _bounded_run(argv, *, cwd, timeout_seconds, max_output_bytes):
    process = subprocess.Popen(
        list(validate_safe_argv(argv)), cwd=cwd, shell=False,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env={"PATH": os.defpath, "LANG": "C", "LC_ALL": "C"},
        start_new_session=True,
    )
    assert process.stdout is not None
    descriptor = process.stdout.fileno()
    os.set_blocking(descriptor, False)
    selector = selectors.DefaultSelector()
    selector.register(descriptor, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout_seconds
    chunks = []
    size = 0
    terminal_reason = None
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                terminal_reason = "timeout"
                _kill_process_session(process)
                break
            events = selector.select(min(remaining, 0.1))
            for _key, _mask in events:
                chunk = os.read(descriptor, min(65_536, max_output_bytes + 1 - size))
                if chunk:
                    chunks.append(chunk); size += len(chunk)
                    if size > max_output_bytes:
                        terminal_reason = "output_limit_exceeded"
                        _kill_process_session(process)
                        break
            if terminal_reason:
                break
            if process.poll() is not None:
                while size <= max_output_bytes:
                    try:
                        chunk = os.read(descriptor, min(65_536, max_output_bytes + 1 - size))
                    except BlockingIOError:
                        break
                    if not chunk:
                        break
                    chunks.append(chunk); size += len(chunk)
                if size > max_output_bytes:
                    terminal_reason = "output_limit_exceeded"
                break
        process.wait(timeout=2)
    finally:
        selector.close()
        # A direct child may exit while one of its descendants still holds the
        # output pipe. The dedicated session is the execution ownership unit.
        _kill_process_session(process)
        if process.poll() is None:
            process.wait(timeout=2)
        process.stdout.close()
    return process.returncode, b"".join(chunks)[:max_output_bytes], terminal_reason


def parse_go_test_json(raw, *, command_digest, exit_code, max_events=MAX_GO_EVENTS,
                       max_packages=MAX_GO_PACKAGES):
    """Parse a bounded newline-delimited `go test -json` stream."""
    if type(raw) is not bytes:
        raise ValueError("invalid go test output")
    if type(max_events) is not int or max_events < 1 or type(max_packages) is not int or max_packages < 1:
        raise ValueError("invalid parser limits")
    packages = {}
    parser_status = "complete"
    parser_reason = None
    lines = raw.splitlines()
    if len(lines) > max_events:
        lines = lines[:max_events]
        parser_status, parser_reason = "truncated", "event_limit_exceeded"
    for line in lines:
        try:
            event = json.loads(line)
        except (UnicodeError, json.JSONDecodeError):
            parser_status, parser_reason = "malformed", "malformed_go_json"
            break
        if type(event) is not dict:
            parser_status, parser_reason = "malformed", "invalid_go_event"
            break
        package = event.get("Package")
        action = event.get("Action")
        if type(package) is not str or not package or action not in {"start", "run", "pause", "cont", "pass", "bench", "fail", "output", "skip"}:
            parser_status, parser_reason = "malformed", "invalid_go_event"
            break
        if package not in packages and len(packages) >= max_packages:
            parser_status, parser_reason = "truncated", "package_limit_exceeded"
            break
        record = packages.setdefault(package, {
            "package": package, "status": "skipped", "elapsed_milliseconds": 0,
            "failures": set(), "coverage_basis_points": None,
        })
        if action in {"pass", "fail", "skip"} and "Test" not in event:
            record["status"] = {"pass": "passed", "fail": "failed", "skip": "skipped"}[action]
            elapsed = event.get("Elapsed", 0)
            if (
                type(elapsed) not in {int, float}
                or isinstance(elapsed, bool)
                or not math.isfinite(elapsed)
                or elapsed < 0
                or elapsed > MAX_GO_ELAPSED_SECONDS
            ):
                parser_status, parser_reason = "malformed", "invalid_go_numeric"
                break
            record["elapsed_milliseconds"] = round(elapsed * 1000)
        if action == "fail" and type(event.get("Test")) is str:
            record["failures"].add(event["Test"])
        if action == "output" and type(event.get("Output")) is str:
            match = _COVERAGE.search(event["Output"])
            if match:
                coverage = float(match.group(1))
                if not math.isfinite(coverage) or coverage < 0 or coverage > 100:
                    parser_status, parser_reason = "malformed", "invalid_go_numeric"
                    break
                record["coverage_basis_points"] = round(coverage * 100)
    result = []
    for record in packages.values():
        record["failures"] = sorted(record["failures"])
        result.append(record)
    return {
        "packages": sorted(result, key=lambda item: item["package"]),
        "parser_status": parser_status, "parser_reason": parser_reason,
        "command_digest": command_digest, "exit_code": exit_code,
    }


def execute_selected_lane(plan, profile, *, lane_id, repo_root, current_repository,
                          prerequisite_states):
    """Execute one selected local lane under current plan/profile authority."""
    plan = validate_verification_plan(plan)
    profile = validate_repository_profile(profile)
    started = _now()
    lane = next((item for item in plan["lanes"] if item["id"] == lane_id), None)
    if lane is None:
        raise ValueError("unknown lane")
    if not lane["selected"] or not lane["runnable"] or lane["authority"] != "local":
        return _blocked_result(lane, plan, "lane_not_runnable", started)
    checks = repository_doctor_checks(plan, profile, current_repository, prerequisite_states)
    if any(item["status"] != "passed" for item in checks if item["id"] not in {"generator_drift", "diff_check"}):
        return _blocked_result(lane, plan, "preflight_blocked", started)
    root = Path(repo_root).resolve(strict=True)
    cwd = (root / lane["workdir"]).resolve(strict=True)
    try:
        cwd.relative_to(root)
    except ValueError:
        return _blocked_result(lane, plan, "working_directory_escape", started)
    command_digest = canonical_digest(lane["argv"])
    try:
        exit_code, output, terminal_reason = _bounded_run(
            lane["argv"], cwd=cwd, timeout_seconds=lane["timeout_seconds"],
            max_output_bytes=lane["max_output_bytes"],
        )
    except (FileNotFoundError, PermissionError, OSError):
        return _blocked_result(lane, plan, "tool_unavailable", started)
    parser = {
        "packages": [], "parser_status": "not_applicable", "parser_reason": None,
        "command_digest": command_digest, "exit_code": exit_code,
    }
    if lane["parser"] == "go-test-json":
        parser = parse_go_test_json(output, command_digest=command_digest, exit_code=exit_code)
    if terminal_reason is not None:
        parser["parser_status"] = "truncated"
        parser["parser_reason"] = terminal_reason
        exit_code = None
    status = "passed" if exit_code == 0 and parser["parser_status"] in {"complete", "not_applicable"} else "failed"
    return validate_verification_result({
        "schema_version": 1, "lane_id": lane["id"],
        "plan_digest": plan["plan_digest"], "status": status,
        "started_at": started, "completed_at": _now(), "exit_code": exit_code,
        "command_digest": command_digest, "evidence_refs": [],
        "packages": parser["packages"], "parser_status": parser["parser_status"],
        "parser_reason": parser["parser_reason"],
    })
