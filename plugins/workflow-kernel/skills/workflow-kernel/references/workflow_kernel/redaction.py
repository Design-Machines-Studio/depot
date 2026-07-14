"""Secret-safe conversion for untrusted workflow data."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any
from urllib.parse import parse_qsl, urlsplit


REDACTED = "[REDACTED]"
MAX_PAYLOAD_DEPTH = 16
MAX_PAYLOAD_ITEMS = 10_000
MAX_STRING_LENGTH = 65_536
_SECRET_PARTS = (
    "token", "key", "secret", "password", "authorization", "cookie", "dsn",
    "environment_value", "environment-value", "env_value",
)


def is_secret_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(part.replace("-", "_") in normalized for part in _SECRET_PARTS)


def _normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def validate_reference(reference: str) -> str:
    """Reject credential-bearing URLs before they enter durable artifacts."""
    if not isinstance(reference, str) or not reference or len(reference) > MAX_STRING_LENGTH:
        raise ValueError("evidence reference is invalid")
    parsed = urlsplit(reference)
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("evidence reference contains URL credentials")
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        normalized = _normalized_name(key)
        if is_secret_key(normalized) or normalized == "sig" or any(
            part in normalized for part in ("signature", "credential", "auth")
        ):
            raise ValueError("evidence reference contains a sensitive query parameter")
    return reference


def _normalize(value: Any, *, key: str, depth: int, count: list, freeze: bool,
               max_depth: int, max_items: int, max_string_length: int) -> Any:
    if depth > max_depth:
        raise TypeError("payload exceeds maximum depth")
    count[0] += 1
    if count[0] > max_items:
        raise TypeError("payload exceeds maximum item count")
    if key and is_secret_key(key):
        return REDACTED
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        if len(value) > max_string_length:
            raise TypeError("string exceeds maximum length")
        if key.casefold() == "reference":
            validate_reference(value)
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("non-finite numbers are not JSON-safe")
        return value
    if isinstance(value, Mapping):
        result = {}
        for child_key, item in value.items():
            if not isinstance(child_key, str):
                raise TypeError("mapping keys must be strings")
            if len(child_key) > max_string_length:
                raise TypeError("mapping key exceeds maximum length")
            result[child_key] = _normalize(
                item, key=child_key, depth=depth + 1, count=count, freeze=freeze,
                max_depth=max_depth, max_items=max_items, max_string_length=max_string_length,
            )
        return MappingProxyType(result) if freeze else result
    if isinstance(value, (list, tuple)):
        if key.casefold() == "evidence":
            for reference in value:
                validate_reference(reference)
        result = tuple(
            _normalize(item, key="", depth=depth + 1, count=count, freeze=freeze,
                       max_depth=max_depth, max_items=max_items, max_string_length=max_string_length)
            for item in value
        )
        return result if freeze else list(result)
    raise TypeError("value is not JSON-safe")


def redact(value: Any, *, _key: str = "") -> Any:
    """Return a JSON-safe deep copy with sensitive keyed values removed."""
    return _normalize(value, key=_key, depth=0, count=[0], freeze=False,
                      max_depth=MAX_PAYLOAD_DEPTH, max_items=MAX_PAYLOAD_ITEMS,
                      max_string_length=MAX_STRING_LENGTH)


def freeze_json(value: Any, *, max_depth: int = MAX_PAYLOAD_DEPTH,
                max_items: int = MAX_PAYLOAD_ITEMS,
                max_string_length: int = MAX_STRING_LENGTH) -> Any:
    """Return a recursively immutable, redacted, JSON-safe value."""
    return _normalize(value, key="", depth=0, count=[0], freeze=True,
                      max_depth=max_depth, max_items=max_items,
                      max_string_length=max_string_length)


def thaw(value: Any) -> Any:
    """Return ordinary JSON containers from an immutable schema value."""
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw(item) for item in value]
    return value
