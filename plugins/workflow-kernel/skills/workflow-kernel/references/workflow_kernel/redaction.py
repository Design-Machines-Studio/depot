"""Secret-safe conversion for untrusted workflow data."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


REDACTED = "[REDACTED]"
_SECRET_PARTS = (
    "token", "key", "secret", "password", "authorization", "cookie", "dsn",
    "environment_value", "environment-value", "env_value",
)


def is_secret_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(part.replace("-", "_") in normalized for part in _SECRET_PARTS)


def redact(value: Any, *, _key: str = "") -> Any:
    """Return a JSON-safe deep copy with sensitive keyed values removed."""
    if _key and is_secret_key(_key):
        return REDACTED
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("non-finite numbers are not JSON-safe")
        return value
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("mapping keys must be strings")
            result[key] = redact(item, _key=key)
        return result
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    raise TypeError("value is not JSON-safe")
