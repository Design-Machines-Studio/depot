import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import detail_digest
from workflow_kernel.adapters.base import HostCapabilities, HostCapability
from workflow_kernel.adapters.host import capabilities_from_harness_profile
from workflow_kernel.schema import InvalidSchemaError


class HostCapabilityTests(unittest.TestCase):
    def test_harness_fixtures_declare_only_observed_dispatch_rails(self):
        expected = {
            "claude-code": {
                HostCapability.NATIVE_DISPATCH,
                HostCapability.COMPANION_DISPATCH,
                HostCapability.WRAPPER_DISPATCH,
                HostCapability.OPENROUTER_EXEC,
                HostCapability.CLAUDE_EXECUTION,
                HostCapability.CODEX_EXECUTION,
                HostCapability.OPENROUTER_EXECUTION,
            },
            "codex": {
                HostCapability.NATIVE_DISPATCH,
                HostCapability.WRAPPER_DISPATCH,
                HostCapability.OPENROUTER_EXEC,
                HostCapability.CLAUDE_EXECUTION,
                HostCapability.CODEX_EXECUTION,
                HostCapability.OPENROUTER_EXECUTION,
            },
            "generic": {
                HostCapability.WRAPPER_DISPATCH,
                HostCapability.OPENROUTER_EXEC,
                HostCapability.CLAUDE_EXECUTION,
                HostCapability.CODEX_EXECUTION,
                HostCapability.OPENROUTER_EXECUTION,
            },
        }
        for host, capabilities in expected.items():
            with self.subTest(host=host):
                fixture = capabilities_from_harness_profile(host)
                self.assertEqual(fixture.capabilities, frozenset(capabilities))
                self.assertEqual(fixture.transition_model_version, 1)
                self.assertEqual(fixture.evidence_model_version, 1)
                self.assertNotIn(HostCapability.SESSION_RESUME, fixture.capabilities)

    def test_unknown_host_capability_fails_with_stable_reason(self):
        with self.assertRaises(InvalidSchemaError) as raised:
            HostCapabilities("test", ("telepathy",))
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("unknown_capability_name"),
        )

    def test_duplicate_host_capabilities_fail_like_policy_schema(self):
        with self.assertRaises(InvalidSchemaError) as raised:
            HostCapabilities("test", (HostCapability.NATIVE_DISPATCH,
                                      HostCapability.NATIVE_DISPATCH))
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("duplicate_capability_name"),
        )

    def test_unknown_harness_role_kind_fails_closed(self):
        payload = {
            "hosts": {"test": {"roles": {"mystery": {"kind": "telepathy"}}}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "harness.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(InvalidSchemaError) as raised:
                capabilities_from_harness_profile("test", path)
        self.assertEqual(
            raised.exception.details["reason_code"],
            detail_digest("unknown_capability_name"),
        )

    def test_required_modules_import_in_clean_processes_without_cycles(self):
        root = str(Path(__file__).parents[1])
        environment = dict(os.environ, PYTHONPATH=root)
        statements = (
            "import workflow_kernel.policies",
            "import workflow_kernel.workflows",
            "import workflow_kernel.adapters",
            "from workflow_kernel.adapters import IsolationSelector, BuilderSessionManager",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                result = subprocess.run(
                    [sys.executable, "-c", statement], cwd="/tmp", env=environment,
                    capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
