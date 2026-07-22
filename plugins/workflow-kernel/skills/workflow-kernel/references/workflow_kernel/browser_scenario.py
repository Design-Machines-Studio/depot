"""Strict, data-only browser scenario declarations."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields

from .browser_target import _validate_route, validate_viewport
from .model import _register_origin, _validate_capture
from .redaction import (
    contains_high_confidence_secret, normalize_durable_string,
    normalize_evidence_reference,
)


SCHEMA_VERSION = 1
MAX_STEPS = 512
MAX_FIXTURES = 128
_ID = re.compile(r"[a-z0-9][a-z0-9._:-]{0,127}\Z")
_CASE_ID = re.compile(r"case-sha256:[0-9a-f]{64}\Z")
_PROFILE_ID = re.compile(r"profile-sha256:[0-9a-f]{64}\Z")
_ORIGIN = re.compile(r"origin-sha256:[0-9a-f]{64}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ENGINES = frozenset({"chromium", "firefox", "webkit"})
_LOCATOR_KINDS = frozenset({"selector", "role", "label", "none"})
_ASSERTIONS = frozenset({
    "url", "status", "visibility", "text", "count", "focus", "toast",
    "validation", "a11y", "console", "network", "computed_style", "overflow",
})
_STEP_FIELDS = {
    "navigate": frozenset({"route"}),
    "interact": frozenset({"locator_kind", "locator", "action", "value_ref"}),
    "state_fixture": frozenset({
        "profile_ref", "cookie_jar_ref", "environment_fixture_refs", "login_fixture_ref",
    }),
    "login": frozenset({"lifecycle", "fixture_ref"}),
    "javascript": frozenset({"enabled"}),
    "assertion": frozenset({"assertion", "locator_kind", "locator", "expected"}),
    "capture": frozenset({"capture_kind", "artifact_ref"}),
    "human_pause": frozenset({"pause_id", "action"}),
    "application_restart": frozenset({"session_expectation"}),
    "primary_quit": frozenset(),
    "primary_launch": frozenset({"fresh_profile"}),
    "session_assertion": frozenset({"expectation"}),
    "primary_retry": frozenset({"attempt"}),
    "alternate_engine": frozenset({"engine"}),
    "terminal": frozenset({"status", "reason"}),
}


def _canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _safe_string(value, name, *, maximum=512, nullable=False):
    if nullable and value is None:
        return None
    if (
        type(value) is not str or not value or len(value) > maximum
        or any(ord(char) < 0x20 or ord(char) == 0x7f for char in value)
        or contains_high_confidence_secret(value)
    ):
        raise ValueError(f"invalid {name}")
    try:
        if normalize_durable_string(value) != value:
            raise ValueError(f"unsafe {name}")
    except ValueError:
        raise ValueError(f"unsafe {name}") from None
    return value


def _safe_id(value, name="identifier"):
    value = _safe_string(value, name, maximum=128)
    if _ID.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")
    return value


def _safe_locator(kind, value):
    if kind not in _LOCATOR_KINDS:
        raise ValueError("invalid locator kind")
    if kind == "none":
        if value is not None:
            raise ValueError("locator must be absent")
        return None
    value = _safe_string(value, "locator", maximum=256)
    lowered = value.casefold().lstrip()
    if lowered.startswith(("javascript:", "xpath=", "//", "eval(", "function(")):
        raise ValueError("unsafe locator")
    if kind == "selector" and not value.startswith(("#", ".", "[data-", "[aria-", "[name=")):
        raise ValueError("selector is not stable")
    return value


def _fixture_ref(value, name, *, nullable=False):
    if nullable and value is None:
        return None
    value = _safe_string(value, name, maximum=256)
    try:
        normalized = normalize_evidence_reference(value)
    except ValueError:
        raise ValueError(f"invalid {name}") from None
    if normalized != value:
        raise ValueError(f"invalid {name}")
    return normalized


def _validate_expected(value):
    if value is None or type(value) in {bool, int}:
        return value
    return _safe_string(value, "assertion expected value", maximum=512)


def _assertion_expected(kind, value):
    value = _validate_expected(value)
    if kind == "status" and (type(value) is not int or not 100 <= value <= 599):
        raise ValueError("invalid status assertion")
    if kind == "count" and (type(value) is not int or not 0 <= value <= 1_000_000):
        raise ValueError("invalid count assertion")
    if kind in {"visibility", "focus", "overflow"} and type(value) is not bool:
        raise ValueError("invalid boolean assertion")
    if kind == "url":
        value = _validate_route(value)
    return value


def _validate_payload(kind, payload):
    if type(payload) is not dict or set(payload) != _STEP_FIELDS.get(kind):
        raise ValueError("scenario step fields mismatch")
    result = dict(payload)
    if kind == "navigate":
        result["route"] = _validate_route(result["route"])
    elif kind == "interact":
        result["locator"] = _safe_locator(result["locator_kind"], result["locator"])
        if result["locator_kind"] == "none" or result["action"] not in {
            "click", "fill", "check", "uncheck", "select", "press",
        }:
            raise ValueError("invalid interaction")
        result["value_ref"] = _fixture_ref(result["value_ref"], "value_ref", nullable=True)
        if (result["action"] in {"fill", "select", "press"}) != (result["value_ref"] is not None):
            raise ValueError("interaction value reference mismatch")
    elif kind == "state_fixture":
        result["profile_ref"] = _fixture_ref(result["profile_ref"], "profile_ref")
        result["cookie_jar_ref"] = _fixture_ref(result["cookie_jar_ref"], "cookie_jar_ref", nullable=True)
        refs = result["environment_fixture_refs"]
        if type(refs) not in {list, tuple} or len(refs) > MAX_FIXTURES:
            raise ValueError("invalid environment fixtures")
        result["environment_fixture_refs"] = tuple(
            _fixture_ref(item, "environment fixture") for item in refs
        )
        if len(result["environment_fixture_refs"]) != len(set(result["environment_fixture_refs"])):
            raise ValueError("duplicate environment fixture")
        result["login_fixture_ref"] = _fixture_ref(
            result["login_fixture_ref"], "login_fixture_ref", nullable=True,
        )
    elif kind == "login":
        if result["lifecycle"] not in {
            "success", "expected_rejection", "human_action_required", "auth_verification",
        }:
            raise ValueError("invalid login lifecycle")
        result["fixture_ref"] = _fixture_ref(result["fixture_ref"], "fixture_ref", nullable=True)
        if result["lifecycle"] in {"success", "expected_rejection"} and result["fixture_ref"] is None:
            raise ValueError("login fixture required")
    elif kind == "javascript":
        if type(result["enabled"]) is not bool:
            raise ValueError("invalid javascript state")
    elif kind == "assertion":
        if result["assertion"] not in _ASSERTIONS:
            raise ValueError("invalid assertion")
        result["locator"] = _safe_locator(result["locator_kind"], result["locator"])
        needs_locator = result["assertion"] in {
            "visibility", "text", "count", "focus", "toast", "validation", "computed_style",
        }
        if needs_locator == (result["locator_kind"] == "none"):
            raise ValueError("assertion locator mismatch")
        result["expected"] = _assertion_expected(result["assertion"], result["expected"])
    elif kind == "capture":
        if result["capture_kind"] not in {
            "screenshot", "trace", "console", "network", "a11y",
        }:
            raise ValueError("invalid evidence capture")
        result["artifact_ref"] = _fixture_ref(result["artifact_ref"], "artifact_ref")
    elif kind == "human_pause":
        result["pause_id"] = _safe_id(result["pause_id"], "pause_id")
        if result["action"] not in {"mfa", "passkey", "qr_scan", "external_sign_in"}:
            raise ValueError("invalid human action")
    elif kind == "application_restart":
        if result["session_expectation"] not in {"preserved", "cleared", "refreshed"}:
            raise ValueError("invalid restart session expectation")
    elif kind == "primary_launch":
        if result["fresh_profile"] is not True:
            raise ValueError("primary launch must be fresh")
    elif kind == "session_assertion":
        if result["expectation"] not in {"new", "preserved", "cleared", "authenticated", "anonymous"}:
            raise ValueError("invalid session expectation")
    elif kind == "primary_retry":
        if type(result["attempt"]) is not int or not 2 <= result["attempt"] <= 3:
            raise ValueError("invalid primary retry")
    elif kind == "alternate_engine":
        if result["engine"] not in _ENGINES:
            raise ValueError("invalid alternate engine")
    elif kind == "terminal":
        if result["status"] not in {
            "passed", "human_action_required", "human_help_required", "application_failure",
        } or result["reason"] not in {
            "first_pass", "fresh_primary", "alternate_engine", "human_action_required",
            "human_help_required", "application_failure",
        }:
            raise ValueError("invalid terminal status")
        if result["status"] != "passed" and result["status"] != result["reason"]:
            raise ValueError("terminal status mismatch")
    return tuple(sorted(result.items()))


@dataclass(frozen=True)
class BrowserScenarioStep:
    step_id: str
    kind: str
    payload: tuple[tuple[str, object], ...]

    def __post_init__(self):
        step_id = _safe_id(self.step_id, "step_id")
        if self.kind not in _STEP_FIELDS or type(self.payload) not in {tuple, list}:
            raise ValueError("invalid scenario step")
        try:
            payload = dict(self.payload)
        except (TypeError, ValueError):
            raise ValueError("invalid scenario step payload") from None
        canonical = _validate_payload(self.kind, payload)
        object.__setattr__(self, "step_id", step_id)
        object.__setattr__(self, "payload", canonical)
        _register_origin(self, "BrowserScenarioStep", self._origin_primitives())

    def _origin_primitives(self):
        return self.step_id, self.kind, self.payload

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != {"step_id", "kind", "payload"}:
            raise ValueError("scenario step fields mismatch")
        if type(value["payload"]) is not dict:
            raise ValueError("invalid scenario step payload")
        return cls(value["step_id"], value["kind"], tuple(value["payload"].items()))

    def to_dict(self):
        payload = dict(self.payload)
        if self.kind == "state_fixture":
            payload["environment_fixture_refs"] = list(payload["environment_fixture_refs"])
        return {"step_id": self.step_id, "kind": self.kind, "payload": payload}


def snapshot_browser_scenario_step(value):
    if type(value) is not BrowserScenarioStep:
        raise ValueError("invalid browser scenario step")
    try:
        captured = tuple(getattr(value, item.name) for item in fields(BrowserScenarioStep))
        _validate_capture(value, "BrowserScenarioStep", captured, value._origin_primitives())
        return BrowserScenarioStep(*captured)
    except Exception:
        raise ValueError("invalid browser scenario step") from None


@dataclass(frozen=True)
class BrowserScenario:
    schema_version: int
    scenario_id: str
    case_id: str
    profile_id: str
    persona_id: str
    target_origin_digest: str
    initial_route: str
    primary_engine: str
    alternate_engine: str | None
    viewport: str
    steps: tuple[BrowserScenarioStep, ...]
    scenario_digest: str = ""

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported browser scenario version")
        _safe_id(self.scenario_id, "scenario_id"); _safe_id(self.persona_id, "persona_id")
        if type(self.case_id) is not str or _CASE_ID.fullmatch(self.case_id) is None:
            raise ValueError("invalid case binding")
        if type(self.profile_id) is not str or _PROFILE_ID.fullmatch(self.profile_id) is None:
            raise ValueError("invalid profile binding")
        if type(self.target_origin_digest) is not str or _ORIGIN.fullmatch(self.target_origin_digest) is None:
            raise ValueError("invalid origin binding")
        _validate_route(self.initial_route); validate_viewport(self.viewport)
        if self.primary_engine not in _ENGINES or (
            self.alternate_engine is not None
            and (self.alternate_engine not in _ENGINES or self.alternate_engine == self.primary_engine)
        ):
            raise ValueError("invalid scenario engines")
        if type(self.steps) is not tuple or not self.steps or len(self.steps) > MAX_STEPS:
            raise ValueError("invalid scenario steps")
        steps = tuple(snapshot_browser_scenario_step(item) for item in self.steps)
        if len({item.step_id for item in steps}) != len(steps) or steps[-1].kind != "terminal":
            raise ValueError("invalid scenario step ordering")
        alternate_steps = [dict(item.payload)["engine"] for item in steps if item.kind == "alternate_engine"]
        if alternate_steps and (self.alternate_engine is None or any(
            engine != self.alternate_engine for engine in alternate_steps
        )):
            raise ValueError("alternate engine is not declared")
        object.__setattr__(self, "steps", steps)
        expected = "sha256:" + hashlib.sha256(_canonical_bytes(self._body())).hexdigest()
        if self.scenario_digest and (type(self.scenario_digest) is not str or self.scenario_digest != expected):
            raise ValueError("scenario digest mismatch")
        object.__setattr__(self, "scenario_digest", expected)
        _register_origin(self, "BrowserScenario", self._origin_primitives())

    def _body(self):
        return {
            "schema_version": self.schema_version, "scenario_id": self.scenario_id,
            "case_id": self.case_id, "profile_id": self.profile_id,
            "persona_id": self.persona_id, "target_origin_digest": self.target_origin_digest,
            "initial_route": self.initial_route, "primary_engine": self.primary_engine,
            "alternate_engine": self.alternate_engine, "viewport": self.viewport,
            "steps": [item.to_dict() for item in self.steps],
        }

    def _origin_primitives(self):
        return tuple(self._body().values()) + (self.scenario_digest,)

    def to_dict(self):
        return {**self._body(), "scenario_digest": self.scenario_digest}

    @classmethod
    def from_dict(cls, value):
        expected = {
            "schema_version", "scenario_id", "case_id", "profile_id", "persona_id",
            "target_origin_digest", "initial_route", "primary_engine", "alternate_engine",
            "viewport", "steps", "scenario_digest",
        }
        if type(value) is not dict or set(value) != expected or type(value["steps"]) is not list:
            raise ValueError("browser scenario fields mismatch")
        return cls(
            value["schema_version"], value["scenario_id"], value["case_id"],
            value["profile_id"], value["persona_id"], value["target_origin_digest"],
            value["initial_route"], value["primary_engine"], value["alternate_engine"],
            value["viewport"], tuple(BrowserScenarioStep.from_dict(item) for item in value["steps"]),
            value["scenario_digest"],
        )


def snapshot_browser_scenario(value):
    if type(value) is not BrowserScenario:
        raise ValueError("invalid browser scenario")
    try:
        captured = tuple(getattr(value, item.name) for item in fields(BrowserScenario))
        _validate_capture(value, "BrowserScenario", captured, value._origin_primitives())
        return BrowserScenario(*captured)
    except Exception:
        raise ValueError("invalid browser scenario") from None
