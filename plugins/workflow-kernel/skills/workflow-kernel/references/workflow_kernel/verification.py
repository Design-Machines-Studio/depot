"""Declared persona coverage and browser evidence contracts."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable, Tuple

from .adapters.base import invalid_policy
from .redaction import normalize_evidence_reference

_ID = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")
_VIEWPORT = re.compile(r"([1-9][0-9]{1,4})x([1-9][0-9]{1,4})\Z")
_ENGINES = frozenset({"chromium", "firefox", "webkit"})
_OUTCOMES = frozenset({"SUCCESS", "FRICTION", "BLOCKED", "PARTIAL"})


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

    def __post_init__(self):
        if self.schema_version != 1:
            _invalid("unsupported_verification_profile_version")
        if self.source not in {"project_declaration", "not_declared"} or self.discovery_status not in {"declared", "not_declared"}:
            _invalid()
        if type(self.cases) is not tuple or any(type(case) is not PersonaCase for case in self.cases):
            _invalid()
        ids = tuple(case.case_id for case in self.cases)
        if len(ids) != len(set(ids)):
            _invalid()
        if (type(self.auth_field_names) is not tuple
                or any(type(name) is not str or _ID.fullmatch(name) is None for name in self.auth_field_names)
                or tuple(sorted(set(self.auth_field_names))) != self.auth_field_names):
            _invalid()
        if self.discovery_status == "not_declared" and self.cases:
            _invalid()

    def to_dict(self):
        return {"schema_version": self.schema_version, "source": self.source,
                "discovery_status": self.discovery_status,
                "cases": [case.to_dict() for case in self.cases],
                "auth_field_names": list(self.auth_field_names)}


@dataclass(frozen=True)
class EvidenceRef:
    case_id: str; persona_id: str; scenario_id: str; route: str
    browser_engine: str; viewport: str; attempt: int; evaluation: str
    authenticated: bool; reference: str; proof_kind: str = "browser"

    def __post_init__(self):
        if type(self.case_id) is not str or not self.case_id.startswith("case-sha256:"):
            _invalid("invalid_verification_evidence")
        _validate_id(self.persona_id); _validate_id(self.scenario_id)
        if type(self.route) is not str or not self.route.startswith("/") or self.browser_engine not in _ENGINES:
            _invalid("invalid_verification_evidence")
        validate_viewport(self.viewport)
        if type(self.attempt) is not int or self.attempt < 1 or type(self.evaluation) is not str or type(self.authenticated) is not bool:
            _invalid("invalid_verification_evidence")
        if self.proof_kind not in {"browser", "curl", "reachability"}:
            _invalid("invalid_verification_evidence")
        try:
            object.__setattr__(self, "reference", normalize_evidence_reference(self.reference))
        except Exception:
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
        supplied = tuple(evidence)
        if any(type(item) is not EvidenceRef for item in supplied):
            _invalid("invalid_verification_evidence")
        required = {case.case_id: case for case in profile.cases if case.required}
        passing, invalid = set(), set()
        for item in supplied:
            case = required.get(item.case_id)
            if case is None:
                continue
            matches = (item.persona_id == case.persona_id and item.scenario_id == case.scenario_id
                       and item.route == case.route and item.browser_engine == case.browser_engine
                       and item.viewport == case.viewport and item.proof_kind == "browser"
                       and item.evaluation == case.expected_outcome
                       and (not case.requires_auth or item.authenticated))
            (passing if matches else invalid).add(case.case_id)
        missing = tuple(sorted(set(required) - passing))
        if missing:
            return CoverageDecision(False, "missing_required_persona_evidence", missing, tuple(sorted(invalid)))
        return CoverageDecision(True, "required_persona_coverage_complete")
