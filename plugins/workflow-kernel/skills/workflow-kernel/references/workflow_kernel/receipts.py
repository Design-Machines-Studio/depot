"""Deterministic secret-safe receipt encoders."""

from __future__ import annotations

import hashlib
import json
from typing import Mapping, Optional

from .redaction import (
    digest_error_detail_string, normalize_evidence_reference, redact,
    sanitize_public_metadata,
)
from .schema import ErrorMessage, UnsafePayloadError, WorkflowEvent


def encode_receipt(receipt: Mapping[str, object]) -> bytes:
    try:
        safe = redact(receipt)
    except (TypeError, ValueError) as exc:
        raise UnsafePayloadError(ErrorMessage.RECEIPT_NON_JSON_SAFE) from exc
    return (json.dumps(safe, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def evidence_receipt(run_id: str, evidence_type: str, reference: str, *, metadata: Optional[Mapping[str, object]] = None) -> dict:
    try:
        if not all(type(value) is str for value in (run_id, evidence_type, reference)):
            raise TypeError("receipt caller fields must be strings")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise TypeError("receipt metadata must be a mapping")
        safe = {
            "schema_version": 1,
            "receipt_type": "evidence",
            "run_id": digest_error_detail_string(run_id),
            "evidence_type": digest_error_detail_string(evidence_type),
            "reference": normalize_evidence_reference(reference),
            "metadata": sanitize_public_metadata(dict(metadata or {})),
        }
    except (TypeError, ValueError) as exc:
        raise UnsafePayloadError(ErrorMessage.EVIDENCE_RECEIPT_UNSAFE) from exc
    safe["digest"] = "sha256:" + hashlib.sha256(encode_receipt(safe)).hexdigest()
    return safe


def transition_receipt(event: WorkflowEvent, state_digest: str) -> dict:
    return redact({"schema_version": 1, "receipt_type": "transition", "event": event.to_dict(), "state_digest": state_digest})
