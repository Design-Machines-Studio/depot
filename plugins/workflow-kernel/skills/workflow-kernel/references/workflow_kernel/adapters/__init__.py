"""Workflow kernel host adapter contracts and deterministic fakes."""

from importlib import import_module

from .base import (
    AttemptLedger, BuilderObservation, BuilderSessionDecision, FailureReason, GateDecision,
    HostAdapter, HostCapabilities, HostCapability, IsolationDecision, IsolationMode,
    IsolationRequirements, NodeSpec, RetryDecision, SessionHandle, SessionResult,
    ValidationFeedback, WorkflowClass, WorkflowContext,
)

_LAZY_EXPORTS = {
    "BuilderSessionManager": (".host", "BuilderSessionManager"),
    "FakeHostAdapter": (".host", "FakeHostAdapter"),
    "capabilities_from_harness_profile": (".host", "capabilities_from_harness_profile"),
    "IsolationSelector": (".isolation", "IsolationSelector"),
}


def __getattr__(name: str) -> object:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module = import_module(target[0], __name__)
    value = getattr(module, target[1])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))

__all__ = [
    "AttemptLedger", "BuilderObservation", "BuilderSessionDecision", "BuilderSessionManager",
    "FailureReason", "FakeHostAdapter", "GateDecision", "HostAdapter",
    "HostCapabilities", "HostCapability", "IsolationDecision", "IsolationMode",
    "IsolationRequirements", "IsolationSelector", "NodeSpec", "RetryDecision",
    "SessionHandle", "SessionResult", "ValidationFeedback", "WorkflowClass",
    "WorkflowContext", "capabilities_from_harness_profile",
]
