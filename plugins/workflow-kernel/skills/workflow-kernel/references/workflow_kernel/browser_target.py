"""Dependency-free browser target and viewport validation primitives."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import unquote, urlsplit

from .model import invalid_policy


VIEWPORT_DIMENSION_PATTERN = (
    r"(?:[1-9][0-9]{1,3}|1[0-5][0-9]{3}|16[0-2][0-9]{2}|"
    r"163[0-7][0-9]|1638[0-4])"
)
VIEWPORT_PATTERN = VIEWPORT_DIMENSION_PATTERN + "x" + VIEWPORT_DIMENSION_PATTERN
_VIEWPORT = re.compile(
    "(" + VIEWPORT_DIMENSION_PATTERN + ")x("
    + VIEWPORT_DIMENSION_PATTERN + r")\Z"
)
_CREDENTIAL_VALUE = re.compile(
    r"(?:sk-|gh[pousr]_|xox[baprs]-|bearer\s)", re.IGNORECASE | re.ASCII,
)
_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_PERCENT_BYTE = re.compile(r"%([0-9A-Fa-f]{2})")
_UNRESERVED_BYTES = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)


def _invalid(reason="invalid_verification_declaration"):
    raise invalid_policy(reason)


def _unsafe_route_character(character):
    codepoint = ord(character)
    return codepoint < 32 or codepoint == 127 or 0xD800 <= codepoint <= 0xDFFF


def validate_viewport(value):
    if type(value) is not str:
        _invalid()
    match = _VIEWPORT.fullmatch(value)
    if match is None or any(int(item) > 16_384 for item in match.groups()):
        _invalid()
    return value


def _validate_route(route):
    if (
        type(route) is not str or len(route) > 2_048
        or not route.startswith("/") or route.startswith("//")
        or "?" in route or "#" in route or "\\" in route
        or any(_unsafe_route_character(character) for character in route)
        or _PERCENT_ESCAPE.search(route)
    ):
        _invalid("invalid_verification_target")
    for raw_part in route.split("/"):
        for match in _PERCENT_BYTE.finditer(raw_part):
            byte = int(match.group(1), 16)
            if (
                byte in _UNRESERVED_BYTES or byte < 32 or byte == 127
                or byte in {ord("/"), ord("\\"), ord("%")}
            ):
                _invalid("invalid_verification_target")
        try:
            part = unquote(raw_part, errors="strict")
        except UnicodeError:
            _invalid("invalid_verification_target")
        if (
            part in {".", ".."} or "/" in part or "\\" in part
            or "?" in part or "#" in part
            or any(_unsafe_route_character(character) for character in part)
            or _CREDENTIAL_VALUE.match(part)
        ):
            _invalid("invalid_verification_target")
    return route


def digest_target_route(route):
    _validate_route(route)
    return "sha256:" + hashlib.sha256(route.encode("utf-8")).hexdigest()


def digest_target_origin(origin):
    if type(origin) is not str or not origin or len(origin) > 2_048:
        _invalid("invalid_verification_target")
    if any(_unsafe_route_character(character) for character in origin):
        _invalid("invalid_verification_target")
    try:
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"} or not parsed.netloc
            or parsed.hostname is None or parsed.username is not None
            or parsed.password is not None or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment
        ):
            _invalid("invalid_verification_target")
        port = parsed.port
    except (TypeError, ValueError):
        _invalid("invalid_verification_target")
    host = parsed.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = "[" + host + "]"
    default_port = 80 if parsed.scheme == "http" else 443
    canonical = parsed.scheme + "://" + host
    if port is not None and port != default_port:
        canonical += ":" + str(port)
    try:
        encoded = canonical.encode("utf-8")
    except UnicodeError:
        _invalid("invalid_verification_target")
    return "origin-sha256:" + hashlib.sha256(encoded).hexdigest()
