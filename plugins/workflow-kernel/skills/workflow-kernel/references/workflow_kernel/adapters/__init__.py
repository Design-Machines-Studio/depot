"""Workflow kernel host contracts, closed builder outcomes, and safe persistence.

Builder observations project to ``evidence.recorded`` events; they are never
node lifecycle transitions. ``SessionHandle`` and ``SessionResult`` expose safe
public projections. ``ResumeStateBlob`` is the supported persistence boundary:
its raw bytes contain an opaque handle and belong only in a package-owned
trusted store. The checksum detects corruption and does not claim authenticity.
"""

from importlib import import_module

from .base import (
    AttemptLedger, BuilderObservation, BuilderOutcome, BuilderSessionDecision,
    FailureReason, GateDecision,
    HostAdapter, HostCapabilities, HostCapability, IsolationDecision, IsolationMode,
    IsolationRequirements, NodeSpec, ResumeStateBlob, ResumeStateContext,
    RetryDecision, SessionHandle, SessionResult, SessionStatus,
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
    "AttemptLedger", "BuilderObservation", "BuilderOutcome", "BuilderSessionDecision",
    "BuilderSessionManager",
    "FailureReason", "FakeHostAdapter", "GateDecision", "HostAdapter",
    "HostCapabilities", "HostCapability", "IsolationDecision", "IsolationMode",
    "IsolationRequirements", "IsolationSelector", "NodeSpec", "RetryDecision",
    "ResumeStateBlob", "ResumeStateContext", "SessionHandle", "SessionResult",
    "SessionStatus", "ValidationFeedback", "WorkflowClass",
    "WorkflowContext", "capabilities_from_harness_profile",
]
