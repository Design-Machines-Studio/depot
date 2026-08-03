"""Closed schema-v1 contract for broker-owned external provider dispatch.

This module is deliberately transport-neutral.  It validates and canonicalizes
documents, freezes framing and signed projections, and supplies a production-
ineligible fake for offline consumers.  It never opens a socket or contacts a
provider.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = 1
PROTOCOL = "workflow-authority-provider-dispatch-v1"
MAPPING = "openrouter-chat-v1"
OPERATION_FAMILY = "external_provider_dispatch"
SUBSTRATE_AUTHORITY = "not_asserted"
PRODUCTION_INELIGIBLE_DOMAIN = "fixture.workflow-authority.invalid"
MAX_FRAME_BYTES = 1_048_576
MAX_REQUEST_BYTES = 8_388_608
MAX_RESPONSE_BYTES = 8_388_608
MAX_PARTS = 256
MAX_DEPTH = 16
MAX_PENDING_PER_PEER = 4
MAX_PENDING_PER_REPOSITORY = 16
MAX_PENDING_PER_DAEMON = 64

EXIT_VERIFIED = 0
EXIT_INVALID = 2
EXIT_AUTHORITY_UNAVAILABLE = 70
EXIT_AUTHORIZATION_DECLINED = 71
EXIT_DISCLOSURE_DECLINED = 72
EXIT_PROVIDER_FAILURE = 73
EXIT_UNKNOWN = 74
EXIT_RESULT_VERIFICATION = 75
EXIT_CODES = frozenset({0, 2, 70, 71, 72, 73, 74, 75})

ERROR_CODES = frozenset({
    "frame_too_large", "part_frame_mismatch", "exchange_state_invalid",
    "content_order_invalid", "terminal_binding_invalid",
    "consent_connection_invalid", "exchange_trailing_data",
    "invalid_document", "noncanonical_document", "bounds_exceeded",
    "authorization_declined", "authorization_expired", "authorization_replayed",
    "disclosure_declined", "authority_unavailable", "provider_failure",
    "provider_result_unknown", "result_verification_failed", "rate_limited",
})

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SIGNATURE = re.compile(r"ed25519:[A-Za-z0-9_-]{86}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_ROLE = frozenset({"system", "user"})
_REQUEST_FIELDS = frozenset({
    "schema_version", "protocol", "mapping", "operation_family",
    "substrate_authority", "destination", "method", "path", "models",
    "parts", "scope", "authority", "limits",
})
_PART_FIELDS = frozenset({"role", "content_length", "content_sha256"})
_SCOPE_FIELDS = frozenset({
    "repository", "run_id", "lane", "candidate", "workload",
})
_AUTHORITY_FIELDS = frozenset({
    "daemon_build_sha256", "scanner_build_sha256", "policy_sha256",
    "nonce", "sequence", "boot_id", "session_id", "connection_nonce_sha256",
    "issued_at", "expires_at",
})
_LIMIT_FIELDS = frozenset({
    "max_request_bytes", "max_response_bytes", "max_parts",
    "max_pending_per_peer", "max_pending_per_repository", "max_pending_per_daemon",
})
_CHALLENGE_FIELDS = frozenset({
    "schema_version", "protocol", "mapping", "operation_family",
    "substrate_authority", "transaction_id", "connection_nonce_sha256",
    "peer_uid", "peer_pid", "request_body_sha256", "destination", "method",
    "path", "models", "scope", "daemon_build_sha256", "scanner_build_sha256",
    "policy_sha256", "nonce", "sequence", "boot_id", "session_id", "issued_at",
    "expires_at", "limits", "result_public_key",
})
_ACK_FIELDS = frozenset({"schema_version", "protocol", "type", "challenge_sha256"})
_RESULT_FIELDS = frozenset({
    "schema_version", "protocol", "operation_family", "substrate_authority",
    "outcome", "exit_code", "request_body_sha256", "response_sha256",
    "response_length", "part_count", "models", "selected_model", "provider",
    "scope", "sequence", "issued_at", "completed_at", "challenge_sha256",
    "fido_assertion_sha256", "result_public_key_sha256", "cleanup", "signature",
})
_STATUS_FIELDS = frozenset({
    "schema_version", "protocol", "production_ready", "fixture_domain",
    "socket_root_source", "pending", "limits", "last_error_code",
})
_EXCHANGE_FIELDS = frozenset({
    "schema_version", "protocol", "state", "request", "request_body_sha256",
    "challenge", "consent_ack", "result", "safe_error", "consumed",
    "network_attempted", "response_retrievable",
})
_CLEANUP_FIELDS = frozenset({"reservation", "connection", "content_buffer"})

FROZEN_EXCHANGE = {
    "transport": "unix-sock-stream-single-connection",
    "request_header": "u32be-canonical-json",
    "request_parts": "ordered-u64be-exact-utf8",
    "server_control": "u32be-canonical-json",
    "response_content": "u64be-raw-bytes",
    "terminal": "u32be-canonical-signed-json",
    "safe_error": "u32be-canonical-json-no-content",
    "ancillary_descriptors": "reject",
    "transaction_id_capability": False,
    "resume": False,
    "retrieve": False,
    "fd3": {
        "required": True, "kind": "inherited-anonymous-pipe", "verify": "fstat",
        "single_write_after_verification": True,
        "reject": ["absent", "regular-file", "path-selected-socket", "reused"],
    },
    "stdout": "one-content-free-terminal-json",
    "client_response_buffer_bytes": MAX_RESPONSE_BYTES,
}

FROZEN_TRUST_CHAIN = {
    "registry": "fixed-root-owned-fido-public-registry",
    "daemon_build_trust": "fixed-root-owned-build-record",
    "user_presence": True,
    "user_verification": "authenticator-internal",
    "host_pin": "unavailable",
    "assertion_binds": ["exact-challenge", "ephemeral-result-public-key"],
    "terminal_verifies_under": "ephemeral-result-public-key",
    "fixture_domain": PRODUCTION_INELIGIBLE_DOMAIN,
    "downgrades_rejected": ["authority-envelope-v1", "hmac", "receipt-key"],
}


class ProviderDispatchError(ValueError):
    """A content-free, stable public contract failure."""

    def __init__(self, code: str):
        safe = code if code in ERROR_CODES else "invalid_document"
        super().__init__(safe)
        self.code = safe


def _fail(code: str = "invalid_document") -> None:
    raise ProviderDispatchError(code)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail()
        result[key] = value
    return result


def _reject_number(_value: str) -> None:
    _fail("noncanonical_document")


def _depth_and_items(value: Any, depth: int = 0) -> int:
    if depth > MAX_DEPTH:
        _fail("bounds_exceeded")
    if type(value) is dict:
        return 1 + sum(_depth_and_items(item, depth + 1) for item in value.values())
    if type(value) is list:
        return 1 + sum(_depth_and_items(item, depth + 1) for item in value)
    return 1


def canonical_json(value: Any) -> bytes:
    """Return the cross-language canonical compact JSON representation."""
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, allow_nan=False, sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        _fail()
    return encoded


def parse_canonical_json(raw: bytes, *, limit: int = MAX_FRAME_BYTES) -> Any:
    """Parse canonical JSON after byte, UTF-8, duplicate, depth and number checks."""
    if type(raw) is not bytes or len(raw) > limit:
        _fail("frame_too_large")
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text, object_pairs_hook=_pairs, parse_float=_reject_number,
            parse_constant=_reject_number,
        )
    except ProviderDispatchError:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _fail()
    _depth_and_items(value)
    if canonical_json(value) != raw:
        _fail("noncanonical_document")
    return value


def _object(value: Any, fields: frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != fields:
        _fail()
    return value


def _string(value: Any, *, pattern: re.Pattern[str] = _ID) -> str:
    if type(value) is not str or not pattern.fullmatch(value):
        _fail()
    return value


def _plain_string(value: Any, maximum: int = 512) -> str:
    if type(value) is not str or not value or len(value.encode("utf-8")) > maximum:
        _fail()
    return value


def _digest(value: Any) -> str:
    return _string(value, pattern=_DIGEST)


def _integer(value: Any, minimum: int = 0, maximum: int = 2**63 - 1) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        _fail()
    return value


def _strings(value: Any, *, maximum: int = MAX_PARTS) -> list[str]:
    if type(value) is not list or not value or len(value) > maximum:
        _fail("bounds_exceeded")
    return [_string(item) for item in value]


def _fixed(document: Mapping[str, Any]) -> None:
    if document["schema_version"] != SCHEMA_VERSION:
        _fail()
    if document["protocol"] != PROTOCOL:
        _fail()


def _scope(value: Any) -> dict[str, Any]:
    scope = _object(value, _SCOPE_FIELDS)
    for field in _SCOPE_FIELDS:
        _string(scope[field])
    return scope


def _limits(value: Any) -> dict[str, Any]:
    limits = _object(value, _LIMIT_FIELDS)
    expected = {
        "max_request_bytes": MAX_REQUEST_BYTES,
        "max_response_bytes": MAX_RESPONSE_BYTES,
        "max_parts": MAX_PARTS,
        "max_pending_per_peer": MAX_PENDING_PER_PEER,
        "max_pending_per_repository": MAX_PENDING_PER_REPOSITORY,
        "max_pending_per_daemon": MAX_PENDING_PER_DAEMON,
    }
    if limits != expected:
        _fail()
    return limits


def validate_request(document: Any, part_bytes: Sequence[bytes] | None = None) -> dict[str, Any]:
    request = _object(document, _REQUEST_FIELDS)
    _fixed(request)
    if (
        request["mapping"] != MAPPING
        or request["operation_family"] != OPERATION_FAMILY
        or request["substrate_authority"] != SUBSTRATE_AUTHORITY
        or request["destination"] != "https://openrouter.ai"
        or request["method"] != "POST"
        or request["path"] != "/api/v1/chat/completions"
    ):
        _fail()
    _strings(request["models"])
    if len(set(request["models"])) != len(request["models"]):
        _fail("content_order_invalid")
    parts = request["parts"]
    if type(parts) is not list or not parts or len(parts) > MAX_PARTS:
        _fail("bounds_exceeded")
    total = 0
    for index, part in enumerate(parts):
        item = _object(part, _PART_FIELDS)
        if item["role"] not in _ROLE:
            _fail()
        length = _integer(item["content_length"], 0, MAX_FRAME_BYTES)
        _digest(item["content_sha256"])
        total += length
        if part_bytes is not None:
            if index >= len(part_bytes) or type(part_bytes[index]) is not bytes:
                _fail("part_frame_mismatch")
            raw = part_bytes[index]
            try:
                raw.decode("utf-8", errors="strict")
            except UnicodeError:
                _fail("part_frame_mismatch")
            if length != len(raw) or item["content_sha256"] != sha256(raw):
                _fail("part_frame_mismatch")
    if part_bytes is not None and len(part_bytes) != len(parts):
        _fail("part_frame_mismatch")
    if total > MAX_REQUEST_BYTES:
        _fail("bounds_exceeded")
    _scope(request["scope"])
    authority = _object(request["authority"], _AUTHORITY_FIELDS)
    for field in ("daemon_build_sha256", "scanner_build_sha256", "policy_sha256", "connection_nonce_sha256"):
        _digest(authority[field])
    for field in ("nonce", "boot_id", "session_id"):
        _string(authority[field])
    _integer(authority["sequence"], 1)
    _string(authority["issued_at"], pattern=_TIME)
    _string(authority["expires_at"], pattern=_TIME)
    if authority["issued_at"] >= authority["expires_at"]:
        _fail("authorization_expired")
    _limits(request["limits"])
    return request


def build_openrouter_body(request: Mapping[str, Any], part_bytes: Sequence[bytes]) -> bytes:
    """Build the exact compact openrouter-chat-v1 body without text normalization."""
    validate_request(request, part_bytes)
    messages = []
    for part, raw in zip(request["parts"], part_bytes, strict=True):
        messages.append({"role": part["role"], "content": raw.decode("utf-8")})
    body = canonical_json({"messages": messages, "models": request["models"]})
    if len(body) > MAX_REQUEST_BYTES:
        _fail("bounds_exceeded")
    return body


def validate_challenge(document: Any) -> dict[str, Any]:
    challenge = _object(document, _CHALLENGE_FIELDS)
    _fixed(challenge)
    if challenge["mapping"] != MAPPING or challenge["operation_family"] != OPERATION_FAMILY or challenge["substrate_authority"] != SUBSTRATE_AUTHORITY:
        _fail()
    for field in ("transaction_id", "nonce", "boot_id", "session_id", "result_public_key"):
        _string(challenge[field])
    for field in ("destination", "method", "path"):
        _plain_string(challenge[field])
    for field in ("connection_nonce_sha256", "request_body_sha256", "daemon_build_sha256", "scanner_build_sha256", "policy_sha256"):
        _digest(challenge[field])
    _integer(challenge["peer_uid"])
    _integer(challenge["peer_pid"], 1)
    _integer(challenge["sequence"], 1)
    _strings(challenge["models"])
    _scope(challenge["scope"])
    _limits(challenge["limits"])
    _string(challenge["issued_at"], pattern=_TIME)
    _string(challenge["expires_at"], pattern=_TIME)
    if challenge["issued_at"] >= challenge["expires_at"]:
        _fail("authorization_expired")
    return challenge


def validate_consent_ack(document: Any) -> dict[str, Any]:
    ack = _object(document, _ACK_FIELDS)
    _fixed(ack)
    if ack["type"] != "consent_ack":
        _fail("consent_connection_invalid")
    _digest(ack["challenge_sha256"])
    return ack


def validate_result(document: Any) -> dict[str, Any]:
    result = _object(document, _RESULT_FIELDS)
    _fixed(result)
    if result["operation_family"] != OPERATION_FAMILY or result["substrate_authority"] != SUBSTRATE_AUTHORITY:
        _fail()
    if result["outcome"] not in {"verified", "provider_failure", "unknown"}:
        _fail()
    if result["exit_code"] not in EXIT_CODES:
        _fail()
    if result["exit_code"] != {
        "verified": EXIT_VERIFIED,
        "provider_failure": EXIT_PROVIDER_FAILURE,
        "unknown": EXIT_UNKNOWN,
    }[result["outcome"]]:
        _fail("terminal_binding_invalid")
    for field in ("request_body_sha256", "response_sha256", "challenge_sha256", "fido_assertion_sha256", "result_public_key_sha256"):
        _digest(result[field])
    _integer(result["response_length"], 0, MAX_RESPONSE_BYTES)
    _integer(result["part_count"], 1, MAX_PARTS)
    _strings(result["models"])
    for field in ("selected_model", "provider"):
        _string(result[field])
    _string(result["signature"], pattern=_SIGNATURE)
    _scope(result["scope"])
    _integer(result["sequence"], 1)
    _string(result["issued_at"], pattern=_TIME)
    _string(result["completed_at"], pattern=_TIME)
    cleanup = _object(result["cleanup"], _CLEANUP_FIELDS)
    if any(value not in {"consumed", "closed", "discarded"} for value in cleanup.values()):
        _fail()
    return result


def validate_status(document: Any) -> dict[str, Any]:
    status = _object(document, _STATUS_FIELDS)
    _fixed(status)
    if type(status["production_ready"]) is not bool or status["production_ready"]:
        _fail()
    if status["fixture_domain"] != PRODUCTION_INELIGIBLE_DOMAIN or status["socket_root_source"] != "injected-test-only":
        _fail()
    _integer(status["pending"], 0, MAX_PENDING_PER_DAEMON)
    _limits(status["limits"])
    if status["last_error_code"] is not None and status["last_error_code"] not in ERROR_CODES:
        _fail()
    return status


def validate_exchange(document: Any) -> dict[str, Any]:
    exchange = _object(document, _EXCHANGE_FIELDS)
    _fixed(exchange)
    if exchange["state"] not in {"reserved", "challenged", "authorized", "sent", "terminal", "tombstone"}:
        _fail("exchange_state_invalid")
    validate_request(exchange["request"])
    _digest(exchange["request_body_sha256"])
    if exchange["challenge"] is not None:
        validate_challenge(exchange["challenge"])
    if exchange["consent_ack"] is not None:
        validate_consent_ack(exchange["consent_ack"])
    if exchange["result"] is not None:
        validate_result(exchange["result"])
    if exchange["safe_error"] is not None and exchange["safe_error"] not in ERROR_CODES:
        _fail()
    for field in ("consumed", "network_attempted", "response_retrievable"):
        if type(exchange[field]) is not bool:
            _fail()
    if exchange["response_retrievable"]:
        _fail("exchange_state_invalid")
    return exchange


def frame32(payload: bytes) -> bytes:
    if type(payload) is not bytes or len(payload) > MAX_FRAME_BYTES:
        _fail("frame_too_large")
    return struct.pack(">I", len(payload)) + payload


def frame64(payload: bytes, *, limit: int = MAX_RESPONSE_BYTES) -> bytes:
    if type(payload) is not bytes or len(payload) > limit:
        _fail("frame_too_large")
    return struct.pack(">Q", len(payload)) + payload


def encode_request(request: Mapping[str, Any], part_bytes: Sequence[bytes]) -> bytes:
    validate_request(request, part_bytes)
    return frame32(canonical_json(request)) + b"".join(frame64(part, limit=MAX_FRAME_BYTES) for part in part_bytes)


def signature_input(kind: str, document: Mapping[str, Any]) -> bytes:
    """Freeze Go-compatible domain-separated inputs; no auth-mode selector exists."""
    if kind == "challenge":
        validate_challenge(document)
        projection = document
    elif kind == "terminal":
        validate_result(document)
        projection = {key: value for key, value in document.items() if key != "signature"}
    else:
        _fail()
    return b"workflow-authority\x00provider-dispatch-v1\x00" + kind.encode("ascii") + b"\x00" + canonical_json(projection)


def validate_authority_binding(
    request: Mapping[str, Any], body: bytes, challenge: Mapping[str, Any],
    consent_ack: Mapping[str, Any],
) -> None:
    """Reject any substitution between reserved request and FIDO challenge."""
    validate_request(request)
    validate_challenge(challenge)
    validate_consent_ack(consent_ack)
    authority = request["authority"]
    expected = {
        "mapping": request["mapping"], "operation_family": request["operation_family"],
        "substrate_authority": request["substrate_authority"],
        "destination": request["destination"], "method": request["method"],
        "path": request["path"], "models": request["models"], "scope": request["scope"],
        "request_body_sha256": sha256(body),
        "connection_nonce_sha256": authority["connection_nonce_sha256"],
        "daemon_build_sha256": authority["daemon_build_sha256"],
        "scanner_build_sha256": authority["scanner_build_sha256"],
        "policy_sha256": authority["policy_sha256"], "nonce": authority["nonce"],
        "sequence": authority["sequence"], "boot_id": authority["boot_id"],
        "session_id": authority["session_id"], "issued_at": authority["issued_at"],
        "expires_at": authority["expires_at"], "limits": request["limits"],
    }
    if any(challenge[field] != value for field, value in expected.items()):
        _fail("terminal_binding_invalid")
    if consent_ack["challenge_sha256"] != sha256(canonical_json(challenge)):
        _fail("consent_connection_invalid")


def verify_terminal_result(
    request: Mapping[str, Any], challenge: Mapping[str, Any],
    response: bytes, result: Mapping[str, Any],
) -> None:
    """Verify content-free terminal binding before fd-3 delivery."""
    validate_request(request)
    validate_challenge(challenge)
    validate_result(result)
    if type(response) is not bytes or len(response) > MAX_RESPONSE_BYTES:
        _fail("frame_too_large")
    checks = (
        result["request_body_sha256"] == challenge["request_body_sha256"],
        result["response_sha256"] == sha256(response),
        result["response_length"] == len(response),
        result["part_count"] == len(request["parts"]),
        result["models"] == request["models"],
        result["scope"] == request["scope"],
        result["sequence"] == request["authority"]["sequence"],
        result["challenge_sha256"] == sha256(canonical_json(challenge)),
        result["result_public_key_sha256"] == sha256(challenge["result_public_key"].encode("utf-8")),
    )
    if not all(checks):
        _fail("terminal_binding_invalid")


def sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class FakeBroker:
    """Offline fixture only; cannot bind or report production readiness."""

    socket_root: str
    fixture_domain: str = PRODUCTION_INELIGIBLE_DOMAIN

    def __post_init__(self) -> None:
        if type(self.socket_root) is not str or not self.socket_root.startswith("/tmp/"):
            _fail()
        if self.fixture_domain != PRODUCTION_INELIGIBLE_DOMAIN:
            _fail()

    def status(self, last_error_code: str | None = None) -> dict[str, Any]:
        status = {
            "schema_version": 1, "protocol": PROTOCOL,
            "production_ready": False, "fixture_domain": self.fixture_domain,
            "socket_root_source": "injected-test-only", "pending": 0,
            "limits": {
                "max_request_bytes": MAX_REQUEST_BYTES,
                "max_response_bytes": MAX_RESPONSE_BYTES, "max_parts": MAX_PARTS,
                "max_pending_per_peer": MAX_PENDING_PER_PEER,
                "max_pending_per_repository": MAX_PENDING_PER_REPOSITORY,
                "max_pending_per_daemon": MAX_PENDING_PER_DAEMON,
            },
            "last_error_code": last_error_code,
        }
        return validate_status(status)

    def production_ready(self) -> bool:
        return False

    def complete_exchange(
        self, request: Mapping[str, Any], parts: Sequence[bytes],
        challenge: Mapping[str, Any], consent_ack: Mapping[str, Any],
        response: bytes, result: Mapping[str, Any],
    ) -> bytes:
        """Return a deterministic fixture transcript without opening a socket."""
        body = build_openrouter_body(request, parts)
        validate_authority_binding(request, body, challenge, consent_ack)
        verify_terminal_result(request, challenge, response, result)
        return (
            encode_request(request, parts)
            + frame32(canonical_json(challenge))
            + frame32(canonical_json(consent_ack))
            + frame64(response)
            + frame32(canonical_json(result))
        )
