"""Closed schema-v1 contract for broker-owned external provider dispatch.

This module is deliberately transport-neutral.  It validates and canonicalizes
documents, freezes framing and signed projections, and supplies a production-
ineligible fake for offline consumers.  It never opens a socket or contacts a
provider.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import struct
from datetime import datetime, timezone
from dataclasses import dataclass, field
from types import MappingProxyType
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
_FIXTURE_SIGNATURE = re.compile(r"fixture-rsa-sha256-v1:[0-9a-f]{256}\Z")
_BASE64URL = re.compile(r"[A-Za-z0-9_-]{1,4096}\Z")
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
    "issued_at", "expires_at", "prior_chain_digest",
    "allocation_hello_sha256", "dispatch_proposal_sha256",
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
    "expires_at", "limits", "result_signer", "authority_assertion",
    "prior_chain_digest", "allocation_hello_sha256",
    "dispatch_proposal_sha256",
})
_ACK_FIELDS = frozenset({"schema_version", "protocol", "type", "challenge_sha256"})
_AUTHORITY_HELLO_FIELDS = frozenset({
    "schema_version", "protocol", "type", "daemon_build_sha256",
    "scanner_build_sha256", "policy_sha256", "boot_id", "session_id",
    "sequence", "issued_at", "expires_at", "prior_chain_digest",
    "connection_nonce_sha256", "limits",
})
_ALLOCATION_LIMIT_FIELDS = frozenset({
    "max_request_bytes", "max_response_bytes", "max_parts",
    "max_active_allocations", "allocation_ttl_seconds", "cancellation",
})
_DISPATCH_PROPOSAL_FIELDS = frozenset({
    "schema_version", "protocol", "type", "mapping", "operation_family",
    "substrate_authority", "destination", "method", "path", "models",
    "parts", "scope", "caller_nonce", "authority_hello_sha256",
})
_AUTHORIZATION_PROOF_FIELDS = frozenset({
    "schema_version", "protocol", "type", "challenge_sha256",
    "authority_assertion",
})
_RESULT_FIELDS = frozenset({
    "schema_version", "protocol", "operation_family", "substrate_authority",
    "outcome", "exit_code", "request_body_sha256", "response_sha256",
    "response_length", "part_count", "models", "selected_model", "provider",
    "generation_id", "serving_provider", "usage_sha256", "fallback",
    "scope", "sequence", "issued_at", "completed_at", "challenge_sha256",
    "authority_assertion_sha256", "result_signer_sha256",
    "cleanup", "signature", "prior_chain_digest",
})
_STATUS_FIELDS = frozenset({
    "schema_version", "protocol", "production_ready", "fixture_domain",
    "socket_root_source", "pending", "limits", "last_error_code",
})
_EXCHANGE_FIELDS = frozenset({
    "schema_version", "protocol", "state", "request", "request_body_sha256",
    "challenge", "consent_ack", "authorization_proof", "result", "safe_error",
    "consumed", "network_attempted", "response_retrievable",
})
_SAFE_ERROR_CONTROL_FIELDS = frozenset({
    "schema_version", "protocol", "type", "code", "exit_code", "consumed",
    "network_attempted",
})
_CLEANUP_FIELDS = frozenset({"reservation", "connection", "content_buffer"})
_FIXTURE_ENVELOPE_FIELDS = frozenset({"kind", "domain", "value"})
_FIXTURE_SIGNER_FIELDS = frozenset({"kind", "domain", "public_key"})
_FIDO_FIELDS = frozenset({
    "kind", "credential_id", "authenticator_data", "client_data_json",
    "signature_der", "user_presence", "user_verification",
})
_ES256_SIGNER_FIELDS = frozenset({"kind", "public_key_sec1"})
_ES256_SIGNATURE_FIELDS = frozenset({"kind", "signature_der"})

FROZEN_EXCHANGE = {
    "transport": "unix-sock-stream-single-connection",
    "request_header": "u32be-canonical-json",
    "request_parts": "ordered-u64be-exact-utf8",
    "server_control": "u32be-canonical-json",
    "authorization_proof": "u32be-canonical-json-before-provider-content",
    "response_content": "u64be-raw-bytes-after-authorization-proof",
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

FROZEN_ALLOCATION_LIMITS = MappingProxyType({
    "max_request_bytes": MAX_REQUEST_BYTES,
    "max_response_bytes": MAX_RESPONSE_BYTES,
    "max_parts": MAX_PARTS,
    "max_active_allocations": 1,
    "allocation_ttl_seconds": 120,
    "cancellation": "consume_tombstone",
})

FROZEN_ALLOCATION_EXCHANGE = MappingProxyType({
    "transport": "unix-sock-stream-single-connection",
    "first_frame": "daemon-u32be-canonical-authority_hello",
    "next_frame": "caller-u32be-canonical-dispatch_proposal",
    "request_parts": "caller-ordered-u64be-exact-utf8",
    "allocation_ordering": "required-global-serialized-sequence",
    "endpoint_discovery": "required-fixed-trusted-endpoint-only",
    "ancillary_descriptors": "required-reject",
})

SAFE_ERROR_EXITS = {
    "disclosure_declined": EXIT_DISCLOSURE_DECLINED,
    "authorization_declined": EXIT_AUTHORIZATION_DECLINED,
    "authorization_expired": EXIT_AUTHORIZATION_DECLINED,
    "authorization_replayed": EXIT_AUTHORIZATION_DECLINED,
    "consent_connection_invalid": EXIT_AUTHORIZATION_DECLINED,
    "authority_unavailable": EXIT_AUTHORITY_UNAVAILABLE,
}
SAFE_ERROR_NETWORK_ATTEMPTED = {
    "disclosure_declined": False,
    "authorization_declined": False,
    "authorization_expired": False,
    "authorization_replayed": False,
    "consent_connection_invalid": False,
    "authority_unavailable": False,
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

FIXTURE_ROOT_N = int(
    "73e08fd9e3b795fb174140de9f83b2484e5ba8644364cd6f3b3ba8890071d834"
    "3a3c6a40b1b35f304fc3c4514893effa95dd6f39f5e2efafeedc37e094822c0e"
    "d9022246d4fa52a182b537066bc3d698411f3884ec81aabebc3e3aa982351b57d"
    "53b38559979c9227baba6ef365294abc925ab9e5004884e0cd063329292e69d", 16,
)
FIXTURE_RSA_E = 65537
FIXTURE_ROOT_PUBLIC_KEY = f"fixture-rsa-sha256-v1:{FIXTURE_ROOT_N:0256x}:10001"


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
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError):
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
    _scope(request["scope"])
    authority = _object(request["authority"], _AUTHORITY_FIELDS)
    for field in ("daemon_build_sha256", "scanner_build_sha256", "policy_sha256", "connection_nonce_sha256", "prior_chain_digest", "allocation_hello_sha256", "dispatch_proposal_sha256"):
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
    body = canonical_json({
        "messages": messages, "models": request["models"], "temperature": None,
    })
    if len(body) > MAX_REQUEST_BYTES:
        _fail("bounds_exceeded")
    return body


def _authority_assertion(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        _fail()
    kind = value.get("kind")
    if kind == "fido2-es256":
        assertion = _object(value, _FIDO_FIELDS)
        for field in ("credential_id", "authenticator_data", "client_data_json", "signature_der"):
            _string(assertion[field], pattern=_BASE64URL)
        if assertion["user_presence"] is not True or assertion["user_verification"] is not True:
            _fail("terminal_binding_invalid")
    elif kind == "fixture-rsa-sha256-v1":
        assertion = _object(value, _FIXTURE_ENVELOPE_FIELDS)
        if assertion["domain"] != PRODUCTION_INELIGIBLE_DOMAIN:
            _fail()
        _string(assertion["value"], pattern=_FIXTURE_SIGNATURE)
    else:
        _fail()
    return assertion


def _result_signer(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        _fail()
    kind = value.get("kind")
    if kind == "ephemeral-es256":
        signer = _object(value, _ES256_SIGNER_FIELDS)
        _string(signer["public_key_sec1"], pattern=_BASE64URL)
    elif kind == "fixture-rsa-sha256-v1":
        signer = _object(value, _FIXTURE_SIGNER_FIELDS)
        if signer["domain"] != PRODUCTION_INELIGIBLE_DOMAIN:
            _fail()
        _plain_string(signer["public_key"], 1024)
    else:
        _fail()
    return signer


def _terminal_signature(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        _fail()
    kind = value.get("kind")
    if kind == "es256":
        signature = _object(value, _ES256_SIGNATURE_FIELDS)
        _string(signature["signature_der"], pattern=_BASE64URL)
    elif kind == "fixture-rsa-sha256-v1":
        signature = _object(value, _FIXTURE_ENVELOPE_FIELDS)
        if signature["domain"] != PRODUCTION_INELIGIBLE_DOMAIN:
            _fail()
        _string(signature["value"], pattern=_FIXTURE_SIGNATURE)
    else:
        _fail()
    return signature


def validate_challenge(document: Any) -> dict[str, Any]:
    challenge = _object(document, _CHALLENGE_FIELDS)
    _fixed(challenge)
    if challenge["mapping"] != MAPPING or challenge["operation_family"] != OPERATION_FAMILY or challenge["substrate_authority"] != SUBSTRATE_AUTHORITY:
        _fail()
    for field in ("transaction_id", "nonce", "boot_id", "session_id"):
        _string(challenge[field])
    _result_signer(challenge["result_signer"])
    if challenge["authority_assertion"] is not None:
        _fail("terminal_binding_invalid")
    for field in ("destination", "method", "path"):
        _plain_string(challenge[field])
    for field in ("connection_nonce_sha256", "request_body_sha256", "daemon_build_sha256", "scanner_build_sha256", "policy_sha256", "prior_chain_digest", "allocation_hello_sha256", "dispatch_proposal_sha256"):
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


def validate_authority_hello(
    document: Any, *, now: datetime,
) -> dict[str, Any]:
    """Validate the daemon-first, content-free allocation frame."""
    hello = _object(document, _AUTHORITY_HELLO_FIELDS)
    _fixed(hello)
    if hello["type"] != "authority_hello":
        _fail("exchange_state_invalid")
    for field in (
        "daemon_build_sha256", "scanner_build_sha256", "policy_sha256",
        "prior_chain_digest", "connection_nonce_sha256",
    ):
        _digest(hello[field])
    for field in ("boot_id", "session_id"):
        _string(hello[field])
    _integer(hello["sequence"], 1)
    _string(hello["issued_at"], pattern=_TIME)
    _string(hello["expires_at"], pattern=_TIME)
    limits = _object(hello["limits"], _ALLOCATION_LIMIT_FIELDS)
    if limits != FROZEN_ALLOCATION_LIMITS:
        _fail("bounds_exceeded")
    try:
        issued = datetime.strptime(hello["issued_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        expires = datetime.strptime(hello["expires_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        _fail()
    if expires <= issued or int((expires - issued).total_seconds()) != limits["allocation_ttl_seconds"]:
        _fail("authorization_expired")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        _fail()
    current = now.astimezone(timezone.utc)
    if issued > current:
        _fail()
    if current >= expires:
        _fail("authorization_expired")
    return hello


def validate_dispatch_proposal(
    document: Any, part_bytes: Sequence[bytes] | None = None,
) -> dict[str, Any]:
    """Validate only caller-owned proposal fields and their ordered bytes."""
    proposal = _object(document, _DISPATCH_PROPOSAL_FIELDS)
    _fixed(proposal)
    if (
        proposal["type"] != "dispatch_proposal"
        or proposal["mapping"] != MAPPING
        or proposal["operation_family"] != OPERATION_FAMILY
        or proposal["substrate_authority"] != SUBSTRATE_AUTHORITY
        or proposal["destination"] != "https://openrouter.ai"
        or proposal["method"] != "POST"
        or proposal["path"] != "/api/v1/chat/completions"
    ):
        _fail()
    _string(proposal["caller_nonce"])
    _digest(proposal["authority_hello_sha256"])
    _strings(proposal["models"])
    if len(set(proposal["models"])) != len(proposal["models"]):
        _fail("content_order_invalid")
    _scope(proposal["scope"])
    parts = proposal["parts"]
    if type(parts) is not list or not parts or len(parts) > MAX_PARTS:
        _fail("bounds_exceeded")
    if part_bytes is not None and len(part_bytes) != len(parts):
        _fail("part_frame_mismatch")
    total = 0
    for index, raw_part in enumerate(parts):
        part = _object(raw_part, _PART_FIELDS)
        if part["role"] not in _ROLE:
            _fail()
        length = _integer(part["content_length"], 0, MAX_FRAME_BYTES)
        _digest(part["content_sha256"])
        total += length
        if part_bytes is not None:
            raw = part_bytes[index]
            if type(raw) is not bytes or len(raw) != length or sha256(raw) != part["content_sha256"]:
                _fail("part_frame_mismatch")
            try:
                raw.decode("utf-8", errors="strict")
            except UnicodeError:
                _fail("part_frame_mismatch")
    if total > MAX_REQUEST_BYTES:
        _fail("bounds_exceeded")
    return proposal


def authority_hello_bytes(document: Mapping[str, Any], *, now: datetime) -> bytes:
    return canonical_json(validate_authority_hello(document, now=now))


def dispatch_proposal_bytes(document: Mapping[str, Any], part_bytes: Sequence[bytes]) -> bytes:
    return canonical_json(validate_dispatch_proposal(document, part_bytes))


def bind_allocation_request(
    hello: Mapping[str, Any], proposal: Mapping[str, Any],
    part_bytes: Sequence[bytes], *, now: datetime,
) -> dict[str, Any]:
    """Synthesize closed request v1 without performing transport or allocation."""
    hello_bytes = authority_hello_bytes(hello, now=now)
    if sha256(hello_bytes) != proposal.get("authority_hello_sha256"):
        _fail("terminal_binding_invalid")
    proposal_bytes = dispatch_proposal_bytes(proposal, part_bytes)
    request = {
        "schema_version": SCHEMA_VERSION, "protocol": PROTOCOL,
        "mapping": proposal["mapping"],
        "operation_family": proposal["operation_family"],
        "substrate_authority": proposal["substrate_authority"],
        "destination": proposal["destination"], "method": proposal["method"],
        "path": proposal["path"], "models": list(proposal["models"]),
        "parts": [dict(part) for part in proposal["parts"]],
        "scope": dict(proposal["scope"]),
        "authority": {
            "daemon_build_sha256": hello["daemon_build_sha256"],
            "scanner_build_sha256": hello["scanner_build_sha256"],
            "policy_sha256": hello["policy_sha256"],
            "nonce": proposal["caller_nonce"], "sequence": hello["sequence"],
            "boot_id": hello["boot_id"], "session_id": hello["session_id"],
            "connection_nonce_sha256": hello["connection_nonce_sha256"],
            "issued_at": hello["issued_at"], "expires_at": hello["expires_at"],
            "prior_chain_digest": hello["prior_chain_digest"],
            "allocation_hello_sha256": sha256(hello_bytes),
            "dispatch_proposal_sha256": sha256(proposal_bytes),
        },
        "limits": {
            "max_request_bytes": MAX_REQUEST_BYTES,
            "max_response_bytes": MAX_RESPONSE_BYTES, "max_parts": MAX_PARTS,
            "max_pending_per_peer": MAX_PENDING_PER_PEER,
            "max_pending_per_repository": MAX_PENDING_PER_REPOSITORY,
            "max_pending_per_daemon": MAX_PENDING_PER_DAEMON,
        },
    }
    return validate_request(request, part_bytes)


def validate_authorization_proof(document: Any) -> dict[str, Any]:
    proof = _object(document, _AUTHORIZATION_PROOF_FIELDS)
    _fixed(proof)
    if proof["type"] != "authorization_proof":
        _fail("terminal_binding_invalid")
    _digest(proof["challenge_sha256"])
    _authority_assertion(proof["authority_assertion"])
    return proof


def validate_safe_error_control(document: Any) -> dict[str, Any]:
    control = _object(document, _SAFE_ERROR_CONTROL_FIELDS)
    _fixed(control)
    if control["type"] != "safe_error" or control["code"] not in SAFE_ERROR_EXITS:
        _fail()
    if control["exit_code"] != SAFE_ERROR_EXITS[control["code"]]:
        _fail("terminal_binding_invalid")
    for field in ("consumed", "network_attempted"):
        if type(control[field]) is not bool:
            _fail()
    if not control["consumed"]:
        _fail("terminal_binding_invalid")
    if control["network_attempted"] is not SAFE_ERROR_NETWORK_ATTEMPTED[control["code"]]:
        _fail("terminal_binding_invalid")
    return control


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
    for field in ("request_body_sha256", "response_sha256", "usage_sha256", "challenge_sha256", "authority_assertion_sha256", "result_signer_sha256", "prior_chain_digest"):
        _digest(result[field])
    _integer(result["response_length"], 0, MAX_RESPONSE_BYTES)
    _integer(result["part_count"], 1, MAX_PARTS)
    _strings(result["models"])
    if len(set(result["models"])) != len(result["models"]):
        _fail("content_order_invalid")
    for field in ("selected_model", "provider", "generation_id", "serving_provider"):
        _string(result[field])
    if result["provider"] != "openrouter":
        _fail("terminal_binding_invalid")
    if type(result["fallback"]) is not bool or result["fallback"] != (result["selected_model"] != result["models"][0]):
        _fail("terminal_binding_invalid")
    _terminal_signature(result["signature"])
    _scope(result["scope"])
    _integer(result["sequence"], 1)
    _string(result["issued_at"], pattern=_TIME)
    _string(result["completed_at"], pattern=_TIME)
    cleanup = _object(result["cleanup"], _CLEANUP_FIELDS)
    if cleanup != {"reservation": "consumed", "connection": "closed", "content_buffer": "discarded"}:
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
    if exchange["authorization_proof"] is not None:
        validate_authorization_proof(exchange["authorization_proof"])
    if exchange["result"] is not None:
        validate_result(exchange["result"])
    if exchange["safe_error"] is not None and exchange["safe_error"] not in SAFE_ERROR_EXITS:
        _fail()
    for field in ("consumed", "network_attempted", "response_retrievable"):
        if type(exchange[field]) is not bool:
            _fail()
    if exchange["response_retrievable"]:
        _fail("exchange_state_invalid")
    state = exchange["state"]
    combinations = {
        "reserved": (False, False, False, False, False, False, False),
        "challenged": (True, False, False, False, False, False, False),
        "authorized": (True, True, True, False, False, False, False),
        "sent": (True, True, True, False, False, False, True),
        "terminal": (True, True, True, True, False, True, True),
        "tombstone": (exchange["challenge"] is not None, exchange["consent_ack"] is not None, exchange["authorization_proof"] is not None, False, not exchange["network_attempted"], True, exchange["network_attempted"]),
    }
    actual = (
        exchange["challenge"] is not None, exchange["consent_ack"] is not None,
        exchange["authorization_proof"] is not None, exchange["result"] is not None,
        exchange["safe_error"] is not None, exchange["consumed"],
        exchange["network_attempted"],
    )
    if actual != combinations[state]:
        _fail("exchange_state_invalid")
    challenge = exchange["challenge"]
    request = exchange["request"]
    if challenge is not None:
        authority = request["authority"]
        repeated = (
            exchange["request_body_sha256"] == challenge["request_body_sha256"],
            request["mapping"] == challenge["mapping"],
            request["operation_family"] == challenge["operation_family"],
            request["substrate_authority"] == challenge["substrate_authority"],
            request["destination"] == challenge["destination"],
            request["method"] == challenge["method"], request["path"] == challenge["path"],
            request["models"] == challenge["models"], request["scope"] == challenge["scope"],
            authority["sequence"] == challenge["sequence"],
            authority["nonce"] == challenge["nonce"],
            authority["prior_chain_digest"] == challenge["prior_chain_digest"],
            authority["allocation_hello_sha256"] == challenge["allocation_hello_sha256"],
            authority["dispatch_proposal_sha256"] == challenge["dispatch_proposal_sha256"],
            authority["issued_at"] == challenge["issued_at"],
            authority["expires_at"] == challenge["expires_at"],
        )
        if not all(repeated):
            _fail("terminal_binding_invalid")
        if exchange["consent_ack"] is not None and exchange["consent_ack"]["challenge_sha256"] != sha256(canonical_json(challenge)):
            _fail("consent_connection_invalid")
        proof = exchange["authorization_proof"]
        if proof is not None and proof["challenge_sha256"] != sha256(canonical_json(challenge)):
            _fail("terminal_binding_invalid")
    result = exchange["result"]
    if result is not None:
        proof = exchange["authorization_proof"]
        if challenge is None or not all((
            proof is not None,
            exchange["request_body_sha256"] == result["request_body_sha256"],
            challenge["request_body_sha256"] == result["request_body_sha256"],
            request["models"] == result["models"], request["scope"] == result["scope"],
            request["authority"]["sequence"] == result["sequence"],
            request["authority"]["prior_chain_digest"] == result["prior_chain_digest"],
            request["authority"]["issued_at"] == result["issued_at"],
            result["challenge_sha256"] == sha256(canonical_json(challenge)),
            proof["challenge_sha256"] == sha256(canonical_json(challenge)),
            result["authority_assertion_sha256"] == sha256(canonical_json(proof["authority_assertion"])),
            result["result_signer_sha256"] == sha256(canonical_json(challenge["result_signer"])),
            result["selected_model"] in request["models"], result["provider"] == "openrouter",
            result["fallback"] == (result["selected_model"] != request["models"][0]),
        )):
            _fail("terminal_binding_invalid")
    return exchange


def frame32(payload: bytes) -> bytes:
    if type(payload) is not bytes or len(payload) > MAX_FRAME_BYTES:
        _fail("frame_too_large")
    return struct.pack(">I", len(payload)) + payload


def frame64(payload: bytes, *, limit: int = MAX_RESPONSE_BYTES) -> bytes:
    if type(payload) is not bytes or len(payload) > limit:
        _fail("frame_too_large")
    return struct.pack(">Q", len(payload)) + payload


def encode_safe_error_control(document: Mapping[str, Any]) -> bytes:
    validate_safe_error_control(document)
    return frame32(canonical_json(document))


def decode_safe_error_control(wire: bytes) -> dict[str, Any]:
    if type(wire) is not bytes or len(wire) < 4:
        _fail("frame_too_large")
    length = struct.unpack(">I", wire[:4])[0]
    if length > MAX_FRAME_BYTES or len(wire) != 4 + length:
        _fail("exchange_trailing_data" if len(wire) > 4 + length else "frame_too_large")
    return validate_safe_error_control(parse_canonical_json(wire[4:]))


def encode_request(request: Mapping[str, Any], part_bytes: Sequence[bytes]) -> bytes:
    validate_request(request, part_bytes)
    header = canonical_json(request)
    wire_length = 4 + len(header) + sum(8 + len(part) for part in part_bytes)
    if wire_length > MAX_REQUEST_BYTES:
        _fail("bounds_exceeded")
    return frame32(header) + b"".join(frame64(part, limit=MAX_FRAME_BYTES) for part in part_bytes)


def decode_request(wire: bytes) -> tuple[dict[str, Any], tuple[bytes, ...]]:
    """Independently parse one bounded request frame without trailing data."""
    if type(wire) is not bytes or len(wire) > MAX_REQUEST_BYTES or len(wire) < 4:
        _fail("frame_too_large")
    header_length = struct.unpack(">I", wire[:4])[0]
    if header_length > MAX_FRAME_BYTES or 4 + header_length > len(wire):
        _fail("frame_too_large")
    request = parse_canonical_json(wire[4:4 + header_length])
    offset = 4 + header_length
    parts = []
    if type(request) is not dict or type(request.get("parts")) is not list:
        _fail()
    for _part in request["parts"]:
        if offset + 8 > len(wire):
            _fail("part_frame_mismatch")
        length = struct.unpack(">Q", wire[offset:offset + 8])[0]
        offset += 8
        if length > MAX_FRAME_BYTES or offset + length > len(wire):
            _fail("part_frame_mismatch")
        parts.append(wire[offset:offset + length])
        offset += length
    if offset != len(wire):
        _fail("exchange_trailing_data")
    validate_request(request, parts)
    return request, tuple(parts)


def decode_response(
    wire: bytes, request: Mapping[str, Any], challenge: Mapping[str, Any],
    *, fixture_trust: bool = False, production_verifier=None,
) -> tuple[dict[str, Any], bytes, dict[str, Any]]:
    """Buffer and verify one response/terminal pair before any fd-3 release."""
    if type(wire) is not bytes or len(wire) < 16:
        _fail("part_frame_mismatch")
    proof_length = struct.unpack(">I", wire[:4])[0]
    proof_end = 4 + proof_length
    if proof_length > MAX_FRAME_BYTES or proof_end + 12 > len(wire):
        _fail("frame_too_large")
    proof = validate_authorization_proof(parse_canonical_json(wire[4:proof_end]))
    content_length = struct.unpack(">Q", wire[proof_end:proof_end + 8])[0]
    if content_length > MAX_RESPONSE_BYTES or proof_end + 8 + content_length + 4 > len(wire):
        _fail("frame_too_large")
    content_end = proof_end + 8 + content_length
    content = wire[proof_end + 8:content_end]
    terminal_length = struct.unpack(">I", wire[content_end:content_end + 4])[0]
    terminal_end = content_end + 4 + terminal_length
    if terminal_length > MAX_FRAME_BYTES or terminal_end > len(wire):
        _fail("frame_too_large")
    if terminal_end != len(wire):
        _fail("exchange_trailing_data")
    terminal = parse_canonical_json(wire[content_end + 4:terminal_end])
    verify_terminal_result(
        request, challenge, proof, content, terminal, fixture_trust=fixture_trust,
        production_verifier=production_verifier,
    )
    return proof, content, terminal


def validate_fd3(fd: int, used_descriptors: set[int]) -> None:
    """Accept only unused descriptor 3 backed by an inherited anonymous pipe."""
    if type(fd) is not int or fd != 3 or type(used_descriptors) is not set or fd in used_descriptors:
        _fail("exchange_state_invalid")
    try:
        metadata = os.fstat(fd)
    except OSError:
        _fail("exchange_state_invalid")
    if not stat.S_ISFIFO(metadata.st_mode) or metadata.st_nlink != 0:
        _fail("exchange_state_invalid")


def deliver_verified_fd3(
    fd: int, used_descriptors: set[int], response_wire: bytes,
    request: Mapping[str, Any], challenge: Mapping[str, Any], *,
    fixture_trust: bool = False, production_verifier=None,
) -> dict[str, Any]:
    """Buffer, verify, and write content exactly once to inherited fd 3."""
    validate_fd3(fd, used_descriptors)
    _proof, content, terminal = decode_response(
        response_wire, request, challenge, fixture_trust=fixture_trust,
        production_verifier=production_verifier,
    )
    used_descriptors.add(fd)
    try:
        written = os.write(fd, content)
    except OSError:
        _fail("result_verification_failed")
    if written != len(content):
        _fail("result_verification_failed")
    return terminal


def signature_input(kind: str, document: Mapping[str, Any]) -> bytes:
    """Freeze Go-compatible domain-separated inputs; no auth-mode selector exists."""
    if kind == "challenge":
        validate_challenge(document)
        projection = dict(document)
    elif kind == "terminal":
        validate_result(document)
        projection = {key: value for key, value in document.items() if key != "signature"}
    else:
        _fail()
    return b"workflow-authority\x00provider-dispatch-v1\x00" + kind.encode("ascii") + b"\x00" + canonical_json(projection)


def _fixture_verify(public_key: str, signature: str, payload: bytes) -> bool:
    """Verify domain-marked fixture RSA; never represents production FIDO."""
    try:
        marker, n_hex, e_hex = public_key.split(":")
        signature_marker, signature_hex = signature.split(":")
        if marker != "fixture-rsa-sha256-v1" or signature_marker != marker:
            return False
        n, exponent, signed = int(n_hex, 16), int(e_hex, 16), int(signature_hex, 16)
        expected = int.from_bytes(hashlib.sha256(payload).digest(), "big")
        return len(n_hex) == 256 and exponent == FIXTURE_RSA_E and signed < n and pow(signed, exponent, n) == expected
    except (AttributeError, TypeError, ValueError):
        return False


def verify_fixture_assertion(
    challenge: Mapping[str, Any], assertion: Mapping[str, Any],
) -> None:
    validate_challenge(challenge)
    _authority_assertion(assertion)
    if assertion["kind"] != "fixture-rsa-sha256-v1":
        _fail("terminal_binding_invalid")
    if not _fixture_verify(
        FIXTURE_ROOT_PUBLIC_KEY, assertion["value"],
        signature_input("challenge", challenge),
    ):
        _fail("terminal_binding_invalid")


def validate_authority_binding(
    request: Mapping[str, Any], body: bytes, challenge: Mapping[str, Any],
    consent_ack: Mapping[str, Any],
) -> None:
    """Reject any substitution between reserved request and FIDO challenge."""
    validate_request_challenge_binding(request, challenge)
    if challenge["request_body_sha256"] != sha256(body):
        _fail("terminal_binding_invalid")
    validate_consent_ack(consent_ack)
    if consent_ack["challenge_sha256"] != sha256(canonical_json(challenge)):
        _fail("consent_connection_invalid")


def validate_request_challenge_binding(
    request: Mapping[str, Any], challenge: Mapping[str, Any],
) -> None:
    """Bind every repeated request field before trusting challenge signatures."""
    validate_request(request)
    validate_challenge(challenge)
    authority = request["authority"]
    expected = {
        "mapping": request["mapping"], "operation_family": request["operation_family"],
        "substrate_authority": request["substrate_authority"],
        "destination": request["destination"], "method": request["method"],
        "path": request["path"], "models": request["models"], "scope": request["scope"],
        "connection_nonce_sha256": authority["connection_nonce_sha256"],
        "daemon_build_sha256": authority["daemon_build_sha256"],
        "scanner_build_sha256": authority["scanner_build_sha256"],
        "policy_sha256": authority["policy_sha256"], "nonce": authority["nonce"],
        "sequence": authority["sequence"], "boot_id": authority["boot_id"],
        "session_id": authority["session_id"], "issued_at": authority["issued_at"],
        "expires_at": authority["expires_at"], "limits": request["limits"],
        "prior_chain_digest": authority["prior_chain_digest"],
        "allocation_hello_sha256": authority["allocation_hello_sha256"],
        "dispatch_proposal_sha256": authority["dispatch_proposal_sha256"],
    }
    if any(challenge[field] != value for field, value in expected.items()):
        _fail("terminal_binding_invalid")


def verify_terminal_result(
    request: Mapping[str, Any], challenge: Mapping[str, Any],
    authorization_proof: Mapping[str, Any], response: bytes,
    result: Mapping[str, Any], *, fixture_trust: bool = False,
    production_verifier=None,
) -> None:
    """Verify content-free terminal binding before fd-3 delivery."""
    validate_request_challenge_binding(request, challenge)
    proof = validate_authorization_proof(authorization_proof)
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
        result["result_signer_sha256"] == sha256(canonical_json(challenge["result_signer"])),
        proof["challenge_sha256"] == sha256(canonical_json(challenge)),
        result["authority_assertion_sha256"] == sha256(canonical_json(proof["authority_assertion"])),
        result["prior_chain_digest"] == request["authority"]["prior_chain_digest"],
        result["selected_model"] in request["models"],
        result["provider"] == "openrouter",
        result["fallback"] == (result["selected_model"] != request["models"][0]),
    )
    if not all(checks):
        _fail("terminal_binding_invalid")
    assertion = proof["authority_assertion"]
    assertion_kind = assertion["kind"]
    signer_kind = challenge["result_signer"]["kind"]
    signature_kind = result["signature"]["kind"]
    if assertion_kind == "fixture-rsa-sha256-v1":
        if not fixture_trust or signer_kind != assertion_kind or signature_kind != assertion_kind:
            _fail("terminal_binding_invalid")
        verify_fixture_assertion(challenge, assertion)
        if not _fixture_verify(
            challenge["result_signer"]["public_key"], result["signature"]["value"],
            signature_input("terminal", result),
        ):
            _fail("terminal_binding_invalid")
    else:
        if assertion_kind != "fido2-es256" or signer_kind != "ephemeral-es256" or signature_kind != "es256":
            _fail("terminal_binding_invalid")
        if production_verifier is None:
            _fail("authority_unavailable")
        try:
            verified = production_verifier(
                signature_input("challenge", challenge), assertion,
                signature_input("terminal", result), challenge["result_signer"],
                result["signature"],
            )
        except Exception:
            _fail("authority_unavailable")
        if verified is not True:
            _fail("terminal_binding_invalid")


def sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass
class _Reservation:
    connection_id: str
    peer_uid: int
    repository: str
    request: Mapping[str, Any]
    parts: Sequence[bytes]
    body: bytes
    challenge: Mapping[str, Any]
    state: str = "challenged"
    consumed: bool = False
    network_attempted: bool = False
    safe_error: str | None = None
    consent_ack: Mapping[str, Any] | None = None
    authorization_proof: Mapping[str, Any] | None = None
    result: Mapping[str, Any] | None = None


@dataclass
class FakeBroker:
    """Stateful offline fixture; all authority remains production-ineligible."""

    socket_root: str
    fixture_domain: str = PRODUCTION_INELIGIBLE_DOMAIN
    reservations: dict[str, _Reservation] = field(default_factory=dict, init=False)
    used_transactions: set[str] = field(default_factory=set, init=False)
    fido_attempts: int = field(default=0, init=False)
    network_attempts: int = field(default=0, init=False)
    response_allocations: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if type(self.socket_root) is not str or not self.socket_root.startswith("/tmp/"):
            _fail()
        if self.fixture_domain != PRODUCTION_INELIGIBLE_DOMAIN:
            _fail()

    def status(self, last_error_code: str | None = None) -> dict[str, Any]:
        status = {
            "schema_version": 1, "protocol": PROTOCOL,
            "production_ready": False, "fixture_domain": self.fixture_domain,
            "socket_root_source": "injected-test-only", "pending": self._pending(),
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

    def _pending(self) -> int:
        return sum(not item.consumed for item in self.reservations.values())

    def _owned(self, transaction_id: str, connection_id: str) -> _Reservation:
        reservation = self.reservations.get(transaction_id)
        if reservation is None or transaction_id in self.used_transactions or reservation.consumed:
            _fail("authorization_replayed")
        if reservation.connection_id != connection_id:
            _fail("consent_connection_invalid")
        return reservation

    def _tombstone(self, reservation: _Reservation, code: str | None) -> None:
        reservation.state = "tombstone"
        reservation.consumed = True
        reservation.safe_error = code
        self.used_transactions.add(reservation.challenge["transaction_id"])

    def expire(self, now: str) -> None:
        _string(now, pattern=_TIME)
        for reservation in self.reservations.values():
            if not reservation.consumed and reservation.challenge["expires_at"] <= now:
                self._tombstone(reservation, "authorization_expired")

    def reserve(
        self, connection_id: str, peer_uid: int, request: Mapping[str, Any],
        parts: Sequence[bytes], challenge: Mapping[str, Any], now: str,
    ) -> str:
        """Validate bytes before in-memory fixture state or fixture UV.

        Durable allocation and replay enforcement remain future daemon/WAL
        obligations; this production-ineligible fake proves only process-local
        state transitions.
        """
        _string(connection_id)
        _integer(peer_uid)
        _string(now, pattern=_TIME)
        encode_request(request, parts)  # full wire bound before state allocation
        body = build_openrouter_body(request, parts)
        validate_challenge(challenge)
        if challenge["peer_uid"] != peer_uid:
            _fail("consent_connection_invalid")
        synthetic_ack = {
            "schema_version": 1, "protocol": PROTOCOL, "type": "consent_ack",
            "challenge_sha256": sha256(canonical_json(challenge)),
        }
        validate_authority_binding(request, body, challenge, synthetic_ack)
        self.expire(now)
        if not challenge["issued_at"] <= now < challenge["expires_at"]:
            _fail("authorization_expired")
        transaction_id = challenge["transaction_id"]
        if transaction_id in self.reservations or transaction_id in self.used_transactions:
            _fail("authorization_replayed")
        repository = request["scope"]["repository"]
        active = [item for item in self.reservations.values() if not item.consumed]
        if (
            len(active) >= MAX_PENDING_PER_DAEMON
            or sum(item.peer_uid == peer_uid for item in active) >= MAX_PENDING_PER_PEER
            or sum(item.repository == repository for item in active) >= MAX_PENDING_PER_REPOSITORY
        ):
            _fail("rate_limited")
        self.reservations[transaction_id] = _Reservation(
            connection_id, peer_uid, repository, request, tuple(parts), body, challenge,
        )
        return transaction_id

    def acknowledge(
        self, transaction_id: str, connection_id: str,
        consent_ack: Mapping[str, Any], now: str,
    ) -> None:
        reservation = self._owned(transaction_id, connection_id)
        _string(now, pattern=_TIME)
        if not reservation.challenge["issued_at"] <= now < reservation.challenge["expires_at"]:
            self._tombstone(reservation, "authorization_expired")
            _fail("authorization_expired")
        if reservation.state != "challenged":
            _fail("exchange_state_invalid")
        validate_authority_binding(
            reservation.request, reservation.body, reservation.challenge, consent_ack,
        )
        reservation.consent_ack = consent_ack
        reservation.state = "consented"

    def authorize(
        self, transaction_id: str, connection_id: str,
        authorization_proof: Mapping[str, Any], *, approved: bool = True,
    ) -> None:
        reservation = self._owned(transaction_id, connection_id)
        if reservation.state != "consented":
            _fail("exchange_state_invalid")
        self.fido_attempts += 1
        if not approved:
            self._tombstone(reservation, "authorization_declined")
            _fail("authorization_declined")
        proof = validate_authorization_proof(authorization_proof)
        if proof["challenge_sha256"] != sha256(canonical_json(reservation.challenge)):
            _fail("terminal_binding_invalid")
        verify_fixture_assertion(
            reservation.challenge, proof["authority_assertion"],
        )
        reservation.authorization_proof = proof
        reservation.state = "authorized"

    def mark_sent(self, transaction_id: str, connection_id: str) -> None:
        reservation = self._owned(transaction_id, connection_id)
        if reservation.state != "authorized":
            _fail("exchange_state_invalid")
        if reservation.authorization_proof is None:
            _fail("authority_unavailable")
        reservation.state = "sent"
        reservation.network_attempted = True
        self.network_attempts += 1

    def finish(
        self, transaction_id: str, connection_id: str,
        response: bytes, result: Mapping[str, Any],
    ) -> None:
        reservation = self._owned(transaction_id, connection_id)
        if reservation.state != "sent":
            _fail("exchange_state_invalid")
        if type(response) is not bytes or len(response) > MAX_RESPONSE_BYTES:
            _fail("frame_too_large")
        verify_terminal_result(
            reservation.request, reservation.challenge,
            reservation.authorization_proof,
            response, result,
            fixture_trust=True,
        )
        self.response_allocations += 1
        reservation.result = result
        reservation.state = "terminal"
        reservation.consumed = True
        self.used_transactions.add(transaction_id)

    def disconnect(self, transaction_id: str, connection_id: str) -> None:
        reservation = self._owned(transaction_id, connection_id)
        code = (
            None if reservation.state == "sent"
            else "consent_connection_invalid" if reservation.state == "challenged"
            else "authorization_declined"
        )
        self._tombstone(reservation, code)

    def retrieve(self, transaction_id: str, connection_id: str) -> None:
        """Transactions are never bearer capabilities and content is unretrievable."""
        reservation = self.reservations.get(transaction_id)
        if reservation is not None and reservation.connection_id != connection_id:
            _fail("consent_connection_invalid")
        _fail("authorization_replayed")

    def decline_disclosure(self) -> None:
        """Represent scanner/operator decline before reservation or transport."""
        _fail("disclosure_declined")

    def reserve_for_delivery(
        self, fd: int, used_descriptors: set[int], connection_id: str,
        peer_uid: int, request: Mapping[str, Any], parts: Sequence[bytes],
        challenge: Mapping[str, Any], now: str,
    ) -> str:
        """Validate the path-free delivery seam before allocating reservation state."""
        validate_fd3(fd, used_descriptors)
        return self.reserve(connection_id, peer_uid, request, parts, challenge, now)

    def complete_exchange(
        self, request: Mapping[str, Any], parts: Sequence[bytes],
        challenge: Mapping[str, Any], consent_ack: Mapping[str, Any],
        authorization_proof: Mapping[str, Any], response: bytes,
        result: Mapping[str, Any],
    ) -> bytes:
        """Run the deterministic lifecycle and return its byte transcript."""
        body = build_openrouter_body(request, parts)
        transaction_id = self.reserve(
            "fixture-connection", challenge["peer_uid"], request, parts,
            challenge, challenge["issued_at"],
        )
        self.acknowledge(
            transaction_id, "fixture-connection", consent_ack,
            challenge["issued_at"],
        )
        self.authorize(
            transaction_id, "fixture-connection", authorization_proof,
        )
        self.mark_sent(transaction_id, "fixture-connection")
        self.finish(transaction_id, "fixture-connection", response, result)
        return (
            encode_request(request, parts)
            + frame32(canonical_json(challenge))
            + frame32(canonical_json(consent_ack))
            + frame32(canonical_json(authorization_proof))
            + frame64(response)
            + frame32(canonical_json(result))
        )
