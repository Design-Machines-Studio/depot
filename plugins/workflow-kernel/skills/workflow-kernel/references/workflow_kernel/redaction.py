"""Secret-safe conversion for untrusted workflow data."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Callable, Optional, Tuple
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
_WHOLE_URI = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:\S*\Z")
_WHOLE_NETWORK_PATH = re.compile(r"//\S+\Z")
_ISO_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z"
)
_ASCII_LETTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
_SCHEME_CHARACTERS = _ASCII_LETTERS | frozenset("0123456789+.-")
_TRAILING_PUNCTUATION = frozenset(".,;!?\"'")
_OPENING_TO_CLOSING = {"(": ")", "[": "]", "{": "}", "<": ">"}
_CLOSING_PUNCTUATION = frozenset(_OPENING_TO_CLOSING.values())


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
    parse_target = "https:" + reference if reference.startswith("//") else reference
    try:
        parsed = urlsplit(parse_target)
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


def _uri_token_end(value: str, start: int, raw_end: int) -> int:
    """Return the URI end after one balance scan and one reverse index scan."""
    balance = {closing: 0 for closing in _CLOSING_PUNCTUATION}
    for index in range(start, raw_end):
        character = value[index]
        closing = _OPENING_TO_CLOSING.get(character)
        if closing is not None:
            balance[closing] -= 1
        elif character in balance:
            balance[character] += 1

    unmatched = {closing: max(0, count) for closing, count in balance.items()}
    end = raw_end
    while end > start:
        trailing = value[end - 1]
        if trailing in _TRAILING_PUNCTUATION:
            end -= 1
            continue
        if trailing in unmatched and unmatched[trailing] > 0:
            unmatched[trailing] -= 1
            end -= 1
            continue
        break
    return end


def _nonspace_end(value: str, start: int) -> int:
    end = start
    while end < len(value) and not value[end].isspace():
        end += 1
    return end


def _next_uri_shape(value: str, start: int) -> Optional[Tuple[int, int]]:
    """Return the next URI marker while advancing through each character once."""
    index = start
    length = len(value)
    while index < length:
        character = value[index]
        if (character == "/" and index + 2 < length and value[index + 1] == "/"
                and not value[index + 2].isspace()):
            return index, index + 2
        if character in _ASCII_LETTERS:
            token_start = index
            index += 1
            while index < length and value[index] in _SCHEME_CHARACTERS:
                index += 1
            if (index < length and value[index] == ":" and index + 1 < length
                    and not value[index + 1].isspace()):
                return token_start, index + 1
            continue
        index += 1
    return None


def _reject_remaining_uri_shapes(value: str) -> None:
    """Fail closed if normalization leaves any non-content-ID URI shape."""
    index = 0
    while index < len(value):
        shape = _next_uri_shape(value, index)
        if shape is None:
            return
        token_start, shape_end = shape
        raw_end = _nonspace_end(value, shape_end)
        token_end = _uri_token_end(value, token_start, raw_end)
        if not _CONTENT_ID.fullmatch(value[token_start:token_end]):
            raise ValueError("durable string contains an unhandled URI")
        index = raw_end


def _normalize_uri_tokens(value: str) -> str:
    """Normalize embedded URI tokens with forward-only bounded scans."""
    pieces = []
    cursor = 0
    index = 0

    while index < len(value):
        shape = _next_uri_shape(value, index)
        if shape is None:
            break
        token_start, shape_end = shape
        raw_end = _nonspace_end(value, shape_end)
        token_end = _uri_token_end(value, token_start, raw_end)
        token = value[token_start:token_end]
        normalized = token if _CONTENT_ID.fullmatch(token) else normalize_evidence_reference(token)
        pieces.extend((value[cursor:token_start], normalized, value[token_end:raw_end]))
        cursor = raw_end
        index = raw_end

    pieces.append(value[cursor:])
    normalized_value = "".join(pieces)
    _reject_remaining_uri_shapes(normalized_value)
    return normalized_value


def normalize_durable_string(value: str) -> str:
    """Digest supported URIs and reject unsupported ones in durable strings."""
    if _ISO_TIMESTAMP.fullmatch(value):
        return value
    stripped = value.strip()
    if stripped != value and (_CONTENT_ID.fullmatch(stripped) or _WHOLE_URI.fullmatch(stripped)
                              or _WHOLE_NETWORK_PATH.fullmatch(stripped)):
        raise ValueError("standalone URI contains surrounding whitespace")
    if _CONTENT_ID.fullmatch(value):
        return value
    if _WHOLE_URI.fullmatch(value):
        return normalize_evidence_reference(value)
    if _WHOLE_NETWORK_PATH.fullmatch(value):
        return normalize_evidence_reference(value)
    return _normalize_uri_tokens(value)


def validate_durable_key(key: str) -> str:
    """Return an unchanged safe mapping key or reject URI-bearing input."""
    normalized = normalize_durable_string(key)
    if normalized != key:
        raise ValueError("mapping key contains a URI")
    return key


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
            return normalize_durable_string(value)
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
                validate_durable_key(child_key)
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
