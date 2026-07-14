"""Deterministic, case-bound browser recovery using injected host adapters."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Optional, Protocol, Tuple

from ..redaction import digest_error_detail_string, normalize_evidence_reference
from ..verification import validate_viewport

_ENGINES = frozenset({"chromium", "firefox", "webkit"})
_RESULTS = frozenset({"passed", "failed", "unavailable"})
_REASON_CODES = frozenset({
    "adapter_exception", "invalid_adapter_evidence", "browser_tool_failure",
    "browser_unavailable", "curl_not_browser_evidence", "session_identity_mismatch",
})
_SESSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
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


@dataclass(frozen=True)
class BrowserRequest:
    case_id: str; url: str; viewport: str; primary_engine: str; secondary_engine: str

    def __post_init__(self):
        _safe_case_id(self.case_id)
        if type(self.url) is not str or not self.url:
            raise ValueError("invalid browser request")
        validate_viewport(self.viewport)
        if (self.primary_engine not in _ENGINES or self.secondary_engine not in _ENGINES
                or self.primary_engine == self.secondary_engine):
            raise ValueError("browser engines must be genuinely different")


@dataclass(frozen=True)
class BrowserAttempt:
    case_id: str; attempt_number: int; requested_engine: str; actual_engine: str
    action: str; result: str; reason_code: Optional[str]; failure_detail: Optional[str]
    screenshot_reference: Optional[str]; trace_reference: Optional[str]
    console_reference: Optional[str]; session_id: str; proof_kind: str = "browser"
    substitution_provenance: Optional[str] = None

    def __post_init__(self):
        _safe_case_id(self.case_id); _safe_session_id(self.session_id)
        if (type(self.attempt_number) is not int or self.attempt_number < 1
                or self.requested_engine not in _ENGINES or self.actual_engine not in _ENGINES
                or self.action != "verify" or self.result not in _RESULTS
                or self.proof_kind not in {"browser", "curl", "reachability"}):
            raise ValueError("invalid browser attempt")
        if self.substitution_provenance not in {None, _SUBSTITUTION}:
            raise ValueError("invalid browser substitution")
        if self.actual_engine == self.requested_engine and self.substitution_provenance is not None:
            raise ValueError("invalid browser substitution")
        if self.result == "passed":
            if self.reason_code is not None or self.failure_detail is not None:
                raise ValueError("inconsistent browser attempt")
        elif self.reason_code not in _REASON_CODES:
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
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


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

    def __post_init__(self):
        _safe_case_id(self.case_id); _safe_session_id(self.session_id)
        if self.previous_session_id is not None:
            _safe_session_id(self.previous_session_id)
        if (self.requested_engine not in _ENGINES or self.actual_engine not in _ENGINES
                or self.action not in {
                    "browser_process_quit", "browser_process_launch", "application_restart",
                    "primary_restart", "session_validation",
                }
                or self.result not in {
                    "confirmed", "unconfirmed", "launched", "unavailable",
                    "primary_restart_unavailable", "session_identity_mismatch",
                }
                or self.substitution_provenance not in {None, _SUBSTITUTION}):
            raise ValueError("invalid browser lifecycle evidence")
        if self.reason_code is not None and self.reason_code not in _REASON_CODES:
            raise ValueError("invalid browser lifecycle reason")
        object.__setattr__(self, "failure_detail", _safe_detail(self.failure_detail))

    def to_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class BrowserRecoveryReceipt:
    schema_version: int; status: str; reason_code: str; case_id: str
    requested_engine: str; actual_engine: str; substitution_provenance: Optional[str]
    attempts: Tuple[BrowserAttempt, ...]; lifecycle: Tuple[BrowserLifecycleEvidence, ...]
    missing_case_ids: Tuple[str, ...]

    def __post_init__(self):
        _safe_case_id(self.case_id)
        if (self.schema_version != 1 or self.status not in {"clean", "recovered", "blocked"}
                or self.reason_code not in _RECEIPT_REASONS
                or self.requested_engine not in _ENGINES or self.actual_engine not in _ENGINES
                or self.substitution_provenance not in {None, _SUBSTITUTION}
                or type(self.attempts) is not tuple
                or any(type(item) is not BrowserAttempt for item in self.attempts)
                or type(self.lifecycle) is not tuple
                or any(type(item) is not BrowserLifecycleEvidence for item in self.lifecycle)
                or type(self.missing_case_ids) is not tuple):
            raise ValueError("invalid browser recovery receipt")
        if any(item.case_id != self.case_id for item in self.attempts + self.lifecycle):
            raise ValueError("browser receipt case mismatch")

    def to_dict(self):
        return {
            "schema_version": self.schema_version, "status": self.status,
            "reason_code": self.reason_code, "case_id": self.case_id,
            "requested_engine": self.requested_engine, "actual_engine": self.actual_engine,
            "substitution_provenance": self.substitution_provenance,
            "attempts": [item.to_dict() for item in self.attempts],
            "lifecycle": [item.to_dict() for item in self.lifecycle],
            "missing_case_ids": list(self.missing_case_ids),
        }


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
        )

    def _attempt(self, request, adapter, engine, number):
        try:
            item = adapter.attempt(request, engine)
        except Exception as error:
            return self._unavailable_attempt(
                request, engine, number, "adapter_exception", str(error),
            )
        expected_substitution = _SUBSTITUTION if engine != request.primary_engine else None
        if (type(item) is not BrowserAttempt or item.case_id != request.case_id
                or item.attempt_number != number or item.requested_engine != request.primary_engine
                or item.actual_engine != engine
                or item.substitution_provenance not in {None, expected_substitution}):
            return self._unavailable_attempt(
                request, engine, number, "invalid_adapter_evidence",
                "adapter attempt identity mismatch",
            )
        if item.substitution_provenance != expected_substitution:
            item = replace(item, substitution_provenance=expected_substitution)
        if item.result == "passed" and item.proof_kind != "browser":
            return replace(
                item, result="failed", reason_code="curl_not_browser_evidence",
                failure_detail=None,
            )
        return item

    @staticmethod
    def _lifecycle(
        request, engine, action, result, session_id, *, previous=None, reason=None,
        detail=None,
    ):
        return BrowserLifecycleEvidence(
            request.case_id, request.primary_engine, engine, action, result, session_id,
            previous, reason, detail,
            _SUBSTITUTION if engine != request.primary_engine else None,
        )

    def _quit(self, request, adapter, initial):
        try:
            item = adapter.quit_engine(request.primary_engine)
        except Exception as error:
            return None, self._lifecycle(
                request, request.primary_engine, "browser_process_quit", "unavailable",
                initial.session_id, reason="adapter_exception", detail=str(error),
            )
        if type(item) is not BrowserQuitEvidence or item.engine != request.primary_engine:
            return None, self._lifecycle(
                request, request.primary_engine, "browser_process_quit", "unavailable",
                initial.session_id, reason="invalid_adapter_evidence",
                detail="adapter quit identity mismatch",
            )
        return item, self._lifecycle(
            request, item.engine, item.action,
            "confirmed" if item.confirmed else "unconfirmed", item.session_id,
            previous=initial.session_id,
        )

    def _launch(self, request, adapter, engine, previous):
        try:
            item = adapter.launch_engine(engine, True)
        except Exception as error:
            return None, self._lifecycle(
                request, engine, "browser_process_launch", "unavailable",
                f"unavailable-launch-{engine}", previous=previous,
                reason="adapter_exception", detail=str(error),
            )
        if type(item) is not BrowserLaunchEvidence or item.engine != engine:
            return None, self._lifecycle(
                request, engine, "browser_process_launch", "unavailable",
                f"unavailable-launch-{engine}", previous=previous,
                reason="invalid_adapter_evidence", detail="adapter launch identity mismatch",
            )
        return item, self._lifecycle(
            request, item.engine, item.action,
            "launched" if item.launched else "unavailable", item.session_id,
            previous=previous,
        )

    @staticmethod
    def _bind_attempt_session(item, session_id):
        if item.session_id == session_id:
            return item
        return replace(
            item, result="failed", reason_code="session_identity_mismatch",
            failure_detail=None,
        )

    @staticmethod
    def _receipt(request, status, reason, attempts, lifecycle, missing=()):
        successful = next((item for item in reversed(attempts) if item.result == "passed"), None)
        actual = successful.actual_engine if successful is not None else attempts[-1].actual_engine
        substitution = successful.substitution_provenance if successful is not None else None
        return BrowserRecoveryReceipt(
            1, status, reason, request.case_id, request.primary_engine, actual, substitution,
            tuple(attempts), tuple(lifecycle), tuple(missing),
        )

    def run(self, request, adapter):
        if type(request) is not BrowserRequest:
            raise ValueError("invalid browser request")
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
            )
            lifecycle.append(launch_lifecycle)
            restart_proved = (
                primary_launch is not None and primary_launch.launched
                and primary_launch.fresh_profile
                and primary_launch.session_id != initial.session_id
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
        secondary_launch, launch_lifecycle = self._launch(
            request, adapter, request.secondary_engine, initial.session_id,
        )
        lifecycle.append(launch_lifecycle)
        secondary_proved = (
            secondary_launch is not None and secondary_launch.launched
            and secondary_launch.fresh_profile
            and secondary_launch.session_id not in previous_sessions
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
