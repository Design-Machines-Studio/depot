"""Secret-safe conversion for untrusted workflow data."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Callable
from urllib.parse import urlsplit


REDACTED = "[REDACTED]"
MAX_PAYLOAD_DEPTH = 16
MAX_PAYLOAD_ITEMS = 10_000
MAX_STRING_LENGTH = 65_536
_SECRET_PARTS = (
    "token", "key", "secret", "password", "authorization", "cookie", "dsn",
    "environment_value", "environment-value", "env_value",
)
_CONTENT_ID = re.compile(r"(?:sha256|url-sha256):[0-9a-f]{64}\Z")
_ARTIFACT_SEGMENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*\Z")
_URL_VALUE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S*\Z")


def is_secret_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return any(part.replace("-", "_") in normalized for part in _SECRET_PARTS)


def normalize_evidence_reference(reference: str) -> str:
    """Return one safe artifact ID, relative path, or opaque URL digest."""
    if not isinstance(reference, str) or not reference or len(reference) > MAX_STRING_LENGTH:
        raise ValueError("evidence reference is invalid")
    if "\\" in reference or any(ord(character) < 32 or ord(character) == 127 for character in reference):
        raise ValueError("evidence reference contains ambiguous characters")
    if "?" in reference:
        raise ValueError("evidence reference contains a URL query")
    if "#" in reference:
        raise ValueError("evidence reference contains a URL fragment")
    if _CONTENT_ID.fullmatch(reference):
        return reference
    try:
        parsed = urlsplit(reference)
    except ValueError as exc:
        raise ValueError("evidence reference is invalid") from exc
    if parsed.scheme:
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.hostname is None:
            raise ValueError("evidence reference uses an unsupported URL")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("evidence reference contains URL credentials")
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError("evidence reference contains an invalid URL port") from exc
        return "url-sha256:" + hashlib.sha256(reference.encode("utf-8")).hexdigest()
    if reference.startswith("/"):
        raise ValueError("evidence reference is not a run-relative artifact path")
    segments = reference.split("/")
    if any(not _ARTIFACT_SEGMENT.fullmatch(segment) for segment in segments):
        raise ValueError("evidence reference is not a run-relative artifact path")
    return reference


def normalize_url_value(value: str) -> str:
    """Normalize a standalone URL value while preserving prose and local strings."""
    if _URL_VALUE.fullmatch(value):
        return normalize_evidence_reference(value)
    return value


def _mutable_mapping(value: dict) -> dict:
    return value


def _mutable_sequence(value: tuple) -> list:
    return list(value)


def _frozen_mapping(value: dict) -> MappingProxyType:
    return MappingProxyType(value)


def _frozen_sequence(value: tuple) -> tuple:
    return value


@dataclass
class _Traversal:
    max_depth: int
    max_items: int
    max_string_length: int
    wrap_mapping: Callable[[dict], Any]
    wrap_sequence: Callable[[tuple], Any]
    count: int = 0

    def normalize(self, value: Any, *, key: str = "", depth: int = 0) -> Any:
        if depth > self.max_depth:
            raise TypeError("payload exceeds maximum depth")
        self.count += 1
        if self.count > self.max_items:
            raise TypeError("payload exceeds maximum item count")
        if key and is_secret_key(key):
            return REDACTED
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, str):
            if len(value) > self.max_string_length:
                raise TypeError("string exceeds maximum length")
            if key.casefold() == "reference":
                return normalize_evidence_reference(value)
            return normalize_url_value(value)
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
                if len(child_key) > self.max_string_length:
                    raise TypeError("mapping key exceeds maximum length")
                result[child_key] = self.normalize(item, key=child_key, depth=depth + 1)
            return self.wrap_mapping(result)
        if isinstance(value, (list, tuple)):
            if key.casefold() == "evidence":
                value = tuple(normalize_evidence_reference(reference) for reference in value)
            result = tuple(self.normalize(item, depth=depth + 1) for item in value)
            return self.wrap_sequence(result)
        raise TypeError("value is not JSON-safe")


def redact(value: Any, *, _key: str = "") -> Any:
    """Return a JSON-safe deep copy with sensitive keyed values removed."""
    return _Traversal(MAX_PAYLOAD_DEPTH, MAX_PAYLOAD_ITEMS, MAX_STRING_LENGTH,
                      _mutable_mapping, _mutable_sequence).normalize(value, key=_key)


def freeze_json(value: Any, *, max_depth: int = MAX_PAYLOAD_DEPTH,
                max_items: int = MAX_PAYLOAD_ITEMS,
                max_string_length: int = MAX_STRING_LENGTH) -> Any:
    """Return a recursively immutable, redacted, JSON-safe value."""
    return _Traversal(max_depth, max_items, max_string_length,
                      _frozen_mapping, _frozen_sequence).normalize(value)


def thaw(value: Any) -> Any:
    """Return ordinary JSON containers from an immutable schema value."""
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw(item) for item in value]
    return value
