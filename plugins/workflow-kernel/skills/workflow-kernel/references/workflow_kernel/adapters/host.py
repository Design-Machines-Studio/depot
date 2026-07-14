"""Declared host capabilities and fake-safe builder session handling."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from .base import (
    BuilderOutcome, BuilderSessionDecision, HostAdapter, HostCapabilities,
    DISPATCH_RAIL_CAPABILITIES, HostRoute, HostCapability,
    MAX_RESUME_STATE_BYTES, NodeSpec, ResumeStateBlob, ResumeStateContext,
    SessionHandle, SessionResult, ValidationFeedback, _snapshot_resume_context,
    _snapshot_host_capabilities, _snapshot_node_spec, _snapshot_session_handle,
    _snapshot_session_result, route_satisfies_node,
    _snapshot_validation_feedback, invalid_policy,
)
from ..schema import InvalidSchemaError


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
    routes = set()
    for role in roles.values():
        if type(role) is not dict or type(role.get("kind")) is not str:
            raise invalid_policy("invalid_harness_profile")
        kind = role["kind"]
        if kind != "none" and kind not in DISPATCH_RAIL_CAPABILITIES:
            raise invalid_policy("unknown_capability_name")
        if kind == "none":
            if set(role) != {"kind"}:
                raise invalid_policy("invalid_harness_profile")
            continue
        if set(role) != {"kind", "probe", "models"}:
            raise invalid_policy("invalid_harness_profile")
        probe = role["probe"]
        models = role["models"]
        expected_probes = {
            "native": {"claude", "codex"},
            "codex_companion": {"codex"},
            "wrapper": {"openrouter"},
            "openrouter_exec": {"openrouter"},
        }[kind]
        if type(probe) is not str or probe not in expected_probes:
            raise invalid_policy("invalid_harness_profile")
        if not isinstance(models, list) or not models or any(
            type(model) is not str or not model for model in models
        ):
            raise invalid_policy("invalid_harness_profile")
        if kind in ("native", "codex_companion") and (
            (probe == "claude" and any(
                model.startswith("openai/") or model.startswith("gpt-")
                for model in models
            ))
            or (probe == "codex" and any(
                model.startswith("anthropic/") for model in models
            ))
        ):
            raise invalid_policy("invalid_harness_profile")
        if kind == "native" and probe == "claude":
            routes.add(HostRoute(
                "anthropic", HostCapability.CLAUDE_EXECUTION, "native",
            ))
            routes.add(HostRoute(
                "anthropic", HostCapability.ANTHROPIC_NATIVE_EXECUTION, "native",
            ))
        elif kind in ("native", "codex_companion") and probe == "codex":
            routes.add(HostRoute(
                "openai", HostCapability.CODEX_EXECUTION, kind,
            ))
        elif kind in ("wrapper", "openrouter_exec"):
            routes.add(HostRoute(
                "openrouter", HostCapability.OPENROUTER_EXECUTION, kind,
            ))
        if kind in ("wrapper", "openrouter_exec") and any(
            model.startswith("anthropic/") for model in models
        ):
            routes.add(HostRoute(
                "openrouter", HostCapability.CLAUDE_EXECUTION, kind,
            ))
        if kind in ("wrapper", "openrouter_exec") and any(
            model.startswith("openai/") or model.startswith("gpt-")
            for model in models
        ):
            routes.add(HostRoute(
                "openrouter", HostCapability.CODEX_EXECUTION, kind,
            ))
    return HostCapabilities(host_name, frozenset(), routes=frozenset(routes))


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

    def dispatch(
        self, node: NodeSpec, context: ResumeStateContext,
    ) -> Optional[SessionHandle]:
        if type(node) is not NodeSpec or type(context) is not ResumeStateContext:
            raise invalid_policy("invalid_node_spec")
        self.dispatch_calls.append((node, context))
        return self._dispatch_handles.pop(0) if self._dispatch_handles else None

    def resume(
        self,
        handle: SessionHandle,
        feedback: ValidationFeedback,
    ) -> SessionResult:
        self.resume_calls.append((handle, feedback))
        if not self._resume_results:
            return SessionResult(
                "blocked", handle.context, (), "fake_resume_result_unavailable",
            )
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
    """Owns provenance-safe dispatch/resume and trusted-store persistence.

    Adapter receipts must match the authorized node, run, attempt, provider,
    executor capability, and concrete dispatch rail. Resume blobs contain real
    opaque handles and belong only in a protected package-owned trusted store
    with explicit retention/deletion. Their checksum detects corruption; it
    does not claim authenticity. Public repr/projections remain redacted, and
    blobs are excluded from ordinary receipts, events, evidence, artifacts,
    shadow reports, Airlift payloads, and checkpoints.
    """
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
        if type(capabilities) is not HostCapabilities:
            return None
        try:
            return _snapshot_host_capabilities(capabilities)
        except Exception:
            return None

    def dispatch(
        self, node: NodeSpec, context: ResumeStateContext,
    ) -> BuilderSessionDecision:
        node = _snapshot_node_spec(node)
        context = self._authorized_context(node, context, "invalid_builder_dispatch_request")
        blocked = self._gate_preflight(node, context)
        if blocked is not None:
            return blocked
        capabilities = self._safe_capabilities()
        if capabilities is None:
            return BuilderSessionDecision(
                BuilderOutcome.ADAPTER_CAPABILITIES_FAILED, context,
            )
        preflight = self._capability_preflight(context, capabilities)
        if preflight is not None:
            return preflight
        return self._dispatch_with_capabilities(
            node, context, capabilities, replacement=False,
        )

    def _authorized_context(
        self, node: NodeSpec, context: ResumeStateContext, reason_code: str,
    ) -> ResumeStateContext:
        try:
            context = _snapshot_resume_context(context)
        except (InvalidSchemaError, KeyError, TypeError):
            raise invalid_policy(reason_code) from None
        if (
            node.executor is None
            or context.node_id != node.node_id
            or not route_satisfies_node(context.route, node)
        ):
            raise invalid_policy(reason_code)
        return context

    def _gate_preflight(
        self, node: NodeSpec, context: ResumeStateContext,
    ) -> Optional[BuilderSessionDecision]:
        if not node.gate_decision.allowed:
            return BuilderSessionDecision(BuilderOutcome.NODE_GATE_BLOCKED, context)
        return None

    def _capability_preflight(
        self, context: ResumeStateContext, capabilities: HostCapabilities,
    ) -> Optional[BuilderSessionDecision]:
        if not capabilities.supports_route(context.route):
            return BuilderSessionDecision(
                BuilderOutcome.HOST_CAPABILITY_UNAVAILABLE, context,
            )
        return None

    def _dispatch_with_capabilities(
        self,
        node: NodeSpec,
        context: ResumeStateContext,
        capabilities: HostCapabilities,
        *,
        replacement: bool,
    ) -> BuilderSessionDecision:
        try:
            candidate = self._adapter.dispatch(node, context)
        except Exception:
            return BuilderSessionDecision(
                BuilderOutcome.REPLACEMENT_ADAPTER_DISPATCH_FAILED
                if replacement else BuilderOutcome.ADAPTER_DISPATCH_FAILED,
                context,
            )
        if candidate is None:
            return BuilderSessionDecision(
                BuilderOutcome.REPLACEMENT_SESSION_HANDLE_UNAVAILABLE
                if replacement else BuilderOutcome.SESSION_HANDLE_UNAVAILABLE,
                context,
            )
        try:
            handle = _snapshot_session_handle(candidate)
        except Exception:
            return BuilderSessionDecision(
                BuilderOutcome.REPLACEMENT_INVALID_SESSION_HANDLE
                if replacement else BuilderOutcome.INVALID_SESSION_HANDLE,
                context,
            )
        if (
            handle.host_name != capabilities.host_name
            or handle.context != context
        ):
            return BuilderSessionDecision(
                BuilderOutcome.REPLACEMENT_INVALID_SESSION_HANDLE
                if replacement else BuilderOutcome.INVALID_SESSION_HANDLE,
                context,
            )
        return BuilderSessionDecision(
            BuilderOutcome.REPLACEMENT_DISPATCHED if replacement
            else BuilderOutcome.BUILDER_DISPATCHED,
            context,
            handle,
        )

    def _can_resume(
        self,
        handle: Optional[SessionHandle],
        now: datetime,
        context: ResumeStateContext,
        capabilities: HostCapabilities,
    ) -> bool:
        if handle is None or type(handle) is not SessionHandle:
            return False
        if HostCapability.SESSION_RESUME not in capabilities.capabilities:
            return False
        if (
            not handle.resume_capable
            or handle.host_name != capabilities.host_name
            or handle.context != context
        ):
            return False
        age = (now - _timestamp(handle.created_at)).total_seconds()
        return 0 <= age <= self._max_age_seconds

    def resume_or_replace(
        self,
        node: NodeSpec,
        handle: Optional[SessionHandle],
        feedback: ValidationFeedback,
        *,
        context: ResumeStateContext,
        now: str,
    ) -> BuilderSessionDecision:
        if type(feedback) is not ValidationFeedback:
            raise invalid_policy("invalid_builder_resume_request")
        try:
            handle = (
                None if handle is None else _snapshot_session_handle(handle)
            )
            if type(now) is not str:
                raise TypeError
            now_timestamp = _timestamp(now)
        except Exception:
            raise invalid_policy("invalid_builder_resume_request") from None
        node = _snapshot_node_spec(node)
        context = self._authorized_context(
            node, context, "invalid_builder_resume_request",
        )
        feedback = _snapshot_validation_feedback(feedback)
        if feedback.node_id != node.node_id:
            raise invalid_policy("invalid_builder_resume_request")
        blocked = self._gate_preflight(node, context)
        if blocked is not None:
            return blocked
        capabilities = self._safe_capabilities()
        if capabilities is None:
            return BuilderSessionDecision(
                BuilderOutcome.ADAPTER_CAPABILITIES_FAILED, context,
            )
        preflight = self._capability_preflight(context, capabilities)
        if preflight is not None:
            return preflight
        if self._can_resume(handle, now_timestamp, context, capabilities):
            try:
                result = self._adapter.resume(_snapshot_session_handle(handle), feedback)
            except Exception:
                result = None
            if type(result) is SessionResult:
                try:
                    safe_result = _snapshot_session_result(result)
                except Exception:
                    safe_result = None
                if safe_result is not None and safe_result.context == context:
                    return BuilderSessionDecision(
                        BuilderOutcome.SESSION_RESUMED, context, handle, safe_result,
                    )
        return self._dispatch_with_capabilities(
            node, context, capabilities, replacement=True,
        )

    def serialize_resume_state(self, handle: SessionHandle) -> ResumeStateBlob:
        """Persist validated receipt provenance in a trusted package store only.

        The blob is excluded from receipts, events, evidence, artifacts, shadow
        reports, and checkpoints. A protected store owns retention and deletion.
        """
        snapshot = _snapshot_session_handle(handle)
        context = snapshot.context
        handle_payload = {
            "host_name": snapshot.host_name,
            "opaque_handle": snapshot.opaque_handle,
            "created_at": snapshot.created_at,
            "resume_capable": snapshot.resume_capable,
        }
        checked = {
            "schema_version": 1,
            "context": context.to_dict(),
            "handle": handle_payload,
        }
        payload = dict(checked)
        payload["checksum"] = hashlib.sha256(_canonical_json(checked)).hexdigest()
        return ResumeStateBlob(_canonical_json(payload))

    def restore_resume_state(
        self,
        state: Optional[object],
        expected_context: ResumeStateContext,
    ) -> Optional[SessionHandle]:
        """Restore trusted-store bytes only when immutable context still matches."""
        expected_context = _snapshot_resume_context(expected_context)
        if state is None:
            return None
        if type(state) is ResumeStateBlob:
            raw = state.to_trusted_bytes()
        elif type(state) is bytes:
            raw = state
        else:
            raise invalid_policy("invalid_session_resume_state")
        if len(raw) > MAX_RESUME_STATE_BYTES:
            raise invalid_policy("invalid_session_resume_state")
        try:
            payload = json.loads(raw.decode("utf-8"))
            if type(payload) is not dict or set(payload) != {
                "schema_version", "context", "handle", "checksum",
            } or type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
                raise ValueError
            context_payload = payload["context"]
            if type(context_payload) is not dict or set(context_payload) != {
                "run_id", "node_id", "attempt_id", "provider", "rail",
                "capability",
            }:
                raise ValueError
            stored_context = ResumeStateContext(**context_payload)
            handle_payload = payload["handle"]
            if type(handle_payload) is not dict or set(handle_payload) != {
                "host_name", "opaque_handle", "created_at", "resume_capable",
            } or type(payload["checksum"]) is not str:
                raise ValueError
            checked = {
                "schema_version": payload["schema_version"],
                "context": stored_context.to_dict(),
                "handle": handle_payload,
            }
            if hashlib.sha256(_canonical_json(checked)).hexdigest() != payload["checksum"]:
                raise ValueError
            handle = SessionHandle(context=stored_context, **handle_payload)
        except (AttributeError, TypeError, ValueError, UnicodeError, json.JSONDecodeError,
                RecursionError):
            raise invalid_policy("invalid_session_resume_state") from None
        except Exception as error:
            if getattr(error, "details", None) is not None:
                raise invalid_policy("invalid_session_resume_state") from None
            raise
        if stored_context != expected_context:
            raise invalid_policy("foreign_session_resume_state")
        capabilities = self._safe_capabilities()
        if capabilities is None:
            raise invalid_policy("adapter_capabilities_failed")
        if (
            handle.host_name != capabilities.host_name
            or not capabilities.supports_route(stored_context.route)
        ):
            raise invalid_policy("foreign_session_resume_state")
        return _snapshot_session_handle(handle)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
