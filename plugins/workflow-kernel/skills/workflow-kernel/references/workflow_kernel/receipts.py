"""Deterministic secret-safe receipt encoders."""

from __future__ import annotations

import hashlib
import json
from typing import Mapping, Optional

from .redaction import redact
from .schema import UnsafePayloadError, WorkflowEvent


def encode_receipt(receipt: Mapping[str, object]) -> bytes:
    try:
        safe = redact(receipt)
    except TypeError as exc:
        raise UnsafePayloadError("receipt contains a non-JSON-safe value") from exc
    return (json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def evidence_receipt(run_id: str, evidence_type: str, reference: str, *, metadata: Optional[Mapping[str, object]] = None) -> dict:
    receipt = {"schema_version": 1, "receipt_type": "evidence", "run_id": run_id,
               "evidence_type": evidence_type, "reference": reference, "metadata": dict(metadata or {})}
    safe = redact(receipt)
    safe["digest"] = "sha256:" + hashlib.sha256(encode_receipt(safe)).hexdigest()
    return safe


def transition_receipt(event: WorkflowEvent, state_digest: str) -> dict:
    return redact({"schema_version": 1, "receipt_type": "transition", "event": event.to_dict(), "state_digest": state_digest})
