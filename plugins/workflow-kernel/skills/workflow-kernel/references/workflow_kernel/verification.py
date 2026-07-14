"""Declared persona coverage and browser evidence contracts."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Iterable, Tuple

from .adapters.base import invalid_policy
from .redaction import normalize_evidence_reference

_ID = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")
VIEWPORT_DIMENSION_PATTERN = (
    r"(?:[1-9][0-9]{1,3}|1[0-5][0-9]{3}|16[0-2][0-9]{2}|"
    r"163[0-7][0-9]|1638[0-4])"
)
VIEWPORT_PATTERN = VIEWPORT_DIMENSION_PATTERN + "x" + VIEWPORT_DIMENSION_PATTERN
_VIEWPORT = re.compile("(" + VIEWPORT_DIMENSION_PATTERN + ")x(" + VIEWPORT_DIMENSION_PATTERN + r")\Z")
_ENGINES = frozenset({"chromium", "firefox", "webkit"})
_OUTCOMES = frozenset({"SUCCESS", "FRICTION", "BLOCKED", "PARTIAL"})
_PROFILE_ID = re.compile(r"profile-sha256:[0-9a-f]{64}\Z")


def _invalid(reason="invalid_verification_declaration"):
    raise invalid_policy(reason)


def _validate_id(value):
    if type(value) is not str or _ID.fullmatch(value) is None:
        _invalid()
    return value


def validate_viewport(value):
    if type(value) is not str:
        _invalid()
    match = _VIEWPORT.fullmatch(value)
    if match is None or any(int(item) > 16_384 for item in match.groups()):
        _invalid()
    return value


def digest_target_route(route):
    if (type(route) is not str or not route.startswith("/") or "?" in route
            or "#" in route or any(part == ".." for part in route.split("/"))):
        _invalid("invalid_verification_target")
    return "sha256:" + hashlib.sha256(route.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PersonaCase:
    persona_id: str
    scenario_id: str
    role: str
    route: str
    browser_engine: str
    viewport: str
    required: bool
    expected_outcome: str = "SUCCESS"
    requires_auth: bool = False
    browser_source: str = "workflow_policy_default"
    viewport_source: str = "workflow_policy_default"
    legacy_status_defaulted: bool = False

    def __post_init__(self):
        _validate_id(self.persona_id); _validate_id(self.scenario_id)
        if type(self.role) is not str or not self.role:
            _invalid()
        if (type(self.route) is not str or not self.route.startswith("/")
                or "?" in self.route or "#" in self.route
                or any(part == ".." for part in self.route.split("/"))):
            _invalid()
        if self.browser_engine not in _ENGINES:
            _invalid()
        validate_viewport(self.viewport)
        if type(self.required) is not bool or type(self.requires_auth) is not bool:
            _invalid()
        if type(self.legacy_status_defaulted) is not bool:
            _invalid()
        if self.expected_outcome not in _OUTCOMES:
            _invalid()
        if self.browser_source not in {"project_config", "workflow_policy_default"}:
            _invalid()
        if self.viewport_source not in {"project_config", "task_declaration", "persona_default", "workflow_policy_default"}:
            _invalid()

    @property
    def case_id(self):
        raw = "\0".join((self.persona_id, self.scenario_id, self.role, self.route,
                          self.browser_engine, self.viewport))
        return "case-sha256:" + hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self):
        return {"case_id": self.case_id, "persona_id": self.persona_id,
                "scenario_id": self.scenario_id, "role": self.role, "route": self.route,
                "browser_engine": self.browser_engine, "viewport": self.viewport,
                "required": self.required, "expected_outcome": self.expected_outcome,
                "requires_auth": self.requires_auth, "browser_source": self.browser_source,
                "viewport_source": self.viewport_source,
                "legacy_status_defaulted": self.legacy_status_defaulted}


@dataclass(frozen=True)
class VerificationProfile:
    schema_version: int
    source: str
    cases: Tuple[PersonaCase, ...]
    auth_field_names: Tuple[str, ...]
    discovery_status: str = "declared"
    selection_status: str = "runnable_cases"
    configured_engines: Tuple[str, ...] = ("chromium", "firefox")

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 1:
            _invalid("unsupported_verification_profile_version")
        if (self.source not in {"project_declaration", "not_declared"}
                or self.discovery_status not in {"declared", "not_declared"}
                or self.selection_status not in {
                    "runnable_cases", "optional_cases_only", "no_runnable_tasks", "not_declared",
                }):
            _invalid()
        if type(self.cases) is not tuple or any(type(case) is not PersonaCase for case in self.cases):
            _invalid()
        if (type(self.configured_engines) is not tuple
                or not self.configured_engines and self.discovery_status == "declared"
                or len(self.configured_engines) != len(set(self.configured_engines))
                or any(type(engine) is not str or engine not in _ENGINES
                       for engine in self.configured_engines)
                or any(case.browser_engine not in self.configured_engines for case in self.cases)):
            _invalid()
        ids = tuple(case.case_id for case in self.cases)
        if len(ids) != len(set(ids)):
            _invalid()
        if (type(self.auth_field_names) is not tuple
                or any(type(name) is not str or _ID.fullmatch(name) is None for name in self.auth_field_names)
                or tuple(sorted(set(self.auth_field_names))) != self.auth_field_names):
            _invalid()
        if self.discovery_status == "not_declared" and (
                self.source != "not_declared" or self.selection_status != "not_declared"
                or self.cases or self.configured_engines):
            _invalid()
        if self.discovery_status == "declared" and self.source != "project_declaration":
            _invalid()
        if self.selection_status == "no_runnable_tasks" and self.cases:
            _invalid()
        if self.selection_status == "optional_cases_only" and (
                not self.cases or any(case.required for case in self.cases)):
            _invalid()
        if self.selection_status == "runnable_cases" and (
                not self.cases or not any(case.required for case in self.cases)):
            _invalid()

    def to_dict(self):
        return {"schema_version": self.schema_version, "profile_id": self.profile_id,
                "source": self.source,
                "discovery_status": self.discovery_status,
                "selection_status": self.selection_status,
                "cases": [case.to_dict() for case in self.cases],
                "auth_field_names": list(self.auth_field_names),
                "configured_engines": list(self.configured_engines)}

    @property
    def profile_id(self):
        payload = {
            "schema_version": self.schema_version, "source": self.source,
            "discovery_status": self.discovery_status,
            "selection_status": self.selection_status,
            "configured_engines": list(self.configured_engines),
            "cases": [case.to_dict() for case in self.cases],
            "auth_field_names": list(self.auth_field_names),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "profile-sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceRef:
    case_id: str; persona_id: str; scenario_id: str; route: str
    browser_engine: str; viewport: str; attempt: int; evaluation: str
    authenticated: bool; reference: str; proof_kind: str = "browser"
    actual_browser_engine: str | None = None
    substitution_provenance: str | None = None
    verification_profile_id: str = ""
    configured_engines: Tuple[str, ...] = ()
    recovery_receipt: object | None = None

    def __post_init__(self):
        if type(self.case_id) is not str or not self.case_id.startswith("case-sha256:"):
            _invalid("invalid_verification_evidence")
        _validate_id(self.persona_id); _validate_id(self.scenario_id)
        if type(self.route) is not str or not self.route.startswith("/") or self.browser_engine not in _ENGINES:
            _invalid("invalid_verification_evidence")
        actual = self.browser_engine if self.actual_browser_engine is None else self.actual_browser_engine
        if (actual not in _ENGINES
                or self.substitution_provenance not in {None, "alternate_engine_recovery"}
                or type(self.verification_profile_id) is not str
                or _PROFILE_ID.fullmatch(self.verification_profile_id) is None
                or type(self.configured_engines) is not tuple
                or not self.configured_engines
                or len(self.configured_engines) != len(set(self.configured_engines))
                or any(type(engine) is not str or engine not in _ENGINES
                       for engine in self.configured_engines)
                or self.browser_engine not in self.configured_engines
                or actual not in self.configured_engines):
            _invalid("invalid_verification_evidence")
        if self.substitution_provenance == "alternate_engine_recovery" and actual == self.browser_engine:
            _invalid("invalid_verification_evidence")
        object.__setattr__(self, "actual_browser_engine", actual)
        validate_viewport(self.viewport)
        if type(self.attempt) is not int or self.attempt < 1 or type(self.evaluation) is not str or type(self.authenticated) is not bool:
            _invalid("invalid_verification_evidence")
        if self.proof_kind not in {"browser", "curl", "reachability"}:
            _invalid("invalid_verification_evidence")
        try:
            object.__setattr__(self, "reference", normalize_evidence_reference(self.reference))
        except Exception:
            _invalid("invalid_verification_evidence")
        if self.substitution_provenance == "alternate_engine_recovery":
            from .adapters.browser import BrowserRecoveryReceipt
            receipt = self.recovery_receipt
            if (type(receipt) is not BrowserRecoveryReceipt
                    or receipt.status != "recovered"
                    or receipt.reason_code != "alternate_engine_recovered_degraded"
                    or receipt.verification_profile_id != self.verification_profile_id
                    or receipt.configured_engines != self.configured_engines
                    or receipt.case_id != self.case_id
                    or receipt.requested_engine != self.browser_engine
                    or receipt.actual_engine != actual
                    or receipt.substitution_provenance != self.substitution_provenance
                    or receipt.viewport != self.viewport
                    or receipt.target_route_digest != digest_target_route(self.route)
                    or not receipt.attempts
                    or receipt.attempts[-1].attempt_number != self.attempt
                    or receipt.attempts[-1].result != "passed"
                    or receipt.attempts[-1].screenshot_reference != self.reference):
                _invalid("invalid_verification_evidence")
        elif self.recovery_receipt is not None:
            _invalid("invalid_verification_evidence")


@dataclass(frozen=True)
class CoverageDecision:
    allowed: bool; reason_code: str
    missing_case_ids: Tuple[str, ...] = (); invalid_case_ids: Tuple[str, ...] = ()


class VerificationGate:
    def evaluate(self, profile, evidence: Iterable[EvidenceRef], *, work_kind="ui"):
        if type(profile) is not VerificationProfile or work_kind not in {"ui", "integration", "logic", "documentation"}:
            _invalid("invalid_verification_gate")
        if profile.discovery_status == "not_declared":
            return CoverageDecision(work_kind not in {"ui", "integration"},
                                    "persona_declarations_not_declared" if work_kind in {"ui", "integration"} else "persona_declarations_not_applicable")
        if profile.selection_status == "no_runnable_tasks":
            return CoverageDecision(True, "no_runnable_persona_cases_declared")
        supplied = tuple(evidence)
        if any(type(item) is not EvidenceRef for item in supplied):
            _invalid("invalid_verification_evidence")
        required = {case.case_id: case for case in profile.cases if case.required}
        passing, invalid = set(), set()
        for item in supplied:
            case = required.get(item.case_id)
            if case is None:
                continue
            engine_matches = (
                item.browser_engine == case.browser_engine
                and item.verification_profile_id == profile.profile_id
                and item.configured_engines == profile.configured_engines
                and item.browser_engine in profile.configured_engines
                and item.actual_browser_engine in profile.configured_engines
                and (
                    item.actual_browser_engine == case.browser_engine
                    and item.substitution_provenance is None
                    or item.actual_browser_engine != case.browser_engine
                    and item.substitution_provenance == "alternate_engine_recovery"
                )
            )
            matches = (item.persona_id == case.persona_id and item.scenario_id == case.scenario_id
                       and item.route == case.route and item.browser_engine == case.browser_engine
                       and item.viewport == case.viewport and item.proof_kind == "browser"
                       and item.evaluation == case.expected_outcome
                       and engine_matches and (not case.requires_auth or item.authenticated))
            (passing if matches else invalid).add(case.case_id)
        missing = tuple(sorted(set(required) - passing))
        if missing:
            return CoverageDecision(False, "missing_required_persona_evidence", missing, tuple(sorted(invalid)))
        if not required:
            return CoverageDecision(True, "optional_persona_cases_only")
        return CoverageDecision(True, "required_persona_coverage_complete")
