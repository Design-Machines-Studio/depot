"""Deterministic secret-safe receipt capabilities and encoders."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from enum import Enum
from typing import Optional

from .redaction import (
    MAX_PAYLOAD_DEPTH, MAX_PAYLOAD_ITEMS, MAX_STRING_LENGTH,
    REDACTED, VALUE_DIGEST_PREFIX, digest_error_detail_key, is_secret_key,
    normalize_durable_string, normalize_evidence_reference, validate_durable_key,
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


EVIDENCE_RECEIPT_FIELDS = frozenset({
    ReceiptField.SCHEMA_VERSION.value,
    ReceiptField.RECEIPT_TYPE.value,
    ReceiptField.RUN_ID.value,
    ReceiptField.EVIDENCE_TYPE.value,
    ReceiptField.REFERENCE.value,
    ReceiptField.METADATA.value,
    ReceiptField.DIGEST.value,
})
TRANSITION_RECEIPT_FIELDS = frozenset({
    ReceiptField.SCHEMA_VERSION.value,
    ReceiptField.RECEIPT_TYPE.value,
    ReceiptField.EVENT.value,
    ReceiptField.STATE_DIGEST.value,
})

_STATE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_KEY_DIGEST = re.compile(r"key-sha256:[0-9a-f]{64}\Z")
_SAFE_RECEIPT_CAPABILITY = object()


class _FrozenReceiptMapping(dict):
    """JSON-encodable mapping that rejects mutation through its public API."""

    def __init__(self, value, *, _capability=None):
        if _capability is not _SAFE_RECEIPT_CAPABILITY:
            raise TypeError("safe receipt mappings are sanitizer-owned")
        dict.__init__(self, ((key, _freeze_safe(item)) for key, item in value.items()))

    @staticmethod
    def _immutable(*_args, **_kwargs):
        raise TypeError("safe receipt is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __ior__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable

    def __setattr__(self, _name, _value):
        raise TypeError("safe receipt is immutable")

    def __delattr__(self, _name):
        raise TypeError("safe receipt is immutable")

    def copy(self):
        """A copy deliberately loses provenance and becomes an ordinary dict."""
        return dict(self)


class SafeReceipt(_FrozenReceiptMapping):
    """Immutable proof that a receipt payload passed the owned sanitizer."""


def _freeze_safe(value):
    if isinstance(value, Mapping):
        return _FrozenReceiptMapping(value, _capability=_SAFE_RECEIPT_CAPABILITY)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_safe(item) for item in value)
    return value


def _make_safe_receipt(value: Mapping[str, object]) -> SafeReceipt:
    return SafeReceipt(value, _capability=_SAFE_RECEIPT_CAPABILITY)


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


def _public_digest(value: str) -> str:
    normalized = normalize_durable_string(value)
    return VALUE_DIGEST_PREFIX + hashlib.sha256(str.encode(normalized, "utf-8")).hexdigest()


class _ReceiptSanitizer:
    """One-pass recursive durable normalization and public-value sanitization."""

    def __init__(self):
        self.count = 0

    def sanitize(self, value, *, schema=None, policy=None, key="", depth=0):
        if depth > MAX_PAYLOAD_DEPTH:
            raise TypeError("receipt exceeds maximum depth")
        self.count += 1
        if self.count > MAX_PAYLOAD_ITEMS:
            raise TypeError("receipt exceeds maximum item count")
        if (key and not _KEY_DIGEST.fullmatch(key) and is_secret_key(key)):
            return REDACTED
        if policy is _Policy.PUBLIC:
            if value is None:
                return None
            if not isinstance(value, str):
                raise TypeError("public receipt field must be a string")
            if str.__len__(value) > MAX_STRING_LENGTH:
                raise TypeError("string exceeds maximum length")
            return _public_digest(value)
        if policy is _Policy.PLAIN:
            if isinstance(value, str):
                if type(value) is not str or str.__len__(value) > MAX_STRING_LENGTH:
                    raise TypeError("plain receipt field must be an exact string")
                return value
            if value is None or isinstance(value, bool) or isinstance(value, int):
                return value
            raise TypeError("plain receipt field has an invalid type")
        if policy is _Policy.MAPPING:
            if not isinstance(value, Mapping):
                raise TypeError("receipt field must be a mapping")
            return self._mapping(value, schema=None, depth=depth)
        if isinstance(policy, Mapping):
            if not isinstance(value, Mapping):
                raise TypeError("receipt field must be a mapping")
            return self._mapping(value, schema=policy, depth=depth)
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, str):
            if str.__len__(value) > MAX_STRING_LENGTH:
                raise TypeError("string exceeds maximum length")
            return _public_digest(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise TypeError("non-finite numbers are not JSON-safe")
            return value
        if isinstance(value, Mapping):
            return self._mapping(value, schema=schema, depth=depth)
        if isinstance(value, (list, tuple)):
            return [self.sanitize(item, depth=depth + 1) for item in value]
        raise TypeError("value is not JSON-safe")

    def _mapping(self, value: Mapping, *, schema, depth: int) -> dict:
        result = {}
        vocabulary = schema or {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise TypeError("mapping keys must be strings")
            if str.__len__(raw_key) > MAX_STRING_LENGTH:
                raise TypeError("mapping key exceeds maximum length")
            validate_durable_key(raw_key)
            known = type(raw_key) is str and raw_key in vocabulary
            safe_key = raw_key if known else digest_error_detail_key(raw_key)
            if safe_key in result:
                raise TypeError("mapping keys collide after sanitization")
            child_policy = vocabulary[raw_key] if known else None
            result[safe_key] = self.sanitize(
                item, schema=None, policy=child_policy, key=raw_key, depth=depth + 1,
            )
        return result


def _sanitize_receipt(receipt: Mapping[str, object], *, schema=None) -> SafeReceipt:
    if not isinstance(receipt, Mapping):
        raise TypeError("receipt must be a mapping")
    safe = _ReceiptSanitizer().sanitize(receipt, schema=schema)
    return _make_safe_receipt(safe)


def _encode_safe(receipt: SafeReceipt) -> bytes:
    return (json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def encode_receipt(receipt: Mapping[str, object]) -> bytes:
    try:
        safe = receipt if isinstance(receipt, SafeReceipt) else _sanitize_receipt(receipt)
        return _encode_safe(safe)
    except (TypeError, ValueError) as exc:
        raise UnsafePayloadError(ErrorMessage.RECEIPT_NON_JSON_SAFE) from exc


def evidence_receipt(run_id: str, evidence_type: str, reference: str, *,
                     metadata: Optional[Mapping[str, object]] = None) -> SafeReceipt:
    try:
        if not all(type(value) is str for value in (run_id, evidence_type, reference)):
            raise TypeError("receipt caller fields must be strings")
        if metadata is not None and not isinstance(metadata, Mapping):
            raise TypeError("receipt metadata must be a mapping")
        normalized_reference = normalize_evidence_reference(reference)
        safe = _sanitize_receipt({
            ReceiptField.SCHEMA_VERSION.value: 1,
            ReceiptField.RECEIPT_TYPE.value: "evidence",
            ReceiptField.RUN_ID.value: run_id,
            ReceiptField.EVIDENCE_TYPE.value: evidence_type,
            ReceiptField.REFERENCE.value: normalized_reference,
            ReceiptField.METADATA.value: dict(metadata or {}),
        }, schema=_EVIDENCE_RECEIPT_SCHEMA)
        complete = dict(safe)
        complete[ReceiptField.DIGEST.value] = "sha256:" + hashlib.sha256(_encode_safe(safe)).hexdigest()
        return _make_safe_receipt(complete)
    except (TypeError, ValueError) as exc:
        raise UnsafePayloadError(ErrorMessage.EVIDENCE_RECEIPT_UNSAFE) from exc


def transition_receipt(event: WorkflowEvent, state_digest: str) -> SafeReceipt:
    try:
        if not isinstance(event, WorkflowEvent):
            raise TypeError("transition receipt requires a workflow event")
        if type(state_digest) is not str or not _STATE_DIGEST.fullmatch(state_digest):
            raise ValueError("state digest must be canonical sha256")
        return _sanitize_receipt({
            ReceiptField.SCHEMA_VERSION.value: 1,
            ReceiptField.RECEIPT_TYPE.value: "transition",
            ReceiptField.EVENT.value: event.to_dict(),
            ReceiptField.STATE_DIGEST.value: state_digest,
        }, schema=_TRANSITION_RECEIPT_SCHEMA)
    except (TypeError, ValueError) as exc:
        raise UnsafePayloadError(ErrorMessage.RECEIPT_NON_JSON_SAFE) from exc


__all__ = [
    "EVIDENCE_RECEIPT_FIELDS", "TRANSITION_RECEIPT_FIELDS", "ReceiptField",
    "SafeReceipt", "encode_receipt", "evidence_receipt", "transition_receipt",
]
