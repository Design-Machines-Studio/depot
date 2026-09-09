"""Codex 0.153.4 hook metadata projection; never reads referenced artifacts."""
from __future__ import annotations

import os
import select
import time
import uuid

from .live_observation import (CONTRACT, FACTS, MAX_INPUT, LiveObservationError,
    available, unavailable, parse_bounded, publish_live_observation, stamp,
    validate_event)

EVENTS = {
    "SessionStart": "session_started", "SessionEnd": "session_closed",
    "UserPromptSubmit": "turn_submitted", "PreToolUse": "tool_started",
    "PostToolUse": "tool_returned", "PermissionRequest": "approval_requested",
    "PreCompact": "compaction_started", "PostCompact": "compaction_finished",
    "SubagentStart": "agent_started", "SubagentStop": "response_closed",
    "Stop": "response_closed", "Interrupt": "interrupted",
}
TURN_EVENTS = set(EVENTS) - {"SessionStart", "SessionEnd"}


def project_codex_hook(payload, *, workspace, producer="codex-0.153.4",
                       publication_id=None, observed_at=None):
    """Only the documented metadata allowlist survives this boundary.

    SubagentStart/Stop report the PARENT session/model/turn and the CHILD
    agent_id. Never attribute that parent model or turn to the child.
    Unknown extension fields (including apparent outcomes) are discarded.
    """
    if type(payload) is not dict or payload.get("hook_event_name") not in EVENTS:
        raise LiveObservationError()
    # No version field is currently specified. Refuse claimed future schemas.
    if "schema_version" in payload or "version" in payload:
        raise LiveObservationError()
    name = payload["hook_event_name"]
    facts = {key: unavailable("unsupported_by_source") for key in FACTS}
    facts["work"] = unavailable("explicit_binding_required")
    facts["session"] = available(payload.get("session_id"))
    if facts["session"]["value"] is None:
        raise LiveObservationError()
    child = name in ("SubagentStart", "SubagentStop")
    if child:
        if payload.get("agent_id") is None:
            raise LiveObservationError()
        facts["session"] = available(payload["agent_id"])
        facts["agent"] = available(payload["agent_id"])
        facts["parent"] = available(payload["session_id"])
        facts["model"] = unavailable("parent_model_not_child_model")
        if payload.get("turn_id") is not None:
            facts["trigger_turn"] = available(payload["turn_id"])
    else:
        if payload.get("model") is not None:
            facts["model"] = available(payload["model"])
        if name in TURN_EVENTS and payload.get("turn_id") is not None:
            facts["turn"] = available(payload["turn_id"])
    if name in ("PreToolUse", "PostToolUse") and payload.get("tool_use_id") is not None:
        facts["tool_call"] = available(payload["tool_use_id"])
    activity = EVENTS[name]
    if name == "SessionStart":
        source = payload.get("source")
        if source not in ("startup", "resume", "clear", "compact"):
            raise LiveObservationError()
        activity = {"resume": "session_resumed", "compact": "compaction_finished"}.get(source, activity)
    if name == "SessionEnd" and payload.get("reason") != "other":
        raise LiveObservationError()
    event = {"contract": CONTRACT, "workspace": workspace, "producer": producer,
             "publication_id": publication_id or uuid.uuid4().hex,
             "observed_at": observed_at or stamp(), "activity": activity, "facts": facts,
             "execution": "unknown", "response": "unknown", "session_state": "unknown",
             "attention": "unknown", "outcome": "unknown"}
    if name == "UserPromptSubmit":
        event.update(execution="active", response="open", attention="none")
    if name == "PreToolUse":
        event["execution"] = "active"
    # A delayed tool return can follow interruption or response closure. Neither
    # tool callback proves response reopening or resolution of another approval.
    if name in ("SessionStart", "SubagentStart"):
        event["session_state"] = "open"
    if name == "PermissionRequest":
        event.update(execution="waiting", attention="approval_required")
    if name in ("Stop", "SubagentStop"):
        event.update(execution="idle", response="closed", attention="none")
    if name == "Interrupt":
        event.update(execution="interrupted", response="closed", attention="none")
    if name == "SessionEnd":
        event["session_state"] = "closed"
    return validate_event(event)


def read_callback(fd=0):
    """Bound bytes and receipt time before parsing; never persist raw stdin."""
    deadline = time.monotonic() + 0.25
    result = bytearray()
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            raise LiveObservationError()
        block = os.read(fd, min(16384, MAX_INPUT + 1 - len(result)))
        if not block:
            return parse_bounded(bytes(result))
        result.extend(block)
        if len(result) > MAX_INPUT:
            raise LiveObservationError()


def hook_main(args):
    """Inert hook success on every observer error; no model-visible context."""
    import signal
    def deadline(*_):
        raise LiveObservationError("publication_failed")
    started = time.monotonic()
    old = signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, 0.85)
    try:
        observed_at = stamp()
        event = project_codex_hook(read_callback(), workspace=args.workspace,
                                   producer=args.producer, observed_at=observed_at)
        publish_live_observation(args.parent, args.identity, event)
    except Exception as error:
        # Errors cannot steer work. A missing new revision means contact will
        # become unconfirmed; no success, failure or heartbeat is invented.
        try:
            if time.monotonic() - started >= 0.80:
                raise LiveObservationError("publication_failed")
            from .live_observation import publish_diagnostic
            publish_diagnostic(args.parent, args.identity,
                               error.code if isinstance(error, LiveObservationError) else "publication_failed")
        except Exception:
            pass
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
    print("{}")
    return 0
