"""Immutable, exact-match browser evidence bundles shared by reviewers."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields

from .browser_target import digest_target_route, validate_viewport
from .model import _register_origin, _validate_capture
from .redaction import contains_high_confidence_secret, normalize_evidence_reference


SCHEMA_VERSION = 1
MAX_RESULTS = 512
MAX_EVIDENCE = 1024
_ID = re.compile(r"[a-z0-9][a-z0-9._:-]{0,127}\Z")
_PROFILE_ID = re.compile(r"profile-sha256:[0-9a-f]{64}\Z")
_CASE_ID = re.compile(r"case-sha256:[0-9a-f]{64}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ORIGIN = re.compile(r"origin-sha256:[0-9a-f]{64}\Z")
_ENGINES = frozenset({"chromium", "firefox", "webkit"})
_TERMINALS = frozenset({
    "first_pass", "fresh_primary", "alternate_engine", "human_action_required",
    "human_help_required", "application_failure",
})
_RESULT_STATUSES = frozenset({
    "passed", "failed", "skipped", "human_action_required",
    "human_help_required", "application_failure",
})


def _canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _id(value, name="identifier"):
    if (type(value) is not str or _ID.fullmatch(value) is None
            or contains_high_confidence_secret(value)):
        raise ValueError(f"invalid {name}")
    return value


def _digest(value, name="digest", *, nullable=False):
    if nullable and value is None:
        return None
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")
    return value


def _unique_ids(value, name, maximum):
    if type(value) not in {tuple, list} or len(value) > maximum:
        raise ValueError(f"invalid {name}")
    result = tuple(_id(item, name) for item in value)
    if len(result) != len(set(result)):
        raise ValueError(f"duplicate {name}")
    return result


@dataclass(frozen=True)
class BrowserStepResult:
    step_id: str
    status: str
    reason_code: str | None
    evidence_digests: tuple[str, ...]

    def __post_init__(self):
        _id(self.step_id, "step_id")
        if self.status not in _RESULT_STATUSES:
            raise ValueError("invalid browser step status")
        if self.reason_code is not None:
            _id(self.reason_code, "reason_code")
        if type(self.evidence_digests) is not tuple or len(self.evidence_digests) > MAX_EVIDENCE:
            raise ValueError("invalid result evidence")
        digests = tuple(_digest(item, "evidence digest") for item in self.evidence_digests)
        if len(digests) != len(set(digests)):
            raise ValueError("duplicate result evidence")
        if self.status == "passed" and self.reason_code is not None:
            raise ValueError("passed step has reason")
        object.__setattr__(self, "evidence_digests", digests)
        _register_origin(self, "BrowserStepResult", self._origin_primitives())

    def _origin_primitives(self):
        return self.step_id, self.status, self.reason_code, self.evidence_digests

    def to_dict(self):
        return {
            "step_id": self.step_id, "status": self.status,
            "reason_code": self.reason_code, "evidence_digests": list(self.evidence_digests),
        }

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {
            "step_id", "status", "reason_code", "evidence_digests",
        } or type(value["evidence_digests"]) is not list:
            raise ValueError("browser step result fields mismatch")
        return cls(value["step_id"], value["status"], value["reason_code"], tuple(value["evidence_digests"]))


@dataclass(frozen=True)
class BrowserBundleEvidence:
    step_id: str
    capture_kind: str
    reference: str
    evidence_digest: str
    proof_kind: str = "browser"

    def __post_init__(self):
        _id(self.step_id, "step_id")
        if self.capture_kind not in {"screenshot", "trace", "console", "network", "a11y"}:
            raise ValueError("invalid evidence kind")
        try:
            reference = normalize_evidence_reference(self.reference)
        except ValueError:
            raise ValueError("invalid evidence reference") from None
        if self.proof_kind not in {"browser", "curl", "reachability"}:
            raise ValueError("invalid evidence proof kind")
        object.__setattr__(self, "reference", reference)
        _digest(self.evidence_digest, "evidence digest")
        _register_origin(self, "BrowserBundleEvidence", self._origin_primitives())

    def _origin_primitives(self):
        return self.step_id, self.capture_kind, self.reference, self.evidence_digest, self.proof_kind

    def to_dict(self):
        return {
            "step_id": self.step_id, "capture_kind": self.capture_kind,
            "reference": self.reference, "evidence_digest": self.evidence_digest,
            "proof_kind": self.proof_kind,
        }

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {
            "step_id", "capture_kind", "reference", "evidence_digest", "proof_kind",
        }:
            raise ValueError("browser evidence fields mismatch")
        return cls(**value)


def _snapshot(value, expected, name):
    if type(value) is not expected:
        raise ValueError(f"invalid {name}")
    try:
        captured = tuple(getattr(value, item.name) for item in fields(expected))
        _validate_capture(value, expected.__name__, captured, value._origin_primitives())
        return expected(*captured)
    except Exception:
        raise ValueError(f"invalid {name}") from None


@dataclass(frozen=True)
class BrowserEvidenceBundle:
    schema_version: int
    scenario_digest: str
    profile_id: str
    persona_id: str
    repository_state_digest: str
    evidence_binding_digest: str
    login_state: str
    javascript_enabled: bool
    restart_state: str
    engine: str
    viewport: str
    origin_digest: str
    route_digest: str
    session_ref: str
    attempt_refs: tuple[str, ...]
    recovery_receipt_digest: str | None
    results: tuple[BrowserStepResult, ...]
    evidence: tuple[BrowserBundleEvidence, ...]
    covered_case_ids: tuple[str, ...]
    missing_case_ids: tuple[str, ...]
    terminal_reason: str
    bundle_digest: str = ""

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported browser bundle version")
        for name in ("scenario_digest", "repository_state_digest", "evidence_binding_digest", "route_digest"):
            _digest(getattr(self, name), name)
        if type(self.profile_id) is not str or _PROFILE_ID.fullmatch(self.profile_id) is None:
            raise ValueError("invalid bundle profile")
        _id(self.persona_id, "persona_id"); _id(self.session_ref, "session_ref")
        if self.login_state not in {
            "anonymous", "authenticated", "expected_rejection", "human_action_required",
        } or type(self.javascript_enabled) is not bool:
            raise ValueError("invalid bundle runtime state")
        if self.restart_state not in {
            "none", "application_restarted", "fresh_primary", "alternate_engine",
        } or self.engine not in _ENGINES:
            raise ValueError("invalid bundle recovery state")
        validate_viewport(self.viewport)
        if type(self.origin_digest) is not str or _ORIGIN.fullmatch(self.origin_digest) is None:
            raise ValueError("invalid bundle origin")
        attempts = _unique_ids(self.attempt_refs, "attempt ref", 3)
        recovery = _digest(self.recovery_receipt_digest, "recovery receipt digest", nullable=True)
        if type(self.results) is not tuple or not self.results or len(self.results) > MAX_RESULTS:
            raise ValueError("invalid bundle results")
        results = tuple(_snapshot(item, BrowserStepResult, "browser step result") for item in self.results)
        if len({item.step_id for item in results}) != len(results):
            raise ValueError("duplicate browser step result")
        if type(self.evidence) is not tuple or len(self.evidence) > MAX_EVIDENCE:
            raise ValueError("invalid bundle evidence")
        evidence = tuple(_snapshot(item, BrowserBundleEvidence, "browser evidence") for item in self.evidence)
        evidence_by_digest = {item.evidence_digest: item for item in evidence}
        evidence_digests = set(evidence_by_digest)
        if len(evidence_digests) != len(evidence):
            raise ValueError("duplicate browser evidence")
        if any(
            not set(item.evidence_digests) <= evidence_digests
            or any(evidence_by_digest[digest].step_id != item.step_id for digest in item.evidence_digests)
            for item in results
        ):
            raise ValueError("step result references missing evidence")
        if {item.step_id for item in evidence} - {item.step_id for item in results}:
            raise ValueError("evidence has no step result")
        covered = _unique_ids(self.covered_case_ids, "covered case", MAX_RESULTS)
        missing = _unique_ids(self.missing_case_ids, "missing case", MAX_RESULTS)
        if any(_CASE_ID.fullmatch(item) is None for item in covered + missing):
            raise ValueError("invalid bundle case binding")
        if set(covered) & set(missing):
            raise ValueError("case is both covered and missing")
        if self.terminal_reason not in _TERMINALS:
            raise ValueError("invalid bundle terminal reason")
        if ((self.terminal_reason == "human_action_required")
                != (self.login_state == "human_action_required")):
            raise ValueError("human action login binding mismatch")
        passed_terminal = self.terminal_reason in {"first_pass", "fresh_primary", "alternate_engine"}
        expected_restart = {
            "first_pass": "none", "fresh_primary": "fresh_primary",
            "alternate_engine": "alternate_engine",
        }.get(self.terminal_reason)
        if expected_restart is not None and self.restart_state != expected_restart:
            raise ValueError("terminal recovery binding mismatch")
        if passed_terminal:
            browser_digests = {item.evidence_digest for item in evidence if item.proof_kind == "browser"}
            passed_evidence = {
                digest for item in results if item.status == "passed" for digest in item.evidence_digests
            }
            if missing or not browser_digests or not passed_evidence <= browser_digests:
                raise ValueError("browser terminal lacks current browser proof")
        elif self.terminal_reason == "application_failure" and any(
            item.status in {"human_action_required", "human_help_required"} for item in results
        ):
            raise ValueError("application failure is not human intervention")
        elif self.terminal_reason in {"human_action_required", "human_help_required"} and not missing:
            raise ValueError("human intervention must preserve missing coverage")
        elif self.terminal_reason == "application_failure" and not missing:
            raise ValueError("application failure must preserve missing coverage")
        terminal_status = {
            "human_action_required": "human_action_required",
            "human_help_required": "human_help_required",
            "application_failure": "application_failure",
        }.get(self.terminal_reason)
        if terminal_status is not None and not any(item.status == terminal_status for item in results):
            raise ValueError("terminal result is missing")
        object.__setattr__(self, "attempt_refs", attempts)
        object.__setattr__(self, "recovery_receipt_digest", recovery)
        object.__setattr__(self, "results", results)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "covered_case_ids", covered)
        object.__setattr__(self, "missing_case_ids", missing)
        expected = "sha256:" + hashlib.sha256(_canonical_bytes(self._body())).hexdigest()
        if self.bundle_digest and self.bundle_digest != expected:
            raise ValueError("browser bundle digest mismatch")
        object.__setattr__(self, "bundle_digest", expected)
        _register_origin(self, "BrowserEvidenceBundle", self._origin_primitives())

    def _body(self):
        return {
            "schema_version": self.schema_version, "scenario_digest": self.scenario_digest,
            "profile_id": self.profile_id, "persona_id": self.persona_id,
            "repository_state_digest": self.repository_state_digest,
            "evidence_binding_digest": self.evidence_binding_digest,
            "login_state": self.login_state, "javascript_enabled": self.javascript_enabled,
            "restart_state": self.restart_state, "engine": self.engine,
            "viewport": self.viewport, "origin_digest": self.origin_digest,
            "route_digest": self.route_digest, "session_ref": self.session_ref,
            "attempt_refs": list(self.attempt_refs),
            "recovery_receipt_digest": self.recovery_receipt_digest,
            "results": [item.to_dict() for item in self.results],
            "evidence": [item.to_dict() for item in self.evidence],
            "covered_case_ids": list(self.covered_case_ids),
            "missing_case_ids": list(self.missing_case_ids),
            "terminal_reason": self.terminal_reason,
        }

    def _origin_primitives(self):
        return tuple(self._body().values()) + (self.bundle_digest,)

    def to_dict(self):
        return {**self._body(), "bundle_digest": self.bundle_digest}

    @classmethod
    def from_dict(cls, value):
        expected = {
            "schema_version", "scenario_digest", "profile_id", "persona_id",
            "repository_state_digest", "evidence_binding_digest", "login_state",
            "javascript_enabled", "restart_state", "engine", "viewport", "origin_digest",
            "route_digest", "session_ref", "attempt_refs", "recovery_receipt_digest",
            "results", "evidence", "covered_case_ids", "missing_case_ids",
            "terminal_reason", "bundle_digest",
        }
        list_fields = {"attempt_refs", "results", "evidence", "covered_case_ids", "missing_case_ids"}
        if type(value) is not dict or set(value) != expected or any(
            type(value[name]) is not list for name in list_fields
        ):
            raise ValueError("browser bundle fields mismatch")
        return cls(
            value["schema_version"], value["scenario_digest"], value["profile_id"],
            value["persona_id"], value["repository_state_digest"], value["evidence_binding_digest"],
            value["login_state"], value["javascript_enabled"], value["restart_state"],
            value["engine"], value["viewport"], value["origin_digest"], value["route_digest"],
            value["session_ref"], tuple(value["attempt_refs"]), value["recovery_receipt_digest"],
            tuple(BrowserStepResult.from_dict(item) for item in value["results"]),
            tuple(BrowserBundleEvidence.from_dict(item) for item in value["evidence"]),
            tuple(value["covered_case_ids"]), tuple(value["missing_case_ids"]),
            value["terminal_reason"], value["bundle_digest"],
        )


def snapshot_browser_evidence_bundle(value):
    return _snapshot(value, BrowserEvidenceBundle, "browser evidence bundle")


_MATCH_FIELDS = (
    ("scenario_digest", "scenario_changed"),
    ("profile_id", "profile_changed"),
    ("persona_id", "persona_changed"),
    ("repository_state_digest", "repository_state_changed"),
    ("evidence_binding_digest", "build_binding_changed"),
    ("login_state", "login_state_changed"),
    ("javascript_enabled", "javascript_state_changed"),
    ("restart_state", "restart_state_changed"),
    ("engine", "engine_changed"),
    ("viewport", "viewport_changed"),
    ("origin_digest", "origin_changed"),
    ("route_digest", "route_changed"),
    ("session_ref", "session_changed"),
    ("attempt_refs", "attempts_changed"),
    ("recovery_receipt_digest", "recovery_changed"),
    ("results", "results_changed"),
    ("evidence", "evidence_changed"),
    ("covered_case_ids", "coverage_changed"),
    ("missing_case_ids", "missing_cases_changed"),
    ("terminal_reason", "terminal_reason_changed"),
)


def match_browser_evidence_bundle(expected, current):
    """Allow reuse only when every evidence/build/runtime binding is exact."""
    expected = snapshot_browser_evidence_bundle(expected)
    current = snapshot_browser_evidence_bundle(current)
    reasons = [reason for field, reason in _MATCH_FIELDS if getattr(expected, field) != getattr(current, field)]
    return {"matches": not reasons, "reasons": reasons}


def bind_browser_evidence_bundle(scenario, bundle):
    """Validate scenario identity and preserve declared step/result order."""
    from .browser_scenario import snapshot_browser_scenario

    scenario = snapshot_browser_scenario(scenario)
    bundle = snapshot_browser_evidence_bundle(bundle)
    ordered_steps = tuple(item.step_id for item in scenario.steps)
    ordered_results = tuple(item.step_id for item in bundle.results)
    positions = [ordered_steps.index(item) for item in ordered_results if item in ordered_steps]
    terminal = dict(scenario.steps[-1].payload)
    if (
        bundle.scenario_digest != scenario.scenario_digest
        or bundle.profile_id != scenario.profile_id
        or bundle.persona_id != scenario.persona_id
        or bundle.engine not in {scenario.primary_engine, scenario.alternate_engine}
        or bundle.viewport != scenario.viewport
        or bundle.origin_digest != scenario.target_origin_digest
        or bundle.route_digest != digest_target_route(scenario.initial_route)
        or len(positions) != len(ordered_results)
        or positions != sorted(positions)
        or terminal["reason"] != bundle.terminal_reason
    ):
        raise ValueError("browser bundle scenario binding mismatch")
    return bundle
