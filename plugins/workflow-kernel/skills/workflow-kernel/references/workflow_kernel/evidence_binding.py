"""Exact build and evidence identity with pure stale-match reasons."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime

from .redaction import contains_high_confidence_secret, normalize_durable_string


SCHEMA_VERSION = 1
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_SHA = re.compile(r"[0-9a-f]{40,64}")
_FIELDS = frozenset({
    "schema_version", "commit_sha", "tree_digest", "tracked_diff_digest",
    "untracked_digest", "untracked_classification", "profile_digest",
    "plan_digest", "scenario_digest", "command_digest", "artifact_digest",
    "image_digest", "started_at", "completed_at", "exit_status",
    "evidence_digest", "binding_digest",
})
_MATCH_FIELDS = (
    ("commit_sha", "head_changed"),
    ("tree_digest", "tree_changed"),
    ("tracked_diff_digest", "tracked_diff_changed"),
    ("untracked_digest", "untracked_state_changed"),
    ("untracked_classification", "untracked_classification_changed"),
    ("profile_digest", "profile_changed"),
    ("plan_digest", "plan_changed"),
    ("scenario_digest", "scenario_changed"),
    ("command_digest", "command_changed"),
    ("artifact_digest", "artifact_changed"),
    ("image_digest", "image_changed"),
    ("exit_status", "exit_status_changed"),
    ("evidence_digest", "evidence_changed"),
)


def _fail(reason):
    raise ValueError(reason)


def _string(value, name, pattern=None, nullable=False):
    if nullable and value is None:
        return None
    if (
        type(value) is not str or not value or len(value) > 2048
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
    value = _string(value, name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail(f"invalid {name}")
    if parsed.tzinfo is None:
        _fail(f"invalid {name}")
    return value


def _canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def validate_evidence_binding(value):
    if type(value) is not dict or set(value) != _FIELDS:
        _fail("evidence binding fields mismatch")
    if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
        _fail("unsupported schema_version")
    exit_status = value["exit_status"]
    if exit_status is not None and (type(exit_status) is not int or exit_status < 0):
        _fail("invalid exit_status")
    classification = value["untracked_classification"]
    if classification not in {"none", "safe", "private", "mixed", "unknown"}:
        _fail("invalid untracked_classification")
    started = _timestamp(value["started_at"], "started_at")
    completed = _timestamp(value["completed_at"], "completed_at")
    if datetime.fromisoformat(completed.replace("Z", "+00:00")) < datetime.fromisoformat(started.replace("Z", "+00:00")):
        _fail("binding time order invalid")
    body = {
        "schema_version": SCHEMA_VERSION,
        "commit_sha": _string(value["commit_sha"], "commit_sha", _SHA),
        "tree_digest": _string(value["tree_digest"], "tree_digest", _DIGEST),
        "tracked_diff_digest": _string(value["tracked_diff_digest"], "tracked_diff_digest", _DIGEST),
        "untracked_digest": _string(value["untracked_digest"], "untracked_digest", _DIGEST),
        "untracked_classification": classification,
        "profile_digest": _string(value["profile_digest"], "profile_digest", _DIGEST),
        "plan_digest": _string(value["plan_digest"], "plan_digest", _DIGEST),
        "scenario_digest": _string(value["scenario_digest"], "scenario_digest", _DIGEST, nullable=True),
        "command_digest": _string(value["command_digest"], "command_digest", _DIGEST),
        "artifact_digest": _string(value["artifact_digest"], "artifact_digest", _DIGEST, nullable=True),
        "image_digest": _string(value["image_digest"], "image_digest", _DIGEST, nullable=True),
        "started_at": started, "completed_at": completed,
        "exit_status": exit_status,
        "evidence_digest": _string(value["evidence_digest"], "evidence_digest", _DIGEST),
    }
    expected = "sha256:" + hashlib.sha256(_canonical_bytes(body)).hexdigest()
    if value["binding_digest"] != expected:
        _fail("binding digest mismatch")
    body["binding_digest"] = expected
    return body


def build_evidence_binding(**fields):
    fields = dict(fields)
    fields["schema_version"] = SCHEMA_VERSION
    fields["binding_digest"] = ""
    body = dict(fields); body.pop("binding_digest")
    fields["binding_digest"] = "sha256:" + hashlib.sha256(_canonical_bytes(body)).hexdigest()
    return validate_evidence_binding(fields)


def match_evidence_binding(expected, current):
    expected = validate_evidence_binding(expected)
    current = validate_evidence_binding(current)
    reasons = [reason for field, reason in _MATCH_FIELDS if expected[field] != current[field]]
    if expected["started_at"] != current["started_at"] or expected["completed_at"] != current["completed_at"]:
        reasons.append("timing_changed")
    return {"matches": not reasons, "reasons": reasons}
