"""Deterministic browser recovery using injected host adapters."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Protocol, Tuple
from ..redaction import normalize_evidence_reference
from ..verification import validate_viewport

_ENGINES = frozenset({"chromium", "firefox", "webkit"})


@dataclass(frozen=True)
class BrowserRequest:
    case_id: str; url: str; viewport: str; primary_engine: str; secondary_engine: str
    def __post_init__(self):
        if type(self.case_id) is not str or not self.case_id or type(self.url) is not str or not self.url:
            raise ValueError("invalid browser request")
        validate_viewport(self.viewport)
        if self.primary_engine not in _ENGINES or self.secondary_engine not in _ENGINES or self.primary_engine == self.secondary_engine:
            raise ValueError("browser engines must be genuinely different")


@dataclass(frozen=True)
class BrowserAttempt:
    attempt_number: int; engine: str; action: str; result: str
    failure_reason: Optional[str]; screenshot_reference: Optional[str]
    trace_reference: Optional[str]; console_reference: Optional[str]
    session_id: str; proof_kind: str = "browser"
    def __post_init__(self):
        if (type(self.attempt_number) is not int or self.attempt_number < 1 or self.engine not in _ENGINES
                or self.action != "verify" or self.result not in {"passed", "failed", "unavailable"}
                or type(self.session_id) is not str or not self.session_id or self.proof_kind not in {"browser", "curl", "reachability"}):
            raise ValueError("invalid browser attempt")
        if (self.result == "passed") != (self.failure_reason is None):
            raise ValueError("inconsistent browser attempt")
        for name in ("screenshot_reference", "trace_reference", "console_reference"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, normalize_evidence_reference(value))
    def to_dict(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class BrowserQuitEvidence:
    engine: str; confirmed: bool; session_id: str; action: str = "browser_process_quit"


@dataclass(frozen=True)
class BrowserLaunchEvidence:
    engine: str; launched: bool; fresh_profile: bool; session_id: str
    action: str = "browser_process_launch"


@dataclass(frozen=True)
class BrowserLifecycleEvidence:
    engine: str; action: str; result: str; session_id: str
    def to_dict(self):
        return {"engine": self.engine, "action": self.action, "result": self.result, "session_id": self.session_id}


@dataclass(frozen=True)
class BrowserRecoveryReceipt:
    schema_version: int; status: str; reason_code: str
    attempts: Tuple[BrowserAttempt, ...]; lifecycle: Tuple[BrowserLifecycleEvidence, ...]
    missing_case_ids: Tuple[str, ...]
    def to_dict(self):
        return {"schema_version": self.schema_version, "status": self.status, "reason_code": self.reason_code,
                "attempts": [item.to_dict() for item in self.attempts],
                "lifecycle": [item.to_dict() for item in self.lifecycle],
                "missing_case_ids": list(self.missing_case_ids)}


class BrowserAdapter(Protocol):
    def attempt(self, request: BrowserRequest, engine: str) -> BrowserAttempt: ...
    def quit_engine(self, engine: str) -> BrowserQuitEvidence: ...
    def launch_engine(self, engine: str, fresh_profile: bool = True) -> BrowserLaunchEvidence: ...


class BrowserRecovery:
    @staticmethod
    def _attempt(request, adapter, engine):
        item = adapter.attempt(request, engine)
        if type(item) is not BrowserAttempt or item.engine != engine:
            raise ValueError("invalid adapter attempt")
        if item.result == "passed" and item.proof_kind != "browser":
            return replace(item, result="failed", failure_reason="curl_not_browser_evidence")
        return item
    @staticmethod
    def _receipt(status, reason, attempts, lifecycle, missing=()):
        return BrowserRecoveryReceipt(1, status, reason, tuple(attempts), tuple(lifecycle), tuple(missing))
    def run(self, request, adapter):
        attempts, lifecycle = [], []
        initial = self._attempt(request, adapter, request.primary_engine); attempts.append(initial)
        if initial.result == "passed":
            return self._receipt("clean", "browser_verified_first_pass", attempts, lifecycle)
        quit_item = adapter.quit_engine(request.primary_engine)
        lifecycle.append(BrowserLifecycleEvidence(quit_item.engine, quit_item.action,
                         "confirmed" if quit_item.confirmed else "unconfirmed", quit_item.session_id))
        restarted = quit_item.engine == request.primary_engine and quit_item.action == "browser_process_quit" and quit_item.confirmed
        if restarted:
            launch = adapter.launch_engine(request.primary_engine, True)
            lifecycle.append(BrowserLifecycleEvidence(launch.engine, launch.action,
                             "launched" if launch.launched else "unavailable", launch.session_id))
            restarted = launch.engine == request.primary_engine and launch.launched and launch.fresh_profile and launch.session_id != initial.session_id
        if restarted:
            retry = self._attempt(request, adapter, request.primary_engine); attempts.append(retry)
            if retry.result == "passed":
                return self._receipt("recovered", "primary_recovered_degraded", attempts, lifecycle)
        else:
            lifecycle.append(BrowserLifecycleEvidence(request.primary_engine, "primary_restart", "primary_restart_unavailable", initial.session_id))
        secondary_launch = adapter.launch_engine(request.secondary_engine, True)
        lifecycle.append(BrowserLifecycleEvidence(secondary_launch.engine, secondary_launch.action,
                         "launched" if secondary_launch.launched else "unavailable", secondary_launch.session_id))
        if secondary_launch.engine == request.secondary_engine and secondary_launch.launched and secondary_launch.fresh_profile:
            secondary = self._attempt(request, adapter, request.secondary_engine); attempts.append(secondary)
            if secondary.result == "passed":
                return self._receipt("recovered", "alternate_engine_recovered_degraded", attempts, lifecycle)
        return self._receipt("blocked", "human_help_required", attempts, lifecycle, (request.case_id,))
