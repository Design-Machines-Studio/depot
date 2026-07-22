"""Pure expected-versus-observed PR, issue, scope, and evidence closeout."""

from __future__ import annotations

import hashlib
import json
import re

from .redaction import (
    contains_high_confidence_secret, normalize_durable_string,
    normalize_evidence_reference,
)


SCHEMA_VERSION = 1
_SHA = re.compile(r"[0-9a-f]{40,64}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_EXPECTED = frozenset({
    "local_head_sha", "reviewed_sha", "delivered_sha", "pr_head_sha", "base_branch",
    "default_branch", "draft", "claimed_paths", "required_evidence_ids", "closing_issue_ids",
    "affected_surface", "affected_surface_mapping_provenance",
})
_OBSERVED = frozenset({
    "actual_pr_head_sha", "merge_commit_sha", "actual_base_branch", "actual_draft",
    "changed_paths", "ci_gate", "unresolved_findings", "issue_references", "artifacts",
    "open_issue_inventory",
})


def _fail(reason):
    raise ValueError(reason)


def _list(value, name, maximum=2048):
    if (
        type(value) is not list or len(value) > maximum
        or not all(type(item) is str and item and len(item) <= 512 and not any(ord(char) < 0x20 for char in item) for item in value)
    ):
        _fail("invalid " + name)
    return value


def _text(value, name, *, nullable=False):
    if nullable and value is None:
        return None
    if type(value) is not str or not value or len(value) > 512 or any(ord(char) < 0x20 for char in value):
        _fail("invalid " + name)
    if contains_high_confidence_secret(value):
        _fail("unsafe " + name)
    try:
        if normalize_durable_string(value) != value:
            _fail("unsafe " + name)
    except ValueError:
        _fail("unsafe " + name)
    return value


def _paths(value, name):
    paths = _list(value, name)
    for path in paths:
        parts = path.split("/")
        if path.startswith("/") or "\\" in path or any(part in {"", ".", ".."} for part in parts) or any(char in path for char in "*?[]"):
            _fail("invalid " + name)
    if len(set(paths)) != len(paths):
        _fail("duplicate " + name)
    return paths


def _safe_list(value, name, maximum=2048):
    values = _list(value, name, maximum)
    for item in values:
        _text(item, name)
    return values


def _check(checks, check_id, passed, reason, *, unresolved=False):
    checks.append({"id": check_id, "status": "passed" if passed else ("unresolved" if unresolved else "failed"), "reason": reason})


def evaluate_closeout(expected, observed):
    if type(expected) is not dict or set(expected) != _EXPECTED:
        _fail("closeout expectation fields mismatch")
    if type(observed) is not dict or set(observed) != _OBSERVED:
        _fail("closeout observation fields mismatch")
    for field in ("local_head_sha", "reviewed_sha", "delivered_sha", "pr_head_sha"):
        if type(expected[field]) is not str or _SHA.fullmatch(expected[field]) is None:
            _fail("invalid " + field)
    if type(observed["actual_pr_head_sha"]) is not str or _SHA.fullmatch(observed["actual_pr_head_sha"]) is None:
        _fail("invalid actual_pr_head_sha")
    if observed["merge_commit_sha"] is not None and (type(observed["merge_commit_sha"]) is not str or _SHA.fullmatch(observed["merge_commit_sha"]) is None):
        _fail("invalid merge_commit_sha")
    if type(expected["draft"]) is not bool or type(observed["actual_draft"]) is not bool:
        _fail("invalid draft state")
    for field in ("base_branch", "default_branch", "affected_surface", "affected_surface_mapping_provenance"):
        _text(expected[field], field)
    _text(observed["actual_base_branch"], "actual_base_branch")
    claimed = set(_paths(expected["claimed_paths"], "claimed_paths"))
    changed = set(_paths(observed["changed_paths"], "changed_paths"))
    required_artifacts = set(_safe_list(expected["required_evidence_ids"], "required_evidence_ids"))
    closing_ids = set(_safe_list(expected["closing_issue_ids"], "closing_issue_ids", 512))
    findings = _safe_list(observed["unresolved_findings"], "unresolved_findings", 4096)
    checks = []
    identity_ok = len({expected["local_head_sha"], expected["reviewed_sha"], expected["delivered_sha"], expected["pr_head_sha"], observed["actual_pr_head_sha"]}) == 1
    _check(checks, "head_identity", identity_ok, "exact_heads_match" if identity_ok else "head_identity_mismatch")
    merge_substituted = observed["merge_commit_sha"] is not None and expected["pr_head_sha"] == observed["merge_commit_sha"] and observed["actual_pr_head_sha"] != observed["merge_commit_sha"]
    _check(checks, "pr_head_not_merge_commit", not merge_substituted, "pr_head_is_source_head" if not merge_substituted else "synthetic_merge_sha_substituted")
    base_ok = expected["base_branch"] == observed["actual_base_branch"]
    _check(checks, "base_branch", base_ok, "base_matches" if base_ok else "base_mismatch")
    draft_ok = expected["draft"] == observed["actual_draft"]
    _check(checks, "draft_state", draft_ok, "draft_matches" if draft_ok else "draft_mismatch")
    scope_ok = claimed == changed
    _check(checks, "changed_scope", scope_ok, "scope_matches" if scope_ok else "claimed_changed_scope_mismatch")
    ci = observed["ci_gate"]
    ci_status = None
    if type(ci) is dict and set(ci) == {"schema_version", "status", "checks"} and ci.get("schema_version") == 1 and type(ci.get("checks")) is list and ci["checks"]:
        check_statuses = []
        for item in ci["checks"]:
            if type(item) is not dict or set(item) != {"context", "status", "reason"} or item.get("status") not in {"passed", "failed", "unresolved"}:
                check_statuses = []
                break
            check_statuses.append(item["status"])
        derived = "failed" if "failed" in check_statuses else "unresolved" if "unresolved" in check_statuses else "passed" if check_statuses else None
        if ci.get("status") == derived:
            ci_status = derived
    _check(checks, "required_ci", ci_status == "passed", "ci_passed" if ci_status == "passed" else "ci_not_authoritatively_passed", unresolved=ci_status in {None, "unresolved", "unavailable"})
    _check(checks, "unresolved_findings", not findings, "no_unresolved_findings" if not findings else "unresolved_findings_remain")

    artifacts = observed["artifacts"]
    if type(artifacts) is not list or len(artifacts) > 1024:
        _fail("invalid artifacts")
    by_id = {}
    for item in artifacts:
        required = {"id", "path", "expected_digest", "observed_digest", "exists", "classification", "binding_valid"}
        if type(item) is not dict or set(item) != required:
            _fail("invalid artifact snapshot")
        _text(item["id"], "artifact id")
        try:
            item["path"] = normalize_evidence_reference(item["path"])
        except ValueError:
            _fail("invalid artifact path")
        if item["id"] in by_id or type(item["exists"]) is not bool or type(item["binding_valid"]) is not bool:
            _fail("invalid artifact snapshot")
        if type(item["expected_digest"]) is not str or _DIGEST.fullmatch(item["expected_digest"]) is None:
            _fail("invalid artifact digest")
        if item["observed_digest"] is not None and (type(item["observed_digest"]) is not str or _DIGEST.fullmatch(item["observed_digest"]) is None):
            _fail("invalid artifact digest")
        if item["classification"] not in {"committable", "private_receipt", "ephemeral", "blocked_sensitive", "unknown"}:
            _fail("invalid artifact classification")
        by_id[item["id"]] = item
    for artifact_id in sorted(required_artifacts):
        item = by_id.get(artifact_id)
        if item is None:
            _check(checks, "artifact:" + artifact_id, False, "artifact_snapshot_missing", unresolved=True)
            continue
        if not item["exists"]:
            passed, reason = False, "artifact_missing"
        elif item["expected_digest"] != item["observed_digest"]:
            passed, reason = False, "artifact_digest_mismatch"
        elif item["classification"] != "committable":
            passed, reason = False, "artifact_not_safely_classified"
        elif not item["binding_valid"]:
            passed, reason = False, "artifact_binding_stale"
        else:
            passed, reason = True, "artifact_current_and_safe"
        _check(checks, "artifact:" + artifact_id, passed, reason)

    references = observed["issue_references"]
    if type(references) is not list or len(references) > 1024:
        _fail("invalid issue references")
    by_issue = {}
    for item in references:
        fields = {"issue_id", "mention", "closing_intent", "resolved_entity_kind", "provider_closing_link", "actual_state", "auto_close_policy"}
        if type(item) is not dict or set(item) != fields:
            _fail("invalid issue reference")
        _text(item["issue_id"], "issue_id")
        if item["issue_id"] in by_issue or type(item["mention"]) is not bool or type(item["closing_intent"]) is not bool or type(item["provider_closing_link"]) is not bool:
            _fail("invalid issue reference")
        if item["resolved_entity_kind"] not in {"issue", "pull_request", "missing", "transferred", "unknown"}:
            _fail("invalid issue entity")
        if item["actual_state"] not in {"open", "closed", "missing", "unknown"} or item["auto_close_policy"] not in {"enabled", "disabled", "unknown"}:
            _fail("invalid issue state")
        by_issue[item["issue_id"]] = item
    for issue_id in sorted(closing_ids):
        item = by_issue.get(issue_id)
        if item is None:
            _check(checks, "issue:" + issue_id, False, "issue_reference_missing", unresolved=True)
        elif item["resolved_entity_kind"] != "issue":
            _check(checks, "issue:" + issue_id, False, "reference_not_resolved_issue")
        elif not item["mention"]:
            _check(checks, "issue:" + issue_id, False, "issue_not_textually_referenced")
        elif not item["closing_intent"]:
            _check(checks, "issue:" + issue_id, False, "plain_mention_is_not_closure")
        elif expected["base_branch"] != expected["default_branch"]:
            _check(checks, "issue:" + issue_id, False, "non_default_base_cannot_guarantee_closure")
        elif item["auto_close_policy"] != "enabled" or not item["provider_closing_link"]:
            _check(checks, "issue:" + issue_id, False, "provider_closure_not_guaranteed", unresolved=item["auto_close_policy"] == "unknown")
        elif item["actual_state"] == "closed":
            _check(checks, "issue:" + issue_id, True, "issue_observed_closed")
        else:
            _check(checks, "issue:" + issue_id, False, "issue_closure_pending")

    inventory = observed["open_issue_inventory"]
    fields = {"available", "surface", "mapping_provenance", "issue_ids"}
    if type(inventory) is not dict or set(inventory) != fields or type(inventory["available"]) is not bool:
        _fail("invalid open issue inventory")
    _text(inventory["surface"], "inventory surface")
    if type(inventory["mapping_provenance"]) is not str or len(inventory["mapping_provenance"]) > 512:
        _fail("invalid inventory provenance")
    inventory_ids = _safe_list(inventory["issue_ids"], "inventory issue_ids", 4096)
    if not inventory["available"]:
        remaining = []
        _check(checks, "affected_surface_inventory", False, "surface_inventory_unavailable", unresolved=True)
    elif (
        inventory["surface"] != expected["affected_surface"]
        or inventory["mapping_provenance"] != expected["affected_surface_mapping_provenance"]
    ):
        remaining = list(inventory_ids)
        _check(checks, "affected_surface_inventory", False, "surface_inventory_scope_mismatch")
    else:
        remaining = sorted(set(inventory_ids))
        _check(checks, "affected_surface_inventory", not remaining, "surface_has_no_open_issues" if not remaining else "surface_open_issues_remain")

    statuses = {item["status"] for item in checks}
    status = "failed" if "failed" in statuses else "unresolved" if "unresolved" in statuses else "passed"
    disposition = "closing" if status == "passed" and closing_ids else "non_closing" if status == "passed" else "blocked"
    body = {
        "schema_version": SCHEMA_VERSION, "status": status, "checks": checks,
        "unresolved_findings": list(findings), "remaining_open_issues": remaining,
        "disposition": disposition,
    }
    body["audit_digest"] = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return body
