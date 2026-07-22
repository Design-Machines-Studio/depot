"""Pure provider-neutral CI observations and repository-policy decisions."""

from __future__ import annotations

from datetime import datetime, timezone
import re

from .redaction import normalize_durable_string, normalize_evidence_reference


SCHEMA_VERSION = 1
_SHA = re.compile(r"[0-9a-f]{40,64}\Z")
_SCOPES = frozenset({"pull_request", "push", "schedule", "merge_group", "default_branch", "post_merge"})
_SUBJECTS = frozenset({"pr_head", "test_merge", "commit", "merge_group", "default_branch"})
_GITHUB_LIFECYCLE = {"queued": "pending", "in_progress": "running", "completed": "completed"}
_GITHUB_CONCLUSION = {
    "success": "success", "skipped": "skipped", "neutral": "neutral",
    "failure": "failure", "cancelled": "cancelled", "timed_out": "timed_out",
    "action_required": "action_required", "stale": "stale",
}
_SUCCESS_CONCLUSIONS = frozenset({"success", "skipped", "neutral"})
_FIELDS = frozenset({
    "schema_version", "provider", "adapter_version", "mapping_version", "event_scope",
    "ref", "base_sha", "pr_head_sha", "test_merge_sha", "subject_sha", "subject_kind",
    "run_id", "check_id", "job_id", "attempt", "check_kind", "context", "app_identity",
    "raw_status", "raw_conclusion", "normalized_lifecycle", "normalized_conclusion",
    "started_at", "completed_at", "observed_at", "evidence_ref", "requirement_source",
    "satisfies_provider_merge_rule",
})
_REQUIREMENT_FIELDS = frozenset({
    "provider", "event_scope", "subject_kind", "subject_sha", "ref", "check_kind",
    "context", "app_identity", "allowed_conclusions", "max_age_seconds", "requirement_source",
})


def _fail(reason):
    raise ValueError(reason)


def _text(value, name, *, nullable=False, maximum=512):
    if nullable and value is None:
        return None
    if type(value) is not str or not value or len(value) > maximum:
        _fail("invalid " + name)
    if any(ord(char) < 0x20 or ord(char) == 0x7f for char in value):
        _fail("invalid " + name)
    try:
        if normalize_durable_string(value) != value:
            _fail("unsafe " + name)
    except ValueError:
        _fail("unsafe " + name)
    return value


def _sha(value, name, *, nullable=False):
    value = _text(value, name, nullable=nullable, maximum=64)
    if value is not None and _SHA.fullmatch(value) is None:
        _fail("invalid " + name)
    return value


def _timestamp(value, name, *, nullable=False):
    value = _text(value, name, nullable=nullable, maximum=64)
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail("invalid " + name)
    if parsed.tzinfo is None:
        _fail("invalid " + name)
    return value


def _explicit_mapping(provider, raw_status, raw_conclusion, mapping):
    if provider == "github":
        lifecycle = _GITHUB_LIFECYCLE.get(raw_status, "unknown")
        conclusion = None if raw_conclusion is None else _GITHUB_CONCLUSION.get(raw_conclusion, "unknown")
        return lifecycle, conclusion, lifecycle != "unknown" and (raw_conclusion is None or conclusion != "unknown")
    if type(mapping) is not dict:
        return "unknown", None if raw_conclusion is None else "unknown", False
    if set(mapping) != {"provider", "version", "capabilities", "statuses", "conclusions"}:
        _fail("mapping fields mismatch")
    capabilities = mapping["capabilities"]
    if mapping["provider"] != provider or type(capabilities) is not list or not all(type(item) is str for item in capabilities):
        _fail("invalid mapping")
    statuses, conclusions = mapping["statuses"], mapping["conclusions"]
    if type(statuses) is not dict or type(conclusions) is not dict:
        _fail("invalid mapping")
    lifecycle = statuses.get(raw_status, "unknown")
    conclusion = None if raw_conclusion is None else conclusions.get(raw_conclusion, "unknown")
    authoritative = "subject_identity" in capabilities and lifecycle != "unknown" and (raw_conclusion is None or conclusion != "unknown")
    return lifecycle, conclusion, authoritative


def build_ci_evidence(raw, *, mapping=None):
    """Normalize one caller-collected CI observation without network access."""
    if type(raw) is not dict or set(raw) != _FIELDS - {"schema_version", "normalized_lifecycle", "normalized_conclusion"}:
        _fail("ci evidence fields mismatch")
    provider = _text(raw["provider"], "provider", maximum=64)
    status = _text(raw["raw_status"], "raw_status", maximum=128)
    conclusion = _text(raw["raw_conclusion"], "raw_conclusion", nullable=True, maximum=128)
    lifecycle, normalized, mapped = _explicit_mapping(provider, status, conclusion, mapping)
    if provider == "github":
        if status == "completed" and conclusion is None:
            _fail("completed github check requires conclusion")
        if status != "completed" and conclusion is not None:
            _fail("incomplete github check cannot have conclusion")
    result = dict(raw)
    result.update(schema_version=SCHEMA_VERSION, normalized_lifecycle=lifecycle,
                  normalized_conclusion=normalized)
    result["mapping_version"] = _text(result["mapping_version"], "mapping_version", nullable=True, maximum=64)
    result["event_scope"] = _text(result["event_scope"], "event_scope", maximum=32)
    result["subject_kind"] = _text(result["subject_kind"], "subject_kind", maximum=32)
    if result["event_scope"] not in _SCOPES or result["subject_kind"] not in _SUBJECTS:
        _fail("invalid ci scope")
    for field in ("base_sha", "pr_head_sha", "test_merge_sha"):
        result[field] = _sha(result[field], field, nullable=True)
    result["subject_sha"] = _sha(result["subject_sha"], "subject_sha")
    for field in ("provider", "adapter_version", "ref", "run_id", "check_kind", "context", "requirement_source"):
        result[field] = _text(result[field], field)
    for field in ("check_id", "job_id", "app_identity"):
        result[field] = _text(result[field], field, nullable=True)
    if type(result["attempt"]) is not int or result["attempt"] < 1:
        _fail("invalid attempt")
    for field in ("started_at", "completed_at"):
        result[field] = _timestamp(result[field], field, nullable=True)
    result["observed_at"] = _timestamp(result["observed_at"], "observed_at")
    if (
        result["normalized_lifecycle"] == "completed" and result["completed_at"] is None
        or result["normalized_lifecycle"] in {"pending", "running"} and result["completed_at"] is not None
    ):
        _fail("completion timestamp mismatch")
    result["evidence_ref"] = normalize_evidence_reference(result["evidence_ref"])
    if type(result["satisfies_provider_merge_rule"]) is not bool:
        _fail("invalid provider merge-rule fact")
    result["mapping_authoritative"] = mapped
    return validate_ci_evidence(result)


def validate_ci_evidence(value):
    if type(value) is not dict or set(value) != _FIELDS | {"mapping_authoritative"}:
        _fail("ci evidence fields mismatch")
    if value["schema_version"] != SCHEMA_VERSION or type(value["schema_version"]) is not int:
        _fail("unsupported schema_version")
    result = dict(value)
    for field in ("provider", "adapter_version", "ref", "run_id", "check_kind", "context", "requirement_source"):
        result[field] = _text(result[field], field)
    for field in ("mapping_version", "check_id", "job_id", "app_identity", "raw_conclusion"):
        result[field] = _text(result[field], field, nullable=True)
    result["raw_status"] = _text(result["raw_status"], "raw_status", maximum=128)
    if result["event_scope"] not in _SCOPES or result["subject_kind"] not in _SUBJECTS:
        _fail("invalid ci scope")
    for field in ("base_sha", "pr_head_sha", "test_merge_sha"):
        result[field] = _sha(result[field], field, nullable=True)
    result["subject_sha"] = _sha(result["subject_sha"], "subject_sha")
    if type(result["attempt"]) is not int or result["attempt"] < 1:
        _fail("invalid attempt")
    for field in ("started_at", "completed_at"):
        result[field] = _timestamp(result[field], field, nullable=True)
    result["observed_at"] = _timestamp(result["observed_at"], "observed_at")
    result["evidence_ref"] = normalize_evidence_reference(result["evidence_ref"])
    if result["normalized_lifecycle"] not in {"pending", "running", "completed", "unknown"}:
        _fail("invalid normalized lifecycle")
    if result["normalized_conclusion"] not in {None, "success", "skipped", "neutral", "failure", "cancelled", "timed_out", "action_required", "stale", "unknown"}:
        _fail("invalid normalized conclusion")
    if type(result["mapping_authoritative"]) is not bool or type(result["satisfies_provider_merge_rule"]) is not bool:
        _fail("invalid ci authority fact")
    if result["provider"] == "github":
        lifecycle = _GITHUB_LIFECYCLE.get(result["raw_status"], "unknown")
        conclusion = None if result["raw_conclusion"] is None else _GITHUB_CONCLUSION.get(result["raw_conclusion"], "unknown")
        if (result["normalized_lifecycle"], result["normalized_conclusion"]) != (lifecycle, conclusion):
            _fail("github normalization mismatch")
        if result["mapping_authoritative"] != (lifecycle != "unknown" and (conclusion is None or conclusion != "unknown")):
            _fail("github mapping authority mismatch")
        if result["raw_status"] == "completed" and result["raw_conclusion"] is None:
            _fail("completed github check requires conclusion")
        if result["raw_status"] != "completed" and result["raw_conclusion"] is not None:
            _fail("incomplete github check cannot have conclusion")
    if result["normalized_lifecycle"] == "completed" and result["completed_at"] is None:
        _fail("completed check requires completed_at")
    if result["normalized_lifecycle"] in {"pending", "running"} and result["completed_at"] is not None:
        _fail("incomplete check cannot have completed_at")
    bound_sha = {
        "pr_head": result["pr_head_sha"],
        "test_merge": result["test_merge_sha"],
    }.get(result["subject_kind"])
    if result["subject_kind"] in {"pr_head", "test_merge"} and result["subject_sha"] != bound_sha:
        _fail("subject identity mismatch")
    return result


def evaluate_ci_gate(requirements, observations, *, now):
    """Evaluate exact repository requirements against normalized observations."""
    if type(requirements) is not list or not requirements or len(requirements) > 256:
        _fail("invalid requirements")
    if type(observations) is not list or len(observations) > 4096:
        _fail("invalid observations")
    current = datetime.fromisoformat(_timestamp(now, "now").replace("Z", "+00:00"))
    records = [validate_ci_evidence(item) for item in observations]
    checks = []
    for requirement in requirements:
        if type(requirement) is not dict or set(requirement) != _REQUIREMENT_FIELDS:
            _fail("ci requirement fields mismatch")
        if requirement["event_scope"] not in _SCOPES or requirement["subject_kind"] not in _SUBJECTS:
            _fail("invalid requirement scope")
        allowed = requirement["allowed_conclusions"]
        if type(allowed) is not list or not allowed or len(allowed) > 16 or not all(type(item) is str for item in allowed):
            _fail("invalid allowed conclusions")
        max_age = requirement["max_age_seconds"]
        if type(max_age) is not int or max_age < 0 or max_age > 31_536_000:
            _fail("invalid max age")
        matches = [item for item in records if all(item[field] == requirement[field] for field in (
            "provider", "event_scope", "subject_kind", "subject_sha", "ref", "check_kind", "context", "app_identity", "requirement_source"
        ))]
        if not matches:
            checks.append({"context": requirement["context"], "status": "unresolved", "reason": "required_lane_absent"})
            continue
        item = max(
            matches,
            key=lambda entry: datetime.fromisoformat(entry["observed_at"].replace("Z", "+00:00")),
        )
        age = (current - datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00"))).total_seconds()
        if age < 0 or age > max_age:
            status, reason = "unresolved", "observation_stale"
        elif not item["mapping_authoritative"]:
            status, reason = "unresolved", "provider_mapping_unavailable"
        elif item["normalized_lifecycle"] != "completed":
            status, reason = "unresolved", "check_not_completed"
        elif item["normalized_conclusion"] not in _SUCCESS_CONCLUSIONS:
            status, reason = "failed", "terminal_conclusion_is_not_success"
        elif item["normalized_conclusion"] in allowed:
            status, reason = "passed", "declared_policy_satisfied"
        else:
            status, reason = "failed", "conclusion_not_allowed"
        checks.append({"context": requirement["context"], "status": status, "reason": reason})
    statuses = {item["status"] for item in checks}
    status = "failed" if "failed" in statuses else "unresolved" if "unresolved" in statuses else "passed"
    return {"schema_version": SCHEMA_VERSION, "status": status, "checks": checks}
