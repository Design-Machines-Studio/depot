#!/usr/bin/env python3
"""Production-ineligible fixture for the fixed workflow-authority client seam."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys


PROTOCOL = "workflow-authority-provider-dispatch-v1"
FIXTURE_DOMAIN = "fixture.workflow-authority.invalid"
MARKER = "workflow-authority-fixture-v1\n"
SENSITIVE_ENV = {
    "OPENROUTER_API_KEY", "OPENROUTER_BASE", "OPENROUTER_ZDR",
    "OPENROUTER_PAYLOAD_AUTHORIZATION", "OPENROUTER_PAYLOAD_APPROVAL_SHA256",
    "OPENROUTER_AUTHORIZATION_MODE", "OPENROUTER_RECEIPT_FILE",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
}


def fail(code: int, reason: str) -> "None":
    print(f"fake-workflow-authority: {reason}", file=sys.stderr)
    raise SystemExit(code)


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def fixture_root() -> Path:
    if os.environ.get("DM_AUTOMATION_TEST") != "1":
        fail(70, "explicit automation-test marker required")
    raw = os.environ.get("DM_AUTOMATION_TEST_ROOT", "")
    if not raw or not os.path.isabs(raw):
        fail(70, "absolute injected fixture root required")
    root = Path(raw).resolve()
    try:
        if (root / ".workflow-authority-fixture").read_text() != MARKER:
            fail(70, "fixture trust marker invalid")
    except OSError:
        fail(70, "fixture trust marker unavailable")
    if Path(sys.argv[0]).resolve().parent != root:
        fail(70, "client is not inside injected fixture root")
    if any(name in os.environ for name in SENSITIVE_ENV):
        fail(70, "authority or provider environment was not scrubbed")
    return root


def parse_dispatch(argv: list[str]) -> dict[str, object]:
    valued = {
        "--repository", "--run-id", "--lane", "--candidate", "--workload",
        "--nonce", "--model", "--fallback-model", "--system-fd", "--user-fd",
        "--response-fd",
    }
    parsed: dict[str, object] = {}
    index = 0
    while index < len(argv):
        key = argv[index]
        if key not in valued or index + 1 >= len(argv) or key in parsed:
            fail(2, "closed dispatch arguments violated")
        parsed[key] = argv[index + 1]
        index += 2
    required = valued - {"--fallback-model"}
    if set(parsed) < required:
        fail(2, "required dispatch argument missing")
    if parsed["--lane"] != "pipeline-assessment-artifact-delegation-v1":
        fail(70, "lane unavailable")
    if parsed["--system-fd"] != "4" or parsed["--user-fd"] != "5" or parsed["--response-fd"] != "3":
        fail(2, "fixed descriptor contract violated")
    return parsed


def status() -> None:
    fixture_root()
    print(canonical({
        "schema_version": 1,
        "protocol": PROTOCOL,
        "production_ready": False,
        "fixture_ready": True,
        "fixture_domain": FIXTURE_DOMAIN,
        "socket_root_source": "injected-test-only",
    }).decode())


def dispatch(argv: list[str]) -> None:
    root = fixture_root()
    args = parse_dispatch(argv)
    case = os.environ.get("DM_WORKFLOW_AUTHORITY_FIXTURE_CASE", "signed-success")
    if case == "unavailable":
        fail(70, "host_authority_unavailable")
    if case in {"disclosure-declined", "approval-declined"}:
        fail(72 if case == "disclosure-declined" else 71, case)
    if case in {"provider-failure", "timeout"}:
        fail(73 if case == "provider-failure" else 74, case)
    system = os.read(4, 8_388_609)
    user = os.read(5, 8_388_609)
    if len(system) + len(user) > 8_388_608:
        fail(2, "request bound exceeded")
    (root / "observed-system").write_bytes(system)
    (root / "observed-user").write_bytes(user)
    response_path = root / "response"
    try:
        response = response_path.read_bytes()
    except OSError:
        fail(75, "fixture response unavailable")

    models = [str(args["--model"])]
    if args.get("--fallback-model"):
        models.append(str(args["--fallback-model"]))
    header = {
        "repository": args["--repository"], "run_id": args["--run-id"],
        "lane": args["--lane"], "candidate": args["--candidate"],
        "workload": args["--workload"], "nonce": args["--nonce"],
        "models": models,
        "parts": [
            {"role": "system", "content_length": len(system), "content_sha256": digest(system)},
            {"role": "user", "content_length": len(user), "content_sha256": digest(user)},
        ],
    }
    selected_model = str(args["--model"])
    if case == "signed-fallback" and len(models) > 1:
        selected_model = models[1]
    usage = {"completion_tokens": 2, "prompt_tokens": 3, "total_tokens": 5}
    terminal = {
        "schema_version": 1, "protocol": PROTOCOL,
        "operation_family": "external_provider_dispatch",
        "substrate_authority": "not_asserted", "outcome": "verified", "exit_code": 0,
        "request_body_sha256": digest(canonical({
            "messages": [{"content": system.decode(), "role": "system"},
                         {"content": user.decode(), "role": "user"}],
            "models": models, "temperature": None,
        })),
        "response_sha256": digest(response), "response_length": len(response),
        "part_count": 2, "models": models, "selected_model": selected_model,
        "provider": "openrouter",
        "generation_id": "generation-fixture", "serving_provider": "fixture-provider",
        "usage_sha256": digest(canonical(usage)), "fallback": selected_model != models[0],
        "scope": {
            "repository": args["--repository"], "run_id": args["--run-id"],
            "lane": args["--lane"], "candidate": args["--candidate"],
            "workload": args["--workload"],
        },
        "sequence": 1, "issued_at": "2026-08-03T00:00:00Z",
        "completed_at": "2026-08-03T00:00:01Z",
        "challenge_sha256": digest(canonical(header)),
        "authority_assertion_sha256": digest(b"fixture-authority-assertion"),
        "result_signer_sha256": digest(b"fixture-result-signer"),
        "prior_chain_digest": digest(b"fixture-prior-chain"),
        "cleanup": {"reservation": "consumed", "connection": "closed", "content_buffer": "discarded"},
        "signature": {"kind": "fixture-rsa-sha256-v1", "domain": FIXTURE_DOMAIN, "value": "fixture-rsa-sha256-v1:" + "a" * 256},
    }
    if case == "wrong-scope":
        terminal["scope"]["candidate"] = "wrong-candidate"
    elif case == "wrong-response-length":
        terminal["response_length"] = len(response) + 1
    elif case == "wrong-response-digest":
        terminal["response_sha256"] = digest(b"wrong-response")
    elif case == "unknown-outcome":
        terminal["outcome"] = "unknown"
        terminal["exit_code"] = 74
    elif case == "wrong-body":
        terminal["request_body_sha256"] = digest(b"wrong-body")
    elif case == "wrong-model-order":
        terminal["models"] = list(reversed(models))
    elif case == "wrong-selected-model":
        terminal["selected_model"] = "fixture/not-requested"
    elif case == "wrong-generation":
        terminal["generation_id"] = "bad generation"
    elif case == "wrong-serving-provider":
        terminal["serving_provider"] = "bad provider"
    elif case == "wrong-usage-digest":
        terminal["usage_sha256"] = digest(b"wrong-usage")
    elif case == "wrong-fallback":
        terminal["fallback"] = not terminal["fallback"]
    elif case == "forged-signature":
        terminal["signature"]["value"] = "fixture-rsa-sha256-v1:" + "0" * 256
    os.write(3, response)
    if case == "missing-result":
        return
    if case == "malformed-frame":
        sys.stdout.buffer.write(b"{malformed\n")
        return
    sys.stdout.buffer.write(canonical(terminal) + b"\n")


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "provider-transport-status":
        status()
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "dispatch-provider-request":
        dispatch(sys.argv[2:])
        return
    fail(2, "unknown command")


if __name__ == "__main__":
    main()
