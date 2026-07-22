"""Exact artifact classification and staging allowlist facts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath

from ._files import _OwnedResourceScope, UnsafeFileError, bind_durable_path
from .redaction import contains_high_confidence_secret, normalize_durable_string


SCHEMA_VERSION = 1
MAX_ARTIFACT_BYTES = 4 * 1024 * 1024
MAX_ARTIFACTS = 4096
MAX_METADATA_ITEMS = 256
MAX_METADATA_BYTES = 256 * 1024
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_EMAIL = re.compile(r"(?i)(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![A-Za-z0-9.-])")
_AUTH = re.compile(r"(?i)(?:authorization\s*[:=]\s*(?:bearer|basic)\s+\S+|set-cookie\s*:|cookie\s*[:=])")
_PASSWORD = re.compile(r"(?i)(?:password|passwd|passphrase|api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*\S+")
_MFA = re.compile(r"(?i)(?:mfa|otp|totp|authenticator|qr[_-]?(?:code|secret))\s*[:=]\s*\S+")
_ENV = re.compile(r"(?m)^[A-Z][A-Z0-9_]{1,127}=\S+")
_PRIVATE_URL = re.compile(r"(?i)https?://(?:localhost|127(?:\.[0-9]{1,3}){3}|10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2}|[^/\s.]+\.(?:internal|local))(?:[:/]|$)")
_SENSITIVE_FILENAME = re.compile(r"(?i)(?:cookie|credential|password|passwd|private[_-]?key|authenticator|qr[_-]?secret|\.env(?:\.|$))")
_BLOCKING_RULES = frozenset({
    "high_confidence_secret", "cookie_or_authorization", "password_or_token",
    "mfa_qr_authenticator", "environment_value", "opaque_binary",
})
_PRIVATE_RULES = frozenset({"sensitive_filename", "private_url", "real_email"})
_CONTROL_BYTES = frozenset(range(0x20)) - {0x09, 0x0A, 0x0D}
_BINARY_SUFFIXES = frozenset({
    ".7z", ".avif", ".bmp", ".dmp", ".gif", ".gz", ".ico", ".jpeg", ".jpg",
    ".pdf", ".png", ".tar", ".tiff", ".trace", ".webp", ".zip",
})
_RECORD_FIELDS = frozenset({
    "schema_version", "path", "state", "source_path", "digest", "byte_count",
    "classification", "sensitivity", "lifecycle", "redaction_state", "provenance", "owner",
    "committable", "rule_ids", "record_digest",
})
_INTENT_FIELDS = frozenset({"operation", "path", "source_path", "expected_digest"})


def _fail(reason):
    raise ValueError(reason)


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


def _path_shape(value, name="artifact path", *, nullable=False):
    if nullable and value is None:
        return None
    if (
        type(value) is not str or not value or len(value) > 1024
        or any(ord(char) < 0x20 or ord(char) == 0x7f for char in value)
    ):
        _fail(f"invalid {name}")
    try:
        if normalize_durable_string(value) != value:
            _fail(f"unsafe {name}")
    except ValueError:
        _fail(f"unsafe {name}")
    if value is None:
        return None
    path = PurePosixPath(value)
    if (
        path.is_absolute() or value in {"", "."} or ".." in path.parts
        or "\\" in value or any(char in value for char in "*?[]{}")
        or path.as_posix() != value
    ):
        _fail(f"unsafe {name}")
    return value


def _fictional_email(match):
    domain = match.group(1).casefold()
    return domain.endswith((".test", ".example")) or domain in {"test", "example"}


def _path_is_sensitive(value):
    return bool(
        contains_high_confidence_secret(value)
        or any(not _fictional_email(match) for match in _EMAIL.finditer(value))
        or _AUTH.search(value) or _PASSWORD.search(value) or _MFA.search(value)
    )


def _path(value, name="artifact path", *, nullable=False):
    value = _path_shape(value, name, nullable=nullable)
    if value is not None and _path_is_sensitive(value):
        _fail(f"unsafe {name}")
    return value


def _digest(value, name, *, nullable=False):
    return _string(value, name, pattern=_DIGEST, maximum=71, nullable=nullable)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _content_digest(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _record_digest(value):
    return _content_digest(_canonical(value))


def _metadata_text(metadata):
    if metadata is None:
        return ""
    if type(metadata) is not dict or len(metadata) > MAX_METADATA_ITEMS:
        _fail("invalid artifact metadata")
    parts = []
    size = 0
    for key in sorted(metadata):
        key = _string(key, "metadata key", maximum=128)
        value = metadata[key]
        if (
            type(value) is not str or not value or len(value) > 4096
            or any(ord(char) < 0x20 and char not in "\n\r\t" for char in value)
        ):
            _fail("invalid metadata value")
        size += len(key.encode()) + len(value.encode())
        if size > MAX_METADATA_BYTES:
            _fail("artifact metadata exceeds size limit")
        parts.extend((key, value))
    return "\n".join(parts)


def _sensitive_rules(value, path, *, fixture_provenance):
    rules = []
    if _SENSITIVE_FILENAME.search(path):
        rules.append("sensitive_filename")
    if contains_high_confidence_secret(value):
        rules.append("high_confidence_secret")
    if _AUTH.search(value):
        rules.append("cookie_or_authorization")
    if _PASSWORD.search(value):
        rules.append("password_or_token")
    if _MFA.search(value):
        rules.append("mfa_qr_authenticator")
    if _PRIVATE_URL.search(value):
        rules.append("private_url")
    if _ENV.search(value):
        rules.append("environment_value")
    for match in _EMAIL.finditer(value):
        if not _fictional_email(match) or not fixture_provenance:
            rules.append("real_email")
            break
    return sorted(set(rules))


def _derived_sensitivity(rules):
    identities = set(rules)
    allowed = _BLOCKING_RULES | _PRIVATE_RULES | {
        "explicit_deletion", "classification_unavailable",
    }
    if not identities <= allowed:
        _fail("unknown artifact rule")
    if "explicit_deletion" in identities and identities != {"explicit_deletion"}:
        _fail("deletion rule contradicts artifact rules")
    if identities & _BLOCKING_RULES:
        return "blocked"
    if identities & _PRIVATE_RULES:
        return "private"
    if "classification_unavailable" in identities:
        return "unknown"
    return "safe"


def _looks_binary(raw, path):
    if PurePosixPath(path).suffix.casefold() in _BINARY_SUFFIXES:
        return True
    return any(byte in _CONTROL_BYTES for byte in raw)


def _validate_record(value):
    if type(value) is not dict or set(value) != _RECORD_FIELDS:
        _fail("artifact record fields mismatch")
    if type(value["schema_version"]) is not int or value["schema_version"] != SCHEMA_VERSION:
        _fail("unsupported schema_version")
    state = value["state"]
    if state not in {"present", "deleted"}:
        _fail("invalid artifact state")
    classification = value["classification"]
    if classification not in {"committable", "private_receipt", "ephemeral", "blocked_sensitive", "unknown"}:
        _fail("invalid artifact classification")
    sensitivity = value["sensitivity"]
    if sensitivity not in {"safe", "private", "blocked", "unknown"}:
        _fail("invalid artifact sensitivity")
    lifecycle = value["lifecycle"]
    if lifecycle not in {"durable", "run_scoped", "chunk_scoped"}:
        _fail("invalid artifact lifecycle")
    redaction = value["redaction_state"]
    if redaction not in {"not_required", "required", "redacted", "blocked"}:
        _fail("invalid redaction_state")
    if type(value["byte_count"]) is not int or value["byte_count"] < 0 or value["byte_count"] > MAX_ARTIFACT_BYTES:
        _fail("invalid byte_count")
    if type(value["committable"]) is not bool:
        _fail("invalid committable")
    rules = value["rule_ids"]
    if type(rules) is not list or len(rules) > MAX_METADATA_ITEMS:
        _fail("invalid rule_ids")
    rules = sorted(_string(item, "rule id", pattern=_ID, maximum=128) for item in rules)
    if len(rules) != len(set(rules)):
        _fail("duplicate rule id")
    body = {
        "schema_version": SCHEMA_VERSION, "path": _path(value["path"]),
        "state": state, "source_path": _path(value["source_path"], "source path", nullable=True),
        "digest": _digest(value["digest"], "artifact digest"), "byte_count": value["byte_count"],
        "classification": classification, "sensitivity": sensitivity,
        "lifecycle": lifecycle, "redaction_state": redaction,
        "provenance": _string(value["provenance"], "provenance", pattern=_ID, maximum=128),
        "owner": _string(value["owner"], "owner", pattern=_ID, maximum=128),
        "committable": value["committable"], "rule_ids": rules,
    }
    derived_sensitivity = _derived_sensitivity(rules)
    if sensitivity != derived_sensitivity:
        _fail("sensitivity contradicts artifact rules")
    allowed_redaction = {
        "safe": {"not_required"}, "private": {"required", "redacted"},
        "blocked": {"blocked"}, "unknown": {"required", "blocked"},
    }
    if redaction not in allowed_redaction[sensitivity]:
        _fail("redaction contradicts sensitivity")
    expected_classification = (
        "blocked_sensitive" if sensitivity == "blocked" else
        "private_receipt" if sensitivity == "private" else
        "unknown" if sensitivity == "unknown" else
        "committable" if lifecycle == "durable" else "ephemeral"
    )
    if classification != expected_classification:
        _fail("classification contradicts sensitivity or lifecycle")
    expected_committable = classification == "committable"
    if value["committable"] != expected_committable:
        _fail("committable state contradicts classification")
    if state == "deleted" and (value["byte_count"] != 0 or value["source_path"] is not None):
        _fail("invalid deleted artifact record")
    expected = _record_digest(body)
    if value["record_digest"] != expected:
        _fail("artifact record digest mismatch")
    body["record_digest"] = expected
    return body


def validate_artifact_record(value):
    return _validate_record(value)


def _make_record(*, path, state, source_path, digest, byte_count, sensitivity,
                 lifecycle, redaction_state, provenance, owner, rule_ids):
    classification = (
        "blocked_sensitive" if sensitivity == "blocked" else
        "private_receipt" if sensitivity == "private" else
        "unknown" if sensitivity == "unknown" else
        "committable" if lifecycle == "durable" else "ephemeral"
    )
    body = {
        "schema_version": SCHEMA_VERSION, "path": path, "state": state,
        "source_path": source_path, "digest": digest, "byte_count": byte_count,
        "classification": classification, "sensitivity": sensitivity, "lifecycle": lifecycle,
        "redaction_state": redaction_state, "provenance": provenance, "owner": owner,
        "committable": classification == "committable",
        "rule_ids": sorted(set(rule_ids)),
    }
    body["record_digest"] = _record_digest(body)
    return _validate_record(body)


def classify_artifact(repo_root, relative_path, *, lifecycle, provenance, owner,
                      metadata=None, source_path=None):
    """Classify one exact regular artifact without scanning its surroundings."""
    physical_path = _path_shape(relative_path)
    physical_source_path = _path_shape(source_path, "source path", nullable=True)
    path_rules = _sensitive_rules(
        physical_path, physical_path, fixture_provenance=provenance == "test_fixture",
    )
    source_rules = [] if physical_source_path is None else _sensitive_rules(
        physical_source_path, physical_source_path,
        fixture_provenance=provenance == "test_fixture",
    )
    relative_path = (
        _unsafe_path_reference(physical_path) if _path_is_sensitive(physical_path)
        else physical_path
    )
    source_path = (
        None if physical_source_path is None else
        _unsafe_path_reference(physical_source_path)
        if _path_is_sensitive(physical_source_path) else physical_source_path
    )
    provenance = _string(provenance, "provenance", pattern=_ID, maximum=128)
    owner = _string(owner, "owner", pattern=_ID, maximum=128)
    fixture = provenance == "test_fixture"
    root = Path(repo_root).resolve(strict=True)
    target = root / physical_path
    try:
        target.relative_to(root)
    except ValueError:
        _fail("unsafe artifact path")
    binding = bind_durable_path(target)
    chunks = []
    size = 0
    try:
        with _OwnedResourceScope() as owned:
            directory = owned.pin(binding)
            entry = os.stat(binding.path.name, dir_fd=directory.descriptor, follow_symlinks=False)
            if not stat.S_ISREG(entry.st_mode) or stat.S_ISLNK(entry.st_mode) or entry.st_nlink != 1:
                _fail("unsafe or missing artifact")
            descriptor = owned.own(directory.open_regular(binding.path.name, os.O_RDONLY))
            while True:
                chunk = os.read(descriptor, min(65_536, MAX_ARTIFACT_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk); size += len(chunk)
                if size > MAX_ARTIFACT_BYTES:
                    _fail("artifact exceeds size limit")
            directory.require_identity(descriptor, binding.path.name)
            directory.revalidate()
    except (FileNotFoundError, NotADirectoryError, UnsafeFileError, OSError):
        _fail("unsafe or missing artifact")
    raw = b"".join(chunks)
    digest = _content_digest(raw)
    metadata_text = _metadata_text(metadata)
    opaque = _looks_binary(raw, physical_path)
    if opaque:
        text = ""
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = ""
            opaque = True
    rules = sorted(set(
        path_rules + source_rules
        + _sensitive_rules(text + "\n" + metadata_text, physical_path, fixture_provenance=fixture)
    ))
    if opaque:
        rules.append("opaque_binary")
        rules = sorted(set(rules))
    if rules:
        sensitivity = _derived_sensitivity(rules)
        redaction = "blocked" if sensitivity == "blocked" else "required"
    else:
        sensitivity, redaction = "safe", "not_required"
    return _make_record(
        path=relative_path, state="present", source_path=source_path, digest=digest,
        byte_count=len(raw), sensitivity=sensitivity, lifecycle=lifecycle,
        redaction_state=redaction, provenance=provenance, owner=owner, rule_ids=rules,
    )


def deleted_artifact_record(path, previous_digest, *, provenance, owner):
    """Represent one exact intended deletion without treating absence as a scan."""
    return _make_record(
        path=_path(path), state="deleted", source_path=None,
        digest=_digest(previous_digest, "previous digest"), byte_count=0,
        sensitivity="safe", lifecycle="durable", redaction_state="not_required",
        provenance=_string(provenance, "provenance", pattern=_ID, maximum=128),
        owner=_string(owner, "owner", pattern=_ID, maximum=128),
        rule_ids=["explicit_deletion"],
    )


def _validate_intent(value):
    if type(value) is not dict or set(value) != _INTENT_FIELDS:
        _fail("intended change fields mismatch")
    operation = value["operation"]
    if operation not in {"add", "modify", "delete", "rename"}:
        _fail("invalid intended operation")
    source = _path(value["source_path"], "source path", nullable=True)
    if (operation == "rename") != (source is not None):
        _fail("invalid rename source")
    if source is not None and source == value["path"]:
        _fail("invalid rename source")
    return {
        "operation": operation, "path": _path(value["path"]), "source_path": source,
        "expected_digest": _digest(value["expected_digest"], "expected digest", nullable=True),
    }


def _unsafe_path_reference(value):
    raw = value if type(value) is str else repr(type(value).__name__)
    return "unsafe-path-sha256-" + hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()


def build_staging_allowlist(intended_changes, records, observed_digests):
    """Return the exact safe intersection of intent, classification, and state."""
    if type(intended_changes) is not list or len(intended_changes) > MAX_ARTIFACTS:
        _fail("invalid intended changes")
    if type(records) is not list or len(records) > MAX_ARTIFACTS:
        _fail("invalid artifact records")
    if type(observed_digests) is not dict or len(observed_digests) > MAX_ARTIFACTS:
        _fail("invalid observed digests")
    normalized_records = [_validate_record(item) for item in records]
    by_path = {}
    for record in normalized_records:
        if record["path"] in by_path:
            _fail("duplicate artifact path")
        by_path[record["path"]] = record
    observed = {}
    for raw_path, raw_digest in observed_digests.items():
        physical = _path_shape(raw_path)
        path = _unsafe_path_reference(physical) if _path_is_sensitive(physical) else physical
        observed[path] = _digest(raw_digest, "observed digest", nullable=True)
    intents = []
    unsafe_rejections = []
    for raw in intended_changes:
        if type(raw) is not dict or set(raw) != _INTENT_FIELDS:
            _fail("intended change fields mismatch")
        if raw["operation"] not in {"add", "modify", "delete", "rename"}:
            _fail("invalid intended operation")
        try:
            intents.append(_validate_intent(raw))
        except ValueError as error:
            if "path" not in str(error):
                raise
            unsafe_rejections.append({
                "operation": raw["operation"],
                "path": _unsafe_path_reference(raw.get("path")),
                "reason": "unsafe_path",
            })
    path_use_counts = {}
    for item in intents:
        path_use_counts[item["path"]] = path_use_counts.get(item["path"], 0) + 1
        if item["operation"] == "rename":
            source = item["source_path"]
            path_use_counts[source] = path_use_counts.get(source, 0) + 1
    conflicting_paths = {path for path, count in path_use_counts.items() if count > 1}
    authorized = []
    rejected = sorted(unsafe_rejections, key=lambda item: (item["path"], item["operation"]))
    for intent in sorted(intents, key=lambda item: (item["path"], item["operation"], item["source_path"] or "")):
        record = by_path.get(intent["path"])
        reason = (
            "conflicting_intent" if intent["path"] in conflicting_paths
            or intent["operation"] == "rename" and intent["source_path"] in conflicting_paths
            else None
        )
        if reason is None and record is None:
            reason = "unclassified"
        elif reason is None and record["classification"] == "private_receipt":
            reason = "private"
        elif reason is None and record["classification"] == "blocked_sensitive":
            reason = "blocked_sensitive"
        elif reason is None and record["classification"] == "unknown":
            reason = "unclassified"
        elif reason is None and record["classification"] == "ephemeral":
            reason = "ephemeral"
        elif reason is None and not record["committable"]:
            reason = "unclassified"
        elif reason is None and intent["operation"] == "delete":
            if intent["expected_digest"] is not None and intent["expected_digest"] != record["digest"]:
                reason = "stale_digest"
            elif record["state"] != "deleted" or observed.get(intent["path"]) is not None:
                reason = "stale_digest" if record["state"] == "deleted" else "missing"
        elif reason is None:
            actual = observed.get(intent["path"])
            if actual is None:
                reason = "missing"
            elif actual != record["digest"] or (intent["expected_digest"] is not None and actual != intent["expected_digest"]):
                reason = "stale_digest"
        if reason is None and intent["operation"] == "rename":
            source_record = by_path.get(intent["source_path"])
            if record["source_path"] != intent["source_path"]:
                reason = "unclassified"
            elif source_record is None or source_record["state"] != "deleted":
                reason = "unclassified"
            elif observed.get(intent["source_path"]) is not None:
                reason = "stale_digest"
        if reason is None:
            authorized.append(intent)
        else:
            rejected.append({"operation": intent["operation"], "path": intent["path"], "reason": reason})
    record_digests = sorted(item["record_digest"] for item in normalized_records)
    rejected = sorted(
        {(item["operation"], item["path"], item["reason"]): item for item in rejected}.values(),
        key=lambda item: (item["path"], item["operation"]),
    )
    body = {
        "schema_version": SCHEMA_VERSION, "record_digests": record_digests,
        "authorized": authorized, "rejected": rejected,
    }
    body["allowlist_digest"] = _record_digest(body)
    return body
