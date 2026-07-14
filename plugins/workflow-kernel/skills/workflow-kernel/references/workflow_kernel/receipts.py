"""Deterministic secret-safe receipt encoders."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping, Optional

from .redaction import normalize_evidence_reference, redact, sanitize_public_metadata
from .schema import ErrorMessage, UnsafePayloadError, WorkflowEvent


_STATE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RECEIPT_KEYS = frozenset({
    "schema_version", "receipt_type", "run_id", "evidence_type", "reference",
    "metadata", "digest", "event", "state_digest", "sequence", "node_id",
    "kind", "occurred_at", "payload",
})


def _sanitize_receipt(receipt: Mapping[str, object]) -> dict:
    if not isinstance(receipt, Mapping):
        raise TypeError("receipt must be a mapping")
    safe = sanitize_public_metadata(receipt, known_keys=_RECEIPT_KEYS)
    if "reference" in receipt:
        reference = receipt["reference"]
        if type(reference) is not str:
            raise TypeError("receipt reference must be a string")
        safe["reference"] = normalize_evidence_reference(reference)
    receipt_type = receipt.get("receipt_type")
    if type(receipt_type) is str and receipt_type in {"evidence", "transition"}:
        safe["receipt_type"] = receipt_type
    return safe


def encode_receipt(receipt: Mapping[str, object]) -> bytes:
    try:
        safe = _sanitize_receipt(redact(receipt))
    except (TypeError, ValueError) as exc:
        raise UnsafePayloadError(ErrorMessage.RECEIPT_NON_JSON_SAFE) from exc
    return (json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def evidence_receipt(run_id: str, evidence_type: str, reference: str, *, metadata: Optional[Mapping[str, object]] = None) -> dict:
    try:
        if not all(type(value) is str for value in (run_id, evidence_type, reference)):
            raise TypeError("receipt caller fields must be strings")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise TypeError("receipt metadata must be a mapping")
        safe = _sanitize_receipt({
            "schema_version": 1,
            "receipt_type": "evidence",
            "run_id": run_id,
            "evidence_type": evidence_type,
            "reference": reference,
            "metadata": dict(metadata or {}),
        })
    except (TypeError, ValueError) as exc:
        raise UnsafePayloadError(ErrorMessage.EVIDENCE_RECEIPT_UNSAFE) from exc
    safe["digest"] = "sha256:" + hashlib.sha256(encode_receipt(safe)).hexdigest()
    return safe


def transition_receipt(event: WorkflowEvent, state_digest: str) -> dict:
    try:
        if not isinstance(event, WorkflowEvent):
            raise TypeError("transition receipt requires a workflow event")
        if type(state_digest) is not str or not _STATE_DIGEST.fullmatch(state_digest):
            raise ValueError("state digest must be canonical sha256")
        return _sanitize_receipt({
            "schema_version": 1,
            "receipt_type": "transition",
            "event": event.to_dict(),
            "state_digest": state_digest,
        })
    except (TypeError, ValueError) as exc:
        raise UnsafePayloadError(ErrorMessage.RECEIPT_NON_JSON_SAFE) from exc
