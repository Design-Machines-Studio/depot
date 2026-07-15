"""Declared persona coverage and browser evidence contracts."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields, replace
from typing import Iterable, Tuple
from urllib.parse import unquote, urlsplit

from .model import _register_origin, _validate_capture, invalid_policy
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
_CASE_ID = re.compile(r"case-sha256:[0-9a-f]{64}\Z")
_ORIGIN_ID = re.compile(r"origin-sha256:[0-9a-f]{64}\Z")
_CREDENTIAL_VALUE = re.compile(
    r"(?:sk-|gh[pousr]_|xox[baprs]-|bearer\s)", re.IGNORECASE | re.ASCII,
)
_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_PERCENT_BYTE = re.compile(r"%([0-9A-Fa-f]{2})")
_UNRESERVED_BYTES = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)
_COVERAGE_DIAGNOSTICS = frozenset({
    "coverage_matrix_mismatch", "unresolved_route_parameters",
})
_ROUTE_BINDING_GAP = re.compile(
    r"[a-z0-9][a-z0-9._-]{0,127}:[a-z][a-z0-9_]*(?:,[a-z][a-z0-9_]*)*\Z",
)


def _invalid(reason="invalid_verification_declaration"):
    raise invalid_policy(reason)


def _field_values(value, expected_type):
    return tuple(getattr(value, field.name) for field in fields(expected_type))


def _unsafe_route_character(character):
    codepoint = ord(character)
    return codepoint < 32 or codepoint == 127 or 0xD800 <= codepoint <= 0xDFFF


def _validate_id(value, *, reject_secret_shape=False):
    secret_parts = {"token", "key", "secret", "password", "authorization", "cookie", "dsn"}
    if (type(value) is not str or len(value) > 128 or _ID.fullmatch(value) is None
            or reject_secret_shape
            and any(part in secret_parts for part in re.split(r"[._-]", value.casefold()))):
        _invalid()
    return value


def validate_viewport(value):
    if type(value) is not str:
        _invalid()
    match = _VIEWPORT.fullmatch(value)
    if match is None or any(int(item) > 16_384 for item in match.groups()):
        _invalid()
    return value


def _validate_route(route):
    if (type(route) is not str or len(route) > 2_048
            or not route.startswith("/") or route.startswith("//")
            or "?" in route or "#" in route or "\\" in route
            or any(_unsafe_route_character(character) for character in route)
            or _PERCENT_ESCAPE.search(route)):
        _invalid("invalid_verification_target")
    for raw_part in route.split("/"):
        for match in _PERCENT_BYTE.finditer(raw_part):
            byte = int(match.group(1), 16)
            if (byte in _UNRESERVED_BYTES or byte < 32 or byte == 127
                    or byte in {ord("/"), ord("\\"), ord("%")}):
                _invalid("invalid_verification_target")
        try:
            part = unquote(raw_part, errors="strict")
        except UnicodeError:
            _invalid("invalid_verification_target")
        if (part in {".", ".."} or "/" in part or "\\" in part
                or "?" in part or "#" in part
                or any(_unsafe_route_character(character) for character in part)
                or _CREDENTIAL_VALUE.match(part)):
            _invalid("invalid_verification_target")
    return route


def digest_target_route(route):
    _validate_route(route)
    return "sha256:" + hashlib.sha256(route.encode("utf-8")).hexdigest()


def digest_target_origin(origin):
    if type(origin) is not str or not origin or len(origin) > 2_048:
        _invalid("invalid_verification_target")
    if any(_unsafe_route_character(character) for character in origin):
        _invalid("invalid_verification_target")
    try:
        parsed = urlsplit(origin)
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc
                or parsed.hostname is None or parsed.username is not None
                or parsed.password is not None or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment):
            _invalid("invalid_verification_target")
        port = parsed.port
    except (TypeError, ValueError):
        _invalid("invalid_verification_target")
    host = parsed.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = "[" + host + "]"
    default_port = 80 if parsed.scheme == "http" else 443
    canonical = parsed.scheme + "://" + host
    if port is not None and port != default_port:
        canonical += ":" + str(port)
    try:
        encoded = canonical.encode("utf-8")
    except UnicodeError:
        _invalid("invalid_verification_target")
    return "origin-sha256:" + hashlib.sha256(encoded).hexdigest()


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
    declared_route_digest: str = ""

    def __post_init__(self):
        _validate_id(self.persona_id); _validate_id(self.scenario_id)
        _validate_id(self.role, reject_secret_shape=True)
        _validate_route(self.route)
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
        if not self.declared_route_digest:
            object.__setattr__(self, "declared_route_digest", digest_target_route(self.route))
        elif (type(self.declared_route_digest) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", self.declared_route_digest) is None):
            _invalid()
        _register_origin(self, "PersonaCase", self._origin_primitives())

    def _origin_primitives(self):
        return _field_values(self, PersonaCase)

    @property
    def case_id(self):
        raw = "\0".join((self.persona_id, self.scenario_id, self.role, self.route,
                          self.browser_engine, self.viewport, self.declared_route_digest))
        return "case-sha256:" + hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self):
        return {"case_id": self.case_id, "persona_id": self.persona_id,
                "scenario_id": self.scenario_id, "role": self.role, "route": self.route,
                "browser_engine": self.browser_engine, "viewport": self.viewport,
                "required": self.required, "expected_outcome": self.expected_outcome,
                "requires_auth": self.requires_auth, "browser_source": self.browser_source,
                "viewport_source": self.viewport_source,
                "legacy_status_defaulted": self.legacy_status_defaulted,
                "declared_route_digest": self.declared_route_digest}


@dataclass(frozen=True)
class VerificationProfile:
    schema_version: int
    source: str
    cases: Tuple[PersonaCase, ...]
    auth_field_names: Tuple[str, ...]
    discovery_status: str = "declared"
    selection_status: str = "runnable_cases"
    configured_engines: Tuple[str, ...] = ("chromium", "firefox")
    target_origin_digest: str | None = None
    coverage_diagnostics: Tuple[str, ...] = ()
    route_binding_gaps: Tuple[str, ...] = ()

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 1:
            _invalid("unsupported_verification_profile_version")
        if (self.source not in {"project_declaration", "not_declared"}
                or self.discovery_status not in {"declared", "not_declared"}
                or self.selection_status not in {
                    "runnable_cases", "optional_cases_only", "no_runnable_tasks",
                    "blocked_route_bindings", "not_declared",
                }):
            _invalid()
        if type(self.cases) is not tuple or any(type(case) is not PersonaCase for case in self.cases):
            _invalid()
        try:
            canonical_cases = tuple(sorted(
                (_snapshot_persona_case(case) for case in self.cases),
                key=lambda case: case.case_id,
            ))
        except Exception:
            _invalid()
        object.__setattr__(self, "cases", canonical_cases)
        if (type(self.configured_engines) is not tuple
                or not self.configured_engines and self.discovery_status == "declared"
                or any(type(engine) is not str or engine not in _ENGINES
                       for engine in self.configured_engines)
                or len(self.configured_engines) != len(set(self.configured_engines))
                or any(case.browser_engine not in self.configured_engines for case in self.cases)):
            _invalid()
        ids = tuple(case.case_id for case in self.cases)
        if len(ids) != len(set(ids)):
            _invalid()
        if (type(self.auth_field_names) is not tuple
                or any(type(name) is not str or len(name) > 128
                       or _ID.fullmatch(name) is None for name in self.auth_field_names)
                or len(self.auth_field_names) != len(set(self.auth_field_names))):
            _invalid()
        object.__setattr__(self, "auth_field_names", tuple(sorted(self.auth_field_names)))
        if (type(self.coverage_diagnostics) is not tuple
                or any(type(item) is not str or item not in _COVERAGE_DIAGNOSTICS
                       for item in self.coverage_diagnostics)
                or len(self.coverage_diagnostics) != len(set(self.coverage_diagnostics))):
            _invalid()
        object.__setattr__(
            self, "coverage_diagnostics", tuple(sorted(self.coverage_diagnostics)),
        )
        if (type(self.route_binding_gaps) is not tuple
                or any(type(item) is not str or len(item) > 512
                       or _ROUTE_BINDING_GAP.fullmatch(item) is None
                       for item in self.route_binding_gaps)
                or len(self.route_binding_gaps) != len(set(self.route_binding_gaps))):
            _invalid()
        object.__setattr__(
            self, "route_binding_gaps", tuple(sorted(self.route_binding_gaps)),
        )
        if (self.target_origin_digest is not None and (
                type(self.target_origin_digest) is not str
                or _ORIGIN_ID.fullmatch(self.target_origin_digest) is None)):
            _invalid("invalid_verification_target")
        if self.discovery_status == "not_declared" and (
                self.source != "not_declared" or self.selection_status != "not_declared"
                or self.cases or self.configured_engines):
            _invalid()
        if self.discovery_status == "declared" and self.source != "project_declaration":
            _invalid()
        if self.discovery_status == "declared" and self.selection_status == "not_declared":
            _invalid()
        if self.selection_status in {"no_runnable_tasks", "blocked_route_bindings"} and self.cases:
            _invalid()
        if ((self.selection_status == "blocked_route_bindings")
                != ("unresolved_route_parameters" in self.coverage_diagnostics)):
            _invalid()
        if ((self.selection_status == "blocked_route_bindings")
                != bool(self.route_binding_gaps)):
            _invalid()
        if self.selection_status == "optional_cases_only" and (
                not self.cases or any(case.required for case in self.cases)):
            _invalid()
        if self.selection_status == "runnable_cases" and (
                not self.cases or not any(case.required for case in self.cases)):
            _invalid()
        _register_origin(self, "VerificationProfile", self._origin_primitives())

    def _origin_primitives(self):
        return (
            self.schema_version, self.source,
            tuple(case._origin_primitives() for case in self.cases),
            self.auth_field_names, self.discovery_status, self.selection_status,
            self.configured_engines, self.target_origin_digest,
            self.coverage_diagnostics,
            self.route_binding_gaps,
        )

    def to_dict(self):
        return {"schema_version": self.schema_version, "profile_id": self.profile_id,
                "source": self.source,
                "discovery_status": self.discovery_status,
                "selection_status": self.selection_status,
                "cases": [case.to_dict() for case in self.cases],
                "auth_field_names": list(self.auth_field_names),
                "configured_engines": list(self.configured_engines),
                "target_origin_digest": self.target_origin_digest,
                "coverage_diagnostics": list(self.coverage_diagnostics),
                "route_binding_gaps": list(self.route_binding_gaps)}

    @property
    def profile_id(self):
        payload = {
            "schema_version": self.schema_version, "source": self.source,
            "discovery_status": self.discovery_status,
            "selection_status": self.selection_status,
            "configured_engines": list(self.configured_engines),
            "target_origin_digest": self.target_origin_digest,
            "cases": [case.to_dict() for case in self.cases],
            "auth_field_names": list(self.auth_field_names),
            "route_binding_gaps": list(self.route_binding_gaps),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return "profile-sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def bind_target_origin(self, origin):
        return replace(self, target_origin_digest=digest_target_origin(origin))

    @classmethod
    def from_dict(cls, payload):
        expected = {
            "schema_version", "profile_id", "source", "discovery_status",
            "selection_status", "configured_engines", "target_origin_digest",
            "cases", "auth_field_names", "coverage_diagnostics",
            "route_binding_gaps",
        }
        try:
            if type(payload) is not dict or set(payload) != expected:
                raise ValueError
            raw_cases = payload["cases"]
            if type(raw_cases) is not list:
                raise ValueError
            case_keys = {
                "case_id", "persona_id", "scenario_id", "role", "route",
                "browser_engine", "viewport", "required", "expected_outcome",
                "requires_auth", "browser_source", "viewport_source",
                "legacy_status_defaulted",
                "declared_route_digest",
            }
            cases = []
            for raw in raw_cases:
                if type(raw) is not dict or set(raw) != case_keys:
                    raise ValueError
                case = PersonaCase(**{key: raw[key] for key in case_keys if key != "case_id"})
                if type(raw["case_id"]) is not str or raw["case_id"] != case.case_id:
                    raise ValueError
                cases.append(case)
            if (type(payload["configured_engines"]) is not list
                    or type(payload["auth_field_names"]) is not list
                    or type(payload["coverage_diagnostics"]) is not list
                    or type(payload["route_binding_gaps"]) is not list):
                raise ValueError
            profile = cls(
                payload["schema_version"], payload["source"], tuple(cases),
                tuple(payload["auth_field_names"]), payload["discovery_status"],
                payload["selection_status"], tuple(payload["configured_engines"]),
                payload["target_origin_digest"], tuple(payload["coverage_diagnostics"]),
                tuple(payload["route_binding_gaps"]),
            )
            if type(payload["profile_id"]) is not str or payload["profile_id"] != profile.profile_id:
                raise ValueError
            return profile
        except Exception:
            _invalid("invalid_verification_profile")


def _snapshot_persona_case(value):
    if type(value) is not PersonaCase:
        _invalid("invalid_verification_profile")
    try:
        captured = _field_values(value, PersonaCase)
        _validate_capture(value, "PersonaCase", captured, value._origin_primitives())
        return PersonaCase(*captured)
    except Exception:
        _invalid("invalid_verification_profile")


def _snapshot_verification_profile(value):
    if type(value) is not VerificationProfile:
        _invalid("invalid_verification_gate")
    try:
        captured = _field_values(value, VerificationProfile)
        cases = tuple(_snapshot_persona_case(case) for case in captured[2])
        captured = captured[:2] + (cases,) + captured[3:]
        _validate_capture(
            value, "VerificationProfile", captured, value._origin_primitives(),
        )
        return VerificationProfile(*captured)
    except Exception:
        _invalid("invalid_verification_profile")


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
    target_origin_digest: str = ""
    declared_route_digest: str = ""

    def _origin_primitives(self):
        receipt = self.recovery_receipt
        receipt_payload = None
        if receipt is not None:
            try:
                receipt_payload = json.dumps(
                    receipt.to_dict(), sort_keys=True, separators=(",", ":"),
                )
            except Exception:
                _invalid("invalid_verification_evidence")
        return (
            self.case_id, self.persona_id, self.scenario_id, self.route,
            self.browser_engine, self.viewport, self.attempt, self.evaluation,
            self.authenticated, self.reference, self.proof_kind,
            self.actual_browser_engine, self.substitution_provenance,
            self.verification_profile_id, self.configured_engines,
            receipt_payload, self.target_origin_digest,
            self.declared_route_digest,
        )

    def __post_init__(self):
        if type(self.case_id) is not str or not self.case_id.startswith("case-sha256:"):
            _invalid("invalid_verification_evidence")
        _validate_id(self.persona_id); _validate_id(self.scenario_id)
        try:
            _validate_route(self.route)
        except Exception:
            _invalid("invalid_verification_evidence")
        if self.browser_engine not in _ENGINES:
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
        if (type(self.target_origin_digest) is not str
                or _ORIGIN_ID.fullmatch(self.target_origin_digest) is None):
            _invalid("invalid_verification_evidence")
        if not self.declared_route_digest:
            object.__setattr__(self, "declared_route_digest", digest_target_route(self.route))
        elif (type(self.declared_route_digest) is not str
                or re.fullmatch(r"sha256:[0-9a-f]{64}", self.declared_route_digest) is None):
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
        if self.proof_kind == "browser":
            from .adapters.browser import snapshot_browser_recovery_receipt
            try:
                receipt = snapshot_browser_recovery_receipt(self.recovery_receipt)
            except Exception:
                _invalid("invalid_verification_evidence")
            object.__setattr__(self, "recovery_receipt", receipt)
            expected_reason = (
                "alternate_engine_recovered_degraded"
                if self.substitution_provenance == "alternate_engine_recovery"
                else {"browser_verified_first_pass", "primary_recovered_degraded"}
            )
            if (receipt.status not in {"clean", "recovered"}
                    or (receipt.reason_code != expected_reason
                        if type(expected_reason) is str
                        else receipt.reason_code not in expected_reason)
                    or receipt.verification_profile_id != self.verification_profile_id
                    or receipt.configured_engines != self.configured_engines
                    or receipt.case_id != self.case_id
                    or receipt.requested_engine != self.browser_engine
                    or receipt.actual_engine != actual
                    or receipt.substitution_provenance != self.substitution_provenance
                    or receipt.viewport != self.viewport
                    or receipt.target_origin_digest != self.target_origin_digest
                    or receipt.target_route_digest != digest_target_route(self.route)
                    or receipt.declared_route_digest != self.declared_route_digest
                    or not receipt.attempts
                    or receipt.attempts[-1].attempt_number != self.attempt
                    or receipt.attempts[-1].result != "passed"
                    or receipt.attempts[-1].screenshot_reference != self.reference):
                _invalid("invalid_verification_evidence")
        elif self.recovery_receipt is not None:
            _invalid("invalid_verification_evidence")
        _register_origin(self, "EvidenceRef", self._origin_primitives())


def _snapshot_evidence_ref(value):
    if type(value) is not EvidenceRef:
        _invalid("invalid_verification_evidence")
    try:
        captured = _field_values(value, EvidenceRef)
        _validate_capture(
            value, "EvidenceRef", captured, value._origin_primitives(),
        )
        return EvidenceRef(*captured)
    except Exception:
        _invalid("invalid_verification_evidence")


@dataclass(frozen=True)
class CoverageDecision:
    allowed: bool; reason_code: str
    missing_case_ids: Tuple[str, ...] = (); invalid_case_ids: Tuple[str, ...] = ()
    route_binding_gaps: Tuple[str, ...] = ()


class VerificationGate:
    def evaluate(self, profile, evidence: Iterable[EvidenceRef], *, work_kind="ui"):
        if work_kind not in {"ui", "integration", "logic", "documentation"}:
            _invalid("invalid_verification_gate")
        profile = _snapshot_verification_profile(profile)
        try:
            supplied = tuple(_snapshot_evidence_ref(item) for item in evidence)
        except Exception:
            _invalid("invalid_verification_evidence")
        if profile.discovery_status == "not_declared":
            return CoverageDecision(work_kind not in {"ui", "integration"},
                                    "persona_declarations_not_declared" if work_kind in {"ui", "integration"} else "persona_declarations_not_applicable")
        if profile.selection_status == "no_runnable_tasks":
            return CoverageDecision(True, "no_runnable_persona_cases_declared")
        if profile.selection_status == "blocked_route_bindings":
            return CoverageDecision(
                False, "unresolved_route_parameters",
                route_binding_gaps=profile.route_binding_gaps,
            )
        required = {case.case_id: case for case in profile.cases if case.required}
        if required and profile.target_origin_digest is None:
            return CoverageDecision(
                False, "verification_target_unbound", tuple(sorted(required)), (),
            )
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
                and item.target_origin_digest == profile.target_origin_digest
                and (
                    item.actual_browser_engine == case.browser_engine
                    and item.substitution_provenance is None
                    or item.actual_browser_engine != case.browser_engine
                    and item.substitution_provenance == "alternate_engine_recovery"
                )
            )
            matches = (item.persona_id == case.persona_id and item.scenario_id == case.scenario_id
                       and item.route == case.route and item.browser_engine == case.browser_engine
                       and item.declared_route_digest == case.declared_route_digest
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
