"""Deterministic secret-safe receipt builders and raw-mapping encoder."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from enum import Enum
from typing import Optional

from .redaction import (
    VALUE_DIGEST_PREFIX, apply_json_policy, digest_error_detail_key,
    normalize_durable_string, normalize_evidence_reference,
    validate_durable_key,
)
from .schema import (
    ErrorMessage, UnsafePayloadError, WORKFLOW_EVENT_FIELDS, WorkflowEvent,
    WorkflowEventField,
)


class ReceiptField(str, Enum):
    """Developer-owned field vocabulary for receipt schemas."""

    SCHEMA_VERSION = "schema_version"
    RECEIPT_TYPE = "receipt_type"
    RUN_ID = "run_id"
    EVIDENCE_TYPE = "evidence_type"
    REFERENCE = "reference"
    METADATA = "metadata"
    DIGEST = "digest"
    EVENT = "event"
    STATE_DIGEST = "state_digest"


_STATE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _canonical_bytes(value: Mapping[str, object]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class _Policy(Enum):
    PUBLIC = "public"
    PLAIN = "plain"
    MAPPING = "mapping"


_EVENT_RECEIPT_SCHEMA = {
    WorkflowEventField.SCHEMA_VERSION.value: _Policy.PLAIN,
    WorkflowEventField.SEQUENCE.value: _Policy.PLAIN,
    WorkflowEventField.RUN_ID.value: _Policy.PUBLIC,
    WorkflowEventField.NODE_ID.value: _Policy.PUBLIC,
    WorkflowEventField.KIND.value: _Policy.PUBLIC,
    WorkflowEventField.OCCURRED_AT.value: _Policy.PUBLIC,
    WorkflowEventField.PAYLOAD.value: _Policy.MAPPING,
}
if frozenset(_EVENT_RECEIPT_SCHEMA) != WORKFLOW_EVENT_FIELDS:  # pragma: no cover - import-time invariant
    raise RuntimeError("transition receipt event schema drifted from WorkflowEvent")

_EVIDENCE_RECEIPT_SCHEMA = {
    ReceiptField.SCHEMA_VERSION.value: _Policy.PLAIN,
    ReceiptField.RECEIPT_TYPE.value: _Policy.PLAIN,
    ReceiptField.RUN_ID.value: _Policy.PUBLIC,
    ReceiptField.EVIDENCE_TYPE.value: _Policy.PUBLIC,
    ReceiptField.REFERENCE.value: _Policy.PLAIN,
    ReceiptField.METADATA.value: _Policy.MAPPING,
    ReceiptField.DIGEST.value: _Policy.PLAIN,
}
_TRANSITION_RECEIPT_SCHEMA = {
    ReceiptField.SCHEMA_VERSION.value: _Policy.PLAIN,
    ReceiptField.RECEIPT_TYPE.value: _Policy.PLAIN,
    ReceiptField.EVENT.value: _EVENT_RECEIPT_SCHEMA,
    ReceiptField.STATE_DIGEST.value: _Policy.PLAIN,
}

EVIDENCE_RECEIPT_FIELDS = frozenset(_EVIDENCE_RECEIPT_SCHEMA)
TRANSITION_RECEIPT_FIELDS = frozenset(_TRANSITION_RECEIPT_SCHEMA)


def _public_digest(value: str) -> str:
    normalized = normalize_durable_string(value)
    return VALUE_DIGEST_PREFIX + hashlib.sha256(str.encode(normalized, "utf-8")).hexdigest()


def _receipt_string_policy(value: str, _key: str, policy) -> str:
    if policy is _Policy.PLAIN:
        return value
    return _public_digest(value)


def _receipt_mapping_policy(raw_key: str, schema):
    validate_durable_key(raw_key)
    vocabulary = schema if isinstance(schema, Mapping) else {}
    known = type(raw_key) is str and raw_key in vocabulary
    safe_key = raw_key if known else digest_error_detail_key(raw_key)
    return safe_key, vocabulary[raw_key] if known else None


def _receipt_value_policy(value, _key: str, policy) -> None:
    if policy is _Policy.PUBLIC:
        if value is not None and not isinstance(value, str):
            raise TypeError("public receipt field must be a string")
        return
    if policy is _Policy.PLAIN:
        if isinstance(value, str):
            if type(value) is not str:
                raise TypeError("plain receipt field must be an exact string")
            return
        if value is None or isinstance(value, bool) or isinstance(value, int):
            return
        raise TypeError("plain receipt field has an invalid type")
    if policy is _Policy.MAPPING or isinstance(policy, Mapping):
        if not isinstance(value, Mapping):
            raise TypeError("receipt field must be a mapping")


def _sanitize_receipt(receipt: Mapping[str, object], *, schema=None) -> dict:
    if not isinstance(receipt, Mapping):
        raise TypeError("receipt must be a mapping")
    return apply_json_policy(
        receipt,
        string_policy=_receipt_string_policy,
        mapping_policy=_receipt_mapping_policy,
        value_policy=_receipt_value_policy,
        schema=schema,
    )


def encode_receipt(receipt: Mapping[str, object]) -> bytes:
    """Sanitize one untrusted mapping traversal and return canonical bytes."""
    try:
        return _canonical_bytes(_sanitize_receipt(receipt))
    except (TypeError, ValueError):
        raise UnsafePayloadError(ErrorMessage.RECEIPT_NON_JSON_SAFE) from None


def evidence_receipt(run_id: str, evidence_type: str, reference: str, *,
                     metadata: Optional[Mapping[str, object]] = None) -> bytes:
    try:
        if not all(type(value) is str for value in (run_id, evidence_type, reference)):
            raise TypeError("receipt caller fields must be strings")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise TypeError("receipt metadata must be a mapping")
        normalized_reference = normalize_evidence_reference(reference)
        digest_free = {
            ReceiptField.SCHEMA_VERSION.value: 1,
            ReceiptField.RECEIPT_TYPE.value: "evidence",
            ReceiptField.RUN_ID.value: run_id,
            ReceiptField.EVIDENCE_TYPE.value: evidence_type,
            ReceiptField.REFERENCE.value: normalized_reference,
            ReceiptField.METADATA.value: metadata if metadata is not None else {},
        }
        final = _sanitize_receipt(digest_free, schema=_EVIDENCE_RECEIPT_SCHEMA)
        digest_free_bytes = _canonical_bytes(final)
        final[ReceiptField.DIGEST.value] = (
            "sha256:" + hashlib.sha256(digest_free_bytes).hexdigest()
        )
        return _canonical_bytes(final)
    except (TypeError, ValueError):
        raise UnsafePayloadError(ErrorMessage.EVIDENCE_RECEIPT_UNSAFE) from None


def transition_receipt(event: WorkflowEvent, state_digest: str) -> bytes:
    try:
        if type(event) is not WorkflowEvent:
            raise TypeError("transition receipt requires a workflow event")
        if type(state_digest) is not str or not _STATE_DIGEST.fullmatch(state_digest):
            raise ValueError("state digest must be canonical sha256")
        return _canonical_bytes(_sanitize_receipt({
            ReceiptField.SCHEMA_VERSION.value: 1,
            ReceiptField.RECEIPT_TYPE.value: "transition",
            ReceiptField.EVENT.value: WorkflowEvent.to_dict(
                WorkflowEvent.from_dict(WorkflowEvent.to_dict(event))
            ),
            ReceiptField.STATE_DIGEST.value: state_digest,
        }, schema=_TRANSITION_RECEIPT_SCHEMA))
    except (TypeError, ValueError):
        raise UnsafePayloadError(ErrorMessage.RECEIPT_NON_JSON_SAFE) from None


__all__ = [
    "EVIDENCE_RECEIPT_FIELDS", "TRANSITION_RECEIPT_FIELDS", "ReceiptField",
    "encode_receipt", "evidence_receipt", "transition_receipt",
]
