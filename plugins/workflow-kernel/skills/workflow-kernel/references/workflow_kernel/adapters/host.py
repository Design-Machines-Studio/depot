"""Declared host capabilities and fake-safe builder session handling."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from .base import (
    BuilderSessionDecision, HostAdapter, HostCapabilities, HostCapability, NodeSpec,
    SessionHandle, SessionResult, ValidationFeedback, invalid_policy,
)


_ROLE_CAPABILITIES = {
    "native": HostCapability.NATIVE_DISPATCH,
    "codex_companion": HostCapability.COMPANION_DISPATCH,
    "wrapper": HostCapability.WRAPPER_DISPATCH,
    "openrouter_exec": HostCapability.OPENROUTER_EXEC,
    "none": None,
}


def _repository_file(relative: str) -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / relative
        if candidate.is_file():
            return candidate
    raise invalid_policy("harness_profile_unavailable")


def capabilities_from_harness_profile(
    host_name: str,
    path: Optional[Path] = None,
) -> HostCapabilities:
    source = Path(path) if path is not None else _repository_file(
        "plugins/pipeline/references/harness-profile.json"
    )
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        roles = payload["hosts"][host_name]["roles"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        raise invalid_policy("invalid_harness_profile") from None
    if type(roles) is not dict:
        raise invalid_policy("invalid_harness_profile")
    declared = set()
    for role in roles.values():
        if type(role) is not dict or type(role.get("kind")) is not str:
            raise invalid_policy("invalid_harness_profile")
        kind = role["kind"]
        if kind not in _ROLE_CAPABILITIES:
            raise invalid_policy("unknown_capability_name")
        capability = _ROLE_CAPABILITIES[kind]
        if capability is not None:
            declared.add(capability)
    return HostCapabilities(host_name, frozenset(declared))


class FakeHostAdapter:
    """Deterministic adapter fixture; it never performs external dispatch."""

    def __init__(
        self,
        capabilities: HostCapabilities,
        *,
        dispatch_handles: Iterable[Optional[SessionHandle]] = (),
        resume_results: Iterable[SessionResult] = (),
    ):
        if type(capabilities) is not HostCapabilities:
            raise invalid_policy("invalid_host_capabilities")
        self._capabilities = capabilities
        self._dispatch_handles = list(dispatch_handles)
        self._resume_results = list(resume_results)
        self.dispatch_calls = []
        self.resume_calls = []

    def capabilities(self) -> HostCapabilities:
        return self._capabilities

    def dispatch(self, node: NodeSpec) -> Optional[SessionHandle]:
        if type(node) is not NodeSpec:
            raise invalid_policy("invalid_node_spec")
        self.dispatch_calls.append(node)
        return self._dispatch_handles.pop(0) if self._dispatch_handles else None

    def resume(
        self,
        handle: SessionHandle,
        feedback: ValidationFeedback,
    ) -> SessionResult:
        self.resume_calls.append((handle, feedback))
        if not self._resume_results:
            return SessionResult("blocked", (), "fake_resume_result_unavailable")
        return self._resume_results.pop(0)


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        raise invalid_policy("invalid_session_handle") from None
    if parsed.tzinfo is None:
        raise invalid_policy("invalid_session_handle")
    return parsed


class BuilderSessionManager:
    def __init__(self, adapter: HostAdapter, max_age_seconds: int = 86_400):
        if type(max_age_seconds) is not int or max_age_seconds < 0:
            raise invalid_policy("invalid_session_age_limit")
        self._adapter = adapter
        self._max_age_seconds = max_age_seconds

    def dispatch(self, node: NodeSpec) -> Optional[SessionHandle]:
        candidate = self._adapter.dispatch(node)
        if candidate is None:
            return None
        self._validate_dispatched_handle(candidate)
        return candidate

    def _validate_dispatched_handle(self, handle: SessionHandle) -> None:
        capabilities = self._adapter.capabilities()
        if type(handle) is not SessionHandle or handle.host_name != capabilities.host_name:
            raise invalid_policy("invalid_session_handle")

    def _can_resume(self, handle: Optional[SessionHandle], now: str) -> bool:
        if handle is None or type(handle) is not SessionHandle:
            return False
        capabilities = self._adapter.capabilities()
        if not capabilities.supports(HostCapability.SESSION_RESUME):
            return False
        if not handle.resume_capable or handle.host_name != capabilities.host_name:
            return False
        age = (_timestamp(now) - _timestamp(handle.created_at)).total_seconds()
        return 0 <= age <= self._max_age_seconds

    def resume_or_replace(
        self,
        node: NodeSpec,
        handle: Optional[SessionHandle],
        feedback: ValidationFeedback,
        *,
        now: str,
    ) -> BuilderSessionDecision:
        if type(node) is not NodeSpec or type(feedback) is not ValidationFeedback:
            raise invalid_policy("invalid_builder_resume_request")
        if self._can_resume(handle, now):
            result = self._adapter.resume(handle, feedback)
            if type(result) is not SessionResult:
                raise invalid_policy("invalid_session_result")
            return BuilderSessionDecision(
                "resumed", "session_resumed", handle, result, True,
                ("session_resumed",),
            )
        replacement = self.dispatch(node)
        if replacement is None:
            return BuilderSessionDecision(
                "resume_unavailable", "session_resume_unavailable", None, None, False,
                ("session_resume_unavailable",),
            )
        return BuilderSessionDecision(
            "replacement_dispatched", "session_resume_unavailable", replacement, None,
            False, ("session_resume_unavailable", "builder_replacement_dispatched"),
        )
