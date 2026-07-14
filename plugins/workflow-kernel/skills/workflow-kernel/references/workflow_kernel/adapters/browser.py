"""Deterministic, case-bound browser recovery using injected host adapters."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, fields, replace
from typing import Optional, Protocol, Tuple
from urllib.parse import urlsplit

from .base import _register_origin, _validate_capture
from ..redaction import digest_error_detail_string, normalize_evidence_reference
from ..verification import digest_target_origin, digest_target_route, validate_viewport

_ENGINES = frozenset({"chromium", "firefox", "webkit"})
_RESULTS = frozenset({"passed", "failed", "unavailable"})
_REASON_CODES = frozenset({
    "adapter_exception", "invalid_adapter_evidence", "browser_tool_failure",
    "browser_unavailable", "curl_not_browser_evidence", "session_identity_mismatch",
    "fresh_profile_unavailable", "secondary_engine_unavailable",
})
_ATTEMPT_REASON_CODES = frozenset({
    "adapter_exception", "invalid_adapter_evidence", "browser_tool_failure",
    "browser_unavailable", "curl_not_browser_evidence", "session_identity_mismatch",
})
_SESSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_PROFILE_ID = re.compile(r"profile-sha256:[0-9a-f]{64}\Z")
_TARGET_DIGEST = re.compile(r"(?:sha256|url-sha256):[0-9a-f]{64}\Z")
_ORIGIN_DIGEST = re.compile(r"origin-sha256:[0-9a-f]{64}\Z")
_SUBSTITUTION = "alternate_engine_recovery"
_RECEIPT_REASONS = frozenset({
    "browser_verified_first_pass", "primary_recovered_degraded",
    "alternate_engine_recovered_degraded", "human_help_required",
})


def _field_values(value, expected_type):
    return tuple(getattr(value, field.name) for field in fields(expected_type))


def _safe_case_id(value):
    if type(value) is not str or not value or len(value) > 128 or any(
            character.isspace() or character in "/?#@" for character in value):
        raise ValueError("invalid browser case id")
    return value


def _safe_session_id(value):
    if type(value) is not str or _SESSION.fullmatch(value) is None:
        raise ValueError("invalid browser session id")
    return value


def _safe_detail(value):
    if value is None:
        return None
    if type(value) is not str:
        raise ValueError("invalid browser failure detail")
    return digest_error_detail_string(value)


def _sealed_exception_detail(error):
    """Return a digest even when attacker-controlled exception rendering fails."""
    try:
        rendered = str(error)
        if type(rendered) is not str:
            raise TypeError("invalid exception rendering")
    except BaseException:
        rendered = "unrenderable-adapter-exception"
    return digest_error_detail_string(rendered)


def _target_metadata(url):
    if type(url) is not str or not url or len(url) > 65_536:
        raise ValueError("invalid browser target")
    try:
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.netloc
                or parsed.hostname is None or parsed.username is not None
                or parsed.password is not None):
            raise ValueError("invalid browser target")
        port = parsed.port
    except (TypeError, ValueError):
        raise ValueError("invalid browser target") from None
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = "[" + host + "]"
    origin = parsed.scheme + "://" + host
    if port is not None:
        origin += ":" + str(port)
    return (
        "url-sha256:" + hashlib.sha256(url.encode("utf-8")).hexdigest(),
        digest_target_origin(origin),
        digest_target_route(parsed.path or "/"),
    )


def _validate_profile_binding(profile_id, engines):
    if (type(profile_id) is not str or _PROFILE_ID.fullmatch(profile_id) is None
            or type(engines) is not tuple or not engines
            or any(type(engine) is not str or engine not in _ENGINES for engine in engines)
            or len(engines) != len(set(engines))):
        raise ValueError("invalid verification profile binding")


def _validate_target_binding(url_digest, origin_digest, route_digest, viewport):
    if (type(url_digest) is not str or not url_digest.startswith("url-sha256:")
            or _TARGET_DIGEST.fullmatch(url_digest) is None
            or type(origin_digest) is not str
            or _ORIGIN_DIGEST.fullmatch(origin_digest) is None
            or type(route_digest) is not str or not route_digest.startswith("sha256:")
            or _TARGET_DIGEST.fullmatch(route_digest) is None):
        raise ValueError("invalid browser target binding")
    validate_viewport(viewport)


@dataclass(frozen=True)
class BrowserRequest:
    case_id: str; url: str; viewport: str; primary_engine: str; secondary_engine: Optional[str]
    verification_profile_id: str; configured_engines: Tuple[str, ...]
    target_origin_digest: str

    def _origin_primitives(self):
        metadata = _target_metadata(self.url)
        return (
            self.case_id, metadata[0], metadata[1], metadata[2], self.viewport,
            self.primary_engine, self.secondary_engine, self.verification_profile_id,
            self.configured_engines, self.target_origin_digest,
        )

    def __post_init__(self):
        _safe_case_id(self.case_id)
        _target_metadata(self.url)
        validate_viewport(self.viewport)
        _validate_profile_binding(self.verification_profile_id, self.configured_engines)
        metadata = _target_metadata(self.url)
        if metadata[1] != self.target_origin_digest:
            raise ValueError("browser target origin mismatch")
        if (self.primary_engine not in _ENGINES
                or self.primary_engine not in self.configured_engines):
            raise ValueError("browser engines must be genuinely different")
        if len(self.configured_engines) == 1:
            if self.secondary_engine is not None:
                raise ValueError("single engine profile cannot name a secondary")
        elif (self.secondary_engine not in _ENGINES
                or self.primary_engine == self.secondary_engine
                or self.secondary_engine not in self.configured_engines):
            raise ValueError("browser engines must be genuinely different")
        _register_origin(self, "BrowserRequest", self._origin_primitives())

    @property
    def target_url_digest(self):
        return _target_metadata(self.url)[0]

    @property
    def target_route_digest(self):
        return _target_metadata(self.url)[2]


def snapshot_browser_request(value):
    if type(value) is not BrowserRequest:
        raise ValueError("invalid browser request")
    try:
        captured = tuple(
            getattr(value, name) for name in value.__dataclass_fields__
        )
        _validate_capture(
            value, "BrowserRequest", captured, value._origin_primitives(),
        )
        return BrowserRequest(*captured)
    except Exception:
        raise ValueError("invalid browser request") from None


@dataclass(frozen=True)
class BrowserAttempt:
    case_id: str; attempt_number: int; requested_engine: str; actual_engine: str
    action: str; result: str; reason_code: Optional[str]; failure_detail: Optional[str]
    screenshot_reference: Optional[str]; trace_reference: Optional[str]
    console_reference: Optional[str]; session_id: str; proof_kind: str = "browser"
    substitution_provenance: Optional[str] = None
    verification_profile_id: str = ""
    configured_engines: Tuple[str, ...] = ()
    target_url_digest: str = ""
    target_origin_digest: str = ""
    target_route_digest: str = ""
    viewport: str = ""

    def __post_init__(self):
        _safe_case_id(self.case_id); _safe_session_id(self.session_id)
        _validate_profile_binding(self.verification_profile_id, self.configured_engines)
        _validate_target_binding(
            self.target_url_digest, self.target_origin_digest,
            self.target_route_digest, self.viewport,
        )
        if (type(self.attempt_number) is not int or self.attempt_number < 1
                or self.requested_engine not in _ENGINES or self.actual_engine not in _ENGINES
                or self.requested_engine not in self.configured_engines
                or self.actual_engine not in self.configured_engines
                or self.action != "verify" or self.result not in _RESULTS
                or self.proof_kind not in {"browser", "curl", "reachability"}):
            raise ValueError("invalid browser attempt")
        if self.substitution_provenance not in {None, _SUBSTITUTION}:
            raise ValueError("invalid browser substitution")
        if ((self.actual_engine == self.requested_engine)
                != (self.substitution_provenance is None)):
            raise ValueError("invalid browser substitution")
        if self.result == "passed":
            if (self.reason_code is not None or self.failure_detail is not None
                    or self.proof_kind != "browser"):
                raise ValueError("inconsistent browser attempt")
        elif self.reason_code not in _ATTEMPT_REASON_CODES:
            raise ValueError("invalid browser reason code")
        object.__setattr__(self, "failure_detail", _safe_detail(self.failure_detail))
        for name in ("screenshot_reference", "trace_reference", "console_reference"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, normalize_evidence_reference(value))
        _register_origin(self, "BrowserAttempt", self._origin_primitives())

    def _origin_primitives(self):
        return _field_values(self, BrowserAttempt)

    @property
    def engine(self):
        """Compatibility alias for the engine that produced this attempt."""
        return self.actual_engine

    @property
    def failure_reason(self):
        """Compatibility alias retaining only the stable reason code."""
        return self.reason_code

    def to_dict(self):
        payload = {field.name: getattr(self, field.name) for field in fields(BrowserAttempt)}
        payload["configured_engines"] = list(self.configured_engines)
        return payload


def snapshot_browser_attempt(value):
    if type(value) is not BrowserAttempt:
        raise ValueError("invalid browser attempt")
    try:
        captured = _field_values(value, BrowserAttempt)
        _validate_capture(
            value, "BrowserAttempt", captured, value._origin_primitives(),
        )
        return BrowserAttempt(*captured)
    except Exception:
        raise ValueError("invalid browser attempt") from None


@dataclass(frozen=True)
class BrowserQuitEvidence:
    engine: str; confirmed: bool; session_id: str; action: str = "browser_process_quit"

    def __post_init__(self):
        if (self.engine not in _ENGINES or type(self.confirmed) is not bool
                or self.action not in {"browser_process_quit", "application_restart"}):
            raise ValueError("invalid browser quit evidence")
        _safe_session_id(self.session_id)


@dataclass(frozen=True)
class BrowserLaunchEvidence:
    engine: str; launched: bool; fresh_profile: bool; session_id: str
    action: str = "browser_process_launch"

    def __post_init__(self):
        if (self.engine not in _ENGINES or type(self.launched) is not bool
                or type(self.fresh_profile) is not bool or self.action != "browser_process_launch"):
            raise ValueError("invalid browser launch evidence")
        _safe_session_id(self.session_id)


@dataclass(frozen=True)
class BrowserLifecycleEvidence:
    case_id: str; requested_engine: str; actual_engine: str; action: str; result: str
    session_id: str; previous_session_id: Optional[str] = None
    reason_code: Optional[str] = None; failure_detail: Optional[str] = None
    substitution_provenance: Optional[str] = None
    fresh_profile: Optional[bool] = None

    def __post_init__(self):
        _safe_case_id(self.case_id); _safe_session_id(self.session_id)
        if self.previous_session_id is not None:
            _safe_session_id(self.previous_session_id)
        if (self.requested_engine not in _ENGINES or self.actual_engine not in _ENGINES
                or self.action not in {
                    "browser_process_quit", "browser_process_launch", "application_restart",
                    "primary_restart", "session_validation", "secondary_engine",
                }
                or self.result not in {
                    "confirmed", "unconfirmed", "launched", "unavailable",
                    "primary_restart_unavailable", "session_identity_mismatch",
                    "fresh_profile_unavailable", "secondary_engine_unavailable",
                }
                or self.substitution_provenance not in {None, _SUBSTITUTION}):
            raise ValueError("invalid browser lifecycle evidence")
        allowed_results = {
            "browser_process_quit": {"confirmed", "unconfirmed", "unavailable"},
            "application_restart": {"confirmed", "unconfirmed"},
            "browser_process_launch": {"launched", "unavailable"},
            "primary_restart": {"primary_restart_unavailable"},
            "session_validation": {"session_identity_mismatch"},
            "secondary_engine": {"secondary_engine_unavailable"},
        }
        allowed_results["browser_process_launch"].add("fresh_profile_unavailable")
        if (self.result not in allowed_results[self.action]
                or ((self.actual_engine == self.requested_engine)
                    != (self.substitution_provenance is None))):
            raise ValueError("inconsistent browser lifecycle evidence")
        if self.reason_code is not None and self.reason_code not in _REASON_CODES:
            raise ValueError("invalid browser lifecycle reason")
        object.__setattr__(self, "failure_detail", _safe_detail(self.failure_detail))
        if self.result in {"confirmed", "launched"} and (
                self.reason_code is not None or self.failure_detail is not None):
            raise ValueError("inconsistent browser lifecycle result")
        if self.result == "unavailable" and self.reason_code not in _ATTEMPT_REASON_CODES:
            raise ValueError("inconsistent browser lifecycle result")
        exact_reasons = {
            "unconfirmed": "browser_unavailable",
            "session_identity_mismatch": "session_identity_mismatch",
            "fresh_profile_unavailable": "fresh_profile_unavailable",
            "secondary_engine_unavailable": "secondary_engine_unavailable",
        }
        if (self.result in exact_reasons
                and self.reason_code != exact_reasons[self.result]):
            raise ValueError("inconsistent browser lifecycle reason")
        if (self.result == "primary_restart_unavailable"
                and self.reason_code is not None):
            raise ValueError("inconsistent browser lifecycle reason")
        if self.action == "browser_process_launch":
            if (self.result == "launched" and self.fresh_profile is not True
                    or self.result == "fresh_profile_unavailable" and self.fresh_profile is not False
                    or self.result == "unavailable" and self.fresh_profile is not None):
                raise ValueError("inconsistent browser lifecycle freshness")
        elif self.fresh_profile is not None:
            raise ValueError("unexpected browser lifecycle freshness")
        _register_origin(
            self, "BrowserLifecycleEvidence", self._origin_primitives(),
        )

    def _origin_primitives(self):
        return _field_values(self, BrowserLifecycleEvidence)

    def to_dict(self):
        return {
            field.name: getattr(self, field.name)
            for field in fields(BrowserLifecycleEvidence)
        }


def snapshot_browser_lifecycle(value):
    if type(value) is not BrowserLifecycleEvidence:
        raise ValueError("invalid browser lifecycle evidence")
    try:
        captured = _field_values(value, BrowserLifecycleEvidence)
        _validate_capture(
            value, "BrowserLifecycleEvidence", captured, value._origin_primitives(),
        )
        return BrowserLifecycleEvidence(*captured)
    except Exception:
        raise ValueError("invalid browser lifecycle evidence") from None


@dataclass(frozen=True)
class BrowserRecoveryReceipt:
    schema_version: int; status: str; reason_code: str; case_id: str
    requested_engine: str; actual_engine: str; substitution_provenance: Optional[str]
    attempts: Tuple[BrowserAttempt, ...]; lifecycle: Tuple[BrowserLifecycleEvidence, ...]
    missing_case_ids: Tuple[str, ...]
    verification_profile_id: str; configured_engines: Tuple[str, ...]
    target_url_digest: str; target_route_digest: str; viewport: str
    target_origin_digest: str

    def __post_init__(self):
        try:
            if type(self.attempts) is not tuple or type(self.lifecycle) is not tuple:
                raise ValueError
            attempts = tuple(snapshot_browser_attempt(item) for item in self.attempts)
            lifecycle = tuple(snapshot_browser_lifecycle(item) for item in self.lifecycle)
            if len(attempts) != len(self.attempts) or len(lifecycle) != len(self.lifecycle):
                raise ValueError
            object.__setattr__(self, "attempts", attempts)
            object.__setattr__(self, "lifecycle", lifecycle)
        except Exception:
            raise ValueError("invalid browser recovery receipt") from None
        _safe_case_id(self.case_id)
        _validate_profile_binding(self.verification_profile_id, self.configured_engines)
        _validate_target_binding(
            self.target_url_digest, self.target_origin_digest,
            self.target_route_digest, self.viewport,
        )
        if (type(self.schema_version) is not int or self.schema_version != 1
                or self.status not in {"clean", "recovered", "blocked"}
                or self.reason_code not in _RECEIPT_REASONS
                or self.requested_engine not in _ENGINES or self.actual_engine not in _ENGINES
                or self.substitution_provenance not in {None, _SUBSTITUTION}
                or type(self.attempts) is not tuple
                or any(type(item) is not BrowserAttempt for item in self.attempts)
                or type(self.lifecycle) is not tuple
                or any(type(item) is not BrowserLifecycleEvidence for item in self.lifecycle)
                or self.requested_engine not in self.configured_engines
                or self.actual_engine not in self.configured_engines
                or type(self.missing_case_ids) is not tuple
                or any(type(item) is not str for item in self.missing_case_ids)
                or len(self.missing_case_ids) != len(set(self.missing_case_ids))):
            raise ValueError("invalid browser recovery receipt")
        if (not self.attempts or len(self.attempts) > 3
                or any(item.case_id != self.case_id for item in self.attempts + self.lifecycle)
                or any(_safe_case_id(item) != item for item in self.missing_case_ids)):
            raise ValueError("browser receipt case mismatch")
        self._validate_history()
        _register_origin(
            self, "BrowserRecoveryReceipt", self._origin_primitives(),
        )

    def _origin_primitives(self):
        return (
            self.schema_version, self.status, self.reason_code, self.case_id,
            self.requested_engine, self.actual_engine, self.substitution_provenance,
            tuple(item._origin_primitives() for item in self.attempts),
            tuple(item._origin_primitives() for item in self.lifecycle),
            self.missing_case_ids, self.verification_profile_id,
            self.configured_engines, self.target_url_digest,
            self.target_route_digest, self.viewport, self.target_origin_digest,
        )

    def _validate_history(self):
        attempts = self.attempts
        for number, item in enumerate(attempts, 1):
            if (item.attempt_number != number
                    or item.requested_engine != self.requested_engine
                    or item.verification_profile_id != self.verification_profile_id
                    or item.configured_engines != self.configured_engines
                    or item.target_url_digest != self.target_url_digest
                    or item.target_origin_digest != self.target_origin_digest
                    or item.target_route_digest != self.target_route_digest
                    or item.viewport != self.viewport
                    or (number == 1 and item.actual_engine != self.requested_engine)):
                raise ValueError("browser attempt history mismatch")
        passed = tuple(item for item in attempts if item.result == "passed")
        if self.status == "clean":
            if not (len(attempts) == 1 and passed == attempts
                    and self.reason_code == "browser_verified_first_pass"
                    and self.actual_engine == self.requested_engine
                    and self.substitution_provenance is None
                    and not self.lifecycle and not self.missing_case_ids):
                raise ValueError("inconsistent browser recovery receipt")
            return

        if attempts[0].result == "passed" or not self.lifecycle:
            raise ValueError("browser recovery lacks initial failed attempt")
        first_session = attempts[0].session_id
        for item in self.lifecycle:
            if (item.requested_engine != self.requested_engine
                    or item.actual_engine not in self.configured_engines):
                raise ValueError("browser lifecycle profile mismatch")

        lifecycle_index = 0
        attempt_index = 1
        initial = self.lifecycle[lifecycle_index]
        lifecycle_index += 1
        if (initial.action not in {"browser_process_quit", "application_restart"}
                or initial.actual_engine != self.requested_engine
                or initial.session_id != first_session
                or initial.previous_session_id != first_session):
            raise ValueError("browser quit session mismatch")

        primary_retry = None
        primary_restart_proved = (
            initial.action == "browser_process_quit" and initial.result == "confirmed"
        )
        if primary_restart_proved:
            if lifecycle_index >= len(self.lifecycle):
                raise ValueError("browser receipt omits primary launch evidence")
            launch = self.lifecycle[lifecycle_index]
            lifecycle_index += 1
            if (launch.actual_engine != self.requested_engine
                    or launch.action not in {"browser_process_launch", "session_validation"}
                    or launch.previous_session_id != first_session):
                raise ValueError("browser primary launch order mismatch")
            if launch.result == "launched":
                if (launch.action != "browser_process_launch"
                        or launch.session_id == first_session
                        or attempt_index >= len(attempts)):
                    raise ValueError("browser primary launch session mismatch")
                primary_retry = attempts[attempt_index]
                attempt_index += 1
                if (primary_retry.actual_engine != self.requested_engine
                        or primary_retry.session_id != launch.session_id):
                    raise ValueError("browser primary retry session mismatch")
            else:
                primary_restart_proved = False

        if not primary_restart_proved:
            if lifecycle_index >= len(self.lifecycle):
                raise ValueError("browser receipt omits unavailable primary restart")
            gap = self.lifecycle[lifecycle_index]
            lifecycle_index += 1
            if (gap.actual_engine != self.requested_engine
                    or gap.action != "primary_restart"
                    or gap.result != "primary_restart_unavailable"
                    or gap.session_id != first_session
                    or gap.previous_session_id != first_session):
                raise ValueError("browser primary restart gap mismatch")

        if primary_retry is not None and primary_retry.result == "passed":
            valid = (
                lifecycle_index == len(self.lifecycle)
                and attempt_index == len(attempts)
                and passed == (primary_retry,)
                and self.status == "recovered"
                and self.reason_code == "primary_recovered_degraded"
                and self.actual_engine == self.requested_engine
                and self.substitution_provenance is None
                and not self.missing_case_ids
            )
            if not valid:
                raise ValueError("inconsistent browser primary recovery receipt")
            return

        alternate_attempt = None
        if len(self.configured_engines) == 1:
            if lifecycle_index >= len(self.lifecycle):
                raise ValueError("browser receipt omits unavailable secondary")
            secondary = self.lifecycle[lifecycle_index]
            lifecycle_index += 1
            if (secondary.actual_engine != self.requested_engine
                    or secondary.action != "secondary_engine"
                    or secondary.result != "secondary_engine_unavailable"
                    or secondary.session_id != first_session
                    or secondary.previous_session_id != first_session):
                raise ValueError("browser unavailable secondary mismatch")
        else:
            if lifecycle_index >= len(self.lifecycle):
                raise ValueError("browser receipt omits alternate engine evidence")
            alternate = self.lifecycle[lifecycle_index]
            lifecycle_index += 1
            prior_sessions = {
                item.session_id for item in attempts[:attempt_index]
            }
            prior_sessions.update(
                item.session_id for item in self.lifecycle[:lifecycle_index - 1]
                if item.action in {"browser_process_launch", "session_validation"}
            )
            if (alternate.actual_engine == self.requested_engine
                    or alternate.action not in {"browser_process_launch", "session_validation"}
                    or alternate.previous_session_id != first_session
                    or alternate.result == "launched"
                    and alternate.session_id in prior_sessions):
                raise ValueError("browser alternate launch order mismatch")
            if alternate.result == "launched":
                if (alternate.action != "browser_process_launch"
                        or alternate.session_id == first_session
                        or attempt_index >= len(attempts)):
                    raise ValueError("browser alternate launch session mismatch")
                alternate_attempt = attempts[attempt_index]
                attempt_index += 1
                if (alternate_attempt.actual_engine != alternate.actual_engine
                        or alternate_attempt.session_id != alternate.session_id):
                    raise ValueError("browser alternate attempt session mismatch")

        if lifecycle_index != len(self.lifecycle) or attempt_index != len(attempts):
            raise ValueError("browser recovery contains out-of-order evidence")
        if alternate_attempt is not None and alternate_attempt.result == "passed":
            valid = (
                passed == (alternate_attempt,)
                and self.status == "recovered"
                and self.reason_code == "alternate_engine_recovered_degraded"
                and self.actual_engine == alternate_attempt.actual_engine
                and self.substitution_provenance == _SUBSTITUTION
                and not self.missing_case_ids
            )
            if not valid:
                raise ValueError("inconsistent browser alternate recovery receipt")
            return

        if not (not passed and self.status == "blocked"
                and self.reason_code == "human_help_required"
                and self.actual_engine == attempts[-1].actual_engine
                and self.substitution_provenance is None
                and self.missing_case_ids == (self.case_id,)):
            raise ValueError("inconsistent browser recovery receipt")

    def to_dict(self):
        return {
            "schema_version": self.schema_version, "status": self.status,
            "reason_code": self.reason_code, "case_id": self.case_id,
            "requested_engine": self.requested_engine, "actual_engine": self.actual_engine,
            "substitution_provenance": self.substitution_provenance,
            "attempts": [item.to_dict() for item in self.attempts],
            "lifecycle": [item.to_dict() for item in self.lifecycle],
            "missing_case_ids": list(self.missing_case_ids),
            "verification_profile_id": self.verification_profile_id,
            "configured_engines": list(self.configured_engines),
            "target_url_digest": self.target_url_digest,
            "target_origin_digest": self.target_origin_digest,
            "target_route_digest": self.target_route_digest,
            "viewport": self.viewport,
        }


def snapshot_browser_recovery_receipt(value):
    if type(value) is not BrowserRecoveryReceipt:
        raise ValueError("invalid browser recovery receipt")
    try:
        captured = _field_values(value, BrowserRecoveryReceipt)
        _validate_capture(
            value, "BrowserRecoveryReceipt", captured, value._origin_primitives(),
        )
        attempts = tuple(snapshot_browser_attempt(item) for item in captured[7])
        lifecycle = tuple(snapshot_browser_lifecycle(item) for item in captured[8])
        captured = captured[:7] + (attempts, lifecycle) + captured[9:]
        return BrowserRecoveryReceipt(*captured)
    except Exception:
        raise ValueError("invalid browser recovery receipt") from None


class BrowserAdapter(Protocol):
    def attempt(self, request: BrowserRequest, engine: str) -> BrowserAttempt: ...
    def quit_engine(self, engine: str) -> BrowserQuitEvidence: ...
    def launch_engine(self, engine: str, fresh_profile: bool = True) -> BrowserLaunchEvidence: ...


class BrowserRecovery:
    @staticmethod
    def _unavailable_attempt(request, engine, number, reason, detail=None):
        return BrowserAttempt(
            request.case_id, number, request.primary_engine, engine, "verify", "unavailable",
            reason, detail, None, None, None, f"unavailable-{number}-{engine}", "browser",
            _SUBSTITUTION if engine != request.primary_engine else None,
            request.verification_profile_id, request.configured_engines,
            request.target_url_digest, request.target_origin_digest,
            request.target_route_digest, request.viewport,
        )

    def _attempt(self, request, adapter, engine, number):
        try:
            item = adapter.attempt(request, engine)
        except Exception as error:
            return self._unavailable_attempt(
                request, engine, number, "adapter_exception", _sealed_exception_detail(error),
            )
        if type(item) is BrowserAttempt:
            try:
                item = snapshot_browser_attempt(item)
            except Exception:
                return self._unavailable_attempt(
                    request, engine, number, "invalid_adapter_evidence",
                    "adapter attempt failed canonical validation",
                )
        expected_substitution = _SUBSTITUTION if engine != request.primary_engine else None
        if (type(item) is not BrowserAttempt or item.case_id != request.case_id
                or item.attempt_number != number or item.requested_engine != request.primary_engine
                or item.actual_engine != engine
                or item.verification_profile_id != request.verification_profile_id
                or item.configured_engines != request.configured_engines
                or item.target_url_digest != request.target_url_digest
                or item.target_origin_digest != request.target_origin_digest
                or item.target_route_digest != request.target_route_digest
                or item.viewport != request.viewport
                or item.substitution_provenance not in {None, expected_substitution}):
            return self._unavailable_attempt(
                request, engine, number, "invalid_adapter_evidence",
                "adapter attempt identity mismatch",
            )
        if item.substitution_provenance != expected_substitution:
            return self._unavailable_attempt(
                request, engine, number, "invalid_adapter_evidence",
                "adapter substitution mismatch",
            )
        if item.result == "passed" and item.proof_kind != "browser":
            return replace(
                item, result="failed", reason_code="curl_not_browser_evidence",
                failure_detail=None,
            )
        return item

    @staticmethod
    def _lifecycle(
        request, engine, action, result, session_id, *, previous=None, reason=None,
        detail=None, fresh_profile=None,
    ):
        return BrowserLifecycleEvidence(
            request.case_id, request.primary_engine, engine, action, result, session_id,
            previous, reason, detail,
            _SUBSTITUTION if engine != request.primary_engine else None,
            fresh_profile,
        )

    def _quit(self, request, adapter, initial):
        try:
            item = adapter.quit_engine(request.primary_engine)
        except Exception as error:
            return None, self._lifecycle(
                request, request.primary_engine, "browser_process_quit", "unavailable",
                initial.session_id, previous=initial.session_id,
                reason="adapter_exception", detail=_sealed_exception_detail(error),
            )
        if type(item) is BrowserQuitEvidence:
            try:
                item = BrowserQuitEvidence(**{
                    name: getattr(item, name) for name in item.__dataclass_fields__
                })
            except Exception:
                item = None
        if (type(item) is not BrowserQuitEvidence or item.engine != request.primary_engine
                or item.session_id != initial.session_id):
            return None, self._lifecycle(
                request, request.primary_engine, "browser_process_quit", "unavailable",
                initial.session_id, previous=initial.session_id,
                reason="invalid_adapter_evidence",
                detail="adapter quit identity mismatch",
            )
        return item, self._lifecycle(
            request, item.engine, item.action,
            "confirmed" if item.confirmed else "unconfirmed", item.session_id,
            previous=initial.session_id,
            reason=None if item.confirmed else "browser_unavailable",
        )

    def _launch(self, request, adapter, engine, previous, forbidden_sessions):
        try:
            item = adapter.launch_engine(engine, True)
        except Exception as error:
            return None, self._lifecycle(
                request, engine, "browser_process_launch", "unavailable",
                f"unavailable-launch-{engine}", previous=previous,
                reason="adapter_exception", detail=_sealed_exception_detail(error),
            )
        if type(item) is BrowserLaunchEvidence:
            try:
                item = BrowserLaunchEvidence(**{
                    name: getattr(item, name) for name in item.__dataclass_fields__
                })
            except Exception:
                item = None
        if type(item) is not BrowserLaunchEvidence or item.engine != engine:
            return None, self._lifecycle(
                request, engine, "browser_process_launch", "unavailable",
                f"unavailable-launch-{engine}", previous=previous,
                reason="invalid_adapter_evidence", detail="adapter launch identity mismatch",
            )
        if not item.launched:
            return None, self._lifecycle(
                request, item.engine, item.action, "unavailable", item.session_id,
                previous=previous, reason="browser_unavailable",
            )
        if not item.fresh_profile:
            return None, self._lifecycle(
                request, item.engine, item.action, "fresh_profile_unavailable",
                item.session_id, previous=previous,
                reason="fresh_profile_unavailable", fresh_profile=False,
            )
        if item.session_id in forbidden_sessions:
            return None, self._lifecycle(
                request, item.engine, "session_validation", "session_identity_mismatch",
                item.session_id, previous=previous, reason="session_identity_mismatch",
            )
        return item, self._lifecycle(
            request, item.engine, item.action, "launched", item.session_id,
            previous=previous, fresh_profile=True,
        )

    @staticmethod
    def _bind_attempt_session(item, session_id):
        if item.session_id == session_id:
            return item
        return replace(
            item, result="failed", reason_code="session_identity_mismatch",
            failure_detail=None, session_id=session_id,
        )

    @staticmethod
    def _receipt(request, status, reason, attempts, lifecycle, missing=()):
        successful = next((item for item in reversed(attempts) if item.result == "passed"), None)
        actual = successful.actual_engine if successful is not None else attempts[-1].actual_engine
        substitution = successful.substitution_provenance if successful is not None else None
        return BrowserRecoveryReceipt(
            1, status, reason, request.case_id, request.primary_engine, actual, substitution,
            tuple(attempts), tuple(lifecycle), tuple(missing),
            request.verification_profile_id, request.configured_engines,
            request.target_url_digest, request.target_route_digest, request.viewport,
            request.target_origin_digest,
        )

    def run(self, request, adapter):
        request = snapshot_browser_request(request)
        attempts, lifecycle = [], []
        initial = self._attempt(request, adapter, request.primary_engine, 1)
        attempts.append(initial)
        if initial.result == "passed":
            return self._receipt(request, "clean", "browser_verified_first_pass", attempts, lifecycle)

        quit_item, quit_lifecycle = self._quit(request, adapter, initial)
        lifecycle.append(quit_lifecycle)
        restart_proved = (
            quit_item is not None and quit_item.engine == request.primary_engine
            and quit_item.action == "browser_process_quit" and quit_item.confirmed
            and quit_item.session_id == initial.session_id
        )
        primary_launch = None
        if restart_proved:
            primary_launch, launch_lifecycle = self._launch(
                request, adapter, request.primary_engine, initial.session_id,
                {initial.session_id},
            )
            lifecycle.append(launch_lifecycle)
            restart_proved = (
                primary_launch is not None
            )
        if restart_proved:
            retry = self._attempt(
                request, adapter, request.primary_engine, len(attempts) + 1,
            )
            retry = self._bind_attempt_session(retry, primary_launch.session_id)
            attempts.append(retry)
            if retry.result == "passed":
                return self._receipt(
                    request, "recovered", "primary_recovered_degraded", attempts, lifecycle,
                )
        else:
            lifecycle.append(self._lifecycle(
                request, request.primary_engine, "primary_restart",
                "primary_restart_unavailable", initial.session_id,
                previous=initial.session_id,
            ))

        previous_sessions = {item.session_id for item in attempts}
        previous_sessions.update(
            item.session_id for item in lifecycle
            if item.action in {"browser_process_launch", "session_validation"}
        )
        if request.secondary_engine is None:
            lifecycle.append(self._lifecycle(
                request, request.primary_engine, "secondary_engine",
                "secondary_engine_unavailable", initial.session_id,
                previous=initial.session_id, reason="secondary_engine_unavailable",
            ))
            return self._receipt(
                request, "blocked", "human_help_required", attempts, lifecycle,
                (request.case_id,),
            )
        secondary_launch, launch_lifecycle = self._launch(
            request, adapter, request.secondary_engine, initial.session_id,
            previous_sessions,
        )
        lifecycle.append(launch_lifecycle)
        secondary_proved = (
            secondary_launch is not None
        )
        if secondary_proved:
            secondary = self._attempt(
                request, adapter, request.secondary_engine, len(attempts) + 1,
            )
            secondary = self._bind_attempt_session(secondary, secondary_launch.session_id)
            attempts.append(secondary)
            if secondary.result == "passed":
                return self._receipt(
                    request, "recovered", "alternate_engine_recovered_degraded",
                    attempts, lifecycle,
                )
        return self._receipt(
            request, "blocked", "human_help_required", attempts, lifecycle,
            (request.case_id,),
        )
