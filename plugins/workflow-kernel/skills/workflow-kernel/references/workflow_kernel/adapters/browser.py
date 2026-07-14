"""Deterministic, case-bound browser recovery using injected host adapters."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
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

    @property
    def engine(self):
        """Compatibility alias for the engine that produced this attempt."""
        return self.actual_engine

    @property
    def failure_reason(self):
        """Compatibility alias retaining only the stable reason code."""
        return self.reason_code

    def to_dict(self):
        payload = {name: getattr(self, name) for name in self.__dataclass_fields__}
        payload["configured_engines"] = list(self.configured_engines)
        return payload


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

    def to_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


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
            attempts = tuple(
                BrowserAttempt(**{
                    name: getattr(item, name) for name in item.__dataclass_fields__
                })
                for item in self.attempts if type(item) is BrowserAttempt
            )
            lifecycle = tuple(
                BrowserLifecycleEvidence(**{
                    name: getattr(item, name) for name in item.__dataclass_fields__
                })
                for item in self.lifecycle if type(item) is BrowserLifecycleEvidence
            )
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
        first_session = attempts[0].session_id
        if self.status != "clean" and (
                not self.lifecycle
                or self.lifecycle[0].action not in {"browser_process_quit", "application_restart"}):
            raise ValueError("browser recovery lacks initial quit evidence")
        launched = {}
        primary_quit_confirmed = False
        secondary_started = False
        for index, item in enumerate(self.lifecycle):
            if (item.requested_engine != self.requested_engine
                    or item.actual_engine not in self.configured_engines):
                raise ValueError("browser lifecycle profile mismatch")
            if index and item.action in {"browser_process_quit", "application_restart"}:
                raise ValueError("browser quit must be the first lifecycle action")
            is_secondary = (
                item.actual_engine != self.requested_engine
                or item.action == "secondary_engine"
            )
            if is_secondary:
                secondary_started = True
            elif secondary_started:
                raise ValueError("primary lifecycle action follows secondary recovery")
            if item.action in {"browser_process_quit", "application_restart"} and (
                    item.actual_engine != self.requested_engine
                    or item.session_id != first_session or item.previous_session_id != first_session):
                raise ValueError("browser quit session mismatch")
            if item.action == "browser_process_quit" and item.result == "confirmed":
                primary_quit_confirmed = True
            if item.action == "browser_process_launch" and item.result == "launched":
                if (item.previous_session_id != first_session
                        or item.session_id == item.previous_session_id
                        or item.session_id in launched or item.session_id == first_session):
                    raise ValueError("browser launch session mismatch")
                launched[item.session_id] = item.actual_engine
        attempted_launches = {
            item.session_id: item.actual_engine for item in attempts[1:]
        }
        if launched != attempted_launches:
            raise ValueError("browser launch lacks exactly one bound attempt")
        for item in attempts[1:]:
            if (launched.get(item.session_id) != item.actual_engine
                    and item.reason_code != "session_identity_mismatch"):
                raise ValueError("browser attempt lacks launch session")
            if item.actual_engine == self.requested_engine and not primary_quit_confirmed:
                raise ValueError("primary retry lacks confirmed quit")
        passed = tuple(item for item in attempts if item.result == "passed")
        primary_retry_attempted = any(
            item.actual_engine == self.requested_engine for item in attempts[1:]
        )
        restart_unavailable_recorded = any(
            item.action == "primary_restart"
            and item.result == "primary_restart_unavailable"
            for item in self.lifecycle
        )
        if (self.status != "clean" and not primary_retry_attempted
                and not restart_unavailable_recorded):
            raise ValueError("browser receipt omits unavailable primary restart")
        if self.status == "blocked" and len(self.configured_engines) > 1:
            alternate_attempted = any(
                item.actual_engine != self.requested_engine for item in attempts[1:]
            )
            alternate_unavailable_recorded = any(
                item.actual_engine != self.requested_engine
                and item.action in {"browser_process_launch", "session_validation"}
                and item.result != "launched"
                for item in self.lifecycle
            )
            if not alternate_attempted and not alternate_unavailable_recorded:
                raise ValueError("browser receipt omits alternate engine evidence")
        status_reason = {
            "clean": "browser_verified_first_pass",
            "blocked": "human_help_required",
        }
        if self.status in status_reason and self.reason_code != status_reason[self.status]:
            raise ValueError("browser receipt status mismatch")
        if self.status == "clean":
            valid = (len(attempts) == 1 and passed == attempts
                     and self.actual_engine == self.requested_engine
                     and self.substitution_provenance is None and not self.lifecycle
                     and not self.missing_case_ids)
        elif self.status == "recovered":
            expected_reason = (
                "primary_recovered_degraded" if self.actual_engine == self.requested_engine
                else "alternate_engine_recovered_degraded"
            )
            history_valid = (
                len(attempts) == 2 and attempts[-1].actual_engine == self.requested_engine
                if self.actual_engine == self.requested_engine else
                len(attempts) in {2, 3}
                and attempts[-1].actual_engine != self.requested_engine
                and all(item.actual_engine == self.requested_engine for item in attempts[:-1])
            )
            valid = (history_valid and passed == (attempts[-1],)
                     and self.reason_code == expected_reason
                     and self.actual_engine == attempts[-1].actual_engine
                     and self.substitution_provenance == attempts[-1].substitution_provenance
                     and not self.missing_case_ids)
        else:
            history_valid = (
                len(attempts) == 1
                or len(attempts) == 2
                or len(attempts) == 3
                and attempts[1].actual_engine == self.requested_engine
                and attempts[2].actual_engine != self.requested_engine
            )
            valid = (history_valid and not passed
                     and all(item.actual_engine == self.requested_engine
                             for item in attempts[:-1])
                     and self.actual_engine == attempts[-1].actual_engine
                     and self.substitution_provenance is None
                     and self.missing_case_ids == (self.case_id,))
            if len(self.configured_engines) == 1:
                valid = valid and any(
                    item.action == "secondary_engine"
                    and item.result == "secondary_engine_unavailable"
                    for item in self.lifecycle
                )
        if not valid:
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
        payload = {
            name: getattr(value, name) for name in value.__dataclass_fields__
        }
        attempts = []
        for item in payload["attempts"]:
            if type(item) is not BrowserAttempt:
                raise ValueError
            attempts.append(BrowserAttempt(**{
                name: getattr(item, name) for name in item.__dataclass_fields__
            }))
        lifecycle = []
        for item in payload["lifecycle"]:
            if type(item) is not BrowserLifecycleEvidence:
                raise ValueError
            lifecycle.append(BrowserLifecycleEvidence(**{
                name: getattr(item, name) for name in item.__dataclass_fields__
            }))
        payload["attempts"] = tuple(attempts)
        payload["lifecycle"] = tuple(lifecycle)
        return BrowserRecoveryReceipt(**payload)
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
                item = BrowserAttempt(**{
                    name: getattr(item, name) for name in item.__dataclass_fields__
                })
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

        previous_sessions = {initial.session_id}
        if primary_launch is not None:
            previous_sessions.add(primary_launch.session_id)
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
