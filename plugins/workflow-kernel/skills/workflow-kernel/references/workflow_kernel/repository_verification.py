"""Deterministic repository verification profiles, plans, and results."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import PurePosixPath

from .argv import validate_safe_argv
from .redaction import contains_high_confidence_secret, normalize_durable_string


SCHEMA_VERSION = 1
MAX_ITEMS = 1024
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_SHA = re.compile(r"[0-9a-f]{40,64}")
_TIERS = frozenset({
    "doctor", "fast", "focused", "full", "race", "security", "container",
    "browser", "accessibility", "remote_pr", "push", "schedule",
    "merge_group", "post_merge",
})
_STATUSES = frozenset({"passed", "failed", "skipped", "unavailable", "blocked"})
_PARSERS = frozenset({"exit-code", "go-test-json", "doctor"})
_PROFILE_FIELDS = frozenset({
    "schema_version", "profile_id", "profile_version", "source",
    "declaration_digests", "lanes",
})
_SOURCE_FIELDS = frozenset({"kind", "reference"})
_LANE_FIELDS = frozenset({
    "id", "tier", "argv", "workdir", "parser", "authority", "runnable",
    "timeout_seconds", "max_output_bytes", "selectors", "risk_escalators",
    "prerequisites", "doctor_check",
})
_SELECTOR_FIELDS = frozenset({"path_prefixes", "packages"})
_PREREQUISITE_FIELDS = frozenset({"kind", "id", "required"})
_STATE_FIELDS = frozenset({
    "scope_id", "commit_sha", "tree_digest", "tracked_diff_digest",
    "untracked_digest", "branch", "worktree_state",
})
_PLAN_FIELDS = frozenset({
    "schema_version", "profile_id", "profile_digest", "repository",
    "declaration_digests", "changed_paths", "changed_packages", "risk_inputs",
    "lanes", "execution_budget_seconds", "generated_at", "plan_digest",
})
_PLAN_LANE_FIELDS = frozenset({
    "id", "tier", "selected", "reason", "authority", "runnable", "argv",
    "workdir", "parser", "timeout_seconds", "max_output_bytes", "prerequisites",
    "doctor_check",
})
_RESULT_FIELDS = frozenset({
    "schema_version", "lane_id", "plan_digest", "status", "started_at",
    "completed_at", "exit_code", "command_digest", "evidence_refs", "packages",
    "parser_status", "parser_reason",
})
_PACKAGE_FIELDS = frozenset({"package", "status", "elapsed_milliseconds", "failures", "coverage_basis_points"})


def _fail(reason: str):
    raise ValueError(reason)


def _object(value, fields, name):
    if type(value) is not dict or set(value) != fields:
        _fail(f"{name} fields mismatch")
    return value


def _integer(value, name, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        _fail(f"invalid {name}")
    return value


def _number(value, name, minimum=0):
    if type(value) not in {int, float} or isinstance(value, bool) or value < minimum:
        _fail(f"invalid {name}")
    return value


def _string(value, name, *, pattern=None, maximum=2048, nullable=False):
    if nullable and value is None:
        return None
    if (
        type(value) is not str or not value or len(value) > maximum
        or any(ord(char) < 0x20 for char in value)
        or contains_high_confidence_secret(value)
        or (pattern is not None and pattern.fullmatch(value) is None)
    ):
        _fail(f"invalid {name}")
    try:
        if normalize_durable_string(value) != value:
            _fail(f"unsafe {name}")
    except ValueError:
        _fail(f"unsafe {name}")
    return value


def _timestamp(value, name):
    value = _string(value, name, maximum=64)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail(f"invalid {name}")
    if parsed.tzinfo is None:
        _fail(f"invalid {name}")
    return value


def _parsed_timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _unique_strings(value, name, *, pattern=None, maximum=MAX_ITEMS):
    if type(value) is not list or len(value) > maximum:
        _fail(f"invalid {name}")
    result = [_string(item, name, pattern=pattern) for item in value]
    if len(result) != len(set(result)):
        _fail(f"duplicate {name}")
    return sorted(result)


def _relative_path(value, name, *, allow_dot=False):
    value = _string(value, name, maximum=1024)
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or (not allow_dot and value in {"", "."}):
        _fail(f"invalid {name}")
    return value


def _canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def canonical_digest(value) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _validate_source(value):
    value = _object(value, _SOURCE_FIELDS, "profile source")
    kind = value["kind"]
    if kind not in {"project", "plugin"}:
        _fail("invalid profile source kind")
    return {"kind": kind, "reference": _relative_path(value["reference"], "source reference")}


def _validate_prerequisites(value):
    if type(value) is not list or len(value) > MAX_ITEMS:
        _fail("invalid prerequisites")
    result = []
    identities = set()
    for raw in value:
        item = _object(raw, _PREREQUISITE_FIELDS, "prerequisite")
        kind = item["kind"]
        if kind not in {"tool", "runtime", "service"}:
            _fail("invalid prerequisite kind")
        identifier = _string(item["id"], "prerequisite id", pattern=_ID, maximum=128)
        identity = (kind, identifier)
        if identity in identities:
            _fail("duplicate prerequisite")
        identities.add(identity)
        if type(item["required"]) is not bool:
            _fail("invalid prerequisite required")
        result.append({"kind": kind, "id": identifier, "required": item["required"]})
    return sorted(result, key=lambda item: (item["kind"], item["id"]))


def _validate_lane(value):
    value = _object(value, _LANE_FIELDS, "lane")
    identifier = _string(value["id"], "lane id", pattern=_ID, maximum=128)
    tier = value["tier"]
    if tier not in _TIERS:
        _fail("invalid lane tier")
    parser = value["parser"]
    if parser not in _PARSERS:
        _fail("invalid lane parser")
    if tier == "doctor" and parser != "doctor":
        _fail("doctor lane requires doctor parser")
    doctor_check = value["doctor_check"]
    if tier == "doctor":
        if doctor_check not in {"generator_drift", "diff_check", "custom"}:
            _fail("invalid doctor_check")
    elif doctor_check is not None:
        _fail("non-doctor lane has doctor_check")
    authority = _string(value["authority"], "authority", pattern=_ID, maximum=128)
    if type(value["runnable"]) is not bool:
        _fail("invalid lane runnable")
    if value["runnable"]:
        argv = list(validate_safe_argv(value["argv"]))
    else:
        if value["argv"] != []:
            _fail("non-runnable lane has argv")
        argv = []
    selectors = _object(value["selectors"], _SELECTOR_FIELDS, "selectors")
    paths = [_relative_path(item, "path selector") for item in selectors["path_prefixes"]] if type(selectors["path_prefixes"]) is list else _fail("invalid path selectors")
    packages = _unique_strings(selectors["packages"], "package selector", maximum=MAX_ITEMS)
    if len(paths) != len(set(paths)) or len(paths) > MAX_ITEMS:
        _fail("duplicate or excessive path selectors")
    workdir = _relative_path(value["workdir"], "lane workdir", allow_dot=True)
    return {
        "id": identifier, "tier": tier, "argv": argv, "workdir": workdir,
        "parser": parser, "authority": authority, "runnable": value["runnable"],
        "timeout_seconds": _integer(value["timeout_seconds"], "timeout_seconds", 1, 86_400),
        "max_output_bytes": _integer(value["max_output_bytes"], "max_output_bytes", 1, MAX_OUTPUT_BYTES),
        "selectors": {"path_prefixes": sorted(paths), "packages": packages},
        "risk_escalators": _unique_strings(value["risk_escalators"], "risk escalator", pattern=_ID),
        "prerequisites": _validate_prerequisites(value["prerequisites"]),
        "doctor_check": doctor_check,
    }


def validate_repository_profile(value):
    value = _object(value, _PROFILE_FIELDS, "repository profile")
    if _integer(value["schema_version"], "schema_version", 1) != SCHEMA_VERSION:
        _fail("unsupported schema_version")
    if type(value["lanes"]) is not list or not value["lanes"] or len(value["lanes"]) > MAX_ITEMS:
        _fail("invalid lanes")
    lanes = [_validate_lane(item) for item in value["lanes"]]
    if len({item["id"] for item in lanes}) != len(lanes):
        _fail("duplicate lane id")
    canonical = {
        "schema_version": SCHEMA_VERSION,
        "profile_id": _string(value["profile_id"], "profile_id", pattern=_ID, maximum=128),
        "profile_version": _integer(value["profile_version"], "profile_version", 1),
        "source": _validate_source(value["source"]),
        "declaration_digests": _unique_strings(value["declaration_digests"], "declaration digest", pattern=_DIGEST),
        "lanes": sorted(lanes, key=lambda item: item["id"]),
    }
    return canonical


def repository_profile_digest(profile) -> str:
    return canonical_digest(validate_repository_profile(profile))


def resolve_repository_profile(*, project_profile=None, plugin_profile=None):
    """Apply project, then plugin, then explicit unavailable precedence."""
    if project_profile is not None:
        profile = validate_repository_profile(project_profile)
        if profile["source"]["kind"] != "project":
            _fail("project profile has wrong provenance")
        return {"status": "resolved", "source": "project", "profile": profile}
    if plugin_profile is not None:
        profile = validate_repository_profile(plugin_profile)
        if profile["source"]["kind"] != "plugin":
            _fail("plugin profile has wrong provenance")
        return {"status": "resolved", "source": "plugin", "profile": profile}
    return {"status": "unavailable", "source": "none", "profile": None}


def validate_repository_state(value):
    value = _object(value, _STATE_FIELDS, "repository state")
    state = {
        "scope_id": _string(value["scope_id"], "scope_id", pattern=re.compile(r"[0-9a-f]{64}")),
        "commit_sha": _string(value["commit_sha"], "commit_sha", pattern=_SHA),
        "tree_digest": _string(value["tree_digest"], "tree_digest", pattern=_DIGEST),
        "tracked_diff_digest": _string(value["tracked_diff_digest"], "tracked_diff_digest", pattern=_DIGEST),
        "untracked_digest": _string(value["untracked_digest"], "untracked_digest", pattern=_DIGEST),
        "branch": _string(value["branch"], "branch", maximum=256),
        "worktree_state": value["worktree_state"],
    }
    if state["worktree_state"] not in {"clean", "dirty", "detached"}:
        _fail("invalid worktree_state")
    return state


def _lane_selected(lane, changed_paths, changed_packages, risk_inputs, required):
    if lane["id"] in required or lane["tier"] == "doctor":
        return True, "required"
    selectors = lane["selectors"]
    if set(lane["risk_escalators"]) & set(risk_inputs):
        return True, "risk_escalated"
    if any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for path in changed_paths for prefix in selectors["path_prefixes"]):
        return True, "changed_path"
    if set(changed_packages) & set(selectors["packages"]):
        return True, "changed_package"
    if not selectors["path_prefixes"] and not selectors["packages"] and lane["tier"] in {"fast", "focused"}:
        return True, "default_local"
    return False, "scope_not_matched"


def derive_verification_plan(profile, repository, *, changed_paths, changed_packages,
                             risk_inputs, required_lane_ids=(), generated_at):
    profile = validate_repository_profile(profile)
    repository = validate_repository_state(repository)
    paths = sorted({_relative_path(item, "changed path") for item in changed_paths})
    packages = sorted({_string(item, "changed package", maximum=512) for item in changed_packages})
    risks = sorted({_string(item, "risk input", pattern=_ID, maximum=128) for item in risk_inputs})
    required = {_string(item, "required lane id", pattern=_ID, maximum=128) for item in required_lane_ids}
    known = {lane["id"] for lane in profile["lanes"]}
    if not required <= known:
        _fail("required lane is unknown")
    plan_lanes = []
    for lane in profile["lanes"]:
        selected, reason = _lane_selected(lane, paths, packages, risks, required)
        plan_lanes.append({
            "id": lane["id"], "tier": lane["tier"], "selected": selected,
            "reason": reason, "authority": lane["authority"],
            "runnable": lane["runnable"], "argv": lane["argv"],
            "workdir": lane["workdir"], "parser": lane["parser"],
            "timeout_seconds": lane["timeout_seconds"],
            "max_output_bytes": lane["max_output_bytes"],
            "prerequisites": lane["prerequisites"],
            "doctor_check": lane["doctor_check"],
        })
    plan = {
        "schema_version": SCHEMA_VERSION, "profile_id": profile["profile_id"],
        "profile_digest": repository_profile_digest(profile), "repository": repository,
        "declaration_digests": profile["declaration_digests"],
        "changed_paths": paths, "changed_packages": packages, "risk_inputs": risks,
        "lanes": plan_lanes,
        "execution_budget_seconds": sum(lane["timeout_seconds"] for lane in plan_lanes if lane["selected"] and lane["runnable"]),
        "generated_at": _timestamp(generated_at, "generated_at"),
    }
    plan["plan_digest"] = canonical_digest(plan)
    return plan


def validate_verification_plan(value):
    value = _object(value, _PLAN_FIELDS, "verification plan")
    digest = value["plan_digest"]
    body = dict(value); body.pop("plan_digest")
    profile_id = _string(value["profile_id"], "profile_id", pattern=_ID, maximum=128)
    lanes = []
    if type(value["lanes"]) is not list or len(value["lanes"]) > MAX_ITEMS:
        _fail("invalid plan lanes")
    ids = set()
    for raw in value["lanes"]:
        item = _object(raw, _PLAN_LANE_FIELDS, "plan lane")
        identifier = _string(item["id"], "lane id", pattern=_ID, maximum=128)
        if identifier in ids:
            _fail("duplicate plan lane id")
        ids.add(identifier)
        if type(item["selected"]) is not bool or type(item["runnable"]) is not bool:
            _fail("invalid plan lane flags")
        if item["runnable"]:
            argv = list(validate_safe_argv(item["argv"]))
        else:
            if item["argv"] != []:
                _fail("non-runnable plan lane has argv")
            argv = []
        lanes.append({
            "id": identifier, "tier": item["tier"], "selected": item["selected"],
            "reason": _string(item["reason"], "lane reason", pattern=_ID, maximum=128),
            "authority": _string(item["authority"], "authority", pattern=_ID, maximum=128),
            "runnable": item["runnable"], "argv": argv,
            "workdir": _relative_path(item["workdir"], "lane workdir", allow_dot=True),
            "parser": item["parser"],
            "timeout_seconds": _integer(item["timeout_seconds"], "timeout_seconds", 1, 86_400),
            "max_output_bytes": _integer(item["max_output_bytes"], "max_output_bytes", 1, MAX_OUTPUT_BYTES),
            "prerequisites": _validate_prerequisites(item["prerequisites"]),
            "doctor_check": item["doctor_check"],
        })
        if item["tier"] not in _TIERS or item["parser"] not in _PARSERS:
            _fail("invalid plan lane vocabulary")
        if item["tier"] == "doctor":
            if item["doctor_check"] not in {"generator_drift", "diff_check", "custom"}:
                _fail("invalid plan doctor_check")
        elif item["doctor_check"] is not None:
            _fail("non-doctor plan lane has doctor_check")
    canonical = {
        "schema_version": _integer(value["schema_version"], "schema_version", 1),
        "profile_id": profile_id,
        "profile_digest": _string(value["profile_digest"], "profile_digest", pattern=_DIGEST),
        "repository": validate_repository_state(value["repository"]),
        "declaration_digests": _unique_strings(value["declaration_digests"], "declaration digest", pattern=_DIGEST),
        "changed_paths": sorted(_relative_path(item, "changed path") for item in value["changed_paths"]),
        "changed_packages": _unique_strings(value["changed_packages"], "changed package"),
        "risk_inputs": _unique_strings(value["risk_inputs"], "risk input", pattern=_ID),
        "lanes": sorted(lanes, key=lambda item: item["id"]),
        "execution_budget_seconds": _integer(value["execution_budget_seconds"], "execution_budget_seconds"),
        "generated_at": _timestamp(value["generated_at"], "generated_at"),
    }
    if canonical["schema_version"] != SCHEMA_VERSION:
        _fail("unsupported schema_version")
    expected = canonical_digest(canonical)
    if digest != expected:
        _fail("plan digest mismatch")
    canonical["plan_digest"] = expected
    return canonical


def validate_verification_result(value):
    value = _object(value, _RESULT_FIELDS, "verification result")
    status = value["status"]
    if status not in _STATUSES:
        _fail("invalid result status")
    packages = []
    if type(value["packages"]) is not list or len(value["packages"]) > MAX_ITEMS:
        _fail("invalid packages")
    package_ids = set()
    for raw in value["packages"]:
        item = _object(raw, _PACKAGE_FIELDS, "package result")
        package = _string(item["package"], "package", maximum=512)
        if package in package_ids:
            _fail("duplicate package result")
        package_ids.add(package)
        package_status = item["status"]
        if package_status not in {"passed", "failed", "skipped"}:
            _fail("invalid package status")
        failures = _unique_strings(item["failures"], "failure", maximum=MAX_ITEMS)
        coverage = item["coverage_basis_points"]
        if coverage is not None:
            coverage = _integer(coverage, "coverage_basis_points")
            if coverage > 10_000:
                _fail("invalid coverage")
        packages.append({
            "package": package, "status": package_status,
            "elapsed_milliseconds": _integer(item["elapsed_milliseconds"], "elapsed_milliseconds"),
            "failures": failures, "coverage_basis_points": coverage,
        })
    parser_status = value["parser_status"]
    if parser_status not in {"complete", "malformed", "truncated", "not_applicable"}:
        _fail("invalid parser_status")
    exit_code = value["exit_code"]
    if exit_code is not None:
        exit_code = _integer(exit_code, "exit_code")
    schema_version = _integer(value["schema_version"], "schema_version", 1)
    if schema_version != SCHEMA_VERSION:
        _fail("unsupported schema_version")
    started = _timestamp(value["started_at"], "started_at")
    completed = _timestamp(value["completed_at"], "completed_at")
    if _parsed_timestamp(completed) < _parsed_timestamp(started):
        _fail("result time order invalid")
    return {
        "schema_version": schema_version,
        "lane_id": _string(value["lane_id"], "lane_id", pattern=_ID, maximum=128),
        "plan_digest": _string(value["plan_digest"], "plan_digest", pattern=_DIGEST),
        "status": status, "started_at": started, "completed_at": completed,
        "exit_code": exit_code,
        "command_digest": _string(value["command_digest"], "command_digest", pattern=_DIGEST),
        "evidence_refs": _unique_strings(value["evidence_refs"], "evidence ref"),
        "packages": sorted(packages, key=lambda item: item["package"]),
        "parser_status": parser_status,
        "parser_reason": _string(value["parser_reason"], "parser_reason", pattern=_ID, maximum=128, nullable=True),
    }


def compare_coverage(current, baseline, *, current_metadata, baseline_metadata):
    """Compare coverage only when all declared authority metadata matches."""
    required = {"packages", "command_digest", "tags", "coverage_mode", "profile_digest", "binding_digest"}
    if set(current_metadata) != required or set(baseline_metadata) != required:
        _fail("coverage metadata fields mismatch")
    if current_metadata != baseline_metadata or current is None or baseline is None:
        return {"status": "unavailable", "regression": None, "reason": "incomparable_baseline"}
    current = _number(current, "current coverage")
    baseline = _number(baseline, "baseline coverage")
    return {"status": "compared", "regression": current < baseline, "delta": current - baseline}
