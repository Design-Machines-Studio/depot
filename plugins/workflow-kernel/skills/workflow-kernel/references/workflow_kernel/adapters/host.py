"""Declared host capabilities and fake-safe builder session handling."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from .base import (
    BuilderObservation, BuilderSessionDecision, HostAdapter, HostCapabilities,
    HostCapability, NodeSpec, SessionHandle, SessionResult, ValidationFeedback,
    _snapshot_session_handle, invalid_policy,
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
        if kind == "codex_companion":
            declared.add(HostCapability.CODEX_EXECUTION)
        if kind in ("wrapper", "openrouter_exec"):
            declared.add(HostCapability.OPENROUTER_EXECUTION)
        if kind == "native":
            if host_name == "claude-code":
                declared.add(HostCapability.CLAUDE_EXECUTION)
            elif host_name == "codex":
                declared.add(HostCapability.CODEX_EXECUTION)
        models = role.get("models", [])
        if not isinstance(models, list) or any(type(model) is not str for model in models):
            raise invalid_policy("invalid_harness_profile")
        if any(model.startswith("anthropic/") for model in models):
            declared.add(HostCapability.CLAUDE_EXECUTION)
        if any(model.startswith("openai/") or model.startswith("gpt-") for model in models):
            declared.add(HostCapability.CODEX_EXECUTION)
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

    def _safe_capabilities(self) -> Optional[HostCapabilities]:
        try:
            capabilities = self._adapter.capabilities()
        except Exception:
            return None
        return capabilities if type(capabilities) is HostCapabilities else None

    def dispatch(self, node: NodeSpec) -> BuilderSessionDecision:
        if type(node) is not NodeSpec:
            raise invalid_policy("invalid_node_spec")
        capabilities = self._safe_capabilities()
        if capabilities is None:
            return _blocked_decision("adapter_capabilities_failed")
        return self._dispatch_with_capabilities(node, capabilities)

    def _dispatch_with_capabilities(
        self,
        node: NodeSpec,
        capabilities: HostCapabilities,
    ) -> BuilderSessionDecision:
        if not node.gate_decision.allowed:
            return _blocked_decision("node_gate_blocked")
        if (
            node.required_capability is None
            or not capabilities.supports(node.required_capability)
        ):
            return _blocked_decision("host_capability_unavailable")
        try:
            candidate = self._adapter.dispatch(node)
        except Exception:
            return _blocked_decision("adapter_dispatch_failed")
        if candidate is None:
            return _blocked_decision("session_handle_unavailable")
        try:
            handle = _snapshot_session_handle(candidate)
        except Exception:
            return _blocked_decision("invalid_session_handle")
        if handle.host_name != capabilities.host_name:
            return _blocked_decision("invalid_session_handle")
        return BuilderSessionDecision(
            "dispatched", "builder_dispatched", handle, None, False,
            (BuilderObservation.BUILDER_DISPATCHED,),
        )

    def _can_resume(
        self,
        handle: Optional[SessionHandle],
        now: str,
        capabilities: HostCapabilities,
    ) -> bool:
        if handle is None or type(handle) is not SessionHandle:
            return False
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
        capabilities = self._safe_capabilities()
        if capabilities is None:
            return _blocked_decision("adapter_capabilities_failed")
        if self._can_resume(handle, now, capabilities):
            try:
                result = self._adapter.resume(_snapshot_session_handle(handle), feedback)
            except Exception:
                result = None
            if type(result) is SessionResult:
                return BuilderSessionDecision(
                    "resumed", "session_resumed", handle, result, True,
                    (BuilderObservation.SESSION_RESUMED,),
                )
        replacement = self._dispatch_with_capabilities(node, capabilities)
        if replacement.status != "dispatched":
            if replacement.reason_code in {
                "adapter_dispatch_failed", "adapter_capabilities_failed",
                "host_capability_unavailable", "node_gate_blocked", "invalid_session_handle",
            }:
                return replacement
            return BuilderSessionDecision(
                "resume_unavailable", "session_resume_unavailable", None, None, False,
                (BuilderObservation.SESSION_RESUME_UNAVAILABLE,),
            )
        return BuilderSessionDecision(
            "replacement_dispatched", "session_resume_unavailable", replacement.handle, None,
            False, (BuilderObservation.SESSION_RESUME_UNAVAILABLE,
                    BuilderObservation.BUILDER_REPLACEMENT_DISPATCHED),
        )

    def _serialize_resume_state(self, handle: SessionHandle) -> "_DurableResumeState":
        snapshot = _snapshot_session_handle(handle)
        handle_payload = {
            "host_name": snapshot.host_name,
            "opaque_handle": snapshot.opaque_handle,
            "created_at": snapshot.created_at,
            "resume_capable": snapshot.resume_capable,
        }
        canonical = _canonical_json(handle_payload)
        payload = {
            "schema_version": 1,
            "handle": handle_payload,
            "checksum": hashlib.sha256(canonical).hexdigest(),
        }
        return _DurableResumeState(_canonical_json(payload))

    def _restore_resume_state(
        self,
        state: Optional[object],
    ) -> Optional[SessionHandle]:
        if state is None:
            return None
        if type(state) is _DurableResumeState:
            raw = state._payload
        elif type(state) is bytes:
            raw = state
        else:
            raise invalid_policy("invalid_session_resume_state")
        try:
            payload = json.loads(raw.decode("utf-8"))
            if type(payload) is not dict or set(payload) != {
                "schema_version", "handle", "checksum",
            } or payload["schema_version"] != 1:
                raise ValueError
            handle_payload = payload["handle"]
            if type(handle_payload) is not dict or set(handle_payload) != {
                "host_name", "opaque_handle", "created_at", "resume_capable",
            } or type(payload["checksum"]) is not str:
                raise ValueError
            if hashlib.sha256(_canonical_json(handle_payload)).hexdigest() != payload["checksum"]:
                raise ValueError
            handle = SessionHandle(**handle_payload)
        except (AttributeError, TypeError, ValueError, UnicodeError, json.JSONDecodeError):
            raise invalid_policy("invalid_session_resume_state") from None
        except Exception as error:
            if getattr(error, "details", None) is not None:
                raise invalid_policy("invalid_session_resume_state") from None
            raise
        capabilities = self._safe_capabilities()
        if capabilities is None:
            raise invalid_policy("adapter_capabilities_failed")
        if handle.host_name != capabilities.host_name:
            raise invalid_policy("foreign_session_resume_state")
        return _snapshot_session_handle(handle)


def _blocked_decision(reason_code: str) -> BuilderSessionDecision:
    return BuilderSessionDecision(
        "blocked", reason_code, None, None, False,
        (BuilderObservation.DISPATCH_BLOCKED,),
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, repr=False)
class _DurableResumeState:
    _payload: bytes

    def __repr__(self) -> str:
        digest = hashlib.sha256(self._payload).hexdigest()
        return f"_DurableResumeState(sha256:{digest})"

    def __getitem__(self, key: object) -> object:
        return self._payload[key]
