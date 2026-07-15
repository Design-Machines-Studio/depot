"""Deterministic, case-bound browser recovery using injected host adapters.

The browser evidence model (requests, attempts, lifecycle, receipts, and their
sealed snapshot functions) is core validation policy and lives in
workflow_kernel.browser_evidence; every name is re-exported here so existing
import sites keep working. This module owns only the I/O-facing pieces: the
BrowserAdapter protocol and the BrowserRecovery escalation ladder.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Protocol

from ..browser_evidence import (  # noqa: F401 -- re-exported evidence model
    BrowserAttempt,
    BrowserLaunchEvidence,
    BrowserLifecycleEvidence,
    BrowserQuitEvidence,
    BrowserReadinessEvidence,
    BrowserRecoveryReceipt,
    BrowserRequest,
    _SUBSTITUTION,
    _field_values,
    _sealed_exception_detail,
    snapshot_browser_attempt,
    snapshot_browser_lifecycle,
    snapshot_browser_readiness,
    snapshot_browser_recovery_receipt,
    snapshot_browser_request,
)

class BrowserAdapter(Protocol):
    def attempt(self, request: BrowserRequest, engine: str) -> BrowserAttempt: ...
    def quit_engine(self, engine: str) -> BrowserQuitEvidence: ...
    def launch_engine(self, engine: str, fresh_profile: bool = True) -> BrowserLaunchEvidence: ...
    def recheck_readiness(
        self, request: BrowserRequest, previous_session_id: str,
    ) -> BrowserReadinessEvidence: ...


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
            request.declared_route_digest,
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
                or item.declared_route_digest != request.declared_route_digest
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
        detail=None, fresh_profile=None, readiness_checks=None,
        readiness_evidence_digest=None,
    ):
        return BrowserLifecycleEvidence(
            request.case_id, request.primary_engine, engine, action, result, session_id,
            previous, reason, detail,
            _SUBSTITUTION if engine != request.primary_engine else None,
            fresh_profile, readiness_checks, readiness_evidence_digest,
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
                item = BrowserQuitEvidence(*_field_values(item, BrowserQuitEvidence))
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
                item = BrowserLaunchEvidence(*_field_values(item, BrowserLaunchEvidence))
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

    def _readiness(self, request, adapter, previous):
        try:
            item = snapshot_browser_readiness(
                adapter.recheck_readiness(request, previous),
            )
        except Exception as error:
            failure_digest = "sha256:" + hashlib.sha256(
                (request.case_id + "\0" + previous + "\0adapter_exception").encode()
            ).hexdigest()
            return self._lifecycle(
                request, request.primary_engine, "readiness_recheck", "unavailable",
                previous, previous=previous, reason="adapter_exception",
                detail=_sealed_exception_detail(error),
                readiness_checks=("unavailable", "unavailable", "unavailable"),
                readiness_evidence_digest=failure_digest,
            )
        if (item.case_id != request.case_id
                or item.session_id != previous
                or item.target_url_digest != request.target_url_digest
                or item.target_origin_digest != request.target_origin_digest):
            failure_digest = "sha256:" + hashlib.sha256(
                (request.case_id + "\0" + previous
                 + "\0invalid_adapter_evidence").encode()
            ).hexdigest()
            return self._lifecycle(
                request, request.primary_engine, "readiness_recheck", "unavailable",
                previous, previous=previous, reason="invalid_adapter_evidence",
                detail="adapter readiness identity mismatch",
                readiness_checks=("unavailable", "unavailable", "unavailable"),
                readiness_evidence_digest=failure_digest,
            )
        ready = all((item.dev_server_ready, item.target_url_ready,
                     item.auth_fixture_ready))
        return self._lifecycle(
            request, request.primary_engine, "readiness_recheck",
            "confirmed" if ready else "unavailable", previous,
            previous=previous, reason=item.reason_code,
            readiness_checks=tuple(
                "confirmed" if value else "unavailable" for value in (
                    item.dev_server_ready, item.target_url_ready,
                    item.auth_fixture_ready,
                )
            ),
            readiness_evidence_digest=item.evidence_digest,
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
            request.declared_route_digest,
        )

    def run(self, request, adapter):
        request = snapshot_browser_request(request)
        attempts, lifecycle = [], []
        initial = self._attempt(request, adapter, request.primary_engine, 1)
        attempts.append(initial)
        if initial.result == "passed":
            return self._receipt(request, "clean", "browser_verified_first_pass", attempts, lifecycle)
        if initial.reason_code == "application_failure":
            return self._receipt(
                request, "blocked", "application_failure", attempts, lifecycle,
                (request.case_id,),
            )

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
            if retry.reason_code == "application_failure":
                return self._receipt(
                    request, "blocked", "application_failure", attempts, lifecycle,
                    (request.case_id,),
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
        current_primary_session = attempts[-1].session_id
        readiness = self._readiness(request, adapter, current_primary_session)
        lifecycle.append(readiness)
        secondary_launch, launch_lifecycle = self._launch(
            request, adapter, request.secondary_engine, current_primary_session,
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
            if secondary.reason_code == "application_failure":
                return self._receipt(
                    request, "blocked", "application_failure", attempts, lifecycle,
                    (request.case_id,),
                )
        return self._receipt(
            request, "blocked", "human_help_required", attempts, lifecycle,
            (request.case_id,),
        )
