"""Closed authority-provider contracts for repository verification.

The production seam exchanges public, signed documents only.  The native
adapter is injected by the caller; importing this module performs no discovery,
I/O, or process execution.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

from .verification_contract import COMMIT_PATTERN
from .verification_errors import VerificationPlannerError


MAX_STRING_BYTES = 4096
MAX_ARRAY_ITEMS = 256
MAX_FUTURE_SKEW = dt.timedelta(seconds=30)
NONCE_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SIGNATURE_PATTERN = re.compile(r"^p256-sha256:[A-Za-z0-9+/]+={0,2}$")
OPERATIONS = frozenset({
    "approve_profile", "plan_verification", "run_verification",
    "record_result", "provider_attestation", "verify_envelope",
    "substrate_enroll_endpoint", "substrate_prepare", "substrate_inspect",
    "substrate_execute", "substrate_cleanup", "key_enroll", "key_rotate",
    "key_revoke", "status", "doctor",
})
ALGORITHMS = frozenset({"ecdsa-p256-sha256"})
REQUEST_BINDING_KEYS = frozenset({
    "repository_descriptor_id", "repository_scope_digest", "run_id",
    "authorization_event_id", "profile_ref", "profile_digest",
    "authority_digest", "trusted_base_commit", "candidate_commit",
    "candidate_snapshot_digest", "include_worktree", "cadence_boundary",
    "lane_id", "provider", "substrate_digest",
})
KEY_RECORD_KEYS = frozenset({
    "schema_version", "artifact_role", "record_digest", "key_id",
    "algorithm", "public_key_digest", "issuer_identity", "activated_at",
    "revoked_at", "verify_not_before", "verify_not_after",
})
REQUEST_KEYS = frozenset({
    "schema_version", "artifact_role", "operation", "bindings", "nonce",
    "sequence", "key_id", "boot_id", "session_id", "issued_at",
    "expires_at", "document_digest",
})
GRANT_KEYS = frozenset({
    "schema_version", "artifact_role", "authority_mode", "request_digest",
    "key_id", "public_key_digest", "operation", "bindings", "nonce",
    "sequence", "boot_id", "session_id", "issued_at", "expires_at",
})
ENVELOPE_KEYS = frozenset({
    "schema_version", "artifact_role", "authority_mode", "algorithm",
    "key_id", "public_key_digest", "request_digest", "document_digest",
    "signature",
})
RESPONSE_KEYS = frozenset({
    "schema_version", "artifact_role", "status", "reason_code", "request",
    "grant", "envelope", "key_record", "evidence_decision",
})
EVIDENCE_DECISION_KEYS = frozenset({
    "schema_version", "artifact_role", "verifier_id", "verifier_key_id",
    "provider", "provider_run_id", "head_commit", "evidence_ref",
    "evidence_digest", "verified_at", "outcome", "exit_code",
})


def canonical_bytes(value: object) -> bytes:
    """Encode the single canonical JSON representation used cross-runtime."""
    _validate_public_value(value)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


class AuthorityProviderError(VerificationPlannerError):
    """Stable, non-secret authority-provider contract failure."""


def _fail(reason: str = "authority_invalid") -> None:
    raise AuthorityProviderError(reason)


def _validate_public_value(value: object, depth: int = 0) -> None:
    if depth > 16:
        _fail()
    if value is None or type(value) in {bool, int}:
        return
    if type(value) is float:
        if value != value or value in {float("inf"), float("-inf")}:
            _fail()
        return
    if type(value) is str:
        if len(value.encode("utf-8")) > MAX_STRING_BYTES:
            _fail()
        return
    if type(value) is list:
        if len(value) > MAX_ARRAY_ITEMS:
            _fail()
        for item in value:
            _validate_public_value(item, depth + 1)
        return
    if type(value) is dict:
        if len(value) > MAX_ARRAY_ITEMS or any(type(name) is not str for name in value):
            _fail()
        for name, item in value.items():
            _validate_public_value(name, depth + 1)
            _validate_public_value(item, depth + 1)
        return
    _fail()


def _timestamp(value: object) -> dt.datetime:
    if type(value) is not str or not value or len(value.encode("utf-8")) > MAX_STRING_BYTES:
        _fail()
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail()
    if parsed.tzinfo is None:
        _fail()
    return parsed.astimezone(dt.timezone.utc)


def _closed(document: object, keys: frozenset[str]) -> dict:
    if type(document) is not dict or set(document) != set(keys):
        _fail()
    _validate_public_value(document)
    return document


def build_authority_request(
    *, operation: str, bindings: dict, nonce: str, sequence: int, key_id: str,
    boot_id: str, session_id: str, issued_at: str, expires_at: str,
    document_digest: str, now: dt.datetime | None = None,
) -> dict:
    """Build and validate one exact, replay-resistant v2 request."""
    request = {
        "schema_version": 2,
        "artifact_role": "workflow_authority_request",
        "operation": operation,
        "bindings": bindings,
        "nonce": nonce,
        "sequence": sequence,
        "key_id": key_id,
        "boot_id": boot_id,
        "session_id": session_id,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "document_digest": document_digest,
    }
    validate_authority_request(request, now=now)
    return request


def validate_authority_request(
    request: object, *, now: dt.datetime | None = None,
) -> dict:
    request = _closed(request, REQUEST_KEYS)
    bindings = request.get("bindings")
    if (
        request.get("schema_version") != 2
        or request.get("artifact_role") != "workflow_authority_request"
        or request.get("operation") not in OPERATIONS
        or type(bindings) is not dict
        or set(bindings) != set(REQUEST_BINDING_KEYS)
        or type(request.get("nonce")) is not str
        or NONCE_PATTERN.fullmatch(request["nonce"]) is None
        or type(request.get("sequence")) is not int
        or request["sequence"] < 1
        or any(
            type(request.get(name)) is not str or not request[name]
            for name in ("key_id", "boot_id", "session_id")
        )
        or type(bindings.get("include_worktree")) is not bool
        or type(request.get("document_digest")) is not str
        or DIGEST_PATTERN.fullmatch(request["document_digest"]) is None
    ):
        _fail()
    required_strings = (
        "repository_descriptor_id", "repository_scope_digest", "run_id",
        "authorization_event_id", "profile_ref", "profile_digest",
        "authority_digest", "candidate_snapshot_digest",
    )
    if any(
        type(bindings.get(name)) is not str or not bindings[name]
        for name in required_strings
    ):
        _fail()
    for name, value in bindings.items():
        if name == "include_worktree":
            continue
        if value is not None and (type(value) is not str or not value):
            _fail()
    if (
        type(bindings["trusted_base_commit"]) is not str
        or COMMIT_PATTERN.fullmatch(bindings["trusted_base_commit"]) is None
        or type(bindings["candidate_commit"]) is not str
        or COMMIT_PATTERN.fullmatch(bindings["candidate_commit"]) is None
        or bindings["cadence_boundary"] not in {
            "chunk", "revision_batch", "execution_level",
            "merge_candidate", "post_merge",
        }
        or bindings["provider"] not in {None, "github", "blueprint", "other"}
        or type(bindings["lane_id"]) not in {str, type(None)}
        or bindings["lane_id"] == ""
    ):
        _fail()
    for name in (
        "repository_scope_digest", "profile_digest", "authority_digest",
        "candidate_snapshot_digest", "substrate_digest",
    ):
        value = bindings[name]
        if value is not None and DIGEST_PATTERN.fullmatch(value) is None:
            _fail()
    issued = _timestamp(request["issued_at"])
    expires = _timestamp(request["expires_at"])
    current = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    if expires <= issued or issued > current + MAX_FUTURE_SKEW:
        _fail("authority_stale")
    return request


def key_record_digest(record: dict) -> str:
    return canonical_digest({
        name: value for name, value in record.items() if name != "record_digest"
    })


def validate_public_key_record(
    record: object, *, now: dt.datetime | None = None,
    for_new_authority: bool = True,
    signature_time: dt.datetime | None = None,
) -> dict:
    record = _closed(record, KEY_RECORD_KEYS)
    if (
        record.get("schema_version") != 2
        or record.get("artifact_role") != "workflow_authority_public_key_record"
        or record.get("algorithm") not in ALGORITHMS
        or any(
            type(record.get(name)) is not str or not record[name]
            for name in ("key_id", "issuer_identity")
        )
        or any(
            type(record.get(name)) is not str
            or DIGEST_PATTERN.fullmatch(record[name]) is None
            for name in ("record_digest", "public_key_digest")
        )
        or record["record_digest"] != key_record_digest(record)
    ):
        _fail("authority_key_invalid")
    activated = _timestamp(record["activated_at"])
    not_before = _timestamp(record["verify_not_before"])
    not_after = _timestamp(record["verify_not_after"])
    revoked = None if record["revoked_at"] is None else _timestamp(record["revoked_at"])
    current = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    if activated > not_before or not_after <= not_before:
        _fail("authority_key_invalid")
    if for_new_authority:
        if current < not_before or current > not_after:
            _fail("authority_key_invalid")
        if revoked is not None and current >= revoked:
            _fail("authority_key_revoked")
    elif signature_time is not None and (
        signature_time < activated
        or signature_time < not_before
        or signature_time > not_after
        or revoked is not None and signature_time >= revoked
    ):
        _fail("authority_signature_time_invalid")
    return record


@runtime_checkable
class AuthorityProvider(Protocol):
    mode: str
    write_schema_version: int

    def seal(self, document: dict, field: str, *, operation: str,
             request: dict | None = None) -> dict: ...

    def verify(self, document: dict, field: str, *, operation: str,
               request: dict | None = None) -> dict: ...


class LegacyHMACAuthority:
    """Explicit, compatibility-only authority for schema-v1 documents."""

    mode = "legacy_hmac"
    write_schema_version = 1

    def __init__(self, key: bytes):
        if type(key) is not bytes or len(key) < 32:
            raise VerificationPlannerError(
                "verification receipt key must contain at least 32 bytes",
            )
        self.__key = key

    def _auth(self, document: dict, field: str) -> str:
        payload = {name: value for name, value in document.items() if name != field}
        return "hmac-sha256:" + hmac.new(
            self.__key, canonical_bytes(payload), hashlib.sha256,
        ).hexdigest()

    def seal(self, document: dict, field: str, *, operation: str,
             request: dict | None = None) -> dict:
        if document.get("schema_version") != 1 or request is not None:
            _fail("mixed_authority")
        result = {**document, field: ""}
        result[field] = self._auth(result, field)
        return result

    def verify(self, document: dict, field: str, *, operation: str,
               request: dict | None = None) -> dict:
        if document.get("schema_version") != 1 or request is not None:
            _fail("mixed_authority")
        supplied = document.get(field)
        if (
            type(supplied) is not str
            or re.fullmatch(r"hmac-sha256:[0-9a-f]{64}", supplied) is None
            or not hmac.compare_digest(supplied, self._auth(document, field))
        ):
            _fail("authority_invalid")
        return document


@dataclass(frozen=True)
class NativeProviderAdapter:
    """Canonical fixed-adapter seam; no executable path is accepted."""

    exchange: Callable[[dict], dict]

    def request(self, request: dict) -> dict:
        try:
            response = self.exchange(request)
        except Exception:
            raise VerificationPlannerError("authority_provider_unavailable") from None
        if type(response) is not dict:
            _fail("authority_provider_malformed")
        return response


class NativeProviderAuthority:
    """Fail-closed consumer of native-provider signed public envelopes."""

    mode = "native_provider"
    write_schema_version = 2

    def __init__(
        self, adapter: NativeProviderAdapter, public_key_records: list[dict],
        *, signature_verifier: Callable[[dict, dict], bool],
        now: Callable[[], dt.datetime] | None = None,
    ):
        if (
            type(adapter) is not NativeProviderAdapter
            or type(public_key_records) is not list
            or not callable(signature_verifier)
        ):
            _fail()
        current = (now or self._utcnow)()
        self._adapter = adapter
        self._records = {
            record["key_id"]: record
            for record in public_key_records
            if validate_public_key_record(
                record, now=current, for_new_authority=False,
            )
        }
        if len(self._records) != len(public_key_records):
            _fail("authority_key_invalid")
        self._now = now or self._utcnow
        self._signature_verifier = signature_verifier
        self._seen: set[tuple[str, str]] = set()
        self._sequence: dict[tuple[str, str], int] = {}

    @staticmethod
    def _utcnow() -> dt.datetime:
        return dt.datetime.now(dt.timezone.utc)

    def _validate_response(self, response: object, expected_request: dict,
                           document_digest: str, *, consume: bool,
                           expected_evidence: dict | None = None) -> dict:
        response = _closed(response, RESPONSE_KEYS)
        if (
            response.get("schema_version") != 2
            or response.get("artifact_role")
            != "workflow_authority_provider_response"
        ):
            _fail("authority_provider_malformed")
        status = response.get("status")
        if status != "approved":
            reasons = {
                "denied": "authority_unauthorized",
                "cancelled": "authority_cancelled",
                "unavailable": "authority_provider_unavailable",
            }
            _fail(reasons.get(status, "authority_provider_malformed"))
        if response.get("reason_code") is not None:
            _fail("authority_provider_malformed")
        request = validate_authority_request(
            response.get("request"), now=self._now(),
        )
        if (
            request != expected_request
            or request["document_digest"] != document_digest
            or canonical_digest(request)
            != response.get("envelope", {}).get("request_digest")
        ):
            _fail("authority_binding_mismatch")
        grant = _closed(response.get("grant"), GRANT_KEYS)
        envelope = _closed(response.get("envelope"), ENVELOPE_KEYS)
        issued = _timestamp(request["issued_at"])
        record = validate_public_key_record(
            response.get("key_record"), now=self._now(),
            for_new_authority=consume,
            signature_time=None if consume else issued,
        )
        trusted_record = self._records.get(record["key_id"])
        if trusted_record is None or record != trusted_record:
            _fail("authority_key_untrusted")
        request_digest = canonical_digest(request)
        if (
            grant.get("schema_version") != 2
            or grant.get("artifact_role") != "workflow_authority_grant"
            or grant.get("authority_mode") != self.mode
            or envelope.get("schema_version") != 2
            or envelope.get("artifact_role") != "workflow_authority_signature_envelope"
            or envelope.get("authority_mode") != self.mode
            or envelope.get("algorithm") not in ALGORITHMS
            or envelope.get("signature") is None
            or SIGNATURE_PATTERN.fullmatch(envelope["signature"]) is None
            or request["key_id"] != record["key_id"]
            or grant["key_id"] != record["key_id"]
            or envelope["key_id"] != record["key_id"]
            or grant["public_key_digest"] != record["public_key_digest"]
            or envelope["public_key_digest"] != record["public_key_digest"]
            or envelope["algorithm"] != record["algorithm"]
            or grant["request_digest"] != request_digest
            or envelope["request_digest"] != request_digest
            or envelope["document_digest"] != document_digest
            or grant["operation"] != request["operation"]
            or grant["bindings"] != request["bindings"]
            or any(grant[name] != request[name] for name in (
                "nonce", "sequence", "boot_id", "session_id", "issued_at", "expires_at",
            ))
        ):
            _fail("authority_binding_mismatch")
        _timestamp(grant["issued_at"])
        if self._now().astimezone(dt.timezone.utc) > _timestamp(grant["expires_at"]):
            if consume:
                _fail("authority_stale")
        try:
            verified = self._signature_verifier(trusted_record, envelope)
        except Exception:
            raise VerificationPlannerError("authority_signature_invalid") from None
        if verified is not True:
            _fail("authority_signature_invalid")
        if response["evidence_decision"] is not None:
            decision = _closed(response["evidence_decision"], EVIDENCE_DECISION_KEYS)
            if decision.get("schema_version") != 2 or decision.get("artifact_role") != "workflow_authority_evidence_decision":
                _fail("provider_evidence_invalid")
        if expected_evidence is not None and response["evidence_decision"] != expected_evidence:
            _fail("provider_evidence_invalid")
        if consume:
            replay_key = (request["boot_id"], request["nonce"])
            sequence_key = (request["boot_id"], request["session_id"])
            if replay_key in self._seen or request["sequence"] <= self._sequence.get(sequence_key, 0):
                _fail("authority_replay")
            self._seen.add(replay_key)
            self._sequence[sequence_key] = request["sequence"]
        return response

    def accept_response(self, response: dict, expected_request: dict,
                        document: dict) -> dict:
        return self._validate_response(
            response, validate_authority_request(
                expected_request, now=self._now(),
            ),
            canonical_digest(document), consume=True,
        )

    def seal(self, document: dict, field: str, *, operation: str,
             request: dict | None = None) -> dict:
        if document.get("schema_version") != 2 or field in document or request is None:
            _fail("mixed_authority")
        request = validate_authority_request(request, now=self._now())
        if request["operation"] != operation:
            _fail("authority_binding_mismatch")
        if request["document_digest"] != canonical_digest(document):
            _fail("authority_binding_mismatch")
        response = self._adapter.request(request)
        response = self._validate_response(
            response, request, canonical_digest(document), consume=True,
            expected_evidence=(
                document.get("verifier_provenance")
                if operation == "provider_attestation" else None
            ),
        )
        return {**document, field: {
            "authority_mode": self.mode,
            "grant": response["grant"],
            "envelope": response["envelope"],
            "key_record": response["key_record"],
        }}

    def verify(self, document: dict, field: str, *, operation: str,
               request: dict | None = None) -> dict:
        if document.get("schema_version") != 2 or request is None:
            _fail("mixed_authority")
        provenance = document.get(field)
        if type(provenance) is not dict or set(provenance) != {"authority_mode", "grant", "envelope", "key_record"}:
            _fail()
        if provenance["authority_mode"] != self.mode:
            _fail("mixed_authority")
        unsigned = {name: value for name, value in document.items() if name != field}
        if validate_authority_request(
            request, now=self._now(),
        )["document_digest"] != canonical_digest(unsigned):
            _fail("authority_binding_mismatch")
        response = {
            "schema_version": 2,
            "artifact_role": "workflow_authority_provider_response",
            "status": "approved",
            "reason_code": None,
            "request": request,
            "grant": provenance["grant"],
            "envelope": provenance["envelope"],
            "key_record": provenance["key_record"],
            "evidence_decision": None,
        }
        self._validate_response(response, request, canonical_digest(unsigned), consume=False)
        if request["operation"] != operation:
            _fail("authority_binding_mismatch")
        return document


def synthetic_signature(payload: bytes) -> str:
    """Return a public test-only signature-shaped value, never key material."""
    return "p256-sha256:" + base64.b64encode(hashlib.sha256(payload).digest()).decode("ascii")
