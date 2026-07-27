"""Neutral, deterministic inspection mechanics for repository-owned profiles.

Policy stays in profiles and their catalogs.  This module validates and freezes
that input, admits only digest-bound host-authorized Docker execution, and
produces canonical redacted data from which human-readable output is rendered.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

from .receipts import _canonical_bytes
from .redaction import (
    REDACTED, contains_high_confidence_secret, is_secret_key,
    normalize_durable_string, normalize_evidence_reference,
    sanitize_durable_payload,
)
PROFILE_SCHEMA_VERSION = 1
AUTHORITATIVE_SCHEMA_VERSION = 1
FIXED_EXECUTION_ENV = MappingProxyType({
    "PATH": "/usr/bin:/bin",
    "LANG": "C",
    "LC_ALL": "C",
    "TZ": "UTC",
})
EVIDENCE_STATUSES = frozenset({
    "available", "unavailable", "failed", "fallback", "skipped",
})
_IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")
_SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
_GIT_REF = re.compile(r"refs/(?:heads|tags)/[A-Za-z0-9][A-Za-z0-9._/-]{0,254}\Z")
_COMPOSE_IDENTITY = re.compile(r"([a-z0-9][a-z0-9._-]{0,127})@sha256:[0-9a-f]{64}\Z")
_IMAGE_IDENTITY = re.compile(r"[^@\s]+@sha256:[0-9a-f]{64}\Z")
_SHELL_TOKEN = re.compile(r"(?:\$\(|`|[;&|<>]|\r|\n)")
_PROFILE_FIELDS = frozenset({
    "schema_version", "profile_id", "profile_version", "repository",
    "catalogs", "surfaces", "metrics", "rules", "lanes", "classifications",
    "outputs", "trend_compatibility",
})
_ATTESTATION_FIELDS = frozenset({
    "schema_version", "repository_root", "profile_path", "profile_digest",
    "source", "ref", "commit", "dirty", "operator_authorization_event_id",
    "purpose",
})


class InspectionError(Exception):
    """Closed, stable inspection failure safe for process-boundary emission."""

    __slots__ = ("reason_code",)

    def __init__(self, reason_code):
        if type(reason_code) is not str or _IDENTIFIER.fullmatch(reason_code) is None:
            reason_code = "inspection_error"
        self.reason_code = reason_code
        super().__init__("inspection input rejected")


def _fail(reason_code, *, field=None):
    del field
    raise InspectionError(reason_code)


def _exact_object(value, fields, *, required=None, reason="invalid_object"):
    if type(value) is not dict:
        _fail(reason)
    keys = frozenset(value)
    required = fields if required is None else frozenset(required)
    if not required <= keys:
        _fail("missing_field", field=sorted(required - keys)[0])
    if not keys <= fields:
        _fail("unknown_key", field=sorted(keys - fields)[0])
    return value


def _exact_list(value, *, field):
    if type(value) is not list:
        _fail("wrong_type", field=field)
    return value


def _string(value, *, field, identifier=False):
    if type(value) is not str or not value:
        _fail("wrong_type", field=field)
    if identifier and _IDENTIFIER.fullmatch(value) is None:
        _fail("invalid_identifier", field=field)
    return value


def _integer(value, *, field, minimum=0, maximum=None):
    if type(value) is not int or value < minimum or (
        maximum is not None and value > maximum
    ):
        _fail("wrong_type", field=field)
    return value


def _unique_by_id(items, id_field, *, field):
    seen = set()
    for item in items:
        if type(item) is not dict:
            _fail("invalid_collection_item", field=field)
        identity = _string(item.get(id_field), field=f"{field}.{id_field}", identifier=True)
        if identity in seen:
            _fail("duplicate_id", field=f"{field}.{id_field}")
        seen.add(identity)
    return seen


def _duplicate_rejecting_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            _fail("duplicate_json_key", field=key)
        value[key] = item
    return value


def decode_json_bytes(raw):
    if type(raw) is not bytes or len(raw) > 16 * 1024 * 1024:
        _fail("invalid_json")
    try:
        return json.loads(
            raw.decode("utf-8"), object_pairs_hook=_duplicate_rejecting_object,
            parse_constant=lambda _value: _fail("invalid_json"),
        )
    except InspectionError:
        raise
    except (UnicodeError, json.JSONDecodeError):
        _fail("invalid_json")


def _freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value):
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _canonical_digest(value):
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _repository_root(value):
    try:
        root = Path(value).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        _fail("invalid_repository_root")
    if not root.is_dir():
        _fail("invalid_repository_root")
    return root


def normalize_owned_path(repository_root, value, *, must_exist=False):
    """Return a normalized repository-relative POSIX path."""
    root = _repository_root(repository_root)
    if type(value) is not str or not value or "\0" in value or "\\" in value:
        _fail("invalid_repository_path")
    candidate = Path(value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        _fail("invalid_repository_path")
    normalized = Path(*candidate.parts)
    try:
        resolved = (root / normalized).resolve(strict=must_exist)
    except (OSError, RuntimeError, ValueError):
        _fail("invalid_repository_path")
    if not resolved.is_relative_to(root):
        _fail("repository_path_escape")
    return normalized.as_posix()


def _validate_catalogs(catalogs):
    fields = frozenset({
        "catalog_id", "schema_version", "catalog_version", "source_reference",
        "content_digest", "rules", "metrics",
    })
    rule_fields = frozenset({"rule_id", "definition"})
    metric_fields = frozenset({"metric_id", "definition"})
    catalog_ids = _unique_by_id(catalogs, "catalog_id", field="catalogs")
    catalog_index = {}
    all_rule_ids = set()
    all_metric_ids = set()
    for catalog in catalogs:
        _exact_object(catalog, fields, reason="invalid_catalog")
        catalog_id = catalog["catalog_id"]
        if type(catalog["schema_version"]) is not int or catalog["schema_version"] != 1:
            _fail("unsupported_catalog_schema", field=catalog_id)
        version = _string(catalog["catalog_version"], field="catalog_version")
        if _SEMVER.fullmatch(version) is None:
            _fail("invalid_catalog_version", field=catalog_id)
        try:
            source = normalize_evidence_reference(catalog["source_reference"])
        except (TypeError, ValueError):
            _fail("invalid_catalog_source", field=catalog_id)
        catalog["source_reference"] = source
        rules = _exact_list(catalog["rules"], field="catalog.rules")
        metrics = _exact_list(catalog["metrics"], field="catalog.metrics")
        for item in rules:
            _exact_object(item, rule_fields, reason="invalid_catalog_rule")
            if type(item["definition"]) is not dict:
                _fail("invalid_catalog_rule", field=item.get("rule_id"))
        for item in metrics:
            _exact_object(item, metric_fields, reason="invalid_catalog_metric")
            if type(item["definition"]) is not dict:
                _fail("invalid_catalog_metric", field=item.get("metric_id"))
        rule_ids = _unique_by_id(rules, "rule_id", field="catalog.rules")
        metric_ids = _unique_by_id(metrics, "metric_id", field="catalog.metrics")
        if all_rule_ids & rule_ids or all_metric_ids & metric_ids:
            _fail("duplicate_catalog_member_id", field=catalog_id)
        all_rule_ids |= rule_ids
        all_metric_ids |= metric_ids
        projection = {
            key: catalog[key] for key in (
                "catalog_id", "schema_version", "catalog_version",
                "source_reference", "rules", "metrics",
            )
        }
        digest = _canonical_digest(projection)
        if type(catalog["content_digest"]) is not str or catalog["content_digest"] != digest:
            _fail("catalog_digest_mismatch", field=catalog_id)
        catalog_index[catalog_id] = {
            "version": version, "digest": digest,
            "rules": rule_ids, "metrics": metric_ids,
        }
    return catalog_ids, catalog_index


def _validate_bindings(items, *, kind, id_field, catalog_index):
    fields = (
        frozenset({id_field, "catalog_id", "catalog_version", "catalog_digest"})
        if kind == "metric"
        else frozenset({
            id_field, "catalog_id", "catalog_version", "catalog_digest",
            "metric_ids", "surface_ids",
        })
    )
    identities = _unique_by_id(items, id_field, field=kind + "s")
    for item in items:
        _exact_object(item, fields, reason=f"invalid_{kind}")
        catalog_id = _string(item["catalog_id"], field="catalog_id", identifier=True)
        catalog = catalog_index.get(catalog_id)
        if catalog is None:
            _fail("unknown_catalog_reference", field=catalog_id)
        if (
            item["catalog_version"] != catalog["version"]
            or item["catalog_digest"] != catalog["digest"]
        ):
            _fail("catalog_binding_mismatch", field=item[id_field])
        if item[id_field] not in catalog[kind + "s"]:
            _fail(f"unknown_{kind}_reference", field=item[id_field])
    return identities


def _validate_lane_argv(lane, repository_root):
    argv = _exact_list(lane["argv"], field="lane.argv")
    if not argv or any(type(arg) is not str or not arg for arg in argv):
        _fail("invalid_lane_argv", field=lane["lane_id"])
    if argv[0] != "docker":
        _fail("untrusted_executable", field=lane["lane_id"])
    expected = ["docker", "run"] if lane["execution_type"] == "docker" else ["docker", "compose"]
    if argv[:2] != expected:
        _fail("invalid_lane_argv", field=lane["lane_id"])
    prohibited = {
        "sh", "bash", "zsh", "-c", "--env", "--env-file", "-e",
        "--volume", "-v", "--mount", "--privileged", "--entrypoint",
        "--network=host", "--pid=host", "--userns=host",
    }
    if any(
        arg in prohibited
        or arg.startswith((
            "-e", "--env=", "--volume=", "--mount=", "--entrypoint=",
            "--device", "--cap-add", "--security-opt", "--network",
            "--pid", "--userns",
        ))
        or "docker.sock" in arg
        or _SHELL_TOKEN.search(arg)
        for arg in argv
    ):
        _fail("shell_or_environment_authority", field=lane["lane_id"])
    if lane["execution_type"] == "docker":
        index = 2
        allowed_flags = {"--rm", "--pull=never", "--read-only", "--no-healthcheck"}
        while index < len(argv) and argv[index] in allowed_flags:
            index += 1
        if index >= len(argv) or argv[index] != lane["image_identity"]:
            _fail("lane_identity_mismatch", field=lane["lane_id"])
    else:
        index = 2
        while index < len(argv) and argv[index] in {"-f", "--file"}:
            if index + 1 >= len(argv):
                _fail("invalid_lane_argv", field=lane["lane_id"])
            normalize_owned_path(repository_root, argv[index + 1], must_exist=True)
            index += 2
        if index >= len(argv) or argv[index] != "run":
            _fail("invalid_lane_argv", field=lane["lane_id"])
        index += 1
        while index < len(argv) and argv[index] in {"--rm", "--no-deps"}:
            index += 1
        match = _COMPOSE_IDENTITY.fullmatch(lane["service_identity"])
        if match is None or index >= len(argv) or argv[index] != match.group(1):
            _fail("lane_identity_mismatch", field=lane["lane_id"])


def _validate_profile_document(document, repository_root):
    _exact_object(document, _PROFILE_FIELDS, reason="invalid_profile")
    if (
        type(document["schema_version"]) is not int
        or document["schema_version"] != PROFILE_SCHEMA_VERSION
    ):
        _fail("unsupported_schema_version", field="schema_version")
    _string(document["profile_id"], field="profile_id", identifier=True)
    version = _string(document["profile_version"], field="profile_version")
    if _SEMVER.fullmatch(version) is None:
        _fail("invalid_profile_version", field="profile_version")

    repository = _exact_object(
        document["repository"], frozenset({"scope_paths"}), reason="invalid_repository",
    )
    repository["scope_paths"] = sorted({
        normalize_owned_path(repository_root, path)
        for path in _exact_list(repository["scope_paths"], field="repository.scope_paths")
    })

    catalogs = _exact_list(document["catalogs"], field="catalogs")
    _catalog_ids, catalog_index = _validate_catalogs(catalogs)

    surfaces = _exact_list(document["surfaces"], field="surfaces")
    surface_fields = frozenset({"surface_id", "paths"})
    surface_ids = _unique_by_id(surfaces, "surface_id", field="surfaces")
    for surface in surfaces:
        _exact_object(surface, surface_fields, reason="invalid_surface")
        surface["paths"] = sorted({
            normalize_owned_path(repository_root, path)
            for path in _exact_list(surface["paths"], field="surface.paths")
        })

    metrics = _exact_list(document["metrics"], field="metrics")
    metric_ids = _validate_bindings(
        metrics, kind="metric", id_field="metric_id", catalog_index=catalog_index,
    )
    rules = _exact_list(document["rules"], field="rules")
    rule_ids = _validate_bindings(
        rules, kind="rule", id_field="rule_id", catalog_index=catalog_index,
    )
    for rule in rules:
        linked_metrics = set(_exact_list(rule["metric_ids"], field="rule.metric_ids"))
        linked_surfaces = set(_exact_list(rule["surface_ids"], field="rule.surface_ids"))
        if not linked_metrics <= metric_ids:
            _fail("unknown_metric_reference", field=rule["rule_id"])
        if not linked_surfaces <= surface_ids:
            _fail("unknown_surface_reference", field=rule["rule_id"])
        rule["metric_ids"] = sorted(linked_metrics)
        rule["surface_ids"] = sorted(linked_surfaces)

    lane_fields = frozenset({
        "lane_id", "execution_type", "argv", "tool_identity", "image_identity",
        "service_identity", "plugin_version", "timeout_seconds",
        "primary_lane_id", "evidence_paths",
    })
    lanes = _exact_list(document["lanes"], field="lanes")
    lane_ids = _unique_by_id(lanes, "lane_id", field="lanes")
    for lane in lanes:
        _exact_object(lane, lane_fields, reason="invalid_lane")
        if lane["execution_type"] not in {"docker", "compose"}:
            _fail("unknown_execution_type", field=lane["lane_id"])
        identity = _string(lane["tool_identity"], field="tool_identity")
        if not identity.startswith("docker:") or _SEMVER.fullmatch(identity[7:]) is None:
            _fail("unpinned_tool_identity", field=lane["lane_id"])
        for field in ("image_identity", "service_identity"):
            if lane[field] is not None and type(lane[field]) is not str:
                _fail("wrong_type", field=field)
        if lane["execution_type"] == "docker":
            image = _string(lane["image_identity"], field="image_identity")
            if "@sha256:" not in image and (
                ":" not in image or image.endswith(":latest")
            ):
                _fail("unpinned_image_identity", field=lane["lane_id"])
            if lane["service_identity"] is not None:
                _fail("invalid_lane_identity", field=lane["lane_id"])
        else:
            service = _string(lane["service_identity"], field="service_identity")
            if _COMPOSE_IDENTITY.fullmatch(service) is None:
                _fail("unpinned_service_identity", field=lane["lane_id"])
            if lane["image_identity"] is not None:
                _fail("invalid_lane_identity", field=lane["lane_id"])
        plugin_version = _string(lane["plugin_version"], field="plugin_version")
        if _SEMVER.fullmatch(plugin_version) is None:
            _fail("invalid_plugin_version", field=lane["lane_id"])
        _integer(lane["timeout_seconds"], field="timeout_seconds", minimum=1, maximum=86400)
        lane["evidence_paths"] = sorted({
            normalize_owned_path(repository_root, path)
            for path in _exact_list(lane["evidence_paths"], field="evidence_paths")
        })
        _validate_lane_argv(lane, repository_root)
    for lane in lanes:
        primary = lane["primary_lane_id"]
        if primary is not None:
            if type(primary) is not str or primary not in lane_ids or primary == lane["lane_id"]:
                _fail("invalid_fallback_relationship", field=lane["lane_id"])
            target = next(item for item in lanes if item["lane_id"] == primary)
            if target["primary_lane_id"] is not None:
                _fail("fallback_chain_forbidden", field=lane["lane_id"])

    classification_fields = frozenset({
        "classification_id", "rule_ids", "metric_ids", "surface_ids", "confidence",
    })
    classifications = _exact_list(document["classifications"], field="classifications")
    _unique_by_id(classifications, "classification_id", field="classifications")
    for item in classifications:
        _exact_object(item, classification_fields, reason="invalid_classification")
        if item["confidence"] not in {"high", "medium", "low", "unknown"}:
            _fail("unknown_confidence", field=item["classification_id"])
        for field, known in (
            ("rule_ids", rule_ids), ("metric_ids", metric_ids),
            ("surface_ids", surface_ids),
        ):
            values = set(_exact_list(item[field], field=f"classification.{field}"))
            if not values <= known:
                _fail("unknown_classification_reference", field=item["classification_id"])
            item[field] = sorted(values)

    outputs = _exact_object(
        document["outputs"], frozenset({"authoritative_json", "markdown"}),
        reason="invalid_outputs",
    )
    outputs["authoritative_json"] = normalize_owned_path(
        repository_root, outputs["authoritative_json"],
    )
    outputs["markdown"] = normalize_owned_path(repository_root, outputs["markdown"])
    trend = _exact_object(
        document["trend_compatibility"],
        frozenset({"schema_version", "required_identity_fields"}),
        reason="invalid_trend_compatibility",
    )
    if type(trend["schema_version"]) is not int or trend["schema_version"] != 1:
        _fail("unsupported_trend_schema")
    required = set(_exact_list(
        trend["required_identity_fields"], field="trend_compatibility.required_identity_fields",
    ))
    mandatory = {"profile", "metric_definitions", "tool_identities"}
    if required != mandatory:
        _fail("incomplete_trend_identity")

    for field in ("catalogs", "surfaces", "metrics", "rules", "lanes", "classifications"):
        key = field[:-1] + "_id" if field != "classifications" else "classification_id"
        if field == "catalogs":
            key = "catalog_id"
        document[field].sort(key=lambda item: item[key])
    return document


@dataclass(frozen=True, slots=True)
class InspectionProfile:
    """One immutable validated profile snapshot and its observed source identity."""

    document: Mapping
    canonical_bytes: bytes
    digest: str
    repository_root: Path
    profile_path: str
    source_identity: tuple

    def to_dict(self):
        return _thaw(self.document)


def validate_inspection_profile(document, repository_root, *, profile_path="profile.json"):
    root = _repository_root(repository_root)
    path = normalize_owned_path(root, profile_path)
    if type(document) is not dict:
        _fail("invalid_profile")
    try:
        mutable = json.loads(json.dumps(document, allow_nan=False))
    except (TypeError, ValueError):
        _fail("wrong_type")
    validated = _validate_profile_document(mutable, root)
    canonical = _canonical_bytes(validated)
    return InspectionProfile(
        _freeze(validated), canonical,
        "sha256:" + hashlib.sha256(canonical).hexdigest(),
        root, path, (),
    )


def load_inspection_profile(profile_path, repository_root):
    root = _repository_root(repository_root)
    path = Path(profile_path)
    if path.is_absolute():
        try:
            relative = path.resolve(strict=True).relative_to(root).as_posix()
        except (OSError, RuntimeError, ValueError):
            _fail("profile_outside_repository")
    else:
        relative = normalize_owned_path(root, str(path), must_exist=True)
        path = root / relative
    try:
        lexical = path if path.is_absolute() else root / path
        if lexical.is_symlink():
            _fail("profile_symlink_forbidden")
        descriptor = os.open(lexical, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            before = os.fstat(descriptor)
            raw = b""
            while True:
                chunk = os.read(descriptor, 65536)
                if not chunk:
                    break
                raw += chunk
                if len(raw) > 16 * 1024 * 1024:
                    _fail("profile_size_limit")
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
    except InspectionError:
        raise
    except OSError:
        _fail("profile_read_failed")
    identity = (
        after.st_dev, after.st_ino, after.st_size,
        after.st_mtime_ns, after.st_ctime_ns,
    )
    if identity != (
        before.st_dev, before.st_ino, before.st_size,
        before.st_mtime_ns, before.st_ctime_ns,
    ):
        _fail("profile_digest_mismatch")
    profile = validate_inspection_profile(
        decode_json_bytes(raw), root, profile_path=relative,
    )
    return InspectionProfile(
        profile.document, profile.canonical_bytes, profile.digest,
        root, relative, identity,
    )


def _profile_source_unchanged(profile):
    if not profile.source_identity:
        return
    try:
        stat_result = os.stat(
            profile.repository_root / profile.profile_path, follow_symlinks=False,
        )
    except OSError:
        _fail("profile_digest_mismatch")
    current = (
        stat_result.st_dev, stat_result.st_ino,
        stat_result.st_size, stat_result.st_mtime_ns, stat_result.st_ctime_ns,
    )
    if current != profile.source_identity or stat_result.st_mode & 0o170000 != 0o100000:
        _fail("profile_digest_mismatch")


def validate_host_attestation(attestation, profile, *, source, ref, commit, dirty, purpose):
    _exact_object(attestation, _ATTESTATION_FIELDS, reason="invalid_attestation")
    if (
        type(attestation["schema_version"]) is not int
        or attestation["schema_version"] != 1
    ):
        _fail("unsupported_attestation_schema")
    if type(dirty) is not bool or type(attestation["dirty"]) is not bool:
        _fail("invalid_attestation_binding", field="dirty")
    expected = {
        "repository_root": str(profile.repository_root),
        "profile_path": profile.profile_path,
        "profile_digest": profile.digest,
        "source": source,
        "ref": ref,
        "commit": commit,
        "dirty": dirty,
        "purpose": purpose,
    }
    for field, value in expected.items():
        if type(attestation[field]) is not type(value) or attestation[field] != value:
            reason = "profile_digest_mismatch" if field == "profile_digest" else "attestation_binding_mismatch"
            _fail(reason, field=field)
    if source != "git" or type(ref) is not str or _GIT_REF.fullmatch(ref) is None:
        _fail("unverified_repository_source")
    if type(commit) is not str or _COMMIT.fullmatch(commit) is None:
        _fail("invalid_commit_binding")
    _string(
        attestation["operator_authorization_event_id"],
        field="operator_authorization_event_id", identifier=True,
    )
    _string(purpose, field="purpose", identifier=True)
    return MappingProxyType(dict(attestation))


def load_host_attestation(path, repository_root):
    root = _repository_root(repository_root)
    candidate = Path(path).resolve(strict=True)
    if candidate.is_relative_to(root):
        _fail("repository_controlled_attestation")
    if Path(path).is_symlink() or not candidate.is_file():
        _fail("untrusted_attestation_channel")
    try:
        return decode_json_bytes(candidate.read_bytes())
    except OSError:
        _fail("attestation_read_failed")


def _redact_durable(value):
    redacted = 0
    if type(value) is dict:
        result = {}
        for key, item in value.items():
            if type(key) is str and is_secret_key(key):
                result[key] = REDACTED
                redacted += 1
            else:
                result[key], count = _redact_durable(item)
                redacted += count
        return result, redacted
    if type(value) is list:
        result = []
        for item in value:
            safe, count = _redact_durable(item)
            result.append(safe)
            redacted += count
        return result, redacted
    if type(value) is str and contains_high_confidence_secret(value):
        return REDACTED, 1
    return sanitize_durable_payload(value), 0


def classify_observations(profile, observations):
    if type(profile) is not InspectionProfile:
        _fail("validated_profile_required")
    if type(observations) is not list:
        _fail("invalid_observations")
    document = profile.to_dict()
    surfaces = {item["surface_id"]: item for item in document["surfaces"]}
    metrics = {item["metric_id"] for item in document["metrics"]}
    rules = {item["rule_id"] for item in document["rules"]}
    classifications = {
        item["classification_id"]: item for item in document["classifications"]
    }
    results = []
    for index, raw in enumerate(observations):
        safe_raw, redacted = _redact_durable(raw)
        reason = None
        normalized_evidence = []
        if type(raw) is not dict or raw.get("schema_version") != 1:
            reason = "unknown_observation_schema"
        else:
            required = {
                "schema_version", "observation_id", "surface_id", "rule_id",
                "metric_id", "path", "classification_id", "evidence_status",
                "evidence_references", "raw_telemetry",
            }
            if set(raw) != required:
                reason = "invalid_observation_shape"
            elif raw["surface_id"] not in surfaces:
                reason = "unknown_surface"
            elif raw["metric_id"] not in metrics:
                reason = "unknown_metric"
            elif raw["rule_id"] not in rules:
                reason = "unknown_rule"
            elif raw["classification_id"] not in classifications:
                reason = "unknown_classification"
            elif raw["evidence_status"] not in EVIDENCE_STATUSES:
                reason = "unknown_evidence_status"
            else:
                try:
                    path = normalize_owned_path(profile.repository_root, raw["path"])
                    references = raw["evidence_references"]
                    if (
                        type(references) is not list
                        or any(type(reference) is not str for reference in references)
                    ):
                        raise ValueError("invalid evidence reference list")
                    normalized_evidence = [
                        normalize_evidence_reference(reference)
                        for reference in references
                    ]
                except (InspectionError, TypeError, ValueError):
                    reason = "unknown_path"
                else:
                    if path not in surfaces[raw["surface_id"]]["paths"]:
                        reason = "unknown_path"
        if reason is None:
            declared = classifications[raw["classification_id"]]
            if (
                raw["rule_id"] not in declared["rule_ids"]
                or raw["metric_id"] not in declared["metric_ids"]
                or raw["surface_id"] not in declared["surface_ids"]
            ):
                reason = "classification_binding_mismatch"
        results.append({
            "observation_id": (
                raw.get("observation_id")
                if type(raw) is dict and type(raw.get("observation_id")) is str
                else f"unknown-{index:04d}"
            ),
            "surface_id": raw.get("surface_id") if type(raw) is dict else None,
            "rule_id": raw.get("rule_id") if type(raw) is dict else None,
            "metric_id": raw.get("metric_id") if type(raw) is dict else None,
            "classification": "fail_closed" if reason else raw["classification_id"],
            "confidence": "unknown" if reason else classifications[
                raw["classification_id"]
            ]["confidence"],
            "actionable": reason is not None,
            "reason_code": reason or "classified",
            "evidence_status": (
                raw.get("evidence_status")
                if type(raw) is dict and raw.get("evidence_status") in EVIDENCE_STATUSES
                else "failed"
            ),
            "evidence_references": normalized_evidence,
            "raw_telemetry": (
                safe_raw.get("raw_telemetry", {})
                if type(safe_raw) is dict else safe_raw
            ),
            "redacted_values": redacted,
        })
    return sorted(results, key=lambda item: item["observation_id"])


class SubprocessAdapter:
    """Injectable shell-free subprocess boundary."""

    def run(self, argv, *, cwd, env, timeout):
        return subprocess.run(
            tuple(argv), cwd=cwd, env=dict(env), timeout=timeout,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, shell=False, check=False,
        )


def _timestamp(clock):
    value = clock()
    if type(value) is datetime:
        if value.tzinfo is None:
            _fail("invalid_invocation_time")
        value = value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return normalize_durable_string(value)


def _attempt(lane, adapter, root, clock, *, fallback_reason=None):
    started = _timestamp(clock)
    reason = "completed"
    try:
        completed = adapter.run(
            tuple(lane["argv"]), cwd=root, env=FIXED_EXECUTION_ENV,
            timeout=lane["timeout_seconds"],
        )
        exit_code = completed.returncode
        if type(exit_code) is not int:
            _fail("invalid_adapter_result")
        if exit_code == 0:
            status = "fallback" if fallback_reason else "available"
            reason = fallback_reason or "completed"
        elif exit_code in {125, 126, 127}:
            status, reason = "unavailable", "runtime_unavailable"
        else:
            status, reason = "failed", "nonzero_exit"
        stdout, stdout_redacted = _redact_durable(completed.stdout)
        stderr, stderr_redacted = _redact_durable(completed.stderr)
    except (OSError, subprocess.TimeoutExpired):
        status = "unavailable"
        reason = "runtime_unavailable"
        exit_code = None
        stdout = stderr = ""
        stdout_redacted = stderr_redacted = 0
    finished = _timestamp(clock)
    return {
        "lane_id": lane["lane_id"],
        "status": status,
        "reason_code": reason,
        "primary_lane_id": lane["primary_lane_id"],
        "argv_identity": _canonical_digest({"argv": lane["argv"]}),
        "tool_identity": lane["tool_identity"],
        "image_identity": lane["image_identity"],
        "service_identity": lane["service_identity"],
        "plugin_version": lane["plugin_version"],
        "timeout_seconds": lane["timeout_seconds"],
        "started_at": started,
        "finished_at": finished,
        "exit_code": exit_code,
        "evidence_references": list(lane["evidence_paths"]),
        "stdout": stdout,
        "stderr": stderr,
        "redacted_values": stdout_redacted + stderr_redacted,
    }


def execute_inspection_lanes(profile, lane_ids, attestation, *, source, ref, commit,
                             dirty, purpose, adapter=None, clock=None,
                             pre_admission_hook=None):
    """Admit and execute selected primary lanes from one immutable snapshot."""
    if type(profile) is not InspectionProfile or not profile.source_identity:
        _fail("loaded_profile_required")
    if type(lane_ids) not in {list, tuple} or not lane_ids:
        _fail("lane_selection_required")
    document = profile.to_dict()
    lanes = {item["lane_id"]: item for item in document["lanes"]}
    if any(type(item) is not str or item not in lanes for item in lane_ids):
        _fail("unknown_lane_id")
    if len(set(lane_ids)) != len(lane_ids):
        _fail("duplicate_lane_id")
    if any(lanes[item]["primary_lane_id"] is not None for item in lane_ids):
        _fail("fallback_requires_primary")
    validate_host_attestation(
        attestation, profile, source=source, ref=ref, commit=commit,
        dirty=dirty, purpose=purpose,
    )
    if pre_admission_hook is not None:
        pre_admission_hook()
    _profile_source_unchanged(profile)

    adapter = SubprocessAdapter() if adapter is None else adapter
    clock = (
        (lambda: datetime.now(timezone.utc))
        if clock is None else clock
    )
    fallbacks = {}
    for lane in document["lanes"]:
        if lane["primary_lane_id"] is not None:
            fallbacks.setdefault(lane["primary_lane_id"], []).append(lane)
    receipts = []
    for lane_id in lane_ids:
        primary = lanes[lane_id]
        receipt = _attempt(primary, adapter, profile.repository_root, clock)
        receipts.append(receipt)
        candidates = sorted(fallbacks.get(lane_id, ()), key=lambda item: item["lane_id"])
        if receipt["status"] == "available":
            for fallback in candidates:
                receipts.append({
                    "lane_id": fallback["lane_id"], "status": "skipped",
                    "reason_code": "primary_available", "primary_lane_id": lane_id,
                    "argv_identity": _canonical_digest({"argv": fallback["argv"]}),
                    "tool_identity": fallback["tool_identity"],
                    "image_identity": fallback["image_identity"],
                    "service_identity": fallback["service_identity"],
                    "plugin_version": fallback["plugin_version"],
                    "timeout_seconds": fallback["timeout_seconds"],
                    "started_at": None, "finished_at": None, "exit_code": None,
                    "evidence_references": list(fallback["evidence_paths"]),
                    "stdout": "", "stderr": "", "redacted_values": 0,
                })
            continue
        fallback_reason = (
            "primary_unavailable"
            if receipt["status"] == "unavailable" else "primary_failed"
        )
        fallback_succeeded = False
        for fallback in candidates:
            if fallback_succeeded:
                receipts.append({
                    "lane_id": fallback["lane_id"], "status": "skipped",
                    "reason_code": "earlier_fallback_available",
                    "primary_lane_id": lane_id,
                    "argv_identity": _canonical_digest({"argv": fallback["argv"]}),
                    "tool_identity": fallback["tool_identity"],
                    "image_identity": fallback["image_identity"],
                    "service_identity": fallback["service_identity"],
                    "plugin_version": fallback["plugin_version"],
                    "timeout_seconds": fallback["timeout_seconds"],
                    "started_at": None, "finished_at": None, "exit_code": None,
                    "evidence_references": list(fallback["evidence_paths"]),
                    "stdout": "", "stderr": "", "redacted_values": 0,
                })
                continue
            fallback_receipt = _attempt(
                fallback, adapter, profile.repository_root, clock,
                fallback_reason=fallback_reason,
            )
            receipts.append(fallback_receipt)
            if fallback_receipt["status"] == "fallback":
                fallback_succeeded = True
    return receipts


def _compatibility_identity(profile):
    document = profile.to_dict()
    return {
        "schema_version": AUTHORITATIVE_SCHEMA_VERSION,
        "profile": {
            "profile_id": document["profile_id"],
            "profile_version": document["profile_version"],
            "profile_digest": profile.digest,
        },
        "metric_definitions": [
            {
                "metric_id": item["metric_id"],
                "catalog_id": item["catalog_id"],
                "catalog_version": item["catalog_version"],
                "catalog_digest": item["catalog_digest"],
            }
            for item in document["metrics"]
        ],
        "tool_identities": [
            {
                "lane_id": item["lane_id"],
                "tool_identity": item["tool_identity"],
                "image_identity": item["image_identity"],
                "service_identity": item["service_identity"],
                "plugin_version": item["plugin_version"],
            }
            for item in document["lanes"]
        ],
    }


def stable_projection(result):
    receipts = []
    for receipt in result["lane_receipts"]:
        receipts.append({
            key: value for key, value in receipt.items()
            if key not in {"started_at", "finished_at", "stdout", "stderr"}
        })
    return {
        "schema_version": result["schema_version"],
        "result_type": result["result_type"],
        "repository": result["repository"],
        "profile": result["profile"],
        "compatibility_identity": result["compatibility_identity"],
        "observations": result["observations"],
        "lane_receipts": receipts,
        "redaction": result["redaction"],
    }


def build_authoritative_result(profile, *, source, ref, commit, dirty,
                               observations, lane_receipts, invocation):
    if type(profile) is not InspectionProfile:
        _fail("validated_profile_required")
    if type(dirty) is not bool or type(commit) is not str or _COMMIT.fullmatch(commit) is None:
        _fail("invalid_repository_provenance")
    classified = classify_observations(profile, observations)
    redacted_count = sum(item["redacted_values"] for item in classified)
    redacted_count += sum(item.get("redacted_values", 0) for item in lane_receipts)
    result = {
        "schema_version": AUTHORITATIVE_SCHEMA_VERSION,
        "result_type": "inspection_authoritative",
        "repository": {
            "source": source, "ref": ref, "commit": commit, "dirty": dirty,
        },
        "profile": {
            "profile_id": profile.document["profile_id"],
            "profile_version": profile.document["profile_version"],
            "profile_digest": profile.digest,
            "profile_path": profile.profile_path,
        },
        "compatibility_identity": _compatibility_identity(profile),
        "observations": classified,
        "lane_receipts": lane_receipts,
        "invocation": invocation,
        "redaction": {
            "applied": redacted_count > 0,
            "redacted_value_count": redacted_count,
        },
    }
    result["stable_projection_digest"] = _canonical_digest(stable_projection(result))
    return validate_authoritative_result(result)


def validate_authoritative_result(result):
    fields = frozenset({
        "schema_version", "result_type", "repository", "profile",
        "compatibility_identity", "observations", "lane_receipts", "invocation",
        "redaction", "stable_projection_digest",
    })
    _exact_object(result, fields, reason="invalid_authoritative_result")
    if (
        type(result["schema_version"]) is not int
        or result["schema_version"] != AUTHORITATIVE_SCHEMA_VERSION
        or result["result_type"] != "inspection_authoritative"
    ):
        _fail("unsupported_authoritative_schema")
    repository = _exact_object(
        result["repository"], frozenset({"source", "ref", "commit", "dirty"}),
        reason="invalid_authoritative_repository",
    )
    if (
        repository["source"] != "git"
        or type(repository["ref"]) is not str
        or _GIT_REF.fullmatch(repository["ref"]) is None
        or type(repository["commit"]) is not str
        or _COMMIT.fullmatch(repository["commit"]) is None
        or type(repository["dirty"]) is not bool
    ):
        _fail("invalid_authoritative_repository")
    profile = _exact_object(
        result["profile"],
        frozenset({"profile_id", "profile_version", "profile_digest", "profile_path"}),
        reason="invalid_authoritative_profile",
    )
    _string(profile["profile_id"], field="profile_id", identifier=True)
    if (
        type(profile["profile_version"]) is not str
        or _SEMVER.fullmatch(profile["profile_version"]) is None
        or type(profile["profile_digest"]) is not str
        or _DIGEST.fullmatch(profile["profile_digest"]) is None
    ):
        _fail("invalid_authoritative_profile")
    try:
        if normalize_evidence_reference(profile["profile_path"]) != profile["profile_path"]:
            _fail("invalid_authoritative_profile")
    except (TypeError, ValueError):
        _fail("invalid_authoritative_profile")
    compatibility = _exact_object(
        result["compatibility_identity"],
        frozenset({"schema_version", "profile", "metric_definitions", "tool_identities"}),
        reason="invalid_compatibility_identity",
    )
    if (
        type(compatibility["schema_version"]) is not int
        or compatibility["schema_version"] != 1
    ):
        _fail("invalid_compatibility_identity")
    compatibility_profile = _exact_object(
        compatibility["profile"],
        frozenset({"profile_id", "profile_version", "profile_digest"}),
        reason="invalid_compatibility_identity",
    )
    if compatibility_profile != {
        "profile_id": profile["profile_id"],
        "profile_version": profile["profile_version"],
        "profile_digest": profile["profile_digest"],
    }:
        _fail("invalid_compatibility_identity")
    metric_fields = frozenset({
        "metric_id", "catalog_id", "catalog_version", "catalog_digest",
    })
    metric_ids = set()
    for metric in _exact_list(
        compatibility["metric_definitions"], field="metric_definitions",
    ):
        _exact_object(metric, metric_fields, reason="invalid_compatibility_identity")
        metric_id = _string(metric["metric_id"], field="metric_id", identifier=True)
        if metric_id in metric_ids:
            _fail("invalid_compatibility_identity")
        metric_ids.add(metric_id)
        _string(metric["catalog_id"], field="catalog_id", identifier=True)
        if (
            type(metric["catalog_version"]) is not str
            or _SEMVER.fullmatch(metric["catalog_version"]) is None
            or type(metric["catalog_digest"]) is not str
            or _DIGEST.fullmatch(metric["catalog_digest"]) is None
        ):
            _fail("invalid_compatibility_identity")
    tool_fields = frozenset({
        "lane_id", "tool_identity", "image_identity", "service_identity",
        "plugin_version",
    })
    lane_ids = set()
    for tool in _exact_list(
        compatibility["tool_identities"], field="tool_identities",
    ):
        _exact_object(tool, tool_fields, reason="invalid_compatibility_identity")
        lane_id = _string(tool["lane_id"], field="lane_id", identifier=True)
        if lane_id in lane_ids:
            _fail("invalid_compatibility_identity")
        lane_ids.add(lane_id)
        if (
            type(tool["tool_identity"]) is not str
            or not tool["tool_identity"].startswith("docker:")
            or _SEMVER.fullmatch(tool["tool_identity"][7:]) is None
            or type(tool["plugin_version"]) is not str
            or _SEMVER.fullmatch(tool["plugin_version"]) is None
        ):
            _fail("invalid_compatibility_identity")
        image, service = tool["image_identity"], tool["service_identity"]
        if not (
            (
                type(image) is str and service is None
                and _IMAGE_IDENTITY.fullmatch(image) is not None
            )
            or (
                image is None and type(service) is str
                and _COMPOSE_IDENTITY.fullmatch(service) is not None
            )
        ):
            _fail("invalid_compatibility_identity")
    tool_by_lane = {
        item["lane_id"]: item for item in compatibility["tool_identities"]
    }
    observation_fields = frozenset({
        "observation_id", "surface_id", "rule_id", "metric_id",
        "classification", "confidence", "actionable", "reason_code",
        "evidence_status", "evidence_references", "raw_telemetry",
        "redacted_values",
    })
    for observation in _exact_list(result["observations"], field="observations"):
        _exact_object(
            observation, observation_fields,
            reason="invalid_authoritative_observation",
        )
        if (
            observation["evidence_status"] not in EVIDENCE_STATUSES
            or type(observation["actionable"]) is not bool
            or type(observation["redacted_values"]) is not int
        ):
            _fail("invalid_authoritative_observation")
        _string(observation["observation_id"], field="observation_id", identifier=True)
        for field in ("surface_id", "rule_id", "metric_id"):
            if observation[field] is not None:
                _string(observation[field], field=field, identifier=True)
        _string(observation["classification"], field="classification", identifier=True)
        _string(observation["reason_code"], field="reason_code", identifier=True)
        if observation["confidence"] not in {"high", "medium", "low", "unknown"}:
            _fail("invalid_authoritative_observation")
        references = _exact_list(
            observation["evidence_references"], field="evidence_references",
        )
        if any(
            type(reference) is not str
            or normalize_evidence_reference(reference) != reference
            for reference in references
        ):
            _fail("invalid_authoritative_observation")
        try:
            if json.loads(
                json.dumps(observation["raw_telemetry"], allow_nan=False),
            ) != observation["raw_telemetry"]:
                _fail("invalid_authoritative_observation")
        except (TypeError, ValueError):
            _fail("invalid_authoritative_observation")
        safe_telemetry, leaked = _redact_durable(observation["raw_telemetry"])
        if safe_telemetry != observation["raw_telemetry"] or leaked:
            _fail("invalid_authoritative_observation")
    receipt_fields = frozenset({
        "lane_id", "status", "reason_code", "primary_lane_id", "argv_identity",
        "tool_identity", "image_identity", "service_identity", "plugin_version",
        "timeout_seconds", "started_at", "finished_at", "exit_code",
        "evidence_references", "stdout", "stderr", "redacted_values",
    })
    for receipt in _exact_list(result["lane_receipts"], field="lane_receipts"):
        _exact_object(receipt, receipt_fields, reason="invalid_lane_receipt")
        if (
            receipt["status"] not in EVIDENCE_STATUSES
            or type(receipt["timeout_seconds"]) is not int
            or receipt["timeout_seconds"] < 1
            or type(receipt["redacted_values"]) is not int
            or receipt["redacted_values"] < 0
            or (
                receipt["exit_code"] is not None
                and type(receipt["exit_code"]) is not int
            )
        ):
            _fail("invalid_lane_receipt")
        _string(receipt["lane_id"], field="lane_id", identifier=True)
        _string(receipt["reason_code"], field="reason_code", identifier=True)
        if receipt["primary_lane_id"] is not None:
            _string(
                receipt["primary_lane_id"], field="primary_lane_id", identifier=True,
            )
        if (
            type(receipt["argv_identity"]) is not str
            or _DIGEST.fullmatch(receipt["argv_identity"]) is None
            or type(receipt["tool_identity"]) is not str
            or not receipt["tool_identity"].startswith("docker:")
            or _SEMVER.fullmatch(receipt["tool_identity"][7:]) is None
            or type(receipt["plugin_version"]) is not str
            or _SEMVER.fullmatch(receipt["plugin_version"]) is None
            or type(receipt["stdout"]) is not str
            or type(receipt["stderr"]) is not str
            or contains_high_confidence_secret(receipt["stdout"])
            or contains_high_confidence_secret(receipt["stderr"])
        ):
            _fail("invalid_lane_receipt")
        declared_tool = tool_by_lane.get(receipt["lane_id"])
        if declared_tool is None or any(
            receipt[field] != declared_tool[field]
            for field in (
                "tool_identity", "image_identity", "service_identity",
                "plugin_version",
            )
        ):
            _fail("invalid_lane_receipt")
        if (
            receipt["status"] in {"fallback", "skipped"}
            and receipt["primary_lane_id"] is None
        ):
            _fail("invalid_lane_receipt")
        for field in ("started_at", "finished_at"):
            if receipt[field] is not None:
                normalize_durable_string(receipt[field])
        for reference in _exact_list(
            receipt["evidence_references"], field="evidence_references",
        ):
            if (
                type(reference) is not str
                or normalize_evidence_reference(reference) != reference
            ):
                _fail("invalid_lane_receipt")
    invocation = _exact_object(
        result["invocation"],
        frozenset({
            "started_at", "finished_at", "operator_authorization_event_id",
            "purpose", "selected_lane_ids",
        }),
        reason="invalid_invocation",
    )
    for field in ("started_at", "finished_at"):
        if type(invocation[field]) is not str:
            _fail("invalid_invocation")
        normalize_durable_string(invocation[field])
    _string(
        invocation["operator_authorization_event_id"],
        field="operator_authorization_event_id", identifier=True,
    )
    _string(invocation["purpose"], field="purpose", identifier=True)
    selected = _exact_list(
        invocation["selected_lane_ids"], field="selected_lane_ids",
    )
    if (
        any(type(lane_id) is not str or _IDENTIFIER.fullmatch(lane_id) is None
            for lane_id in selected)
        or len(set(selected)) != len(selected)
    ):
        _fail("invalid_invocation")
    redaction = _exact_object(
        result["redaction"], frozenset({"applied", "redacted_value_count"}),
        reason="invalid_redaction_outcome",
    )
    if (
        type(redaction["applied"]) is not bool
        or type(redaction["redacted_value_count"]) is not int
        or redaction["redacted_value_count"] < 0
    ):
        _fail("invalid_redaction_outcome")
    if _canonical_digest(stable_projection(result)) != result["stable_projection_digest"]:
        _fail("authoritative_digest_mismatch")
    return result


def authoritative_bytes(result):
    return _canonical_bytes(validate_authoritative_result(result))


def compare_trends(current, baseline):
    validate_authoritative_result(current)
    validate_authoritative_result(baseline)
    mismatches = []
    for field in ("schema_version", "profile", "metric_definitions", "tool_identities"):
        current_value = (
            current["compatibility_identity"].get(field)
            if field != "schema_version" else current["schema_version"]
        )
        baseline_value = (
            baseline["compatibility_identity"].get(field)
            if field != "schema_version" else baseline["schema_version"]
        )
        if current_value != baseline_value:
            mismatches.append(field)
    if mismatches:
        return {
            "schema_version": 1, "status": "baseline_discontinuity",
            "reason_code": "incompatible_baseline",
            "incompatible_identity_fields": sorted(mismatches),
            "deltas": [],
        }
    baseline_values = {
        item["observation_id"]: item["raw_telemetry"].get("value")
        for item in baseline["observations"]
        if type(item["raw_telemetry"]) is dict
        and type(item["raw_telemetry"].get("value")) in {int, float}
        and type(item["raw_telemetry"].get("value")) is not bool
    }
    deltas = []
    for item in current["observations"]:
        value = (
            item["raw_telemetry"].get("value")
            if type(item["raw_telemetry"]) is dict else None
        )
        prior = baseline_values.get(item["observation_id"])
        if (
            type(value) in {int, float} and type(value) is not bool
            and type(prior) in {int, float} and type(prior) is not bool
        ):
            deltas.append({
                "observation_id": item["observation_id"],
                "current": value, "baseline": prior, "delta": value - prior,
            })
    return {
        "schema_version": 1, "status": "compatible",
        "reason_code": "comparable", "incompatible_identity_fields": [],
        "deltas": sorted(deltas, key=lambda item: item["observation_id"]),
    }


def render_markdown(result):
    """Render validated authoritative JSON; Markdown is never an input authority."""
    validate_authoritative_result(result)
    lines = [
        "# Inspection Result", "",
        f"- Profile: `{result['profile']['profile_id']}` `{result['profile']['profile_version']}`",
        f"- Commit: `{result['repository']['commit']}`",
        f"- Dirty: `{str(result['repository']['dirty']).lower()}`",
        f"- Stable digest: `{result['stable_projection_digest']}`",
        "", "## Observations", "",
    ]
    for item in result["observations"]:
        lines.append(
            f"- `{item['observation_id']}`: **{item['classification']}** "
            f"({item['confidence']}; {item['evidence_status']}; {item['reason_code']})"
        )
    lines.extend(("", "## Lane receipts", ""))
    for receipt in result["lane_receipts"]:
        lines.append(
            f"- `{receipt['lane_id']}`: **{receipt['status']}** "
            f"({receipt['reason_code']})"
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "AUTHORITATIVE_SCHEMA_VERSION", "EVIDENCE_STATUSES", "FIXED_EXECUTION_ENV",
    "InspectionError", "InspectionProfile", "PROFILE_SCHEMA_VERSION", "SubprocessAdapter",
    "authoritative_bytes", "build_authoritative_result", "classify_observations",
    "compare_trends", "decode_json_bytes", "execute_inspection_lanes",
    "load_host_attestation", "load_inspection_profile", "normalize_owned_path",
    "render_markdown", "stable_projection", "validate_authoritative_result",
    "validate_host_attestation", "validate_inspection_profile",
]
