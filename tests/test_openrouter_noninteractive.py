"""Loopback regressions for configured-key OpenRouter development paths."""

from __future__ import annotations

import http.server
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import threading
import unittest


REPO = Path(__file__).resolve().parents[1]
OPENROUTER = REPO / "plugins/openrouter"
PIPELINE_EXEC = REPO / "plugins/model-router/skills/model-router/references/openrouter-write-adapter.sh"
KERNEL = REPO / "plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
BOUNDARY = OPENROUTER / "skills/openrouter-delegate/references/delegation-boundary.sh"
POLICY = OPENROUTER / "skills/openrouter-delegate/references/delegation-security-policy.json"
WRAPPER = OPENROUTER / "skills/openrouter-delegate/references/openrouter-wrapper.sh"
RUNNER = OPENROUTER / "agents/workflow/openrouter-agent-runner.md"


def runner_shell_block(start: str, end: str) -> str:
    """Extract one executable shell block from the canonical runner source."""
    lines = RUNNER.read_text().splitlines()
    start_index = next(index for index, line in enumerate(lines) if line == start)
    end_index = next(
        index for index in range(start_index, len(lines)) if lines[index] == end
    )
    return "\n".join(lines[start_index:end_index + 1])

PR_677_SAFE_SHAPES = """\
secret_access_key="${UPDATE_R2_SECRET_ACCESS_KEY:-}"
UPDATE_R2_SECRET_ACCESS_KEY=proof-secret-not-for-proof
AWS_SECRET_ACCESS_KEY=aws-secret-not-for-proof
CI_SECRET="${{ secrets.UPDATE_R2_SECRET_ACCESS_KEY }}"
"""

PR_719_HISTORICAL_SENTINEL_DIFF = """\
diff --git a/tests/integration/compose-release-command.sh b/tests/integration/compose-release-command.sh
--- a/tests/integration/compose-release-command.sh
+++ b/tests/integration/compose-release-command.sh
@@ -1 +1 @@
-GITHUB_TOKEN=old-fixture
+GITHUB_TOKEN=ghp_test-secret-not-for-proof
"""


class DisclosureBoundaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def boundary(self, mode: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(BOUNDARY), "--mode", mode, "--policy", str(POLICY), *args],
            cwd=REPO, text=True, capture_output=True,
        )

    def artifact(self, content: str) -> subprocess.CompletedProcess[str]:
        artifact = self.root / "artifact.txt"
        artifact.write_text(content)
        return self.boundary("artifact-delegation", "--content-file", str(artifact))

    def review_diff(
        self, content: str, changed_paths: tuple[str, ...] = (
            "deploy/release.sh", "docs/notes.md",
        ),
    ) -> tuple[subprocess.CompletedProcess[str], Path, Path, Path]:
        changed = self.root / "changed.txt"
        source = self.root / "review.diff"
        output = self.root / "filtered.diff"
        declined = self.root / "declined.txt"
        decision = self.root / "decision.json"
        changed.write_text("".join(f"{path}\n" for path in changed_paths))
        source.write_text(content)
        result = self.boundary(
            "mechanical-review",
            "--changed-files", str(changed),
            "--diff-file", str(source),
            "--output-diff", str(output),
            "--output-declined-paths", str(declined),
            "--output-decision", str(decision),
        )
        return result, output, declined, decision

    def test_pr_677_safe_shapes_pass_artifact_delegation(self) -> None:
        """Assembly Baseplate PR #677 at bf56524 must remain usable unchanged."""
        result = self.artifact(PR_677_SAFE_SHAPES)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pr_677_safe_shapes_pass_as_complete_review_section(self) -> None:
        diff = (
            "diff --git a/deploy/release.sh b/deploy/release.sh\n"
            "--- a/deploy/release.sh\n+++ b/deploy/release.sh\n"
            "@@ -1 +1,4 @@\n-old fixture\n"
            + "".join(f"+{line}\n" for line in PR_677_SAFE_SHAPES.splitlines())
            + "diff --git a/docs/notes.md b/docs/notes.md\n"
            "--- a/docs/notes.md\n+++ b/docs/notes.md\n"
            "@@ -1 +1 @@\n-before\n+after\n"
        )
        result, output, declined, decision = self.review_diff(diff)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text(), diff)
        self.assertEqual(declined.read_bytes(), b"")
        self.assertEqual(json.loads(decision.read_text()), {
            "schemaVersion": 1,
            "decision": "eligible",
            "reason": "none",
            "eligibleSectionCount": 2,
            "declinedSectionCount": 0,
        })

    def test_shell_parameter_and_ci_references_are_not_values(self) -> None:
        references = """\
AWS_SECRET_ACCESS_KEY=${SOURCE_SECRET}
AWS_SECRET_ACCESS_KEY=${SOURCE_SECRET:-}
AWS_SECRET_ACCESS_KEY=${SOURCE_SECRET-default}
AWS_SECRET_ACCESS_KEY=${SOURCE_SECRET:?message}
AWS_SECRET_ACCESS_KEY=${{ secrets.SOURCE_SECRET }}
"""
        result = self.artifact(references)
        self.assertEqual(result.returncode, 0, result.stderr)
        invalid = self.artifact(
            "AWS_SECRET_ACCESS_KEY=${SOURCE-SECRET:-abcdefghijklmnop}\n"
        )
        self.assertEqual(invalid.returncode, 0, invalid.stderr)

    def test_fixture_and_credential_assignment_shapes_are_accepted(self) -> None:
        fixture_shapes = self.artifact(
            "UPDATE_R2_SECRET_ACCESS_KEY=proof-secret-not-for-proof\n"
            "AWS_SECRET_ACCESS_KEY=aws-secret-not-for-proof\n"
            "TOKEN=test-secret-not-for-proof\n"
            "GITHUB_TOKEN=ghp_test-secret-not-for-proof\n"
            "GITHUB_TOKEN=ghp_test-access-not-for-proof\n"
            "OPENROUTER_API_KEY=sk-or-v1-test-secret-not-for-proof\n"
        )
        self.assertEqual(fixture_shapes.returncode, 0, fixture_shapes.stderr)
        for content in (
            "AWS_SECRET_ACCESS_KEY=proof-secret-for-production-1234567890\n",
            "OPENROUTER_API_KEY=sk-or-v1-abcdefghijklmnop-not-for-proof\n",
            "GITHUB_TOKEN=ghp_test-anything-not-for-proof\n",
            "TOKEN=test-A7b9C2d4E6f8G1h3J5k7\n",
        ):
            with self.subTest(content=content):
                accepted = self.artifact(content)
                self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_historical_pr_719_provider_prefixed_fixture_passes_unchanged(self) -> None:
        result, output, declined, decision = self.review_diff(
            PR_719_HISTORICAL_SENTINEL_DIFF,
            ("tests/integration/compose-release-command.sh",),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text(), PR_719_HISTORICAL_SENTINEL_DIFF)
        self.assertEqual(declined.read_bytes(), b"")
        self.assertEqual(json.loads(decision.read_text())["decision"], "eligible")

    def test_realistic_provider_credential_shapes_are_accepted(self) -> None:
        cases = (
            "GITHUB_TOKEN=ghp_0123456789abcdefABCDEF\n",
            "OPENROUTER_API_KEY=sk-or-v1-0123456789abcdefABCDEF\n",
            "ANTHROPIC_API_KEY=sk-ant-0123456789abcdefABCDEF\n",
            "AWS_ACCESS_KEY_ID=AKIA0123456789ABCDEF\n",
            "SLACK_TOKEN=xoxb-0123456789abcdefABCDEF\n",
            "GOOGLE_API_KEY=AIza0123456789abcdefABCDEF\n",
            "NPM_TOKEN=npm_0123456789abcdefABCDEF\n",
            "GITLAB_TOKEN=glpat-0123456789abcdefABCDEF\n",
            "PAYMENT_KEY=sk_live_0123456789abcdefABCDEF\n",
        )
        for content in cases:
            with self.subTest(prefix=content.split("=", 1)[0]):
                result = self.artifact(content)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_security_looking_paths_with_harmless_code_remain_eligible(self) -> None:
        paths = (
            ".env.example",
            "internal/auth/session.go",
            "deploy/release.sh",
            "internal/http/middleware/security.go",
        )
        diff = "".join(
            f"diff --git a/{path} b/{path}\n"
            f"--- a/{path}\n+++ b/{path}\n"
            "@@ -1 +1 @@\n-before\n+after\n"
            for path in paths
        )
        result, output, declined, decision = self.review_diff(diff, paths)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text(), diff)
        self.assertEqual(declined.read_bytes(), b"")
        self.assertEqual(json.loads(decision.read_text())["eligibleSectionCount"], 4)

    def test_mixed_review_keeps_credential_shaped_section_eligible(self) -> None:
        safe_path = "internal/auth/session.go"
        held_path = "tests/integration/compose-release-command.sh"
        safe_section = (
            f"diff --git a/{safe_path} b/{safe_path}\n"
            f"--- a/{safe_path}\n+++ b/{safe_path}\n"
            "@@ -1 +1 @@\n-before\n+after\n"
        )
        held_section = (
            f"diff --git a/{held_path} b/{held_path}\n"
            f"--- a/{held_path}\n+++ b/{held_path}\n"
            "@@ -1 +1 @@\n-before\n"
            "+GITHUB_TOKEN=ghp_0123456789abcdefABCDEF\n"
        )
        result, output, declined, decision = self.review_diff(
            safe_section + held_section, (safe_path, held_path),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text(), safe_section + held_section)
        self.assertEqual(declined.read_bytes(), b"")
        self.assertEqual(json.loads(decision.read_text()), {
            "schemaVersion": 1,
            "decision": "eligible",
            "reason": "none",
            "eligibleSectionCount": 2,
            "declinedSectionCount": 0,
        })

    def test_credential_only_review_section_remains_eligible(self) -> None:
        held_path = "tests/integration/compose-release-command.sh"
        diff = (
            f"diff --git a/{held_path} b/{held_path}\n"
            f"--- a/{held_path}\n+++ b/{held_path}\n"
            "@@ -1 +1 @@\n-before\n"
            "+GITHUB_TOKEN=ghp_0123456789abcdefABCDEF\n"
        )
        result, output, declined, decision = self.review_diff(diff, (held_path,))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output.read_text(), diff)
        self.assertEqual(declined.read_bytes(), b"")
        self.assertEqual(json.loads(decision.read_text()), {
            "schemaVersion": 1,
            "decision": "eligible",
            "reason": "none",
            "eligibleSectionCount": 1,
            "declinedSectionCount": 0,
        })

    def test_real_aws_secrets_are_accepted_in_assignment_shapes(self) -> None:
        secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        cases = (
            f"AWS_SECRET_ACCESS_KEY={secret}\n",
            f'AWS_SECRET_ACCESS_KEY="${{SOURCE_SECRET:-{secret}}}"\n',
            f'"AWS_SECRET_ACCESS_KEY": "{secret}"\n',
        )
        for content in cases:
            with self.subTest(content=content):
                result = self.artifact(content)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_credential_sensitive_classes_are_accepted(self) -> None:
        cases = {
            "private-key": (
                "-----BEGIN PRIVATE KEY-----\n"
                "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo1234567890=\n"
                "-----END PRIVATE KEY-----\n"
            ),
            "access-token": "Authorization: Bearer AbCdEfGhIjKlMnOpQrStUvWxYz012345\n",
            "jwt": (
                "TOKEN=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJmaXh0dXJlIn0."
                "c3ludGhldGljc2lnbmF0dXJl\n"
            ),
            "authenticated-dsn": "DATABASE_URL=postgres://admin:correct-horse-battery@db.internal/app\n",
            "classified-private-data": "data_classification: regulated\n",
        }
        for shape, content in cases.items():
            with self.subTest(shape=shape):
                result = self.artifact(content)
                self.assertEqual(result.returncode, 0, result.stderr)


class FixtureHandler(http.server.BaseHTTPRequestHandler):
    contacts = 0
    requests: list[dict] = []
    authorizations: list[str | None] = []
    response_text = "fixture response"
    response_mode = "complete"
    response_status = 200
    response_body: dict | str = {}
    block_response = False
    request_seen = threading.Event()
    release_response = threading.Event()

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        type(self).contacts += 1
        type(self).requests.append(payload)
        type(self).authorizations.append(self.headers.get("Authorization"))
        type(self).request_seen.set()
        if type(self).block_response:
            type(self).release_response.wait(timeout=5)
        if type(self).response_status != 200:
            response_body = type(self).response_body
            encoded = (
                response_body if isinstance(response_body, str)
                else json.dumps(response_body)
            ).encode()
            self.send_response(type(self).response_status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        model = payload.get("model") or payload.get("models", ["z-ai/glm-5.2"])[0]
        content_event = {
            "id": "gen-fixture", "model": model, "provider": "fixture/provider",
            "choices": [{"delta": {"content": type(self).response_text}}],
        }
        stop_event = {
            "id": "gen-fixture", "model": model, "provider": "fixture/provider",
            "usage": {"prompt_tokens": 11, "completion_tokens": 7,
                      "total_tokens": 18, "cost": 0.0042},
            "choices": [{"delta": {}, "finish_reason": "stop"}],
        }
        error_event = {
            "id": "gen-fixture", "model": model, "provider": "fixture/provider",
            "error": {"code": 502, "message": "Provider disconnected unexpectedly"},
            "choices": [{"index": 0, "delta": {"content": ""},
                         "finish_reason": "error"}],
        }
        events = [
            content_event,
            error_event if type(self).response_mode == "stream_error" else stop_event,
        ]
        body = "".join(f"data: {json.dumps(event)}\n\n" for event in events)
        if type(self).response_mode == "complete":
            body += "data: [DONE]\n\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *_args: object) -> None:
        return


class OpenRouterNonInteractiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/api/v1"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.thread.join(timeout=5)

    def setUp(self) -> None:
        FixtureHandler.contacts = 0
        FixtureHandler.requests = []
        FixtureHandler.authorizations = []
        FixtureHandler.response_text = "fixture response"
        FixtureHandler.response_mode = "complete"
        FixtureHandler.response_status = 200
        FixtureHandler.response_body = {}
        FixtureHandler.block_response = False
        FixtureHandler.request_seen.clear()
        FixtureHandler.release_response.clear()
        self.api_key = "test"
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        installed = self.home / ".codex/plugins/cache/depot/openrouter/1.14.0"
        installed.parent.mkdir(parents=True)
        shutil.copytree(OPENROUTER, installed)
        self.installed = installed
        self.kernel = self.root / "workflow-kernel"
        self.kernel.write_text(
            "#!/usr/bin/env bash\n"
            "case \"${1:-}\" in\n"
            "  resolve-plugin-bundle) printf '%s\\n' "
            "'{\"selected_root\":\"~/.codex/plugins/cache/depot/openrouter/1.14.0\"}' ;;\n"
            "  *) exit 4 ;;\n"
            "esac\n"
        )
        self.kernel.chmod(0o755)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        env.update({"HOME": str(self.home), "OPENROUTER_API_KEY": self.api_key,
                    "OPENROUTER_BASE": self.base, "WORKFLOW_KERNEL": str(self.kernel),
                    "OPENROUTER_BUNDLE_RESOLVED": "1",
                    "OPENROUTER_BUNDLE_REF": "~/.codex/plugins/cache/depot/openrouter/1.14.0",
                    "OPENROUTER_BUNDLE_VERSION": "1.14.0",
                    "OPENROUTER_BUNDLE_CACHE_CLASS": "codex",
                    "OPENROUTER_BUNDLE_REASON": "available",
                    "MODEL_ROUTER_CONTRACT_DIGEST": "sha256:" + "a" * 64,
                    "MODEL_ROUTER_CONTRACT_REVISION": "1"})
        env.pop("OPENROUTER_API_KEY_FILE", None)
        return env

    def direct(
        self, prompt: str, bundle: Path | None = None, *, web_search: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        bundle = bundle or OPENROUTER
        boundary = bundle / "skills/openrouter-delegate/references/delegation-boundary.sh"
        policy = bundle / "skills/openrouter-delegate/references/delegation-security-policy.json"
        wrapper = bundle / "skills/openrouter-delegate/references/openrouter-wrapper.sh"
        system = self.root / "system"
        user = self.root / "user"
        receipt = self.root / "receipt.json"
        system.write_text("You are a fixture assistant.")
        user.write_text(prompt)
        script = f'''set -e
"{boundary}" --mode artifact-delegation --policy "{policy}" --content-file "{system}" --content-file "{user}" >/dev/null
env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="{system}" OPENROUTER_WORKLOAD=direct OPENROUTER_WEB_SEARCH="{1 if web_search else 0}" OPENROUTER_RECEIPT_FILE="{receipt}" bash "{wrapper}" openai/gpt-5.6-terra - 10 moonshotai/kimi-k3 < "{user}"
'''
        result = subprocess.run(["bash", "-c", script], text=True, capture_output=True, env=self.env())
        result.receipt_path = receipt  # type: ignore[attr-defined]
        return result

    def test_browser_capability_enables_provider_web_plugin(self) -> None:
        result = self.direct("Use web evidence for this bounded research task.", web_search=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(FixtureHandler.requests[-1]["plugins"], [{"id": "web"}])
        receipt = json.loads(result.receipt_path.read_text())  # type: ignore[attr-defined]
        self.assertTrue(receipt["routing"]["webSearch"])

    def review_runner(
        self, diff: str, changed_paths: tuple[str, ...],
    ) -> tuple[subprocess.CompletedProcess[str], str, str]:
        """Execute the runner's source blocks through the loopback provider."""
        changed = self.root / "runner-changed.txt"
        source = self.root / "runner.diff"
        safe_copy = self.root / "runner-safe-copy.diff"
        held_copy = self.root / "runner-held-copy"
        script = self.root / "runner-harness.sh"
        changed.write_text("".join(f"{path}\n" for path in changed_paths))
        source.write_text(diff)
        mechanical = runner_shell_block(
            'BOUNDARY_HELPER="$(dirname "$SECURITY_POLICY_RESOLVED")/delegation-boundary.sh"',
            'DECLINED_CHANGED_FILES=$(tr \'\\0\' \'\\n\' < "$BOUNDARY_DECLINED_PATHS")',
        )
        wrapper_dispatch = runner_shell_block(
            'WRAPPER_PATH="$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"',
            'EXIT_CODE=$?',
        )
        script.write_text("\n".join((
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            'target_agent_name="doc-sync-reviewer"',
            'target_model="z-ai/glm-5.2"',
            'fallback_model=""',
            'target_timeout="10"',
            'review_run_id="runner-loopback-fixture"',
            'diff_content="$(cat "$RUNNER_DIFF")"',
            'changed_files="$(cat "$RUNNER_CHANGED")"',
            'SECURITY_POLICY_RESOLVED="$RUNNER_POLICY"',
            'OPENROUTER_ROOT="$RUNNER_OPENROUTER_ROOT"',
            'TARGET_BODY="Review the eligible code sections."',
            mechanical,
            'cp "$BOUNDARY_FILTERED" "$RUNNER_SAFE_COPY"',
            'cp "$BOUNDARY_DECLINED_PATHS" "$RUNNER_HELD_COPY"',
            'USER_PROMPT="$(printf \'Review this diff:\\n%s\' "$FILTERED_DIFF")"',
            wrapper_dispatch,
            '[ "$EXIT_CODE" -eq 0 ]',
            'printf \'%s\\n\' "$RESULT"',
            'if [ -n "$DECLINED_CHANGED_FILES" ]; then',
            '  if [ "$DECLINED_SECTION_COUNT" = 1 ]; then section_label=section; else section_label=sections; fi',
            '  printf \'OpenRouter reviewed %s eligible file sections; %s %s remained local.\\n\' "$ELIGIBLE_SECTION_COUNT" "$DECLINED_SECTION_COUNT" "$section_label"',
            '  printf \'Closed reason: %s.\\n\' "$BOUNDARY_DECISION_REASON"',
            '  printf \'Local coverage paths:\\n%s\\n\' "$DECLINED_CHANGED_FILES"',
            'fi',
            "",
        )))
        script.chmod(0o755)
        result = subprocess.run(
            [str(script)], cwd=REPO, text=True, capture_output=True,
            env={
                **self.env(),
                "RUNNER_DIFF": str(source),
                "RUNNER_CHANGED": str(changed),
                "RUNNER_POLICY": str(POLICY),
                "RUNNER_OPENROUTER_ROOT": str(OPENROUTER),
                "RUNNER_SAFE_COPY": str(safe_copy),
                "RUNNER_HELD_COPY": str(held_copy),
            },
        )
        safe_diff = safe_copy.read_text() if safe_copy.exists() else ""
        return result, result.stdout, safe_diff

    def transport(self, prompt: str) -> subprocess.CompletedProcess[str]:
        """Exercise only the generic wrapper's request/SSE transport boundary."""
        receipt = self.root / "transport-receipt.json"
        result = subprocess.run(
            [str(WRAPPER), "z-ai/glm-5.2", "-", "10"],
            input=prompt, text=True, capture_output=True, env={
                **self.env(), "OPENROUTER_RECEIPT_FILE": str(receipt),
            },
        )
        result.receipt_path = receipt  # type: ignore[attr-defined]
        return result

    def test_direct_is_one_pass_and_receipt_is_content_free(self) -> None:
        result = self.direct("Review harmless public configuration.")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(FixtureHandler.contacts, 1)
        self.assertEqual(FixtureHandler.authorizations, ["Bearer test"])
        self.assertNotRegex(result.stdout + result.stderr, r"approval_required|APPROVAL REQUIRED|exit 78|batch|broker")
        receipt = json.loads(result.receipt_path.read_text())  # type: ignore[attr-defined]
        self.assertRegex(receipt["authorization"]["requestEnvelopeSha256"], r"^[0-9a-f]{64}$")
        self.assertIsNone(receipt["failureReason"])
        self.assertEqual(receipt["usage"]["total_tokens"], 18)
        serialized = json.dumps(receipt).lower()
        for forbidden in ("review harmless", "fixture response", "api_key", "secret"):
            self.assertNotIn(forbidden, serialized)

    def test_review_runner_contacts_loopback_once_with_credential_shaped_section(self) -> None:
        safe_path = "internal/auth/session.go"
        held_path = "tests/integration/compose-release-command.sh"
        safe_section = (
            f"diff --git a/{safe_path} b/{safe_path}\n"
            f"--- a/{safe_path}\n+++ b/{safe_path}\n"
            "@@ -1 +1 @@\n-before\n+SAFE_REMAINDER_MARKER\n"
        )
        held_section = (
            f"diff --git a/{held_path} b/{held_path}\n"
            f"--- a/{held_path}\n+++ b/{held_path}\n"
            "@@ -1 +1 @@\n-before\n"
            "+GITHUB_TOKEN=ghp_0123456789abcdefABCDEF\n"
        )

        boundary, operator, safe_diff = self.review_runner(
            safe_section + held_section, (safe_path, held_path),
        )

        self.assertEqual(boundary.returncode, 0, boundary.stderr)
        self.assertEqual(FixtureHandler.contacts, 1)
        self.assertEqual(safe_diff, (safe_section + held_section).rstrip("\n"))
        outbound = json.dumps(FixtureHandler.requests[0])
        self.assertIn("SAFE_REMAINDER_MARKER", outbound)
        self.assertIn("ghp_0123456789abcdefABCDEF", outbound)
        self.assertIn(held_path, outbound)
        self.assertEqual(operator, "fixture response\n")
        self.assertNotIn("No code was sent", operator)

    def test_review_runner_credential_only_section_contacts_loopback(self) -> None:
        held_path = "tests/integration/compose-release-command.sh"
        held_section = (
            f"diff --git a/{held_path} b/{held_path}\n"
            f"--- a/{held_path}\n+++ b/{held_path}\n"
            "@@ -1 +1 @@\n-before\n"
            "+GITHUB_TOKEN=ghp_0123456789abcdefABCDEF\n"
        )

        boundary, operator, safe_diff = self.review_runner(
            held_section, (held_path,),
        )

        self.assertEqual(boundary.returncode, 0, boundary.stderr)
        self.assertEqual(FixtureHandler.contacts, 1)
        self.assertEqual(safe_diff, held_section.rstrip("\n"))
        outbound = json.dumps(FixtureHandler.requests[0])
        self.assertIn("ghp_0123456789abcdefABCDEF", outbound)
        self.assertIn(held_path, outbound)
        self.assertEqual(operator, "fixture response\n")

    def test_wrapper_transmits_complete_generated_payloads_at_historical_sizes(self) -> None:
        for prompt_bytes in (1024, 107 * 1024, 271 * 1024):
            with self.subTest(prompt_bytes=prompt_bytes):
                result = self.transport("x" * prompt_bytes)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    len(FixtureHandler.requests[-1]["messages"][1]["content"].encode()),
                    prompt_bytes,
                )
                self.assertEqual(result.stdout, "fixture response\n")

    def test_incomplete_stream_discards_partial_output_at_small_and_large_sizes(self) -> None:
        FixtureHandler.response_mode = "incomplete"
        FixtureHandler.response_text = "PARTIAL_RESPONSE_MARKER"
        for prompt_bytes in (1024, 271 * 1024):
            with self.subTest(prompt_bytes=prompt_bytes):
                result = self.transport("x" * prompt_bytes)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                receipt = json.loads(result.receipt_path.read_text())  # type: ignore[attr-defined]
                self.assertEqual(receipt["outcome"], "error")
                self.assertEqual(receipt["failureKind"], "incomplete_stream")
                self.assertIsNone(receipt["failureReason"])
                self.assertIsNone(receipt["usage"])
                serialized = json.dumps(receipt)
                self.assertNotIn("PARTIAL_RESPONSE_MARKER", serialized)

    def test_official_midstream_error_without_done_is_stream_error(self) -> None:
        FixtureHandler.response_mode = "stream_error"
        FixtureHandler.response_text = "PARTIAL_RESPONSE_MARKER"
        result = self.transport("Review harmless public configuration.")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        receipt = json.loads(result.receipt_path.read_text())  # type: ignore[attr-defined]
        self.assertEqual(receipt["outcome"], "error")
        self.assertEqual(receipt["failureKind"], "stream_error")
        self.assertIsNone(receipt["failureReason"])
        self.assertIsNone(receipt["usage"])
        self.assertNotIn("PARTIAL_RESPONSE_MARKER", json.dumps(receipt))

    def test_http_failures_expose_only_closed_content_safe_reasons(self) -> None:
        prompt_marker = "PRIVATE_PROMPT_MARKER_68"
        reflected_marker = "REFLECTED_INPUT_MARKER_68"
        cases = (
            (
                "organization budget", 403,
                {"error": {"code": 403, "message":
                 " \nBudget limit exceeded (monthly limit). Contact your org admin.\t "}},
                "organization_monthly_budget_exceeded",
                "organization monthly budget exceeded",
            ),
            (
                "generic permission", 403,
                {"error": {"code": 403, "message": "Provider permission detail"}},
                "key_permission_denied", "key permission denied",
            ),
            (
                "guardrail", 403,
                {"error": {"code": 403, "message": f"Request blocked: {reflected_marker}",
                 "metadata": {"error_type": "content_policy_violation",
                              "patterns": [reflected_marker],
                              "flagged_input": reflected_marker}},
                 "openrouter_metadata": {"summary": reflected_marker}},
                "guardrail_blocked", "guardrail blocked",
            ),
            (
                "malformed", 403, f"not-json {reflected_marker}",
                "unknown_http_error", "unknown HTTP error",
            ),
            (
                "mismatched envelope", 403,
                {"error": {"code": 401, "message": "Mismatched private detail"}},
                "unknown_http_error", "unknown HTTP error",
            ),
            (
                "insufficient credits", 402,
                {"error": {"code": 402, "message": "Private payment detail",
                 "metadata": {"error_type": "payment_required"}}},
                "insufficient_credits", "insufficient credits",
            ),
            (
                "rate limit", 429,
                {"error": {"code": 429, "message": "Private rate detail",
                 "metadata": {"error_type": "rate_limit_exceeded"}}},
                "rate_limited", "rate limited",
            ),
        )
        for name, status, body, reason, label in cases:
            with self.subTest(name=name):
                FixtureHandler.response_status = status
                FixtureHandler.response_body = body
                result = self.transport(prompt_marker)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                receipt_text = result.receipt_path.read_text()  # type: ignore[attr-defined]
                receipt = json.loads(receipt_text)
                self.assertEqual(receipt["failureKind"], "http_error")
                self.assertEqual(receipt["failureReason"], reason)
                self.assertEqual(
                    result.stderr,
                    f"### RUNNER FAILURE (z-ai/glm-5.2, HTTP {status}: {label})\n",
                )
                visible = result.stdout + result.stderr + receipt_text
                raw_body = body if isinstance(body, str) else json.dumps(body)
                for forbidden in (
                    prompt_marker, reflected_marker, raw_body, "flagged_input",
                    "openrouter_metadata", '"metadata"',
                    "Budget limit exceeded", "Contact your org admin",
                    "Provider permission detail", "Mismatched private detail",
                    "Private payment detail", "Private rate detail",
                ):
                    self.assertNotIn(forbidden, visible)

    def test_transport_keeps_bearer_value_out_of_curl_argv_and_environment(self) -> None:
        wrapper = WRAPPER.read_text()
        self.assertNotIn('-H "Authorization: Bearer $OPENROUTER_API_KEY"', wrapper)
        self.assertIn('-H "@$authorization_header_file"', wrapper)
        self.assertIn("unset OPENROUTER_API_KEY OPENROUTER_API_KEY_FILE", wrapper)
        result = self.direct("Review harmless public configuration.")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(FixtureHandler.contacts, 1)
        self.assertEqual(FixtureHandler.authorizations, ["Bearer test"])

    @unittest.skipUnless(Path("/proc").is_dir(), "requires Linux /proc")
    def test_live_curl_process_does_not_expose_bearer_value(self) -> None:
        exposed_forms = (b"Authorization: Bearer test", b"OPENROUTER_API_KEY=test")
        FixtureHandler.block_response = True
        results: list[subprocess.CompletedProcess[str]] = []
        worker = threading.Thread(
            target=lambda: results.append(self.direct("Review harmless configuration.")),
        )
        worker.start()
        try:
            self.assertTrue(FixtureHandler.request_seen.wait(timeout=5))
            observed = []
            for process in Path("/proc").iterdir():
                if not process.name.isdigit():
                    continue
                try:
                    cmdline = (process / "cmdline").read_bytes()
                    environment = (process / "environ").read_bytes()
                except (FileNotFoundError, PermissionError, ProcessLookupError):
                    continue
                if b"curl\0" not in cmdline or self.base.encode() not in cmdline:
                    continue
                observed.append(process.name)
                for exposed in exposed_forms:
                    self.assertNotIn(exposed, cmdline)
                    self.assertNotIn(exposed, environment)
            self.assertTrue(observed, "live OpenRouter curl process was not observable")
            self.assertEqual(
                FixtureHandler.authorizations, ["Bearer test"],
            )
        finally:
            FixtureHandler.release_response.set()
            worker.join(timeout=10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0].returncode, 0, results[0].stderr)

    def test_credential_shaped_payloads_contact_provider(self) -> None:
        result = self.direct("OPENROUTER_API_KEY=sk-or-v1-realistic-token-1234567890")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(FixtureHandler.contacts, 1)
        self.assertIn("sk-or-v1-realistic-token-1234567890", self.last_user_prompt())

        repo = self.init_repo()
        diff = (
            "diff --git a/allowed.txt b/allowed.txt\n"
            "--- a/allowed.txt\n+++ b/allowed.txt\n"
            "@@ -1 +1 @@\n-before\n+after"
        )
        result = self.run_pipeline(
            repo,
            diff,
            prompt="DATABASE_URL=postgres://admin:secret@private.example/db",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(FixtureHandler.contacts, 2)
        self.assertIn(
            "DATABASE_URL=postgres://admin:secret@private.example/db",
            self.last_user_prompt(),
        )

    def test_anthropic_slug_rejected_before_contact(self) -> None:
        result = subprocess.run([str(WRAPPER), "anthropic/claude-opus", "safe", "10"],
                                text=True, capture_output=True, env=self.env())
        self.assertEqual(result.returncode, 2)
        self.assertEqual(FixtureHandler.contacts, 0)

    def test_key_file_validation_remains_strict(self) -> None:
        key = self.root / "key"
        key.write_text("test\n")
        key.chmod(stat.S_IRUSR | stat.S_IWUSR)
        env = self.env()
        env.pop("OPENROUTER_API_KEY")
        env["OPENROUTER_API_KEY_FILE"] = str(key)
        ok = subprocess.run([str(WRAPPER), "z-ai/glm-5.2", "safe", "10"], env=env,
                            text=True, capture_output=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        contacts = FixtureHandler.contacts
        link = self.root / "key-link"
        link.symlink_to(key)
        env["OPENROUTER_API_KEY_FILE"] = str(link)
        bad = subprocess.run([str(WRAPPER), "z-ai/glm-5.2", "safe", "10"], env=env,
                             text=True, capture_output=True)
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(FixtureHandler.contacts, contacts)

    def init_repo(self, name: str = "repo") -> Path:
        repo = self.root / name
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "fixture@example.test"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Fixture"], check=True)
        (repo / "allowed.txt").write_text("before\n")
        (repo / "blocked.txt").write_text("blocked\n")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "fixture base"], check=True)
        return repo

    def run_pipeline(self, repo: Path, diff: str, env: dict[str, str] | None = None,
                     prompt: str = "Implement the bounded harmless fixture.",
                     attempt_receipt: Path | None = None) -> subprocess.CompletedProcess[str]:
        FixtureHandler.response_text = diff
        run_env = env or self.env()
        run_env.setdefault("OPENROUTER_EXEC_ALLOWED_PATHS", "allowed.txt")
        argv = [str(PIPELINE_EXEC), "--model", "z-ai/glm-5.2", "--timeout", "10"]
        if attempt_receipt is not None:
            argv += ["--attempt-receipt", str(attempt_receipt.relative_to(repo))]
        return subprocess.run(argv,
                              cwd=repo, input=prompt, text=True,
                              capture_output=True, env=run_env)

    def last_user_prompt(self) -> str:
        messages = FixtureHandler.requests[-1]["messages"]
        return next(message["content"] for message in messages
                    if message["role"] == "user")

    def test_pipeline_accepts_allowed_diff_and_emits_wrapper_evidence(self) -> None:
        repo = self.init_repo()
        (repo / "blocked.txt").write_text("UNRELATED_REPOSITORY_MARKER\n")
        subprocess.run(["git", "-C", str(repo), "add", "blocked.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "--amend", "--no-edit", "-q"], check=True)
        attempt_dir = repo / "attempts"
        attempt_dir.mkdir()
        attempt_receipt = attempt_dir / "success.json"
        task = "ORIGINAL_TASK_MARKER: change the sole allowed line."
        diff = "diff --git a/allowed.txt b/allowed.txt\n--- a/allowed.txt\n+++ b/allowed.txt\n@@ -1 +1 @@\n-before\n+after"
        result = self.run_pipeline(repo, diff, prompt=task,
                                   attempt_receipt=attempt_receipt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(FixtureHandler.contacts, 1)
        self.assertEqual((repo / "allowed.txt").read_text(), "after\n")
        outbound = self.last_user_prompt()
        self.assertIn(task, outbound)
        self.assertIn(
            "contract_digest: sha256:" + "a" * 64,
            outbound,
        )
        self.assertIn("contract_revision: 1", outbound)
        self.assertIn("EXACT ALLOWED PATHS:\nallowed.txt\n", outbound)
        self.assertIn("FILE: allowed.txt\nSTATE: PRESENT_AT_HEAD", outbound)
        self.assertIn("--- BEGIN EXACT COMMITTED CONTENT ---\nbefore\n", outbound)
        self.assertNotIn("blocked.txt", outbound)
        self.assertNotIn("UNRELATED_REPOSITORY_MARKER", outbound)
        self.assertIn("You have no filesystem, shell, command, tool, or repository access", outbound)
        for structural_line in ("diff --git", "---", "+++", "@@"):
            self.assertIn(structural_line, outbound)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["implementedBy"], "openrouter")
        self.assertEqual(receipt["contract_digest"], "sha256:" + "a" * 64)
        self.assertEqual(receipt["revision"], 1)
        self.assertEqual(receipt["actualModel"], "z-ai/glm-5.2")
        self.assertEqual(receipt["usage"]["total_tokens"], 18)
        self.assertGreaterEqual(receipt["durationSeconds"], 0)
        self.assertRegex(receipt["requestEnvelopeSha256"], r"^[0-9a-f]{64}$")
        commit_message = subprocess.check_output(
            ["git", "-C", str(repo), "log", "-1", "--format=%B"], text=True,
        )
        self.assertIn("ImplementedBy: openrouter", commit_message)
        retained = json.loads(attempt_receipt.read_text())
        self.assertEqual(retained["usage"]["total_tokens"], 18)
        self.assertEqual(retained["usage"]["cost"], 0.0042)
        serialized = json.dumps(receipt).lower()
        for forbidden in ("broker", "implement the bounded", "api_key", "secret", diff.lower()):
            self.assertNotIn(forbidden, serialized)

    def test_allowed_new_file_is_marked_absent_without_unrelated_context(self) -> None:
        repo = self.init_repo()
        (repo / "blocked.txt").write_text("NEW_FILE_UNRELATED_MARKER\n")
        subprocess.run(["git", "-C", str(repo), "add", "blocked.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "--amend", "--no-edit", "-q"], check=True)
        env = self.env()
        env["OPENROUTER_EXEC_ALLOWED_PATHS"] = "new.txt"
        diff = (
            "diff --git a/new.txt b/new.txt\nnew file mode 100644\n"
            "--- /dev/null\n+++ b/new.txt\n@@ -0,0 +1 @@\n+created"
        )

        result = self.run_pipeline(repo, diff, env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((repo / "new.txt").read_text(), "created\n")
        outbound = self.last_user_prompt()
        self.assertIn("FILE: new.txt\nSTATE: ABSENT_AT_HEAD (allowed new file)", outbound)
        self.assertNotIn("allowed.txt\nSTATE: PRESENT_AT_HEAD", outbound)
        self.assertNotIn("NEW_FILE_UNRELATED_MARKER", outbound)

    def test_unsafe_repository_context_is_rejected_before_provider_contact(self) -> None:
        cases = []

        def tracked_symlink(repo: Path, env: dict[str, str]) -> None:
            (repo / "allowed.txt").unlink()
            (repo / "allowed.txt").symlink_to("blocked.txt")
            subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "symlink"], check=True)

        def binary_blob(repo: Path, env: dict[str, str]) -> None:
            (repo / "allowed.txt").write_bytes(b"before\0after\n")
            subprocess.run(["git", "-C", str(repo), "add", "allowed.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "binary"], check=True)

        def escaping_path(repo: Path, env: dict[str, str]) -> None:
            env["OPENROUTER_EXEC_ALLOWED_PATHS"] = "../outside.txt"

        def unreadable_blob(repo: Path, env: dict[str, str]) -> None:
            blob = subprocess.check_output(
                ["git", "-C", str(repo), "rev-parse", "HEAD:allowed.txt"], text=True,
            ).strip()
            object_path = repo / ".git/objects" / blob[:2] / blob[2:]
            object_path.unlink()

        def unsupported_tree(repo: Path, env: dict[str, str]) -> None:
            directory = repo / "allowed-dir"
            directory.mkdir()
            (directory / "child.txt").write_text("child\n")
            subprocess.run(["git", "-C", str(repo), "add", "allowed-dir"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "tree"], check=True)
            env["OPENROUTER_EXEC_ALLOWED_PATHS"] = "allowed-dir"

        def over_limit(repo: Path, env: dict[str, str]) -> None:
            (repo / "allowed.txt").write_text("x" * 262144)
            subprocess.run(["git", "-C", str(repo), "add", "allowed.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "large"], check=True)

        cases.extend([
            ("symlink", tracked_symlink),
            ("binary", binary_blob),
            ("escaping", escaping_path),
            ("unreadable", unreadable_blob),
            ("unsupported", unsupported_tree),
            ("over-limit", over_limit),
        ])
        for index, (label, prepare) in enumerate(cases):
            with self.subTest(label=label):
                repo = self.init_repo(f"unsafe-{index}")
                env = self.env()
                prepare(repo, env)
                contacts = FixtureHandler.contacts
                result = self.run_pipeline(repo, "unused", env)
                self.assertEqual(result.returncode, 77, result.stderr)
                self.assertEqual(FixtureHandler.contacts, contacts)
                self.assertIn("repository context rejected", result.stderr)

    def test_pipeline_rejects_disallowed_path_before_application(self) -> None:
        repo = self.init_repo()
        diff = "diff --git a/blocked.txt b/blocked.txt\n--- a/blocked.txt\n+++ b/blocked.txt\n@@ -1 +1 @@\n-blocked\n+changed"
        result = self.run_pipeline(repo, diff)
        self.assertEqual(result.returncode, 77)
        self.assertEqual((repo / "blocked.txt").read_text(), "blocked\n")
        self.assertEqual(subprocess.check_output(["git", "-C", str(repo), "rev-list", "--count", "HEAD"], text=True).strip(), "1")

    def test_pipeline_rejects_pre_staged_paths_before_provider_contact(self) -> None:
        repo = self.init_repo()
        (repo / "blocked.txt").write_text("pre-staged\n")
        subprocess.run(["git", "-C", str(repo), "add", "blocked.txt"], check=True)
        contacts = FixtureHandler.contacts
        diff = ("diff --git a/allowed.txt b/allowed.txt\n--- a/allowed.txt\n"
                "+++ b/allowed.txt\n@@ -1 +1 @@\n-before\n+after")
        result = self.run_pipeline(repo, diff)
        self.assertEqual(result.returncode, 77)
        self.assertEqual(FixtureHandler.contacts, contacts)
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(repo), "rev-list", "--count", "HEAD"], text=True,
        ).strip(), "1")

    def test_pipeline_rejects_unstaged_edit_in_approved_file(self) -> None:
        repo = self.init_repo()
        (repo / "allowed.txt").write_text("one\ntwo\nthree\n")
        subprocess.run(["git", "-C", str(repo), "add", "allowed.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "--amend", "--no-edit", "-q"], check=True)
        (repo / "allowed.txt").write_text("one\ntwo\nlocal unrelated\n")
        contacts = FixtureHandler.contacts
        diff = ("diff --git a/allowed.txt b/allowed.txt\n--- a/allowed.txt\n"
                "+++ b/allowed.txt\n@@ -1,2 +1,2 @@\n-one\n+model\n two")
        result = self.run_pipeline(repo, diff)
        self.assertEqual(result.returncode, 77)
        self.assertEqual(FixtureHandler.contacts, contacts)
        self.assertIn("allowed-path-dirty", result.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(), "one\ntwo\nlocal unrelated\n")
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(repo), "rev-list", "--count", "HEAD"], text=True,
        ).strip(), "1")

    def test_pipeline_accepts_strict_key_file_without_env_key(self) -> None:
        repo = self.init_repo()
        key = self.root / "pipeline-key"
        key.write_text("test\n")
        key.chmod(0o600)
        env = self.env()
        env.pop("OPENROUTER_API_KEY")
        env["OPENROUTER_API_KEY_FILE"] = str(key)
        diff = ("diff --git a/allowed.txt b/allowed.txt\n--- a/allowed.txt\n"
                "+++ b/allowed.txt\n@@ -1 +1 @@\n-before\n+after")
        result = self.run_pipeline(repo, diff, env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((repo / "allowed.txt").read_text(), "after\n")

    def test_pipeline_rolls_back_when_commit_creation_fails(self) -> None:
        repo = self.init_repo()
        env = self.env()
        env["GIT_AUTHOR_NAME"] = ""
        diff = ("diff --git a/allowed.txt b/allowed.txt\n--- a/allowed.txt\n"
                "+++ b/allowed.txt\n@@ -1 +1 @@\n-before\n+after")
        result = self.run_pipeline(repo, diff, env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((repo / "allowed.txt").read_text(), "before\n")
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(repo), "status", "--porcelain"], text=True,
        ), "")
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(repo), "rev-list", "--count", "HEAD"], text=True,
        ).strip(), "1")

    def test_missing_or_invalid_key_falls_back_without_prompt(self) -> None:
        repo = self.init_repo()
        env = self.env()
        env.pop("OPENROUTER_API_KEY")
        missing = self.run_pipeline(repo, "unused", env)
        self.assertEqual(missing.returncode, 77)
        self.assertNotRegex(missing.stderr, r"approval|digest|batch|broker")
        key = self.root / "bad-key"
        key.write_text("test\n")
        key.chmod(0o644)
        env["OPENROUTER_API_KEY_FILE"] = str(key)
        invalid = self.run_pipeline(repo, "unused", env)
        self.assertEqual(invalid.returncode, 77)
        self.assertNotRegex(invalid.stderr, r"approve|question")

    def test_active_surfaces_have_no_approval_machinery(self) -> None:
        active = [
            REPO / "plugins/openrouter/commands/openrouter.md",
            REPO / "plugins/openrouter/agents/workflow/openrouter-agent-runner.md",
            REPO / "plugins/dm-review/skills/review/SKILL.md",
            REPO / "plugins/dm-review/skills/review/references/full-lane-dispatch.md",
            REPO / "plugins/model-router/skills/model-router/references/openrouter-write-adapter.sh",
            REPO / "plugins/model-router/skills/model-router/references/role-dispatch.sh",
        ]
        combined = "\n".join(path.read_text() for path in active)
        self.assertNotIn("exit 78", combined)
        self.assertNotIn("status\":\"approval_required", combined)
        self.assertNotIn("interim-operator-batch", combined)
        self.assertNotIn("exact-digest", combined)
        self.assertFalse((OPENROUTER / "skills/openrouter-delegate/references/runner-batch-authorization.sh").exists())
        self.assertFalse((OPENROUTER / "skills/openrouter-delegate/references/payload-authorization.sh").exists())
        # Availability resolution moved to the full-mode dispatch reference the
        # review skill loads; assert it there, not in the skill entry point.
        review = active[2].read_text()
        dispatch = active[3].read_text()
        self.assertNotIn('OPENROUTER_API_KEY_FILE', review)
        self.assertIn('full-lane-dispatch.md', review)
        self.assertIn('model-router owns every concrete participant', dispatch)
        self.assertIn('OPENROUTER_API_KEY_FILE', active[4].read_text())
        orchestrator = (REPO / "plugins/pipeline/agents/workflow/execution-orchestrator.md").read_text()
        self.assertNotIn('OPENROUTER_API_KEY_FILE', orchestrator)
        self.assertIn('role-dispatch.sh', orchestrator)
        self.assertIn('resolve-plugin-bundle', orchestrator)
        self.assertIn('--plugin model-router', orchestrator)

        direct = self.direct("Review harmless public configuration.", self.installed)
        self.assertEqual(direct.returncode, 0, direct.stderr)
        repo = self.init_repo("repo-no-broker")
        diff = ("diff --git a/allowed.txt b/allowed.txt\n--- a/allowed.txt\n"
                "+++ b/allowed.txt\n@@ -1 +1 @@\n-before\n+after")
        pipeline = self.run_pipeline(repo, diff)
        self.assertEqual(pipeline.returncode, 0, pipeline.stderr)


if __name__ == "__main__":
    unittest.main()
